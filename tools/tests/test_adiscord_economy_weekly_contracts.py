import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_economy_ai import (
    ai_assistance_contract_issues,
    ai_assistance_lifecycle_issues,
    ai_policy_contract_issues,
    automatic_borrow_flow_issues,
    debt_notification_flow_issues,
    debt_reconciler_issues,
    debt_transition_flow_issues,
    migration_contract_issues,
    policy_selector_issues,
    reachable_script_entries,
    research_policy_flow_issues,
    retired_capacity_boundary_issues,
    validate as validate_economy_ai,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_minor_optimization import (
    validate as validate_minor_optimization,
)


ROOT = Path(__file__).resolve().parents[2]
ON_ACTIONS = (ROOT / "common" / "on_actions" / "00_ADISCORD_on_actions.txt").read_text(
    encoding="utf-8-sig"
)
TRIGGERS = (
    ROOT / "common" / "scripted_triggers" / "ADISCORD_economy_triggers.txt"
).read_text(encoding="utf-8-sig")
EFFECTS = (
    ROOT / "common" / "scripted_effects" / "ADISCORD_economy_effects.txt"
).read_text(encoding="utf-8-sig")
MODIFIER_EFFECTS = (
    ROOT / "common" / "scripted_effects" / "ADISCORD_economy_modifier_effects.txt"
).read_text(encoding="utf-8-sig")
MODIFIER_DEFINITIONS = (
    ROOT
    / "common"
    / "modifier_definitions"
    / "00_ADISCORD_economy_modifiers_definition.txt"
).read_text(encoding="utf-8-sig")
TOKENS = (
    ROOT / "common" / "synchronized_dynamic_tokens" / "ADISCORD_tokens.txt"
).read_text(encoding="utf-8-sig")
MODIFIER_LOC = (
    ROOT / "localisation" / "russian" / "ADISCORD_economy_modifiers_l_russian.yml"
).read_text(encoding="utf-8-sig")
ECONOMY_LOC = (
    ROOT / "localisation" / "russian" / "ADISCORD_economy_l_russian.yml"
).read_text(encoding="utf-8-sig")
ECONOMY_LOC_EN_PATH = (
    ROOT / "localisation" / "english" / "ADISCORD_economy_l_english.yml"
)
ECONOMY_LOC_EN = (
    ECONOMY_LOC_EN_PATH.read_text(encoding="utf-8-sig")
    if ECONOMY_LOC_EN_PATH.exists()
    else ""
)
ECONOMY_EVENTS = (ROOT / "events" / "ADISCORD_economy_events.txt").read_text(
    encoding="utf-8-sig"
)
ECONOMY_IDEAS = (
    ROOT / "common" / "ideas" / "ADISCORD_economy_ideas.txt"
).read_text(encoding="utf-8-sig")
BUILDINGS = (ROOT / "common" / "buildings" / "00_buildings.txt").read_text(
    encoding="utf-8-sig"
)
DYNAMIC_MODIFIERS = (
    ROOT / "common" / "dynamic_modifiers" / "ADISCORD_economy_dynamic_modifiers.txt"
).read_text(encoding="utf-8-sig")
ECONOMY_AI = (
    ROOT / "common" / "ai_strategy" / "ADISCORD_economy_ai.txt"
).read_text(encoding="utf-8-sig")
SCRIPTED_GUI = (
    ROOT / "common" / "scripted_guis" / "ADISCORD_economy_scripted_gui.txt"
).read_text(encoding="utf-8-sig")
SCRIPTED_LOC = (
    ROOT
    / "common"
    / "scripted_localisation"
    / "ADISCORD_economy_scripted_loc.txt"
).read_text(encoding="utf-8-sig")
BUILDING_DOC = ROOT / "docs" / "economy" / "economic-buildings.md"
MODIFIER_DOC = ROOT / "docs" / "economy" / "economic-modifiers.md"


def block(text, name):
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block: {name}")
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index]
    raise AssertionError(f"unclosed block: {name}")


