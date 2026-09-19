#!/usr/bin/env python3
"""Static contract for the historical Shabrat AI campaign."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from tools.lib.paths import repository_root
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = repository_root()
PLANS = ROOT / "common/ai_strategy_plans/ADISCORD_STP_plans.txt"
STRATEGY = ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt"
FOCUS = ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
EVENTS = ROOT / "events/ADISCORD_STP_events.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"

SCORE_TOTAL = 101

INTRO_FOCUSES = (
    "STP_NECTAR_OF_GODS",
    "STP_2160_budget",
    "STP_STATE_OF_THE_REPUBLIC",
)
CORE_FOCUSES = (
    "STP_ADRESS_PARTY_CRISIS",
    "STP_Count_The_Loyalists",
    "STP_Call_For_Shabrat",
    "STP_cw_officer_contacts",
    "STP_Garrisons_Hesitate",
    "STP_cw_port_budget",
    "STP_cw_repair_niansas",
    "STP_cw_northern_dossier",
    "STP_cw_arm_the_north",
    "STP_cw_district_printing",
    "STP_The_Silent_Mountain_March",
    "STP_cw_cabinet_archives",
    "STP_cw_buy_silence",
    "STP_cw_national_mandate",
)
DEPTH_FOCUSES = (
    "STP_Turn_The_Young_Officers",
    "STP_cw_defensive_lines",
    "STP_cw_heavy_reserve",
    "STP_cw_abila_reserve",
    "STP_cw_abila_workshops",
    "STP_cw_warehouse_inventory",
    "STP_cw_supply_officers",
    "STP_cw_district_administration",
    "STP_cw_courier_service",
    "STP_cw_local_council_envoys",
    "STP_cw_autonomy_guarantees",
    "STP_Kefreite_Security_Offer",
    "STP_cw_prepare_capital_sabotage",
)
WAR_FOCUSES = (
    "STP_cw_unified_headquarters",
    "STP_cw_mobilization_register",
    "STP_cw_wartime_arsenals",
    "STP_cw_road_to_fada",
    "STP_cw_supply_routes",
    "STP_cw_front_scouts",
    "STP_cw_mobile_workshops",
    "STP_cw_frontline_relief",
    "STP_cw_last_banquet",
    "STP_cw_cut_capital_roads",
    "STP_cw_government_quarter_assault",
    "STP_cw_line_formations",
    "STP_cw_route_columns",
)
RECONSTRUCTION_FOCUSES = (
    'STP_cw_first_postwar_budget',
    'STP_cw_restore_civil_authority',
    'STP_pc_after_victory',
    'STP_pc_economy_count_the_cost',
    'STP_pc_economy_reopen_tax_offices',
    'STP_pc_economy_repair_workshops',
    'STP_pc_economy_stabilize_currency',
    'STP_pc_economy_recovery_budget',
    'STP_pc_development_country_must_live',
    'STP_pc_development_posters_on_ruins',
    'STP_pc_development_rebuild_as_duty',
    'STP_pc_development_engineers_on_radio',
    'STP_pc_development_reopen_universities',
    'STP_pc_development_generation_reconstruction',
    'STP_pc_development_national_research_institutes',
    'STP_pc_shabrat_cabinet',
    'STP_pw_republic_new_republic',
    'STP_pw_republic_district_authority',
    'STP_pw_republic_civil_records',
    'STP_pw_republic_firm_settlement',
    'STP_pw_republic_civil_charter',
    'STP_pw_republic_restore_roads',
    'STP_pw_republic_homes_for_returnees',
    'STP_pw_republic_civil_workshops',
    'STP_pw_republic_accountable_arsenals',
    'STP_pw_republic_industrial_settlement',
    'STP_pw_republic_army_register',
    'STP_pw_republic_officer_school',
    'STP_pw_republic_supply_service',
    'STP_pw_republic_professional_service',
    'STP_pw_republic_settled_state',
)
HEGEMONY_FOCUSES = (
    "STP_pc_after_victory",
    "STP_pc_shabrat_cabinet",
    "STP_pc_war_ledgers",
    "STP_pc_two_borders",
    "STP_pc_shabrat_politics",
    "STP_pc_hegemony_open",
    "STP_pc_heg_unity",
    "STP_pc_heg_emergency",
    "STP_pc_heg_subordinate",
    "STP_pc_heg_limit_parties",
    "STP_pc_heg_lock",
    "STP_pc_heg_person",
    "STP_pc_heg_val_audit",
    "STP_pc_heg_val_terms",
    "STP_pc_heg_nod_break",
)

FOCUS_WEIGHTS = {
    "STP_NECTAR_OF_GODS": 20,
    "STP_2160_budget": 20,
    "STP_STATE_OF_THE_REPUBLIC": 20,
    "STP_Show_Him_The_Truth": 0,
    "STP_Govern_In_His_Name": 0,
    "STP_cw_pay_officials": 8,
    "STP_cw_repair_niansas": 12,
    "STP_cw_border_evidence": 4,
    "STP_cw_arm_the_north": 12,
    "STP_cw_expose_the_cabinet": 1,
    "STP_cw_buy_silence": 16,
    "STP_Kefreite_Security_Offer": 8,
    "STP_No_Mercenaries_In_Our_Mountains": 2,
    "STP_cw_unified_headquarters": 10,
    "STP_cw_wartime_laboratories": 1,
    "STP_cw_road_to_fada": 8,
    "STP_cw_last_banquet": 8,
    "STP_cw_cut_capital_roads": 8,
    "STP_cw_district_levies": 2,
    "STP_cw_first_postwar_budget": 8,
    "STP_cw_restore_civil_authority": 8,
    "STP_pc_after_victory": 10,
    "STP_pc_shabrat_cabinet": 12,
    "STP_pc_shabrat_politics": 12,
    "STP_pc_hegemony_open": 12,
    "STP_pc_freedom_open": 2,
}

PARTY_FOCUSES = {
    "STP_Govern_In_His_Name",
    "STP_PRESIDENT_REMAINS_IN_OFFICE",
    "STP_PARTY_DISCIPLINE",
    "STP_EMERGENCY_PRESIDIUM",
}
FORBIDDEN_PLAN_FOCUSES = PARTY_FOCUSES | {
    "STP_Show_Him_The_Truth",
    "STP_cw_pay_officials",
    "STP_cw_border_evidence",
    "STP_cw_expose_the_cabinet",
    "STP_No_Mercenaries_In_Our_Mountains",
    "STP_cw_military_committee_fund",
    "STP_cw_district_levies",
    "STP_pc_freedom_open",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def named_block(source: str, name: str) -> str:
    marker = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if marker is None:
        return ""
    start = marker.end() - 1
    depth = 0
    for index, char in enumerate(source[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return ""


def focus_list(plan: str) -> tuple[str, ...]:
    block = named_block(plan, "ai_national_focuses")
    return tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", block))


def scalar_int(source: str, key: str) -> int | None:
    match = re.search(rf"\b{re.escape(key)}\s*=\s*(-?\d+)\b", source)
    return int(match.group(1)) if match else None


def parse_focuses() -> dict[str, dict]:
    items = parse_clausewitz(read(FOCUS))
    result: dict[str, dict] = {}
    for tree in (entry for entry in items if entry.key == "focus_tree"):
        for focus in (entry for entry in tree.value if entry.key == "focus"):
            focus_id = next(child.value for child in focus.value if child.key == "id")
            ai = next((child.value for child in focus.value if child.key == "ai_will_do"), [])
            base = next((child.value for child in ai if child.key == "base"), None)
            prereqs = [
                [child.value for child in group if child.key == "focus"]
                for group in (child.value for child in focus.value if child.key == "prerequisite")
            ]
            exclusive = [
                child.value
                for group in (child.value for child in focus.value if child.key == "mutually_exclusive")
                for child in group
                if child.key == "focus"
            ]
            result[focus_id] = {"base": int(base) if base is not None else None, "prereqs": prereqs, "exclusive": exclusive}
    return result


def sequence_reachable(sequence: tuple[str, ...], focuses: dict[str, dict], assumed: set[str]) -> bool:
    done = set(assumed)
    for focus_id in sequence:
        spec = focuses.get(focus_id)
        if spec is None:
            return False
        for group in spec["prereqs"]:
            if group and not any(item in done for item in group):
                return False
        if any(partner in sequence for partner in spec["exclusive"]):
            return False
        done.add(focus_id)
    return True


def event_option(source: str, event_id: str, option_name: str) -> str:
    marker = f"\tid = {event_id}\n"
    start = source.find(marker)
    if start < 0:
        return ""
    nxt = source.find("\ncountry_event = {", start + len(marker))
    body = source[start : nxt if nxt != -1 else len(source)]
    option_marker = f"name = {option_name}"
    opt_start = body.find(option_marker)
    if opt_start < 0:
        return ""
    brace = body.rfind("{", 0, opt_start)
    if brace < 0:
        return ""
    depth = 0
    for index, char in enumerate(body[brace:], brace):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return body[brace : index + 1]
    return ""


def option_chance(source: str, event_id: str, option_name: str) -> int | None:
    option = event_option(source, event_id, option_name)
    return scalar_int(option, "factor") if "factor" in option else scalar_int(option, "base")


def decision_block(source: str, name: str) -> str:
    return named_block(source, name)


def run_checks() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    plans_text = read(PLANS) if PLANS.exists() else ""
    strategy_text = read(STRATEGY) if STRATEGY.exists() else ""
    events_text = read(EVENTS) if EVENTS.exists() else ""
    decisions_text = read(DECISIONS) if DECISIONS.exists() else ""
    focuses = parse_focuses() if FOCUS.exists() else {}

    add("plans file exists", PLANS.exists())
    add("strategy file exists", STRATEGY.exists())
    add("focus file exists", FOCUS.exists())
    add("events file exists", EVENTS.exists())
    add("decisions file exists", DECISIONS.exists())

    plan_ids = {
        "STP_shabrat_intro_plan": INTRO_FOCUSES,
        "STP_shabrat_preparation_core_plan": CORE_FOCUSES,
        "STP_shabrat_preparation_depth_plan": DEPTH_FOCUSES,
        "STS_shabrat_civil_war_plan": WAR_FOCUSES,
        "STS_shabrat_reconstruction_plan": RECONSTRUCTION_FOCUSES,
        "STS_shabrat_hegemony_plan": HEGEMONY_FOCUSES,
    }
    parsed_plans = {plan_id: named_block(plans_text, plan_id) for plan_id in plan_ids}
    add("all six plans defined once", all(plans_text.count(f"{plan_id} = {{") == 1 for plan_id in plan_ids))
    add("all plans enable AI", all("is_ai = yes" in body for body in parsed_plans.values()))
    add("all plans abort", all("abort =" in body for body in parsed_plans.values()))
    for plan_id, expected in plan_ids.items():
        add(f"{plan_id} focus order", focus_list(parsed_plans[plan_id]) == expected, str(focus_list(parsed_plans[plan_id])))

    intro = parsed_plans["STP_shabrat_intro_plan"]
    add("intro allowed STP", "original_tag = STP" in intro)
    add("intro weight 20", "weight = { factor = 20 }" in intro)
    add("intro abort after side choice", "has_country_flag = STP_sided_with_Maksim_flag" in named_block(intro, "abort"))
    add("intro hidden until the illness choice", "NOT = { has_country_flag = STP_sided_with_the_party_flag }" in named_block(intro, "enable"))

    core = parsed_plans["STP_shabrat_preparation_core_plan"]
    add("core requires Shabrat flag", "has_country_flag = STP_sided_with_Maksim_flag" in named_block(core, "enable"))
    add("core weight 20", "weight = { factor = 20 }" in core)
    add("core abort after mandate", "has_completed_focus = STP_cw_national_mandate" in named_block(core, "abort"))
    add("core waits for mandate", "NOT = { has_completed_focus = STP_cw_national_mandate }" in named_block(core, "enable"))

    depth = parsed_plans["STP_shabrat_preparation_depth_plan"]
    add("depth starts after mandate", "has_completed_focus = STP_cw_national_mandate" in named_block(depth, "enable"))
    add("depth weight 16", "weight = { factor = 16 }" in depth)
    add("depth prefers Kefreyt aid", "STP_Kefreite_Security_Offer" in depth and "STP_No_Mercenaries_In_Our_Mountains" not in depth)
    add("depth prefers workshops", "STP_cw_abila_workshops" in depth and "STP_cw_military_committee_fund" not in depth)

    war = parsed_plans["STS_shabrat_civil_war_plan"]
    add("war allowed STS", "original_tag = STS" in war)
    add("war weight 20", "weight = { factor = 20 }" in war)
    add("war abort postwar", "has_country_flag = STP_cw_postwar" in named_block(war, "abort"))
    add("war enable civil war", "has_global_flag = STP_cw_started" in named_block(war, "enable"))
    add("war prefers capital assault", "STP_cw_cut_capital_roads" in war and "STP_cw_district_levies" not in war)

    reconstruction = parsed_plans["STS_shabrat_reconstruction_plan"]
    add("reconstruction enable postwar", "has_country_flag = STP_cw_postwar" in named_block(reconstruction, "enable"))
    add("reconstruction weight 18", "weight = { factor = 18 }" in reconstruction)
    add("reconstruction prefers firm settlement", "STP_pw_republic_firm_settlement" in reconstruction and "STP_pw_republic_open_settlement" not in reconstruction)
    add("reconstruction abort settled", "has_completed_focus = STP_pw_republic_settled_state" in named_block(reconstruction, "abort"))

    hegemony = parsed_plans["STS_shabrat_hegemony_plan"]
    add("hegemony requires founder", "STP_pc_founder_rules = yes" in named_block(hegemony, "enable"))
    add("hegemony weight 16", "weight = { factor = 16 }" in hegemony)
    add("hegemony prefers lock-in", "STP_pc_hegemony_open" in hegemony and "STP_pc_freedom_open" not in hegemony)
    add("hegemony abort if founder lost", "STP_pc_founder_rules = no" in named_block(hegemony, "abort"))

    all_plan_focuses = [focus_id for expected in plan_ids.values() for focus_id in expected]
    add("plans avoid forbidden focuses", not FORBIDDEN_PLAN_FOCUSES.intersection(all_plan_focuses), str(FORBIDDEN_PLAN_FOCUSES.intersection(all_plan_focuses)))
    add("plans contain no add_ai_strategy", "add_ai_strategy" not in plans_text)
    add("every planned focus exists", all(focus_id in focuses for focus_id in all_plan_focuses), str([focus_id for focus_id in all_plan_focuses if focus_id not in focuses]))
    add("intro sequence reachable", sequence_reachable(INTRO_FOCUSES, focuses, set()))
    add("core sequence reachable", sequence_reachable(CORE_FOCUSES, focuses, {"STP_Show_Him_The_Truth"}))
    add("depth sequence reachable", sequence_reachable(DEPTH_FOCUSES, focuses, {"STP_Show_Him_The_Truth", *CORE_FOCUSES}))
    add("war sequence reachable", sequence_reachable(WAR_FOCUSES, focuses, set()))
    add("reconstruction sequence reachable", sequence_reachable(RECONSTRUCTION_FOCUSES, focuses, set()))
    add("hegemony sequence reachable", sequence_reachable(HEGEMONY_FOCUSES, focuses, set(RECONSTRUCTION_FOCUSES)))

    for focus_id, expected in FOCUS_WEIGHTS.items():
        actual = focuses.get(focus_id, {}).get("base")
        add(f"{focus_id} AI base {expected}", actual == expected, str(actual))

    add("Shabrat event chance 90", option_chance(events_text, "ADISCORD_STP_preparation.1", "ADISCORD_STP_preparation.1.a") == 90, str(option_chance(events_text, "ADISCORD_STP_preparation.1", "ADISCORD_STP_preparation.1.a")))
    add("party event chance 10", option_chance(events_text, "ADISCORD_STP_preparation.1", "ADISCORD_STP_preparation.1.b") == 10, str(option_chance(events_text, "ADISCORD_STP_preparation.1", "ADISCORD_STP_preparation.1.b")))
    add("postwar keep current leader 90", option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.a") == 90, str(option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.a")))
    add("postwar promote Shabrat 10", option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.b") == 10, str(option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.b")))
    add("postwar Gornin AI off", option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.c") == 0, str(option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.c")))
    add("postwar Vera AI off", option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.da") == 0, str(option_chance(events_text, "ADISCORD_STP_pc.7", "ADISCORD_STP_pc.7.da")))

    delegates = decision_block(decisions_text, "STP_cw_negotiate_with_delegates")
    campaign = decision_block(decisions_text, "STP_cw_open_election_campaign")
    kefreyt = decision_block(decisions_text, "STP_cw_renew_kefreyt_request")
    banquet = decision_block(decisions_text, "STP_cw_launch_last_banquet")
    network = decision_block(decisions_text, "STP_cw_raise_district_network")
    recruit = decision_block(decisions_text, "STP_recruit_regional_official")
    uprising = decision_block(decisions_text, "STP_cw_start_uprising")
    command = decision_block(decisions_text, "STP_cw_secure_election_result")

    add("delegates AI base 8", scalar_int(named_block(delegates, "ai_will_do"), "base") == 8)
    add("campaign AI base 6", scalar_int(named_block(campaign, "ai_will_do"), "base") == 6)
    add("Kefreyt request AI base 10", scalar_int(named_block(kefreyt, "ai_will_do"), "base") == 10)
    add("Last Banquet AI base 10", scalar_int(named_block(banquet, "ai_will_do"), "base") == 10)
    add("network prefers Niansas", "state = 3" in named_block(network, "ai_will_do"))
    add("network prefers Monaya", "state = 2" in named_block(network, "ai_will_do"))
    add("officials prefer credential districts", "state = 2" in named_block(recruit, "ai_will_do") and "state = 3" in named_block(recruit, "ai_will_do"))
    add("early uprising still vetoes a live mandate", "value > 0.10" in named_block(uprising, "ai_will_do"))
    add("public command stays inside the 40-80 window", "value = 40" in named_block(command, "ai_will_do") and "value = 80" in named_block(command, "ai_will_do"))
    fund_ai = re.search(
        r"id = STP_cw_military_committee_fund[\s\S]*?ai_will_do = \{[\s\S]*?\n\t\t\}",
        read(FOCUS) if FOCUS.exists() else "",
    )
    add(
        "military fund still yields to a late election",
        bool(fund_ai) and "days_mission_timeout@STP_cw_election_window" in fund_ai.group(0),
    )

    army = named_block(strategy_text, "STS_shabrat_civil_war_army")
    abilia = named_block(strategy_text, "STS_cw_defend_abilia")
    val_front = named_block(strategy_text, "STS_shabrat_val_front")
    sts_front = named_block(strategy_text, "STS_cw_front_against_stp")
    add("Shabrat army strategy exists", bool(army))
    add("Shabrat army abort_when_not_enabled", "abort_when_not_enabled = yes" in army)
    add("Shabrat army is AI-only", "is_ai = yes" in army)
    add("Shabrat army rush_weak", "execution_type = rush_weak" in army)
    add("Shabrat army consider_weak STP", "consider_weak id = STP" in army)
    add("Shabrat army concentrates", "force_concentration_factor" in army)
    add("Shabrat army produces infantry", "equipment_production_factor id = infantry" in army)
    add(
        "Shabrat reserve holds Abilia without stacking",
        "states = { 1 }" in abilia and "ratio = 0.05" in abilia and "put_unit_buffers" not in army,
    )
    add("STS front rush_weak", "execution_type = rush_weak" in sts_front)
    add("VAL front exists", bool(val_front) and "tag = VAL" in val_front)
    add("strategy file has no add_ai_strategy", "add_ai_strategy" not in strategy_text)

    return checks


def collect_issues() -> list[str]:
    results = run_checks()
    issues = [f"{name}: {detail}" if detail else name for name, ok, detail in results if not ok]
    if len(results) != SCORE_TOTAL:
        issues.insert(0, f"internal: expected {SCORE_TOTAL} checks, got {len(results)}")
    return issues


def score() -> tuple[int, int]:
    results = run_checks()
    passed = sum(1 for _, ok, _ in results if ok)
    return passed, SCORE_TOTAL


def validate() -> list[str]:
    return collect_issues()


def main() -> int:
    results = run_checks()
    passed = sum(1 for _, ok, _ in results if ok)
    issues = collect_issues()
    print(f"Shabrat AI validation: {passed}/{SCORE_TOTAL}")
    if issues:
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Historical Shabrat AI plans, weights, events, decisions and army strategies match the contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
