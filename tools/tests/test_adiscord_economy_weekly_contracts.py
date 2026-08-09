import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_economy_ai import (
    ai_assistance_contract_issues,
    automatic_borrow_flow_issues,
    debt_notification_flow_issues,
    debt_reconciler_issues,
    debt_transition_flow_issues,
    migration_contract_issues,
    reachable_script_entries,
    research_policy_flow_issues,
    retired_capacity_boundary_issues,
    validate as validate_economy_ai,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


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
 ADISCORD_economy_ai_assistance_base = { modifier = { ADISCORD_economy_overall_income_factor = 0.05 industrial_capacity_factory = 0.05 } }
 ADISCORD_economy_ai_assistance_civil_war = { modifier = { supply_consumption_factor = -0.10 } }
 ADISCORD_economy_ai_assistance_retreat = { modifier = { army_defence_factor = 0.05 } }
} }
"""
    ASSISTANCE_EFFECT = """
ADISCORD_economy_refresh_ai_assistance = {
 remove_ideas = ADISCORD_economy_ai_assistance_base
 remove_ideas = ADISCORD_economy_ai_assistance_civil_war
 remove_ideas = ADISCORD_economy_ai_assistance_retreat
 if = {
  limit = { is_ai = yes }
  if = { limit = { check_variable = { var = ADISCORD_economy_simulation_tier value = 1 compare = greater_than_or_equals } } add_ideas = ADISCORD_economy_ai_assistance_base }
  if = { limit = { check_variable = { var = ADISCORD_vorkerland_collapse_phase value = 1 compare = greater_than_or_equals } has_war = yes } add_ideas = ADISCORD_economy_ai_assistance_civil_war }
  if = { limit = { check_variable = { var = surrender_progress value = 0.35 compare = greater_than } } add_ideas = ADISCORD_economy_ai_assistance_retreat }
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

    def test_ai_assistance_requires_remove_first_ai_gate_and_exact_conditions(self):
        self.assertEqual(
            ai_assistance_contract_issues(self.ASSISTANCE_IDEAS, self.ASSISTANCE_EFFECT),
            [],
        )
        nested_positive = self.ASSISTANCE_EFFECT.replace(
            "check_variable = { var = surrender_progress value = 0.35 compare = greater_than }",
            "OR = { AND = { check_variable = { var = surrender_progress value = 0.35 compare = greater_than } } AND = { always = no } }",
        )
        self.assertEqual(
            ai_assistance_contract_issues(self.ASSISTANCE_IDEAS, nested_positive),
            [],
        )
        mutations = (
            self.ASSISTANCE_EFFECT.replace(
                "  limit = { is_ai = yes }",
                "  limit = { always = yes }\n  is_ai = yes",
                1,
            ),
            self.ASSISTANCE_EFFECT.replace(
                " remove_ideas = ADISCORD_economy_ai_assistance_civil_war\n", "", 1
            ).replace(
                "add_ideas = ADISCORD_economy_ai_assistance_civil_war",
                "remove_ideas = ADISCORD_economy_ai_assistance_civil_war add_ideas = ADISCORD_economy_ai_assistance_civil_war",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "ADISCORD_vorkerland_collapse_phase", "surrender_progress", 1
            ).replace("var = surrender_progress value = 0.35", "var = ADISCORD_vorkerland_collapse_phase value = 1", 1),
            self.ASSISTANCE_EFFECT.replace(
                " remove_ideas = ADISCORD_economy_ai_assistance_retreat\n", "", 1
            ),
            self.ASSISTANCE_EFFECT.replace(
                "var = ADISCORD_economy_simulation_tier value = 1 compare = greater_than_or_equals",
                "var = ADISCORD_economy_simulation_tier value = 1 compare = less_than",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "var = ADISCORD_economy_simulation_tier value = 1",
                "var = ADISCORD_economy_simulation_tier value = 2",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "var = ADISCORD_vorkerland_collapse_phase value = 1 compare = greater_than_or_equals",
                "var = ADISCORD_vorkerland_collapse_phase value = 1 compare = less_than",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "var = ADISCORD_vorkerland_collapse_phase value = 1",
                "var = ADISCORD_vorkerland_collapse_phase value = 2",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "var = surrender_progress value = 0.35 compare = greater_than",
                "var = surrender_progress value = 0.35 compare = less_than",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "var = surrender_progress value = 0.35",
                "var = surrender_progress value = 0.50",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "limit = { is_ai = yes }",
                "limit = { is_ai = yes always = no }",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "var = surrender_progress value = 0.35 compare = greater_than } }",
                "var = surrender_progress value = 0.35 compare = greater_than } always = no }",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "check_variable = { var = surrender_progress value = 0.35 compare = greater_than }",
                "NOT = { check_variable = { var = surrender_progress value = 0.35 compare = greater_than } }",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "check_variable = { var = surrender_progress value = 0.35 compare = greater_than }",
                "check_variable = { var = surrender_progress value = 0.35 compare = greater_than } AND = { always = no }",
            ),
            self.ASSISTANCE_EFFECT.replace(
                "check_variable = { var = surrender_progress value = 0.35 compare = greater_than }",
                "OR = { AND = { check_variable = { var = surrender_progress value = 0.35 compare = greater_than } always = no } always = yes }",
            ),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertTrue(
                    ai_assistance_contract_issues(self.ASSISTANCE_IDEAS, mutation)
                )

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
  if = { limit = { check_variable = { var = ADISCORD_economy_debt_emergency_streak value = 4 compare = greater_than_or_equals } } set_variable = { var = ADISCORD_economy_debt_state value = 3 } }
 } else = { set_variable = { var = ADISCORD_economy_debt_emergency_streak value = 0 } }
 if = { limit = {
  check_variable = { var = ADISCORD_economy_interest_share_income value = 40 compare = greater_than_or_equals }
  check_variable = { var = ADISCORD_economy_weekly_balance value = 0 compare = less_than }
 } add_to_variable = { var = ADISCORD_economy_debt_default_streak value = 1 }
  if = { limit = { check_variable = { var = ADISCORD_economy_debt_default_streak value = 13 compare = greater_than_or_equals } } set_variable = { var = ADISCORD_economy_debt_state value = 4 } }
 } else = { set_variable = { var = ADISCORD_economy_debt_default_streak value = 0 } }
}
"""
        self.assertEqual(debt_transition_flow_issues(transition), [])
        self.assertTrue(debt_transition_flow_issues(transition.replace(
            "check_variable = { var = ADISCORD_economy_weekly_balance value = 0 compare = less_than }", "always = yes"
        )))
        self.assertTrue(debt_transition_flow_issues(transition.replace(
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
        )):
            with self.subTest(transition_mutation=index):
                self.assertTrue(debt_transition_flow_issues(invalid))

        notification = """
ADISCORD_economy_queue_debt_notification = { set_country_flag = queued }
ADISCORD_first_loan = { if = { limit = { NOT = { has_variable = ADISCORD_economy_first_loan_notified } } ADISCORD_economy_queue_debt_notification = yes } }
ADISCORD_transition = { if = { limit = { check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_last_notified_debt_state compare = greater_than } } ADISCORD_economy_queue_debt_notification = yes } }
"""
        self.assertEqual(debt_notification_flow_issues(notification), [])
        self.assertTrue(debt_notification_flow_issues(notification + "\nADISCORD_routine = { ADISCORD_economy_queue_debt_notification = yes }"))
        positive_first_loan = notification.replace(
            "NOT = { has_variable = ADISCORD_economy_first_loan_notified }",
            "has_variable = ADISCORD_economy_first_loan_notified",
        )
        self.assertTrue(debt_notification_flow_issues(positive_first_loan))
        double_negated = notification.replace(
            "NOT = { has_variable = ADISCORD_economy_first_loan_notified }",
            "NOT = { NOT = { has_variable = ADISCORD_economy_first_loan_notified } }",
        )
        self.assertTrue(debt_notification_flow_issues(double_negated))
        duplicate_queue = notification.replace(
            "ADISCORD_economy_queue_debt_notification = yes } }",
            "ADISCORD_economy_queue_debt_notification = yes ADISCORD_economy_queue_debt_notification = yes } }",
            1,
        )
        self.assertTrue(debt_notification_flow_issues(duplicate_queue))
        negated_upward = notification.replace(
            "check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_last_notified_debt_state compare = greater_than }",
            "NOT = { check_variable = { var = ADISCORD_economy_debt_state value = ADISCORD_economy_last_notified_debt_state compare = greater_than } }",
        )
        with self.subTest(mutation="negated upward notification"):
            self.assertTrue(debt_notification_flow_issues(negated_upward))

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
        }
        for name, invalid in mutations.items():
            with self.subTest(reconciler_mutation=name):
                self.assertNotEqual(invalid, reconciler)
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
        for activity_scalar in (
            "num_of_civilian_factories",
            "num_of_available_civilian_factories",
        ):
            self.assertIn(activity_scalar, construction)
        self.assertRegex(
            construction,
            r"subtract_from_variable\s*=\s*\{\s*var\s*=\s*ADISCORD_economy_active_construction_temp"
            r"\s+value\s*=\s*num_of_available_civilian_factories\s*\}",
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

    def test_live_construction_compatibility_localisation_describes_research_policy(self):
        budget_controls = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_budget_controls_tt"
        )
        self.assertIn("наук", budget_controls.lower())
        self.assertNotIn("строительств", budget_controls.lower())

        row = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_budget_construction_row"
        )
        self.assertIn("Наука", row)
        self.assertIn("[GetADISCORDConstructionSpendingModeLoc]", row)

        controls = localisation_value(
            ECONOMY_LOC, "ADISCORD_economy_construction_controls_tt"
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
                ECONOMY_LOC, f"ADISCORD_economy_construction_level_{level}_tt"
            )
            effect_tooltip = localisation_value(
                ECONOMY_LOC, f"ADISCORD_economy_construction_effects_{level}"
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
                ECONOMY_LOC, f"ADISCORD_economy_construction_funding_mode_{level}"
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
            "ADISCORD_economy_construction_decrease_tt",
            "ADISCORD_economy_construction_increase_tt",
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
        for direction in ("increase", "decrease"):
            construction = unique_block(
                SCRIPTED_GUI, f"ADISCORD_economy_construction_{direction}_click"
            )
            self.assertEqual(
                construction.strip(),
                f"ADISCORD_economy_{direction}_research_spending = yes",
            )

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
            "research": "ADISCORD_economy_construction_effects",
            "social": "ADISCORD_economy_social_effects",
        }
        for policy, localisation_prefix in effect_prefixes.items():
            for direction in ("Increase", "Decrease"):
                selector = unique_defined_text(
                    SCRIPTED_LOC,
                    f"GetADISCORDEconomy{policy.title()}{direction}PreviewLoc",
                )
                target = (
                    f"ADISCORD_economy_{policy}_{direction.lower()}_target_level"
                )
                self.assertEqual(selector.count(target), 4)
                for level in range(1, 6):
                    self.assertIn(f"{localisation_prefix}_{level}", selector)

        for direction in ("Increase", "Decrease"):
            compatibility = unique_defined_text(
                SCRIPTED_LOC,
                f"GetADISCORDConstruction{direction}PolicyPreviewLoc",
            )
            self.assertIn(
                f"ADISCORD_economy_research_{direction.lower()}_target_level",
                compatibility,
            )
            self.assertIn("ADISCORD_economy_construction_effects_5", compatibility)

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
        risk_clamp = (
            "clamp_variable = { var = ADISCORD_economy_debt_crisis_level min = 0 max = 4 }"
        )
        self.assertEqual(EFFECTS.count(risk_clamp), 2)
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
            "?ADISCORD_economy_debt_crisis_level|0",
            localisation_value(ECONOMY_LOC, "ADISCORD_economy_debt_tt"),
        )
        self.assertIn(
            "?ADISCORD_economy_debt_crisis_level|0]/4",
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
        self.assertFalse(debt_transition_flow_issues(EFFECTS))
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

    def test_debt_notifications_are_first_loan_and_upward_transitions_only(self):
        self.assertFalse(debt_notification_flow_issues(EFFECTS))
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

    def test_weekly_path_has_no_idea_query_building_recount_or_country_iteration(self):
        reachable = reachable_script_blocks(
            (EFFECTS, MODIFIER_EFFECTS, TRIGGERS),
            (
                "ADISCORD_economy_prepare_weekly_country",
                "ADISCORD_economy_light_update",
                "ADISCORD_economy_apply_weekly_balance",
            ),
        )
        forbidden_tokens = (
            "has_idea",
            "every_country",
            "any_country",
            "every_owned_state",
            "all_owned_state",
            "num_of_civilian_factories",
            "num_of_available_civilian_factories",
            "num_of_military_factories",
            "num_of_available_military_factories",
            "ADISCORD_economy_recount_economic_buildings",
            "ADISCORD_economy_full_refresh",
            "ADISCORD_economy_full_refresh_if_needed",
            "ADISCORD_economy_recalculate_policy_modifiers",
            "ADISCORD_economy_apply_visible_modifier_definition_factors",
            "ADISCORD_economy_refresh_spending_ideas",
            "ADISCORD_economy_update_gui",
        )
        offenders = {
            name: [token for token in forbidden_tokens if token in body]
            for name, body in reachable.items()
            if any(token in body for token in forbidden_tokens)
        }
        self.assertFalse(offenders, f"heavy weekly reachability: {offenders}")

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
        self.assertFalse(
            ai_assistance_contract_issues(minor_ideas, minor_effects + "\n" + EFFECTS)
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
        self.assertIn("ADISCORD_economy_migrate_schema = yes", prepare)
        for forbidden in (
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
        self.assertTrue(
            all("country_event =" not in body for body in reachable.values())
        )

        gui = (ROOT / "interface" / "ADISCORD_economy.gui").read_text(encoding="utf-8-sig")
        self.assertIn('name = "ADISCORD_economy_debt_notification_window"', gui)
        self.assertIn("ADISCORD_economy_debt_notification_script", SCRIPTED_GUI)
        for key in (
            "ADISCORD_economy_debt_notification_title",
            "ADISCORD_economy_debt_notification_desc",
            "ADISCORD_economy_debt_notification_ok",
        ):
            self.assertRegex(ECONOMY_LOC, rf"(?m)^\s*{re.escape(key)}:\d*\s+")
        self.assertIn("ADISCORD_economy_pending_debt_notification_amount", ECONOMY_LOC)

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
