"""Targeted structural validation for the Kefreyt rework."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig", errors="replace")


def named_blocks(text: str, key: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(key)}\s*=\s*\{{", text):
        depth = 0
        start = match.start()
        in_string = False
        escaped = False
        for index in range(match.end() - 1, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start : index + 1])
                    break
    return blocks


def mask_comments(text: str) -> str:
    """Mask Clausewitz comments while preserving source offsets and line breaks."""
    result: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for character in text:
        if in_comment:
            if character in "\r\n":
                in_comment = False
                result.append(character)
            else:
                result.append(" ")
            continue
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == "#":
            in_comment = True
            result.append(" ")
        else:
            result.append(character)
            if character == '"':
                in_string = True
    return "".join(result)


def mask_non_code(text: str) -> str:
    """Mask comments and strings while preserving source offsets and line breaks."""
    result: list[str] = []
    in_string = False
    escaped = False
    in_comment = False
    for character in text:
        if in_comment:
            if character in "\r\n":
                in_comment = False
                result.append(character)
            else:
                result.append(" ")
            continue
        if in_string:
            result.append(" " if character not in "\r\n" else character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == "#":
            in_comment = True
            result.append(" ")
        elif character == '"':
            in_string = True
            result.append(" ")
        else:
            result.append(character)
    return "".join(result)


def closing_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"unclosed brace at index {opening}")


@dataclass(frozen=True)
class Block:
    name: str
    start: int
    end: int
    text: str


def named_block_spans(text: str, name: str, offset: int = 0) -> list[Block]:
    masked = mask_non_code(text)
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*=\s*\{{")
    blocks: list[Block] = []
    for match in pattern.finditer(masked):
        opening = masked.index("{", match.start(), match.end())
        closing = closing_brace(masked, opening) + 1
        blocks.append(
            Block(
                name=name,
                start=offset + match.start(),
                end=offset + closing,
                text=text[match.start() : closing],
            )
        )
    return blocks


def brace_depth_before(text: str, position: int) -> int:
    return text[:position].count("{") - text[:position].count("}")


def direct_named_blocks(text: str, name: str, offset: int = 0) -> list[Block]:
    masked = mask_non_code(text)
    return [
        block
        for block in named_block_spans(text, name, offset)
        if brace_depth_before(masked, block.start - offset) == 1
    ]


def scalar_values(text: str, key: str) -> list[str]:
    return re.findall(
        rf"(?m)^\s*{re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\s*(?:#.*)?$",
        mask_comments(text),
    )


def assignment_values(text: str, key: str) -> list[str]:
    return re.findall(
        rf"\b{re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\b",
        mask_non_code(text),
    )


def assignment_names_at_depth(text: str, depth: int) -> list[str]:
    masked = mask_non_code(text)
    return [
        match.group(1)
        for match in re.finditer(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*=", masked)
        if brace_depth_before(masked, match.start()) == depth
    ]


def assignment_values_at_depth(text: str, key: str, depth: int) -> list[str]:
    masked = mask_non_code(text)
    return [
        match.group(1)
        for match in re.finditer(
            rf"(?<![A-Za-z0-9_]){re.escape(key)}\s*=\s*([A-Za-z0-9_]+)\b",
            masked,
        )
        if brace_depth_before(masked, match.start()) == depth
    ]


def main() -> int:
    issues: list[str] = []
    focus_text = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
    focuses = named_blocks(focus_text, "focus")
    if "relative_position_id" in focus_text:
        issues.append("focus layout still uses cascading relative coordinates")
    ids = {
        match.group(1)
        for block in focuses
        if (match := re.search(r"(?m)^\s*id\s*=\s*(VAL_[A-Za-z0-9_]+)", block))
    }
    required = {
        "VAL_Operational_Directorate",
        "VAL_Ministry_Of_Contract_Memory",
        "VAL_Quarterly_Contract_Norm",
        "VAL_Arsenal_Reserve",
        "VAL_Contract_General_Staff",
        "VAL_State_Above_Captains",
        "VAL_Westerholm_Concessions",
        "VAL_Vorkerland_Contracts_Burn",
        "VAL_Look_To_Stelander",
        "VAL_The_Passes_Are_Open",
        "VAL_State_Contract",
        "VAL_Industrial_Mobilization_Plan",
        "VAL_Army_Of_The_Ledger",
        "VAL_Wireless_Contract_Bureau",
        "VAL_Two_Concurrent_Narratives",
        "VAL_Logistics_Command",
    }
    for missing in sorted(required - ids):
        issues.append(f"missing focus {missing}")
    if len(focuses) < 75:
        issues.append(f"focus tree is still too small ({len(focuses)} focuses)")
    for block in focuses:
        focus_id = re.search(r"(?m)^\s*id\s*=\s*(\S+)", block)
        cost = re.search(r"(?m)^\s*cost\s*=\s*(\d+)", block)
        if not cost:
            issues.append(f"{focus_id.group(1) if focus_id else 'unknown focus'} has no cost")
        elif int(cost.group(1)) > 5:
            issues.append(f"{focus_id.group(1) if focus_id else 'unknown focus'} exceeds 35 days")
        for forbidden in ("army_experience", "add_command_power", "add_political_power"):
            if forbidden in block:
                issues.append(
                    f"{focus_id.group(1) if focus_id else 'unknown focus'} uses filler reward {forbidden}"
                )

    focus_blocks = {
        match.group(1): block
        for block in focuses
        if (match := re.search(r"(?m)^\s*id\s*=\s*(VAL_[A-Za-z0-9_]+)", block))
    }
    exclusive_pairs: set[frozenset[str]] = set()
    for focus_id, block in focus_blocks.items():
        exclusive = named_blocks(block, "mutually_exclusive")
        if not exclusive:
            continue
        for rival in re.findall(r"\bfocus\s*=\s*(VAL_[A-Za-z0-9_]+)", exclusive[0]):
            exclusive_pairs.add(frozenset((focus_id, rival)))
    for focus_id, block in focus_blocks.items():
        prerequisites = named_blocks(block, "prerequisite")
        prerequisite_groups = [
            set(re.findall(r"\bfocus\s*=\s*(VAL_[A-Za-z0-9_]+)", prerequisite))
            for prerequisite in prerequisites
        ]
        for pair in exclusive_pairs:
            if len(pair) != 2:
                continue
            if all(any(member in group for group in prerequisite_groups) for member in pair):
                if not any(pair.issubset(group) for group in prerequisite_groups):
                    issues.append(
                        f"{focus_id} requires mutually exclusive focuses in separate prerequisite blocks"
                    )

    prerequisite_groups = {
        focus_id: [
            re.findall(r"\bfocus\s*=\s*(VAL_[A-Za-z0-9_]+)", prerequisite)
            for prerequisite in named_blocks(block, "prerequisite")
        ]
        for focus_id, block in focus_blocks.items()
    }
    viable_cache: dict[str, list[frozenset[str]]] = {}
    visiting: set[str] = set()

    def viable_paths(focus_id: str) -> list[frozenset[str]]:
        if focus_id in viable_cache:
            return viable_cache[focus_id]
        if focus_id in visiting:
            return []
        visiting.add(focus_id)
        candidates = [frozenset((focus_id,))]
        for prerequisite_group in prerequisite_groups[focus_id]:
            alternatives = [
                path
                for prerequisite_id in prerequisite_group
                if prerequisite_id in focus_blocks
                for path in viable_paths(prerequisite_id)
            ]
            candidates = [
                current | alternative
                for current in candidates
                for alternative in alternatives
                if not any(pair <= current | alternative for pair in exclusive_pairs)
            ]
            minimal: list[frozenset[str]] = []
            for candidate in sorted(set(candidates), key=len):
                if not any(existing <= candidate for existing in minimal):
                    minimal.append(candidate)
            candidates = minimal
        visiting.remove(focus_id)
        viable_cache[focus_id] = candidates
        return candidates

    for focus_id in focus_blocks:
        if not viable_paths(focus_id):
            issues.append(f"{focus_id} has no completable prerequisite path")

    final_join = focus_blocks.get("VAL_Contracts_Outlive_Kings", "")
    for terminal in (
        "VAL_State_Contract",
        "VAL_Industrial_Mobilization_Plan",
        "VAL_Army_Of_The_Ledger",
    ):
        if not re.search(
            rf"prerequisite\s*=\s*\{{\s*focus\s*=\s*{terminal}\s*\}}",
            final_join,
        ):
            issues.append(f"final branch join is missing {terminal}")
    final_invoice = focus_blocks.get("VAL_Present_The_Final_Invoice", "")
    invoice_prerequisites = named_blocks(final_invoice, "prerequisite")
    if len(invoice_prerequisites) != 1 or len(
        re.findall(r"\bfocus\s*=\s*VAL_(?:Offer|Secure|Negotiate|Let)_[A-Za-z0-9_]+", invoice_prerequisites[0])
    ) != 4:
        issues.append("final invoice must accept any one of the four crisis strategies")

    coordinates: dict[str, tuple[int, int, str | None]] = {}
    for block in focuses:
        focus_id = re.search(r"(?m)^\s*id\s*=\s*(\S+)", block)
        x = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)", block)
        y = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)", block)
        relative = re.search(r"(?m)^\s*relative_position_id\s*=\s*(\S+)", block)
        if focus_id and x and y:
            coordinates[focus_id.group(1)] = (
                int(x.group(1)),
                int(y.group(1)),
                relative.group(1) if relative else None,
            )

    resolved: dict[str, tuple[int, int]] = {}

    def resolve(focus_id: str) -> tuple[int, int]:
        if focus_id in resolved:
            return resolved[focus_id]
        x, y, relative = coordinates[focus_id]
        if relative:
            parent_x, parent_y = resolve(relative)
            x, y = x + parent_x, y + parent_y
        resolved[focus_id] = (x, y)
        return x, y

    occupied: dict[tuple[int, int], list[str]] = {}
    for focus_id in coordinates:
        occupied.setdefault(resolve(focus_id), []).append(focus_id)
    for position, focus_ids in occupied.items():
        if len(focus_ids) > 1:
            issues.append(f"focus coordinate collision at {position}: {', '.join(focus_ids)}")
    if resolved:
        xs = [position[0] for position in resolved.values()]
        if max(xs) - min(xs) < 24:
            issues.append("focus tree is not wide enough to separate its main branches")
        final_position = resolved.get("VAL_Contracts_Outlive_Kings")
        terminal_positions = [
            resolved.get(terminal)
            for terminal in (
                "VAL_State_Contract",
                "VAL_Industrial_Mobilization_Plan",
                "VAL_Army_Of_The_Ledger",
            )
        ]
        if final_position and all(terminal_positions):
            if final_position[1] <= max(position[1] for position in terminal_positions if position):
                issues.append("final branch join is drawn above a required branch ending")
            terminal_rows = {position[1] for position in terminal_positions if position}
            if len(terminal_rows) != 1:
                issues.append("political, industrial and army branch endings are not aligned")
        strategy_positions = [
            resolved.get(strategy)
            for strategy in (
                "VAL_Offer_The_Mountain_Contract",
                "VAL_Secure_The_Resource_Corridor",
                "VAL_Negotiate_The_Deferred_Invoice",
                "VAL_Let_Nodrul_Bleed",
            )
        ]
        if all(strategy_positions):
            strategy_rows = {position[1] for position in strategy_positions if position}
            if len(strategy_rows) != 1:
                issues.append("the four final crisis alternatives are not aligned")

    for focus_id in ("VAL_Westerholm_Concessions", "VAL_Vorkerland_Contracts_Burn", "VAL_The_Passes_Are_Open"):
        block = next((block for block in focuses if f"id = {focus_id}" in block), "")
        if "allow_branch" not in block:
            issues.append(f"{focus_id} is not world-reactive")

    shared_effects = read("common/scripted_effects/ADISCORD_shared_action_effects.txt")
    shared_triggers = read("common/scripted_triggers/ADISCORD_shared_action_triggers.txt")
    if "VAL_" in shared_effects or "VAL_" in shared_triggers:
        issues.append("shared action API contains Kefreyt-specific content")
    for token in (
        "ADISCORD_economy_spend_25",
        "ADISCORD_economy_spend_50",
        "ADISCORD_economy_receive_15",
        "ADISCORD_economy_receive_50",
        "ADISCORD_campaign_slot_consume",
        "ADISCORD_campaign_slot_release",
    ):
        if token not in shared_effects:
            issues.append(f"shared action API is missing {token}")

    decisions = read("common/decisions/ADISCORD_VAL_rework_decisions.txt")
    for token in (
        "days_mission_timeout = 90",
        "amount = -2500",
        "amount = -5000",
        "VAL_resolve_quarterly_contract_norm = yes",
        "ADISCORD_has_campaign_slot = yes",
    ):
        if token not in decisions:
            issues.append(f"decision system is missing {token}")
    if re.search(r"ADISCORD_economy_treasury\s+value\s*=", decisions):
        issues.append("Kefreyt decisions bypass the shared treasury API")
    for debug_decision in (
        "VAL_debug_initialize_systems",
        "VAL_debug_unlock_operations_map",
        "VAL_debug_set_crisis_rupture",
        "VAL_debug_set_active_civil_war",
        "VAL_debug_set_postwar_stelander",
        "VAL_debug_disrupt_vorkerland_contracts",
        "VAL_debug_reputation_maximum",
        "VAL_debug_reputation_minimum",
        "VAL_debug_grant_contract_reserves",
        "VAL_debug_reset_rework_state",
    ):
        if not named_blocks(decisions, debug_decision):
            issues.append(f"missing debug decision {debug_decision}")
    categories = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
    debug_category = named_blocks(categories, "VAL_rework_debug")
    if not debug_category or "is_debug = yes" not in debug_category[0]:
        issues.append("Kefreyt debug category is not gated by debug mode")

    legacy_decisions = read("common/decisions/ADISCORD_VAL_contract_decisions.txt")
    service_decisions = {
        "VAL_resource_corridor_control_30",
        "VAL_STP_adviser_factory_obligation",
        "VAL_STP_arms_debt_day_30",
        "VAL_STP_arms_debt_day_90",
        "VAL_STP_arms_debt_day_150",
        "VAL_northern_campaign_timeout_210",
        "STP_VAL_war_countdown_120",
        "STP_VAL_war_countdown_180",
        "STP_VAL_war_countdown_300",
        "STP_VAL_war_countdown_450",
        "STP_VAL_war_countdown_breached",
    }
    legacy_children = set(
        re.findall(r"(?m)^\t([A-Z][A-Za-z0-9_]+)\s*=\s*\{", legacy_decisions)
    )
    for obsolete in sorted(legacy_children - service_decisions):
        issues.append(f"obsolete player-facing legacy decision remains: {obsolete}")
    compatibility_mission = named_blocks(legacy_decisions, "VAL_resource_corridor_control_30")
    if compatibility_mission and "visible = { always = no }" not in " ".join(
        compatibility_mission[0].split()
    ):
        issues.append("legacy resource-corridor mission is not hidden")
    for obsolete_path in (
        "common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt",
        "interface/ADISCORD_STP_VAL_crisis.gui",
    ):
        if (ROOT / obsolete_path).exists():
            issues.append(f"obsolete legacy panel still exists: {obsolete_path}")

    operational_focus = focus_blocks.get("VAL_Operational_Directorate", "")
    if "set_country_flag = VAL_operations_map_unlocked" not in operational_focus:
        issues.append("Operational Directorate does not unlock the operations map")
    map_category = named_blocks(categories, "VAL_military_operations")
    if not map_category:
        issues.append("operations-map decision category is missing")
    else:
        for token in (
            "has_country_flag = VAL_operations_map_unlocked",
            "visible_when_empty = yes",
            "scripted_gui = ADISCORD_VAL_operations_panel",
        ):
            if token not in map_category[0]:
                issues.append(f"operations-map category is missing {token}")
    for decision_id in (
        "VAL_ops_finance_cin_contacts",
        "VAL_ops_sell_rifles_to_cin",
        "VAL_ops_finance_osf_contacts",
        "VAL_ops_sell_rifles_to_osf",
    ):
        block = named_blocks(decisions, decision_id)
        if not block or "has_country_flag = VAL_northern_operations_unlocked" not in block[0]:
            issues.append(f"{decision_id} is not gated by its world-reactive focus")

    effects = read("common/scripted_effects/ADISCORD_VAL_rework_effects.txt")
    for token in (
        "amount = -4000",
        "VAL_contract_reputation_level",
        "VAL_vorkerland_contract_disruptions",
        "give_resource_rights = { receiver = VAL state = 202 }",
        "remove_resource_rights = 202",
        "give_resource_rights = { receiver = VAL state = 45 }",
    ):
        if token not in effects:
            issues.append(f"rework effects are missing {token}")
    initialize = named_blocks(effects, "VAL_initialize_rework")
    if not initialize or "set_country_flag = VAL_operations_map_unlocked" not in initialize[0]:
        issues.append("rework initialization does not migrate the operations-map unlock")

    tier_families = {
        "administration": tuple(f"VAL_contract_administration_{tier}" for tier in range(1, 4)),
        "industry": tuple(f"VAL_contract_industry_{tier}" for tier in range(1, 4)),
        "army": tuple(f"VAL_contract_army_{tier}" for tier in range(1, 4)),
        "reputation": tuple(f"VAL_contract_reputation_{tier}" for tier in range(4)),
    }
    level_variables = {
        "administration": "VAL_contract_administration_level",
        "industry": "VAL_contract_industry_level",
        "army": "VAL_contract_army_level",
    }
    authoritative_level_variables = {
        *level_variables.values(),
        "VAL_contract_reputation_level",
    }
    used_contract_level_variables = set(
        re.findall(
            r"\bvar\s*=\s*(VAL_contract_[A-Za-z0-9_]*level)\b",
            mask_comments(effects),
        )
    )
    if used_contract_level_variables != authoritative_level_variables:
        issues.append(
            "contract tier effects do not use exactly the authoritative level variables: "
            + ", ".join(sorted(used_contract_level_variables))
        )
    for family, expected_variable in {
        **level_variables,
        "reputation": "VAL_contract_reputation_level",
    }.items():
        family_variables = set(
            re.findall(
                rf"\bvar\s*=\s*(VAL_contract_{family}_[A-Za-z0-9_]+)\b",
                mask_comments(effects),
            )
        )
        if family_variables != {expected_variable}:
            issues.append(
                f"{family} contract state must use only {expected_variable}: "
                + ", ".join(sorted(family_variables))
            )

    def validate_hidden_renderer(
        owner: str,
        container: str,
        family: str,
        target: str,
    ) -> str | None:
        hidden_blocks = direct_named_blocks(container, "hidden_effect")
        if len(hidden_blocks) != 1:
            issues.append(f"{owner} needs exactly one direct hidden_effect renderer")
            return None
        hidden = hidden_blocks[0].text
        expected_ideas = set(tier_families[family])
        removals = assignment_values_at_depth(hidden, "remove_ideas", 1)
        additions = assignment_values_at_depth(hidden, "add_ideas", 1)
        if (
            len(removals) != len(expected_ideas)
            or set(removals) != expected_ideas
            or assignment_values_at_depth(hidden, "remove_idea", 1)
        ):
            issues.append(
                f"{owner} does not directly remove every {family} tier exactly once"
            )
        if additions != [target] or assignment_values_at_depth(hidden, "add_idea", 1):
            issues.append(f"{owner} does not directly add only target tier {target}")
        idea_commands = {"add_idea", "add_ideas", "remove_idea", "remove_ideas", "swap_ideas"}
        direct_idea_commands = [
            name for name in assignment_names_at_depth(hidden, 1) if name in idea_commands
        ]
        expected_direct_commands = ["remove_ideas"] * len(expected_ideas) + ["add_ideas"]
        if direct_idea_commands != expected_direct_commands:
            issues.append(f"{owner} has an invalid direct idea-render command sequence")
        masked_hidden = mask_non_code(hidden)
        nested_idea_commands = [
            match.group(1)
            for match in re.finditer(
                r"(?<![A-Za-z0-9_])(add_idea|add_ideas|remove_idea|remove_ideas|swap_ideas)\s*=",
                masked_hidden,
            )
            if brace_depth_before(masked_hidden, match.start()) > 1
        ]
        if nested_idea_commands:
            issues.append(f"{owner} nests idea rendering below hidden_effect direct depth")
        removal_positions = [
            match.start()
            for match in re.finditer(r"(?m)^\s*remove_ideas\s*=", mask_comments(hidden))
            if brace_depth_before(masked_hidden, match.start()) == 1
        ]
        addition_positions = [
            match.start()
            for match in re.finditer(r"(?m)^\s*add_ideas\s*=", mask_comments(hidden))
            if brace_depth_before(masked_hidden, match.start()) == 1
        ]
        if removal_positions and addition_positions and max(removal_positions) > min(addition_positions):
            issues.append(f"{owner} adds {target} before completing its remove-all render")
        return hidden

    for family in ("administration", "industry", "army"):
        variable = level_variables[family]
        for tier, target in enumerate(tier_families[family], start=1):
            effect_id = f"VAL_apply_contract_{family}_{tier}"
            effect_blocks = named_block_spans(effects, effect_id)
            if len(effect_blocks) != 1:
                issues.append(f"expected exactly one tier effect {effect_id}")
                continue
            effect_block = effect_blocks[0].text
            engine_effect = mask_comments(effect_block)
            if re.search(r"\b(?:has_idea|swap_ideas)\s*=", engine_effect):
                issues.append(f"{effect_id} still derives transitions from idea state")
            branches = direct_named_blocks(effect_block, "if")
            if len(branches) != 1 or direct_named_blocks(effect_block, "else_if"):
                issues.append(f"{effect_id} needs one direct guarded transition branch")
                continue
            branch = branches[0]
            limits = direct_named_blocks(branch.text, "limit", branch.start)
            setters = direct_named_blocks(branch.text, "set_variable", branch.start)
            hidden_blocks = direct_named_blocks(branch.text, "hidden_effect", branch.start)
            if len(limits) != 1 or len(setters) != 1 or len(hidden_blocks) != 1:
                issues.append(
                    f"{effect_id} must directly contain one limit, level setter, and hidden renderer"
                )
                continue
            limit = limits[0]
            guards = direct_named_blocks(limit.text, "OR", limit.start)
            if len(guards) != 1:
                issues.append(f"{effect_id} needs one direct OR level guard")
            else:
                guard = guards[0]
                missing_checks = direct_named_blocks(guard.text, "NOT", guard.start)
                level_checks = direct_named_blocks(guard.text, "check_variable", guard.start)
                guard_operands = assignment_names_at_depth(guard.text, 1)
                if len(guard_operands) != 2 or set(guard_operands) != {
                    "NOT",
                    "check_variable",
                }:
                    issues.append(
                        f"{effect_id} OR guard must contain only missing-variable and less-than checks"
                    )
                if (
                    len(missing_checks) != 1
                    or assignment_values(missing_checks[0].text, "has_variable") != [variable]
                    or assignment_names_at_depth(missing_checks[0].text, 1)
                    != ["has_variable"]
                ):
                    issues.append(f"{effect_id} does not guard the missing {variable}")
                if len(level_checks) != 1 or (
                    scalar_values(level_checks[0].text, "var") != [variable]
                    or scalar_values(level_checks[0].text, "value") != [str(tier)]
                    or scalar_values(level_checks[0].text, "compare") != ["less_than"]
                    or assignment_names_at_depth(level_checks[0].text, 1)
                    != ["var", "value", "compare"]
                ):
                    issues.append(f"{effect_id} does not guard {variable} as less than {tier}")
            setter = setters[0].text
            if not re.search(
                rf"\bvar\s*=\s*{re.escape(variable)}\b.*?\bvalue\s*=\s*{tier}\b",
                mask_comments(setter),
                re.DOTALL,
            ):
                issues.append(f"{effect_id} does not set {variable} to {tier}")
            hidden = validate_hidden_renderer(effect_id, branch.text, family, target)
            all_removals = scalar_values(effect_block, "remove_ideas")
            all_additions = scalar_values(effect_block, "add_ideas")
            if hidden is not None and (
                all_removals != scalar_values(hidden, "remove_ideas")
                or all_additions != scalar_values(hidden, "add_ideas")
            ):
                issues.append(f"{effect_id} renders tier ideas outside hidden_effect")
            dirty_calls = scalar_values(hidden or "", "ADISCORD_economy_mark_dirty")
            if family in {"administration", "industry"} and dirty_calls != ["yes"]:
                issues.append(f"{effect_id} must mark the economy dirty inside its renderer")
            if family == "army" and dirty_calls:
                issues.append(f"{effect_id} must not mark the economy dirty")

    reputation_refresh = named_block_spans(effects, "VAL_refresh_contract_reputation")
    if len(reputation_refresh) != 1:
        issues.append("expected exactly one reputation refresh selector")
    else:
        refresh = reputation_refresh[0].text
        conditional_branches = sorted(
            [
                *direct_named_blocks(refresh, "if"),
                *direct_named_blocks(refresh, "else_if"),
            ],
            key=lambda branch: branch.start,
        )
        if [branch.name for branch in conditional_branches] != ["if", "else_if", "else_if"]:
            issues.append("reputation refresh must select tiers 3, 2, and 1 in descending order")
        else:
            for tier, branch in zip((3, 2, 1), conditional_branches):
                limits = direct_named_blocks(branch.text, "limit", branch.start)
                checks = (
                    direct_named_blocks(limits[0].text, "check_variable", limits[0].start)
                    if len(limits) == 1
                    else []
                )
                if len(checks) != 1 or (
                    assignment_values(checks[0].text, "var")
                    != ["VAL_contract_reputation_level"]
                    or assignment_values(checks[0].text, "value") != [str(tier)]
                    or assignment_values(checks[0].text, "compare")
                    != ["greater_than_or_equals"]
                ):
                    issues.append(f"reputation refresh has an invalid tier {tier} level check")
                effect_id = f"VAL_apply_contract_reputation_{tier}"
                renderer_calls = re.findall(
                    r"\bVAL_apply_contract_reputation_([0-3])\s*=\s*yes\b",
                    mask_comments(branch.text),
                )
                if renderer_calls != [str(tier)]:
                    issues.append(f"reputation refresh tier {tier} does not call only {effect_id}")
        fallback = direct_named_blocks(refresh, "else")
        fallback_calls = re.findall(
            r"\bVAL_apply_contract_reputation_([0-3])\s*=\s*yes\b",
            mask_comments(fallback[0].text if fallback else ""),
        )
        if len(fallback) != 1 or fallback_calls != ["0"]:
            issues.append("reputation refresh needs an unconditional tier-0 fallback")
        elif named_block_spans(fallback[0].text, "check_variable"):
            issues.append("reputation tier-0 fallback must not have a level guard")
    for level in range(4):
        effect_id = f"VAL_apply_contract_reputation_{level}"
        effect_blocks = named_block_spans(effects, effect_id)
        if len(effect_blocks) != 1:
            issues.append(f"expected exactly one reputation renderer {effect_id}")
            continue
        effect_block = effect_blocks[0].text
        if re.search(r"\b(?:has_idea|swap_ideas)\s*=", mask_comments(effect_block)):
            issues.append(f"{effect_id} still derives rendering from idea state")
        target = tier_families["reputation"][level]
        hidden = validate_hidden_renderer(effect_id, effect_block, "reputation", target)
        if hidden is not None and (
            scalar_values(effect_block, "remove_ideas")
            != scalar_values(hidden, "remove_ideas")
            or scalar_values(effect_block, "add_ideas")
            != scalar_values(hidden, "add_ideas")
        ):
            issues.append(f"{effect_id} renders reputation ideas outside hidden_effect")

    migration_focuses = {
        ("administration", 3): {"VAL_State_Contract"},
        ("administration", 2): {
            "VAL_Central_Payment_Office",
            "VAL_Provincial_Contract_Courts",
        },
        ("administration", 1): {
            "VAL_The_Weaponry_Baron",
            "VAL_Provincial_Brokers",
            "VAL_Ministry_Auditors",
        },
        ("industry", 3): {"VAL_Industrial_Mobilization_Plan"},
        ("industry", 2): {
            "VAL_Standardize_Rifle_Lots",
            "VAL_Standard_Cartridges",
            "VAL_Three_Shift_Arsenals",
        },
        ("industry", 1): {
            "VAL_Contract_Accounting_Office",
            "VAL_Munitions_Board",
        },
        ("army", 3): {"VAL_Contract_General_Staff", "VAL_Army_Of_The_Ledger"},
        ("army", 2): {
            "VAL_Contractor_Officers",
            "VAL_Motorized_Columns",
            "VAL_Field_Repair_Corps",
            "VAL_Contract_NCO_Schools",
            "VAL_Logistics_Command",
        },
        ("army", 1): {
            "VAL_Count_The_Captains",
            "VAL_The_Mercenary_State",
            "VAL_Company_Rosters",
            "VAL_Border_Survey_Corps",
            "VAL_Company_Service_Code",
        },
    }
    migration_blocks = named_block_spans(effects, "VAL_migrate_contract_tier_levels")
    if len(migration_blocks) != 1:
        issues.append("expected exactly one VAL_migrate_contract_tier_levels effect")
    else:
        migration = migration_blocks[0].text
        migration_branches = sorted(
            [
                *direct_named_blocks(migration, "if"),
                *direct_named_blocks(migration, "else_if"),
            ],
            key=lambda branch: branch.start,
        )
        expected_branches = [
            (family, tier, "if" if tier == 3 else "else_if")
            for family in ("administration", "industry", "army")
            for tier in (3, 2, 1)
        ]
        if len(migration_branches) != len(expected_branches):
            issues.append("tier migration must have one descending three-branch chain per family")
        else:
            for branch, (family, tier, branch_name) in zip(
                migration_branches, expected_branches
            ):
                effect_id = f"VAL_apply_contract_{family}_{tier}"
                if branch.name != branch_name:
                    issues.append(f"{effect_id} migration branch is out of descending order")
                apply_calls = re.findall(
                    r"(?m)^\s*(VAL_apply_contract_(?:administration|industry|army)_[1-3])\s*=\s*yes\s*$",
                    mask_comments(branch.text),
                )
                if apply_calls != [effect_id]:
                    issues.append(f"migration branch must call only {effect_id}")
                limits = direct_named_blocks(branch.text, "limit", branch.start)
                if len(limits) != 1:
                    issues.append(f"{effect_id} migration branch needs one direct limit")
                    continue
                limit = limits[0]
                missing = direct_named_blocks(limit.text, "NOT", limit.start)
                variable = level_variables[family]
                if (
                    len(missing) != 1
                    or assignment_values(missing[0].text, "has_variable") != [variable]
                    or assignment_names_at_depth(missing[0].text, 1)
                    != ["has_variable"]
                ):
                    issues.append(f"{effect_id} migration must require missing {variable}")
                expected_focuses = migration_focuses[(family, tier)]
                limit_operands = assignment_names_at_depth(limit.text, 1)
                if len(expected_focuses) == 1:
                    direct_focuses = assignment_values_at_depth(
                        limit.text, "has_completed_focus", 1
                    )
                    if (
                        len(limit_operands) != 2
                        or set(limit_operands) != {"NOT", "has_completed_focus"}
                        or direct_focuses != list(expected_focuses)
                    ):
                        issues.append(
                            f"{effect_id} migration must directly check its single caller focus"
                        )
                else:
                    alternatives = direct_named_blocks(limit.text, "OR", limit.start)
                    if (
                        len(limit_operands) != 2
                        or set(limit_operands) != {"NOT", "OR"}
                        or len(alternatives) != 1
                    ):
                        issues.append(
                            f"{effect_id} migration must combine caller focuses in one direct OR"
                        )
                    else:
                        alternative_operands = assignment_names_at_depth(
                            alternatives[0].text, 1
                        )
                        alternative_focuses = assignment_values_at_depth(
                            alternatives[0].text, "has_completed_focus", 1
                        )
                        if (
                            alternative_operands
                            != ["has_completed_focus"] * len(expected_focuses)
                            or len(alternative_focuses) != len(expected_focuses)
                            or set(alternative_focuses) != expected_focuses
                        ):
                            issues.append(
                                f"{effect_id} migration OR alternatives do not exactly cover callers"
                            )

    if not initialize or not re.search(
        r"VAL_initialize_rework\s*=\s*\{\s*VAL_migrate_contract_tier_levels\s*=\s*yes\b",
        mask_comments(initialize[0]),
    ):
        issues.append("VAL_initialize_rework does not begin with tier-level migration")

    ideas_text = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
    hidden_ideas = named_blocks(ideas_text, "hidden_ideas")
    if not hidden_ideas:
        issues.append("Kefreyt has no hidden-idea layer for technical bonuses")
    else:
        for idea_id in (
            "VAL_contract_reputation_0",
            "VAL_contract_reputation_1",
            "VAL_contract_reputation_2",
            "VAL_contract_reputation_3",
            "VAL_contract_administration_1",
            "VAL_contract_administration_2",
            "VAL_contract_administration_3",
            "VAL_contract_industry_1",
            "VAL_contract_industry_2",
            "VAL_contract_industry_3",
            "VAL_contract_army_1",
            "VAL_contract_army_2",
            "VAL_contract_army_3",
            "VAL_contract_propaganda_office",
            "VAL_factory_cathedrals_drive",
            "VAL_hot_production_lines",
            "VAL_northern_roads_drive",
        ):
            declarations = named_blocks(hidden_ideas[0], idea_id)
            if len(declarations) != 1:
                issues.append(f"technical idea must be declared once under hidden_ideas: {idea_id}")

    for ideas_path in (
        "common/ideas/ADISCORD_VAL_rework_ideas.txt",
        "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt",
    ):
        ideas_text = read(ideas_path)
        for idea_id in sorted(set(re.findall(r"(?m)^\s*(VAL_[A-Za-z0-9_]+)\s*=\s*\{", ideas_text))):
            idea_blocks = named_blocks(ideas_text, idea_id)
            if idea_blocks and not re.search(r"(?m)^\s*picture\s*=", idea_blocks[0]):
                issues.append(f"idea {idea_id} has no picture")

    state_202 = read("history/states/202-202.txt")
    if not re.search(r"resources\s*=\s*\{[^}]*steel\s*=\s*16", state_202, re.S):
        issues.append("state 202 does not contain the baseline Westerholm steel deposit")
    collapse_events = read("events/ADISCORD_vorkerland_collapse_events.txt")
    if "VAL_handle_vorkerland_war_outbreak = yes" not in collapse_events:
        issues.append("Vorkerland war start does not disrupt Kefreyt contracts")

    gfx = read("interface/ADISCORD_VAL_operations.gfx")
    gui = read("interface/ADISCORD_VAL_operations.gui")
    scripted_gui = read("common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt")
    panel = named_blocks(scripted_gui, "ADISCORD_VAL_operations_panel")
    if not panel:
        issues.append("operations scripted-GUI panel is missing")
    else:
        for token in (
            "context_type = decision_category",
            'window_name = "ADISCORD_VAL_operations_panel_window"',
            "visible = { always = yes }",
        ):
            if token not in " ".join(panel[0].split()):
                issues.append(f"operations scripted-GUI panel is missing {token}")
    for state in (43, 44, 45, 88, 59, 61):
        path = ROOT / f"gfx/interface/VAL_operations/VAL_ops_state_{state}.png"
        if not path.exists():
            issues.append(f"missing operations overlay for state {state}")
            continue
        with Image.open(path) as image:
            if image.size != (2100, 260):
                issues.append(f"state {state} overlay has size {image.size}, expected 2100x260")
        for text, label in ((gfx, "GFX"), (gui, "GUI"), (scripted_gui, "scripted GUI")):
            if f"{state}" not in text:
                issues.append(f"state {state} is missing from operations {label}")
    background = ROOT / "gfx/interface/VAL_operations/VAL_ops_map_background.png"
    if not background.exists():
        issues.append("missing operations-map background")
    else:
        with Image.open(background) as image:
            if image.size != (420, 260):
                issues.append(f"operations background has size {image.size}, expected 420x260")

    localization_path = ROOT / "localisation/russian/ADISCORD_VAL_rework_l_russian.yml"
    if not localization_path.read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian rework localisation is missing its UTF-8 BOM")
    localization = read("localisation/russian/ADISCORD_VAL_rework_l_russian.yml")
    for key in (*required, "VAL_quarterly_contract_deadline", "VAL_operations_map_tt"):
        if not re.search(rf"(?m)^\s*{re.escape(key)}:", localization):
            issues.append(f"missing Russian localisation {key}")

    all_russian_localization = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="replace")
        for path in (ROOT / "localisation/russian").glob("*.yml")
    )
    for focus_id in sorted(ids):
        for key in (focus_id, f"{focus_id}_desc"):
            if not re.search(rf"(?m)^\s*{re.escape(key)}:", all_russian_localization):
                issues.append(f"missing Russian localisation {key}")
    for key in (
        "VAL_rework_debug",
        "VAL_debug_initialize_systems",
        "VAL_debug_unlock_operations_map",
        "VAL_debug_set_crisis_rupture",
        "VAL_debug_set_active_civil_war",
        "VAL_debug_set_postwar_stelander",
        "VAL_debug_disrupt_vorkerland_contracts",
        "VAL_debug_lose_westerholm_metal",
        "VAL_debug_reputation_maximum",
        "VAL_debug_reputation_minimum",
        "VAL_debug_grant_contract_reserves",
        "VAL_debug_reset_rework_state",
        "ADISCORD_cost_t25",
        "ADISCORD_cost_r2500",
        "ADISCORD_cost_t50_r5000",
        "ADISCORD_cost_r4000",
    ):
        if not re.search(rf"(?m)^\s*{re.escape(key)}:", all_russian_localization):
            issues.append(f"missing Russian localisation {key}")

    if issues:
        print("Kefreyt rework validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"Kefreyt rework validation passed ({len(focuses)} focuses, 6 dynamic map regions).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
