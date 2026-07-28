"""Targeted structural validation for the Kefreyt rework."""

from __future__ import annotations

import re
import sys
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
        "has_campaign_slot = yes",
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
    for effect_id in (
        "VAL_apply_contract_administration_1",
        "VAL_apply_contract_administration_2",
        "VAL_apply_contract_administration_3",
        "VAL_apply_contract_industry_1",
        "VAL_apply_contract_industry_2",
        "VAL_apply_contract_industry_3",
        "VAL_apply_contract_army_1",
        "VAL_apply_contract_army_2",
        "VAL_apply_contract_army_3",
        "VAL_refresh_contract_reputation",
    ):
        effect_blocks = named_blocks(effects, effect_id)
        if not effect_blocks:
            issues.append(f"missing tier effect {effect_id}")
            continue
        effect_block = effect_blocks[0]
        hidden = named_blocks(effect_block, "hidden_effect")
        if "custom_effect_tooltip" not in effect_block or not hidden:
            issues.append(f"{effect_id} exposes implementation details in its tooltip")
            continue
        if effect_block.count("remove_ideas") != hidden[0].count("remove_ideas"):
            issues.append(f"{effect_id} exposes tier removals outside hidden_effect")

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
            if not named_blocks(hidden_ideas[0], idea_id):
                issues.append(f"technical idea remains visible: {idea_id}")

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
