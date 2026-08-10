#!/usr/bin/env python3
"""Validate the WRK/WKR/VAD/TVA lifecycle focus tree."""

from __future__ import annotations

from collections import Counter
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

FOCUS_FILE = Path("common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt")
ENGLISH_LOCALISATION = Path(
    "localisation/english/ADISCORD_vorkerland_civil_war_focus_l_english.yml"
)
RUSSIAN_LOCALISATION = Path(
    "localisation/russian/ADISCORD_vorkerland_civil_war_focus_l_russian.yml"
)
SHINE_FILE = Path("interface/goals_shine.gfx")
FOCUS_DECISIONS_FILE = Path("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
DIPLOMACY_DECISIONS_FILE = Path(
    "common/decisions/ADISCORD_vorkerland_diplomacy_decisions.txt"
)

PREWAR_WRK_FOCUSES = (
    "WRK_measure_confederation_fault_lines",
    "WRK_convene_council_of_republics",
    "WRK_inventory_emergency_stores",
    "WRK_bind_districts_to_charter",
    "WRK_disperse_railway_reserves",
    "WRK_issue_continuity_orders",
)

PREWAR_VAD_FOCUSES = (
    "VAD_review_district_obligations",
    "VAD_open_continuity_registers",
    "VAD_drill_district_guard",
    "VAD_secure_administrative_archives",
    "VAD_disperse_eastern_depots",
    "VAD_form_emergency_chancery",
)

SHARED_WARTIME_FOCUSES = (
    "ADISCORD_vorkerland_stabilize_claimant_regime",
    "ADISCORD_vorkerland_mobilize_field_forces",
    "ADISCORD_vorkerland_fortify_home_region",
    "ADISCORD_vorkerland_prepare_central_front",
    "ADISCORD_vorkerland_conduct_central_showdown",
)

WARTIME_ROUTE_FOCUSES = {
    "WKR": (
        "WKR_affirm_worker_mandate",
        "WKR_convene_front_soviets",
        "WKR_organize_factory_battalions",
        "WKR_put_railways_under_councils",
        "WKR_authorize_retreat_levies",
        "WKR_form_revolutionary_supply_commission",
        "WKR_train_shopfloor_officers",
        "WKR_open_free_republics_channel",
        "WKR_republic_fights_as_one",
    ),
    "VAD": (
        "VAD_proclaim_joint_charter",
        "VAD_open_imperial_registers",
        "VAD_form_field_commandantures",
        "VAD_invite_sol_delegation",
        "VAD_establish_mobile_headquarters",
        "VAD_dispatch_solland_liaison_mission",
        "VAD_standardize_district_logistics",
        "VAD_balance_council_and_command",
        "VAD_assemble_joint_general_staff",
    ),
    "TVA": (
        "TVA_codify_utilitarian_directorate",
        "TVA_reroute_city_grid",
        "TVA_deploy_field_laboratories",
        "TVA_raise_technical_battalions",
        "TVA_seal_the_approaches",
        "TVA_issue_emergency_output_norms",
        "TVA_build_mobile_repair_trains",
        "TVA_publish_operational_metrics",
        "TVA_close_operational_loop",
    ),
}

POSTWAR_ROUTE_FOCUSES = {
    "ADISCORD_vorkerland_route_worker": (
        "WRK_worker_convene_reunification_congress",
        "WRK_worker_open_erased_nations_archives",
        "WRK_worker_recognize_free_republics",
        "WRK_worker_fund_cooperative_reconstruction",
        "WRK_worker_restore_displaced_councils",
        "WRK_worker_authorize_homecoming_commissions",
        "WRK_worker_write_constitutional_guarantees",
    ),
    "ADISCORD_vorkerland_route_joint": (
        "WRK_joint_convene_restoration_council",
        "WRK_joint_publish_amnesty_registers",
        "WRK_joint_establish_military_districts",
        "WRK_joint_reopen_district_rail_commands",
        "WRK_joint_issue_integration_warrants",
        "WRK_joint_restore_central_chancery",
        "WRK_joint_impose_reunification_settlement",
    ),
    "ADISCORD_vorkerland_route_utilitarian": (
        "WRK_utilitarian_form_reconstruction_directorate",
        "WRK_utilitarian_standardize_power_grid",
        "WRK_utilitarian_rebuild_machine_tool_pool",
        "WRK_utilitarian_expand_national_laboratories",
        "WRK_utilitarian_publish_integration_metrics",
        "WRK_utilitarian_rationalize_districts",
        "WRK_utilitarian_build_measurable_republic",
    ),
}

FOCUS_IDS = (
    *PREWAR_WRK_FOCUSES,
    *PREWAR_VAD_FOCUSES,
    SHARED_WARTIME_FOCUSES[0],
    SHARED_WARTIME_FOCUSES[1],
    SHARED_WARTIME_FOCUSES[2],
    *WARTIME_ROUTE_FOCUSES["WKR"],
    *WARTIME_ROUTE_FOCUSES["VAD"],
    *WARTIME_ROUTE_FOCUSES["TVA"],
    SHARED_WARTIME_FOCUSES[3],
    SHARED_WARTIME_FOCUSES[4],
    *POSTWAR_ROUTE_FOCUSES["ADISCORD_vorkerland_route_worker"],
    *POSTWAR_ROUTE_FOCUSES["ADISCORD_vorkerland_route_joint"],
    *POSTWAR_ROUTE_FOCUSES["ADISCORD_vorkerland_route_utilitarian"],
)

PREWAR_PHASE = "ADISCORD_vorkerland_phase_prewar"
ACTIVE_PHASE_FLAGS = {
    "ADISCORD_vorkerland_phase_collapse",
    "ADISCORD_vorkerland_phase_regional_consolidation",
    "ADISCORD_vorkerland_phase_central_preparation",
    "ADISCORD_vorkerland_phase_central_showdown",
}
POSTWAR_PHASE = "ADISCORD_vorkerland_phase_postwar_integration"
FINAL_FOCUS = "ADISCORD_vorkerland_conduct_central_showdown"

CENTRAL_CAPSTONES = {
    "WKR": (
        "WKR_republic_fights_as_one",
        "ADISCORD_vorkerland_focus_wkr_central_war_unlocked",
    ),
    "VAD": (
        "VAD_assemble_joint_general_staff",
        "ADISCORD_vorkerland_focus_vad_central_war_unlocked",
    ),
    "TVA": (
        "TVA_close_operational_loop",
        "ADISCORD_vorkerland_focus_tva_central_war_unlocked",
    ),
}

RETREAT_HOOKS = {
    "WKR": "ADISCORD_vorkerland_focus_wkr_retreat_levies_unlocked",
    "VAD": "ADISCORD_vorkerland_focus_vad_retreat_levies_unlocked",
    "TVA": "ADISCORD_vorkerland_focus_tva_retreat_levies_unlocked",
}

WARTIME_CONVERGENCE = {
    "WKR": ("WKR_open_free_republics_channel", "WKR_republic_fights_as_one"),
    "VAD": ("VAD_balance_council_and_command", "VAD_assemble_joint_general_staff"),
    "TVA": ("TVA_publish_operational_metrics", "TVA_close_operational_loop"),
}

POSTWAR_CORE_UNLOCK_FOCUSES = {
    "WRK_worker_authorize_homecoming_commissions",
    "WRK_joint_issue_integration_warrants",
    "WRK_utilitarian_publish_integration_metrics",
}

CORE_DECISIONS = {
    "ADISCORD_vorkerland_restore_core_claimant_homes",
    "ADISCORD_vorkerland_restore_core_central_historical",
    "ADISCORD_vorkerland_restore_core_rimat",
    "ADISCORD_vorkerland_restore_core_techlar",
    "ADISCORD_vorkerland_restore_core_ebern",
    "ADISCORD_vorkerland_restore_core_solar",
}

POSTWAR_HOOKS = {
    "ADISCORD_vorkerland_focus_worker_postwar_congress",
    "ADISCORD_vorkerland_focus_worker_erased_archives",
    "ADISCORD_vorkerland_focus_worker_displaced_councils",
    "ADISCORD_vorkerland_focus_worker_constitutional_guarantees",
    "ADISCORD_vorkerland_focus_worker_free_republics",
    "ADISCORD_vorkerland_focus_worker_cooperative_reconstruction",
    "ADISCORD_vorkerland_focus_worker_homecoming_commissions",
    "ADISCORD_vorkerland_focus_joint_postwar_council",
    "ADISCORD_vorkerland_focus_joint_amnesty_registers",
    "ADISCORD_vorkerland_focus_joint_military_districts",
    "ADISCORD_vorkerland_focus_joint_rail_commands",
    "ADISCORD_vorkerland_focus_joint_integration_warrants",
    "ADISCORD_vorkerland_focus_joint_restored_chancery",
    "ADISCORD_vorkerland_focus_joint_order_settlement",
    "ADISCORD_vorkerland_focus_utilitarian_postwar_directorate",
    "ADISCORD_vorkerland_focus_utilitarian_power_standard",
    "ADISCORD_vorkerland_focus_utilitarian_machine_tools",
    "ADISCORD_vorkerland_focus_utilitarian_national_laboratories",
    "ADISCORD_vorkerland_focus_utilitarian_integration_metrics",
    "ADISCORD_vorkerland_focus_utilitarian_rationalized_districts",
    "ADISCORD_vorkerland_focus_utilitarian_measurable_republic",
}

KNOWN_SHINED_ICONS = {
    "GFX_goal_generic_allies_build_infantry",
    "GFX_goal_generic_army_doctrines",
    "GFX_goal_generic_construct_civ_factory",
    "GFX_goal_generic_construct_infrastructure",
    "GFX_goal_generic_major_war",
    "GFX_goal_generic_military_sphere",
    "GFX_goal_generic_national_unity",
    "GFX_goal_generic_political_pressure",
    "GFX_goal_generic_positive_trade_relations",
    "GFX_goal_generic_production",
    "GFX_goal_generic_scientific_exchange",
}


def read(relative: Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def _blocks(text: str, assignment: str) -> list[str]:
    results: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(assignment)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        start = text.find("{", match.start())
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    results.append(text[match.start() : index + 1])
                    break
        else:
            raise ValueError(f"unterminated {assignment} block")
    return results


def focus_blocks(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in _blocks(text, "focus"):
        match = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+)\s*$", block)
        if not match:
            raise ValueError("focus block lacks an id")
        focus_id = match.group(1)
        if focus_id in result:
            raise ValueError(f"duplicate focus id {focus_id}")
        result[focus_id] = block
    return result


def localisation_entries(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for match in re.finditer(r'(?m)^\s+([A-Za-z0-9_]+):(?:\d+)?\s+"(.*)"\s*$', text):
        entries[match.group(1)] = match.group(2)
    return entries


def localisation_keys(text: str) -> list[str]:
    return re.findall(r'(?m)^\s+([A-Za-z0-9_]+):(?:\d+)?\s+"', text)


def expected_localisation_keys() -> set[str]:
    return {
        *FOCUS_IDS,
        *(f"{focus_id}_desc" for focus_id in FOCUS_IDS),
        "ADISCORD_vorkerland_claimant_focus_phase_tt",
        "ADISCORD_vorkerland_central_showdown_phase_tt",
    }


def _phase_flags(block: str) -> set[str]:
    return set(
        re.findall(
            r"\bhas_global_flag\s*=\s*(ADISCORD_vorkerland_phase_[A-Za-z0-9_]+)",
            block,
        )
    )


def _allow_branch(block: str) -> str:
    blocks = _blocks(block, "allow_branch")
    return blocks[0] if len(blocks) == 1 else ""


def _prerequisites(block: str) -> set[str]:
    result: set[str] = set()
    for prerequisite in _blocks(block, "prerequisite"):
        result.update(re.findall(r"\bfocus\s*=\s*([A-Za-z0-9_]+)", prerequisite))
    return result


def _check_graph(blocks: dict[str, str]) -> list[str]:
    issues: list[str] = []
    edges = {focus_id: _prerequisites(block) for focus_id, block in blocks.items()}
    for focus_id, prerequisites in edges.items():
        unknown = sorted(prerequisites - set(blocks))
        if unknown:
            issues.append(f"{focus_id} has unknown prerequisites {unknown}")
        if focus_id in prerequisites:
            issues.append(f"{focus_id} depends on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(focus_id: str) -> None:
        if focus_id in visited:
            return
        if focus_id in visiting:
            issues.append(f"focus graph contains a cycle through {focus_id}")
            return
        visiting.add(focus_id)
        for prerequisite in edges.get(focus_id, set()):
            if prerequisite in blocks:
                visit(prerequisite)
        visiting.remove(focus_id)
        visited.add(focus_id)

    for focus_id in blocks:
        visit(focus_id)
    return issues


def collect_issues() -> list[str]:
    issues: list[str] = []
    required_paths = (
        FOCUS_FILE,
        ENGLISH_LOCALISATION,
        RUSSIAN_LOCALISATION,
        SHINE_FILE,
        FOCUS_DECISIONS_FILE,
        DIPLOMACY_DECISIONS_FILE,
    )
    for relative in required_paths:
        if not (ROOT / relative).is_file():
            issues.append(f"missing {relative.as_posix()}")
    if issues:
        return issues

    source = read(FOCUS_FILE)
    shine_source = read(SHINE_FILE)
    focus_decisions = read(FOCUS_DECISIONS_FILE)
    diplomacy_decisions = read(DIPLOMACY_DECISIONS_FILE)
    try:
        trees = _blocks(source, "focus_tree")
        blocks = focus_blocks(source)
    except ValueError as exc:
        return [str(exc)]

    if len(trees) != 1:
        issues.append(f"lifecycle focus source must define one tree, found {len(trees)}")
        tree = source
    else:
        tree = trees[0]
    if "id = ADISCORD_vorkerland_civil_war_focus" not in tree:
        issues.append("lifecycle focus tree id is missing")
    if not re.search(r"(?m)^\s*default\s*=\s*no\s*$", tree):
        issues.append("lifecycle focus tree must be non-default")

    country_blocks = _blocks(tree, "country")
    if len(country_blocks) != 1:
        issues.append(f"lifecycle focus tree must have one country selector, found {len(country_blocks)}")
    else:
        country = country_blocks[0]
        tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", country))
        if tags != {"WRK", "WKR", "VAD", "TVA"}:
            issues.append(f"country selector must cover WRK/WKR/VAD/TVA, found {sorted(tags)}")
        if "original_tag" in country:
            issues.append("country selector must use current lifecycle tags, not original_tag")
        if not re.search(r"\bfactor\s*=\s*0\b", country):
            issues.append("country selector must start from factor 0")
        if not re.search(r"\badd\s*=\s*100\b", country):
            issues.append("country selector must add weight 100 for lifecycle tags")

    if tuple(blocks) != FOCUS_IDS:
        issues.append(f"focus IDs/order differ from the 65-focus lifecycle manifest: {tuple(blocks)}")
    if len(FOCUS_IDS) != 65:
        issues.append(f"validator manifest must contain 65 definitions, found {len(FOCUS_IDS)}")
    issues.extend(_check_graph(blocks))

    category_by_focus: dict[str, tuple[str, str | None]] = {}
    for focus_id in PREWAR_WRK_FOCUSES:
        category_by_focus[focus_id] = ("prewar", "WRK")
    for focus_id in PREWAR_VAD_FOCUSES:
        category_by_focus[focus_id] = ("prewar", "VAD")
    for focus_id in SHARED_WARTIME_FOCUSES:
        category_by_focus[focus_id] = ("wartime", None)
    for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
        for focus_id in focus_ids:
            category_by_focus[focus_id] = ("wartime", tag)
    for route_flag, focus_ids in POSTWAR_ROUTE_FOCUSES.items():
        for focus_id in focus_ids:
            category_by_focus[focus_id] = ("postwar", route_flag)

    for focus_id, block in blocks.items():
        if "cancel_if_invalid = yes" not in block:
            issues.append(f"{focus_id} must cancel when its lifecycle phase becomes invalid")
        allow = _allow_branch(block)
        if not allow:
            issues.append(f"{focus_id} must define exactly one allow_branch gate")
        category, gate = category_by_focus.get(focus_id, ("unknown", None))
        flags = _phase_flags(block)
        if category == "prewar":
            if flags != {PREWAR_PHASE}:
                issues.append(f"{focus_id} must be prewar-only, found phases {sorted(flags)}")
            if _phase_flags(allow) != {PREWAR_PHASE}:
                issues.append(f"{focus_id} allow_branch must hide outside the prewar phase")
            if set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow)) != {gate}:
                issues.append(f"{focus_id} must expose only the prewar {gate} block")
            cost_expected = {5}
        elif category == "wartime":
            expected_flags = {"ADISCORD_vorkerland_phase_central_showdown"} if focus_id == FINAL_FOCUS else ACTIVE_PHASE_FLAGS
            if flags != expected_flags:
                issues.append(f"{focus_id} has wrong wartime phases {sorted(flags)}")
            if _phase_flags(allow) != expected_flags:
                issues.append(f"{focus_id} allow_branch has wrong wartime phases {sorted(_phase_flags(allow))}")
            branch_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow))
            expected_tags = {gate} if gate else {"WKR", "VAD", "TVA"}
            if branch_tags != expected_tags:
                issues.append(f"{focus_id} branch tags {sorted(branch_tags)} != {sorted(expected_tags)}")
            cost_expected = {3, 4, 5}
        elif category == "postwar":
            if flags != {POSTWAR_PHASE}:
                issues.append(f"{focus_id} must be postwar-only, found phases {sorted(flags)}")
            if _phase_flags(allow) != {POSTWAR_PHASE}:
                issues.append(f"{focus_id} allow_branch must hide outside postwar integration")
            if set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow)) != {"WRK"}:
                issues.append(f"{focus_id} must expose only the reunified WRK block")
            if f"has_country_flag = {gate}" not in allow:
                issues.append(f"{focus_id} is not isolated behind {gate}")
            cost_expected = {5, 7, 10}
        else:
            issues.append(f"{focus_id} is not classified in the lifecycle manifest")
            continue

        cost_match = re.search(r"(?m)^\s*cost\s*=\s*(\d+)\s*$", block)
        cost = int(cost_match.group(1)) if cost_match else -1
        if cost not in cost_expected:
            issues.append(f"{focus_id} cost {cost} is outside {sorted(cost_expected)}")

        position = {
            axis: re.search(rf"(?m)^\s*{axis}\s*=\s*(-?\d+)\s*$", block)
            for axis in ("x", "y")
        }
        if any(match is None or int(match.group(1)) < 0 for match in position.values()):
            issues.append(f"{focus_id} must have non-negative absolute x/y coordinates")

        icon_matches = re.findall(r"(?m)^\s*icon\s*=\s*([A-Za-z0-9_]+)\s*$", block)
        if len(icon_matches) != 1 or icon_matches[0] not in KNOWN_SHINED_ICONS:
            issues.append(f"{focus_id} must use one known generic shined icon, found {icon_matches}")
        elif f'name = "{icon_matches[0]}_shine"' not in shine_source:
            issues.append(f"{focus_id} icon {icon_matches[0]} lacks an explicit local shine sprite")
        ai = _blocks(block, "ai_will_do")
        if len(ai) != 1 or not re.search(r"\bbase\s*=\s*(?:[1-9]|1\d|20)\b", ai[0]):
            issues.append(f"{focus_id} must define a bounded positive AI weight")

    # Each claimant receives five shared, nine unique wartime and seven postwar
    # definitions. One mutually-exclusive split leaves 19 completable nodes,
    # while all 21 remain visible as the authored political choice.
    for tag, route_flag in (
        ("WKR", "ADISCORD_vorkerland_route_worker"),
        ("VAD", "ADISCORD_vorkerland_route_joint"),
        ("TVA", "ADISCORD_vorkerland_route_utilitarian"),
    ):
        authored = len(SHARED_WARTIME_FOCUSES) + len(WARTIME_ROUTE_FOCUSES[tag]) + len(POSTWAR_ROUTE_FOCUSES[route_flag])
        if authored != 21:
            issues.append(f"{tag} authored civil/postwar route must contain 21 focuses, found {authored}")

    mex_pairs = (
        ("WRK_convene_council_of_republics", "WRK_inventory_emergency_stores"),
        ("VAD_open_continuity_registers", "VAD_drill_district_guard"),
        ("WKR_convene_front_soviets", "WKR_organize_factory_battalions"),
        ("VAD_open_imperial_registers", "VAD_form_field_commandantures"),
        ("TVA_reroute_city_grid", "TVA_deploy_field_laboratories"),
    )
    for left, right in mex_pairs:
        if f"focus = {right}" not in "\n".join(_blocks(blocks.get(left, ""), "mutually_exclusive")):
            issues.append(f"{left} must be mutually exclusive with {right}")
        if f"focus = {left}" not in "\n".join(_blocks(blocks.get(right, ""), "mutually_exclusive")):
            issues.append(f"{right} must be mutually exclusive with {left}")

    prepare = blocks.get("ADISCORD_vorkerland_prepare_central_front", "")
    for tag, (capstone, flag) in CENTRAL_CAPSTONES.items():
        if f"focus = {capstone}" not in prepare:
            issues.append(f"central-front preparation lacks the {tag} capstone {capstone}")
        capstone_block = blocks.get(capstone, "")
        if f"set_country_flag = {flag}" not in capstone_block:
            issues.append(f"{capstone} must set gameplay hook {flag}")

    final = blocks.get(FINAL_FOCUS, "")
    if "focus = ADISCORD_vorkerland_prepare_central_front" not in final:
        issues.append("central showdown must follow central-front preparation")

    for tag, hook in RETREAT_HOOKS.items():
        route_source = "\n".join(blocks.get(focus_id, "") for focus_id in WARTIME_ROUTE_FOCUSES[tag])
        if route_source.count(f"set_country_flag = {hook}") != 2:
            issues.append(f"{tag} alternate wartime paths must both set retreat hook {hook}")
        if hook not in focus_decisions:
            issues.append(f"{tag} retreat hook {hook} is not consumed by visible decisions")

    for tag, (convergence, capstone) in WARTIME_CONVERGENCE.items():
        if _prerequisites(blocks.get(capstone, "")) != {convergence}:
            issues.append(f"{tag} capstone {capstone} must follow expanded convergence {convergence}")

    reward_classes = {
        "political": ("add_political_power", "add_stability"),
        "military": ("army_experience", "add_command_power", "add_manpower", "add_war_support"),
        "economic": ("add_equipment_to_stockpile", "add_building_construction", "add_timed_idea"),
    }
    for tag, route_ids in WARTIME_ROUTE_FOCUSES.items():
        route_source = "\n".join(blocks.get(focus_id, "") for focus_id in route_ids)
        for reward_class, tokens in reward_classes.items():
            if not any(token in route_source for token in tokens):
                issues.append(f"{tag} wartime route lacks a {reward_class} reward")

    sol_hook = "ADISCORD_vorkerland_focus_vad_sol_invitation_intent"
    sol_focus = blocks.get("VAD_invite_sol_delegation", "")
    if f"set_country_flag = {sol_hook}" not in sol_focus:
        issues.append("wartime VAD SOL policy focus must set its outcome-dependent intent hook")
    if source.count(f"set_country_flag = {sol_hook}") != 1:
        issues.append("VAD SOL invitation intent hook must have one focus owner")

    vla_hook = "ADISCORD_vorkerland_focus_wkr_vla_invitation_intent"
    vla_focus = blocks.get("WKR_open_free_republics_channel", "")
    if f"set_country_flag = {vla_hook}" not in vla_focus:
        issues.append("expanded WKR diplomacy focus must expose the VLA invitation intent")
    for hook in (sol_hook, vla_hook):
        if hook not in diplomacy_decisions:
            issues.append(f"diplomacy intent {hook} is not consumed by a visible decision")
    for accepted_flag in (
        "ADISCORD_vorkerland_wkr_vla_alliance_accepted",
        "ADISCORD_vorkerland_vad_sol_alliance_accepted",
    ):
        if accepted_flag not in focus_decisions:
            issues.append(f"allied support decisions lack accepted-policy gate {accepted_flag}")

    postwar_source = "\n".join(
        blocks.get(focus_id, "")
        for focus_ids in POSTWAR_ROUTE_FOCUSES.values()
        for focus_id in focus_ids
    )
    for hook in POSTWAR_HOOKS:
        if postwar_source.count(f"set_country_flag = {hook}") != 1:
            issues.append(f"postwar hook {hook} must have exactly one route focus owner")

    core_unlock = "ADISCORD_vorkerland_focus_postwar_core_decisions_unlocked"
    if postwar_source.count(f"set_country_flag = {core_unlock}") != 3:
        issues.append("each postwar route must set the common core-decision unlock exactly once")
    for focus_id in POSTWAR_CORE_UNLOCK_FOCUSES:
        if f"set_country_flag = {core_unlock}" not in blocks.get(focus_id, ""):
            issues.append(f"{focus_id} must unlock visible postwar core decisions")
    for decision_id in CORE_DECISIONS:
        decision_blocks = _blocks(focus_decisions, decision_id)
        if len(decision_blocks) != 1:
            issues.append(f"core decision {decision_id} must have one public definition")
        elif f"has_country_flag = {core_unlock}" not in decision_blocks[0]:
            issues.append(f"core decision {decision_id} is not gated by its focus unlock")

    # Military victory is controller-owned. Postwar branches must be reachable
    # even if the showdown focus was canceled by a fast phase transition.
    for focus_ids in POSTWAR_ROUTE_FOCUSES.values():
        root = blocks.get(focus_ids[0], "")
        if _prerequisites(root):
            issues.append(f"postwar root {focus_ids[0]} must not require a wartime focus")
        if FINAL_FOCUS in "\n".join(blocks.get(focus_id, "") for focus_id in focus_ids):
            issues.append(f"postwar route {focus_ids[0]} incorrectly depends on showdown focus completion")

    fortify = blocks.get("ADISCORD_vorkerland_fortify_home_region", "")
    for tag, state, province in (("WKR", 32, 6713), ("VAD", 75, 6192), ("TVA", 36, 12227)):
        pattern = (
            rf"limit\s*=\s*\{{\s*tag\s*=\s*{tag}\s+controls_state\s*=\s*{state}\s*\}}"
            rf"\s*{state}\s*=\s*\{{\s*add_building_construction\s*=\s*\{{"
            rf"\s*type\s*=\s*bunker\s+level\s*=\s*1\s+instant_build\s*=\s*yes"
            rf"\s+province\s*=\s*{province}\s*\}}\s*\}}"
        )
        if not re.search(pattern, fortify):
            issues.append(f"fortification reward lacks bounded {tag} redoubt {state}/{province}")
    if fortify.count("type = bunker level = 1") != 3:
        issues.append("fortification reward must contain one level-one redoubt per claimant")

    forbidden_effects = (
        "declare_war_on",
        "start_civil_war",
        "create_wargoal",
        "annex_country",
        "puppet",
        "set_autonomy",
        "transfer_state",
        "add_core_of",
        "remove_core_of",
        "create_unit",
        "release =",
        "add_offsite_building",
        "add_tech_bonus",
        "set_global_flag",
        "ADISCORD_vorkerland_set_phase_",
        "country_event",
        "news_event",
        "every_country",
        "random_country",
        "on_monthly",
        "monthly_pulse",
    )
    for token in forbidden_effects:
        if token in source:
            issues.append(f"lifecycle focus tree contains forbidden controller/diplomacy effect {token}")
    if re.search(r"lucas", source, re.IGNORECASE):
        issues.append("lifecycle focus content must not depend on Lucas-specific state")

    bounded_values = {
        "add_political_power": 25.0,
        "add_stability": 0.03,
        "add_manpower": 600.0,
        "army_experience": 10.0,
        "add_command_power": 10.0,
        "add_war_support": 0.03,
    }
    for effect, maximum in bounded_values.items():
        for raw in re.findall(rf"\b{effect}\s*=\s*(-?\d+(?:\.\d+)?)", source):
            if float(raw) > maximum:
                issues.append(f"{effect} reward {raw} exceeds maximum {maximum:g}")
    for raw in re.findall(r"\bamount\s*=\s*(-?\d+(?:\.\d+)?)", source):
        if float(raw) > 150:
            issues.append(f"equipment reward {raw} exceeds maximum 150")
    for raw in re.findall(r"\bdays\s*=\s*(\d+)\s*\}", source):
        if int(raw) > 70:
            issues.append(f"timed idea duration {raw} exceeds maximum 70 days")
    for construction in _blocks(source, "add_building_construction"):
        level = re.search(r"\blevel\s*=\s*(\d+)", construction)
        if not level or int(level.group(1)) != 1:
            issues.append(f"focus construction must add exactly one level: {construction}")

    english = read(ENGLISH_LOCALISATION)
    russian = read(RUSSIAN_LOCALISATION)
    if not english.startswith("l_english:\n"):
        issues.append("English lifecycle focus localisation has the wrong header")
    if not russian.startswith("l_russian:\n"):
        issues.append("Russian lifecycle focus localisation has the wrong header")
    if not (ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian lifecycle focus localisation must use UTF-8 BOM")

    expected_keys = expected_localisation_keys()
    for language, text in (("English", english), ("Russian", russian)):
        keys = localisation_keys(text)
        duplicates = sorted(key for key, count in Counter(keys).items() if count != 1)
        if duplicates:
            issues.append(f"{language} localisation has duplicate keys: {duplicates}")
        entries = localisation_entries(text)
        if set(entries) != expected_keys:
            missing = sorted(expected_keys - set(entries))
            extra = sorted(set(entries) - expected_keys)
            issues.append(f"{language} localisation key mismatch: missing={missing}, extra={extra}")
        empty = sorted(key for key, value in entries.items() if not value.strip())
        if empty:
            issues.append(f"{language} localisation has empty values: {empty}")

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        print("A-Discord Vorkerland lifecycle focus validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("A-Discord Vorkerland lifecycle focus validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