def assignment_blocks(text, name):
    """Return every balanced Clausewitz assignment block with *name*."""

    matches = re.finditer(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    bodies = []
    for match in matches:
        opening = text.find("{", match.start())
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(text[opening + 1 : index])
                    break
        else:
            raise AssertionError(f"unclosed block: {name}")
    return bodies


def unique_block(text, name):
    bodies = assignment_blocks(text, name)
    if len(bodies) != 1:
        raise AssertionError(f"expected one block {name}, found {len(bodies)}")
    return bodies[0]


def unique_defined_text(text, name):
    bodies = [
        body
        for body in assignment_blocks(text, "defined_text")
        if re.search(rf"(?m)^\s*name\s*=\s*{re.escape(name)}\s*$", body)
    ]
    if len(bodies) != 1:
        raise AssertionError(f"expected one defined_text {name}, found {len(bodies)}")
    return bodies[0]


def top_level_blocks(text):
    """Parse top-level scripted definitions without accepting shadow copies."""

    definitions = {}
    for match in re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_.@-]*)\s*=\s*\{", text):
        name = match.group(1)
        opening = text.find("{", match.start())
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    definitions.setdefault(name, []).append(text[opening + 1 : index])
                    break
        else:
            raise AssertionError(f"unclosed top-level block: {name}")
    return definitions


def reachable_script_blocks(texts, roots):
    def flatten(entry):
        values = []

        def visit(entries):
            for child in entries:
                values.append(child.key)
                if isinstance(child.value, list):
                    visit(child.value)
                else:
                    values.append(child.value)

        visit(entry.value)
        return " ".join(values)

    return {
        name: flatten(entry)
        for name, entry in reachable_script_entries(tuple(texts), tuple(roots)).items()
    }


WEEKLY_ACCOUNTING_ROOTS = (
    "ADISCORD_economy_weekly_update",
    "ADISCORD_economy_prepare_weekly_country",
    "ADISCORD_economy_light_update",
    "ADISCORD_economy_apply_weekly_balance",
)

WEEKLY_FORBIDDEN_EXACT_TOKENS = {
    "has_idea",
    "every_country",
    "any_country",
    "any_enemy_country",
    "random_country",
    "every_state",
    "any_state",
    "every_owned_state",
    "all_owned_state",
    "random_owned_state",
    "every_controlled_state",
    "num_of_civilian_factories",
    "num_of_available_civilian_factories",
    "num_of_military_factories",
    "num_of_available_military_factories",
    "num_of_naval_factories",
}

WEEKLY_FORBIDDEN_DEFINITIONS = {
    "ADISCORD_economy_initialize_country",
    "ADISCORD_economy_initialize_variables",
    "ADISCORD_economy_migrate_schema",
    "ADISCORD_economy_monthly_update",
    "ADISCORD_economy_yearly_update",
    "ADISCORD_economy_full_refresh",
    "ADISCORD_economy_full_refresh_if_needed",
    "ADISCORD_economy_recount_economic_buildings",
    "ADISCORD_economy_count_buildings",
    "ADISCORD_economy_update_model_and_cycle",
    "ADISCORD_economy_calculate_development_multiplier",
    "ADISCORD_economy_recalculate_policy_modifiers",
    "ADISCORD_economy_calculate_final_modifier_factors",
    "ADISCORD_economy_apply_visible_modifier_definition_factors",
    "ADISCORD_economy_refresh_spending_ideas",
    "ADISCORD_economy_refresh_policy_previews",
    "ADISCORD_economy_preview_tax_policy",
    "ADISCORD_economy_preview_army_policy",
    "ADISCORD_economy_preview_research_policy",
    "ADISCORD_economy_preview_social_policy",
    "ADISCORD_economy_update_gui",
}

WEEKLY_FORBIDDEN_TOKEN_PREFIXES = (
    "building_level@",
    "damaged_building_level@",
    "non_damaged_building_level",
    "modifier@",
)

PERSISTENT_VARIABLE_BLOCK_WRITE_OPERATORS = {
    "set_variable",
    "add_to_variable",
    "subtract_from_variable",
    "multiply_variable",
    "divide_variable",
    "clamp_variable",
}

PERSISTENT_VARIABLE_SCALAR_WRITE_OPERATORS = {
    "clear_variable",
    "round_variable",
}

PERSISTENT_VARIABLE_READ_OPERATORS = {
    "check_variable",
    "has_variable",
}


def persistent_variable_write_targets(entry):
    """Return persistent variables mutated by one parsed Clausewitz entry."""

    if entry.key in PERSISTENT_VARIABLE_READ_OPERATORS:
        return set()
    if entry.key in PERSISTENT_VARIABLE_SCALAR_WRITE_OPERATORS:
        if isinstance(entry.value, str):
            return {entry.value}
        return set()
    if entry.key not in PERSISTENT_VARIABLE_BLOCK_WRITE_OPERATORS:
        return set()
    if not isinstance(entry.value, list):
        return set()

    targets = set()
    named_target = _entry_scalar(entry.value, "var")
    if named_target:
        targets.add(named_target)
    reserved_arguments = {"var", "value", "min", "max", "compare", "tooltip"}
    targets.update(
        child.key for child in entry.value if child.key not in reserved_arguments
    )
    return targets


def weekly_reachability_issues(texts, roots=WEEKLY_ACCOUNTING_ROOTS):
    """Classify heavy operations in the parsed transitive weekly graph."""

    issues = []
    reachable = reachable_script_entries(tuple(texts), tuple(roots))
    for name, definition in reachable.items():
        if name in WEEKLY_FORBIDDEN_DEFINITIONS:
            issues.append(f"{name}: forbidden weekly facade")
        keys = []
        scalar_values = []
        for _, entry in _walk_parsed(definition.value):
            keys.append(entry.key)
            if isinstance(entry.value, str):
                scalar_values.append(entry.value)
        offenders = sorted(
            {
                token
                for token in keys
                if token in WEEKLY_FORBIDDEN_EXACT_TOKENS
                or any(token.startswith(prefix) for prefix in WEEKLY_FORBIDDEN_TOKEN_PREFIXES)
            }
            | {
                token
                for token in scalar_values
                if token.startswith("num_of_")
                or any(token.startswith(prefix) for prefix in WEEKLY_FORBIDDEN_TOKEN_PREFIXES)
            }
        )
        if offenders:
            issues.append(f"{name}: {', '.join(offenders)}")
    return issues


def task7_weekly_on_action_issues(
    on_actions_text, effects_text, modifier_effects_text, triggers_text
):
    """Require the live weekly hook to expose only the guarded accounting facade."""

    try:
        parsed_on_actions = parse_clausewitz(on_actions_text)
        source_texts = (effects_text, modifier_effects_text, triggers_text)
        parsed_sources = tuple(parse_clausewitz(text) for text in source_texts)
    except ValueError as error:
        return [f"weekly hook parse failure: {error}"]

    issues = []
    on_action_owners = [
        entry
        for entry in parsed_on_actions
        if entry.key == "on_actions" and isinstance(entry.value, list)
    ]
    if len(on_action_owners) != 1:
        return [f"weekly hook requires one on_actions owner, found {len(on_action_owners)}"]
    weekly_hooks = [
        entry
        for entry in on_action_owners[0].value
        if entry.key == "on_weekly" and isinstance(entry.value, list)
    ]
    if len(weekly_hooks) != 1:
        return [f"weekly hook requires one on_weekly body, found {len(weekly_hooks)}"]
    weekly_hook = weekly_hooks[0]
    effects = [
        entry
        for entry in weekly_hook.value
        if entry.key == "effect" and isinstance(entry.value, list)
    ]
    if len(effects) != 1 or len(weekly_hook.value) != 1:
        issues.append("on_weekly does not have one country-scoped effect owner")

    hook_entries = list(_walk_parsed(weekly_hook.value))
    weekly_calls = [
        entry
        for _, entry in hook_entries
        if entry.key == "ADISCORD_economy_weekly_update" and entry.value == "yes"
    ]
    gate_calls = [
        entry
        for _, entry in hook_entries
        if entry.key == "ADISCORD_economy_should_weekly_update"
        and entry.value == "yes"
    ]
    if len(weekly_calls) != 1:
        issues.append(
            f"on_weekly must call the weekly facade exactly once, found {len(weekly_calls)}"
        )
    if len(gate_calls) != 1:
        issues.append(
            f"on_weekly must call the weekly gate exactly once, found {len(gate_calls)}"
        )

    guarded_facades = []
    if effects:
        for conditional in effects[0].value:
            if conditional.key != "if" or not isinstance(conditional.value, list):
                continue
            direct_limits = [
                entry
                for entry in conditional.value
                if entry.key == "limit" and isinstance(entry.value, list)
            ]
            direct_facades = [
                entry
                for entry in conditional.value
                if entry.key == "ADISCORD_economy_weekly_update"
                and entry.value == "yes"
            ]
            if len(direct_limits) != 1 or len(direct_facades) != 1:
                continue
            direct_gates = [
                entry
                for entry in direct_limits[0].value
                if entry.key == "ADISCORD_economy_should_weekly_update"
                and entry.value == "yes"
            ]
            if len(direct_gates) == 1 and len(direct_limits[0].value) == 1:
                guarded_facades.append(direct_facades[0])
    if len(guarded_facades) != 1 or (
        weekly_calls and guarded_facades[0] is not weekly_calls[0]
    ):
        issues.append("weekly facade is not owned by its exact country gate")

    source_definitions = {
        entry.key
        for parsed in parsed_sources
        for entry in parsed
        if isinstance(entry.value, list)
    }
    callable_adiscord_entries = {
        entry.key
        for _, entry in hook_entries
        if entry.key.startswith("ADISCORD_")
        and (entry.value == "yes" or isinstance(entry.value, list))
    }
    graph_roots = sorted(
        {
            name for name in callable_adiscord_entries if name in source_definitions
        }
    )
    allowed_roots = {
        "ADISCORD_economy_should_weekly_update",
        "ADISCORD_economy_weekly_update",
    }
    unexpected_roots = sorted(callable_adiscord_entries - allowed_roots)
    if unexpected_roots:
        issues.append(
            "on_weekly contains an extra scripted sibling: "
            + ", ".join(unexpected_roots)
        )

    direct_offenders = sorted(
        {
            entry.key
            for _, entry in hook_entries
            if entry.key in WEEKLY_FORBIDDEN_EXACT_TOKENS
            or any(
                entry.key.startswith(prefix)
                for prefix in WEEKLY_FORBIDDEN_TOKEN_PREFIXES
            )
        }
    )
    if direct_offenders:
        issues.append(
            "on_weekly contains a forbidden direct operation: "
            + ", ".join(direct_offenders)
        )

    if graph_roots:
        try:
            issues.extend(weekly_reachability_issues(source_texts, tuple(graph_roots)))
        except AssertionError as error:
            issues.append(f"weekly hook graph is incomplete: {error}")
    return issues


def task7_schema_fifteen_cache_migration_issues(text):
    """Bind the one-shot Task 7 cache upgrade after the Task 6 migration."""

    try:
        migration = _parsed_definition(text, "ADISCORD_economy_migrate_schema")
        defaults = _parsed_definition(text, "ADISCORD_economy_set_default_values")
    except (AssertionError, ValueError) as error:
        return [f"schema 15 cache migration is missing: {error}"]

    issues = []
    schema_fourteen = [
        entry
        for entry in migration.value
        if entry.key == "if"
        and _exact_direct_check_set(
            entry,
            [("ADISCORD_economy_schema_version", "14", "less_than")],
        )
    ]
    schema_fifteen = [
        entry
        for entry in migration.value
        if entry.key == "if"
        and _exact_direct_check_set(
            entry,
            [("ADISCORD_economy_schema_version", "15", "less_than")],
        )
    ]
    if len(schema_fourteen) != 1 or len(schema_fifteen) != 1:
        return [
            "schema 15 cache upgrade requires one exact owner after one schema 14 owner"
        ]
    owner = schema_fifteen[0]
    if migration.value.index(schema_fourteen[0]) >= migration.value.index(owner):
        issues.append("schema 15 cache upgrade runs before the Task 6 schema 14 migration")

    def signature(entry):
        if entry.key == "set_variable" and isinstance(entry.value, list):
            return (
                entry.key,
                _entry_scalar(entry.value, "var"),
                _entry_scalar(entry.value, "value"),
            )
        return (entry.key, entry.value)

    actual_sequence = [
        signature(entry) for entry in owner.value if entry.key != "limit"
    ]
    expected_sequence = [
        (
            "set_variable",
            "ADISCORD_economy_weekly_source_cache_ready",
            "0",
        ),
        ("set_variable", "ADISCORD_economy_weekly_ready", "0"),
        ("set_variable", "ADISCORD_economy_needs_full_refresh", "1"),
        ("ADISCORD_economy_full_refresh_if_needed", "yes"),
        ("set_variable", "ADISCORD_economy_schema_version", "15"),
    ]
    if actual_sequence != expected_sequence:
        issues.append(
            "schema 15 cache upgrade is not invalidate, request, refresh, then complete"
        )

    schema_fifteen_checks = [
        entry
        for _, entry in _walk_parsed(migration.value)
        if entry.key == "check_variable"
        and isinstance(entry.value, list)
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_schema_version"
        and _entry_scalar(entry.value, "value") == "15"
    ]
    schema_fifteen_writes = [
        entry
        for _, entry in _walk_parsed(migration.value)
        if entry.key == "set_variable"
        and isinstance(entry.value, list)
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_schema_version"
        and _entry_scalar(entry.value, "value") == "15"
    ]
    if len(schema_fifteen_checks) != 1 or len(schema_fifteen_writes) != 1:
        issues.append("schema 15 guard or completion watermark is duplicated or missing")

    direct_fallbacks = [
        entry
        for entry in migration.value
        if entry.key == "ADISCORD_economy_full_refresh_if_needed"
        and entry.value == "yes"
    ]
    if (
        len(direct_fallbacks) != 1
        or migration.value.index(direct_fallbacks[0]) <= migration.value.index(owner)
    ):
        issues.append("schema migration lacks one final bounded dirty-refresh fallback")

    default_schema = [
        entry
        for entry in defaults.value
        if entry.key == "set_variable"
        and isinstance(entry.value, list)
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_schema_version"
    ]
    if not (
        len(default_schema) == 1
        and _entry_scalar(default_schema[0].value, "value") == "15"
    ):
        issues.append("new countries do not start at schema 15")
    return issues


def task7_cache_invalidation_issues(
    effects_text, modifier_effects_text, triggers_text=TRIGGERS
):
    """Require stale weekly sources to become ineligible until a full rebuild."""

    try:
        dirty = _parsed_definition(effects_text, "ADISCORD_economy_mark_dirty")
        full = _parsed_definition(effects_text, "ADISCORD_economy_full_refresh")
        factory = _parsed_definition(
            effects_text, "ADISCORD_economy_cache_weekly_factory_sources"
        )
        recalculate = _parsed_definition(
            modifier_effects_text, "ADISCORD_economy_recalculate_policy_modifiers"
        )
        policy = _parsed_definition(
            modifier_effects_text, "ADISCORD_economy_cache_weekly_policy_sources"
        )
    except (AssertionError, ValueError) as error:
        return [f"weekly cache invalidation owner is missing: {error}"]

    issues = []

    def signature(entry):
        if entry.key == "set_variable" and isinstance(entry.value, list):
            return (
                entry.key,
                _entry_scalar(entry.value, "var"),
                _entry_scalar(entry.value, "value"),
            )
        return (entry.key, entry.value)

    dirty_sequence = [signature(entry) for entry in dirty.value]
    if dirty_sequence != [
        (
            "set_variable",
            "ADISCORD_economy_weekly_source_cache_ready",
            "0",
        ),
        ("set_variable", "ADISCORD_economy_weekly_ready", "0"),
        ("set_variable", "ADISCORD_economy_needs_full_refresh", "1"),
        ("ADISCORD_economy_update_gui", "yes"),
    ]:
        issues.append("dirty invalidation does not disable weekly caches before requesting refresh")

    full_sequence = [signature(entry) for entry in full.value]
    if full_sequence != [
        ("ADISCORD_economy_recount_economic_buildings", "yes"),
        ("ADISCORD_economy_cache_weekly_factory_sources", "yes"),
        ("ADISCORD_economy_recalculate_policy_modifiers", "yes"),
        ("ADISCORD_economy_recalculate_treasury_cap", "yes"),
        (
            "set_variable",
            "ADISCORD_economy_weekly_source_cache_ready",
            "1",
        ),
        ("ADISCORD_economy_clear_dirty", "yes"),
    ]:
        issues.append("full refresh exposes readiness before every source and factor rebuild")

    factory_sources = {
        "ADISCORD_economy_cached_civilian_factories": "num_of_civilian_factories",
        "ADISCORD_economy_cached_available_civilian_factories": "num_of_available_civilian_factories",
        "ADISCORD_economy_cached_military_factories": "num_of_military_factories",
        "ADISCORD_economy_cached_available_military_factories": "num_of_available_military_factories",
        "ADISCORD_economy_cached_naval_factories": "num_of_naval_factories",
    }
    actual_factory_sources = {
        _entry_scalar(entry.value, "var"): _entry_scalar(entry.value, "value")
        for entry in factory.value
        if entry.key == "set_variable" and isinstance(entry.value, list)
    }
    if actual_factory_sources != factory_sources or len(factory.value) != 5:
        issues.append("factory source refresh is not the exact five-source rebuild")

    policy_source_calls = [
        entry
        for _, entry in _walk_parsed(policy.value)
        if entry.key.startswith("ADISCORD_economy_has_") and entry.value == "yes"
    ]
    policy_zeroes = [
        entry
        for entry in policy.value
        if entry.key == "set_variable"
        and isinstance(entry.value, list)
        and str(_entry_scalar(entry.value, "var") or "").startswith(
            "ADISCORD_economy_cached_"
        )
        and _entry_scalar(entry.value, "value") == "0"
    ]
    if len(policy_source_calls) != 19 or len(policy_zeroes) != 19:
        issues.append("policy/law source refresh is not the exact nineteen-source rebuild")

    recalculate_calls = [
        entry
        for entry in recalculate.value
        if entry.key
        in {
            "ADISCORD_economy_cache_weekly_policy_sources",
            "ADISCORD_economy_calculate_final_modifier_factors",
        }
        and entry.value == "yes"
    ]
    if not (
        [entry.key for entry in recalculate_calls]
        == [
            "ADISCORD_economy_cache_weekly_policy_sources",
            "ADISCORD_economy_calculate_final_modifier_factors",
        ]
        and recalculate.value[-1] is recalculate_calls[-1]
    ):
        issues.append("policy source cache and final factors do not rebuild before readiness")

    targeted_roots = (
        "ADISCORD_economy_finish_targeted_policy_refresh",
        "ADISCORD_economy_refresh_tax_policy",
        "ADISCORD_economy_refresh_army_policy",
        "ADISCORD_economy_refresh_research_policy",
        "ADISCORD_economy_refresh_social_policy",
    )
    forbidden_targeted_descendants = {
        "ADISCORD_economy_mark_dirty",
        "ADISCORD_economy_full_refresh",
        "ADISCORD_economy_full_refresh_if_needed",
        "ADISCORD_economy_cache_weekly_factory_sources",
        "ADISCORD_economy_cache_weekly_policy_sources",
        "ADISCORD_economy_recalculate_policy_modifiers",
        "ADISCORD_economy_calculate_final_modifier_factors",
        "ADISCORD_economy_recount_economic_buildings",
        "ADISCORD_economy_clear_dirty",
    }
    targeted_sources = (effects_text, modifier_effects_text, triggers_text)
    for name in targeted_roots:
        try:
            reachable = reachable_script_entries(targeted_sources, (name,))
        except AssertionError as error:
            issues.append(str(error))
            continue
        escaped = sorted(set(reachable) & forbidden_targeted_descendants)
        if escaped:
            issues.append(
                f"{name} escapes its targeted dependency refresh through "
                + ", ".join(escaped)
            )
        readiness_writers = []
        readiness_variables = {
            "ADISCORD_economy_weekly_source_cache_ready",
            "ADISCORD_economy_weekly_ready",
        }
        for definition_name, definition in reachable.items():
            for _, entry in _walk_parsed(definition.value):
                if persistent_variable_write_targets(entry) & readiness_variables:
                    readiness_writers.append(definition_name)
                    break
        if readiness_writers:
            issues.append(
                f"{name} reaches source-readiness writers: "
                + ", ".join(sorted(readiness_writers))
            )
    return issues


def numeric_values(text, key):
    return [
        float(value)
        for value in re.findall(
            rf"\b{re.escape(key)}\s*=\s*(-?\d+(?:\.\d+)?)\b",
            text,
        )
    ]


def policy_multiplier_rows(text, target_variable, output_variables):
    """Extract exact, condition-owned rows from one policy multiplier table."""

    rows = {}
    for branch_name in ("if", "else_if"):
        for body in assignment_blocks(text, branch_name):
            operations = tuple(
                (operation, variable, float(value))
                for operation, variable, value in re.findall(
                    r"\b(multiply_variable|add_to_variable)\s*=\s*\{\s*var\s*=\s*"
                    r"(ADISCORD_economy_[A-Za-z0-9_]+)\s+value\s*=\s*"
                    r"(-?\d+(?:\.\d+)?)\s*\}",
                    body,
                )
                if variable in output_variables
            )
            if not operations:
                continue
            owner = re.search(
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*{re.escape(target_variable)}"
                r"\s+value\s*=\s*([1-5])\s+compare\s*=\s*equals\s*\}",
                body,
            )
            if not owner:
                continue
            level = int(owner.group(1))
            if level in rows:
                raise AssertionError(f"duplicate policy multiplier row: {level}")
            rows[level] = operations
    return rows


def tax_refresh_macro_flow_issues(text):
    """Validate that tax macro work is owned by an actual income-change branch."""

    issues = []
    refresh = unique_block(text, "ADISCORD_economy_refresh_tax_policy")
    saved_income = "ADISCORD_economy_tax_refresh_saved_income_temp"
    save_pattern = (
        r"set_temp_variable\s*=\s*\{\s*var\s*=\s*"
        + re.escape(saved_income)
        + r"\s+value\s*=\s*ADISCORD_economy_monthly_income\s*\}"
    )
    save_matches = list(re.finditer(save_pattern, refresh))
    if len(save_matches) != 1:
        issues.append("tax refresh must cache old monthly income exactly once")

    macro_call = "ADISCORD_economy_calculate_macro_indicators = yes"
    recalculate_call = "ADISCORD_economy_recalculate_tax_dependent_income = yes"
    finish_call = "ADISCORD_economy_finish_targeted_policy_refresh = yes"
    if refresh.count(macro_call) != 1:
        issues.append("tax refresh must contain exactly one macro call")
    if refresh.count(recalculate_call) != 1:
        issues.append("tax refresh must recalculate tax-dependent income exactly once")
    if refresh.count(finish_call) != 1:
        issues.append("tax refresh must reach the targeted tail exactly once")

    owners = [
        body
        for body in assignment_blocks(refresh, "if")
        if macro_call in body
    ]
    if len(owners) != 1:
        issues.append("macro call must be owned by exactly one if branch")
    else:
        exact_changed_limit = (
            r"limit\s*=\s*\{\s*NOT\s*=\s*\{\s*check_variable\s*=\s*\{\s*"
            r"var\s*=\s*ADISCORD_economy_monthly_income\s+value\s*=\s*"
            + re.escape(saved_income)
            + r"\s+compare\s*=\s*equals\s*\}\s*\}\s*\}"
        )
        if not re.search(exact_changed_limit, owners[0]):
            issues.append("macro branch must test current income NOT equals cached old income")

    ordered_tokens = (
        save_matches[0].group(0) if len(save_matches) == 1 else "__missing_save__",
        recalculate_call,
        macro_call,
        finish_call,
    )
    positions = [refresh.find(token) for token in ordered_tokens]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        issues.append("tax refresh must save, recalculate, conditionally update macro, then finish")
    return issues


def _parsed_definition(text, name):
    matches = [
        entry
        for entry in parse_clausewitz(text)
        if entry.key == name and isinstance(entry.value, list)
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one parsed definition {name}, found {len(matches)}")
    return matches[0]


def _walk_parsed(entries, ancestors=()):
    for entry in entries:
        yield ancestors, entry
        if isinstance(entry.value, list):
            yield from _walk_parsed(entry.value, ancestors + (entry,))


def _entry_scalar(entries, key):
    return next(
        (
            entry.value
            for entry in entries
            if entry.key == key and isinstance(entry.value, str)
        ),
        None,
    )


def _exact_direct_check_set(branch, expected):
    if not isinstance(branch.value, list):
        return False
    limits = [
        entry.value
        for entry in branch.value
        if entry.key == "limit" and isinstance(entry.value, list)
    ]
    if len(limits) != 1 or len(limits[0]) != len(expected):
        return False
    actual = []
    for check in limits[0]:
        if check.key != "check_variable" or not isinstance(check.value, list):
            return False
        if len(check.value) != 3:
            return False
        actual.append(
            (
                _entry_scalar(check.value, "var"),
                _entry_scalar(check.value, "value"),
                _entry_scalar(check.value, "compare"),
            )
        )
    return sorted(actual) == sorted(expected)


def _exact_direct_variable_write(branch, operation, variable, value):
    if not isinstance(branch.value, list):
        return False
    matches = []
    for entry in branch.value:
        if entry.key != operation or not isinstance(entry.value, list):
            continue
        if _entry_scalar(entry.value, "var") != variable:
            continue
        matches.append(entry)
    return (
        len(matches) == 1
        and len(matches[0].value) == 2
        and _entry_scalar(matches[0].value, "value") == str(value)
    )


def task6_debt_state_sequence_issues(text):
    """Validate one exact settlement state machine, including branch ownership."""

    issues = list(debt_transition_flow_issues(text))
    try:
        definition = _parsed_definition(
            text, "ADISCORD_economy_update_debt_state_after_settlement"
        )
    except AssertionError as error:
        return issues + [str(error)]

    branches = [
        entry for entry in definition.value if entry.key in {"if", "else_if", "else"}
    ]
    expected_keys = ["if", "else", "if", "else", "if"]
    if [entry.key for entry in branches] != expected_keys:
        issues.append("transition branches are not two streak pairs plus one fallback owner")
        return issues

    emergency, emergency_reset, default, default_reset, fallback = branches
    if not _exact_direct_check_set(
        emergency,
        [("ADISCORD_economy_interest_share_income", "40", "greater_than_or_equals")],
    ):
        issues.append("emergency streak owner is not exactly interest share >= 40")
    if not _exact_direct_variable_write(
        emergency, "add_to_variable", "ADISCORD_economy_debt_emergency_streak", 1
    ):
        issues.append("emergency streak does not advance exactly once")
    emergency_thresholds = [
        entry
        for entry in emergency.value
        if entry.key == "if" and isinstance(entry.value, list)
    ]
    if (
        len(emergency_thresholds) != 1
        or not _exact_direct_check_set(
            emergency_thresholds[0],
            [("ADISCORD_economy_debt_emergency_streak", "4", "greater_than_or_equals")],
        )
        or not _exact_direct_variable_write(
            emergency_thresholds[0], "set_variable", "ADISCORD_economy_debt_state", 3
        )
    ):
        issues.append("emergency state is not owned by the fourth settlement")
    if not _exact_direct_variable_write(
        emergency_reset, "set_variable", "ADISCORD_economy_debt_emergency_streak", 0
    ):
        issues.append("emergency streak reset is missing or not directly owned")

    if not _exact_direct_check_set(
        default,
        [
            ("ADISCORD_economy_interest_share_income", "40", "greater_than_or_equals"),
            ("ADISCORD_economy_weekly_balance", "0", "less_than"),
        ],
    ):
        issues.append("default streak owner is not exactly share >= 40 and balance < 0")
    if not _exact_direct_variable_write(
        default, "add_to_variable", "ADISCORD_economy_debt_default_streak", 1
    ):
        issues.append("default streak does not advance exactly once")
    default_thresholds = [
        entry
        for entry in default.value
        if entry.key == "if" and isinstance(entry.value, list)
    ]
    if (
        len(default_thresholds) != 1
        or not _exact_direct_check_set(
            default_thresholds[0],
            [("ADISCORD_economy_debt_default_streak", "13", "greater_than_or_equals")],
        )
        or not _exact_direct_variable_write(
            default_thresholds[0], "set_variable", "ADISCORD_economy_debt_state", 4
        )
    ):
        issues.append("default state is not owned by the thirteenth deficit settlement")
    if not _exact_direct_variable_write(
        default_reset, "set_variable", "ADISCORD_economy_debt_default_streak", 0
    ):
        issues.append("default streak reset is missing or not directly owned")

    if not _exact_direct_check_set(
        fallback,
        [
            ("ADISCORD_economy_debt_default_streak", "13", "less_than"),
            ("ADISCORD_economy_debt_emergency_streak", "4", "less_than"),
        ],
    ):
        issues.append("lower-state chain can overwrite an earned emergency/default")
        return issues
    state_branches = [
        entry
        for entry in fallback.value
        if entry.key in {"if", "else_if", "else"} and isinstance(entry.value, list)
    ]
    if [entry.key for entry in state_branches] != ["if", "else_if", "else"]:
        issues.append("lower-state chain is not crisis, strain, healthy")
        return issues
    state_contract = (
        ([("ADISCORD_economy_interest_share_income", "25", "greater_than_or_equals")], 2),
        ([("ADISCORD_economy_interest_share_income", "10", "greater_than_or_equals")], 1),
    )
    for branch, (checks, target) in zip(state_branches[:2], state_contract):
        if not _exact_direct_check_set(branch, checks):
            issues.append(f"state {target} has the wrong direct threshold owner")
        if not _exact_direct_variable_write(
            branch, "set_variable", "ADISCORD_economy_debt_state", target
        ):
            issues.append(f"state {target} is not the branch's only direct state write")
    if not _exact_direct_variable_write(
        state_branches[2], "set_variable", "ADISCORD_economy_debt_state", 0
    ):
        issues.append("healthy fallback does not set state 0 directly")

    write_operations = {
        "set_variable", "add_to_variable", "subtract_from_variable",
        "multiply_variable", "divide_variable", "clamp_variable", "clear_variable",
    }
    expected_counts = {
        "ADISCORD_economy_debt_state": 5,
        "ADISCORD_economy_debt_emergency_streak": 3,
        "ADISCORD_economy_debt_default_streak": 3,
    }
    for variable, expected_count in expected_counts.items():
        actual = 0
        for _, entry in _walk_parsed(definition.value):
            if entry.key not in write_operations:
                continue
            if entry.key == "clear_variable":
                owned = entry.value == variable
            else:
                owned = (
                    isinstance(entry.value, list)
                    and _entry_scalar(entry.value, "var") == variable
                )
            actual += int(owned)
        if actual != expected_count:
            issues.append(f"{variable} has {actual} writes, expected {expected_count}")
    return issues


def task6_debt_state_authority_issues(effects_text, localisation_text):
    """Keep persistent state authoritative over the compatibility mirror and UI."""

    issues = []
    try:
        compatibility = unique_block(
            effects_text, "ADISCORD_economy_update_debt_crisis_level"
        )
    except AssertionError as error:
        return [str(error)]

    mirror_writes = re.findall(
        r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_crisis_level"
        r"\s+value\s*=\s*([^\s}]+)\s*\}",
        compatibility,
    )
    if mirror_writes != ["ADISCORD_economy_debt_state"]:
        issues.append("debt_crisis_level is not one exact mirror write from debt_state")
    if re.search(r"\b(?:add_to|clamp|subtract_from)_variable\b", compatibility):
        issues.append("compatibility mirror independently mutates the legacy tier")

    exact_clamp = (
        "clamp_variable = { var = ADISCORD_economy_debt_crisis_level "
        "min = 0 max = 4 }"
    )
    if effects_text.count(exact_clamp) != 1:
        issues.append("debt_crisis_level does not have exactly one 0..4 clamp owner")

    try:
        debt_tooltip = localisation_value(localisation_text, "ADISCORD_economy_debt_tt")
    except AssertionError as error:
        return issues + [str(error)]
    if "?ADISCORD_economy_debt_state|0" not in debt_tooltip:
        issues.append("debt tooltip does not expose persistent debt_state")
    if "?ADISCORD_economy_debt_crisis_level" in debt_tooltip:
        issues.append("debt tooltip still exposes the compatibility tier")
    for visible_metric in (
        "?ADISCORD_economy_interest_rate|1",
        "?ADISCORD_economy_weekly_interest|2",
        "?ADISCORD_economy_interest_share_income|1",
        "?ADISCORD_economy_debt_pressure|0",
    ):
        if visible_metric not in debt_tooltip:
            issues.append(f"debt tooltip hides {visible_metric}")
    return issues


def task6_policy_preview_persistent_state_issues(text):
    """Preview arithmetic may round-trip metrics, never persistent debt state."""

    reachable = reachable_script_blocks(
        (text,), ("ADISCORD_economy_preview_tax_policy",)
    )
    if "ADISCORD_economy_preview_tax_policy" not in reachable:
        return ["tax policy preview is missing"]
    graph = "\n".join(reachable.values())
    writes = set(
        re.findall(
            r"(?:set_variable|add_to_variable|subtract_from_variable|"
            r"multiply_variable|divide_variable|clamp_variable|clear_variable)"
            r"\s+(?:var\s+)?(ADISCORD_economy_[A-Za-z0-9_]+)",
            graph,
        )
    )
    persistent = {
        "ADISCORD_economy_debt_state",
        "ADISCORD_economy_last_notified_debt_state",
        "ADISCORD_economy_debt_emergency_streak",
        "ADISCORD_economy_debt_default_streak",
        "ADISCORD_economy_pending_debt_notification_kind",
    }
    return [
        f"tax policy preview writes persistent state: {', '.join(sorted(writes & persistent))}"
    ] if writes & persistent else []


def task6_schema_fourteen_migration_issues(text):
    """Validate safe migration without manufacturing old streak evidence."""

    try:
        migration = _parsed_definition(text, "ADISCORD_economy_migrate_schema")
    except (AssertionError, ValueError) as error:
        return [f"schema 14 migration is missing: {error}"]
    issues = []
    owners = [
        entry
        for entry in migration.value
        if entry.key == "if"
        and _exact_direct_check_set(
            entry,
            [("ADISCORD_economy_schema_version", "14", "less_than")],
        )
    ]
    if len(owners) != 1:
        return [f"schema 14 requires one exact top-level owner, found {len(owners)}"]
    owner = owners[0]
    assert isinstance(owner.value, list)
    schema_fourteen_checks = [
        (ancestors, entry)
        for ancestors, entry in _walk_parsed(migration.value)
        if entry.key == "check_variable"
        and isinstance(entry.value, list)
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_schema_version"
        and _entry_scalar(entry.value, "value") == "14"
    ]
    if len(schema_fourteen_checks) != 1:
        issues.append("schema 14 guard is duplicated or has a second unowned check")

    variable_write_operations = {
        "set_variable", "add_to_variable", "subtract_from_variable",
        "multiply_variable", "divide_variable", "clamp_variable", "clear_variable",
    }
    state_operations = [
        (ancestors, entry)
        for ancestors, entry in _walk_parsed(owner.value)
        if entry.key in variable_write_operations
        and (
            entry.value == "ADISCORD_economy_debt_state"
            or (
                isinstance(entry.value, list)
                and _entry_scalar(entry.value, "var") == "ADISCORD_economy_debt_state"
            )
        )
    ]
    global_state_operations = [
        (ancestors, entry)
        for ancestors, entry in _walk_parsed(migration.value)
        if entry.key in variable_write_operations
        and (
            entry.value == "ADISCORD_economy_debt_state"
            or (
                isinstance(entry.value, list)
                and _entry_scalar(entry.value, "var") == "ADISCORD_economy_debt_state"
            )
        )
    ]
    direct_state_zero = [
        entry
        for entry in owner.value
        if entry.key == "set_variable"
        and isinstance(entry.value, list)
        and len(entry.value) == 2
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_debt_state"
        and _entry_scalar(entry.value, "value") == "0"
    ]
    mapping_branches = [
        entry
        for entry in owner.value
        if entry.key in {"if", "else_if"}
        and isinstance(entry.value, list)
        and any(
            child.key == "set_variable"
            and isinstance(child.value, list)
            and _entry_scalar(child.value, "var") == "ADISCORD_economy_debt_state"
            for child in entry.value
        )
    ]
    mapping_ok = bool(
        len(direct_state_zero) == 1
        and len(mapping_branches) == 2
        and [branch.key for branch in mapping_branches] == ["if", "else_if"]
        and owner.value.index(direct_state_zero[0]) < owner.value.index(mapping_branches[0])
        and owner.value.index(mapping_branches[0]) + 1 == owner.value.index(mapping_branches[1])
        and _exact_direct_check_set(
            mapping_branches[0],
            [("ADISCORD_economy_debt_crisis_level", "2", "greater_than_or_equals")],
        )
        and _exact_direct_variable_write(
            mapping_branches[0], "set_variable", "ADISCORD_economy_debt_state", 2
        )
        and _exact_direct_check_set(
            mapping_branches[1],
            [("ADISCORD_economy_debt_crisis_level", "1", "greater_than_or_equals")],
        )
        and _exact_direct_variable_write(
            mapping_branches[1], "set_variable", "ADISCORD_economy_debt_state", 1
        )
        and len(state_operations) == 3
        and len(global_state_operations) == 3
        and all(ancestors and ancestors[0] is owner for ancestors, _ in global_state_operations)
        and {
            _entry_scalar(entry.value, "value")
            for _, entry in state_operations
            if entry.key == "set_variable" and isinstance(entry.value, list)
        } == {"0", "1", "2"}
    )
    if not mapping_ok:
        issues.append("schema 14 safe state 0/1/2 mapping lacks exact branch ownership")

    exact_writes = {
        "ADISCORD_economy_debt_emergency_streak": "0",
        "ADISCORD_economy_debt_default_streak": "0",
        "ADISCORD_economy_pending_debt_notification_kind": "0",
        "ADISCORD_economy_pending_debt_notification_amount": "0",
        "ADISCORD_economy_pending_debt_notification_previous_state": (
            "ADISCORD_economy_debt_state"
        ),
        "ADISCORD_economy_pending_debt_notification_new_state": (
            "ADISCORD_economy_debt_state"
        ),
        "ADISCORD_economy_last_notified_debt_state": "ADISCORD_economy_debt_state",
    }
    initialization_entries = []
    initialization_by_variable = {}
    for variable, value in exact_writes.items():
        direct = [
            entry
            for entry in owner.value
            if entry.key == "set_variable"
            and isinstance(entry.value, list)
            and _entry_scalar(entry.value, "var") == variable
        ]
        all_owned = [
            (ancestors, entry)
            for ancestors, entry in _walk_parsed(migration.value)
            if entry.key in variable_write_operations
            and (
                entry.value == variable
                or (
                    isinstance(entry.value, list)
                    and _entry_scalar(entry.value, "var") == variable
                )
            )
        ]
        if not (
            len(direct) == len(all_owned) == 1
            and all_owned[0][0]
            and all_owned[0][0][0] is owner
            and all_owned[0][1] is direct[0]
            and len(direct[0].value) == 2
            and _entry_scalar(direct[0].value, "value") == value
        ):
            issues.append(f"schema 14 does not initialize {variable} exactly to {value}")
        else:
            initialization_entries.append(direct[0])
            initialization_by_variable[variable] = direct[0]
    previous_state_cache = initialization_by_variable.get(
        "ADISCORD_economy_pending_debt_notification_previous_state"
    )
    new_state_cache = initialization_by_variable.get(
        "ADISCORD_economy_pending_debt_notification_new_state"
    )
    last_notified = initialization_by_variable.get("ADISCORD_economy_last_notified_debt_state")
    if not (
        mapping_branches
        and previous_state_cache is not None
        and new_state_cache is not None
        and last_notified is not None
        and owner.value.index(mapping_branches[-1])
        < owner.value.index(previous_state_cache)
        < owner.value.index(new_state_cache)
        < owner.value.index(last_notified)
    ):
        issues.append("schema 14 state caches and notification watermark do not follow mapping")

    direct_clear_first = [
        entry
        for entry in owner.value
        if entry.key == "clear_variable"
        and entry.value == "ADISCORD_economy_first_loan_notified"
    ]
    all_clear_first = [
        (ancestors, entry)
        for ancestors, entry in _walk_parsed(migration.value)
        if entry.key == "clear_variable"
        and entry.value == "ADISCORD_economy_first_loan_notified"
    ]
    marker_owners = [
        entry
        for entry in owner.value
        if entry.key == "if"
        and isinstance(entry.value, list)
        and _exact_direct_variable_write(
            entry, "set_variable", "ADISCORD_economy_first_loan_notified", 1
        )
    ]
    all_first_markers = [
        (ancestors, entry)
        for ancestors, entry in _walk_parsed(migration.value)
        if entry.key in variable_write_operations
        and isinstance(entry.value, list)
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_first_loan_notified"
    ]
    first_loan_ok = bool(
        len(direct_clear_first) == 1
        and len(all_clear_first) == 1
        and len(all_clear_first[0][0]) == 1
        and all_clear_first[0][0][0] is owner
        and all_clear_first[0][1] is direct_clear_first[0]
        and len(marker_owners) == 1
        and len(all_first_markers) == 1
        and all_first_markers[0][0]
        and all_first_markers[0][0][0] is owner
        and _exact_direct_check_set(
            marker_owners[0],
            [("ADISCORD_economy_debt", "0", "greater_than")],
        )
        and owner.value.index(direct_clear_first[0]) < owner.value.index(marker_owners[0])
    )
    if not first_loan_ok:
        issues.append("schema 14 first-loan marker does not preserve existing debt safely")

    completion = [
        entry
        for _, entry in _walk_parsed(migration.value)
        if entry.key == "set_variable"
        and isinstance(entry.value, list)
        and len(entry.value) == 2
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_schema_version"
        and _entry_scalar(entry.value, "value") == "14"
    ]
    direct_completion = [
        entry
        for entry in owner.value
        if entry.key == "set_variable"
        and isinstance(entry.value, list)
        and len(entry.value) == 2
        and _entry_scalar(entry.value, "var") == "ADISCORD_economy_schema_version"
        and _entry_scalar(entry.value, "value") == "14"
    ]
    completion_ok = len(completion) == len(direct_completion) == 1
    if completion_ok:
        completion_position = owner.value.index(direct_completion[0])
        required_before_completion = list(initialization_entries)
        if mapping_branches:
            required_before_completion.append(mapping_branches[-1])
        if marker_owners:
            required_before_completion.append(marker_owners[0])
        completion_ok = bool(
            required_before_completion
            and max(owner.value.index(entry) for entry in required_before_completion)
            < completion_position
            and completion_position == len(owner.value) - 2
            and _exact_direct_variable_write(
                owner,
                "set_variable",
                "ADISCORD_economy_needs_full_refresh",
                1,
            )
            and owner.value[-1].key == "set_variable"
            and isinstance(owner.value[-1].value, list)
            and _entry_scalar(owner.value[-1].value, "var")
            == "ADISCORD_economy_needs_full_refresh"
        )
    if not completion_ok:
        issues.append("schema 14 completion write is missing, unowned, duplicated, or early")
    return issues


def task6_notification_queue_issues(text):
    """Validate first-loan/state precedence and the single human event sink."""

    issues = list(debt_notification_flow_issues(text))
    try:
        queue = unique_block(text, "ADISCORD_economy_queue_debt_notification")
    except AssertionError as error:
        return issues + [str(error)]

    exact_tokens = {
        "pending reset": (
            "set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 0 }"
        ),
        "new-state cache": (
            "set_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = ADISCORD_economy_debt_state }"
        ),
        "first-loan kind": (
            "set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 1 }"
        ),
        "first-loan marker": (
            "set_variable = { var = ADISCORD_economy_first_loan_notified value = 1 }"
        ),
        "human event": "country_event = { id = ADISCORD_economy.3 }",
    }
    for label, token in exact_tokens.items():
        if queue.count(token) != 1:
            issues.append(f"{label} is not unique in the notification queue")

    first_owner = re.search(
        r"if\s*=\s*\{\s*limit\s*=\s*\{\s*"
        r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_pending_debt_notification_amount"
        r"\s+value\s*=\s*0\s+compare\s*=\s*greater_than\s*\}\s*"
        r"NOT\s*=\s*\{\s*has_variable\s*=\s*ADISCORD_economy_first_loan_notified\s*\}\s*\}",
        queue,
    )
    if first_owner is None:
        issues.append("first-loan kind lacks its exact positive amount and unseen owner")

    upward_owner = re.search(
        r"if\s*=\s*\{\s*limit\s*=\s*\{\s*"
        r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_state"
        r"\s+value\s*=\s*ADISCORD_economy_pending_debt_notification_previous_state"
        r"\s+compare\s*=\s*greater_than\s*\}\s*"
        r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_state"
        r"\s+value\s*=\s*ADISCORD_economy_last_notified_debt_state"
        r"\s+compare\s*=\s*greater_than\s*\}\s*\}",
        queue,
    )
    if upward_owner is None:
        issues.append("state notice lacks exact upward and last-notified ownership")

    mapping_positions = []
    for state, kind in ((4, 5), (3, 4), (2, 3), (1, 2)):
        mapping = re.search(
            rf"check_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_debt_state"
            rf"\s+value\s*=\s*{state}\s+compare\s*=\s*equals\s*\}}"
            rf"(?:(?!check_variable).)*set_variable\s*=\s*\{{\s*var\s*=\s*"
            rf"ADISCORD_economy_pending_debt_notification_kind\s+value\s*=\s*{kind}\s*\}}",
            queue,
            re.DOTALL,
        )
        if mapping is None:
            issues.append(f"state {state} does not map uniquely to notification kind {kind}")
        else:
            mapping_positions.append(mapping.start())
    first_kind = queue.find(exact_tokens["first-loan kind"])
    if mapping_positions and not (first_kind >= 0 and first_kind < min(mapping_positions)):
        issues.append("state severity does not override the earlier first-loan kind")

    human_owner = re.search(
        r"if\s*=\s*\{\s*limit\s*=\s*\{\s*is_ai\s*=\s*no\s+"
        r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_pending_debt_notification_kind"
        r"\s+value\s*=\s*0\s+compare\s*=\s*greater_than\s*\}\s*\}"
        r"\s*country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_economy\.3\s*\}\s*\}",
        queue,
    )
    if human_owner is None:
        issues.append("event sink is not exactly human-only with a positive pending kind")
    if text.count("country_event = { id = ADISCORD_economy.3 }") != 1:
        issues.append("debt modal has more than one dispatch sink")
    if "ADISCORD_economy_show_auto_loan_popup" in queue:
        issues.append("obsolete automatic custom popup is still active")
    return issues


def duplicate_direct_key_blocks(text, key):
    """Return parsed block paths that declare ``key`` more than once directly."""

    offenders = []
    for ancestors, entry in _walk_parsed(parse_clausewitz(text)):
        if not isinstance(entry.value, list):
            continue
        if sum(child.key == key for child in entry.value) > 1:
            offenders.append("/".join(node.key for node in ancestors + (entry,)))
    return offenders


def debt_metric_flow_issues(text):
    """Validate the exact interest-pressure arithmetic and its data-flow order."""

    try:
        definition = _parsed_definition(text, "ADISCORD_economy_calculate_debt_metrics")
    except AssertionError as error:
        return [str(error)]

    walked = list(_walk_parsed(definition.value))
    writes = []
    write_keys = {
        "set_variable",
        "add_to_variable",
        "subtract_from_variable",
        "multiply_variable",
        "divide_variable",
        "clamp_variable",
    }
    for position, (ancestors, entry) in enumerate(walked):
        if entry.key not in write_keys or not isinstance(entry.value, list):
            continue
        writes.append(
            (
                position,
                ancestors,
                entry,
                _entry_scalar(entry.value, "var"),
                _entry_scalar(entry.value, "value"),
                _entry_scalar(entry.value, "min"),
                _entry_scalar(entry.value, "max"),
            )
        )

    def signatures(variable):
        return [
            (entry.key, value, minimum, maximum)
            for _, _, entry, target, value, minimum, maximum in writes
            if target == variable
        ]

    expected = {
        "ADISCORD_economy_debt_income_denominator_temp": [
            ("set_variable", "ADISCORD_economy_monthly_income", None, None),
            ("multiply_variable", "12", None, None),
            ("set_variable", "1", None, None),
        ],
        "ADISCORD_economy_debt_income_ratio": [
            ("set_variable", "ADISCORD_economy_debt", None, None),
            ("multiply_variable", "100", None, None),
            (
                "divide_variable",
                "ADISCORD_economy_debt_income_denominator_temp",
                None,
                None,
            ),
        ],
        "ADISCORD_economy_weekly_interest": [
            ("set_variable", "ADISCORD_economy_debt_service", None, None),
            ("multiply_variable", "3", None, None),
            ("divide_variable", "13", None, None),
        ],
        "ADISCORD_economy_interest_income_denominator_temp": [
            ("set_variable", "ADISCORD_economy_monthly_income", None, None),
            ("multiply_variable", "3", None, None),
            ("divide_variable", "13", None, None),
            ("set_variable", "0.1", None, None),
        ],
        "ADISCORD_economy_interest_share_income": [
            ("set_variable", "ADISCORD_economy_weekly_interest", None, None),
            ("multiply_variable", "100", None, None),
            (
                "divide_variable",
                "ADISCORD_economy_interest_income_denominator_temp",
                None,
                None,
            ),
        ],
        "ADISCORD_economy_interest_pressure_temp": [
            ("set_variable", "ADISCORD_economy_interest_share_income", None, None),
            ("multiply_variable", "1.50", None, None),
        ],
        "ADISCORD_economy_debt_streak_pressure_temp": [
            ("set_variable", "ADISCORD_economy_deficit_streak", None, None),
            ("multiply_variable", "2", None, None),
        ],
        "ADISCORD_economy_debt_pressure": [
            ("set_variable", "ADISCORD_economy_debt_income_ratio", None, None),
            ("multiply_variable", "0.20", None, None),
            (
                "add_to_variable",
                "ADISCORD_economy_interest_pressure_temp",
                None,
                None,
            ),
            (
                "add_to_variable",
                "ADISCORD_economy_debt_streak_pressure_temp",
                None,
                None,
            ),
            ("clamp_variable", None, "0", "100"),
        ],
    }

    issues = []
    for variable, wanted in expected.items():
        found = signatures(variable)
        if found != wanted:
            issues.append(f"{variable}: expected {wanted}, found {found}")

    def floor_is_exact(variable, threshold):
        floor_writes = [
            (ancestors, entry)
            for _, ancestors, entry, target, value, _, _ in writes
            if target == variable and entry.key == "set_variable" and value == threshold
        ]
        if len(floor_writes) != 1:
            return False
        ancestors, _ = floor_writes[0]
        if not ancestors or ancestors[-1].key != "if":
            return False
        branch = ancestors[-1]
        limit = next(
            (
                child
                for child in branch.value
                if child.key == "limit" and isinstance(child.value, list)
            ),
            None,
        )
        if limit is None:
            return False
        if len(limit.value) != 1:
            return False
        check = limit.value[0]
        if check.key != "check_variable" or not isinstance(check.value, list):
            return False
        fields = [entry.key for entry in check.value]
        return (
            len(fields) == 3
            and set(fields) == {"var", "value", "compare"}
            and _entry_scalar(check.value, "var") == variable
            and _entry_scalar(check.value, "value") == threshold
            and _entry_scalar(check.value, "compare") == "less_than"
        )

    for variable, threshold in (
        ("ADISCORD_economy_debt_income_denominator_temp", "1"),
        ("ADISCORD_economy_interest_income_denominator_temp", "0.1"),
    ):
        if not floor_is_exact(variable, threshold):
            issues.append(f"{variable}: denominator floor is missing, reversed, or dead")

    calls = {}
    for name in (
        "ADISCORD_economy_calculate_creditworthiness",
        "ADISCORD_economy_calculate_interest_rate",
        "ADISCORD_economy_calculate_debt_service_amount",
        "ADISCORD_economy_update_debt_crisis_level",
    ):
        found = [
            (position, ancestors)
            for position, (ancestors, entry) in enumerate(walked)
            if entry.key == name and entry.value == "yes"
        ]
        if len(found) != 1 or found[0][1]:
            issues.append(f"{name}: expected one direct call")
        else:
            calls[name] = found[0][0]

    def first_write(variable, operation):
        return next(
            (
                position
                for position, _, entry, target, _, _, _ in writes
                if target == variable and entry.key == operation
            ),
            None,
        )

    order = [
        first_write("ADISCORD_economy_debt_income_ratio", "divide_variable"),
        calls.get("ADISCORD_economy_calculate_creditworthiness"),
        calls.get("ADISCORD_economy_calculate_interest_rate"),
        calls.get("ADISCORD_economy_calculate_debt_service_amount"),
        first_write("ADISCORD_economy_weekly_interest", "set_variable"),
        first_write("ADISCORD_economy_interest_share_income", "set_variable"),
        first_write("ADISCORD_economy_debt_pressure", "set_variable"),
        calls.get("ADISCORD_economy_update_debt_crisis_level"),
    ]
    if any(position is None for position in order) or order != sorted(order):
        issues.append("debt metric order is not ratio -> credit/rate -> interest/share -> pressure -> tier")

    if signatures("ADISCORD_economy_debt"):
        issues.append("debt metrics may not write or clamp stored principal")
    return issues


def manual_borrowing_availability_issues(triggers_text, scripted_loc_text):
    """Match each visible loan-block reason to the ordered runtime gate."""

    def condition_signatures(entries, negated=False):
        signatures = []
        for entry in entries:
            if entry.key == "NOT" and isinstance(entry.value, list):
                signatures.extend(condition_signatures(entry.value, not negated))
            elif entry.key in {"OR", "AND"} and isinstance(entry.value, list):
                signatures.append(
                    (
                        entry.key,
                        negated,
                        tuple(condition_signatures(entry.value)),
                    )
                )
            elif entry.key == "check_variable" and isinstance(entry.value, list):
                signatures.append(
                    (
                        "check_variable",
                        negated,
                        _entry_scalar(entry.value, "var"),
                        _entry_scalar(entry.value, "value"),
                        _entry_scalar(entry.value, "compare"),
                    )
                )
            elif isinstance(entry.value, str):
                signatures.append((entry.key, negated, entry.value))
        return signatures

    model_allowed = (
        "OR",
        False,
        (
            ("ADISCORD_economy_model_is_fragmented", True, "yes"),
            ("ADISCORD_economy_model_allows_oligarchic_deals", False, "yes"),
        ),
    )
    model_blocked = (
        ("ADISCORD_economy_model_is_fragmented", False, "yes"),
        ("ADISCORD_economy_model_allows_oligarchic_deals", True, "yes"),
    )
    expected = {
        "internal": (
            "ADISCORD_economy_can_take_debt",
            "GetADISCORDInternalBondsAvailabilityLoc",
            (
                model_allowed,
                ("check_variable", False, "ADISCORD_economy_recent_debt", "1", "less_than"),
                ("ADISCORD_economy_has_treasury_room_50", False, "yes"),
                ("check_variable", False, "ADISCORD_economy_creditworthiness", "25", "greater_than_or_equals"),
                ("check_variable", False, "ADISCORD_economy_interest_share_income", "25", "less_than"),
                ("check_variable", False, "ADISCORD_economy_debt_pressure", "75", "less_than"),
                ("check_variable", False, "ADISCORD_economy_debt_crisis_level", "4", "less_than"),
            ),
            (
                (model_blocked, "ADISCORD_economy_loan_blocked_model"),
                ((("check_variable", False, "ADISCORD_economy_recent_debt", "1", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_cooldown"),
                ((("ADISCORD_economy_has_treasury_room_50", True, "yes"),), "ADISCORD_economy_loan_blocked_treasury_room"),
                ((("check_variable", False, "ADISCORD_economy_creditworthiness", "25", "less_than"),), "ADISCORD_economy_loan_blocked_internal_creditworthiness"),
                ((("check_variable", False, "ADISCORD_economy_interest_share_income", "25", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_interest_share_internal"),
                ((("check_variable", False, "ADISCORD_economy_debt_pressure", "75", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_pressure"),
                ((("check_variable", False, "ADISCORD_economy_debt_crisis_level", "4", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_default"),
            ),
            "ADISCORD_economy_loan_available_internal",
        ),
        "external": (
            "ADISCORD_economy_can_take_external_loan",
            "GetADISCORDExternalLoanAvailabilityLoc",
            (
                model_allowed,
                ("check_variable", False, "ADISCORD_economy_recent_debt", "1", "less_than"),
                ("ADISCORD_economy_has_treasury_room_50", False, "yes"),
                ("check_variable", False, "ADISCORD_economy_creditworthiness", "35", "greater_than_or_equals"),
                ("check_variable", False, "ADISCORD_economy_interest_share_income", "20", "less_than"),
                ("check_variable", False, "ADISCORD_economy_debt_pressure", "75", "less_than"),
                ("check_variable", False, "ADISCORD_economy_debt_crisis_level", "3", "less_than"),
            ),
            (
                (model_blocked, "ADISCORD_economy_loan_blocked_model"),
                ((("check_variable", False, "ADISCORD_economy_recent_debt", "1", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_cooldown"),
                ((("ADISCORD_economy_has_treasury_room_50", True, "yes"),), "ADISCORD_economy_loan_blocked_treasury_room"),
                ((("check_variable", False, "ADISCORD_economy_creditworthiness", "35", "less_than"),), "ADISCORD_economy_loan_blocked_creditworthiness"),
                ((("check_variable", False, "ADISCORD_economy_interest_share_income", "20", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_interest_share_external"),
                ((("check_variable", False, "ADISCORD_economy_debt_pressure", "75", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_pressure"),
                ((("check_variable", False, "ADISCORD_economy_debt_crisis_level", "3", "greater_than_or_equals"),), "ADISCORD_economy_loan_blocked_external_risk"),
            ),
            "ADISCORD_economy_loan_available_external",
        ),
    }

    issues = []
    parsed_loc = parse_clausewitz(scripted_loc_text)
    for label, (trigger_name, selector_name, gates, reasons, available) in expected.items():
        try:
            trigger = _parsed_definition(triggers_text, trigger_name)
        except AssertionError as error:
            issues.append(str(error))
            continue
        found_gates = tuple(condition_signatures(trigger.value))
        if found_gates != gates:
            issues.append(f"{label}: runtime gates expected {gates}, found {found_gates}")

        selectors = [
            entry
            for entry in parsed_loc
            if entry.key == "defined_text"
            and isinstance(entry.value, list)
            and _entry_scalar(entry.value, "name") == selector_name
        ]
        if len(selectors) != 1:
            issues.append(f"{label}: expected one selector {selector_name}")
            continue
        found_reasons = []
        for entry in selectors[0].value:
            if entry.key != "text" or not isinstance(entry.value, list):
                continue
            trigger_block = next(
                (
                    child
                    for child in entry.value
                    if child.key == "trigger" and isinstance(child.value, list)
                ),
                None,
            )
            reason = _entry_scalar(entry.value, "localization_key")
            found_reasons.append(
                (
                    tuple(condition_signatures(trigger_block.value))
                    if trigger_block is not None
                    else (),
                    reason,
                )
            )
        wanted_reasons = reasons + (((), available),)
        if tuple(found_reasons) != wanted_reasons:
            issues.append(
                f"{label}: selector reason order expected {wanted_reasons}, found {tuple(found_reasons)}"
            )
    return issues


def localisation_key_set(text):
    return set(re.findall(r"(?m)^\s*([A-Za-z0-9_.-]+):\d*\s+", text))


def localisation_value(text, key):
    match = re.search(
        rf'(?m)^\s*{re.escape(key)}:\d*\s+"((?:[^"\\]|\\.)*)"\s*$',
        text,
    )
    if not match:
        raise AssertionError(f"missing localisation value: {key}")
    return match.group(1)


class EconomySemanticFixtureTests(unittest.TestCase):
    MIGRATION = """
ADISCORD_economy_migrate_schema = {
    set_variable = { var = ADISCORD_economy_research_spending_mode value = ADISCORD_economy_construction_spending_mode }
    clear_variable = ADISCORD_economy_construction_spending_mode
    clear_variable = ADISCORD_economy_construction_budget_change_cooldown
    remove_ideas = {
        ADISCORD_economy_construction_spending_1
        ADISCORD_economy_construction_spending_2
        ADISCORD_economy_construction_spending_3
        ADISCORD_economy_construction_spending_4
        ADISCORD_economy_construction_spending_5
    }
}
"""
    ASSISTANCE_IDEAS = """
ideas = { hidden_ideas = {
 ADISCORD_economy_ai_assistance_base = { allowed = { always = no } allowed_civil_war = { always = yes } removal_cost = -1 modifier = { ADISCORD_economy_overall_income_factor = 0.05 industrial_capacity_factory = 0.05 } }
 ADISCORD_economy_ai_assistance_civil_war = { allowed = { always = no } allowed_civil_war = { always = yes } removal_cost = -1 modifier = { supply_consumption_factor = -0.10 } }
 ADISCORD_economy_ai_assistance_retreat = { allowed = { always = no } allowed_civil_war = { always = yes } removal_cost = -1 modifier = { army_defence_factor = 0.05 } }
} }
"""
    ASSISTANCE_EFFECT = """
ADISCORD_economy_refresh_ai_assistance = {
 set_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 0 }
 if = { limit = { has_variable = ADISCORD_economy_simulation_tier } set_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = ADISCORD_economy_simulation_tier } }
 if = { limit = { is_ai = yes } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 10 } }
 if = { limit = { has_global_flag = ADISCORD_vorkerland_collapse_wars_started } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 100 } }
 if = { limit = { has_global_flag = ADISCORD_vorkerland_collapse_finished } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 150 } }
 if = { limit = { has_country_flag = ADISCORD_vorkerland_conflict_spirits_finalized } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 200 } }
 if = { limit = { has_war = yes } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 400 } }
 if = { limit = { surrender_progress > 0.35 } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 800 } }
 if = {
  limit = { OR = { NOT = { has_variable = ADISCORD_economy_ai_assistance_signature } check_variable = { var = ADISCORD_economy_ai_assistance_signature value = ADISCORD_economy_ai_assistance_signature_temp compare = not_equals } } }
  remove_ideas = ADISCORD_economy_ai_assistance_base
  remove_ideas = ADISCORD_economy_ai_assistance_civil_war
  remove_ideas = ADISCORD_economy_ai_assistance_retreat
  if = { limit = { ADISCORD_economy_ai_assistance_is_eligible = yes } add_ideas = ADISCORD_economy_ai_assistance_base }
  if = { limit = { ADISCORD_economy_ai_assistance_civil_war_active = yes } add_ideas = ADISCORD_economy_ai_assistance_civil_war }
  if = { limit = { ADISCORD_economy_ai_assistance_retreat_active = yes } add_ideas = ADISCORD_economy_ai_assistance_retreat }
  ADISCORD_economy_refresh_ai_assistance_income_cache = yes
  set_variable = { var = ADISCORD_economy_ai_assistance_signature value = ADISCORD_economy_ai_assistance_signature_temp }
 }
}
"""
    ASSISTANCE_TRIGGERS = """
ADISCORD_economy_ai_assistance_is_eligible = {
 is_ai = yes
 check_variable = { var = ADISCORD_economy_simulation_tier value = 1 compare = greater_than_or_equals }
 check_variable = { var = ADISCORD_economy_simulation_tier value = 2 compare = less_than_or_equals }
}
ADISCORD_economy_ai_assistance_civil_war_active = {
 ADISCORD_economy_ai_assistance_is_eligible = yes
 has_global_flag = ADISCORD_vorkerland_collapse_wars_started
 NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }
 has_country_flag = ADISCORD_vorkerland_conflict_spirits_finalized
 has_war = yes
}
ADISCORD_economy_ai_assistance_retreat_active = {
 ADISCORD_economy_ai_assistance_civil_war_active = yes
 surrender_progress > 0.35
}
ADISCORD_economy_ai_assistance_needs_monthly_evaluation = {
 OR = {
  ADISCORD_economy_ai_assistance_is_eligible = yes
  has_idea = ADISCORD_economy_ai_assistance_base
  has_idea = ADISCORD_economy_ai_assistance_civil_war
  has_idea = ADISCORD_economy_ai_assistance_retreat
 }
}
"""
    DEBT_METRICS = """
ADISCORD_economy_calculate_debt_metrics = {
 set_variable = { var = ADISCORD_economy_debt_income_denominator_temp value = ADISCORD_economy_monthly_income }
 multiply_variable = { var = ADISCORD_economy_debt_income_denominator_temp value = 12 }
 if = { limit = { check_variable = { var = ADISCORD_economy_debt_income_denominator_temp value = 1 compare = less_than } }
  set_variable = { var = ADISCORD_economy_debt_income_denominator_temp value = 1 }
 }
 set_variable = { var = ADISCORD_economy_debt_income_ratio value = ADISCORD_economy_debt }
 multiply_variable = { var = ADISCORD_economy_debt_income_ratio value = 100 }
 divide_variable = { var = ADISCORD_economy_debt_income_ratio value = ADISCORD_economy_debt_income_denominator_temp }
 ADISCORD_economy_calculate_creditworthiness = yes
 ADISCORD_economy_calculate_interest_rate = yes
 ADISCORD_economy_calculate_debt_service_amount = yes
 set_variable = { var = ADISCORD_economy_weekly_interest value = ADISCORD_economy_debt_service }
 multiply_variable = { var = ADISCORD_economy_weekly_interest value = 3 }
 divide_variable = { var = ADISCORD_economy_weekly_interest value = 13 }
 set_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = ADISCORD_economy_monthly_income }
 multiply_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = 3 }
 divide_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = 13 }
 if = { limit = { check_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = 0.1 compare = less_than } }
  set_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = 0.1 }
 }
 set_variable = { var = ADISCORD_economy_interest_share_income value = ADISCORD_economy_weekly_interest }
 multiply_variable = { var = ADISCORD_economy_interest_share_income value = 100 }
 divide_variable = { var = ADISCORD_economy_interest_share_income value = ADISCORD_economy_interest_income_denominator_temp }
 set_variable = { var = ADISCORD_economy_interest_pressure_temp value = ADISCORD_economy_interest_share_income }
 multiply_variable = { var = ADISCORD_economy_interest_pressure_temp value = 1.50 }
 set_variable = { var = ADISCORD_economy_debt_streak_pressure_temp value = ADISCORD_economy_deficit_streak }
 multiply_variable = { var = ADISCORD_economy_debt_streak_pressure_temp value = 2 }
 set_variable = { var = ADISCORD_economy_debt_pressure value = ADISCORD_economy_debt_income_ratio }
 multiply_variable = { var = ADISCORD_economy_debt_pressure value = 0.20 }
 add_to_variable = { var = ADISCORD_economy_debt_pressure value = ADISCORD_economy_interest_pressure_temp }
 add_to_variable = { var = ADISCORD_economy_debt_pressure value = ADISCORD_economy_debt_streak_pressure_temp }
 clamp_variable = { var = ADISCORD_economy_debt_pressure min = 0 max = 100 }
 ADISCORD_economy_update_debt_crisis_level = yes
}
"""

    def test_schema_migration_exception_is_exact_and_live_legacy_use_is_rejected(self):
        self.assertEqual(migration_contract_issues(self.MIGRATION), [])
        injected = self.MIGRATION + "\nADISCORD_live = { ADISCORD_economy_construction_spending_mode = yes }"
        self.assertTrue(migration_contract_issues(injected))

    def test_capacity_boundary_covers_omitted_common_surfaces_and_mixed_migration_operations(self):
        for path in (
            "common/ai_strategy/injected.txt",
            "common/dynamic_modifiers/injected.txt",
        ):
            self.assertTrue(retired_capacity_boundary_issues({path: "replacement_debt_capacity = yes"}), path)
        mixed = """
ADISCORD_economy_migrate_schema = {
 clear_variable = ADISCORD_economy_debt_capacity
 set_variable = { var = ADISCORD_economy_debt_capacity value = 10 }
}
"""
        self.assertTrue(retired_capacity_boundary_issues({
            "common/scripted_effects/ADISCORD_economy_effects.txt": mixed
        }))

    def test_creditworthiness_modifier_migration_has_no_duplicate_block_keys(self):
        paths = (
            ROOT / "common" / "ideas" / "_economic.txt",
            ROOT / "common" / "ideas" / "ADISCORD_laws.txt",
            ROOT / "common" / "ideas" / "ADISCORD_VAL_rework_ideas.txt",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8-sig")
            self.assertFalse(
                duplicate_direct_key_blocks(
                    text, "ADISCORD_economy_creditworthiness_factor"
                ),
                path.name,
            )

        economic = paths[0].read_text(encoding="utf-8-sig")
        migrated_line = "ADISCORD_economy_creditworthiness_factor = -0.10"
        duplicate = economic.replace(
            migrated_line,
            migrated_line + "\n\t\t\t" + migrated_line,
            1,
        )
        self.assertNotEqual(duplicate, economic)
        self.assertTrue(
            duplicate_direct_key_blocks(
                duplicate, "ADISCORD_economy_creditworthiness_factor"
            )
        )

    def test_validator_accepts_full_deficit_ledger_without_obsolete_unfunded_state(self):
        self.assertEqual(automatic_borrow_flow_issues(EFFECTS), [])
        issues = validate_economy_ai()
        for obsolete in (
            "unfunded deficit is not recorded in the weekly ledger",
            "treasury-floor adjustment is missing from the accounting identity",
            "unfunded-deficit pressure ignores its custom modifier",
        ):
            self.assertNotIn(obsolete, issues)

    def test_debt_metric_fixture_rejects_formula_floor_order_and_principal_mutations(self):
        self.assertEqual(debt_metric_flow_issues(self.DEBT_METRICS), [])
        mutations = {
            "reversed annual-income floor": self.DEBT_METRICS.replace(
                "value = 1 compare = less_than",
                "value = 1 compare = greater_than",
                1,
            ),
            "missing weekly-income floor": self.DEBT_METRICS.replace(
                "  set_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = 0.1 }\n",
                "",
                1,
            ),
            "dead weekly-income floor": self.DEBT_METRICS.replace(
                "limit = { check_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = 0.1 compare = less_than } }",
                "limit = { check_variable = { var = ADISCORD_economy_interest_income_denominator_temp value = 0.1 compare = less_than } always = no }",
                1,
            ),
            "reordered ratio arithmetic": self.DEBT_METRICS.replace(
                " multiply_variable = { var = ADISCORD_economy_debt_income_ratio value = 100 }\n divide_variable = { var = ADISCORD_economy_debt_income_ratio value = ADISCORD_economy_debt_income_denominator_temp }",
                " divide_variable = { var = ADISCORD_economy_debt_income_ratio value = ADISCORD_economy_debt_income_denominator_temp }\n multiply_variable = { var = ADISCORD_economy_debt_income_ratio value = 100 }",
                1,
            ),
            "pressure coefficient changed": self.DEBT_METRICS.replace(
                "ADISCORD_economy_interest_pressure_temp value = 1.50",
                "ADISCORD_economy_interest_pressure_temp value = 1.25",
                1,
            ),
            "duplicate weekly-interest calculation": self.DEBT_METRICS.replace(
                " multiply_variable = { var = ADISCORD_economy_weekly_interest value = 3 }",
                " multiply_variable = { var = ADISCORD_economy_weekly_interest value = 3 }\n multiply_variable = { var = ADISCORD_economy_weekly_interest value = 3 }",
                1,
            ),
            "stored principal clamp": self.DEBT_METRICS.replace(
                " ADISCORD_economy_update_debt_crisis_level = yes",
                " clamp_variable = { var = ADISCORD_economy_debt min = 0 max = 5000 }\n ADISCORD_economy_update_debt_crisis_level = yes",
                1,
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutation, self.DEBT_METRICS)
                self.assertTrue(debt_metric_flow_issues(mutation))

        for variable, threshold in (
            ("ADISCORD_economy_debt_income_denominator_temp", "1"),
            ("ADISCORD_economy_interest_income_denominator_temp", "0.1"),
        ):
            exact_limit = (
                "limit = { check_variable = { var = "
                f"{variable} value = {threshold} compare = less_than }} }}"
            )
            for mutation_name, extra_predicate in (
                ("extra scalar predicate", "has_country_flag = hidden_floor_gate "),
                (
                    "extra compound predicate",
                    "AND = { has_country_flag = hidden_floor_gate } ",
                ),
            ):
                mutation = self.DEBT_METRICS.replace(
                    exact_limit,
                    exact_limit.replace(
                        "limit = { ", f"limit = {{ {extra_predicate}", 1
                    ),
                    1,
                )
                with self.subTest(
                    floor=variable,
                    mutation=mutation_name,
                ):
                    self.assertNotEqual(mutation, self.DEBT_METRICS)
                    self.assertTrue(debt_metric_flow_issues(mutation))

    def test_structural_call_graph_handles_parameter_blocks_decoys_duplicates_and_cycles(self):
        graph = """
ADISCORD_root = { ADISCORD_scalar = yes # ADISCORD_comment = yes
                 ADISCORD_parameter = { ARG = value } decoy = "ADISCORD_quote = yes" }
ADISCORD_scalar = { ADISCORD_root = yes }
ADISCORD_parameter = { ADISCORD_heavy = { OTHER = value } }
ADISCORD_heavy = { has_idea = forbidden }
"""
        reachable = reachable_script_entries((graph,), ("ADISCORD_root",))
        self.assertEqual(set(reachable), {
            "ADISCORD_root", "ADISCORD_scalar", "ADISCORD_parameter", "ADISCORD_heavy"
        })
        self.assertNotIn("ADISCORD_comment", reachable)
        self.assertNotIn("ADISCORD_quote", reachable)
        with self.assertRaisesRegex(AssertionError, "duplicate"):
            reachable_script_entries((graph + "\nADISCORD_heavy = { always = yes }",), ("ADISCORD_root",))

    def test_weekly_heavy_analyzer_rejects_all_edge_shapes_without_decoy_noise(self):
        clean = """
ADISCORD_root = {
  ADISCORD_safe = yes
  quoted_decoy = "has_idea"
  quoted_call_decoy = "ADISCORD_heavy = yes"
  # has_idea = forbidden
}
ADISCORD_safe = { check_variable = { var = cached_value value = 1 compare = equals } }
ADISCORD_heavy = { has_idea = forbidden }
ADISCORD_cycle = { ADISCORD_root = yes }
"""
        self.assertEqual(weekly_reachability_issues((clean,), ("ADISCORD_root",)), [])
        mutations = {
            "scalar heavy edge": clean.replace(
                "ADISCORD_safe = yes", "ADISCORD_safe = yes ADISCORD_heavy = yes", 1
            ),
            "parameter heavy edge": clean.replace(
                "ADISCORD_safe = yes",
                "ADISCORD_safe = yes ADISCORD_heavy = { ARG = value }",
                1,
            ),
            "cycle-hidden heavy edge": clean.replace(
                "ADISCORD_safe = {",
                "ADISCORD_safe = { ADISCORD_cycle = yes ADISCORD_heavy = yes",
                1,
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name):
                self.assertTrue(
                    weekly_reachability_issues((mutation,), ("ADISCORD_root",)),
                    name,
                )
        with self.assertRaisesRegex(AssertionError, "duplicate"):
            weekly_reachability_issues(
                (clean + "\nADISCORD_heavy = { always = yes }",),
                ("ADISCORD_root",),
            )

    def test_ai_assistance_requires_complete_signature_remove_first_and_live_gates(self):
        self.assertEqual(
            ai_assistance_contract_issues(
                self.ASSISTANCE_IDEAS,
                self.ASSISTANCE_EFFECT,
                self.ASSISTANCE_TRIGGERS,
            ),
            [],
        )
        effect_mutations = {
            "player bit omitted": self.ASSISTANCE_EFFECT.replace(
                " if = { limit = { is_ai = yes } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 10 } }\n",
                "",
                1,
            ),
            "tier not owned": self.ASSISTANCE_EFFECT.replace(
                " if = { limit = { has_variable = ADISCORD_economy_simulation_tier } set_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = ADISCORD_economy_simulation_tier } }\n",
                "",
                1,
            ),
            "unsafe missing tier read": self.ASSISTANCE_EFFECT.replace(
                " set_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 0 }\n if = { limit = { has_variable = ADISCORD_economy_simulation_tier } set_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = ADISCORD_economy_simulation_tier } }",
                " set_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = ADISCORD_economy_simulation_tier }",
                1,
            ),
            "war bit trapped": self.ASSISTANCE_EFFECT.replace(
                "limit = { has_war = yes }",
                "limit = { has_war = yes always = no }",
                1,
            ),
            "phase-end bit omitted": self.ASSISTANCE_EFFECT.replace(
                " if = { limit = { has_global_flag = ADISCORD_vorkerland_collapse_finished } add_to_temp_variable = { var = ADISCORD_economy_ai_assistance_signature_temp value = 150 } }\n",
                "",
                1,
            ),
            "surrender comparator reversed": self.ASSISTANCE_EFFECT.replace(
                "surrender_progress > 0.35",
                "surrender_progress < 0.35",
                1,
            ),
            "stale signature owner": self.ASSISTANCE_EFFECT.replace(
                "compare = not_equals",
                "compare = equals",
                1,
            ),
            "signature owner uses AND": self.ASSISTANCE_EFFECT.replace(
                "limit = { OR = { NOT = { has_variable = ADISCORD_economy_ai_assistance_signature }",
                "limit = { AND = { NOT = { has_variable = ADISCORD_economy_ai_assistance_signature }",
                1,
            ),
            "signature missing arm inverted": self.ASSISTANCE_EFFECT.replace(
                "NOT = { has_variable = ADISCORD_economy_ai_assistance_signature }",
                "has_variable = ADISCORD_economy_ai_assistance_signature",
                1,
            ),
            "missing civil removal": self.ASSISTANCE_EFFECT.replace(
                "  remove_ideas = ADISCORD_economy_ai_assistance_civil_war\n",
                "",
                1,
            ),
            "addition before removal": self.ASSISTANCE_EFFECT.replace(
                "  remove_ideas = ADISCORD_economy_ai_assistance_base\n",
                "  add_ideas = ADISCORD_economy_ai_assistance_base\n  remove_ideas = ADISCORD_economy_ai_assistance_base\n",
                1,
            ),
            "wrong retreat owner": self.ASSISTANCE_EFFECT.replace(
                "ADISCORD_economy_ai_assistance_retreat_active = yes",
                "ADISCORD_economy_ai_assistance_is_eligible = yes",
                1,
            ),
            "signature published before cache": self.ASSISTANCE_EFFECT.replace(
                "  ADISCORD_economy_refresh_ai_assistance_income_cache = yes\n  set_variable = { var = ADISCORD_economy_ai_assistance_signature value = ADISCORD_economy_ai_assistance_signature_temp }",
                "  set_variable = { var = ADISCORD_economy_ai_assistance_signature value = ADISCORD_economy_ai_assistance_signature_temp }\n  ADISCORD_economy_refresh_ai_assistance_income_cache = yes",
                1,
            ),
        }
        for name, mutation in effect_mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutation, self.ASSISTANCE_EFFECT)
                self.assertTrue(
                    ai_assistance_contract_issues(
                        self.ASSISTANCE_IDEAS,
                        mutation,
                        self.ASSISTANCE_TRIGGERS,
                    )
                )

        trigger_mutations = {
            "player eligible": self.ASSISTANCE_TRIGGERS.replace(
                " is_ai = yes", " is_ai = no", 1
            ),
            "dormant tier eligible": self.ASSISTANCE_TRIGGERS.replace(
                "value = 2 compare = less_than_or_equals",
                "value = 3 compare = less_than_or_equals",
                1,
            ),
            "collapse end ignored": self.ASSISTANCE_TRIGGERS.replace(
                " NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }\n",
                "",
                1,
            ),
            "nonparticipant eligible": self.ASSISTANCE_TRIGGERS.replace(
                " has_country_flag = ADISCORD_vorkerland_conflict_spirits_finalized\n",
                "",
                1,
            ),
            "retreat threshold inclusive": self.ASSISTANCE_TRIGGERS.replace(
                "surrender_progress > 0.35",
                "surrender_progress >= 0.35",
                1,
            ),
            "all stored signatures polled monthly": self.ASSISTANCE_TRIGGERS.replace(
                "  has_idea = ADISCORD_economy_ai_assistance_base\n"
                "  has_idea = ADISCORD_economy_ai_assistance_civil_war\n"
                "  has_idea = ADISCORD_economy_ai_assistance_retreat",
                "  has_variable = ADISCORD_economy_ai_assistance_signature",
                1,
            ),
        }
        for name, mutation in trigger_mutations.items():
            with self.subTest(mutation=name):
                self.assertTrue(
                    ai_assistance_contract_issues(
                        self.ASSISTANCE_IDEAS,
                        self.ASSISTANCE_EFFECT,
                        mutation,
                    )
                )

        idea_mutations = {
            "attack bonus": self.ASSISTANCE_IDEAS.replace(
                "army_defence_factor = 0.05",
                "army_defence_factor = 0.05 army_attack_factor = 0.01",
                1,
            ),
            "renamed stack": self.ASSISTANCE_IDEAS.replace(
                "} }\n",
                " ADISCORD_economy_ai_assistance_shadow = { modifier = { industrial_capacity_factory = 0.01 } }\n} }\n",
                1,
            ),
            "factory bound": self.ASSISTANCE_IDEAS.replace(
                "industrial_capacity_factory = 0.05",
                "industrial_capacity_factory = 0.06",
                1,
            ),
            "political power on add": self.ASSISTANCE_IDEAS.replace(
                "modifier = { ADISCORD_economy_overall_income_factor = 0.05 industrial_capacity_factory = 0.05 }",
                "modifier = { ADISCORD_economy_overall_income_factor = 0.05 industrial_capacity_factory = 0.05 } on_add = { add_political_power = 100 }",
                1,
            ),
            "equipment attack bonus": self.ASSISTANCE_IDEAS.replace(
                "modifier = { army_defence_factor = 0.05 }",
                "modifier = { army_defence_factor = 0.05 } equipment_bonus = { infantry_equipment = { soft_attack = 0.10 } }",
                1,
            ),
        }
        for name, mutation in idea_mutations.items():
            with self.subTest(mutation=name):
                self.assertTrue(
                    ai_assistance_contract_issues(
                        mutation,
                        self.ASSISTANCE_EFFECT,
                        self.ASSISTANCE_TRIGGERS,
                    )
                )

        external_owner = self.ASSISTANCE_EFFECT + """
ADISCORD_bad_assistance_owner = {
 add_ideas = ADISCORD_economy_ai_assistance_base
 remove_ideas = ADISCORD_economy_ai_assistance_retreat
}
"""
        self.assertTrue(
            ai_assistance_contract_issues(
                self.ASSISTANCE_IDEAS,
                external_owner,
                self.ASSISTANCE_TRIGGERS,
            )
        )

        shadow_ideas = self.ASSISTANCE_IDEAS.replace(
            "} }\n",
            " ADISCORD_ai_helper_shadow = { allowed = { always = no } allowed_civil_war = { always = yes } removal_cost = -1 modifier = { ADISCORD_economy_overall_income_factor = 0.05 industrial_capacity_factory = 0.05 } }\n} }\n",
            1,
        )
        shadow_effect = self.ASSISTANCE_EFFECT.replace(
            "add_ideas = ADISCORD_economy_ai_assistance_base }",
            "add_ideas = ADISCORD_economy_ai_assistance_base add_ideas = ADISCORD_ai_helper_shadow }",
            1,
        )
        self.assertNotEqual(shadow_ideas, self.ASSISTANCE_IDEAS)
        self.assertNotEqual(shadow_effect, self.ASSISTANCE_EFFECT)
        self.assertTrue(
            ai_assistance_contract_issues(
                shadow_ideas,
                shadow_effect,
                self.ASSISTANCE_TRIGGERS,
            )
        )

    def test_ai_policy_is_one_reserved_ordered_research_decision(self):
        policy = """
ADISCORD_economy_ai_monthly_policy = {
 if = {
  limit = { is_ai = yes has_political_power > 50 }
  if = {
   limit = { ADISCORD_economy_ai_is_crisis = yes }
   if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_increase_tax_burden = yes } ADISCORD_economy_increase_tax_burden = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } check_variable = { var = ADISCORD_economy_social_spending_mode value = 2 compare = greater_than } ADISCORD_economy_can_decrease_social_spending = yes } ADISCORD_economy_decrease_social_spending = yes }
   else_if = { limit = { has_war = no check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_decrease_army_spending = yes } ADISCORD_economy_decrease_army_spending = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_decrease_research_spending = yes } ADISCORD_economy_decrease_research_spending = yes }
  }
  else_if = {
   limit = { ADISCORD_economy_ai_is_stressed = yes }
   if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_increase_tax_burden = yes } ADISCORD_economy_increase_tax_burden = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } check_variable = { var = ADISCORD_economy_social_spending_mode value = 3 compare = greater_than } ADISCORD_economy_can_decrease_social_spending = yes } ADISCORD_economy_decrease_social_spending = yes }
   else_if = { limit = { has_war = no check_variable = { var = ADISCORD_economy_fiscal_stress value = 55 compare = greater_than_or_equals } ADISCORD_economy_can_decrease_army_spending = yes } ADISCORD_economy_decrease_army_spending = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_decrease_research_spending = yes } ADISCORD_economy_decrease_research_spending = yes }
  }
  else_if = {
   limit = { ADISCORD_economy_ai_is_recovery = yes }
   if = { limit = { check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = greater_than } ADISCORD_economy_can_decrease_research_spending = yes } ADISCORD_economy_decrease_research_spending = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = less_than } ADISCORD_economy_can_increase_research_spending = yes } ADISCORD_economy_increase_research_spending = yes }
  }
  else = {
   if = { limit = { check_variable = { var = ADISCORD_economy_research_spending_mode value = 4 compare = greater_than } ADISCORD_economy_can_decrease_research_spending = yes } ADISCORD_economy_decrease_research_spending = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = greater_than } OR = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than_or_equals } check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = greater_than } check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = greater_than_or_equals } } ADISCORD_economy_can_decrease_research_spending = yes } ADISCORD_economy_decrease_research_spending = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = less_than } ADISCORD_economy_can_increase_research_spending = yes } ADISCORD_economy_increase_research_spending = yes }
   else_if = { limit = { check_variable = { var = ADISCORD_economy_research_spending_mode value = 3 compare = equals } check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = greater_than } check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = equals } check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = less_than } ADISCORD_economy_can_increase_research_spending = yes } ADISCORD_economy_increase_research_spending = yes }
  }
 }
}
"""
        self.assertEqual(ai_policy_contract_issues(policy), [])
        mutations = {
            "missing PP reserve": policy.replace(
                " has_political_power > 50", "", 1
            ),
            "reversed PP reserve": policy.replace(
                "has_political_power > 50", "has_political_power < 50", 1
            ),
            "dead owner": policy.replace(
                "limit = { is_ai = yes has_political_power > 50 }",
                "limit = { is_ai = yes has_political_power > 50 always = no }",
                1,
            ),
            "wrong crisis state owner": policy.replace(
                "ADISCORD_economy_ai_is_crisis = yes",
                "ADISCORD_economy_ai_is_healthy = yes",
                1,
            ),
            "reversed crisis deficit": policy.replace(
                "ADISCORD_economy_monthly_balance value = 0 compare = less_than",
                "ADISCORD_economy_monthly_balance value = 0 compare = greater_than",
                1,
            ),
            "unconditional crisis tax": policy.replace(
                "limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_increase_tax_burden = yes }",
                "limit = { always = yes }",
                1,
            ),
            "negated crisis tax": policy.replace(
                "limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } ADISCORD_economy_can_increase_tax_burden = yes }",
                "limit = { NOT = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } } ADISCORD_economy_can_increase_tax_burden = yes }",
                1,
            ),
            "multiple sibling actions": policy.replace(
                "   else_if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } check_variable = { var = ADISCORD_economy_social_spending_mode value = 2",
                "   if = { limit = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than } check_variable = { var = ADISCORD_economy_social_spending_mode value = 2",
                1,
            ),
            "action outside reserve": policy.replace(
                "ADISCORD_economy_ai_monthly_policy = {",
                "ADISCORD_economy_ai_monthly_policy = { ADISCORD_economy_increase_tax_burden = yes",
                1,
            ),
            "action outside fiscal state": policy.replace(
                "  if = {\n   limit = { ADISCORD_economy_ai_is_crisis = yes }",
                "  ADISCORD_economy_increase_tax_burden = yes\n  if = {\n   limit = { ADISCORD_economy_ai_is_crisis = yes }",
                1,
            ),
            "second action in one decision": policy.replace(
                "ADISCORD_economy_increase_tax_burden = yes }",
                "ADISCORD_economy_increase_tax_burden = yes ADISCORD_economy_decrease_social_spending = yes }",
                1,
            ),
            "research before tax": policy.replace(
                "ADISCORD_economy_increase_tax_burden = yes",
                "ADISCORD_economy_swap_action = yes",
                1,
            ).replace(
                "ADISCORD_economy_decrease_research_spending = yes",
                "ADISCORD_economy_increase_tax_burden = yes",
                1,
            ).replace(
                "ADISCORD_economy_swap_action = yes",
                "ADISCORD_economy_decrease_research_spending = yes",
                1,
            ),
            "reversed current surplus": policy.replace(
                "ADISCORD_economy_monthly_balance value = 0 compare = greater_than",
                "ADISCORD_economy_monthly_balance value = 0 compare = less_than",
                1,
            ),
            "unsafe research four": policy.replace(
                " check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = equals }",
                "",
                1,
            ),
            "automatic research five": policy.replace(
                "ADISCORD_economy_research_spending_mode value = 3 compare = equals",
                "ADISCORD_economy_research_spending_mode value = 4 compare = equals",
                1,
            ),
            "unsafe fallback unconditional": policy.replace(
                "OR = { check_variable = { var = ADISCORD_economy_monthly_balance value = 0 compare = less_than_or_equals } check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = greater_than } check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = greater_than_or_equals } }",
                "always = yes",
                1,
            ),
            "level five not normalized": policy.replace(
                "ADISCORD_economy_research_spending_mode value = 4 compare = greater_than",
                "ADISCORD_economy_research_spending_mode value = 5 compare = greater_than",
                1,
            ),
            "construction alias": policy.replace(
                "ADISCORD_economy_increase_tax_burden = yes",
                "ADISCORD_economy_construction_spending_mode = yes",
                1,
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutation, policy)
                self.assertTrue(ai_policy_contract_issues(mutation))

    def test_core_policy_and_debt_flow_negative_fixtures(self):
        research = "\n".join(
            ["ADISCORD_economy_calculate_research_expenses = {"]
            + [
                f"if = {{ limit = {{ check_variable = {{ var = ADISCORD_economy_research_spending_mode value = {level} compare = equals }} }} multiply_variable = {{ var = ADISCORD_economy_research_expenses value = {factor} }} }}"
                for level, factor in enumerate(("0.60", "0.80", "1.00", "1.30", "1.60"), 1)
            ]
            + ["}"]
        )
        self.assertEqual(research_policy_flow_issues(research), [])
        unconditional = re.sub(r"if = \{ limit = \{[^{}]*\{[^{}]*\} \} (multiply_variable = \{[^{}]*\}) \}", r"\1", research)
        self.assertTrue(research_policy_flow_issues(unconditional))
        overlapping = research.replace("compare = equals", "compare = greater_than")
        self.assertTrue(research_policy_flow_issues(overlapping))
        negated_research = research.replace(
            "limit = { check_variable",
            "limit = { NOT = { check_variable",
        ).replace(
            "compare = equals } } multiply_variable",
            "compare = equals } } } multiply_variable",
        )
        with self.subTest(mutation="negated research owners"):
            self.assertTrue(research_policy_flow_issues(negated_research))
        level_one_branch = (
            "if = { limit = { check_variable = { var = "
            "ADISCORD_economy_research_spending_mode value = 1 compare = equals } } "
            "multiply_variable = { var = ADISCORD_economy_research_expenses value = 0.60 } }"
        )
        duplicate_level = research.rsplit("}", 1)[0] + level_one_branch + "\n}"
        self.assertTrue(research_policy_flow_issues(duplicate_level))
        extra_multiplier = research.rsplit("}", 1)[0] + (
            "multiply_variable = { var = ADISCORD_economy_research_expenses value = 1.00 }\n}"
        )
        self.assertTrue(research_policy_flow_issues(extra_multiplier))

        settlement = """
ADISCORD_economy_apply_weekly_balance = {
 if = { limit = { check_variable = { var = ADISCORD_economy_treasury value = 0 compare = less_than } }
  set_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = 0 }
  subtract_from_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = ADISCORD_economy_treasury }
  set_variable = { var = ADISCORD_economy_auto_borrow_temp value = ADISCORD_economy_uncovered_deficit_temp }
  add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp }
  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }
 }
}
ADISCORD_economy_apply_monthly_balance = {
 if = { limit = { check_variable = { var = ADISCORD_economy_treasury value = 0 compare = less_than } }
  set_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = 0 }
  subtract_from_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = ADISCORD_economy_treasury }
  set_variable = { var = ADISCORD_economy_auto_borrow_temp value = ADISCORD_economy_uncovered_deficit_temp }
  add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp }
  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }
 }
}
"""
        self.assertEqual(automatic_borrow_flow_issues(settlement), [])
        nested_positive_owner = settlement.replace(
            "limit = { check_variable = { var = ADISCORD_economy_treasury value = 0 compare = less_than } }",
            "limit = { OR = { AND = { check_variable = { var = ADISCORD_economy_treasury value = 0 compare = less_than } } AND = { always = no } } }",
        )
        self.assertEqual(automatic_borrow_flow_issues(nested_positive_owner), [])
        outside_accounting = settlement.replace(
            "  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }\n }\n}",
            "  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }\n"
            " }\n"
            " set_variable = { var = ADISCORD_economy_debt value = ADISCORD_unrelated_accounting }\n"
            " add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_unrelated_accounting }\n"
            " clear_variable = ADISCORD_economy_debt\n"
            " clear_variable = ADISCORD_economy_treasury\n"
            "}",
        )
        self.assertEqual(automatic_borrow_flow_issues(outside_accounting), [])
        account_write_templates = {
            "clear": "clear_variable = %s",
            "subtract": "subtract_from_variable = { var = %s value = ADISCORD_economy_auto_borrow_temp }",
            "set": "set_variable = { var = %s value = ADISCORD_economy_auto_borrow_temp }",
            "multiply": "multiply_variable = { var = %s value = ADISCORD_economy_auto_borrow_temp }",
            "divide": "divide_variable = { var = %s value = ADISCORD_economy_auto_borrow_temp }",
            "clamp": "clamp_variable = { var = %s min = 0 max = ADISCORD_economy_auto_borrow_temp }",
        }
        for account in ("ADISCORD_economy_debt", "ADISCORD_economy_treasury"):
            canonical_addition = (
                f"  add_to_variable = {{ var = {account} "
                "value = ADISCORD_economy_auto_borrow_temp }"
            )
            for operation, template in account_write_templates.items():
                account_write = settlement.replace(
                    canonical_addition,
                    canonical_addition + "\n  " + template % account,
                )
                with self.subTest(account=account, operation=operation):
                    self.assertTrue(automatic_borrow_flow_issues(account_write))
            unrelated_owner_write = settlement.replace(
                canonical_addition,
                canonical_addition
                + f"\n  set_variable = {{ var = {account} value = ADISCORD_unrelated_accounting }}",
            )
            with self.subTest(account=account, operation="owner rewrite"):
                self.assertTrue(
                    automatic_borrow_flow_issues(unrelated_owner_write)
                )
        negated_treasury_owner = settlement.replace(
            "limit = { check_variable = { var = ADISCORD_economy_treasury value = 0 compare = less_than } }",
            "limit = { NOT = { check_variable = { var = ADISCORD_economy_treasury value = 0 compare = less_than } } }",
        )
        with self.subTest(mutation="negated treasury owner"):
            self.assertTrue(automatic_borrow_flow_issues(negated_treasury_owner))
        dead_funding = settlement.replace(
            "  add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp }\n  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }",
            "  if = { limit = { always = no } add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp } add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp } }",
        )
        self.assertTrue(automatic_borrow_flow_issues(dead_funding))
        conditional_funding = settlement.replace(
            "  add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp }\n  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }",
            "  if = { limit = { has_country_flag = hidden_gate } add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp } add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp } }",
        )
        self.assertTrue(automatic_borrow_flow_issues(conditional_funding))
        capped = settlement.replace(
            " add_to_variable = { var = ADISCORD_economy_debt",
            " clamp_variable = { var = ADISCORD_economy_auto_borrow_temp min = 0 max = ADISCORD_hidden_borrow_cap }\n add_to_variable = { var = ADISCORD_economy_debt",
            1,
        )
        self.assertTrue(automatic_borrow_flow_issues(capped))
        for source_mutation in (
            "clamp_variable = { var = ADISCORD_economy_uncovered_deficit_temp min = 0 max = ADISCORD_hidden_cap }",
            "subtract_from_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = ADISCORD_hidden_cap }",
            "set_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = ADISCORD_hidden_cap }",
        ):
            hidden_source_cap = settlement.replace(
                "  set_variable = { var = ADISCORD_economy_auto_borrow_temp value = ADISCORD_economy_uncovered_deficit_temp }",
                f"  {source_mutation}\n  set_variable = {{ var = ADISCORD_economy_auto_borrow_temp value = ADISCORD_economy_uncovered_deficit_temp }}",
            )
            self.assertTrue(automatic_borrow_flow_issues(hidden_source_cap))
        nested_source_cap = settlement.replace(
            "  subtract_from_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = ADISCORD_economy_treasury }\n",
            "  subtract_from_variable = { var = ADISCORD_economy_uncovered_deficit_temp value = ADISCORD_economy_treasury }\n"
            "  if = { limit = { always = yes } clamp_variable = { var = ADISCORD_economy_uncovered_deficit_temp min = 0 max = ADISCORD_hidden_cap } }\n",
        )
        with self.subTest(mutation="nested uncovered-source cap"):
            self.assertTrue(automatic_borrow_flow_issues(nested_source_cap))
        additions_before_copy = settlement.replace(
            "  set_variable = { var = ADISCORD_economy_auto_borrow_temp value = ADISCORD_economy_uncovered_deficit_temp }\n"
            "  add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp }\n"
            "  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }",
            "  add_to_variable = { var = ADISCORD_economy_debt value = ADISCORD_economy_auto_borrow_temp }\n"
            "  add_to_variable = { var = ADISCORD_economy_treasury value = ADISCORD_economy_auto_borrow_temp }\n"
            "  set_variable = { var = ADISCORD_economy_auto_borrow_temp value = ADISCORD_economy_uncovered_deficit_temp }",
        )
        with self.subTest(mutation="account additions before copy"):
            self.assertTrue(automatic_borrow_flow_issues(additions_before_copy))

    def test_transition_notification_and_reconciler_negative_fixtures(self):
        transition = """
ADISCORD_economy_update_debt_state_after_settlement = {
 if = { limit = { check_variable = { var = ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals } }
  add_to_variable = { var = ADISCORD_economy_debt_emergency_streak value = 1 }
  if = { limit = { check_variable = { var = ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals } }
   set_variable = { var = ADISCORD_economy_debt_state value = 3 }
  }
 } else = { set_variable = { var = ADISCORD_economy_debt_emergency_streak value = 0 } }
 if = { limit = {
  check_variable = { var = ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals }
  check_variable = { var = ADISCORD_economy_weekly_balance value = 0 compare = less_than }
 } add_to_variable = { var = ADISCORD_economy_debt_default_streak value = 1 }
  if = { limit = { check_variable = { var = ADISCORD_economy_debt_default_streak value = 13 compare = greater_than_or_equals } }
   set_variable = { var = ADISCORD_economy_debt_state value = 4 }
  }
 } else = { set_variable = { var = ADISCORD_economy_debt_default_streak value = 0 } }
 if = { limit = {
  check_variable = { var = ADISCORD_economy_debt_default_streak value = 13 compare = less_than }
  check_variable = { var = ADISCORD_economy_debt_emergency_streak value = 4 compare = less_than }
 }
  if = { limit = { check_variable = { var = ADISCORD_economy_interest_share_income value = 25 compare = greater_than_or_equals } }
   set_variable = { var = ADISCORD_economy_debt_state value = 2 }
  } else_if = { limit = { check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = greater_than_or_equals } }
   set_variable = { var = ADISCORD_economy_debt_state value = 1 }
  } else = { set_variable = { var = ADISCORD_economy_debt_state value = 0 } }
 }
  clamp_variable = { var = ADISCORD_economy_debt_emergency_streak min = 0 max = 4 }
  clamp_variable = { var = ADISCORD_economy_debt_default_streak min = 0 max = 13 }
  set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }
  ADISCORD_economy_sync_debt_state_idea = yes
}
"""
        self.assertEqual(task6_debt_state_sequence_issues(transition), [])
        self.assertTrue(task6_debt_state_sequence_issues(transition.replace(
            "check_variable = { var = ADISCORD_economy_weekly_balance value = 0 compare = less_than }", "always = yes"
        )))
        self.assertTrue(task6_debt_state_sequence_issues(transition.replace(
            " } else = { set_variable = { var = ADISCORD_economy_debt_emergency_streak value = 0 } }",
            " } set_variable = { var = ADISCORD_economy_debt_emergency_streak value = 0 }",
        )))
        for index, invalid in enumerate((
            transition.replace(
                "ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals",
                "ADISCORD_economy_interest_share_income value = 40 compare = less_than",
            ),
            transition.replace(
                "ADISCORD_economy_weekly_balance value = 0 compare = less_than",
                "ADISCORD_economy_weekly_balance value = 0 compare = greater_than",
            ),
            transition.replace(
                "ADISCORD_economy_debt_emergency_streak value = 0",
                "ADISCORD_economy_debt_emergency_streak value = 999",
            ),
            transition.replace(
                "ADISCORD_economy_debt_default_streak value = 0",
                "ADISCORD_economy_debt_default_streak value = 999",
            ),
            transition.replace(
                "ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals",
                "ADISCORD_economy_debt_emergency_streak value = 5 compare = greater_than_or_equals",
            ),
            transition.replace(
                "ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals",
                "ADISCORD_economy_debt_emergency_streak value = 3 compare = greater_than_or_equals",
            ),
            transition.replace(
                "ADISCORD_economy_debt_default_streak value = 13 compare = greater_than_or_equals",
                "ADISCORD_economy_debt_default_streak value = 12 compare = greater_than_or_equals",
            ),
            transition.replace(
                "ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals } }",
                "ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals } always = no }",
                1,
            ),
            transition.replace(
                "ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals } }",
                "ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals } always = no }",
            ),
            transition.replace(
                "check_variable = { var = ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals }",
                "NOT = { check_variable = { var = ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals } }",
                1,
            ),
            transition.replace(
                "check_variable = { var = ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals }",
                "NOT = { check_variable = { var = ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals } }",
            ),
            transition.replace(
                "check_variable = { var = ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals }",
                "check_variable = { var = ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals } AND = { always = no }",
            ),
            transition.replace(
                "add_to_variable = { var = ADISCORD_economy_debt_emergency_streak value = 1 }",
                "add_to_variable = { var = ADISCORD_economy_debt_emergency_streak value = 1 }\n"
                "  add_to_variable = { var = ADISCORD_economy_debt_emergency_streak value = 1 }",
            ),
            transition.replace(
                "ADISCORD_economy_interest_share_income value = 25 compare = greater_than_or_equals",
                "ADISCORD_economy_interest_share_income value = 25 compare = less_than",
            ),
            transition.replace(
                "  } else_if = { limit = { check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = greater_than_or_equals } }\n"
                "   set_variable = { var = ADISCORD_economy_debt_state value = 1 }",
                "  } else_if = { limit = { always = yes }\n"
                "   set_variable = { var = ADISCORD_economy_debt_state value = 1 }",
            ),
            transition.replace(
                "  set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n",
                "",
                1,
            ),
            transition.replace(
                "  ADISCORD_economy_sync_debt_state_idea = yes\n",
                "",
                1,
            ),
            transition.replace(
                "  ADISCORD_economy_sync_debt_state_idea = yes\n",
                "  ADISCORD_economy_sync_debt_state_idea = yes\n"
                "  ADISCORD_economy_sync_debt_state_idea = yes\n",
                1,
            ),
            transition.replace(
                "  ADISCORD_economy_sync_debt_state_idea = yes\n",
                "  if = { limit = { always = yes } ADISCORD_economy_sync_debt_state_idea = yes }\n",
                1,
            ),
            transition.replace(
                "  set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n"
                "  ADISCORD_economy_sync_debt_state_idea = yes\n",
                "",
                1,
            ).replace(
                "  if = { limit = {\n"
                "   check_variable = { var = ADISCORD_economy_debt_default_streak value = 13 compare = less_than }",
                "  set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n"
                "  ADISCORD_economy_sync_debt_state_idea = yes\n"
                "  if = { limit = {\n"
                "   check_variable = { var = ADISCORD_economy_debt_default_streak value = 13 compare = less_than }",
                1,
            ),
        )):
            with self.subTest(transition_mutation=index):
                self.assertTrue(parse_clausewitz(invalid))
                self.assertTrue(task6_debt_state_sequence_issues(invalid))

        queue_notification = """
ADISCORD_economy_queue_debt_notification = {
 set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 0 }
 set_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = ADISCORD_economy_debt_state }
 if = { limit = {
  check_variable = { var = ADISCORD_economy_pending_debt_notification_amount value = 0 compare = greater_than }
  NOT = { has_variable = ADISCORD_economy_first_loan_notified }
 }
  set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 1 }
  set_variable = { var = ADISCORD_economy_first_loan_notified value = 1 }
 }
 if = { limit = {
  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = greater_than }
  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_last_notified_debt_state compare = greater_than }
 }
  if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 4 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 5 } }
  else_if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 3 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 4 } }
  else_if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 2 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 3 } }
  else_if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 1 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 2 } }
  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }
 }
 if = { limit = {
  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }
  check_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state compare = greater_than }
 }
  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }
 }
 if = { limit = { is_ai = no check_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 0 compare = greater_than } }
  country_event = { id = ADISCORD_economy.3 }
 }
}
"""
        self.assertEqual(task6_notification_queue_issues(queue_notification), [])
        severity_mapping = (
            "  if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 4 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 5 } }\n"
            "  else_if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 3 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 4 } }\n"
            "  else_if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 2 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 3 } }\n"
            "  else_if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = 1 compare = equals } } set_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 2 } }\n"
        )
        human_dispatch = (
            " if = { limit = { is_ai = no check_variable = { var = ADISCORD_economy_pending_debt_notification_kind value = 0 compare = greater_than } }\n"
            "  country_event = { id = ADISCORD_economy.3 }\n"
            " }\n"
        )
        upward_marker = (
            " if = { limit = {\n"
            "  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = greater_than }"
        )
        mapping_outside_upward = queue_notification.replace(severity_mapping, "", 1).replace(
            upward_marker,
            severity_mapping + upward_marker,
            1,
        )
        dispatch_before_severity = queue_notification.replace(human_dispatch, "", 1).replace(
            upward_marker,
            human_dispatch + upward_marker,
            1,
        )
        queue_mutations = {
            "already-notified first loan": queue_notification.replace(
                "NOT = { has_variable = ADISCORD_economy_first_loan_notified }",
                "has_variable = ADISCORD_economy_first_loan_notified",
            ),
            "wrong state kind": queue_notification.replace(
                "ADISCORD_economy_pending_debt_notification_kind value = 5",
                "ADISCORD_economy_pending_debt_notification_kind value = 4",
                1,
            ),
            "reversed upward owner": queue_notification.replace(
                "ADISCORD_economy_pending_debt_notification_previous_state compare = greater_than",
                "ADISCORD_economy_pending_debt_notification_previous_state compare = less_than",
                1,
            ),
            "AI event": queue_notification.replace("is_ai = no", "is_ai = yes"),
            "duplicate modal": queue_notification.replace(
                "country_event = { id = ADISCORD_economy.3 }",
                "country_event = { id = ADISCORD_economy.3 }\n"
                "  country_event = { id = ADISCORD_economy.3 }",
            ),
            "legacy popup": queue_notification.replace(
                "country_event = { id = ADISCORD_economy.3 }",
                "country_event = { id = ADISCORD_economy.3 }\n"
                 "  set_variable = { var = ADISCORD_economy_show_auto_loan_popup value = 1 }",
            ),
            "severity mappings moved outside upward owner": mapping_outside_upward,
            "human dispatch moved before severity override": dispatch_before_severity,
            "improvement check hidden behind unrelated gate": queue_notification.replace(
                "  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }",
                "  AND = {\n"
                "   check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }\n"
                "   has_country_flag = hidden_notice_gate\n"
                "  }",
                1,
            ),
            "improvement has an extra direct predicate": queue_notification.replace(
                "  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }",
                "  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }\n"
                "  has_country_flag = hidden_notice_gate",
                1,
            ),
            "improvement owner made dead": queue_notification.replace(
                "  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }",
                "  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }\n"
                "  always = no",
                1,
            ),
            "improvement check negated": queue_notification.replace(
                "  check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }",
                "  NOT = { check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than } }",
                1,
            ),
            "improvement watermark made conditional": queue_notification.replace(
                "  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }\n"
                " }\n"
                " if = { limit = { is_ai = no",
                "  if = { limit = { always = yes } set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state } }\n"
                " }\n"
                " if = { limit = { is_ai = no",
                1,
            ),
            "improvement watermark duplicated": queue_notification.replace(
                "  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }\n"
                " }\n"
                " if = { limit = { is_ai = no",
                "  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }\n"
                "  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }\n"
                " }\n"
                " if = { limit = { is_ai = no",
                1,
            ),
        }
        for name, invalid in queue_mutations.items():
            with self.subTest(notification_mutation=name):
                self.assertNotEqual(invalid, queue_notification)
                self.assertTrue(parse_clausewitz(invalid))
                self.assertTrue(task6_notification_queue_issues(invalid))

        settlement_notification_flow = queue_notification + """
ADISCORD_economy_apply_weekly_balance = {
 set_variable = { var = ADISCORD_economy_pending_debt_notification_previous_state value = ADISCORD_economy_debt_state }
 set_variable = { var = ADISCORD_economy_pending_debt_notification_amount value = 0 }
 ADISCORD_economy_update_debt_state_after_settlement = yes
 ADISCORD_economy_queue_debt_notification = yes
}
ADISCORD_economy_apply_monthly_balance = {
 set_variable = { var = ADISCORD_economy_pending_debt_notification_previous_state value = ADISCORD_economy_debt_state }
 set_variable = { var = ADISCORD_economy_pending_debt_notification_amount value = 0 }
 ADISCORD_economy_update_debt_state_after_settlement = yes
 ADISCORD_economy_queue_debt_notification = yes
}
"""
        self.assertEqual(
            debt_notification_flow_issues(settlement_notification_flow), []
        )
        settlement_mutations = {
            "duplicate settlement queue": settlement_notification_flow.replace(
                " ADISCORD_economy_queue_debt_notification = yes\n}",
                " ADISCORD_economy_queue_debt_notification = yes\n"
                " ADISCORD_economy_queue_debt_notification = yes\n}",
                1,
            ),
            "queue before state": settlement_notification_flow.replace(
                " ADISCORD_economy_update_debt_state_after_settlement = yes\n"
                " ADISCORD_economy_queue_debt_notification = yes",
                " ADISCORD_economy_queue_debt_notification = yes\n"
                " ADISCORD_economy_update_debt_state_after_settlement = yes",
                1,
            ),
            "modal outside queue": settlement_notification_flow.replace(
                " ADISCORD_economy_update_debt_state_after_settlement = yes\n",
                " country_event = { id = ADISCORD_economy.3 }\n"
                " ADISCORD_economy_update_debt_state_after_settlement = yes\n",
                1,
            ),
        }
        for name, invalid in settlement_mutations.items():
            with self.subTest(settlement_notification_mutation=name):
                self.assertTrue(parse_clausewitz(invalid))
                self.assertTrue(debt_notification_flow_issues(invalid))

        branches = {
            0: """ if = {
  limit = {
   check_variable = { var = ADISCORD_economy_interest_share_income value = 10 compare = less_than }
   check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = greater_than }
  }
  set_variable = { var = ADISCORD_economy_debt_state value = 0 }
  if = {
   limit = { check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than } }
   set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 }
  }
  remove_ideas = { ADISCORD_economy_debt_strain ADISCORD_economy_debt_crisis ADISCORD_economy_debt_emergency ADISCORD_economy_debt_default }
 }
""",
            1: """ else_if = {
  limit = {
   check_variable = { var = ADISCORD_economy_interest_share_income value = 25 compare = less_than }
   check_variable = { var = ADISCORD_economy_debt_state value = 1 compare = greater_than }
  }
  set_variable = { var = ADISCORD_economy_debt_state value = 1 }
  if = {
   limit = { check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 1 compare = greater_than } }
   set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 1 }
  }
  remove_ideas = { ADISCORD_economy_debt_strain ADISCORD_economy_debt_crisis ADISCORD_economy_debt_emergency ADISCORD_economy_debt_default }
  add_ideas = ADISCORD_economy_debt_strain
 }
""",
            2: """ else_if = {
  limit = {
   check_variable = { var = ADISCORD_economy_interest_share_income value = 40 compare = less_than }
   check_variable = { var = ADISCORD_economy_debt_state value = 2 compare = greater_than }
  }
  set_variable = { var = ADISCORD_economy_debt_state value = 2 }
  if = {
   limit = { check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 2 compare = greater_than } }
   set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 2 }
  }
  remove_ideas = { ADISCORD_economy_debt_strain ADISCORD_economy_debt_crisis ADISCORD_economy_debt_emergency ADISCORD_economy_debt_default }
  add_ideas = ADISCORD_economy_debt_crisis
 }
""",
        }
        reconciler = (
            "ADISCORD_economy_reconcile_debt_state_after_action = {\n"
            + "".join(branches.values())
            + " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n"
            + "}\n"
        )

        def append_to_reconciler(addition: str) -> str:
            self.assertTrue(reconciler.endswith("}\n"))
            return reconciler[:-2] + addition + "}\n"

        self.assertEqual(debt_reconciler_issues(reconciler), [])
        self.assertTrue(debt_reconciler_issues("ADISCORD_economy_reconcile_debt_state_after_action = {}"))
        metadata_zero = """  if = {
   limit = { check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than } }
   set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 }
  }
"""
        metadata_check_without_write = metadata_zero.replace(
            "   set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 }\n",
            "",
            1,
        )
        state_three = """ else_if = {
  limit = {
   check_variable = { var = ADISCORD_economy_interest_share_income value = 50 compare = less_than }
   check_variable = { var = ADISCORD_economy_debt_state value = 3 compare = greater_than }
  }
  set_variable = { var = ADISCORD_economy_debt_state value = 3 }
  if = {
   limit = { check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 3 compare = greater_than } }
   set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 3 }
  }
  remove_ideas = { ADISCORD_economy_debt_strain ADISCORD_economy_debt_crisis ADISCORD_economy_debt_emergency ADISCORD_economy_debt_default }
  add_ideas = ADISCORD_economy_debt_emergency
 }
"""
        mutations = {
            "missing target zero": reconciler.replace(branches[0], "", 1),
            "duplicate target zero": append_to_reconciler(branches[0]),
            "wrong target zero band": reconciler.replace(
                "value = 10 compare = less_than",
                "value = 11 compare = less_than",
                1,
            ),
            "wrong target one band": reconciler.replace(
                "value = 25 compare = less_than",
                "value = 24 compare = less_than",
                1,
            ),
            "wrong target two band": reconciler.replace(
                "value = 40 compare = less_than",
                "value = 39 compare = less_than",
                1,
            ),
            "extra state predicate": reconciler.replace(
                "check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = greater_than }",
                "check_variable = { var = ADISCORD_economy_debt_state value = 0 compare = greater_than }\n   has_country_flag = hidden_reconcile_gate",
                1,
            ),
            "preserving state comparator": reconciler.replace(
                "ADISCORD_economy_debt_state value = 1 compare = greater_than",
                "ADISCORD_economy_debt_state value = 1 compare = greater_than_or_equals",
                1,
            ),
            "reversed metadata comparator": reconciler.replace(
                "ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than",
                "ADISCORD_economy_last_notified_debt_state value = 0 compare = less_than",
                1,
            ),
            "wrong metadata write target": reconciler.replace(
                "set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 }",
                "set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 4 }",
                1,
            ),
            "missing metadata owner": reconciler.replace(metadata_zero, "", 1),
            "duplicate metadata owner": reconciler.replace(
                metadata_zero, metadata_zero + metadata_zero, 1
            ),
            "extra metadata condition without write": reconciler.replace(
                metadata_zero, metadata_zero + metadata_check_without_write, 1
            ),
            "unowned metadata write": reconciler.replace(
                metadata_zero,
                "  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 }\n",
                1,
            ),
            "extra unowned metadata write": reconciler.replace(
                metadata_zero,
                metadata_zero
                + "  set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 }\n",
                1,
            ),
            "dead metadata owner": reconciler.replace(
                "check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than }",
                "check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than } always = no",
                1,
            ),
            "negated metadata owner": reconciler.replace(
                "check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than }",
                "NOT = { check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than } }",
                1,
            ),
            "extra metadata predicate": reconciler.replace(
                "check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than }",
                "check_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 compare = greater_than } has_country_flag = hidden_metadata_gate",
                1,
            ),
            "extra state write": append_to_reconciler(
                " add_to_variable = { var = ADISCORD_economy_debt_state value = -1 }\n"
            ),
            "state three branch": append_to_reconciler(state_three),
            "settlement streak": append_to_reconciler(
                " set_variable = { var = ADISCORD_economy_debt_emergency_streak value = 0 }\n"
            ),
            "notification queue": append_to_reconciler(
                " ADISCORD_economy_queue_debt_notification = yes\n"
            ),
            "country event": append_to_reconciler(
                " country_event = { id = ADISCORD_economy.999 }\n"
            ),
            "missing compatibility mirror": reconciler.replace(
                " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n",
                "",
                1,
            ),
            "wrong compatibility mirror value": reconciler.replace(
                "ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state",
                "ADISCORD_economy_debt_crisis_level value = 0",
                1,
            ),
            "compatibility mirror before state branches": reconciler.replace(
                " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n",
                "",
                1,
            ).replace(
                "ADISCORD_economy_reconcile_debt_state_after_action = {\n",
                "ADISCORD_economy_reconcile_debt_state_after_action = {\n"
                " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n",
                1,
            ),
            "duplicate compatibility mirror": reconciler.replace(
                " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n",
                " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n"
                " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n",
                1,
            ),
            "conditional compatibility mirror": reconciler.replace(
                " set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n",
                " if = { limit = { always = yes } set_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state } }\n",
                1,
            ),
        }
        for name, invalid in mutations.items():
            with self.subTest(reconciler_mutation=name):
                self.assertNotEqual(invalid, reconciler)
                self.assertTrue(parse_clausewitz(invalid))
                self.assertTrue(debt_reconciler_issues(invalid))


class WeeklyEconomyContracts(unittest.TestCase):
    def test_schema_twelve_maps_construction_policy_to_research_without_resetting_ledger(self):
        self.assertFalse(migration_contract_issues(EFFECTS))
        migration = unique_block(EFFECTS, "ADISCORD_economy_migrate_schema")
        self.assertRegex(
            migration,
            r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_schema_version"
            r"\s+value\s*=\s*12\s+compare\s*=\s*less_than\s*\}",
        )
        self.assertEqual(
            len(
                re.findall(
                    r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_schema_version"
                    r"\s+value\s*=\s*12\s*\}",
                    migration,
                )
            ),
            1,
        )
        self.assertRegex(
            migration,
            r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_research_spending_mode"
            r"\s+value\s*=\s*ADISCORD_economy_construction_spending_mode\s*\}",
        )
        self.assertRegex(
            migration,
            r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_research_budget_change_cooldown"
            r"\s+value\s*=\s*0\s*\}",
        )
        for obsolete in (
            "ADISCORD_economy_construction_spending_mode",
            "ADISCORD_economy_construction_budget_change_cooldown",
        ):
            self.assertRegex(migration, rf"clear_variable\s*=\s*{obsolete}\b")
        for idea in range(1, 6):
            self.assertIn(f"ADISCORD_economy_construction_spending_{idea}", migration)

        protected_ledger = (
            "treasury",
            "debt",
            "accounting_period_treasury_start",
            "last_period_treasury_before",
            "last_period_treasury_after",
            "last_period_income",
            "last_period_expenses",
            "last_period_balance",
            "last_period_debt_added",
            "last_period_debt_paid",
            "current_month_action_income",
            "current_month_action_costs",
            "current_month_debt_added",
            "current_month_debt_paid",
        )
        for suffix in protected_ledger:
            variable = f"ADISCORD_economy_{suffix}"
            self.assertNotRegex(
                migration,
                rf"(?:set_variable|clear_variable)\s*=\s*(?:\{{[^{{}}]*var\s*=\s*)?{variable}\b",
                variable,
            )

    def test_construction_policy_is_retired_and_construction_spend_tracks_real_activity(self):
        retirement_issues = migration_contract_issues(
            EFFECTS,
            {
                "triggers": TRIGGERS,
                "ideas": ECONOMY_IDEAS,
                "scripted_gui": SCRIPTED_GUI,
                "scripted_loc": SCRIPTED_LOC,
                "economy_ai": ECONOMY_AI,
            },
        )
        live_issues = [issue for issue in retirement_issues if "outside migration" in issue]
        self.assertFalse(live_issues, f"live construction-policy API: {live_issues}")

        construction = unique_block(
            EFFECTS, "ADISCORD_economy_calculate_construction_expenses"
        )
        factory_cache = unique_block(
            EFFECTS, "ADISCORD_economy_cache_weekly_factory_sources"
        )
        for activity_scalar, cached_scalar in (
            (
                "num_of_civilian_factories",
                "ADISCORD_economy_cached_civilian_factories",
            ),
            (
                "num_of_available_civilian_factories",
                "ADISCORD_economy_cached_available_civilian_factories",
            ),
        ):
            self.assertIn(activity_scalar, factory_cache)
            self.assertIn(cached_scalar, construction)
            self.assertNotIn(activity_scalar, construction)
        self.assertRegex(
            construction,
            r"subtract_from_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_active_construction_temp"
            r"\s+value\s*=\s*ADISCORD_economy_cached_available_civilian_factories\s*\}",
        )
        self.assertNotIn("spending_mode", construction)
        development = unique_block(
            EFFECTS, "ADISCORD_economy_calculate_development_multiplier"
        )
        self.assertNotIn("construction_spending", development)

    def test_zero_construction_activity_has_no_positive_fixed_expense(self):
        construction = unique_block(
            EFFECTS, "ADISCORD_economy_calculate_construction_expenses"
        )
        initial_values = [
            float(value)
            for value in re.findall(
                r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_construction_expenses"
                r"\s+value\s*=\s*(-?\d+(?:\.\d+)?)\s*\}",
                construction,
            )
        ]
        self.assertEqual(
            initial_values,
            [0.0],
            "zero installed and active civilian factories must start at zero expense",
        )
        self.assertNotRegex(
            construction,
            r"add_to_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_construction_expenses"
            r"\s+value\s*=\s*(?:0*[1-9]\d*(?:\.\d+)?|0*\.0*[1-9]\d*)\s*\}",
            "construction expense cannot contain a positive fixed output term",
        )

    def test_live_research_policy_localisation_uses_canonical_ui_ids(self):
        budget_controls = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_budget_controls_tt"
        )
        self.assertIn("наук", budget_controls.lower())
        self.assertNotIn("строительств", budget_controls.lower())

        row = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_budget_research_row"
        )
        self.assertIn("Наука", row)
        self.assertIn("[GetADISCORDResearchSpendingModeLoc]", row)

        controls = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_research_controls_tt"
        )
        self.assertIn("[?ADISCORD_economy_research_spending_mode|0]", controls)
        self.assertIn(
            "[?ADISCORD_economy_research_budget_change_cooldown|0]", controls
        )
        self.assertNotIn("ADISCORD_economy_construction_spending_mode", controls)
        self.assertNotIn(
            "ADISCORD_economy_construction_budget_change_cooldown", controls
        )

        expected = {
            1: ("§G-40%§!", "§R-8%§!"),
            2: ("§G-20%§!", "§R-3%§!"),
            3: ("§Y0%§!", "§Y0%§!"),
            4: ("§R+30%§!", "§G+3%§!"),
            5: ("§R+60%§!", "§G+5%§!"),
        }
        for expense, research_speed in expected.values():
            self.assertIn(expense, controls)
            self.assertIn(research_speed, controls)
        self.assertIn("скорость строительства §G+2%§!", controls)

        keys = localisation_key_set(ECONOMY_LOC)
        for level, (expense, research_speed) in expected.items():
            level_tooltip = localisation_value(
                ECONOMY_LOC, f"ADISCORD_economy_research_level_{level}_tt"
            )
            effect_tooltip = localisation_value(
                ECONOMY_LOC, f"ADISCORD_economy_research_effects_{level}"
            )
            for value in (level_tooltip, effect_tooltip):
                self.assertIn(f"расходы {expense}".lower(), value.lower())
                self.assertIn(
                    f"скорость исследований {research_speed}".lower(),
                    value.lower(),
                )
                for obsolete_claim in (
                    "скорость всех строек",
                    "гражданских",
                    "военных",
                    "развитие",
                    "стабильность",
                ):
                    self.assertNotIn(obsolete_claim, value.lower())
                if level == 5:
                    self.assertIn("скорость строительства §G+2%§!", value)
                else:
                    self.assertNotIn("строительств", value.lower())

            mode = localisation_value(
                ECONOMY_LOC, f"ADISCORD_economy_research_funding_mode_{level}"
            )
            self.assertIn("наук", mode.lower())

            idea_key = f"ADISCORD_economy_research_spending_{level}"
            self.assertNotIn(
                f"ADISCORD_economy_construction_spending_{level}", keys
            )
            self.assertIn(idea_key, keys)
            self.assertIn(f"{idea_key}_desc", keys)
            idea_name = localisation_value(ECONOMY_LOC, idea_key)
            idea_description = localisation_value(ECONOMY_LOC, f"{idea_key}_desc")
            self.assertIn("наук", idea_name.lower())
            self.assertIn(
                f"расходы {expense}".lower(), idea_description.lower()
            )
            self.assertIn(
                f"скорость исследований {research_speed}".lower(),
                idea_description.lower(),
            )
            if level == 5:
                self.assertIn(
                    "скорость строительства §G+2%§!", idea_description
                )
            else:
                self.assertNotIn("строительств", idea_description.lower())

        for arrow_key in (
            "ADISCORD_economy_research_decrease_tt",
            "ADISCORD_economy_research_increase_tt",
        ):
            self.assertIn(
                "наук", localisation_value(ECONOMY_LOC, arrow_key).lower()
            )

    def test_research_policy_has_five_levels_and_level_five_construction_bonus_is_bounded(self):
        self.assertFalse(research_policy_flow_issues(EFFECTS))
        research = unique_block(EFFECTS, "ADISCORD_economy_calculate_research_expenses")
        self.assertIn("ADISCORD_economy_research_spending_mode", research)
        multipliers = {
            float(value)
            for value in re.findall(
                r"multiply_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_research_expenses"
                r"\s+value\s*=\s*(-?\d+(?:\.\d+)?)\s*\}",
                research,
            )
        }
        self.assertEqual(multipliers, {0.60, 0.80, 1.00, 1.30, 1.60})
        self.assertRegex(
            EFFECTS,
            r"clamp_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_research_spending_mode"
            r"\s+min\s*=\s*1\s+max\s*=\s*5\s*\}",
        )
        self.assertRegex(
            EFFECTS,
            r"clamp_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_research_budget_change_cooldown"
            r"\s+min\s*=\s*0\s+max\s*=\s*3\s*\}",
        )

        expected_research = {1: -0.08, 2: -0.03, 3: 0.0, 4: 0.03, 5: 0.05}
        for level, expected in expected_research.items():
            idea = unique_block(
                ECONOMY_IDEAS, f"ADISCORD_economy_research_spending_{level}"
            )
            self.assertEqual(numeric_values(idea, "research_speed_factor"), [expected])
            construction_bonuses = numeric_values(
                idea, "production_speed_buildings_factor"
            )
            if level == 5:
                self.assertEqual(construction_bonuses, [0.02])
            else:
                self.assertEqual(construction_bonuses, [])
        all_construction_bonuses = numeric_values(
            "\n".join(
                unique_block(
                    ECONOMY_IDEAS, f"ADISCORD_economy_research_spending_{level}"
                )
                for level in range(1, 6)
            ),
            "production_speed_buildings_factor",
        )
        self.assertTrue(all(value <= 0.03 for value in all_construction_bonuses))

    def test_policy_accounting_tables_have_five_exact_condition_owned_levels(self):
        tax_outputs = {
            "ADISCORD_economy_personal_income",
            "ADISCORD_economy_business_income",
            "ADISCORD_economy_factory_income",
            "ADISCORD_economy_consumer_goods_income",
        }
        expected_tax = {
            1: (
                ("multiply_variable", "ADISCORD_economy_personal_income", 0.65),
                ("multiply_variable", "ADISCORD_economy_business_income", 0.85),
                ("multiply_variable", "ADISCORD_economy_factory_income", 0.90),
                ("add_to_variable", "ADISCORD_economy_consumer_goods_income", 0.30),
            ),
            2: (
                ("multiply_variable", "ADISCORD_economy_personal_income", 0.85),
                ("multiply_variable", "ADISCORD_economy_business_income", 0.95),
                ("multiply_variable", "ADISCORD_economy_factory_income", 0.95),
                ("add_to_variable", "ADISCORD_economy_consumer_goods_income", 0.10),
            ),
            3: (
                ("multiply_variable", "ADISCORD_economy_personal_income", 1.00),
                ("multiply_variable", "ADISCORD_economy_business_income", 1.00),
                ("multiply_variable", "ADISCORD_economy_factory_income", 1.00),
                ("add_to_variable", "ADISCORD_economy_consumer_goods_income", 0.00),
            ),
            4: (
                ("multiply_variable", "ADISCORD_economy_personal_income", 1.15),
                ("multiply_variable", "ADISCORD_economy_business_income", 1.08),
                ("multiply_variable", "ADISCORD_economy_factory_income", 1.05),
                ("add_to_variable", "ADISCORD_economy_consumer_goods_income", -0.10),
            ),
            5: (
                ("multiply_variable", "ADISCORD_economy_personal_income", 1.35),
                ("multiply_variable", "ADISCORD_economy_business_income", 1.15),
                ("multiply_variable", "ADISCORD_economy_factory_income", 1.10),
                ("add_to_variable", "ADISCORD_economy_consumer_goods_income", -0.30),
            ),
        }
        tables = {
            "tax": (
                "ADISCORD_economy_apply_tax_burden_to_income",
                "ADISCORD_economy_tax_burden_mode",
                tax_outputs,
                expected_tax,
            ),
            "army": (
                "ADISCORD_economy_calculate_army_expenses",
                "ADISCORD_economy_army_spending_mode",
                {"ADISCORD_economy_army_expenses"},
                {
                    level: (("multiply_variable", "ADISCORD_economy_army_expenses", factor),)
                    for level, factor in enumerate((0.50, 0.75, 1.00, 1.50, 2.50), 1)
                },
            ),
            "research": (
                "ADISCORD_economy_calculate_research_expenses",
                "ADISCORD_economy_research_spending_mode",
                {"ADISCORD_economy_research_expenses"},
                {
                    level: (("multiply_variable", "ADISCORD_economy_research_expenses", factor),)
                    for level, factor in enumerate((0.60, 0.80, 1.00, 1.30, 1.60), 1)
                },
            ),
            "social": (
                "ADISCORD_economy_calculate_social_expenses",
                "ADISCORD_economy_social_spending_mode",
                {"ADISCORD_economy_social_expenses"},
                {
                    level: (("multiply_variable", "ADISCORD_economy_social_expenses", factor),)
                    for level, factor in enumerate((0.45, 0.75, 1.00, 1.35, 1.80), 1)
                },
            ),
        }
        for policy, (effect_name, target, outputs, expected) in tables.items():
            with self.subTest(policy=policy):
                effect = unique_block(EFFECTS, effect_name)
                self.assertEqual(policy_multiplier_rows(effect, target, outputs), expected)

        research = unique_block(EFFECTS, "ADISCORD_economy_calculate_research_expenses")
        for level in range(1, 6):
            with self.subTest(mutation=f"research level {level} unconditional"):
                mutation = re.sub(
                    rf"check_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_research_spending_mode"
                    rf"\s+value\s*=\s*{level}\s+compare\s*=\s*equals\s*\}}",
                    "always = yes",
                    research,
                    count=1,
                )
                self.assertNotEqual(
                    policy_multiplier_rows(
                        mutation,
                        "ADISCORD_economy_research_spending_mode",
                        {"ADISCORD_economy_research_expenses"},
                    ),
                    tables["research"][3],
                )

    def test_policy_previews_cache_clamped_targets_and_exact_weekly_balance_deltas(self):
        refresh = unique_block(EFFECTS, "ADISCORD_economy_refresh_policy_previews")
        for policy, mode in (
            ("tax", "tax_burden"),
            ("army", "army_spending"),
            ("research", "research_spending"),
            ("social", "social_spending"),
        ):
            for direction, offset in (("increase", "1"), ("decrease", "-1")):
                target = f"ADISCORD_economy_{policy}_{direction}_target_level"
                delta = f"ADISCORD_economy_{policy}_{direction}_weekly_balance_delta"
                self.assertRegex(
                    refresh,
                    rf"set_variable\s*=\s*\{{\s*var\s*=\s*{target}\s+value\s*=\s*"
                    rf"ADISCORD_economy_{mode}_mode\s*\}}",
                )
                self.assertRegex(
                    refresh,
                    rf"add_to_variable\s*=\s*\{{\s*var\s*=\s*{target}\s+value\s*=\s*{re.escape(offset)}\s*\}}",
                )
                self.assertRegex(
                    refresh,
                    rf"clamp_variable\s*=\s*\{{\s*var\s*=\s*{target}\s+min\s*=\s*1\s+max\s*=\s*5\s*\}}",
                )
                self.assertRegex(
                    refresh,
                    rf"set_variable\s*=\s*\{{\s*var\s*=\s*{delta}\s+value\s*=\s*"
                    r"ADISCORD_economy_policy_preview_weekly_delta_temp\s*\}",
                )

            preview = unique_block(EFFECTS, f"ADISCORD_economy_preview_{policy}_policy")
            preview_blocks = reachable_script_blocks(
                (EFFECTS,), (f"ADISCORD_economy_preview_{policy}_policy",)
            )
            preview_graph = "\n".join(preview_blocks.values())
            self.assertIn(
                f"ADISCORD_economy_{mode}_mode value = ADISCORD_economy_policy_preview_target_temp",
                preview,
            )
            self.assertIn("ADISCORD_economy_policy_preview_weekly_delta_temp", preview_graph)
            self.assertNotIn("every_country", preview_graph)
            self.assertNotIn("every_owned_state", preview_graph)
            if policy == "tax":
                self.assertIn("ADISCORD_economy_recalculate_tax_dependent_income = yes", preview)
                self.assertIn("ADISCORD_economy_save_tax_policy_preview_macro_state = yes", preview)
                self.assertIn("ADISCORD_economy_calculate_macro_indicators = yes", preview)
                self.assertIn("ADISCORD_economy_sum_expenses = yes", preview)
                self.assertIn("ADISCORD_economy_calculate_monthly_balance = yes", preview)
                macro_owners = [
                    body
                    for body in assignment_blocks(preview, "if")
                    if "ADISCORD_economy_calculate_macro_indicators = yes" in body
                ]
                self.assertEqual(len(macro_owners), 1)
                self.assertRegex(
                    macro_owners[0],
                    r"limit\s*=\s*\{\s*NOT\s*=\s*\{\s*check_variable\s*=\s*\{\s*"
                    r"var\s*=\s*ADISCORD_economy_monthly_income\s+value\s*=\s*"
                    r"ADISCORD_economy_policy_preview_current_monthly_temp\s+"
                    r"compare\s*=\s*equals\s*\}\s*\}\s*\}",
                )
                self.assertRegex(
                    preview,
                    r"set_temp_variable\s*=\s*\{\s*var\s*=\s*"
                    r"ADISCORD_economy_policy_preview_weekly_delta_temp\s+value\s*=\s*"
                    r"ADISCORD_economy_monthly_balance\s*\}",
                )
                self.assertRegex(
                    preview,
                    r"subtract_from_temp_variable\s*=\s*\{\s*var\s*=\s*"
                    r"ADISCORD_economy_policy_preview_weekly_delta_temp\s+value\s*=\s*"
                    r"ADISCORD_economy_policy_preview_saved_monthly_balance_temp\s*\}",
                )
                self.assertIn("value = 3", preview)
                self.assertIn("value = 13", preview)
            else:
                self.assertIn(
                    f"ADISCORD_economy_calculate_{policy}_expenses = yes", preview
                )
                self.assertIn("ADISCORD_economy_policy_preview_uses_cached_base_temp", preview)
                self.assertIn(
                    "ADISCORD_economy_finish_expense_policy_preview", preview_blocks
                )

        expense_finish = unique_block(
            EFFECTS, "ADISCORD_economy_finish_expense_policy_preview"
        )
        self.assertIn("value = 3", expense_finish)
        self.assertIn("value = 13", expense_finish)

        # Controlled debt-tier fixture: an income change alters both revenue and
        # the interest-derived debt-service expense. The preview must report the
        # exact balance delta rather than the tempting income-only shortcut.
        def weekly_tax_delta(current_income, target_income, debt):
            def monthly_balance(income):
                fiscal_stress = 50
                debt_ratio = debt * 100 / max(income * 12, 1)
                creditworthiness = 60 - fiscal_stress / 2 - debt_ratio / 3
                interest_rate = 3
                interest_rate += 1 if debt_ratio >= 40 else 0
                interest_rate += 1 if fiscal_stress >= 30 else 0
                interest_rate += 2 if creditworthiness < 40 else 0
                interest_rate += 4 if creditworthiness < 25 else 0
                debt_service = debt * interest_rate / 1200
                return income - (90 + debt_service)

            return (monthly_balance(target_income) - monthly_balance(current_income)) * 3 / 13

        # Personal-only tax base: adjacent level 3 (1.00) -> level 4 (1.15).
        tier_crossing = weekly_tax_delta(100, 115, 500)
        income_only = (115 - 100) * 3 / 13
        self.assertAlmostEqual(tier_crossing, 3.5576923076923075, places=10)
        self.assertNotAlmostEqual(tier_crossing, income_only, places=10)
        self.assertAlmostEqual(weekly_tax_delta(100, 115, 0), income_only, places=10)

        metrics = unique_block(EFFECTS, "ADISCORD_economy_calculate_debt_metrics")
        interest = unique_block(EFFECTS, "ADISCORD_economy_calculate_interest_rate")
        debt_service = unique_block(
            EFFECTS, "ADISCORD_economy_calculate_debt_service_amount"
        )
        self.assertRegex(
            metrics,
            r"value\s*=\s*ADISCORD_economy_monthly_income\s*\}\s*"
            r"multiply_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_income_denominator_temp\s+value\s*=\s*12",
        )
        self.assertRegex(
            interest,
            r"ADISCORD_economy_debt_income_ratio\s+value\s*=\s*40\s+compare\s*=\s*"
            r"greater_than_or_equals\s*\}\s*\}\s*add_to_variable\s*=\s*\{\s*"
            r"var\s*=\s*ADISCORD_economy_interest_rate\s+value\s*=\s*1",
        )
        self.assertRegex(
            debt_service,
            r"value\s*=\s*ADISCORD_economy_debt\s*\}\s*"
            r"multiply_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_service\s+"
            r"value\s*=\s*ADISCORD_economy_interest_rate\s*\}\s*"
            r"divide_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_service\s+value\s*=\s*1200",
        )

    def test_each_policy_click_reaches_only_its_targeted_refresh_path(self):
        expected = {
            "tax": "ADISCORD_economy_refresh_tax_policy",
            "army": "ADISCORD_economy_refresh_army_policy",
            "research": "ADISCORD_economy_refresh_research_policy",
            "social": "ADISCORD_economy_refresh_social_policy",
        }
        forbidden = (
            "ADISCORD_economy_full_refresh",
            "ADISCORD_economy_light_update",
            "ADISCORD_economy_recount_economic_buildings",
            "ADISCORD_economy_count_buildings",
            "ADISCORD_economy_calculate_income",
            "ADISCORD_economy_calculate_expenses",
            "ADISCORD_economy_recalculate_policy_modifiers",
            "ADISCORD_economy_refresh_spending_ideas",
            "ADISCORD_economy_calculate_development_multiplier",
            "ADISCORD_economy_apply_development_modifier_factors_to_economic_growth",
            "ADISCORD_economy_base_monthly_development_gain",
            "ADISCORD_economy_monthly_development_multiplier",
            "ADISCORD_economy_development_building_temp",
            "ADISCORD_economy_monthly_development_gain",
            "ADISCORD_economy_development_progress",
            "every_country",
            "every_owned_state",
        )
        for policy, refresh_name in expected.items():
            for direction in ("increase", "decrease"):
                noun = "tax_burden" if policy == "tax" else f"{policy}_spending"
                mutator = f"ADISCORD_economy_{direction}_{noun}"
                body = unique_block(EFFECTS, mutator)
                self.assertIn(f"{refresh_name} = yes", body, mutator)
                reachable = reachable_script_blocks((EFFECTS,), (mutator,))
                flattened = "\n".join(reachable.values())
                for forbidden_name in forbidden:
                    self.assertNotIn(forbidden_name, flattened, mutator)

        for policy, refresh_name in expected.items():
            refresh = unique_block(EFFECTS, refresh_name)
            self.assertIn(
                "ADISCORD_economy_finish_targeted_policy_refresh = yes", refresh
            )
            if policy == "tax":
                self.assertEqual(tax_refresh_macro_flow_issues(EFFECTS), [])
            else:
                self.assertIn(f"ADISCORD_economy_calculate_{policy}_expenses = yes", refresh)
                self.assertNotIn("ADISCORD_economy_calculate_macro_indicators", refresh)

        targeted_tail = unique_block(
            EFFECTS, "ADISCORD_economy_finish_targeted_policy_refresh"
        )
        self.assertEqual(
            set(re.findall(r"\b(ADISCORD_economy_[A-Za-z0-9_]+)\s*=\s*yes", targeted_tail)),
            {
                "ADISCORD_economy_sum_expenses",
                "ADISCORD_economy_calculate_monthly_balance",
                "ADISCORD_economy_calculate_weekly_budget",
                "ADISCORD_economy_refresh_policy_previews",
                "ADISCORD_economy_update_gui",
            },
        )
        self.assertLess(
            targeted_tail.index("ADISCORD_economy_sum_expenses = yes"),
            targeted_tail.index("ADISCORD_economy_calculate_monthly_balance = yes"),
        )

        facade = unique_block(
            EFFECTS, "ADISCORD_economy_refresh_after_budget_control_change"
        )
        self.assertEqual(
            facade.strip(), "ADISCORD_economy_refresh_research_policy = yes"
        )
        for policy in expected:
            for direction in ("increase", "decrease"):
                noun = "tax_burden" if policy == "tax" else f"{policy}_spending"
                click = unique_block(
                    SCRIPTED_GUI, f"ADISCORD_economy_{policy}_{direction}_click"
                )
                self.assertEqual(
                    click.strip(), f"ADISCORD_economy_{direction}_{noun} = yes"
                )
        self.assertNotIn("ADISCORD_economy_construction_increase_click", SCRIPTED_GUI)
        self.assertNotIn("ADISCORD_economy_construction_decrease_click", SCRIPTED_GUI)

    def test_tax_targeted_refresh_updates_macro_only_when_income_changes(self):
        self.assertEqual(tax_refresh_macro_flow_issues(EFFECTS), [])

        refresh = unique_block(EFFECTS, "ADISCORD_economy_refresh_tax_policy")
        mutations = {
            "comparison is not negated": refresh.replace(
                "NOT = { check_variable = { var = ADISCORD_economy_monthly_income value = ADISCORD_economy_tax_refresh_saved_income_temp compare = equals } }",
                "check_variable = { var = ADISCORD_economy_monthly_income value = ADISCORD_economy_tax_refresh_saved_income_temp compare = equals }",
                1,
            ),
            "wrong comparator": refresh.replace(
                "compare = equals",
                "compare = greater_than",
                1,
            ),
            "dead self-comparison": refresh.replace(
                "value = ADISCORD_economy_monthly_income",
                "value = ADISCORD_economy_tax_refresh_saved_income_temp",
                1,
            ),
            "macro call is unconditional": re.sub(
                r"if\s*=\s*\{\s*limit\s*=\s*\{\s*NOT\s*=\s*\{\s*check_variable\s*=\s*\{\s*"
                r"var\s*=\s*ADISCORD_economy_monthly_income\s+value\s*=\s*"
                r"ADISCORD_economy_tax_refresh_saved_income_temp\s+compare\s*=\s*equals\s*"
                r"\}\s*\}\s*\}\s*ADISCORD_economy_calculate_macro_indicators\s*=\s*yes\s*\}",
                "ADISCORD_economy_calculate_macro_indicators = yes",
                refresh,
                count=1,
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutation, refresh, "mutation fixture did not change source")
                wrapped = f"ADISCORD_economy_refresh_tax_policy = {{{mutation}}}"
                self.assertTrue(tax_refresh_macro_flow_issues(wrapped))

    def test_policy_preview_selectors_use_cached_directional_targets(self):
        effect_prefixes = {
            "tax": "ADISCORD_economy_tax_effects",
            "army": "ADISCORD_economy_army_effects",
            "research": "ADISCORD_economy_research_effects",
            "social": "ADISCORD_economy_social_effects",
        }
        variables = {
            "tax": (
                "ADISCORD_economy_tax_burden_mode",
                "ADISCORD_economy_tax_change_cooldown",
            ),
            "army": (
                "ADISCORD_economy_army_spending_mode",
                "ADISCORD_economy_army_budget_change_cooldown",
            ),
            "research": (
                "ADISCORD_economy_research_spending_mode",
                "ADISCORD_economy_research_budget_change_cooldown",
            ),
            "social": (
                "ADISCORD_economy_social_spending_mode",
                "ADISCORD_economy_social_budget_change_cooldown",
            ),
        }
        for policy, localisation_prefix in effect_prefixes.items():
            for direction in ("Increase", "Decrease"):
                selector = unique_defined_text(
                    SCRIPTED_LOC,
                    f"GetADISCORDEconomy{policy.title()}{direction}EffectLoc",
                )
                target = (
                    f"ADISCORD_economy_{policy}_{direction.lower()}_target_level"
                )
                self.assertEqual(selector.count(target), 4)
                for level in range(1, 6):
                    self.assertIn(f"{localisation_prefix}_{level}", selector)
                reason_selector = (
                    f"GetADISCORDEconomy{policy.title()}{direction}PreviewLoc"
                )
                mode_var, cooldown_var = variables[policy]
                self.assertEqual(
                    policy_selector_issues(
                        SCRIPTED_LOC,
                        reason_selector,
                        mode_var,
                        cooldown_var,
                        direction.lower(),
                    ),
                    [],
                )

        for alias in (
            "GetADISCORDConstructionSpendingModeLoc",
            "GetADISCORDConstructionSpendingEffectsLoc",
            "GetADISCORDConstructionIncreasePolicyPreviewLoc",
            "GetADISCORDConstructionDecreasePolicyPreviewLoc",
        ):
            self.assertNotIn(alias, SCRIPTED_LOC)

    def test_policy_previews_are_side_effect_bounded_and_restore_live_state(self):
        restored = {
            "tax": {
                "ADISCORD_economy_tax_burden_mode": "ADISCORD_economy_policy_preview_saved_mode_temp",
                "ADISCORD_economy_monthly_income": "ADISCORD_economy_policy_preview_current_monthly_temp",
                "ADISCORD_economy_personal_income": "ADISCORD_economy_policy_preview_saved_personal_temp",
                "ADISCORD_economy_business_income": "ADISCORD_economy_policy_preview_saved_business_temp",
                "ADISCORD_economy_consumer_goods_income": "ADISCORD_economy_policy_preview_saved_consumer_goods_temp",
                "ADISCORD_economy_factory_income": "ADISCORD_economy_policy_preview_saved_factory_temp",
            },
            "army": {
                "ADISCORD_economy_army_spending_mode": "ADISCORD_economy_policy_preview_saved_mode_temp",
                "ADISCORD_economy_army_expenses": "ADISCORD_economy_policy_preview_current_expense_temp",
            },
            "research": {
                "ADISCORD_economy_research_spending_mode": "ADISCORD_economy_policy_preview_saved_mode_temp",
                "ADISCORD_economy_research_expenses": "ADISCORD_economy_policy_preview_current_expense_temp",
            },
            "social": {
                "ADISCORD_economy_social_spending_mode": "ADISCORD_economy_policy_preview_saved_mode_temp",
                "ADISCORD_economy_social_expenses": "ADISCORD_economy_policy_preview_current_expense_temp",
            },
        }
        tax_macro_restored = {
            variable: f"ADISCORD_economy_policy_preview_saved_{variable.removeprefix('ADISCORD_economy_')}_temp"
            for variable in (
                "ADISCORD_economy_debt_income_denominator_temp",
                "ADISCORD_economy_debt_income_ratio",
                "ADISCORD_economy_weekly_interest",
                "ADISCORD_economy_interest_income_denominator_temp",
                "ADISCORD_economy_interest_share_income",
                "ADISCORD_economy_interest_pressure_temp",
                "ADISCORD_economy_debt_streak_pressure_temp",
                "ADISCORD_economy_debt_pressure",
                "ADISCORD_economy_creditworthiness",
                "ADISCORD_economy_credit_temp",
                "ADISCORD_economy_debt_crisis_level",
                "ADISCORD_economy_interest_rate",
                "ADISCORD_economy_debt_service",
                "ADISCORD_economy_investment_confidence",
                "ADISCORD_economy_confidence_temp",
                "ADISCORD_economy_state_financial_control",
                "ADISCORD_economy_control_temp",
                "ADISCORD_economy_austerity_level",
                "ADISCORD_economy_monthly_expenses",
                "ADISCORD_economy_monthly_balance",
            )
        }
        macro_mutator_graph = "\n".join(
            reachable_script_blocks(
                (EFFECTS, MODIFIER_EFFECTS),
                (
                    "ADISCORD_economy_calculate_macro_indicators",
                    "ADISCORD_economy_sum_expenses",
                    "ADISCORD_economy_calculate_monthly_balance",
                ),
            ).values()
        )
        macro_mutated_variables = set(
            re.findall(
                r"(?:set_variable|add_to_variable|subtract_from_variable|"
                r"multiply_variable|divide_variable|clamp_variable)\s+var\s+"
                r"(ADISCORD_economy_[A-Za-z0-9_]+)",
                macro_mutator_graph,
            )
        )
        self.assertEqual(macro_mutated_variables, set(tax_macro_restored))
        save_macro = unique_block(
            EFFECTS, "ADISCORD_economy_save_tax_policy_preview_macro_state"
        )
        restore_macro = unique_block(
            EFFECTS, "ADISCORD_economy_restore_tax_policy_preview_macro_state"
        )
        for variable, saved in tax_macro_restored.items():
            self.assertRegex(
                save_macro,
                rf"set_temp_variable\s*=\s*\{{\s*var\s*=\s*{re.escape(saved)}\s+"
                rf"value\s*=\s*{re.escape(variable)}\s*\}}",
            )
            self.assertRegex(
                restore_macro,
                rf"set_variable\s*=\s*\{{\s*var\s*=\s*{re.escape(variable)}\s+"
                rf"value\s*=\s*{re.escape(saved)}\s*\}}",
            )
        self.assertFalse(task6_policy_preview_persistent_state_issues(EFFECTS))
        preview = unique_block(EFFECTS, "ADISCORD_economy_preview_tax_policy")
        preview_mutation = EFFECTS.replace(
            preview,
            preview
            + "\n\tset_variable = { var = ADISCORD_economy_debt_state value = 4 }",
            1,
        )
        self.assertNotEqual(preview_mutation, EFFECTS)
        self.assertTrue(
            task6_policy_preview_persistent_state_issues(preview_mutation)
        )

        for policy, assignments in restored.items():
            preview_name = f"ADISCORD_economy_preview_{policy}_policy"
            preview = unique_block(EFFECTS, preview_name)
            preview_graph = "\n".join(
                reachable_script_blocks((EFFECTS,), (preview_name,)).values()
            )
            for variable, saved in assignments.items():
                self.assertIn(f"var = {saved} value = {variable}", preview)
                self.assertIn(f"var = {variable} value = {saved}", preview)
            for forbidden in (
                "ADISCORD_economy_update_gui",
                "ADISCORD_economy_refresh_spending_ideas",
                "ADISCORD_economy_apply_weekly_balance",
                "ADISCORD_economy_apply_monthly_balance",
                "ADISCORD_economy_take_debt",
                "add_ideas",
                "remove_ideas",
                "every_country",
                "every_owned_state",
            ):
                self.assertNotIn(forbidden, preview_graph)

            if policy == "tax":
                self.assertLess(
                    preview.index("ADISCORD_economy_save_tax_policy_preview_macro_state = yes"),
                    preview.index("ADISCORD_economy_calculate_macro_indicators = yes"),
                )
                self.assertLess(
                    preview.index("ADISCORD_economy_calculate_monthly_balance = yes"),
                    preview.index("ADISCORD_economy_restore_tax_policy_preview_macro_state = yes"),
                )

            if policy != "tax":
                self.assertIn(
                    "ADISCORD_economy_policy_preview_uses_cached_base_temp value = 1",
                    preview,
                )
                self.assertIn(
                    "ADISCORD_economy_policy_preview_uses_cached_base_temp value = 0",
                    preview,
                )

    def test_debt_capacity_is_absent_from_runtime_and_public_modifier_api(self):
        scanned_boundary = {}
        text_suffixes = {".txt", ".gui", ".gfx", ".yml", ".yaml", ".md", ".py"}
        for directory in ("common", "interface", "events", "localisation", "docs", "tools"):
            for path in (ROOT / directory).rglob("*"):
                if path.is_file() and path.suffix.casefold() in text_suffixes:
                    scanned_boundary[path.relative_to(ROOT).as_posix()] = path.read_text(
                        encoding="utf-8-sig", errors="replace"
                    )
        self.assertFalse(retired_capacity_boundary_issues(scanned_boundary))

        migration = unique_block(EFFECTS, "ADISCORD_economy_migrate_schema")
        for retired_cache in (
            "ADISCORD_economy_capacity_factor_temp",
            "ADISCORD_economy_capacity_temp",
            "ADISCORD_economy_policy_preview_saved_capacity_factor_temp_temp",
            "ADISCORD_economy_policy_preview_saved_capacity_temp_temp",
            "ADISCORD_economy_policy_preview_saved_debt_capacity_temp",
        ):
            self.assertRegex(
                migration,
                rf"clear_variable\s*=\s*{retired_cache}\b",
                retired_cache,
            )
        for line in migration.splitlines():
            if "debt_capacity" in line.casefold():
                self.assertRegex(
                    line,
                    r"clear_variable\s*=\s*ADISCORD_[A-Za-z0-9_]*debt_capacity[A-Za-z0-9_]*",
                    "schema migration may only delete the retired API",
                )

        scanned = {
            "common/scripted_effects/ADISCORD_economy_effects.txt": EFFECTS.replace(
                migration, ""
            ),
        }
        patterns = (
            "common/scripted_effects/*.txt",
            "common/scripted_triggers/*.txt",
            "common/modifier_definitions/*.txt",
            "common/synchronized_dynamic_tokens/*.txt",
            "common/ideas/*.txt",
            "common/scripted_guis/*.txt",
            "common/scripted_localisation/*.txt",
            "interface/*.gui",
            "events/*.txt",
            "localisation/**/*.yml",
            "docs/economy/*.md",
            "tools/validators/*.py",
        )
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                relative = path.relative_to(ROOT).as_posix()
                if relative == "common/scripted_effects/ADISCORD_economy_effects.txt":
                    continue
                scanned[relative] = path.read_text(encoding="utf-8-sig")

        forbidden = re.compile(
            r"debt_capacity|debt\s+capacity|долгов\w*\s+[её]мк",
            re.IGNORECASE,
        )
        offenders = {
            path: sorted({match.group(0) for match in forbidden.finditer(text)})
            for path, text in scanned.items()
            if forbidden.search(text)
        }
        self.assertFalse(offenders, f"retired debt-capacity boundary: {offenders}")

    def test_task45_debt_metrics_use_exact_interest_pressure_flow(self):
        self.assertFalse(debt_metric_flow_issues(EFFECTS))
        self.assertFalse(task6_debt_state_authority_issues(EFFECTS, ECONOMY_LOC))
        risk_clamp = (
            "clamp_variable = { var = ADISCORD_economy_debt_crisis_level min = 0 max = 4 }"
        )
        self.assertEqual(EFFECTS.count(risk_clamp), 1)
        self.assertNotIn(
            "clamp_variable = { var = ADISCORD_economy_debt_crisis_level min = 0 max = 5 }",
            EFFECTS,
        )
        macro = unique_block(EFFECTS, "ADISCORD_economy_calculate_macro_indicators")
        self.assertEqual(
            macro.count("ADISCORD_economy_calculate_debt_metrics = yes"),
            1,
        )
        for retired in (
            "ADISCORD_economy_calculate_debt_capacity",
            "ADISCORD_economy_calculate_debt_pressure",
            "ADISCORD_economy_debt_ratio",
        ):
            self.assertNotIn(retired, macro)

        metrics = unique_block(EFFECTS, "ADISCORD_economy_calculate_debt_metrics")
        self.assertNotRegex(
            metrics,
            r"(?:set|add_to|subtract_from|multiply|divide|clamp)_variable\s*=\s*\{\s*"
            r"var\s*=\s*ADISCORD_economy_debt\b",
        )

    def test_task45_automatic_borrowing_refreshes_metrics_without_a_hidden_cap(self):
        self.assertFalse(automatic_borrow_flow_issues(EFFECTS))
        for settlement_name in (
            "ADISCORD_economy_apply_weekly_balance",
            "ADISCORD_economy_apply_monthly_balance",
        ):
            settlement = unique_block(EFFECTS, settlement_name)
            self.assertNotIn("debt_capacity", settlement, settlement_name)
            self.assertNotIn("auto_borrow_over_cap", settlement, settlement_name)
            self.assertNotIn(
                "ADISCORD_economy_refresh_spending_ideas = yes",
                settlement,
                settlement_name,
            )
            self.assertEqual(
                settlement.count("ADISCORD_economy_calculate_debt_metrics = yes"),
                1,
                settlement_name,
            )

    def test_task45_repayment_refreshes_metrics_without_advancing_settlement_state(self):
        for effect_name in (
            "ADISCORD_economy_repay_debt",
            "ADISCORD_economy_early_repay_debt",
            "ADISCORD_economy_restructure_debt",
        ):
            repayment = unique_block(EFFECTS, effect_name)
            self.assertEqual(
                repayment.count("ADISCORD_economy_calculate_debt_metrics = yes"),
                1,
                effect_name,
            )
            debt_change = repayment.index(
                "subtract_from_variable = { var = ADISCORD_economy_debt"
            )
            metric_refresh = repayment.index(
                "ADISCORD_economy_calculate_debt_metrics = yes"
            )
            self.assertLess(debt_change, metric_refresh, effect_name)
            for forbidden in (
                "ADISCORD_economy_update_debt_state_after_settlement",
                "ADISCORD_economy_debt_emergency_streak",
                "ADISCORD_economy_debt_default_streak",
            ):
                self.assertNotIn(forbidden, repayment, effect_name)

        targeted = unique_block(EFFECTS, "ADISCORD_economy_refresh_after_debt_action")
        for required in (
            "ADISCORD_economy_calculate_expenses = yes",
            "ADISCORD_economy_calculate_monthly_balance = yes",
            "ADISCORD_economy_calculate_weekly_budget = yes",
            "ADISCORD_economy_refresh_policy_previews = yes",
        ):
            self.assertIn(required, targeted)
        for forbidden in (
            "ADISCORD_economy_calculate_debt_metrics",
            "ADISCORD_economy_calculate_macro_indicators",
            "ADISCORD_economy_light_update",
            "ADISCORD_economy_full_refresh",
            "ADISCORD_economy_refresh_spending_ideas",
        ):
            self.assertNotIn(forbidden, targeted)

        gui_actions = {
            "ADISCORD_economy_gui_try_issue_internal_bonds": "ADISCORD_economy_issue_internal_bonds = yes",
            "ADISCORD_economy_gui_try_take_external_loan": "ADISCORD_economy_take_external_loan = yes",
            "ADISCORD_economy_gui_try_repay_debt": "ADISCORD_economy_repay_debt = yes",
            "ADISCORD_economy_gui_try_restructure_debt": "ADISCORD_economy_restructure_debt = yes",
        }
        for gui_name, action_call in gui_actions.items():
            gui = unique_block(EFFECTS, gui_name)
            targeted_call = "ADISCORD_economy_refresh_after_debt_action = yes"
            self.assertIn(targeted_call, gui, gui_name)
            self.assertNotIn("ADISCORD_economy_light_update = yes", gui, gui_name)
            self.assertLess(gui.index(action_call), gui.index(targeted_call), gui_name)

    def test_task45_manual_borrowing_reasons_match_visible_ordered_gates(self):
        self.assertFalse(
            manual_borrowing_availability_issues(TRIGGERS, SCRIPTED_LOC)
        )
        for tooltip_key in (
            "ADISCORD_economy_action_internal_bonds_tt",
            "ADISCORD_economy_action_external_loan_tt",
        ):
            tooltip = localisation_value(ECONOMY_LOC, tooltip_key)
            for visible_metric in (
                "?ADISCORD_economy_interest_rate|1",
                "?ADISCORD_economy_weekly_interest|2",
                "?ADISCORD_economy_interest_share_income|1",
                "?ADISCORD_economy_debt_pressure|0",
            ):
                self.assertIn(visible_metric, tooltip, tooltip_key)
        internal_risk_reason = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_loan_blocked_default"
        )
        self.assertIn("четвёрт", internal_risk_reason.casefold())
        self.assertNotIn("фактическом дефолте", internal_risk_reason.casefold())
        for tier_name in ("warning", "burden", "crisis", "default"):
            tier_effect = localisation_value(
                ECONOMY_LOC, f"ADISCORD_economy_debt_effect_{tier_name}"
            )
            self.assertIn("ступень", tier_effect.casefold(), tier_name)
            for retired_threshold in ("40–69%", "70–99%", "100–139%", "140%"):
                self.assertNotIn(retired_threshold, tier_effect, tier_name)
        no_tier_effect = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_debt_effect_none"
        )
        self.assertIn("нулевая ступень", no_tier_effect.casefold())
        self.assertNotIn("40%", no_tier_effect)
        self.assertIn(
            "?ADISCORD_economy_debt_state|0",
            localisation_value(ECONOMY_LOC, "ADISCORD_economy_debt_tt"),
        )
        self.assertIn(
            "?ADISCORD_economy_debt_state|0]/4",
            localisation_value(ECONOMY_LOC, "ADISCORD_economy_debt_tt"),
        )
        mutations = {
            "reversed interest comparison": TRIGGERS.replace(
                "var = ADISCORD_economy_interest_share_income value = 25 compare = less_than",
                "var = ADISCORD_economy_interest_share_income value = 25 compare = greater_than",
                1,
            ),
            "dead pressure gate": TRIGGERS.replace(
                "check_variable = { var = ADISCORD_economy_debt_pressure value = 75 compare = less_than }",
                "AND = { check_variable = { var = ADISCORD_economy_debt_pressure value = 75 compare = less_than } always = no }",
                1,
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutation, TRIGGERS)
                self.assertTrue(
                    manual_borrowing_availability_issues(mutation, SCRIPTED_LOC)
                )

        first = (
            "\ttext = { trigger = { check_variable = { var = ADISCORD_economy_recent_debt "
            "value = 1 compare = greater_than_or_equals } } localization_key = "
            "ADISCORD_economy_loan_blocked_cooldown }"
        )
        second = (
            "\ttext = { trigger = { NOT = { ADISCORD_economy_has_treasury_room_50 = yes } } "
            "localization_key = ADISCORD_economy_loan_blocked_treasury_room }"
        )
        reordered = SCRIPTED_LOC.replace(
            first + "\n" + second,
            second + "\n" + first,
            1,
        )
        self.assertNotEqual(reordered, SCRIPTED_LOC)
        self.assertTrue(manual_borrowing_availability_issues(TRIGGERS, reordered))

    def test_treasury_operations_debt_hint_names_its_pressure_trigger(self):
        selector = unique_defined_text(
            SCRIPTED_LOC, "GetADISCORDTreasuryOperationsHintLoc"
        )
        self.assertRegex(
            selector,
            r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_pressure"
            r"\s+value\s*=\s*50\s+compare\s*=\s*greater_than_or_equals\s*\}"
            r"\s*\}\s*localization_key\s*=\s*ADISCORD_economy_operations_hint_debt",
        )
        hint = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_operations_hint_debt"
        ).casefold()
        self.assertIn("давление долга", hint)
        self.assertIn("50", hint)
        self.assertNotIn("долг выше 70%", hint)

    def test_automatic_borrowing_covers_full_uncovered_deficit_without_capacity_gate(self):
        self.assertFalse(automatic_borrow_flow_issues(EFFECTS))
        for settlement_name in (
            "ADISCORD_economy_apply_weekly_balance",
            "ADISCORD_economy_apply_monthly_balance",
        ):
            settlement = unique_block(EFFECTS, settlement_name)
            self.assertNotIn("debt_capacity", settlement, settlement_name)
            self.assertNotIn("auto_borrow_over_cap", settlement, settlement_name)
            self.assertRegex(
                settlement,
                r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_auto_borrow_temp"
                r"\s+value\s*=\s*ADISCORD_economy_uncovered_deficit_temp\s*\}",
                settlement_name,
            )
            for account in ("debt", "treasury"):
                self.assertRegex(
                    settlement,
                    rf"add_to_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_{account}"
                    r"\s+value\s*=\s*ADISCORD_economy_auto_borrow_temp\s*\}",
                    settlement_name,
                )
            self.assertNotIn(
                "ADISCORD_economy_refresh_spending_ideas = yes",
                settlement,
                settlement_name,
            )
            self.assertIn("ADISCORD_economy_calculate_debt_metrics = yes", settlement)
            self.assertIn(
                "ADISCORD_economy_update_debt_state_after_settlement = yes",
                settlement,
            )

    def test_debt_tiers_use_interest_share_and_four_thirteen_settlement_streaks(self):
        self.assertFalse(task6_debt_state_sequence_issues(EFFECTS))
        self.assertFalse(task6_debt_state_authority_issues(EFFECTS, ECONOMY_LOC))
        metrics = unique_block(EFFECTS, "ADISCORD_economy_calculate_debt_metrics")
        for variable in (
            "ADISCORD_economy_weekly_interest",
            "ADISCORD_economy_interest_share_income",
            "ADISCORD_economy_debt_income_ratio",
            "ADISCORD_economy_debt_pressure",
        ):
            self.assertIn(variable, metrics)
        weekly_interest = metrics.index("ADISCORD_economy_weekly_interest")
        interest_share = metrics.index("ADISCORD_economy_interest_share_income")
        debt_ratio = metrics.index("ADISCORD_economy_debt_income_ratio")
        pressure = metrics.index("ADISCORD_economy_debt_pressure")
        self.assertLess(debt_ratio, interest_share)
        self.assertLess(weekly_interest, interest_share)
        self.assertLess(interest_share, pressure)
        for value in ("value = 3", "value = 13", "value = 100"):
            self.assertIn(value, metrics)
        for coefficient in ("value = 0.20", "value = 1.50", "value = 2"):
            self.assertIn(coefficient, metrics)
        self.assertRegex(
            metrics,
            r"clamp_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_pressure"
            r"\s+min\s*=\s*0\s+max\s*=\s*100\s*\}",
        )

        transition = unique_block(
            EFFECTS, "ADISCORD_economy_update_debt_state_after_settlement"
        )
        for threshold in (10, 25, 40):
            self.assertRegex(
                transition,
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_interest_share_income"
                rf"\s+value\s*=\s*{threshold}\s+compare\s*=\s*greater_than_or_equals\s*\}}",
            )
        for streak, required, state in (
            ("emergency_streak", 4, 3),
            ("default_streak", 13, 4),
        ):
            variable = f"ADISCORD_economy_debt_{streak}"
            self.assertRegex(
                transition,
                rf"add_to_variable\s*=\s*\{{\s*var\s*=\s*{variable}\s+value\s*=\s*1\s*\}}",
            )
            self.assertRegex(
                transition,
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*{variable}\s+value\s*=\s*{required}"
                r"\s+compare\s*=\s*greater_than_or_equals\s*\}",
            )
            self.assertRegex(
                transition,
                rf"set_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_debt_state\s+value\s*=\s*{state}\s*\}}",
            )
            self.assertRegex(
                transition,
                rf"set_variable\s*=\s*\{{\s*var\s*=\s*{variable}\s+value\s*=\s*0\s*\}}",
            )
        self.assertIn("ADISCORD_economy_weekly_balance", transition)

        exact_debuffs = {
            "ADISCORD_economy_debt_strain": {"political_power_gain": -0.02},
            "ADISCORD_economy_debt_crisis": {
                "political_power_gain": -0.05,
                "research_speed_factor": -0.01,
            },
            "ADISCORD_economy_debt_emergency": {
                "political_power_gain": -0.10,
                "research_speed_factor": -0.03,
                "production_speed_buildings_factor": -0.04,
                "stability_factor": -0.03,
            },
            "ADISCORD_economy_debt_default": {
                "political_power_gain": -0.18,
                "research_speed_factor": -0.07,
                "production_speed_buildings_factor": -0.08,
                "industrial_capacity_factory": -0.05,
                "stability_factor": -0.08,
            },
        }
        for idea_name, expected in exact_debuffs.items():
            idea = unique_block(ECONOMY_IDEAS, idea_name)
            for modifier, value in expected.items():
                self.assertEqual(numeric_values(idea, modifier), [value], idea_name)

        compatibility = unique_block(
            EFFECTS, "ADISCORD_economy_update_debt_crisis_level"
        )
        self.assertEqual(
            re.findall(
                r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_crisis_level"
                r"\s+value\s*=\s*([^\s}]+)\s*\}",
                compatibility,
            ),
            ["ADISCORD_economy_debt_state"],
        )
        self.assertNotRegex(compatibility, r"\b(?:add_to|clamp|subtract_from)_variable\b")
        refresh = unique_block(EFFECTS, "ADISCORD_economy_refresh_spending_ideas")
        self.assertIn("ADISCORD_economy_debt_state", refresh)
        self.assertNotIn("ADISCORD_economy_debt_crisis_level", refresh)

        mirror_line = (
            "set_variable = { var = ADISCORD_economy_debt_crisis_level "
            "value = ADISCORD_economy_debt_state }"
        )
        authority_mutations = {
            "independent legacy tier recomputation": (
                EFFECTS.replace(
                    compatibility,
                    compatibility.replace(
                        mirror_line,
                        mirror_line
                        + "\n\tset_variable = { var = ADISCORD_economy_debt_crisis_level value = 3 }",
                    ),
                    1,
                ),
                ECONOMY_LOC,
            ),
            "extra legacy tier clamp": (
                EFFECTS.replace(
                    mirror_line,
                    mirror_line
                    + "\n\tclamp_variable = { var = ADISCORD_economy_debt_crisis_level min = 0 max = 4 }",
                    1,
                ),
                ECONOMY_LOC,
            ),
            "tooltip reads compatibility tier": (
                EFFECTS,
                ECONOMY_LOC.replace(
                    "?ADISCORD_economy_debt_state|0",
                    "?ADISCORD_economy_debt_crisis_level|0",
                    1,
                ),
            ),
        }
        for name, (mutated_effects, mutated_loc) in authority_mutations.items():
            with self.subTest(authority_mutation=name):
                self.assertTrue(
                    task6_debt_state_authority_issues(mutated_effects, mutated_loc)
                )

    def test_debt_notifications_are_first_loan_and_upward_transitions_only(self):
        self.assertFalse(task6_notification_queue_issues(EFFECTS))
        queue = unique_block(EFFECTS, "ADISCORD_economy_queue_debt_notification")
        transition = unique_block(
            EFFECTS, "ADISCORD_economy_update_debt_state_after_settlement"
        )
        combined = queue + "\n" + transition
        for variable in (
            "ADISCORD_economy_pending_debt_notification_kind",
            "ADISCORD_economy_pending_debt_notification_amount",
            "ADISCORD_economy_pending_debt_notification_previous_state",
            "ADISCORD_economy_pending_debt_notification_new_state",
            "ADISCORD_economy_first_loan_notified",
            "ADISCORD_economy_last_notified_debt_state",
        ):
            self.assertIn(variable, combined)
        kinds = {
            int(value)
            for value in re.findall(
                r"ADISCORD_economy_pending_debt_notification_kind\s+value\s*=\s*([1-5])\b",
                combined,
            )
        }
        self.assertEqual(kinds, {1, 2, 3, 4, 5})
        self.assertRegex(
            combined,
            r"ADISCORD_economy_debt_state\s+value\s*=\s*ADISCORD_economy_last_notified_debt_state"
            r"\s+compare\s*=\s*greater_than",
        )
        self.assertIn("is_ai = no", queue)
        self.assertNotIn("ADISCORD_economy_refresh_spending_ideas", queue)
        hidden_improvement_gate = queue.replace(
            "\t\tcheck_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }",
            "\t\tAND = {\n"
            "\t\t\tcheck_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_pending_debt_notification_previous_state compare = less_than }\n"
            "\t\t\thas_country_flag = hidden_notice_gate\n"
            "\t\t}",
            1,
        )
        self.assertNotEqual(hidden_improvement_gate, queue)
        mutated_effects = EFFECTS.replace(queue, hidden_improvement_gate, 1)
        self.assertTrue(parse_clausewitz(mutated_effects))
        self.assertTrue(task6_notification_queue_issues(mutated_effects))
        for forbidden_scan in (
            "every_country",
            "any_country",
            "random_country",
            "every_owned_state",
        ):
            self.assertNotIn(forbidden_scan, combined)

        for settlement_name in (
            "ADISCORD_economy_apply_weekly_balance",
            "ADISCORD_economy_apply_monthly_balance",
        ):
            settlement = unique_block(EFFECTS, settlement_name)
            update = "ADISCORD_economy_update_debt_state_after_settlement = yes"
            dispatch = "ADISCORD_economy_queue_debt_notification = yes"
            self.assertEqual(settlement.count(update), 1, settlement_name)
            self.assertEqual(settlement.count(dispatch), 1, settlement_name)
            self.assertLess(settlement.index(update), settlement.index(dispatch))
            self.assertEqual(
                settlement.count(
                    "set_variable = { var = ADISCORD_economy_pending_debt_notification_amount value = 0 }"
                ),
                1,
                settlement_name,
            )
            self.assertEqual(
                settlement.count(
                    "set_variable = { var = ADISCORD_economy_pending_debt_notification_previous_state value = ADISCORD_economy_debt_state }"
                ),
                1,
                settlement_name,
            )

    def test_repayment_recalculates_interest_and_can_lower_debuff_immediately(self):
        self.assertFalse(debt_reconciler_issues(EFFECTS))
        for effect_name in (
            "ADISCORD_economy_repay_debt",
            "ADISCORD_economy_early_repay_debt",
            "ADISCORD_economy_restructure_debt",
        ):
            repayment = unique_block(EFFECTS, effect_name)
            self.assertEqual(
                repayment.count("ADISCORD_economy_calculate_debt_metrics = yes"),
                1,
                effect_name,
            )
            self.assertEqual(
                repayment.count(
                    "ADISCORD_economy_reconcile_debt_state_after_action = yes"
                ),
                1,
                effect_name,
            )
            debt_change = repayment.index(
                "subtract_from_variable = { var = ADISCORD_economy_debt"
            )
            metric_refresh = repayment.index(
                "ADISCORD_economy_calculate_debt_metrics = yes"
            )
            reconciliation = repayment.index(
                "ADISCORD_economy_reconcile_debt_state_after_action = yes"
            )
            self.assertLess(debt_change, metric_refresh, effect_name)
            self.assertLess(metric_refresh, reconciliation, effect_name)
            self.assertNotIn(
                "ADISCORD_economy_update_debt_state_after_settlement",
                repayment,
                effect_name,
            )
        reconciler = unique_block(
            EFFECTS, "ADISCORD_economy_reconcile_debt_state_after_action"
        )
        self.assertIn("ADISCORD_economy_debt_state", reconciler)
        self.assertIn("ADISCORD_economy_last_notified_debt_state", reconciler)
        self.assertNotRegex(reconciler, r"add_to_variable[^{]*\{[^{}]*_streak")
        self.assertNotRegex(
            reconciler,
            r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt_state"
            r"\s+value\s*=\s*[34]\b",
        )
        for forbidden in (
            "ADISCORD_economy_update_debt_state_after_settlement",
            "ADISCORD_economy_queue_debt_notification",
            "ADISCORD_economy_debt_emergency_streak",
            "ADISCORD_economy_debt_default_streak",
            "country_event",
            "news_event",
        ):
            self.assertNotIn(forbidden, reconciler)

    def test_debt_debuff_ideas_use_canonical_state_ids(self):
        expected = {
            "ADISCORD_economy_debt_strain": {
                "political_power_gain": -0.02,
            },
            "ADISCORD_economy_debt_crisis": {
                "political_power_gain": -0.05,
                "research_speed_factor": -0.01,
            },
            "ADISCORD_economy_debt_emergency": {
                "political_power_gain": -0.10,
                "research_speed_factor": -0.03,
                "production_speed_buildings_factor": -0.04,
                "stability_factor": -0.03,
            },
            "ADISCORD_economy_debt_default": {
                "political_power_gain": -0.18,
                "research_speed_factor": -0.07,
                "production_speed_buildings_factor": -0.08,
                "industrial_capacity_factory": -0.05,
                "stability_factor": -0.08,
            },
        }
        for idea_name, modifiers in expected.items():
            idea = unique_block(ECONOMY_IDEAS, idea_name)
            localisation_value(ECONOMY_LOC, idea_name)
            for modifier, value in modifiers.items():
                self.assertEqual(numeric_values(idea, modifier), [value], idea_name)
        for retired_id in (
            "ADISCORD_economy_debt_warning",
            "ADISCORD_economy_debt_burden",
        ):
            self.assertEqual(assignment_blocks(ECONOMY_IDEAS, retired_id), [])
            self.assertNotIn(retired_id, localisation_key_set(ECONOMY_LOC))

        sync = unique_block(EFFECTS, "ADISCORD_economy_sync_debt_state_idea")
        for state, idea_name in enumerate(
            (
                None,
                "ADISCORD_economy_debt_strain",
                "ADISCORD_economy_debt_crisis",
                "ADISCORD_economy_debt_emergency",
                "ADISCORD_economy_debt_default",
            )
        ):
            if idea_name is None:
                continue
            self.assertEqual(sync.count(f"add_ideas = {idea_name}"), 1, idea_name)
            self.assertRegex(
                sync,
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_debt_state"
                rf"\s+value\s*=\s*{state}\s+compare\s*=\s*equals\s*\}}"
                rf"[^\n]*add_ideas\s*=\s*{idea_name}",
                idea_name,
            )
        self.assertEqual(sync.count("add_ideas = ADISCORD_economy_debt_"), 4)
        self.assertRegex(sync, r"(?m)^\s*if\s*=.*debt_state value = 4")
        self.assertEqual(len(re.findall(r"(?m)^\s*else_if\s*=", sync)), 3)

    def test_weekly_path_has_no_idea_query_building_recount_or_country_iteration(self):
        sources = (EFFECTS, MODIFIER_EFFECTS, TRIGGERS)
        self.assertFalse(weekly_reachability_issues(sources))
        self.assertFalse(
            task7_weekly_on_action_issues(
                ON_ACTIONS, EFFECTS, MODIFIER_EFFECTS, TRIGGERS
            )
        )
        on_weekly = block(block(ON_ACTIONS, "on_actions"), "on_weekly")
        self.assertEqual(on_weekly.count("ADISCORD_economy_weekly_update = yes"), 1)
        self.assertEqual(
            on_weekly.count("ADISCORD_economy_should_weekly_update = yes"), 1
        )
        self.assertFalse(
            weekly_reachability_issues(
                sources, ("ADISCORD_economy_weekly_update",)
            )
        )

        settlement_anchor = "\tADISCORD_economy_clamp_treasury = yes"
        self.assertIn(settlement_anchor, EFFECTS)
        mutations = {
            "automatic borrowing rebuilds spending ideas": EFFECTS.replace(
                settlement_anchor,
                settlement_anchor + "\n\tADISCORD_economy_refresh_spending_ideas = yes",
                1,
            ),
            "automatic borrowing reaches a parameterized full refresh": EFFECTS.replace(
                settlement_anchor,
                settlement_anchor + "\n\tADISCORD_economy_full_refresh = { FORCE = yes }",
                1,
            ),
            "automatic borrowing performs a direct idea query": EFFECTS.replace(
                settlement_anchor,
                settlement_anchor + "\n\tif = { limit = { has_idea = forbidden } always = yes }",
                1,
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name):
                self.assertTrue(
                    weekly_reachability_issues((mutation, MODIFIER_EFFECTS, TRIGGERS)),
                    name,
                )

        weekly_call = "\t\t\t\tADISCORD_economy_weekly_update = yes"
        self.assertIn(weekly_call, ON_ACTIONS)
        on_action_mutations = {
            "weekly hook calls GUI beside the accounting facade": (
                ON_ACTIONS.replace(
                    weekly_call,
                    weekly_call + "\n\t\t\t\tADISCORD_economy_update_gui = yes",
                    1,
                ),
                EFFECTS,
            ),
            "weekly hook reaches GUI through a parameter wrapper": (
                ON_ACTIONS.replace(
                    weekly_call,
                    weekly_call
                    + "\n\t\t\t\tADISCORD_task7_weekly_wrapper = { SOURCE = weekly }",
                    1,
                ),
                EFFECTS
                + "\nADISCORD_task7_weekly_wrapper = {\n"
                + "\tADISCORD_economy_update_gui = yes\n}\n",
            ),
            "weekly hook calls an external ADISCORD wrapper": (
                ON_ACTIONS.replace(
                    weekly_call,
                    weekly_call
                    + "\n\t\t\t\tADISCORD_tick_all_society_development_monthly = yes",
                    1,
                ),
                EFFECTS,
            ),
            "weekly hook calls an undefined ADISCORD wrapper": (
                ON_ACTIONS.replace(
                    weekly_call,
                    weekly_call
                    + "\n\t\t\t\tADISCORD_task7_unknown_external_wrapper = yes",
                    1,
                ),
                EFFECTS,
            ),
        }
        for name, (mutated_on_actions, mutated_effects) in on_action_mutations.items():
            with self.subTest(on_action_mutation=name):
                self.assertTrue(parse_clausewitz(mutated_on_actions))
                self.assertTrue(parse_clausewitz(mutated_effects))
                self.assertTrue(
                    task7_weekly_on_action_issues(
                        mutated_on_actions,
                        mutated_effects,
                        MODIFIER_EFFECTS,
                        TRIGGERS,
                    ),
                    name,
                )

        decoy_on_actions = ON_ACTIONS.replace(
            weekly_call,
            '# ADISCORD_tick_all_society_development_monthly = yes\n'
            + weekly_call
            + '\n\t\t\t\tlog = "ADISCORD_task7_unknown_external_wrapper = yes"',
            1,
        )
        self.assertFalse(
            task7_weekly_on_action_issues(
                decoy_on_actions, EFFECTS, MODIFIER_EFFECTS, TRIGGERS
            )
        )

    def test_weekly_ready_gate_prevents_uninitialized_or_unmigrated_settlement(self):
        prepare = unique_block(EFFECTS, "ADISCORD_economy_prepare_weekly_country")
        weekly = unique_block(EFFECTS, "ADISCORD_economy_weekly_update")
        should_weekly = unique_block(TRIGGERS, "ADISCORD_economy_should_weekly_update")
        for body in (prepare, should_weekly):
            self.assertIn("has_variable = ADISCORD_economy_initialized", body)
            self.assertIn("has_variable = ADISCORD_economy_weekly_source_cache_ready", body)
            self.assertRegex(
                body,
                r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_schema_version"
                r"\s+value\s*=\s*15\s+compare\s*=\s*greater_than_or_equals\s*\}",
            )
        self.assertEqual(
            prepare.count(
                "set_variable = { var = ADISCORD_economy_weekly_ready value = 0 }"
            ),
            1,
        )
        self.assertEqual(
            prepare.count(
                "set_variable = { var = ADISCORD_economy_weekly_ready value = 1 }"
            ),
            1,
        )
        self.assertNotIn("ADISCORD_economy_initialize_country", prepare)
        self.assertNotIn("ADISCORD_economy_migrate_schema", prepare)
        self.assertRegex(
            weekly,
            r"(?s)^\s*ADISCORD_economy_prepare_weekly_country\s*=\s*yes\s*"
            r"if\s*=\s*\{\s*limit\s*=\s*\{\s*check_variable\s*=\s*\{\s*"
            r"var\s*=\s*ADISCORD_economy_weekly_ready\s+value\s*=\s*1\s+"
            r"compare\s*=\s*greater_than_or_equals\s*\}\s*\}\s*"
            r"ADISCORD_economy_light_update\s*=\s*yes\s*"
            r"ADISCORD_economy_apply_weekly_balance\s*=\s*yes",
        )

    def test_schema_fifteen_bootstraps_task_seven_caches_after_task_six(self):
        self.assertFalse(task6_schema_fourteen_migration_issues(EFFECTS))
        self.assertFalse(task7_schema_fifteen_cache_migration_issues(EFFECTS))

        migration = unique_block(EFFECTS, "ADISCORD_economy_migrate_schema")
        invalidate = (
            "\t\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 0 }\n"
            "\t\tset_variable = { var = ADISCORD_economy_weekly_ready value = 0 }\n"
            "\t\tset_variable = { var = ADISCORD_economy_needs_full_refresh value = 1 }"
        )
        refresh = "\t\tADISCORD_economy_full_refresh_if_needed = yes"
        completion = (
            "\t\tset_variable = { var = ADISCORD_economy_schema_version value = 15 }"
        )
        for anchor in (invalidate, refresh, completion):
            self.assertIn(anchor, migration)

        migration_mutations = {
            "schema 14 cache readiness is not invalidated": migration.replace(
                invalidate.splitlines()[0] + "\n", "", 1
            ),
            "schema 14 cache rebuild is skipped": migration.replace(
                refresh + "\n", "", 1
            ),
            "schema completion watermark is missing": migration.replace(
                completion + "\n", "", 1
            ),
            "schema completes before the cache rebuild": migration.replace(
                refresh + "\n" + completion,
                completion + "\n" + refresh,
                1,
            ),
        }
        for name, mutated_migration in migration_mutations.items():
            with self.subTest(schema15_mutation=name):
                self.assertNotEqual(mutated_migration, migration)
                mutated_effects = EFFECTS.replace(migration, mutated_migration, 1)
                self.assertTrue(parse_clausewitz(mutated_effects))
                self.assertTrue(
                    task7_schema_fifteen_cache_migration_issues(mutated_effects),
                    name,
                )

    def test_weekly_query_caches_have_bounded_refresh_and_invalidation_owners(self):
        self.assertFalse(
            task7_cache_invalidation_issues(EFFECTS, MODIFIER_EFFECTS)
        )
        factory_cache = unique_block(
            EFFECTS, "ADISCORD_economy_cache_weekly_factory_sources"
        )
        factory_sources = {
            "ADISCORD_economy_cached_civilian_factories": "num_of_civilian_factories",
            "ADISCORD_economy_cached_available_civilian_factories": "num_of_available_civilian_factories",
            "ADISCORD_economy_cached_military_factories": "num_of_military_factories",
            "ADISCORD_economy_cached_available_military_factories": "num_of_available_military_factories",
            "ADISCORD_economy_cached_naval_factories": "num_of_naval_factories",
        }
        for variable, source in factory_sources.items():
            self.assertEqual(factory_cache.count(source), 1, source)
            self.assertRegex(
                factory_cache,
                rf"set_variable\s*=\s*\{{\s*var\s*=\s*{variable}\s+value\s*=\s*{source}\s*\}}",
            )

        policy_cache = unique_block(
            MODIFIER_EFFECTS, "ADISCORD_economy_cache_weekly_policy_sources"
        )
        policy_suffixes = (
            "taxation_light_dues",
            "taxation_balanced_register",
            "taxation_progressive_brackets",
            "taxation_industrial_tariffs",
            "taxation_extraction_quotas",
            "industrial_artisan_markets",
            "industrial_balanced_workshops",
            "industrial_civilian_expansion",
            "industrial_military_prioritization",
            "industrial_state_planning",
            "labor_loose_contracts",
            "labor_technocratic_work_norms",
            "labor_mobilized_labor",
            "welfare_basic_services",
            "welfare_social_insurance",
            "welfare_universal_provision",
            "welfare_rationed_support",
            "education_technical_institutes",
            "education_elite_academies",
        )
        for suffix in policy_suffixes:
            source_trigger = f"ADISCORD_economy_has_{suffix}"
            cached_variable = f"ADISCORD_economy_cached_{suffix}_active"
            cached_trigger = f"ADISCORD_economy_cached_has_{suffix}"
            self.assertEqual(policy_cache.count(f"{source_trigger} = yes"), 1, suffix)
            self.assertIn(cached_variable, policy_cache)
            cached_body = unique_block(TRIGGERS, cached_trigger)
            self.assertIn(cached_variable, cached_body)
            self.assertNotIn("has_idea", cached_body)

        recalculate = unique_block(
            MODIFIER_EFFECTS, "ADISCORD_economy_recalculate_policy_modifiers"
        )
        self.assertEqual(
            recalculate.count("ADISCORD_economy_cache_weekly_policy_sources = yes"),
            1,
        )
        full_refresh = unique_block(EFFECTS, "ADISCORD_economy_full_refresh")
        ordered = (
            "ADISCORD_economy_recount_economic_buildings = yes",
            "ADISCORD_economy_cache_weekly_factory_sources = yes",
            "ADISCORD_economy_recalculate_policy_modifiers = yes",
            "set_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }",
            "ADISCORD_economy_clear_dirty = yes",
        )
        positions = [full_refresh.find(token) for token in ordered]
        self.assertTrue(all(position >= 0 for position in positions), positions)
        self.assertEqual(positions, sorted(positions))

        all_sources = (EFFECTS, MODIFIER_EFFECTS, TRIGGERS)
        for owner in (
            "ADISCORD_economy_initialize_country",
            "ADISCORD_economy_migrate_schema",
            "ADISCORD_economy_monthly_update",
            "ADISCORD_economy_yearly_update",
            "ADISCORD_economy_open_window",
        ):
            reachable = reachable_script_entries(all_sources, (owner,))
            self.assertIn("ADISCORD_economy_cache_weekly_factory_sources", reachable, owner)
            self.assertIn("ADISCORD_economy_cache_weekly_policy_sources", reachable, owner)
        migration = unique_block(EFFECTS, "ADISCORD_economy_migrate_schema")
        self.assertIn("ADISCORD_economy_full_refresh_if_needed = yes", migration)
        dirty = unique_block(EFFECTS, "ADISCORD_economy_mark_dirty")
        self.assertIn(
            "set_variable = { var = ADISCORD_economy_needs_full_refresh value = 1 }",
            dirty,
        )
        defaults = unique_block(EFFECTS, "ADISCORD_economy_set_default_values")
        self.assertIn(
            "set_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 0 }",
            defaults,
        )

        dirty_source = unique_block(EFFECTS, "ADISCORD_economy_mark_dirty")
        full_source = unique_block(EFFECTS, "ADISCORD_economy_full_refresh")
        targeted_anchor = "\tADISCORD_economy_finish_targeted_policy_refresh = yes"
        self.assertIn(targeted_anchor, EFFECTS)
        army_idea_source = unique_block(
            EFFECTS, "ADISCORD_economy_refresh_army_policy_idea"
        )
        army_idea_anchor = (
            "\tset_variable = { var = ADISCORD_economy_last_idea_signature value = -1 }"
        )
        self.assertIn(army_idea_anchor, army_idea_source)
        army_policy_source = unique_block(
            EFFECTS, "ADISCORD_economy_refresh_army_policy"
        )
        army_policy_idea_call = "\tADISCORD_economy_refresh_army_policy_idea = yes"
        self.assertIn(army_policy_idea_call, army_policy_source)

        def mutate_army_idea_readiness(write):
            return EFFECTS.replace(
                army_idea_source,
                army_idea_source.replace(
                    army_idea_anchor,
                    f"\t{write}\n" + army_idea_anchor,
                    1,
                ),
                1,
            )

        mutations = {
            "dirty cache remains eligible": (
                EFFECTS.replace(
                    dirty_source,
                    dirty_source.replace(
                        "ADISCORD_economy_weekly_source_cache_ready value = 0",
                        "ADISCORD_economy_weekly_source_cache_ready value = 1",
                        1,
                    ),
                    1,
                ),
                MODIFIER_EFFECTS,
            ),
            "dirty request precedes invalidation": (
                EFFECTS.replace(
                    dirty_source,
                    dirty_source.replace(
                        "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 0 }\n"
                        "\tset_variable = { var = ADISCORD_economy_weekly_ready value = 0 }\n"
                        "\tset_variable = { var = ADISCORD_economy_needs_full_refresh value = 1 }",
                        "\tset_variable = { var = ADISCORD_economy_needs_full_refresh value = 1 }\n"
                        "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 0 }\n"
                        "\tset_variable = { var = ADISCORD_economy_weekly_ready value = 0 }",
                        1,
                    ),
                    1,
                ),
                MODIFIER_EFFECTS,
            ),
            "full refresh omits readiness watermark": (
                EFFECTS.replace(
                    full_source,
                    full_source.replace(
                        "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }\n",
                        "",
                        1,
                    ),
                    1,
                ),
                MODIFIER_EFFECTS,
            ),
            "full refresh exposes readiness before factor sources": (
                EFFECTS.replace(
                    full_source,
                    full_source.replace(
                        "\tADISCORD_economy_recalculate_policy_modifiers = yes\n"
                        "\tADISCORD_economy_recalculate_treasury_cap = yes\n"
                        "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }",
                        "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }\n"
                        "\tADISCORD_economy_recalculate_policy_modifiers = yes\n"
                        "\tADISCORD_economy_recalculate_treasury_cap = yes",
                        1,
                    ),
                    1,
                ),
                MODIFIER_EFFECTS,
            ),
            "final factor rebuild is skipped": (
                EFFECTS,
                MODIFIER_EFFECTS.replace(
                    "\tADISCORD_economy_calculate_final_modifier_factors = yes\n",
                    "",
                    1,
                ),
            ),
            "targeted policy refresh falsely restores global readiness": (
                EFFECTS.replace(
                    targeted_anchor,
                    "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }\n"
                    + targeted_anchor,
                    1,
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted descendant falsely restores global readiness": (
                mutate_army_idea_readiness(
                    "set_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }"
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted descendant adds to source readiness": (
                mutate_army_idea_readiness(
                    "add_to_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }"
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted descendant subtracts a negative from source readiness": (
                mutate_army_idea_readiness(
                    "subtract_from_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = -1 }"
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted descendant multiplies source readiness": (
                mutate_army_idea_readiness(
                    "multiply_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = -1 }"
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted descendant divides source readiness": (
                mutate_army_idea_readiness(
                    "divide_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = -1 }"
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted descendant clamps source readiness to one": (
                mutate_army_idea_readiness(
                    "clamp_variable = { var = ADISCORD_economy_weekly_source_cache_ready min = 1 max = 1 }"
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted descendant clears weekly readiness": (
                mutate_army_idea_readiness(
                    "clear_variable = ADISCORD_economy_weekly_ready"
                ),
                MODIFIER_EFFECTS,
            ),
            "targeted scalar wrapper falsely restores global readiness": (
                EFFECTS.replace(
                    army_policy_source,
                    army_policy_source.replace(
                        army_policy_idea_call,
                        "\tADISCORD_task7_bad_ready_wrapper = yes",
                        1,
                    ),
                    1,
                )
                + "\nADISCORD_task7_bad_ready_wrapper = {\n"
                + "\tADISCORD_economy_refresh_army_policy_idea = yes\n"
                + "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }\n}\n",
                MODIFIER_EFFECTS,
            ),
            "targeted parameter wrapper falsely restores global readiness": (
                EFFECTS.replace(
                    army_policy_source,
                    army_policy_source.replace(
                        army_policy_idea_call,
                        "\tADISCORD_task7_bad_ready_wrapper = { SOURCE = army }",
                        1,
                    ),
                    1,
                )
                + "\nADISCORD_task7_bad_ready_wrapper = {\n"
                + "\tADISCORD_economy_refresh_army_policy_idea = yes\n"
                + "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }\n}\n",
                MODIFIER_EFFECTS,
            ),
            "targeted cycle hides a false global readiness restore": (
                EFFECTS.replace(
                    army_policy_source,
                    army_policy_source.replace(
                        army_policy_idea_call,
                        "\tADISCORD_task7_bad_ready_wrapper_a = yes",
                        1,
                    ),
                    1,
                )
                + "\nADISCORD_task7_bad_ready_wrapper_a = {\n"
                + "\tADISCORD_task7_bad_ready_wrapper_b = { SOURCE = army }\n}\n"
                + "ADISCORD_task7_bad_ready_wrapper_b = {\n"
                + "\tADISCORD_task7_bad_ready_wrapper_a = yes\n"
                + "\tset_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }\n}\n",
                MODIFIER_EFFECTS,
            ),
        }
        for name, (mutated_effects, mutated_modifiers) in mutations.items():
            with self.subTest(cache_mutation=name):
                self.assertTrue(parse_clausewitz(mutated_effects))
                self.assertTrue(parse_clausewitz(mutated_modifiers))
                self.assertTrue(
                    task7_cache_invalidation_issues(
                        mutated_effects, mutated_modifiers
                    ),
                    name,
                )

        decoy_effects = EFFECTS.replace(
            army_policy_idea_call,
            '# add_to_variable = { var = ADISCORD_economy_weekly_source_cache_ready value = 1 }\n'
            + army_policy_idea_call
            + '\n\tlog = "clear_variable = ADISCORD_economy_weekly_ready"'
            + "\n\tif = { limit = { has_variable = ADISCORD_economy_weekly_ready "
            + "check_variable = { var = ADISCORD_economy_weekly_source_cache_ready "
            + "value = 1 compare = equals } } always = yes }",
            1,
        )
        self.assertFalse(
            task7_cache_invalidation_issues(decoy_effects, MODIFIER_EFFECTS)
        )

    def test_weekly_forecast_reprices_live_debt_and_inflation_from_cached_sources(self):
        reachable = reachable_script_entries(
            (EFFECTS, MODIFIER_EFFECTS, TRIGGERS),
            ("ADISCORD_economy_light_update",),
        )
        for definition in (
            "ADISCORD_economy_calculate_income",
            "ADISCORD_economy_calculate_expenses",
            "ADISCORD_economy_calculate_debt_metrics",
            "ADISCORD_economy_calculate_interest_rate",
            "ADISCORD_economy_calculate_monthly_balance",
            "ADISCORD_economy_calculate_weekly_budget",
        ):
            self.assertIn(definition, reachable)
        interest = unique_block(EFFECTS, "ADISCORD_economy_calculate_interest_rate")
        metrics = unique_block(EFFECTS, "ADISCORD_economy_calculate_debt_metrics")

        def live_input_issues(interest_body, metric_body):
            issues = []
            for variable in (
                "ADISCORD_economy_inflation",
                "ADISCORD_economy_fiscal_stress",
            ):
                if not re.search(rf"\b{re.escape(variable)}\b", interest_body):
                    issues.append(f"interest rate lost live {variable}")
            if not re.search(
                r"\bvalue\s*=\s*ADISCORD_economy_debt\b", metric_body
            ):
                issues.append("debt metrics lost live principal")
            return issues

        self.assertEqual(live_input_issues(interest, metrics), [])
        mutations = (
            (interest.replace("ADISCORD_economy_inflation", "ADISCORD_economy_cached_inflation"), metrics),
            (interest.replace("ADISCORD_economy_fiscal_stress", "ADISCORD_economy_cached_fiscal_stress"), metrics),
            (interest, metrics.replace("value = ADISCORD_economy_debt", "value = ADISCORD_economy_cached_debt", 1)),
        )
        for mutation in mutations:
            self.assertTrue(live_input_issues(*mutation))

    def test_ai_policy_uses_one_reserved_ordered_research_action(self):
        self.assertFalse(ai_policy_contract_issues(EFFECTS))

    def test_ai_policy_review_mutations_reject_live_predicate_drift(self):
        policy = unique_block(EFFECTS, "ADISCORD_economy_ai_monthly_policy")
        unsafe_fallback = (
            "OR = { check_variable = { var = ADISCORD_economy_monthly_balance "
            "value = 0 compare = less_than_or_equals } check_variable = { var = "
            "ADISCORD_economy_debt_state value = 0 compare = greater_than } "
            "check_variable = { var = ADISCORD_economy_interest_share_income "
            "value = 10 compare = greater_than_or_equals } }"
        )
        mutations = {
            "wrong crisis state owner": policy.replace(
                "ADISCORD_economy_ai_is_crisis = yes",
                "ADISCORD_economy_ai_is_healthy = yes",
                1,
            ),
            "reversed crisis tax deficit": policy.replace(
                "ADISCORD_economy_monthly_balance value = 0 compare = less_than",
                "ADISCORD_economy_monthly_balance value = 0 compare = greater_than",
                1,
            ),
            "negated crisis state": policy.replace(
                "limit = { ADISCORD_economy_ai_is_crisis = yes }",
                "limit = { NOT = { ADISCORD_economy_ai_is_crisis = yes } }",
                1,
            ),
            "dead reserve owner": policy.replace(
                "limit = { is_ai = yes has_political_power > 50 }",
                "limit = { is_ai = yes has_political_power > 50 always = no }",
                1,
            ),
            "unconditional unsafe fallback": policy.replace(
                unsafe_fallback,
                "always = yes",
                1,
            ),
            "level five retained": policy.replace(
                "ADISCORD_economy_research_spending_mode value = 4 compare = greater_than",
                "ADISCORD_economy_research_spending_mode value = 5 compare = greater_than",
                1,
            ),
            "construction policy alias": policy.replace(
                "ADISCORD_economy_decrease_research_spending = yes",
                "ADISCORD_economy_construction_spending_mode = yes",
                1,
            ),
        }
        for name, mutated_policy in mutations.items():
            with self.subTest(review_policy_mutation=name):
                self.assertNotEqual(mutated_policy, policy)
                mutated_effects = EFFECTS.replace(policy, mutated_policy, 1)
                self.assertNotEqual(mutated_effects, EFFECTS)
                self.assertTrue(ai_policy_contract_issues(mutated_effects), name)

    def test_ai_assistance_review_mutations_reject_live_owner_and_payload_drift(self):
        minor_ideas = (
            ROOT / "common/ideas/ADISCORD_minor_optimization_ideas.txt"
        ).read_text(encoding="utf-8-sig")
        minor_effects = (
            ROOT / "common/scripted_effects/ADISCORD_minor_optimization_effects.txt"
        ).read_text(encoding="utf-8-sig")
        minor_triggers = (
            ROOT / "common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt"
        ).read_text(encoding="utf-8-sig")
        minor_on_actions = (
            ROOT / "common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt"
        ).read_text(encoding="utf-8-sig")
        effects_bundle = minor_effects + "\n" + EFFECTS
        refresh = unique_block(
            effects_bundle, "ADISCORD_economy_refresh_ai_assistance"
        )
        base_idea = unique_block(
            minor_ideas, "ADISCORD_economy_ai_assistance_base"
        )

        signature_mutations = {
            "signature OR changed to AND": refresh.replace(
                "\t\t\tOR = {",
                "\t\t\tAND = {",
                1,
            ),
            "missing-signature arm inverted": refresh.replace(
                "NOT = { has_variable = ADISCORD_economy_ai_assistance_signature }",
                "has_variable = ADISCORD_economy_ai_assistance_signature",
                1,
            ),
        }
        for name, mutated_refresh in signature_mutations.items():
            with self.subTest(review_assistance_mutation=name):
                self.assertNotEqual(mutated_refresh, refresh)
                mutated_effects = effects_bundle.replace(refresh, mutated_refresh, 1)
                self.assertTrue(
                    ai_assistance_contract_issues(
                        minor_ideas, mutated_effects, minor_triggers
                    ),
                    name,
                )

        payload_mutations = {
            "on-add political power": base_idea
            + "\n\t\t\ton_add = { add_political_power = 100 }",
            "equipment attack bonus": base_idea
            + "\n\t\t\tequipment_bonus = { infantry_equipment = { soft_attack = 0.10 } }",
        }
        for name, mutated_idea in payload_mutations.items():
            with self.subTest(review_assistance_mutation=name):
                self.assertNotEqual(mutated_idea, base_idea)
                mutated_ideas = minor_ideas.replace(base_idea, mutated_idea, 1)
                self.assertTrue(
                    ai_assistance_contract_issues(
                        mutated_ideas, effects_bundle, minor_triggers
                    ),
                    name,
                )

        external_owner = effects_bundle + """
ADISCORD_bad_assistance_owner = {
 add_ideas = ADISCORD_economy_ai_assistance_base
 remove_ideas = ADISCORD_economy_ai_assistance_retreat
}
"""
        with self.subTest(review_assistance_mutation="second effect owns stack"):
            self.assertTrue(
                ai_assistance_contract_issues(
                    minor_ideas, external_owner, minor_triggers
                )
            )

        shadow_idea = (
            "\t\tADISCORD_ai_helper_shadow = {\n"
            "\t\t\tallowed = { always = no }\n"
            "\t\t\tallowed_civil_war = { always = yes }\n"
            "\t\t\tremoval_cost = -1\n"
            "\t\t\tmodifier = {\n"
            "\t\t\t\tADISCORD_economy_overall_income_factor = 0.05\n"
            "\t\t\t\tindustrial_capacity_factory = 0.05\n"
            "\t\t\t}\n"
            "\t\t}\n"
        )
        shadow_ideas = minor_ideas.replace("\t}\n}\n", shadow_idea + "\t}\n}\n", 1)
        shadow_refresh = refresh.replace(
            "\t\t\tadd_ideas = ADISCORD_economy_ai_assistance_base",
            "\t\t\tadd_ideas = ADISCORD_economy_ai_assistance_base\n"
            "\t\t\tadd_ideas = ADISCORD_ai_helper_shadow",
            1,
        )
        with self.subTest(review_assistance_mutation="differently named shadow stack"):
            self.assertNotEqual(shadow_ideas, minor_ideas)
            self.assertNotEqual(shadow_refresh, refresh)
            self.assertTrue(
                ai_assistance_contract_issues(
                    shadow_ideas,
                    effects_bundle.replace(refresh, shadow_refresh, 1),
                    minor_triggers,
                )
            )

        guarded_monthly = (
            "\t\t\tif = {\n"
            "\t\t\t\tlimit = { ADISCORD_economy_ai_assistance_needs_monthly_evaluation = yes }\n"
            "\t\t\t\tADISCORD_economy_refresh_ai_assistance = yes\n"
            "\t\t\t}"
        )
        lifecycle_mutations = {
            "monthly refresh escapes owner": minor_on_actions.replace(
                guarded_monthly,
                "\t\t\tif = {\n"
                "\t\t\t\tlimit = { ADISCORD_economy_ai_assistance_needs_monthly_evaluation = yes }\n"
                "\t\t\t\talways = yes\n"
                "\t\t\t}\n"
                "\t\t\tADISCORD_economy_refresh_ai_assistance = yes",
                1,
            ),
            "monthly owner is dead": minor_on_actions.replace(
                "limit = { ADISCORD_economy_ai_assistance_needs_monthly_evaluation = yes }",
                "limit = { ADISCORD_economy_ai_assistance_needs_monthly_evaluation = yes always = no }",
                1,
            ),
        }
        for name, mutation in lifecycle_mutations.items():
            with self.subTest(review_lifecycle_mutation=name):
                self.assertNotEqual(mutation, minor_on_actions)
                self.assertTrue(
                    ai_assistance_lifecycle_issues(
                        EFFECTS, minor_effects, mutation
                    ),
                    name,
                )

    def test_ai_assistance_entrypoints_inventory_every_scripted_effect_source(self):
        expected_issue = "an effect outside the assistance refresh owns an assistance idea"

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            for relative in ("common", "interface", "localisation", "events"):
                shutil.copytree(ROOT / relative, temporary_root / relative)
            shutil.copytree(
                ROOT / "history" / "countries",
                temporary_root / "history" / "countries",
            )
            third_effect_file = (
                temporary_root
                / "common"
                / "scripted_effects"
                / "ZZ_ADISCORD_test_external_assistance_owner.txt"
            )

            for entrypoint in (validate_economy_ai, validate_minor_optimization):
                with self.subTest(entrypoint=entrypoint.__module__, mutation="control"):
                    self.assertNotIn(
                        expected_issue,
                        entrypoint(root=temporary_root),
                    )

            third_effect_file.write_text(
                "# add_ideas = ADISCORD_economy_ai_assistance_base\n"
                "ADISCORD_test_assistance_owner_decoy = {\n"
                '\tlog = "remove_ideas = ADISCORD_economy_ai_assistance_retreat"\n'
                "}\n",
                encoding="utf-8",
            )
            for entrypoint in (validate_economy_ai, validate_minor_optimization):
                with self.subTest(
                    entrypoint=entrypoint.__module__, mutation="comment-and-quote control"
                ):
                    self.assertNotIn(
                        expected_issue,
                        entrypoint(root=temporary_root),
                    )

            assistance_ideas = (
                "ADISCORD_economy_ai_assistance_base",
                "ADISCORD_economy_ai_assistance_civil_war",
                "ADISCORD_economy_ai_assistance_retreat",
            )
            for operation in ("add_ideas", "remove_ideas"):
                for idea in assistance_ideas:
                    third_effect_file.write_text(
                        "ADISCORD_test_external_assistance_owner = {\n"
                        f"\t{operation} = {idea}\n"
                        "}\n",
                        encoding="utf-8",
                    )
                    for entrypoint in (
                        validate_economy_ai,
                        validate_minor_optimization,
                    ):
                        with self.subTest(
                            entrypoint=entrypoint.__module__,
                            operation=operation,
                            idea=idea,
                        ):
                            self.assertIn(
                                expected_issue,
                                entrypoint(root=temporary_root),
                            )

    def test_ai_assistance_is_bounded_reversible_and_never_player_visible(self):
        for relative in (
            "common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt",
            "common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt",
        ):
            self.assertTrue((ROOT / relative).is_file(), f"missing future-owned source: {relative}")
        minor_ideas_path = ROOT / "common" / "ideas" / "ADISCORD_minor_optimization_ideas.txt"
        minor_effects_path = (
            ROOT
            / "common"
            / "scripted_effects"
            / "ADISCORD_minor_optimization_effects.txt"
        )
        self.assertTrue(
            minor_ideas_path.is_file(),
            "missing future-owned source: common/ideas/ADISCORD_minor_optimization_ideas.txt",
        )
        self.assertTrue(
            minor_effects_path.is_file(),
            "missing future-owned source: common/scripted_effects/ADISCORD_minor_optimization_effects.txt",
        )
        minor_ideas = minor_ideas_path.read_text(encoding="utf-8-sig")
        minor_effects = minor_effects_path.read_text(encoding="utf-8-sig")
        minor_triggers = (
            ROOT
            / "common"
            / "scripted_triggers"
            / "ADISCORD_minor_optimization_triggers.txt"
        ).read_text(encoding="utf-8-sig")
        minor_on_actions = (
            ROOT
            / "common"
            / "on_actions"
            / "00_ADISCORD_minor_optimization_on_actions.txt"
        ).read_text(encoding="utf-8-sig")
        self.assertFalse(
            ai_assistance_contract_issues(
                minor_ideas,
                minor_effects + "\n" + EFFECTS,
                minor_triggers,
            )
        )
        self.assertFalse(
            ai_assistance_lifecycle_issues(EFFECTS, minor_effects, minor_on_actions)
        )
        assistance = {
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
        for idea_name, expected in assistance.items():
            idea = unique_block(minor_ideas, idea_name)
            self.assertIn("allowed = { always = no }", idea)
            for modifier, value in expected.items():
                actual = numeric_values(idea, modifier)
                if modifier == "supply_consumption_factor":
                    self.assertEqual(len(actual), 1, idea_name)
                    self.assertGreaterEqual(actual[0], value, idea_name)
                    self.assertLessEqual(actual[0], 0, idea_name)
                else:
                    self.assertEqual(actual, [value], idea_name)
            self.assertNotIn(idea_name, ECONOMY_IDEAS)

        refresh = unique_block(
            minor_effects + "\n" + EFFECTS,
            "ADISCORD_economy_refresh_ai_assistance",
        )
        self.assertIn("is_ai = yes", refresh)
        self.assertIn("ADISCORD_economy_simulation_tier", refresh)
        self.assertIn("surrender_progress", refresh)
        self.assertRegex(refresh, r"surrender_progress\s*>\s*0\.35")
        for idea_name in assistance:
            self.assertRegex(refresh, rf"remove_ideas\s*=\s*{idea_name}\b")
            self.assertRegex(refresh, rf"add_ideas\s*=\s*{idea_name}\b")
        for forbidden in (
            "attack_bonus",
            "army_attack_factor",
            "add_tech",
            "set_technology",
            "add_equipment_to_stockpile",
            "ADISCORD_economy_treasury",
            "ADISCORD_economy_inflation",
            "debt_capacity",
        ):
            self.assertNotIn(forbidden, refresh)

        lifecycle_mutations = {
            "monthly world scan": minor_on_actions.replace(
                "on_monthly = {",
                "on_monthly = { effect = { every_country = { always = yes } }",
                1,
            ),
            "weekly rebuild": minor_on_actions.replace(
                "on_monthly = {",
                "on_weekly = { effect = { ADISCORD_economy_refresh_ai_assistance = yes } }\non_monthly = {",
                1,
            ),
            "war removal omitted": minor_on_actions.replace(
                "ADISCORD_economy_refresh_ai_assistance = yes",
                "always = yes",
                1,
            ),
        }
        for name, mutation in lifecycle_mutations.items():
            with self.subTest(lifecycle_mutation=name):
                self.assertNotEqual(mutation, minor_on_actions)
                self.assertTrue(
                    ai_assistance_lifecycle_issues(EFFECTS, minor_effects, mutation)
                )

        economy_lifecycle_mutations = {
            "tier hook omitted": EFFECTS.replace(
                "\tADISCORD_economy_refresh_ai_assistance = yes\n}\n\n# Keep newly introduced transition effects",
                "}\n\n# Keep newly introduced transition effects",
                1,
            ),
            "dirty full-refresh hook omitted": EFFECTS.replace(
                "\t\tADISCORD_economy_refresh_ai_assistance = yes\n\t\tADISCORD_economy_full_refresh = yes",
                "\t\tADISCORD_economy_full_refresh = yes",
                1,
            ),
            "income cache scans world": EFFECTS.replace(
                "ADISCORD_economy_refresh_ai_assistance_income_cache = {",
                "ADISCORD_economy_refresh_ai_assistance_income_cache = { every_country = { always = yes }",
                1,
            ),
        }
        for name, mutation in economy_lifecycle_mutations.items():
            with self.subTest(economy_lifecycle_mutation=name):
                self.assertNotEqual(mutation, EFFECTS)
                self.assertTrue(
                    ai_assistance_lifecycle_issues(
                        mutation, minor_effects, minor_on_actions
                    )
                )

    def test_recovery_owned_economy_localisation_has_bilingual_keys_and_russian_bom(self):
        russian_path = (
            ROOT / "localisation" / "russian" / "ADISCORD_economy_l_russian.yml"
        )
        english_path = (
            ROOT / "localisation" / "english" / "ADISCORD_economy_l_english.yml"
        )
        self.assertTrue(english_path.is_file(), "schema-12 economy English file is missing")
        self.assertTrue(
            russian_path.read_bytes().startswith(b"\xef\xbb\xbf"),
            "Russian economy localisation lost its UTF-8 BOM",
        )
        russian = russian_path.read_text(encoding="utf-8-sig")
        english = english_path.read_text(encoding="utf-8-sig")
        owned = re.compile(
            r"^ADISCORD_economy_(?:research_|debt_state_|debt_notification_|"
            r"policy_(?:blocked|preview)_|(?:inflation|debt|treasury)_delayed_tt$)"
        )
        russian_keys = {key for key in localisation_key_set(russian) if owned.match(key)}
        english_keys = {key for key in localisation_key_set(english) if owned.match(key)}
        self.assertTrue(russian_keys, "no recovery-owned schema-12 keys were found")
        self.assertEqual(russian_keys, english_keys)
        for required in (
            "ADISCORD_economy_inflation_delayed_tt",
            "ADISCORD_economy_debt_delayed_tt",
            "ADISCORD_economy_treasury_delayed_tt",
            "ADISCORD_economy_policy_blocked_minimum",
            "ADISCORD_economy_policy_blocked_maximum",
            "ADISCORD_economy_policy_blocked_cooldown",
            "ADISCORD_economy_policy_blocked_scope",
        ):
            self.assertIn(required, russian_keys)

    def test_val_and_stp_start_with_distinct_macroeconomic_profiles(self):
        initialization = block(EFFECTS, "ADISCORD_economy_initialize_country")
        profile_call = "ADISCORD_economy_apply_country_starting_profile = yes"
        self.assertEqual(initialization.count(profile_call), 1)
        self.assertLess(initialization.index(profile_call), initialization.index("else ="))
        self.assertIn("ADISCORD_economy_update_stretched = yes", initialization)
        self.assertIn("ADISCORD_economy_calculate_macro_indicators = yes", initialization)

        dispatcher = block(EFFECTS, "ADISCORD_economy_apply_country_starting_profile")
        self.assertIn("tag = VAL", dispatcher)
        self.assertIn("ADISCORD_economy_apply_val_starting_profile = yes", dispatcher)
        self.assertIn("tag = STP", dispatcher)
        self.assertIn("ADISCORD_economy_apply_stp_starting_profile = yes", dispatcher)

        profiles = {
            "val": {
                "treasury": 180,
                "debt": 260,
                "inflation": 9,
                "deficit_pressure": 14,
                "fiscal_stress": 22,
                "price_shock": 10,
            },
            "stp": {
                "treasury": 240,
                "debt": 140,
                "inflation": 14,
                "deficit_pressure": 8,
                "fiscal_stress": 26,
                "price_shock": 16,
            },
        }
        for country, expected in profiles.items():
            profile = block(
                EFFECTS,
                f"ADISCORD_economy_apply_{country}_starting_profile",
            )
            for metric, value in expected.items():
                self.assertRegex(
                    profile,
                    rf"set_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_{metric}\s+value\s*=\s*{value}\s*\}}",
                )
            self.assertIn("ADISCORD_economy_sync_starting_accounting = yes", profile)

        accounting = block(EFFECTS, "ADISCORD_economy_sync_starting_accounting")
        for snapshot in (
            "accounting_period_treasury_start",
            "last_period_treasury_before",
            "last_period_treasury_after",
            "last_month_treasury_before",
            "last_month_treasury_after",
        ):
            self.assertRegex(
                accounting,
                rf"var\s*=\s*ADISCORD_economy_{snapshot}\s+value\s*=\s*ADISCORD_economy_treasury",
            )

        for recurring_effect in (
            "ADISCORD_economy_weekly_update",
            "ADISCORD_economy_monthly_update",
        ):
            self.assertNotIn(profile_call, block(EFFECTS, recurring_effect))

    def test_weekly_pulse_is_country_scoped_and_applies_once(self):
        weekly = block(ON_ACTIONS, "on_weekly")
        self.assertIn("ADISCORD_economy_should_weekly_update", weekly)
        self.assertEqual(weekly.count("ADISCORD_economy_weekly_update = yes"), 1)
        for forbidden in ("every_country", "every_owned_state", "all_owned_state"):
            self.assertNotIn(forbidden, weekly)

    def test_weekly_eligibility_uses_cached_tier_without_country_iteration(self):
        weekly_trigger = block(TRIGGERS, "ADISCORD_economy_should_weekly_update")
        self.assertIn("ADISCORD_economy_is_player_tier_country = yes", weekly_trigger)
        self.assertIn("has_variable = ADISCORD_economy_simulation_tier", weekly_trigger)
        self.assertIn("var = ADISCORD_economy_simulation_tier", weekly_trigger)
        for forbidden in (
            "ADISCORD_economy_is_primary_tier_country",
            "ADISCORD_economy_is_secondary_tier_country",
            "any_enemy_country",
            "any_country",
            "every_country",
        ):
            self.assertNotIn(forbidden, weekly_trigger)

    def test_weekly_budget_uses_exact_annual_parity_ratio(self):
        weekly = block(EFFECTS, "ADISCORD_economy_calculate_weekly_budget")
        self.assertRegex(
            weekly,
            r"weekly_income[\s\S]*multiply_variable[\s\S]*value\s*=\s*3",
        )
        self.assertRegex(
            weekly,
            r"weekly_income[\s\S]*divide_variable[\s\S]*value\s*=\s*13",
        )
        self.assertRegex(
            weekly,
            r"weekly_expenses[\s\S]*multiply_variable[\s\S]*value\s*=\s*3",
        )
        self.assertRegex(
            weekly,
            r"weekly_expenses[\s\S]*divide_variable[\s\S]*value\s*=\s*13",
        )

    def test_safe_reserve_reuses_weekly_expenses_without_a_new_scan(self):
        weekly = block(EFFECTS, "ADISCORD_economy_calculate_weekly_budget")
        self.assertIn(
            "var = ADISCORD_economy_safe_reserve value = ADISCORD_economy_weekly_expenses",
            weekly,
        )
        self.assertIn(
            "clamp_variable = { var = ADISCORD_economy_safe_reserve min = 50 max = 250 }",
            weekly,
        )
        for forbidden in ("every_country", "every_owned_state", "all_owned_state"):
            self.assertNotIn(forbidden, weekly)

    def test_deficit_borrowing_cannot_be_disabled_by_hidden_save_state(self):
        for settlement_name in (
            "ADISCORD_economy_apply_weekly_balance",
            "ADISCORD_economy_apply_monthly_balance",
        ):
            settlement = block(EFFECTS, settlement_name)
            self.assertIn("ADISCORD_economy_auto_borrow_temp", settlement)
            self.assertNotIn("ADISCORD_economy_auto_loan_enabled", settlement)

        for retired_name in (
            "ADISCORD_economy_auto_loan_enabled",
            "ADISCORD_economy_toggle_auto_loan",
            "ADISCORD_economy_gui_try_toggle_auto_loan",
        ):
            self.assertNotIn(retired_name, EFFECTS)

    def test_removed_dashboard_state_has_no_runtime_consumers(self):
        for retired_name in (
            "ADISCORD_economy_gui_page",
            "ADISCORD_economy_admin_spending_mode",
        ):
            self.assertNotIn(retired_name, EFFECTS)

        for retired_effect in (
            "ADISCORD_economy_weekly_player_refresh",
            "ADISCORD_economy_gui_try_early_repay_debt",
            "ADISCORD_economy_gui_try_expand_emission",
            "ADISCORD_economy_gui_try_reduce_emission",
            "ADISCORD_economy_gui_try_invest_reserves",
            "ADISCORD_economy_gui_try_civilian_investment",
            "ADISCORD_economy_gui_try_military_investment",
        ):
            self.assertNotIn(retired_effect, EFFECTS)

    def test_weekly_update_has_no_full_refresh_or_map_scan(self):
        weekly = block(EFFECTS, "ADISCORD_economy_weekly_update")
        self.assertEqual(weekly.count("ADISCORD_economy_apply_weekly_balance = yes"), 1)
        self.assertIn("ADISCORD_economy_prepare_weekly_country = yes", weekly)
        self.assertIn("ADISCORD_economy_light_update = yes", weekly)
        self.assertNotIn("ADISCORD_economy_calculate_weekly_budget = yes", weekly)
        self.assertNotIn("ADISCORD_economy_initialize_country = yes", weekly)
        for forbidden in (
            "ADISCORD_economy_full_refresh",
            "ADISCORD_economy_recount_economic_buildings",
            "ADISCORD_economy_update_gui",
            "every_country",
            "every_owned_state",
            "all_owned_state",
        ):
            self.assertNotIn(forbidden, weekly)

    def test_light_update_refreshes_weekly_forecast_for_every_gui_action(self):
        light = block(EFFECTS, "ADISCORD_economy_light_update")
        self.assertIn("ADISCORD_economy_calculate_monthly_balance = yes", light)
        self.assertIn("ADISCORD_economy_calculate_weekly_budget = yes", light)
        self.assertLess(
            light.index("ADISCORD_economy_calculate_monthly_balance = yes"),
            light.index("ADISCORD_economy_calculate_weekly_budget = yes"),
        )
        targeted_tail = block(
            EFFECTS, "ADISCORD_economy_finish_targeted_policy_refresh"
        )
        self.assertLess(
            targeted_tail.index("ADISCORD_economy_calculate_monthly_balance = yes"),
            targeted_tail.index("ADISCORD_economy_calculate_weekly_budget = yes"),
        )
        for policy in ("tax", "army", "research", "social"):
            policy_refresh = block(
                EFFECTS, f"ADISCORD_economy_refresh_{policy}_policy"
            )
            self.assertIn(
                "ADISCORD_economy_finish_targeted_policy_refresh = yes",
                policy_refresh,
            )

        budget_refresh = block(
            EFFECTS, "ADISCORD_economy_refresh_after_budget_control_change"
        )
        self.assertEqual(
            budget_refresh.strip(), "ADISCORD_economy_refresh_research_policy = yes"
        )

    def test_weekly_hot_path_reuses_monthly_idea_and_policy_caches(self):
        light = block(EFFECTS, "ADISCORD_economy_light_update")
        self.assertIn("ADISCORD_economy_cycle_phase", light)
        for expensive_idea_refresh in (
            "ADISCORD_economy_recalculate_policy_modifiers = yes",
            "ADISCORD_economy_update_model_and_cycle = yes",
            "has_idea =",
        ):
            self.assertNotIn(expensive_idea_refresh, light)

        model_refresh = block(EFFECTS, "ADISCORD_economy_update_model_and_cycle")
        self.assertIn(
            "ADISCORD_economy_has_idea_economic_system_agrarian = yes",
            model_refresh,
        )
        self.assertIn("ADISCORD_economy_cycle_phase", model_refresh)

        # New scripted-effect identifiers do not reliably register during the
        # mod's iterative HOI4 hot-reload workflow. Keep this tiny hot-path
        # calculation inline so a reload cannot produce Unknown effect-type.
        self.assertNotIn("ADISCORD_economy_update_cycle =", EFFECTS)

        for scheduled_refresh in (
            "ADISCORD_economy_monthly_update",
            "ADISCORD_economy_yearly_update",
            "ADISCORD_economy_open_window",
        ):
            body = block(EFFECTS, scheduled_refresh)
            self.assertIn("ADISCORD_economy_update_model_and_cycle = yes", body)
            self.assertIn("ADISCORD_economy_recalculate_policy_modifiers = yes", body)

    def test_weekly_forecast_has_no_transitive_idea_database_queries(self):
        for hot_effect in (
            "ADISCORD_economy_light_update",
            "ADISCORD_economy_calculate_income",
            "ADISCORD_economy_calculate_consumer_goods_income",
            "ADISCORD_economy_calculate_factory_income",
            "ADISCORD_economy_calculate_resource_income",
            "ADISCORD_economy_calculate_expenses",
            "ADISCORD_economy_calculate_army_expenses",
        ):
            self.assertNotIn("has_idea =", block(EFFECTS, hot_effect), hot_effect)

        policy_refresh = block(
            MODIFIER_EFFECTS, "ADISCORD_economy_recalculate_policy_modifiers"
        )
        for cache in (
            "ADISCORD_economy_cached_consumer_goods_law_adjustment",
            "ADISCORD_economy_cached_val_weaponry_active",
            "ADISCORD_economy_cached_resource_trade_law_factor",
            "ADISCORD_economy_cached_army_organization_flat_expense",
            "ADISCORD_economy_cached_army_organization_factor",
        ):
            self.assertIn(cache, policy_refresh)

    def test_treasury_operations_overlay_is_click_only_and_resets_with_window(self):
        for window_effect in (
            "ADISCORD_economy_open_window",
            "ADISCORD_economy_close_window",
        ):
            body = block(EFFECTS, window_effect)
            self.assertRegex(
                body,
                r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_show_operations"
                r"\s+value\s*=\s*0\s*\}",
            )

        for recurring_effect in (
            "ADISCORD_economy_weekly_update",
            "ADISCORD_economy_monthly_update",
            "ADISCORD_economy_yearly_update",
            "ADISCORD_economy_light_update",
        ):
            self.assertNotIn(
                "ADISCORD_economy_show_operations",
                block(EFFECTS, recurring_effect),
                recurring_effect,
            )

    def test_peacetime_war_fatigue_always_decays(self):
        fatigue = block(EFFECTS, "ADISCORD_economy_update_war_fatigue")
        for source in (
            "ADISCORD_economy_has_military_total_defense_grid = yes",
            "ADISCORD_economy_has_labor_mobilized_labor = yes",
            "ADISCORD_economy_has_taxation_extraction_quotas = yes",
        ):
            line = next(line for line in fatigue.splitlines() if source in line)
            self.assertIn("has_war = yes", line, source)

    def test_postwar_demobilization_reuses_scheduled_economy_updates(self):
        definition = EFFECTS.index("ADISCORD_economy_update_postwar_demobilization = {")
        first_monthly_call = EFFECTS.index(
            "ADISCORD_economy_update_postwar_demobilization = yes"
        )
        tick_definition = EFFECTS.index(
            "ADISCORD_economy_tick_postwar_demobilization = {"
        )
        first_tick_call = EFFECTS.index(
            "ADISCORD_economy_tick_postwar_demobilization = yes"
        )
        self.assertLess(definition, first_monthly_call)
        self.assertLess(tick_definition, first_tick_call)

        monthly = block(EFFECTS, "ADISCORD_economy_monthly_update")
        yearly = block(EFFECTS, "ADISCORD_economy_yearly_update")
        for scheduled_update in (monthly, yearly):
            self.assertIn(
                "ADISCORD_economy_update_postwar_demobilization = yes",
                scheduled_update,
            )
        on_monthly = block(ON_ACTIONS, "on_monthly")
        for forbidden in ("every_country", "every_owned_state", "all_owned_state"):
            self.assertNotRegex(on_monthly, rf"(?m)^\s*{forbidden}\s*=")

    def test_war_edges_trigger_demobilization_immediately_without_recurring_scans(self):
        on_war = block(ON_ACTIONS, "on_war")
        on_peace = block(ON_ACTIONS, "on_peace")

        for edge in (on_war, on_peace):
            self.assertIn("has_variable = ADISCORD_economy_initialized", edge)
            self.assertEqual(
                edge.count("ADISCORD_economy_update_postwar_demobilization = yes"),
                1,
            )
            for forbidden in (
                "every_country",
                "every_owned_state",
                "all_owned_state",
                "on_daily",
            ):
                self.assertNotIn(forbidden, edge)

        self.assertIn("has_war = no", on_peace)
        self.assertIn("ADISCORD_economy_recalculate_policy_modifiers = yes", on_peace)
        self.assertIn(
            "ADISCORD_economy_refresh_after_budget_control_change = yes", on_peace
        )

    def test_postwar_transition_is_one_shot_and_automatically_normalizes_war_laws(self):
        transition = block(EFFECTS, "ADISCORD_economy_update_postwar_demobilization")
        self.assertIn("ADISCORD_economy_was_at_war", transition)
        self.assertIn("has_war = no", transition)
        self.assertIn("ADISCORD_economy_postwar_demobilization_months value = 6", transition)
        self.assertIn("ADISCORD_economy_army_spending_mode value = 3", transition)
        self.assertIn("add_ideas = partial_economic_mobilisation", transition)
        self.assertIn("add_ideas = limited_conscription", transition)
        self.assertIn("ADISCORD_economy_postwar_demobilization", transition)
        self.assertIn("country_event = { id = ADISCORD_economy.2 }", transition)
        for forbidden in ("every_country", "every_owned_state", "all_owned_state"):
            self.assertNotIn(forbidden, transition)

    def test_demobilization_accelerates_recovery_and_is_cancelled_by_a_new_war(self):
        transition = block(EFFECTS, "ADISCORD_economy_update_postwar_demobilization")
        fatigue = block(EFFECTS, "ADISCORD_economy_update_war_fatigue")
        tick = block(EFFECTS, "ADISCORD_economy_tick_postwar_demobilization")
        self.assertIn("has_war = yes", transition)
        self.assertIn("remove_ideas = ADISCORD_economy_postwar_demobilization", transition)
        self.assertIn("ADISCORD_economy_postwar_demobilization_months", fatigue)
        self.assertIn("value = -4", fatigue)
        self.assertIn("ADISCORD_economy_tick_scale", tick)
        self.assertIn("min = 0 max = 6", tick)
        self.assertIn("ADISCORD_economy_postwar_demobilization", ECONOMY_IDEAS)

        monthly = block(EFFECTS, "ADISCORD_economy_monthly_update")
        transition_index = monthly.index(
            "ADISCORD_economy_update_postwar_demobilization = yes"
        )
        fatigue_index = monthly.index("ADISCORD_economy_update_war_fatigue = yes")
        tick_index = monthly.index("ADISCORD_economy_tick_postwar_demobilization = yes")
        self.assertLess(transition_index, fatigue_index)
        self.assertLess(fatigue_index, tick_index)

    def test_demobilization_tradeoffs_are_explicit_for_the_player(self):
        idea = block(ECONOMY_IDEAS, "ADISCORD_economy_postwar_demobilization")
        for modifier, value in (
            ("stability_factor", "0.02"),
            ("war_support_factor", "-0.05"),
            ("industrial_capacity_factory", "-0.08"),
            ("production_speed_arms_factory_factor", "-0.15"),
            ("production_speed_dockyard_factor", "-0.10"),
            ("production_speed_industrial_complex_factor", "0.10"),
            ("ADISCORD_economy_army_expense_factor", "-0.10"),
            ("ADISCORD_economy_inflation_pressure_factor", "-0.10"),
            ("ADISCORD_economy_state_overload_gain_factor", "-0.10"),
            ("ADISCORD_country_development_economic_growth_factor", "0.05"),
        ):
            self.assertRegex(idea, rf"\b{modifier}\s*=\s*{re.escape(value)}\b")

        status = re.search(
            r'(?m)^\s*ADISCORD_economy_demobilization_status_active:\d*\s+"([^"]*)"',
            ECONOMY_LOC,
        ).group(1)
        for required in (
            "+2%",
            "+10%",
            "-10%",
            "-8%",
            "-15%",
            "-5%",
        ):
            self.assertIn(required, status)

        fatigue_tooltip = re.search(
            r'(?m)^\s*ADISCORD_economy_war_fatigue_tt:\d*\s+"([^"]*)"',
            ECONOMY_LOC,
        ).group(1)
        self.assertIn("8 пунктов", fatigue_tooltip)
        self.assertIn("первый мирный месяц", fatigue_tooltip)

    def test_every_dashboard_variable_is_backed_by_runtime_script(self):
        references = set(
            re.findall(r"\[\?(ADISCORD_[A-Za-z0-9_]+)", ECONOMY_LOC)
        )
        runtime = "\n".join(
            path.read_text(encoding="utf-8-sig", errors="ignore")
            for path in (ROOT / "common" / "scripted_effects").glob("*.txt")
        )
        missing = sorted(reference for reference in references if reference not in runtime)
        self.assertFalse(missing, f"unbacked dashboard variables: {missing}")

    def test_player_receives_a_plain_language_postwar_notification(self):
        second_event_start = ECONOMY_EVENTS.find("id = ADISCORD_economy.2")
        self.assertGreater(second_event_start, 0)
        self.assertNotIn("id = ADISCORD_economy.1", ECONOMY_EVENTS)
        second_event = ECONOMY_EVENTS[second_event_start:]
        self.assertIn("is_triggered_only = yes", second_event)
        for key in (
            "ADISCORD_economy.2.t",
            "ADISCORD_economy.2.d",
            "ADISCORD_economy.2.a",
            "ADISCORD_economy_postwar_demobilization",
            "ADISCORD_economy_postwar_demobilization_desc",
        ):
            self.assertRegex(ECONOMY_LOC, rf"(?m)^\s*{re.escape(key)}:\d*\s+")

    def test_monthly_model_refresh_checks_each_system_law_only_once(self):
        model_refresh = block(EFFECTS, "ADISCORD_economy_update_model_and_cycle")
        for suffix in (
            "agrarian",
            "industrializing",
            "free_market",
            "mixed",
            "state_coordinated",
            "planned_bureaucratic",
            "mobilization",
            "oligarchic_clan",
            "technocratic",
        ):
            trigger_call = (
                f"ADISCORD_economy_has_idea_economic_system_{suffix} = yes"
            )
            self.assertEqual(model_refresh.count(trigger_call), 1, trigger_call)

        monthly = block(EFFECTS, "ADISCORD_economy_monthly_update")
        self.assertEqual(
            monthly.count("ADISCORD_economy_update_model_and_cycle = yes"), 1
        )
        self.assertIn("ADISCORD_economy_cycle_phase", monthly)

    def test_hot_reloadable_economy_effects_use_stable_idea_wrappers(self):
        self.assertNotIn("has_idea =", EFFECTS)
        self.assertNotIn("has_idea =", MODIFIER_EFFECTS)

        wrappers = {
            "ADISCORD_economy_has_idea_civilian_economy": "civilian_economy",
            "ADISCORD_economy_has_idea_low_economic_mobilisation": "low_economic_mobilisation",
            "ADISCORD_economy_has_idea_partial_economic_mobilisation": "partial_economic_mobilisation",
            "ADISCORD_economy_has_idea_war_economy": "war_economy",
            "ADISCORD_economy_has_idea_total_economic_mobilisation": "tot_economic_mobilisation",
            "ADISCORD_economy_has_idea_extensive_conscription": "extensive_conscription",
            "ADISCORD_economy_has_idea_service_by_requirement": "service_by_requirement",
            "ADISCORD_economy_has_idea_all_adults_serve": "all_adults_serve",
            "ADISCORD_economy_has_idea_scraping_the_barrel": "scraping_the_barrel",
            "ADISCORD_economy_has_idea_free_trade": "free_trade",
            "ADISCORD_economy_has_idea_export_focus": "export_focus",
            "ADISCORD_economy_has_idea_limited_exports": "limited_exports",
            "ADISCORD_economy_has_idea_closed_economy": "closed_economy",
            "ADISCORD_economy_has_idea_val_worldwide_famous_weaponry": "VAL_worldwide_famous_weponry",
            "ADISCORD_economy_has_idea_society_type_information": "ADISCORD_society_type_information",
        }
        for suffix in (
            "agrarian",
            "industrializing",
            "free_market",
            "mixed",
            "state_coordinated",
            "planned_bureaucratic",
            "mobilization",
            "oligarchic_clan",
            "technocratic",
        ):
            wrappers[f"ADISCORD_economy_has_idea_economic_system_{suffix}"] = (
                f"ADISCORD_economic_system_{suffix}"
            )
        for suffix in (
            "contract_brigades",
            "general_staff",
            "total_defense_grid",
            "militia_autonomy",
        ):
            wrappers[f"ADISCORD_economy_has_idea_military_organization_{suffix}"] = (
                f"ADISCORD_military_organization_{suffix}"
            )

        combined_effects = EFFECTS + MODIFIER_EFFECTS
        for wrapper, idea in wrappers.items():
            self.assertIn(f"{wrapper} = yes", combined_effects, wrapper)
            self.assertIn(f"has_idea = {idea}", block(TRIGGERS, wrapper), wrapper)

    def test_state_control_changes_only_invalidate_existing_country_caches(self):
        control_change = block(ON_ACTIONS, "on_state_control_changed")
        self.assertEqual(control_change.count("ADISCORD_economy_mark_dirty = yes"), 2)
        self.assertEqual(
            control_change.count("has_variable = ADISCORD_economy_initialized"), 2
        )
        self.assertIn("FROM =", control_change)
        for forbidden in ("every_country", "every_owned_state", "full_refresh"):
            self.assertNotIn(forbidden, control_change)

    def test_weekly_prepare_does_not_recalculate_simulation_tier(self):
        prepare = block(EFFECTS, "ADISCORD_economy_prepare_weekly_country")
        self.assertIn("has_variable = ADISCORD_economy_initialized", prepare)
        self.assertIn("has_variable = ADISCORD_economy_weekly_source_cache_ready", prepare)
        self.assertIn("ADISCORD_economy_weekly_ready value = 1", prepare)
        for forbidden in (
            "ADISCORD_economy_initialize_country",
            "ADISCORD_economy_migrate_schema",
            "ADISCORD_economy_set_simulation_tier",
            "ADISCORD_economy_is_primary_tier_country",
            "any_enemy_country",
            "any_country",
            "every_country",
            "every_owned_state",
        ):
            self.assertNotIn(forbidden, prepare)

    def test_monthly_tick_does_not_apply_cash(self):
        monthly = block(EFFECTS, "ADISCORD_economy_monthly_update")
        self.assertEqual(
            monthly.count("ADISCORD_economy_update_monthly_budget_trend = yes"), 1
        )
        self.assertNotIn("apply_weekly_balance", monthly)
        self.assertNotIn("apply_monthly_balance", monthly)
        self.assertNotIn("apply_budget_period", monthly)

    def test_monthly_budget_trend_changes_pressure_without_changing_treasury(self):
        trend = block(EFFECTS, "ADISCORD_economy_update_monthly_budget_trend")
        self.assertIn("ADISCORD_economy_monthly_balance", trend)
        self.assertIn("ADISCORD_economy_deficit_streak", trend)
        self.assertIn("ADISCORD_economy_surplus_streak", trend)
        self.assertNotIn("ADISCORD_economy_treasury", trend)

    def test_market_inflation_does_not_self_heal_without_an_explicit_action(self):
        inflation = block(EFFECTS, "ADISCORD_economy_update_inflation")
        market_branch = inflation[inflation.index("else =") :]
        delta_start = market_branch.index(
            "set_variable = { var = ADISCORD_economy_inflation_delta_temp"
        )
        delta_end = market_branch.index(
            "add_to_variable = { var = ADISCORD_economy_inflation value = ADISCORD_economy_inflation_delta_temp",
            delta_start,
        )
        delta_formula = market_branch[delta_start:delta_end]

        self.assertNotIn("ADISCORD_economy_monthly_balance", delta_formula)
        self.assertNotIn("ADISCORD_economy_surplus_streak", delta_formula)
        self.assertNotIn("ADISCORD_economy_money_printing_level", delta_formula)
        self.assertRegex(
            delta_formula,
            r"clamp_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_inflation_delta_temp\s+min\s*=\s*0\s+max\s*=\s*1\.5\s*\}",
        )

        planned_branch = inflation[: inflation.index("else =")]
        self.assertIn(
            "set_variable = { var = ADISCORD_economy_inflation_delta_temp value = -2 }",
            planned_branch,
        )
        self.assertIn(
            "add_to_variable = { var = ADISCORD_economy_inflation value = -8 }",
            block(EFFECTS, "ADISCORD_economy_stabilization_package"),
        )
        self.assertIn(
            "add_to_variable = { var = ADISCORD_economy_inflation value = -2 }",
            block(EFFECTS, "ADISCORD_economy_reduce_money_emission"),
        )

    def test_borrowing_has_immediate_inflation_and_refreshes_visible_penalties(self):
        internal = block(EFFECTS, "ADISCORD_economy_take_debt")
        self.assertIn("ADISCORD_economy_loan_inflation_temp value = 1", internal)
        self.assertIn(
            "value = ADISCORD_economy_loan_realized_factor_temp", internal
        )
        self.assertIn(
            "var = ADISCORD_economy_inflation value = ADISCORD_economy_loan_inflation_temp",
            internal,
        )

        external = block(EFFECTS, "ADISCORD_economy_take_external_loan")
        self.assertIn("ADISCORD_economy_external_inflation_temp value = 1.5", external)
        self.assertIn(
            "value = ADISCORD_economy_external_realized_factor_temp", external
        )
        self.assertIn(
            "var = ADISCORD_economy_inflation value = ADISCORD_economy_external_inflation_temp",
            external,
        )

        weekly_settlement = block(EFFECTS, "ADISCORD_economy_apply_weekly_balance")
        self.assertIn(
            "var = ADISCORD_economy_auto_borrow_inflation_temp value = ADISCORD_economy_auto_borrow_temp",
            weekly_settlement,
        )
        self.assertIn(
            "divide_temp_variable = { var = ADISCORD_economy_auto_borrow_inflation_temp value = 100 }",
            weekly_settlement,
        )

        yearly_settlement = block(EFFECTS, "ADISCORD_economy_apply_monthly_balance")
        self.assertIn(
            "var = ADISCORD_economy_auto_borrow_inflation_temp value = ADISCORD_economy_auto_borrow_temp",
            yearly_settlement,
        )
        self.assertIn(
            "divide_temp_variable = { var = ADISCORD_economy_auto_borrow_inflation_temp value = 100 }",
            yearly_settlement,
        )

        for effect_name in (
            "ADISCORD_economy_gui_try_issue_internal_bonds",
            "ADISCORD_economy_gui_try_take_external_loan",
        ):
            action = block(EFFECTS, effect_name)
            self.assertIn("ADISCORD_economy_update_stretched = yes", action)
            self.assertNotIn("ADISCORD_economy_refresh_spending_ideas = yes", action)

    def test_player_gets_one_cached_notification_when_debt_state_changes(self):
        reachable = reachable_script_blocks(
            (EFFECTS, TRIGGERS), ("ADISCORD_economy_apply_weekly_balance",)
        )
        self.assertIn("ADISCORD_economy_queue_debt_notification", reachable)
        event_owners = [
            name
            for name, body in reachable.items()
            if "country_event id ADISCORD_economy.3" in body
        ]
        self.assertEqual(event_owners, ["ADISCORD_economy_queue_debt_notification"])
        event_blocks = [
            body
            for body in assignment_blocks(ECONOMY_EVENTS, "country_event")
            if re.search(r"\bid\s*=\s*ADISCORD_economy\.3\b", body)
        ]
        self.assertEqual(len(event_blocks), 1)
        event = event_blocks[0]
        self.assertIn("is_triggered_only = yes", event)
        for key in ("ADISCORD_economy.3.t", "ADISCORD_economy.3.d", "ADISCORD_economy.3.a"):
            self.assertIn(key, event)
            self.assertRegex(ECONOMY_LOC, rf"(?m)^\s*{re.escape(key)}:\d*\s+")
            self.assertRegex(ECONOMY_LOC_EN, rf"(?m)^\s*{re.escape(key)}:\d*\s+")
        selector_surfaces = {
            "GetADISCORDEconomyDebtNotificationKindLoc": "ADISCORD_economy.3.t",
            "GetADISCORDEconomyDebtNotificationCauseLoc": "ADISCORD_economy.3.d",
            "GetADISCORDEconomyDebtNotificationStateLoc": "ADISCORD_economy.3.d",
            "GetADISCORDEconomyDebtNotificationNextRiskLoc": "ADISCORD_economy.3.d",
        }
        selector_bodies = []
        for selector, surface_key in selector_surfaces.items():
            self.assertIn(f"name = {selector}", SCRIPTED_LOC)
            self.assertIn(
                f"[{selector}]", localisation_value(ECONOMY_LOC, surface_key)
            )
            self.assertIn(
                f"[{selector}]", localisation_value(ECONOMY_LOC_EN, surface_key)
            )
            selector_body = unique_defined_text(SCRIPTED_LOC, selector)
            selector_bodies.append(selector_body)
            self.assertRegex(
                selector_body,
                r"text\s*=\s*\{\s*localization_key\s*=\s*"
                r"ADISCORD_economy_debt_notification_[A-Za-z0-9_]+\s*\}\s*$",
                selector,
            )
        self.assertIn(
            "[GetADISCORDDebtEffectsLoc]",
            localisation_value(ECONOMY_LOC, "ADISCORD_economy.3.d"),
        )
        self.assertIn(
            "[GetADISCORDDebtEffectsLoc]",
            localisation_value(ECONOMY_LOC_EN, "ADISCORD_economy.3.d"),
        )
        task6_required_keys = {
            "ADISCORD_economy.3.t",
            "ADISCORD_economy.3.d",
            "ADISCORD_economy.3.a",
        }
        for selector_body in selector_bodies + [
            unique_defined_text(SCRIPTED_LOC, "GetADISCORDDebtEffectsLoc")
        ]:
            task6_required_keys.update(
                re.findall(
                    r"localization_key\s*=\s*"
                    r"(ADISCORD_economy_debt_(?:notification|effect)_[A-Za-z0-9_]+)",
                    selector_body,
                )
            )
        for key in sorted(task6_required_keys):
            with self.subTest(task6_localisation_key=key):
                self.assertRegex(ECONOMY_LOC, rf"(?m)^\s*{re.escape(key)}:\d*\s+")
                self.assertRegex(ECONOMY_LOC_EN, rf"(?m)^\s*{re.escape(key)}:\d*\s+")
        for variable in (
            "ADISCORD_economy_pending_debt_notification_amount",
            "ADISCORD_economy_debt",
            "ADISCORD_economy_weekly_interest",
            "ADISCORD_economy_interest_share_income",
        ):
            self.assertIn(variable, localisation_value(ECONOMY_LOC, "ADISCORD_economy.3.d"))
            self.assertIn(variable, localisation_value(ECONOMY_LOC_EN, "ADISCORD_economy.3.d"))
        self.assertNotIn("ADISCORD_economy_auto_loan_popup_script", SCRIPTED_GUI)

    def test_schema_fourteen_initializes_persistent_debt_state_without_load_spam(self):
        self.assertFalse(task6_schema_fourteen_migration_issues(EFFECTS))
        migration = unique_block(EFFECTS, "ADISCORD_economy_migrate_schema")
        self.assertIn(
            "check_variable = { var = ADISCORD_economy_schema_version value = 14 compare = less_than }",
            migration,
        )
        for variable in (
            "ADISCORD_economy_debt_state",
            "ADISCORD_economy_debt_emergency_streak",
            "ADISCORD_economy_debt_default_streak",
            "ADISCORD_economy_last_notified_debt_state",
            "ADISCORD_economy_pending_debt_notification_kind",
            "ADISCORD_economy_pending_debt_notification_amount",
            "ADISCORD_economy_pending_debt_notification_previous_state",
            "ADISCORD_economy_pending_debt_notification_new_state",
        ):
            self.assertIn(variable, migration)
        schema_fourteen = migration[migration.index("value = 14 compare = less_than") :]
        self.assertNotRegex(
            schema_fourteen,
            r"ADISCORD_economy_debt_state\s+value\s*=\s*[34]\b",
        )
        self.assertRegex(
            schema_fourteen,
            r"check_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_debt"
            r"\s+value\s*=\s*0\s+compare\s*=\s*greater_than\s*\}"
            r"(?s:.*?)set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_first_loan_notified\s+value\s*=\s*1\s*\}",
        )
        defaults = unique_block(EFFECTS, "ADISCORD_economy_set_default_values")
        self.assertIn("ADISCORD_economy_schema_version value = 15", defaults)
        self.assertNotIn("ADISCORD_economy_first_loan_notified", defaults)

        migration_mutations = {
            "legacy save jumps directly to emergency": migration.replace(
                "set_variable = { var = ADISCORD_economy_debt_state value = 2 }",
                "set_variable = { var = ADISCORD_economy_debt_state value = 3 }",
                1,
            ),
            "streak evidence manufactured on load": migration.replace(
                "set_variable = { var = ADISCORD_economy_debt_emergency_streak value = 0 }",
                "set_variable = { var = ADISCORD_economy_debt_emergency_streak value = 1 }",
                1,
            ),
            "notification watermark reset below migrated state": migration.replace(
                "set_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }",
                "set_variable = { var = ADISCORD_economy_last_notified_debt_state value = 0 }",
                1,
            ),
            "existing debt no longer suppresses first-loan spam": migration.replace(
                "check_variable = { var = ADISCORD_economy_debt value = 0 compare = greater_than }",
                "check_variable = { var = ADISCORD_economy_debt value = 0 compare = less_than }",
                1,
            ),
            "schema completion removed": migration.replace(
                "set_variable = { var = ADISCORD_economy_schema_version value = 14 }",
                "",
                1,
            ),
            "state two write moved outside legacy owner": migration.replace(
                "\t\tif = {\n"
                "\t\t\tlimit = { check_variable = { var = ADISCORD_economy_debt_crisis_level value = 2 compare = greater_than_or_equals } }\n"
                "\t\t\tset_variable = { var = ADISCORD_economy_debt_state value = 2 }\n"
                "\t\t}",
                "\t\tset_variable = { var = ADISCORD_economy_debt_state value = 2 }\n"
                "\t\tif = {\n"
                "\t\t\tlimit = { check_variable = { var = ADISCORD_economy_debt_crisis_level value = 2 compare = greater_than_or_equals } }\n"
                "\t\t}",
                1,
            ),
            "schema owner guard reversed": migration.replace(
                "ADISCORD_economy_schema_version value = 14 compare = less_than",
                "ADISCORD_economy_schema_version value = 14 compare = greater_than_or_equals",
                1,
            ),
            "schema owner made dead": migration.replace(
                "limit = { check_variable = { var = ADISCORD_economy_schema_version value = 14 compare = less_than } }",
                "limit = { check_variable = { var = ADISCORD_economy_schema_version value = 14 compare = less_than } always = no }",
                1,
            ),
            "watermark moved before legacy mapping": migration.replace(
                "\t\tset_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }\n",
                "",
                1,
            ).replace(
                "\t\tset_variable = { var = ADISCORD_economy_debt_state value = 0 }\n",
                "\t\tset_variable = { var = ADISCORD_economy_last_notified_debt_state value = ADISCORD_economy_debt_state }\n"
                "\t\tset_variable = { var = ADISCORD_economy_debt_state value = 0 }\n",
                1,
            ),
            "schema completion moved outside owner": migration.replace(
                "\t\tset_variable = { var = ADISCORD_economy_schema_version value = 14 }\n",
                "",
                1,
            ).replace(
                "\t}\n}",
                "\t}\n\tset_variable = { var = ADISCORD_economy_schema_version value = 14 }\n}",
                1,
            ),
            "schema completion before final debuff refresh": migration.replace(
                "\t\tset_variable = { var = ADISCORD_economy_schema_version value = 14 }\n",
                "",
                1,
            ).replace(
                "\t\tset_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n"
                "\t\tremove_ideas = {",
                "\t\tset_variable = { var = ADISCORD_economy_debt_crisis_level value = ADISCORD_economy_debt_state }\n"
                "\t\tset_variable = { var = ADISCORD_economy_schema_version value = 14 }\n"
                "\t\tremove_ideas = {",
                1,
            ),
            "unowned duplicate state write": migration
            + "\n\tset_variable = { var = ADISCORD_economy_debt_state value = 2 }",
            "unowned duplicate streak reset": migration
            + "\n\tset_variable = { var = ADISCORD_economy_debt_emergency_streak value = 0 }",
            "first-loan clear hidden behind dead owner": migration.replace(
                "\t\tclear_variable = ADISCORD_economy_first_loan_notified",
                "\t\tif = { limit = { always = no } clear_variable = ADISCORD_economy_first_loan_notified }",
                1,
            ),
            "pending state caches moved before legacy mapping": migration.replace(
                "\t\tset_variable = { var = ADISCORD_economy_pending_debt_notification_previous_state value = ADISCORD_economy_debt_state }\n"
                "\t\tset_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = ADISCORD_economy_debt_state }\n",
                "",
                1,
            ).replace(
                "\t\tset_variable = { var = ADISCORD_economy_debt_state value = 0 }\n",
                "\t\tset_variable = { var = ADISCORD_economy_pending_debt_notification_previous_state value = ADISCORD_economy_debt_state }\n"
                "\t\tset_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = ADISCORD_economy_debt_state }\n"
                "\t\tset_variable = { var = ADISCORD_economy_debt_state value = 0 }\n",
                1,
            ),
        }
        for name, mutated_migration in migration_mutations.items():
            with self.subTest(schema14_mutation=name):
                self.assertNotEqual(mutated_migration, migration)
                mutated_effects = EFFECTS.replace(migration, mutated_migration, 1)
                self.assertTrue(parse_clausewitz(mutated_effects))
                self.assertTrue(task6_schema_fourteen_migration_issues(mutated_effects))

    def test_schema_twelve_initializes_reserve_and_postwar_state_without_resetting_treasury(self):
        migration = block(EFFECTS, "ADISCORD_economy_migrate_schema")
        self.assertIn("value = 12", migration)
        self.assertIn("ADISCORD_economy_was_at_war", migration)
        self.assertIn("ADISCORD_economy_postwar_demobilization_months", migration)
        self.assertIn("ADISCORD_economy_initialize_variables = yes", migration)
        initialization = block(EFFECTS, "ADISCORD_economy_initialize_variables")
        self.assertIn("ADISCORD_economy_safe_reserve", initialization)
        self.assertIn("ADISCORD_economy_recalculate_policy_modifiers = yes", migration)
        self.assertNotRegex(
            migration,
            r"set_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_treasury\s+value\s*=\s*100",
        )

    def test_reserve_growth_factor_is_fully_retired(self):
        for text in (
            EFFECTS,
            MODIFIER_EFFECTS,
            MODIFIER_DEFINITIONS,
            TOKENS,
            MODIFIER_LOC,
        ):
            self.assertNotIn("reserve_growth", text)

    def test_treasury_tooltip_uses_weekly_and_period_values(self):
        self.assertIn("ADISCORD_economy_weekly_balance", ECONOMY_LOC)
        self.assertIn("ADISCORD_economy_weekly_income", ECONOMY_LOC)
        self.assertIn("ADISCORD_economy_weekly_expenses", ECONOMY_LOC)
        self.assertNotIn("ADISCORD_economy_last_period_unexplained_delta", ECONOMY_LOC)
        self.assertNotIn(
            "Фактическое изменение казны происходит раз в месяц", ECONOMY_LOC
        )

    def test_full_deficit_borrowing_has_no_unfunded_accounting_adjustment(self):
        settlement = block(EFFECTS, "ADISCORD_economy_apply_weekly_balance")
        self.assertNotIn("ADISCORD_economy_last_period_unfunded_deficit", settlement)
        self.assertNotIn("ADISCORD_economy_last_uncovered_deficit", settlement)
        migration = unique_block(EFFECTS, "ADISCORD_economy_migrate_schema")
        live_effects = EFFECTS.replace(migration, "")
        for retired_unfunded_state in (
            "ADISCORD_economy_last_period_unfunded_deficit",
            "ADISCORD_economy_last_uncovered_deficit",
        ):
            self.assertNotIn(retired_unfunded_state, live_effects)
            self.assertRegex(
                migration,
                rf"clear_variable\s*=\s*{retired_unfunded_state}\b",
            )

    def test_automatic_borrowing_does_not_add_unfunded_deficit_pressure(self):
        settlement = block(EFFECTS, "ADISCORD_economy_apply_weekly_balance")
        self.assertNotIn("ADISCORD_economy_unfunded_pressure_temp", settlement)
        self.assertNotIn("ADISCORD_economy_final_deficit_pressure_factor_bp", settlement)

    def test_budget_breakdown_leads_with_the_weekly_forecast(self):
        match = re.search(
            r'(?m)^\s*ADISCORD_economy_budget_breakdown_tt:\d*\s+"([^"]*)"',
            ECONOMY_LOC,
        )
        self.assertIsNotNone(match)
        tooltip = match.group(1)
        self.assertIn("ADISCORD_economy_weekly_income", tooltip)
        self.assertIn("ADISCORD_economy_weekly_expenses", tooltip)
        self.assertIn("ADISCORD_economy_weekly_balance", tooltip)

    def test_economic_buildings_keep_distinct_bounded_state_roles(self):
        specs = {
            "ADISCORD_business_center": (
                "5500",
                "750",
                "3",
                "local_building_slots_factor = 0.05",
            ),
            "ADISCORD_science_center": (
                "7000",
                "1250",
                "2",
                "local_building_slots_factor = 0.02",
            ),
            "ADISCORD_industrial_cluster": (
                "8000",
                "1500",
                "3",
                "local_factory_energy_consumption = 0.20",
            ),
        }
        for name, (cost, extra_cost, state_cap, signature) in specs.items():
            building = block(BUILDINGS, name)
            self.assertRegex(building, r"show_on_map\s*=\s*0")
            self.assertRegex(building, rf"base_cost\s*=\s*{cost}\b")
            self.assertRegex(
                building,
                rf"per_controlled_building_extra_cost\s*=\s*{extra_cost}\b",
            )
            self.assertRegex(building, rf"state_max\s*=\s*{state_cap}\b")
            self.assertIn(signature, building)

    def test_economic_building_effects_use_cached_country_counts(self):
        recount = block(EFFECTS, "ADISCORD_economy_recount_economic_buildings")
        weekly = block(EFFECTS, "ADISCORD_economy_weekly_update")
        for building in (
            "ADISCORD_business_center",
            "ADISCORD_science_center",
            "ADISCORD_industrial_cluster",
        ):
            self.assertIn(building, recount)
            self.assertIn(f"{building}_count", EFFECTS)
        self.assertEqual(recount.count("every_owned_state"), 1)
        self.assertNotIn("recount_economic_buildings", weekly)
        self.assertNotIn("every_owned_state", weekly)

    def test_industrial_cluster_output_is_location_weighted_without_a_new_scan(self):
        recount = block(EFFECTS, "ADISCORD_economy_recount_economic_buildings")
        dynamic_modifier = block(
            DYNAMIC_MODIFIERS, "ADISCORD_economy_cluster_local_factory_output"
        )
        self.assertEqual(recount.count("every_owned_state"), 1)
        self.assertGreaterEqual(recount.count("is_controlled_by = ROOT"), 2)
        for signature in (
            "building_level@arms_factory",
            "damaged_building_level@arms_factory",
            "is_controlled_by = ROOT",
            "ADISCORD_economy_state_cluster_level_temp",
            "ADISCORD_economy_cluster_supported_factory_points_temp",
            "ADISCORD_economy_operational_military_factories_temp",
            "ADISCORD_economy_cluster_factory_output_percent value = 5",
            "ADISCORD_economy_cluster_factory_output_factor value = 100",
            "max = 15",
            "remove_dynamic_modifier = { modifier = ADISCORD_economy_cluster_local_factory_output }",
            "force_update_dynamic_modifier = yes",
        ):
            self.assertIn(signature, recount)
        self.assertIn(
            "industrial_capacity_factory = ADISCORD_economy_cluster_factory_output_factor",
            dynamic_modifier,
        )
        self.assertNotIn("icon =", dynamic_modifier)
        for key in (
            "ADISCORD_economy_cluster_local_factory_output",
            "ADISCORD_economy_cluster_local_factory_output_desc",
        ):
            self.assertRegex(ECONOMY_LOC, rf"(?m)^\s*{key}:\d*\s+")
        self.assertIn("ADISCORD_economy_cluster_factory_output_percent", ECONOMY_LOC)
        weekly = block(EFFECTS, "ADISCORD_economy_weekly_update")
        self.assertNotIn("cluster_supported_factory", weekly)
        self.assertNotIn("every_owned_state", weekly)

    def test_ai_building_targets_are_bounded_by_fiscal_state(self):
        expected = {
            "ADISCORD_ai_fiscal_crisis": (0, 0, 0),
            "ADISCORD_ai_fiscal_stress": (0, 0, 0),
            "ADISCORD_ai_fiscal_recovery": (1, 0, 0),
            "ADISCORD_ai_healthy_civilian_growth": (2, 2, 2),
        }
        names = (
            "ADISCORD_business_center",
            "ADISCORD_science_center",
            "ADISCORD_industrial_cluster",
        )
        for strategy_name, targets in expected.items():
            strategy = block(ECONOMY_AI, strategy_name)
            for building, target in zip(names, targets):
                self.assertRegex(
                    strategy,
                    rf"building_target\s+id\s*=\s*{building}\s+value\s*=\s*{target}\b",
                )
        wartime = block(ECONOMY_AI, "ADISCORD_ai_healthy_war_industry")
        self.assertRegex(
            wartime,
            r"building_target\s+id\s*=\s*ADISCORD_industrial_cluster\s+value\s*=\s*3\b",
        )

    def test_building_tooltips_lead_with_role_and_budget_impact(self):
        self.assertNotIn("Строятся в обычном меню", ECONOMY_LOC)
        for key, role, budget in (
            ("ADISCORD_business_center_desc", "Роль: доход", "+0,90"),
            ("ADISCORD_science_center_desc", "Роль: исследования", "-0,42"),
            (
                "ADISCORD_industrial_cluster_desc",
                "Роль: местное военное производство",
                "+0,08",
            ),
        ):
            match = re.search(rf'(?m)^\s*{key}:\d*\s+"([^"]*)"', ECONOMY_LOC)
            self.assertIsNotNone(match, key)
            self.assertIn(role, match.group(1))
            self.assertIn(budget, match.group(1))

    def test_economic_building_reference_documents_roles_and_formulas(self):
        self.assertTrue(BUILDING_DOC.is_file())
        documentation = BUILDING_DOC.read_text(encoding="utf-8-sig")
        for required in (
            "Деловой центр",
            "Научный центр",
            "Промышленный кластер",
            "0.85 + 0.15 - 0.10 = +0.90",
            "0.05 - 0.35 - 0.12 = -0.42",
            "0.30 + 0.08 - 0.18 - 0.12 = +0.08",
            "5% × сумма(исправные военные заводы региона × уровень кластера)",
            "3 / 13",
        ):
            self.assertIn(required, documentation)

    def test_public_modifier_api_is_connected_localised_and_documented(self):
        modifier_keys = set(
            re.findall(
                r"(?m)^\s*(ADISCORD_(?:economy|country_development)_[A-Za-z0-9_]+)\s*=\s*\{",
                MODIFIER_DEFINITIONS,
            )
        )
        self.assertEqual(len(modifier_keys), 41)
        self.assertTrue(MODIFIER_DOC.is_file())
        documentation = MODIFIER_DOC.read_text(encoding="utf-8-sig")
        for key in modifier_keys:
            self.assertIn(f"modifier@{key}", MODIFIER_EFFECTS, key)
            self.assertRegex(MODIFIER_LOC, rf"(?m)^\s*{re.escape(key)}:\d*\s+")
            self.assertIn(f"`{key}`", documentation, key)

    def test_modifier_reference_is_focus_ready_and_has_no_retired_reserve_api(self):
        self.assertTrue(MODIFIER_DOC.is_file())
        documentation = MODIFIER_DOC.read_text(encoding="utf-8-sig")
        self.assertIn("ADISCORD_economy_resource_rent_income_factor = 0.15", documentation)
        self.assertIn("completion_reward", documentation)
        self.assertIn("add_ideas", documentation)
        self.assertIn("Безопасные диапазоны", documentation)
        for text in (MODIFIER_DEFINITIONS, MODIFIER_EFFECTS, MODIFIER_LOC, documentation):
            self.assertNotIn("reserve_growth", text)

    def test_pressure_and_bombing_modifier_outputs_have_real_consumers(self):
        budget_trend = block(EFFECTS, "ADISCORD_economy_update_monthly_budget_trend")
        compatibility_month = block(EFFECTS, "ADISCORD_economy_apply_monthly_balance")
        yearly = block(EFFECTS, "ADISCORD_economy_apply_yearly_balance")
        workforce = block(EFFECTS, "ADISCORD_economy_update_workforce_drain")
        bombing = block(EFFECTS, "ADISCORD_economy_update_bombing_disruption")
        self.assertIn("ADISCORD_economy_final_deficit_pressure_factor_bp", budget_trend)
        self.assertIn(
            "ADISCORD_economy_final_deficit_pressure_factor_bp",
            compatibility_month,
        )
        self.assertIn("ADISCORD_economy_final_deficit_pressure_factor_bp", yearly)
        self.assertIn(
            "ADISCORD_economy_final_demobilization_pressure_gain_factor_bp",
            workforce,
        )
        self.assertIn(
            "ADISCORD_economy_final_bombing_disruption_resistance_factor_bp",
            bombing,
        )


if __name__ == "__main__":
    unittest.main()
