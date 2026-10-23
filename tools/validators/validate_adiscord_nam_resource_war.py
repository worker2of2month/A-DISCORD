"""Focused static contract for the scripted NAM resource war."""

from __future__ import annotations
from tools.lib.on_actions import read_country_on_actions

import re
import sys
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
ISSUES: list[str] = []


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        ISSUES.append(f"missing {relative}")
        return ""
    return path.read_text(encoding="utf-8-sig", errors="strict")


def check(condition: bool, message: str) -> None:
    if not condition:
        ISSUES.append(message)


def balanced_braces(source: str) -> bool:
    depth = 0
    in_quote = False
    escaped = False
    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0]
        for char in line:
            if escaped:
                escaped = False
                continue
            if char == "\\" and in_quote:
                escaped = True
            elif char == '"':
                in_quote = not in_quote
            elif not in_quote and char == "{":
                depth += 1
            elif not in_quote and char == "}":
                depth -= 1
                if depth < 0:
                    return False
    return depth == 0 and not in_quote


def matching_brace(source: str, opening: int) -> int:
    depth = 0
    in_quote = False
    for index in range(opening, len(source)):
        char = source[index]
        if char == '"':
            in_quote = not in_quote
        elif not in_quote and char == "{":
            depth += 1
        elif not in_quote and char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    opening = source.find("{", match.start(), match.end())
    closing = matching_brace(source, opening)
    return source[match.start() : closing + 1] if closing >= 0 else ""


def typed_blocks(source: str, block_type: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(block_type)}\s*=\s*\{{", source):
        opening = source.find("{", match.start(), match.end())
        closing = matching_brace(source, opening)
        if closing >= 0:
            blocks.append(source[match.start() : closing + 1])
    return blocks


def without_comments(source: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in source.splitlines())


def has_script_fragment(source: str, fragment: str) -> bool:
    pattern = r"\s+".join(re.escape(part) for part in fragment.split())
    return re.search(pattern, without_comments(source)) is not None


def state_source(state_id: int) -> str:
    candidates = list((ROOT / "history" / "states").glob(f"{state_id}-*.txt"))
    if len(candidates) != 1:
        ISSUES.append(
            f"state {state_id}: expected one history file, found {len(candidates)}"
        )
        return ""
    return candidates[0].read_text(encoding="utf-8-sig", errors="strict")


def owner_of_state(state_id: int) -> str | None:
    match = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})", state_source(state_id))
    return match.group(1) if match else None


OIL_BUYERS = {
    "EFL", "AZH", "VAL", "STP", "STS", "RHM", "MZR",
    "SHL", "RUS", "WEF", "KDR", "SDR", "GLP", "KYZ",
}
FIELD_CAPACITY = {67: 8, 688: 2, 689: 4, 690: 3, 719: 1}
PROJECT_PRICES = {
    "NAM_project_repair_wells": (25, 150, 45, "NAM_project_complete_repair"),
    "NAM_project_refinery": (40, 300, 90, "NAM_project_complete_refinery"),
    "NAM_project_pipeline": (35, 350, 120, "NAM_project_complete_pipeline"),
    "NAM_project_sea_terminal": (30, 250, 90, "NAM_project_complete_terminal"),
}
DECISION_FOCUS_GATES = {
    "NAM_restitution_note": "NAM_restitution_desk",
    "NAM_order_resource_guard": "NAM_mobilisation_office",
    "NAM_order_field_infantry": "NAM_mobilisation_office",
    "NAM_order_motor_column": "NAM_motor_column_orders",
    "NAM_order_coastal_battalion": "NAM_coastal_battalions",
    "NAM_prepare_line": "NAM_line_survey",
    "NAM_scorch_wells": "NAM_scorched_wells",
    "NAM_oil_contract_offer": "NAM_contract_bureau",
    "NAM_fuel_embargo": "NAM_fuel_leverage",
    "NAM_project_repair_wells": "NAM_field_repair_crews",
    "NAM_project_refinery": "NAM_refinery_programme",
    "NAM_project_pipeline": "NAM_klyuchevsk_pipeline",
    "NAM_project_sea_terminal": "NAM_overseas_buyers",
    "NAM_island_steel_levy": "NAM_island_levy_office",
    "NAM_island_concession_231": "NAM_island_concession",
    "NAM_island_convoy_service": "NAM_island_convoys",
    "NAM_renegotiate_val_concession": "NAM_reclaim_230",
    "NAM_south_allied_fuel": "NAM_south_allied_fuel_office",
    "NAM_south_convoy_interdiction": "NAM_south_convoy_hunters",
}


def check_oil_monopoly(
    effects: str,
    triggers: str,
    on_actions: str,
    decisions: str,
    categories: str,
    events: str,
    hostilities: str,
) -> None:
    """Oil throughput, contracts, embargo, field projects and the islands."""
    initialize = named_block(effects, "NAM_oil_initialize")
    for state_id, capacity in FIELD_CAPACITY.items():
        state_block = named_block(initialize, str(state_id))
        check(
            f"var = NAM_field_capacity value = {capacity}" in state_block
            and "var = NAM_field_condition value = 80" in state_block,
            f"field {state_id} must start with capacity {capacity} and condition 80",
        )
    groups_init = named_block(effects, "NAM_groups_initialize")
    check(
        "NAM_oil_initialize = yes" in groups_init
        and "var = NAM_project_slots value = 1" in groups_init,
        "the single startup entry must seed the oil system and one project slot",
    )
    refresh = named_block(effects, "NAM_oil_refresh")
    check(
        all(f"{state_id} = {{ NAM_field_update_units = yes }}" in refresh for state_id in FIELD_CAPACITY)
        and "NAM_oil_count_clients = yes" in refresh
        and "has_country_flag = NAM_rw_tribute" in refresh
        and "NAM_rw_azh_treaty" not in effects
        and "NAM_sea_terminal_built" in refresh,
        "NAM_oil_refresh must count fields, the terminal, contracts and tribute; the Azhar treaty is retired",
    )
    check(
        "is_controlled_by = NAM" in named_block(effects, "NAM_field_update_units"),
        "throughput must count only fields Svetlogorye controls",
    )
    oil_effects = [
        named_block(effects, name)
        for name in (
            "NAM_oil_refresh",
            "NAM_oil_monthly",
            "NAM_oil_settle_clients",
            "NAM_oil_validate_clients",
            "NAM_oil_count_clients",
            "NAM_island_levy_monthly",
            "NAM_rus_coalition_check",
        )
    ]
    check(
        all(block and "every_country" not in block for block in oil_effects),
        "recurring oil work must read fixed tags, never scan every country",
    )
    for list_effect, call in (
        ("NAM_oil_count_clients", "NAM_oil_count_client"),
        ("NAM_oil_validate_clients", "NAM_oil_validate_client"),
        ("NAM_oil_settle_clients", "NAM_oil_settle_client"),
        ("NAM_oil_release_all_buyers", "NAM_oil_release_buyer"),
    ):
        listed = set(
            re.findall(
                rf"\b([A-Z]{{3}})\s*=\s*\{{\s*{call}\s*=\s*yes\s*\}}",
                named_block(effects, list_effect),
            )
        )
        check(listed == OIL_BUYERS, f"{list_effect} must cover the fixed buyer list: {sorted(listed)}")
    buyer_trigger = set(re.findall(r"tag\s*=\s*([A-Z]{3})", named_block(triggers, "NAM_oil_buyer_tag")))
    check(buyer_trigger == OIL_BUYERS, f"NAM_oil_buyer_tag drifted: {sorted(buyer_trigger)}")
    offer = named_block(decisions, "NAM_oil_contract_offer")
    offer_targets = set(re.findall(r"[A-Z]{3}", named_block(offer, "targets")))
    check(offer_targets == OIL_BUYERS, f"contract targets drifted: {sorted(offer_targets)}")
    check(
        "NAM_oil_unit_free_for_buyer = yes" in offer
        and "NAM_oil_offer_contract = yes" in offer,
        "a contract offer needs a free unit and the buyer's consent event",
    )
    sign = named_block(effects, "NAM_oil_sign_contract")
    check(
        "NAM_oil_unit_free_for_buyer = yes" in sign
        and "set_country_flag = NAM_oil_client" in sign
        and "NAM_oil_refresh = yes" in sign
        and "ADISCORD_nam_oil.2" in sign,
        "signature must recheck capacity, set the client flag, refresh and inform Svetlogorye",
    )
    settle = named_block(effects, "NAM_oil_settle_client")
    check(
        "NOT = { has_fuel < 1500 }" in settle
        and "add_fuel = 1500" in settle
        and "add_fuel = -1500" in settle
        and "value = 40" in settle,
        "monthly settlement must move 1500 fuel from stock and earn 40 treasury",
    )
    check(
        "NAM_add_treasury = yes" in named_block(effects, "NAM_oil_settle_clients"),
        "contract revenue must enter through the treasury helper",
    )
    validate = named_block(effects, "NAM_oil_validate_client")
    check(
        "has_war_with = NAM" in validate
        and "modifier = NAM_fuel_shortage" in validate
        and "days = 90" in validate,
        "a war with a client must end its contract with a 90-day shortage",
    )
    for removal in re.finditer(r"remove_dynamic_modifier\s*=\s*\{\s*modifier\s*=\s*(\w+)", effects):
        window = effects[max(0, removal.start() - 300) : removal.start()]
        check(
            f"has_dynamic_modifier = {{ modifier = {removal.group(1)} }}" in window,
            f"remove_dynamic_modifier {removal.group(1)} lacks its has_dynamic_modifier guard",
        )
    check(
        "NAM_oil_validate_clients = yes" in hostilities
        and hostilities.count("NOT = { has_country_flag = NAM_oil_client }") == 2,
        "hostilities must end belligerent contracts and spare RHM/MZR clients the volunteer idea",
    )
    tension = named_block(effects, "NAM_rw_tension_monthly")
    check(
        tension.count("modifier = NAM_fuel_embargo_modifier") == 2,
        "each embargo on Eflor or Azhar must add restitution pressure",
    )
    check(
        "NAM_oil_release_all_buyers = yes" in named_block(effects, "NAM_oil_close_all")
        and "NAM_oil_release_all_buyers = yes" in named_block(effects, "NAM_rw_settle_island_exile")
        and "NAM_steel_concession_end" not in named_block(effects, "NAM_rw_settle_island_exile"),
        "the partition must close every contract; the island exile keeps the steel concession",
    )
    buy_time = named_block(effects, "NAM_rw_buy_time")
    check(
        "NOT = { has_country_flag = NAM_rw_time_bought }" in buy_time
        and "NOT = { has_fuel < 12000 }" in buy_time
        and buy_time.count("add_fuel = -12000") == 1
        and "AZH = { add_fuel = 12000 }" in buy_time
        and "set_country_flag = NAM_rw_time_bought" in buy_time
        and "NOT = { NAM_rw_time_bought_active = yes }" in named_block(triggers, "NAM_rw_war_window_open")
        and "days < 75" in named_block(triggers, "NAM_rw_time_bought_active"),
        "Azhar's delay must be paid once in fuel and close the war window for 75 days",
    )
    check(
        "NAM_oil_refresh = yes" in named_block(effects, "NAM_rw_start_tribute"),
        "starting the tribute must commit its units",
    )
    check(
        "NAM_oil_monthly = yes" in named_block(effects, "NAM_rw_monthly")
        and "NAM_rw_monthly = yes" in named_block(on_actions, "on_monthly_NAM"),
        "contracts must settle inside on_monthly_NAM",
    )
    check(
        "NAM_oil_refresh = yes" in named_block(on_actions, "on_state_control_changed"),
        "control changes must refresh oil throughput",
    )
    check(
        "NAM_oil_refresh = yes" in named_block(decisions, "NAM_scorch_wells")
        and "modifier = NAM_scorched_wells_modifier" in named_block(decisions, "NAM_scorch_wells"),
        "scorched wells must refresh throughput and use the renamed state modifier",
    )
    slot = named_block(triggers, "NAM_project_slot_free")
    check(
        "value = NAM_projects_in_progress compare = greater_than" in slot
        and "value = 2 compare = less_than" in slot,
        "field projects must respect NAM_project_slots and the ceiling of two",
    )
    for decision_name, (pp, treasury, days, completion) in PROJECT_PRICES.items():
        decision = named_block(decisions, decision_name)
        complete = named_block(decision, "complete_effect")
        check(
            "cost = 0" in decision
            and "custom_cost_text = NAM_cost_project_" in decision
            and f"NOT = {{ has_political_power < {pp} }}" in decision
            and f"value = {treasury} compare = greater_than_or_equals" in decision
            and f"days_remove = {days}" in decision
            and "NAM_project_slot_free = yes" in decision
            and "has_decision" not in decision,
            f"{decision_name} lacks its exact price, duration or slot contract",
        )
        check(
            complete.count(f"add_political_power = -{pp}") == 1
            and complete.count(f"var = NAM_treasury_amount value = {treasury}") == 1
            and complete.count("NAM_spend_treasury = yes") == 1
            and f"var = NAM_project_deposit value = {treasury}" in complete
            and "NAM_project_begin = yes" in complete,
            f"{decision_name} must debit each currency once into the state escrow",
        )
        check(
            f"{completion} = yes" in named_block(decision, "remove_effect")
            and "NAM_project_release = yes" in named_block(decision, "cancel_effect"),
            f"{decision_name} must settle at completion and refund on cancellation",
        )
        settle_block = named_block(effects, completion)
        check(
            "is_owned_by = NAM" in settle_block
            and "is_controlled_by = NAM" in settle_block
            and "NAM_project_release = yes" in settle_block,
            f"{completion} must recheck ownership and control and refund a lost state",
        )
    check(
        "has_state_flag = NAM_project_in_progress" in named_block(effects, "NAM_project_release"),
        "a project refund must settle only a state holding the escrow",
    )
    for decision_name, focus in DECISION_FOCUS_GATES.items():
        decision = named_block(decisions, decision_name)
        check(
            f"has_completed_focus = {focus}" in named_block(decision, "visible"),
            f"{decision_name} must be gated by its unlocking focus {focus}",
        )
    for decision_name in ("NAM_island_convoy_service", "NAM_south_convoy_interdiction"):
        decision = named_block(decisions, decision_name)
        check(
            "cost = 0" in decision and "custom_cost_text" in decision and "hidden_trigger" in decision,
            f"{decision_name} must recheck its custom price before the single debit",
        )
    check(
        "NAM_overseas_districts = {" in categories
        and "ADISCORD_nam_resource_war_compromise" in named_block(categories, "NAM_national_programmes"),
        "the islands category and the defeat-route programme visibility are required",
    )
    for event_id in (
        "ADISCORD_nam_oil.1",
        "ADISCORD_nam_oil.2",
        "ADISCORD_nam_oil.4",
        "ADISCORD_nam_oil.5",
        "ADISCORD_nam_oil.6",
        "ADISCORD_nam_oil.7",
        "ADISCORD_nam_oil.10",
    ):
        check(
            re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", events) is not None,
            f"{event_id} is not defined",
        )
    entry = next(
        (
            block
            for block in typed_blocks(events, "country_event")
            if re.search(r"(?m)^\s*id\s*=\s*ADISCORD_nam_resource_war\.1\s*$", block)
        ),
        "",
    )
    check(
        "global.NAM_rw_entry_dispatches" in entry
        and "value = 0 compare = less_than_or_equals" in entry
        and entry.count("NAM_rw_count_entry_dispatch = yes") == 3,
        "the entry event must stop the war only when no other dispatch is queued",
    )
    check(
        "NAM_rw_time_bought_active = yes" in entry
        and "set_global_flag = ADISCORD_nam_resource_war_time_deferred" in entry
        and "days = 75" in entry,
        "the entry event must honour Azhar's delay and move the backstop by 75 days once",
    )
    check(
        "NAM_rw_count_entry_dispatch = yes" in named_block(effects, "ADISCORD_nam_resource_war_schedule")
        and "NAM_rw_count_entry_dispatch = yes" in named_block(effects, "NAM_rw_tension_clamp"),
        "every scheduled entry dispatch must be counted",
    )


FAVOUR_FOCUSES = {
    "nam": "NAM_namestnik_circuits",
    "oil": "NAM_supports_oil_compact",
    "dist": "NAM_district_assemblies",
    "garr": "NAM_garrison_assembly",
    "trade": "NAM_supports_export_houses",
}


def event_block(events: str, event_id: str) -> str:
    return next(
        (
            block
            for block in typed_blocks(events, "country_event")
            if re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block)
        ),
        "",
    )


def check_ladder(
    effects: str,
    triggers: str,
    on_actions: str,
    decisions: str,
    categories: str,
    events: str,
    hostilities: str,
) -> None:
    """Ladder of seals, rivals, underground, endings, memoirs and the war of return."""
    bop = read("common/bop/NAM.txt")
    check(
        "NAM_ladder_bop = {" in bop
        and "left_side = NAM_bop_vertical" in bop
        and "right_side = NAM_bop_districts" in bop
        and bop.count("on_activate = { ADISCORD_economy_mark_dirty = yes }") == bop.count("range = {")
        and bop.count("on_deactivate = { ADISCORD_economy_mark_dirty = yes }") == bop.count("range = {"),
        "NAM_ladder_bop must exist and mark the economy dirty on every range change",
    )
    declare = named_block(effects, "NAM_ladder_declare_independence")
    check(
        "NAM_ladder_declare_independence = yes" in named_block(effects, "ADISCORD_nam_resource_war_schedule")
        and "NOT = { has_country_flag = NAM_independence_declared }" in declare
        and "NOT = { has_power_balance = { id = NAM_ladder_bop } }" in declare
        and declare.count("set_power_balance") == 1
        and "set_power_balance = { id = NAM_ladder_bop set_value = 0 }" in declare
        and "value = -0.25" in declare
        and "value = 0.25" in declare
        and "NOT = { has_variable = NAM_underground }" in declare
        and "id = ADISCORD_nam_resource_war.80" in declare,
        "the declaration must create the ladder once, apply the course shift and open .80",
    )
    centre = event_block(events, "ADISCORD_nam_resource_war.80")
    colony_close = named_block(effects, "NAM_colony_close")
    check(
        "NAM_colony_close = yes" in named_block(centre, "immediate")
        and "id = ADISCORD_nam_groups.12" in named_block(centre, "option")
        and "set_country_flag = NAM_center_vanished" in colony_close
        and "mark_focus_tree_layout_dirty = yes" in colony_close
        and "fire_only_once = yes" in centre,
        "the vanished-centre event must close the colony, reveal the tree and open the declaration .12",
    )
    runtime = "\n".join((effects, events, decisions))
    check(
        runtime.count("set_power_balance") == 1,
        "only the declaration may set the ladder balance; later writers add to it",
    )
    declaration_event = event_block(events, "ADISCORD_nam_groups.12")
    check(
        "value = -0.15" in declaration_event and "value = 0.15" in declaration_event,
        "the declaration answers must tilt the ladder by 0.15",
    )
    monthly = named_block(effects, "NAM_groups_monthly")
    check(
        "value = 0.5" in monthly and "value = 1 }" not in monthly,
        "pillar drift must be half a point a month",
    )
    for group, focus in FAVOUR_FOCUSES.items():
        decision = named_block(decisions, f"NAM_favour_{group}")
        check(
            f"has_completed_focus = {focus}" in named_block(decision, "visible")
            and f"var = NAM_grp_{group}_support value = 70 compare = greater_than_or_equals" in decision
            and f"idea = NAM_favour_{group}_idea" in decision
            and "days = 120" in decision
            and "NAM_favour_pay_support = yes" in decision
            and "days_re_enable" in decision,
            f"NAM_favour_{group} lacks its focus gate, 70-support price or 120-day favour",
        )
    tokens = read("common/synchronized_dynamic_tokens/ADISCORD_tokens.txt")
    for mission in ("NAM_rival_demand", "NAM_war_of_return_deadline"):
        check(
            re.search(rf"(?m)^{mission}\s*$", tokens) is not None,
            f"{mission} is not registered in the synchronized token file",
        )
    rival_mission = named_block(decisions, "NAM_rival_demand")
    check(
        "NAM_rival_demand_met = yes" in named_block(rival_mission, "available")
        and "days_mission_timeout = 60" in rival_mission
        and "NAM_rival_demand_paid = yes" in rival_mission
        and "NAM_rival_refuse = yes" in named_block(rival_mission, "timeout_effect"),
        "the rival demand must succeed on its term and count its deadline as a refusal",
    )
    deadline = named_block(decisions, "NAM_war_of_return_deadline")
    check(
        "available = { hidden_trigger = { always = no } }" in deadline
        and "days_mission_timeout = 365" in deadline,
        "the war-of-return deadline must be a 365-day timeout-only mission",
    )
    refuse = named_block(effects, "NAM_rival_refuse")
    check(
        "NAM_rival_current_heard = no" in refuse
        and "NAM_rival_current_pillar_broken = yes" in refuse
        and refuse.find("NAM_rival_current_pillar_broken = yes") < refuse.find("NAM_rival_pillar_add = yes")
        and "NAM_rival_open_coup = yes" in refuse,
        "an unheard rival of a pillar already below 25 must open the coup on refusal",
    )
    rivals_monthly = named_block(effects, "NAM_rivals_monthly")
    check(
        "has_country_flag = NAM_coup_pending" in rivals_monthly
        and "clr_country_flag = NAM_coup_pending" in rivals_monthly
        and "flag = NAM_rival_cooldown value = 1 days = 240" in rivals_monthly
        and "id = ADISCORD_nam_groups.20" in rivals_monthly,
        "the rival cycle must wait 240 days and consume the Night of Seals",
    )
    coup = named_block(effects, "NAM_coup_install")
    check(
        coup.count("add_country_leader_role") == 4
        and coup.count("promote_leader = yes") == 4
        and coup.count("ideology = etatism_ideology") == 4
        and "set_country_flag = NAM_coup_succeeded" in coup,
        "every coup leader must take an etatist leader role",
    )
    ladder_monthly = named_block(effects, "NAM_ladder_monthly")
    check(
        "NAM_ladder_monthly = yes" in named_block(on_actions, "on_monthly_NAM")
        and "every_country" not in ladder_monthly
        and "every_country" not in named_block(effects, "NAM_underground_monthly")
        and "every_country" not in rivals_monthly,
        "ladder upkeep must run in on_monthly_NAM without world scans",
    )
    check(
        "NOT = { has_country_flag = NAM_veter_amnesty }"
        in named_block(effects, "ADISCORD_nam_resource_war_start_mainland_rebellion")
        and "NOT = { has_country_flag = NAM_veter_amnesty }"
        in named_block(event_block(events, "ADISCORD_nam_resource_war.2"), "trigger")
        and "set_country_flag = NAM_veter_amnesty" in named_block(effects, "NAM_veter_amnesty")
        and "recruit_character = NAM_Yaroslav_Veter" in named_block(effects, "NAM_veter_amnesty"),
        "the amnesty must recruit Veter for NAM and prevent SLF for good",
    )
    clamp = named_block(effects, "NAM_underground_clamp")
    check(
        "min = 0" in clamp and "max = 100" in clamp and "has_country_flag = NAM_veter_amnesty" in clamp,
        "the underground clamp must hold 0-100 and keep an amnestied network at 0",
    )
    for ending, tag, spirit in (
        ("NAM_apply_ending_iron", "NAM_iron_ladder", "NAM_spirit_iron_ladder"),
        ("NAM_apply_ending_service", "NAM_service_republic", "NAM_spirit_service_republic"),
        ("NAM_apply_ending_federation", "NAM_federation", "NAM_spirit_federation"),
        ("NAM_apply_ending_oil_union", "NAM_oil_union", "NAM_spirit_oil_union"),
    ):
        block = named_block(effects, ending)
        check(
            f"set_cosmetic_tag = {tag}" in block
            and f"add_ideas = {spirit}" in block
            and "has_country_flag = NAM_coup_succeeded" in block
            and "set_country_flag = NAM_ladder_settled" in block,
            f"{ending} must keep a coup leader, set its name and its spirit",
        )
        for size in ("", "medium/", "small/"):
            check(
                (ROOT / "gfx" / "flags" / f"{size}{tag}.tga").exists(),
                f"missing flag gfx/flags/{size}{tag}.tga",
            )
    dispatcher = event_block(events, "ADISCORD_nam_memoir.99")
    check(
        "hidden = yes" in dispatcher and "NAM_memoir_dispatch = yes" in dispatcher,
        "the memoir dispatcher must be a hidden event",
    )
    memoir = named_block(effects, "NAM_memoir_dispatch")
    check(
        "is_ai = no" in memoir and "days = 90" in memoir and "NAM_memoir_next < 6" in memoir,
        "memoirs reach human rulers every 90 days, five chapters at most",
    )
    for chapter in range(1, 6):
        page = event_block(events, f"ADISCORD_nam_memoir.{chapter}")
        second = event_block(events, f"ADISCORD_nam_memoir.{chapter + 10}")
        check(
            "is_ai = no" in page
            and page.count("option = {") == 2
            and f"id = ADISCORD_nam_memoir.{chapter + 10}" in page
            and second.count("option = {") == 1
            and "country_event" not in named_block(second, "option"),
            f"memoir chapter {chapter} needs a continuation page and a full exit on both pages",
        )
    for number in range(1, 7):
        check(
            bool(event_block(events, f"ADISCORD_nam_archive.{number}")),
            f"ADISCORD_nam_archive.{number} is not defined",
        )
    start = named_block(effects, "NAM_war_of_return_start")
    close = named_block(effects, "NAM_war_of_return_close")
    release = named_block(effects, "NAM_wor_release_participants")
    check(
        "NAM_war_of_return_can_start = yes" in start
        and "declare_war_on" in start
        and "NAM_wor_call_participants = yes" in start
        and "add_to_war" in named_block(effects, "NAM_wor_call_participants")
        and "ADISCORD_nam_resource_war_reserve_major = yes" in start
        and "activate_mission = NAM_war_of_return_deadline" in start
        and "id = ADISCORD_nam_resource_war.61 days = 365" in start,
        "the war of return must declare one coalition war with its temporary majors and deadline",
    )
    check(
        -1
        < close.find("set_global_flag = NAM_war_of_return_resolved")
        < close.find("NAM_wor_release_participants = yes")
        and "white_peace" in release
        and "ADISCORD_nam_resource_war_release_major = yes" in release
        and "ADISCORD_nam_resource_war_release_major = yes" in close
        and "remove_mission = NAM_war_of_return_deadline" in close,
        "every war-of-return exit must resolve first, then end the war and release majors",
    )
    for resolver in (
        "NAM_war_of_return_resolve_victory",
        "NAM_war_of_return_resolve_front",
        "NAM_war_of_return_close_external",
    ):
        check(
            "NAM_war_of_return_close = yes" in named_block(effects, resolver),
            f"{resolver} must run the shared war-of-return cleanup",
        )
    check(
        "NAM_war_of_return_close = yes"
        in named_block(effects, "ADISCORD_nam_resource_war_resolve_coalition_victory"),
        "a lost war of return must close the campaign before the partition",
    )
    check(
        on_actions.count("NAM_war_of_return_close_external = yes") >= 3
        and "NAM_war_of_return_resolve_victory = yes" in on_actions
        and "NAM_wor_record_capitulation = yes" in on_actions,
        "the scripted peace hooks must dispatch the war of return",
    )
    delivery = named_block(effects, "NAM_deliver_mobilisation_orders")
    spawn = named_block(effects, "NAM_order_spawn_one")
    check(
        "capital_scope" not in delivery
        and delivery.count("NAM_order_spawn_one = yes") == 4
        and "has_full_control_of_state" in spawn
        and "is_fully_controlled_by = NAM" in spawn
        and "log = " in spawn
        and "NAM_order_unlock_templates = yes" in delivery,
        "paid formations must spawn one by one in a fully held Svetlogorsk state and be logged",
    )
    check(
        "NAM_order_ensure_templates = yes" in named_block(effects, "NAM_order_register")
        and -1 < hostilities.find("NAM_order_ensure_templates = yes")
        < hostilities.find('load_oob = "NAM_resource_war"')
        < hostilities.find("NAM_deliver_mobilisation_orders = yes"),
        "the order templates must exist from the first order and before the baseline OOB",
    )
    templates = named_block(effects, "NAM_order_ensure_templates")
    check(
        templates.count("ADISCORD_mechanized_infantry = {") == 4
        and "has_tech = ADISCORD_tech_armored_carrier_program" in templates
        and "set_technology" in named_block(effects, "NAM_order_grant_motor_technology")
        and "NAM_order_grant_motor_technology = yes" in named_block(decisions, "NAM_order_motor_column"),
        "the motorised order must grant the carrier programme before its mechanised template",
    )
    close_preparation = named_block(effects, "NAM_rw_close_preparation")
    check(
        "id = ADISCORD_nam_resource_war.24" in close_preparation
        and close_preparation.find("ADISCORD_nam_resource_war.24")
        < close_preparation.find("NAM_refund_mobilisation_orders = yes"),
        "an unrequested refund of paid orders must be announced with its amounts",
    )
    check(
        "NAM_rw_clear_punishment = yes" in on_actions,
        "annexation must clear the punitive spirits",
    )


CUSTOM_COST_DECISIONS = {
    "NAM_wrk_fuel_shipment": "NAM_cost_wrk_fuel_shipment",
    "NAM_wrk_trade_concession": "NAM_cost_wrk_trade_concession",
    "NAM_counterinsurgency_sweep": "NAM_cost_counterinsurgency_sweep",
    "NAM_pirate_raid_lane_oil": "NAM_cost_pirate_raid",
    "NAM_pirate_raid_lane_coast": "NAM_cost_pirate_raid",
    "NAM_pirate_raid_lane_strait": "NAM_cost_pirate_raid",
    "NAM_pirate_raid_lane_crossing": "NAM_cost_pirate_raid",
    "NAM_pirate_buy_arms": "NAM_cost_pirate_arms",
    "NAM_pirate_buy_heavy_arms": "NAM_cost_pirate_heavy_arms",
    "NAM_pirate_buy_convoys": "NAM_cost_pirate_convoys",
    "NAM_pirate_fence_loot": "NAM_cost_pirate_fence",
    "NAM_exile_drill": "NAM_cost_exile_drill",
    "NAM_order_marines": "NAM_cost_order_marines",
    "NAM_corp_labour_contract": "NAM_cost_corp_labour",
    "NAM_corp_innovation_park": "NAM_cost_corp_park",
    "NAM_corp_buy_arms": "NAM_cost_corp_arms",
    "NAM_order_marines_corp": "NAM_cost_order_marines_corp",
}
# Humanist decisions and the focus that opens each (M10).
CORP_DECISION_FOCUSES = {
    "NAM_corp_charter_free_zone": "NAM_hum_free_zones",
    "NAM_corp_court_investors": "NAM_hum_open_doors",
    "NAM_corp_sell_steel": "NAM_hum_steel_exchange",
    "NAM_corp_innovation_park": "NAM_hum_innovation_parks",
    "NAM_corp_labour_contract": "NAM_hum_labour_bureau",
    "NAM_corp_buy_arms": "NAM_hum_credit_arms",
    "NAM_order_marines_corp": "NAM_hum_marine_contracts",
    "NAM_federal_council_session": "NAM_hum_union_council",
    "NAM_radical_labour_camp": "NAM_rad_labour_camps",
    "NAM_radical_strip_state": "NAM_rad_spoils_of_return",
    "NAM_rad_terror_campaign": "NAM_rad_martial_law",
    "NAM_rad_garrison_order": "NAM_rad_garrison_belt",
    "NAM_hum_federal_treaty": "NAM_hum_federal_treaties",
    "NAM_hum_reconstruction_fund": "NAM_hum_harbour_rebuilding",
    "NAM_corp_board_arbitration": "NAM_board_constitution",
    "NAM_corp_charter_renewal": "NAM_board_shareholders",
    "NAM_corp_auction_district": "NAM_board_district_auction",
}
GREAT_WAR_TARGETS = ("EFL", "AZH", "RHM", "SDR", "KDR")


def check_exile_revolution(
    effects: str,
    triggers: str,
    on_actions: str,
    decisions: str,
    categories: str,
    events: str,
    loc: str,
) -> None:
    """M10: the island council, the two courses, the corporations and the great war."""
    flight = event_block(events, "ADISCORD_nam_resource_war.81")
    revolution = event_block(events, "ADISCORD_nam_resource_war.100")
    revolution_open = named_block(triggers, "NAM_exile_revolution_open")
    check(
        "NAM_exile_overthrow_namestnik" not in decisions
        and "NAM_exile_overthrow_namestnik" not in loc
        and flight.count("option = {") == 2
        and flight.count("id = ADISCORD_nam_resource_war.100") == 2
        and "timeout_days" in flight
        and "has_completed_focus" not in revolution_open
        and "has_global_flag = ADISCORD_nam_resource_war_island_exile" in revolution_open
        and "NAM_exile_revolution_open = yes" in named_block(revolution, "trigger")
        and "timeout_days" in revolution
        and revolution.count("option = {") == 2,
        "every answer of the flight .81 must convene the island council .100, which needs no focus or decision",
    )
    options = revolution.split("option = {")[1:]
    check(
        len(options) == 2
        and -1 < options[0].find("NAM_exile_choose_radical = yes") < options[0].find("tree = NAM_exile_radical_focus")
        and -1 < options[1].find("NAM_exile_choose_humanist = yes") < options[1].find("tree = NAM_exile_humanist_focus")
        and all("keep_completed = yes" in option for option in options),
        "each council answer, the unattended junta first, must set its flag and then load its tree",
    )
    radical = named_block(effects, "NAM_exile_choose_radical")
    humanist = named_block(effects, "NAM_exile_choose_humanist")
    check(
        "set_country_flag = NAM_exile_radical" in radical
        and "character = NAM_Rostislav_Karamyshev" in radical
        and "set_country_flag = NAM_exile_humanist" in humanist
        and "character = NAM_Yaroslav_Veter" in humanist
        and "ideology = humanism_ideology" in humanist
        and "NAM_corp_initialize = yes" in humanist,
        "each course must install its leader and set its flag",
    )
    check(
        "has_country_flag = NAM_exile_radical" in named_block(triggers, "NAM_piracy_open")
        and "NAM_exile_return_programme_open = yes" in named_block(triggers, "NAM_marine_order_can_place")
        and "NAM_exile_return_programme_open = yes" in named_block(named_block(decisions, "NAM_exile_drill"), "visible")
        and "NAM_exile_drill_currency_ready = yes" in named_block(decisions, "NAM_exile_drill")
        and "has_country_flag = NAM_exile_humanist" in named_block(effects, "NAM_exile_drill_refund")
        and "has_country_flag = NAM_exile_humanist" in named_block(effects, "NAM_marine_orders_refund"),
        "piracy is the junta's; drill and marines serve both courses and refund in the paid currency",
    )
    for decision_name, focus in CORP_DECISION_FOCUSES.items():
        check(
            f"has_completed_focus = {focus}" in named_block(named_block(decisions, decision_name), "visible"),
            f"{decision_name} must open with {focus}",
        )
    monthly = named_block(effects, "NAM_corp_monthly")
    check(
        "NAM_corp_monthly = yes" in named_block(on_actions, "on_monthly_NAM")
        and "every_country" not in monthly
        and "every_owned_state" not in monthly
        and "NAM_corp_count_zones = yes" in monthly
        and "NAM_corp_queue_takeover = yes" in monthly
        and "max = 100" in named_block(effects, "NAM_corp_influence_clamp")
        and "NAM_corp_check_thresholds = yes" in named_block(effects, "NAM_corp_influence_clamp")
        and all(
            f"id = ADISCORD_nam_resource_war.{number}" in named_block(effects, name)
            for number, name in (
                (101, "NAM_corp_check_thresholds"),
                (102, "NAM_corp_check_thresholds"),
                (103, "NAM_corp_queue_takeover"),
            )
        ),
        "the corporations must advance in on_monthly_NAM over the fixed islands and open their events",
    )
    takeover = named_block(effects, "NAM_corp_takeover")
    check(
        "set_cosmetic_tag = NAM_corporate_state" in takeover
        and "character = NAM_Mark_Olshansky" in takeover
        and "modifier = NAM_corporate_board_state" in takeover
        and -1
        < takeover.find("set_country_flag = NAM_corp_takeover")
        < takeover.find("tree = NAM_exile_corporate_focus")
        and "keep_completed = yes" in takeover,
        "the takeover must install the board, the cosmetic tag, the island boards and the corporate tree",
    )
    for event_id in ("101", "102"):
        block = event_block(events, f"ADISCORD_nam_resource_war.{event_id}")
        check(
            block.count("option = {") == 3 and block.count("NAM_corp_close_event = yes") == 3,
            f"corporate event .{event_id} needs three answers that each close the event",
        )
    start = named_block(effects, "NAM_war_of_return_start")
    register = named_block(effects, "NAM_wor_register_target")
    coalition = named_block(effects, "NAM_wor_form_coalition")
    check(
        "EFL = { NAM_wor_register_target = yes }" in start
        and "AZH = { NAM_wor_register_target = yes }" in start
        and "RHM = { NAM_wor_register_target = yes }" not in start
        and register.find("ADISCORD_release_non_participating_minor_optimization = yes")
        < register.find("set_country_flag = NAM_wor_participant")
        and "template = faction_template_ADISCORD_standard" in coalition
        and "dismantle_faction = yes" in named_block(effects, "NAM_wor_release_participants")
        and "NAM_wor_exile_war_ready = yes" in named_block(triggers, "NAM_war_of_return_can_start"),
        "the exile war must fight Eflor and Azhar in one temporary coalition and dismantle it",
    )
    victory = named_block(effects, "NAM_war_of_return_resolve_victory")
    check(
        victory.find("NAM_wor_copy_participants = yes")
        < victory.find("NAM_war_of_return_close = yes")
        < victory.find("NAM_wor_settle_list_by_route = yes")
        and "NAM_consolidation_begin = yes" in victory
        and "NAM_wor_radical_annex = yes" in named_block(effects, "NAM_wor_settle_list_by_route")
        and "NAM_wor_federal_district_join = yes" in named_block(effects, "NAM_wor_settle_list_by_route")
        and "autonomy_state = autonomy_NAM_federal_district" in named_block(effects, "NAM_wor_federal_district_join")
        and "set_state_flag = NAM_conquered_state" in named_block(effects, "NAM_wor_take_state")
        and "NAM_war_of_return_close = yes" in named_block(effects, "NAM_war_of_return_resolve_defeat")
        and "NAM_war_of_return_resolve_defeat = yes" in read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"),
        "the exile war must settle Eflor and Azhar by the course, then open the consolidation",
    )
    # Each exile tree opens the drill and the humanist marine contracts.
    drill_unlocked = named_block(triggers, "NAM_exile_drill_unlocked")
    check(
        all(
            f"has_completed_focus = {focus}" in drill_unlocked
            for focus in ("NAM_exile_general_staff", "NAM_hum_citizen_army", "NAM_hum_company_guard")
        )
        and "NAM_exile_drill_unlocked = yes" in named_block(named_block(decisions, "NAM_exile_drill"), "visible")
        and "NAM_exile_drill_unlocked = yes" in named_block(categories, "NAM_exile_politics")
        and "has_completed_focus = NAM_board_landing_contracts"
        in named_block(named_block(decisions, "NAM_order_marines_corp"), "visible"),
        "the drill and the humanist marines must open in the junta's, the humanists' and the boards' trees",
    )
    # A deadline front settles the return by the homeland it leaves; a failed
    # war may be renewed after its recovery, and a stale deadline is ignored.
    front = named_block(effects, "NAM_war_of_return_resolve_front")
    external = named_block(effects, "NAM_war_of_return_close_external")
    great_front = named_block(effects, "NAM_great_war_resolve_front")
    renew = named_block(decisions, "NAM_exile_renew_war_of_return")
    renew_great = named_block(decisions, "NAM_renew_great_war")
    check(
        all(f"owns_state = {state}" in named_block(triggers, "NAM_wor_front_return_held") for state in (67, 688, 689, 690, 719, 700))
        and -1
        < front.find("NAM_wor_settle_front_states = yes")
        < front.find("NAM_wor_front_return_held = yes")
        < front.find("set_global_flag = NAM_war_of_return_won")
        < front.find("NAM_consolidation_begin = yes")
        and "NAM_wor_front_return_held = yes" in external
        and "set_global_flag = NAM_war_of_return_won" in external
        and re.search(r"has_global_flag = NAM_wor_exile_war\b", named_block(triggers, "NAM_wor_exile_war_ready")) is None
        and "has_global_flag = NAM_war_of_return_won" in named_block(triggers, "NAM_wor_exile_war_ready")
        and re.search(r"has_global_flag = NAM_wor_exile_war\b", named_block(triggers, "NAM_exile_return_programme_open")) is None
        and "flag = NAM_wor_recovery" in named_block(effects, "NAM_war_of_return_close")
        and "NAM_war_of_return_start = yes" in renew
        and "has_global_flag = NAM_wor_recovery" in renew
        and "flag = NAM_wor_deadline_armed" in named_block(effects, "NAM_war_of_return_start")
        and "has_global_flag = NAM_wor_deadline_armed"
        in named_block(event_block(events, "ADISCORD_nam_resource_war.61"), "trigger"),
        "the exile war must count a homeland front as won and let a failed war be renewed after recovery",
    )
    check(
        "add_to_temp_variable = { var = NAM_wor_front_net value = 1 }" in named_block(effects, "NAM_wor_settle_front_states")
        and "subtract_from_temp_variable = { var = NAM_wor_front_net value = 1 }"
        in named_block(effects, "NAM_wor_settle_front_states")
        and -1
        < great_front.find("NAM_wor_settle_front_states = yes")
        < great_front.find("NAM_wor_front_net > 0")
        < great_front.find("set_global_flag = NAM_great_war_won")
        and "NAM_great_war_started" not in named_block(triggers, "NAM_great_war_can_start")
        and "has_global_flag = NAM_great_war_won" in named_block(triggers, "NAM_great_war_can_start")
        and "flag = NAM_great_war_recovery" in named_block(effects, "NAM_great_war_close")
        and "clr_global_flag = NAM_great_war_resolved" in named_block(effects, "NAM_great_war_start")
        and "flag = NAM_great_war_deadline_armed" in named_block(effects, "NAM_great_war_start")
        and "has_global_flag = NAM_great_war_deadline_armed"
        in named_block(event_block(events, "ADISCORD_nam_resource_war.106"), "trigger")
        and "NAM_great_war_start = yes" in renew_great
        and "has_global_flag = NAM_great_war_recovery" in renew_great,
        "the great war must count a southward front as won and let a fruitless war be renewed after recovery",
    )
    for key in (
        "NAM_exile_renew_war_of_return",
        "NAM_exile_renew_war_of_return_desc",
        "NAM_renew_great_war",
        "NAM_renew_great_war_desc",
        "NAM_wor_recovery_tt",
        "NAM_great_war_recovery_tt",
        "ADISCORD_nam_resource_war.62.d_held_exile",
        "ADISCORD_nam_resource_war.107.d_front_won",
    ):
        check(
            re.search(rf"(?m)^\s*{re.escape(key)}:", loc) is not None,
            f"missing localisation key {key}",
        )
    # Consolidation between the exile war and the great war.
    consolidation = named_block(effects, "NAM_consolidation_monthly")
    check(
        "NAM_consolidation_monthly = yes" in named_block(on_actions, "on_monthly_NAM")
        and "every_country" not in consolidation
        and "max = 100" in named_block(effects, "NAM_consolidation_clamp")
        and "id = ADISCORD_nam_resource_war.104" in named_block(effects, "NAM_consolidation_open_incident")
        and "var = NAM_consolidation value = 70 compare = greater_than_or_equals" in named_block(triggers, "NAM_great_war_can_start"),
        "the consolidation must run monthly without world scans and gate the great war at 70",
    )
    incident = event_block(events, "ADISCORD_nam_resource_war.104")
    check(
        incident.count("option = {") == 6 and incident.count("NAM_consolidation_close_event = yes") == 6,
        "consolidation incident .104 needs three answers for each course that close the event",
    )
    # The great war: one war, one peace, temporary majors.
    great = named_block(effects, "NAM_great_war_start")
    great_close = named_block(effects, "NAM_great_war_close")
    check(
        "NAM_great_war_can_start = yes" in great
        and all(f"{tag} = {{ NAM_wor_register_target = yes }}" in great for tag in GREAT_WAR_TARGETS)
        and great.find("NAM_wor_form_coalition = yes") < great.find("declare_war_on")
        and "ADISCORD_nam_resource_war_reserve_major = yes" in great
        and "activate_mission = NAM_great_war_deadline" in great
        and "id = ADISCORD_nam_resource_war.106 days = 365" in great
        and -1
        < great_close.find("set_global_flag = NAM_great_war_resolved")
        < great_close.find("NAM_wor_release_participants = yes")
        and "ADISCORD_nam_resource_war_release_major = yes" in great_close
        and all(
            "NAM_great_war_close = yes" in named_block(effects, name)
            for name in (
                "NAM_great_war_resolve_victory",
                "NAM_great_war_resolve_defeat",
                "NAM_great_war_resolve_front",
                "NAM_great_war_close_external",
            )
        )
        and "set_global_flag = NAM_great_war_won" in named_block(effects, "NAM_great_war_resolve_victory")
        and "NAM_great_war_resolve_victory = yes" in read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        and "NAM_great_war_resolve_defeat = yes" in read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        and read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt").count("NAM_great_war_close_external = yes") >= 3
        and re.search(r"(?m)^NAM_great_war_deadline\s*$", read("common/synchronized_dynamic_tokens/ADISCORD_tokens.txt")) is not None,
        "the great war must wake its targets, unite them, close on every path and settle through the dispatcher",
    )
    # The corporate state's districts.
    check(
        "NAM_corp_assign_district = yes" in named_block(effects, "NAM_corp_takeover")
        and "NAM_corp_districts_monthly = yes" in named_block(effects, "NAM_corp_monthly")
        and "id = ADISCORD_nam_resource_war.108" in named_block(effects, "NAM_corp_open_dispute")
        and all(
            f"modifier = NAM_corp_owner_{n}_district" in named_block(effects, "NAM_corp_district_apply")
            for n in range(1, 7)
        )
        and all(
            f"set_cosmetic_tag = {tag}_NAM_corp_{n}" in named_block(effects, "NAM_corp_district_set_name")
            for tag in GREAT_WAR_TARGETS
            for n in range(1, 7)
        )
        and all(
            named_block(decisions, name)
            for name in ("NAM_corp_auction_district", "NAM_corp_board_arbitration", "NAM_corp_charter_renewal")
        ),
        "every corporate district needs its owner, profile, name and the board's decisions",
    )
    for tag in GREAT_WAR_TARGETS:
        for n in range(1, 7):
            for size in ("", "medium/", "small/"):
                check(
                    (ROOT / "gfx" / "flags" / f"{size}{tag}_NAM_corp_{n}.tga").exists(),
                    f"missing flag gfx/flags/{size}{tag}_NAM_corp_{n}.tga",
                )
            check(
                re.search(rf"(?m)^\s*{tag}_NAM_corp_{n}:", loc) is not None,
                f"missing localisation key {tag}_NAM_corp_{n}",
            )
    autonomy = read("common/autonomous_states/ADISCORD_south_final_war_subjects.txt")
    check(
        "id = autonomy_NAM_federal_district" in autonomy
        and "resources_to_overlord_factor" in autonomy,
        "the federal district autonomy must hand resources, factories and recruits to Svetlogorye",
    )
    for tag in ("NAM_corporate_state",) + tuple(f"{t}_NAM_federal_district" for t in GREAT_WAR_TARGETS):
        for size in ("", "medium/", "small/"):
            check(
                (ROOT / "gfx" / "flags" / f"{size}{tag}.tga").exists(),
                f"missing flag gfx/flags/{size}{tag}.tga",
            )
        for suffix in ("", "_ADJ", "_DEF"):
            check(
                re.search(rf"(?m)^\s*{re.escape(tag + suffix)}:", loc) is not None,
                f"missing localisation key {tag + suffix}",
            )
    for key in (
        "NAM_exile_politics",
        "NAM_free_zones",
        "NAM_southern_lands",
        "ADISCORD_nam_resource_war.100.d",
        "ADISCORD_nam_resource_war.103.d",
        "ADISCORD_nam_resource_war.60.d_exile",
        "ADISCORD_nam_resource_war.105.d",
        "ADISCORD_nam_resource_war.107.d_won_federal",
        "ADISCORD_nam_resource_war.108.d",
        "NAM_consolidation",
        "ADISCORD_nam_resource_war.62.d_won_radical",
        "ADISCORD_nam_resource_war.62.d_won_federal",
        "ADISCORD_nam_resource_news.8.d",
        "ADISCORD_nam_resource_news.9.d_federal",
        "autonomy_NAM_federal_district",
        "NAM_Rostislav_Karamyshev",
        "NAM_Mark_Olshansky",
    ):
        check(
            re.search(rf"(?m)^\s*{re.escape(key)}:", loc) is not None,
            f"missing localisation key {key}",
        )
# Shipping lanes of NAM_pirate_raid_lane_<id> in their lane-input order; the
# piracy map builder draws the same lanes.
PIRATE_LANES = ("oil", "coast", "strait", "crossing")


def check_colony_and_exile(
    effects: str,
    triggers: str,
    on_actions: str,
    decisions: str,
    categories: str,
    events: str,
    loc: str,
) -> None:
    """Colony phase, the active underground, the flight to the islands and piracy."""
    check(
        "visible = { NAM_colony_phase = yes }" in named_block(categories, "NAM_colony")
        and "visible = { NAM_piracy_open = yes }" in named_block(categories, "NAM_piracy")
        and "NOT = { has_country_flag = NAM_center_vanished }" in named_block(triggers, "NAM_colony_phase"),
        "the colony category must close with the centre and the piracy category open in exile",
    )
    monthly = named_block(on_actions, "on_monthly_NAM")
    check(
        all(
            f"{call} = yes" in monthly
            for call in ("NAM_colony_monthly", "NAM_underground_monthly", "NAM_pirate_monthly")
        )
        and "NAM_underground_monthly" not in named_block(effects, "NAM_ladder_monthly")
        and all(
            "every_country" not in named_block(effects, name)
            for name in (
                "NAM_colony_monthly",
                "NAM_underground_monthly",
                "NAM_underground_sabotage_roll",
                "NAM_pirate_monthly",
            )
        ),
        "colony income, the underground and piracy must run in on_monthly_NAM without world scans",
    )
    groups_init = named_block(effects, "NAM_groups_initialize")
    check(
        "NOT = { has_variable = NAM_underground }" in groups_init
        and "var = NAM_underground value = 25" in groups_init
        and "NAM_wrk_trade_refresh = yes" in groups_init,
        "the startup must seed the underground and the trade level without overwriting focus deltas",
    )
    clamp = named_block(effects, "NAM_underground_clamp")
    thresholds = named_block(effects, "NAM_underground_check_thresholds")
    check(
        "NAM_underground_check_thresholds = yes" in clamp
        and all(
            f"id = ADISCORD_nam_resource_war.{number}" in thresholds for number in (82, 83, 84)
        )
        and "NAM_underground_active = yes" in thresholds,
        "the underground clamp must open the 40/60/80 events only while the network is active",
    )
    sabotage = named_block(effects, "NAM_underground_sabotage_roll")
    check(
        all(f"id = ADISCORD_nam_resource_war.{number}" in sabotage for number in (85, 86, 87))
        and "flag = NAM_ug_sabotage_cooldown" in sabotage,
        "sabotage must draw one of its three events under a cooldown",
    )
    for event_id in ("82", "83", "84", "85", "86", "87"):
        block = event_block(events, f"ADISCORD_nam_resource_war.{event_id}")
        check(
            block.count("option = {") == 3
            and block.count("NAM_underground_close_event = yes") == 3,
            f"underground event .{event_id} needs three answers that each close the event",
        )
    coalition = named_block(effects, "ADISCORD_nam_resource_war_resolve_coalition_victory")
    check(
        -1
        < coalition.find("NAM_rw_exile_evacuate = yes")
        < coalition.find("ADISCORD_nam_resource_war_end_all_wars = yes"),
        "the evacuation must run while the divisions still stand on the mainland",
    )
    evacuate = named_block(effects, "NAM_rw_exile_evacuate")
    abandon = named_block(effects, "NAM_rw_exile_abandon_state")
    embark = named_block(effects, "NAM_rw_exile_embark_state")
    damage = named_block(effects, "NAM_rw_exile_damage_army")
    check(
        "value = 0.35" in evacuate
        and "min = 1" in evacuate
        and -1
        < evacuate.find("NAM_rw_exile_move_capital = yes")
        < evacuate.find("719 = { NAM_rw_exile_abandon_state = yes }")
        < evacuate.find("700 = { NAM_rw_exile_abandon_state = yes }")
        < evacuate.find("delete_unit_template_and_units")
        < evacuate.find("NAM_rw_exile_embark_state = yes")
        < evacuate.find("NAM_rw_exile_damage_army = yes")
        and "value = -0.65" in evacuate
        and "log = " in evacuate,
        "the evacuation must keep 35% of the real divisions, leave the harbour last, embark the survivors, "
        "damage them, dump 65% and log the counts",
    )
    check(
        "check_variable = { NAM_exile_to_cut > 0 }" in named_block(abandon, "if")
        and 'change_division_template = { division_template = "Abandoned Columns" }' in abandon
        and "OWNER = { tag = NAM }" in abandon
        and embark.count("teleport_armies = {") == 7
        and embark.count("limit = { tag = NAM }") == 7
        and damage.count("str_damage = 0.45") == 7
        and damage.count("army = yes") == 7
        and damage.count("navy = no") == 7
        and all(f"state = {state}" in damage for state in range(225, 232)),
        "abandoned divisions must be counted inside the loop body, survivors must move to the island "
        "capital and every island garrison must lose 45% strength",
    )
    exile = named_block(effects, "NAM_rw_settle_island_exile")
    check(
        all(f"{state} = {{ NAM_rw_exile_scorch_state = yes }}" in exile for state in (67, 688, 689, 690, 719, 700))
        and "NAM_rw_exile_land_remnants" not in effects
        and "NAM_pirate_initialize = yes" in exile
        and "id = ADISCORD_nam_resource_war.81" in exile,
        "the exile must burn the ceded mainland, open piracy and report the flight without spawning remnants",
    )
    start = named_block(effects, "NAM_war_of_return_start")
    landing = named_block(effects, "NAM_wor_revenge_landing")
    check(
        -1 < start.find("declare_war_on") < start.find("NAM_wor_revenge_landing = yes")
        and "has_global_flag = ADISCORD_nam_resource_war_island_exile" in landing
        and -1
        < landing.find("teleport_armies")
        < landing.find("set_province_controller = 16716")
        < landing.find("prioritize_location = 16716")
        and "allow_spawning_on_enemy_provs = yes" not in landing
        and "var = NAM_marines_landed value = 2" in landing
        and "NAM_landing_third_division = yes" in landing
        and "var = NAM_marine_orders_paid value = 0" in landing
        and "id = ADISCORD_nam_resource_war.94" in landing,
        "the war of return from exile must open with a landing of two or three marine divisions",
    )
    check(
        "var = NAM_marine_orders_paid value = 3 compare = less_than" in named_block(triggers, "NAM_marine_order_can_place")
        and "var = NAM_pirate_raids_active value = 3 compare = less_than" in named_block(triggers, "NAM_pirate_slot_free")
        and "add_manpower = 4300" in named_block(effects, "NAM_marine_orders_refund"),
        "marine orders and raids must respect their caps and refund at the order price",
    )
    for decision_name, cost_key in CUSTOM_COST_DECISIONS.items():
        decision = named_block(decisions, decision_name)
        check(
            "cost = 0" in decision
            and f"custom_cost_text = {cost_key}" in decision
            and "hidden_trigger" in named_block(decision, "complete_effect"),
            f"{decision_name} must recheck its custom price before the single debit",
        )
        for suffix in ("", "_blocked", "_tooltip"):
            check(
                re.search(rf"(?m)^\s*{re.escape(cost_key + suffix)}:", loc) is not None,
                f"missing localisation key {cost_key + suffix}",
            )
    # Lane raids: the paid receipt settles at the end or refunds on cancel, and
    # the lane closes once no owner may be raided.
    settle_lanes = named_block(effects, "NAM_pirate_save_lane_victims")
    for number, lane in enumerate(PIRATE_LANES, 1):
        decision = named_block(decisions, f"NAM_pirate_raid_lane_{lane}")
        receipt = f"has_country_flag = NAM_pirate_at_sea_{lane}"
        check(
            f"NAM_pirate_lane_{lane}_open = no" in named_block(decision, "cancel_trigger")
            and receipt in named_block(decision, "remove_effect")
            and f"NAM_pirate_lane_input = {number}" in named_block(decision, "remove_effect")
            and receipt in named_block(decision, "cancel_effect")
            and "NAM_pirate_raid_release = yes" in named_block(decision, "cancel_effect")
            and f"set_country_flag = NAM_pirate_at_sea_{lane}" in named_block(decision, "complete_effect")
            and named_block(triggers, f"NAM_pirate_lane_{lane}_open")
            and named_block(triggers, f"NAM_pirate_lane_{lane}_alert")
            and f"NAM_pirate_lane_input = {number}" in settle_lanes,
            f"the {lane} lane raid must settle or refund its paid receipt against its own owners",
        )
    for key in (
        "NAM_colony",
        "NAM_colony_desc",
        "NAM_piracy",
        "NAM_piracy_desc",
        "ADISCORD_nam_resource_war.80.d",
        "ADISCORD_nam_resource_war.81.d",
        "ADISCORD_tech_svetlogorsk_marine_corps",
    ):
        check(
            re.search(rf"(?m)^\s*{re.escape(key)}:", loc) is not None,
            f"missing localisation key {key}",
        )


BORDER_BELT_STATES = (720, 721, 722, 701)
STANDOFF_FOCUS_BYPASS = (
    "AND = { has_global_flag = ADISCORD_vorkerland_collapse_wars_started "
    "NOT = { has_global_flag = ADISCORD_nam_resource_war_scheduled } }"
)


def check_settlement(
    effects: str,
    triggers: str,
    decisions: str,
    categories: str,
    events: str,
    loc: str,
) -> None:
    """Standoff at the deadline, Azhar treaty term, Veter refunds and route gates."""
    belt = named_block(triggers, "NAM_rw_holds_border_belt")
    check(
        all(f"controls_state = {state_id}" in belt for state_id in BORDER_BELT_STATES),
        "the border-belt trigger must read control of 720, 721, 722 and 701",
    )
    # The decisive ground ends the war for either side after a 7-day recheck.
    queue = named_block(effects, "NAM_rw_queue_front_check")
    resolution = named_block(effects, "ADISCORD_nam_resource_war_front_resolution")
    territorial = named_block(triggers, "NAM_rw_territorial_victory")
    coalition_ground = named_block(triggers, "NAM_rw_coalition_territorial_victory")
    check(
        "NAM_rw_territorial_victory = yes" in queue
        and "NAM_rw_coalition_territorial_victory = yes" in queue
        and "flag = NAM_rw_front_check_pending" in queue
        and "id = ADISCORD_nam_resource_war.51 days = 7" in queue
        and "NAM_rw_queue_front_check = yes"
        in read("common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt")
        and "ADISCORD_nam_resource_war_front_resolution = yes"
        in event_block(events, "ADISCORD_nam_resource_war.51")
        and "clr_country_flag = NAM_rw_front_check_pending" in resolution
        and "NAM_rw_territorial_victory = yes" in resolution
        and "NAM_rw_coalition_territorial_victory = yes" in resolution,
        "control changes must queue one debounced front settlement that rechecks the ground",
    )
    check(
        all(f"controls_state = {state_id}" in territorial for state_id in (720, 721, 701, 722))
        and "67 = { NAM_rw_field_taken_by_coalition = yes }" in coalition_ground,
        "the territorial settlements must read the border belts and the Northern Deposits",
    )
    record = named_block(triggers, "ADISCORD_nam_victory_record_complete")
    check(
        "has_capitulated" not in record
        and "ADISCORD_nam_resource_war_record_uncapitulation = yes"
        in read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"),
        "the victory record must use defeat receipts that liberation clears",
    )
    close_external = named_block(effects, "ADISCORD_nam_resource_war_close_external")
    check(
        close_external.find("ADISCORD_nam_resource_war_timeout_resolution = yes")
        < close_external.find("set_global_flag = ADISCORD_nam_resource_war_resolved"),
        "a native peace between independent principals must still settle by the oil score",
    )
    address = event_block(events, "ADISCORD_nam_resource_war.70")
    check(
        address.count("option = {") == 3 and "fire_only_once = yes" in address,
        "Rom's address needs its three tones of speech",
    )
    timeout = named_block(effects, "ADISCORD_nam_resource_war_timeout_resolution")
    victory_call = timeout.find("ADISCORD_nam_resource_war_resolve_nam_victory = yes")
    check(
        -1 < timeout.find("NAM_rw_holds_border_belt = yes") < victory_call
        < timeout.find("ADISCORD_nam_resource_war_resolve_standoff = yes")
        < timeout.find("ADISCORD_nam_resource_war_resolve_compromise = yes"),
        "a timeout score of 100 wins the treaty only with a border district; otherwise it is a standoff",
    )
    standoff = named_block(effects, "ADISCORD_nam_resource_war_resolve_standoff")
    for token in (
        "ADISCORD_nam_resource_war_active = yes",
        "set_global_flag = ADISCORD_nam_resource_war_resolved",
        "set_global_flag = ADISCORD_nam_resource_war_nam_victory",
        "set_global_flag = ADISCORD_nam_resource_war_standoff",
        "clr_global_flag = ADISCORD_nam_resource_war_started",
        "ADISCORD_nam_resource_war_end_all_wars = yes",
        "annex_country = { target = SLF transfer_troops = no }",
        "ADISCORD_nam_resource_war_clear_temporary_support = yes",
        "VAL_deliver_nam_concession = yes",
        "VAL_settle_resource_aid = yes",
        "tree = NAM_postwar_focus",
        "keep_completed = yes",
        "ADISCORD_nam_resource_news.3",
    ):
        check(token in standoff, f"the standoff settlement lacks {token}")
    for token in (
        "NAM_rw_award_border_state",
        "NAM_rw_punish_defeated_coalition",
        "NAM_treaty_independence_recognised",
        "VAL_cancel_nam_concession",
        "annex_country = { target = NAM",
    ):
        check(token not in standoff, f"the standoff settlement must not apply {token}")
    news_three = next(
        (
            block
            for block in typed_blocks(events, "news_event")
            if re.search(r"(?m)^\s*id\s*=\s*ADISCORD_nam_resource_news\.3\s*$", block)
        ),
        "",
    )
    check(
        "ADISCORD_nam_resource_news.3.t_standoff" in news_three
        and "ADISCORD_nam_resource_news.3.d_standoff" in news_three,
        "news .3 needs the standoff title and description",
    )
    recognition = event_block(events, "ADISCORD_nam_resource_war.12")
    check(
        "has_global_flag = ADISCORD_nam_resource_war_standoff" in recognition
        and "ADISCORD_nam_resource_war.12.d_standoff" in recognition,
        "the recognition-focus event needs its standoff text",
    )
    check(
        "has_global_flag = ADISCORD_nam_resource_war_standoff"
        in named_block(categories, "NAM_national_programmes"),
        "the national programmes category must stay open after a standoff",
    )

    for effect_name in (
        "ADISCORD_nam_resource_war_resolve_nam_victory",
        "ADISCORD_nam_resource_war_resolve_standoff",
        "ADISCORD_nam_resource_war_resolve_compromise",
        "NAM_rw_settle_island_exile",
        "ADISCORD_nam_resource_war_close_external",
    ):
        check(
            "ADISCORD_nam_resource_war_clear_temporary_support = yes"
            in named_block(effects, effect_name),
            f"{effect_name} must run the shared wartime cleanup",
        )
    check(
        "azh_neutral" not in effects + triggers + events + decisions
        and event_block(events, "ADISCORD_nam_resource_war.22") == ""
        and event_block(events, "ADISCORD_nam_resource_war.23") == "",
        "the Azhar neutrality route is retired",
    )
    ultimatum = event_block(events, "ADISCORD_nam_resource_war.21")
    buy_option = ultimatum[ultimatum.find("ADISCORD_nam_resource_war.21.c"):]
    check(
        "NOT = { has_country_flag = NAM_rw_time_bought }" in buy_option
        and "NOT = { has_fuel < 12000 }" in buy_option
        and "NAM_rw_buy_time = yes" in buy_option,
        "the ultimatum must offer Azhar's paid delay once and only with the fuel in stock",
    )

    refund = named_block(effects, "NAM_veter_talks_refund")
    check(
        "NAM_add_treasury = yes" in refund
        and "clear_variable = NAM_veter_talks_deposit" in refund
        and "add_political_power" not in refund,
        "broken-off talks must return only the treasury deposit",
    )
    check(
        "custom_effect_tooltip = NAM_veter_talks_1_cancel_tt"
        in named_block(named_block(decisions, "NAM_veter_talks_1"), "cancel_effect"),
        "the first round must explain that its political power is not refunded",
    )
    for number, amount in ((2, 100), (3, 200)):
        talks = named_block(decisions, f"NAM_veter_talks_{number}")
        check(
            f"var = NAM_veter_talks_deposit value = {amount}" in named_block(talks, "complete_effect")
            and "NAM_veter_talks_refund = yes" in named_block(talks, "cancel_effect")
            and "clear_variable = NAM_veter_talks_deposit" in named_block(talks, "remove_effect"),
            f"NAM_veter_talks_{number} must hold its {amount} treasury in escrow until it ends",
        )

    for decision_name in ("NAM_south_allied_fuel", "NAM_south_convoy_interdiction"):
        check(
            "has_completed_focus = NAM_defeat_southern_charter"
            in named_block(named_block(decisions, decision_name), "visible"),
            f"{decision_name} must also open on the defeat route's Southern Compact",
        )
    main_tree = read("focus_trees/NAM/main/focuses.txt")
    for focus in typed_blocks(main_tree, "focus"):
        if "tooltip = NAM_restitution_clock_tt" in named_block(focus, "available"):
            check(
                has_script_fragment(named_block(focus, "bypass"), STANDOFF_FOCUS_BYPASS),
                "a focus waiting for the restitution clock must bypass once the entry has closed",
            )

    check(
        "NAM_coup_leader" not in effects and "NAM_war_of_return_front_peace" not in effects,
        "unread coup-leader and front-peace markers must stay removed",
    )
    for key in (
        "NAM_Arseny_Klyuch_advisor",
        "NAM_Lev_Gavanov_advisor",
        "NAM_Taras_Shtyk_advisor",
        "NAM_Vera_Pechat_advisor",
        "ADISCORD_nam_resource_news.3.t_standoff",
        "ADISCORD_nam_resource_news.3.d_standoff",
        "ADISCORD_nam_resource_war.12.d_standoff",
        "ADISCORD_nam_resource_war.21.c",
        "NAM_rw_21_c_tt",
        "NAM_rw_next_time_bought",
        "ADISCORD_nam_resource_news.2.t_exile",
        "ADISCORD_nam_resource_news.2.d_exile",
        "ADISCORD_nam_resource_news.2.a_exile",
        "ADISCORD_nam_resource_war.70.d",
        "NAM_orders_summary_delivered",
        "NAM_veter_talks_1_cancel_tt",
        "NAM_veter_talks_2_cancel_tt",
        "NAM_veter_talks_3_cancel_tt",
    ):
        check(
            re.search(rf"(?m)^\s*{re.escape(key)}:", loc) is not None,
            f"missing localisation key {key}",
        )
    # Event paper is light: its descriptions use native dark text only.
    paper_keys = set(re.findall(r"\b(?:desc|text)\s*=\s*([A-Za-z0-9_.]+)", events))
    for match in re.finditer(r'(?m)^\s*([A-Za-z0-9_.]+):\d*\s*"(.*)"\s*$', loc):
        if match.group(1) in paper_keys:
            check(
                "§Y" not in match.group(2),
                f"{match.group(1)} uses yellow text on event paper",
            )


def main() -> int:
    files = (
        "common/country_tags/03_ADISCORD_nam_resource_war_tags.txt",
        "common/countries/SLF.txt",
        "common/countries/cosmetic.txt",
        "common/characters/ADISCORD_nam_resource_war_characters.txt",
        "common/ideas/ADISCORD_nam_resource_war_ideas.txt",
        "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt",
        "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt",
        "common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt",
        "common/decisions/categories/ADISCORD_scenario_debug_categories.txt",
        "common/decisions/ADISCORD_scenario_debug_decisions.txt",
        "common/decisions/categories/ADISCORD_nam_resource_war_categories.txt",
        "common/decisions/ADISCORD_nam_resource_war_decisions.txt",
        "common/ai_strategy/ADISCORD_nam_resource_war_ai.txt",
        "events/ADISCORD_nam_resource_war_events.txt",
        "events/ADISCORD_vorkerland_events.txt",
        "history/countries/SLF - Svetlogorsk Uprising.txt",
        "history/units/NAM_resource_war.txt",
        "history/units/EFL_nam_resource_war.txt",
        "history/units/AZH_nam_resource_war.txt",
        "history/units/SLF_nam_resource_war.txt",
        "common/units/ADISCORD_naval_units.txt",
        "common/units/equipment/ADISCORD_convoy_equipment.txt",
        "common/script_enums.txt",
        "history/units/NAM.txt",
        "history/units/EFL.txt",
        "history/units/AZH.txt",
        "history/countries/NAM - NamestnikLand.txt",
        "history/countries/EFL - Eflor.txt",
        "history/countries/AZH - Azhar Black Basin.txt",
        "common/ideas/ADISCORD_nam_resource_war_ideas.txt",
        "docs/lore/countries.md",
    )
    sources = {relative: read(relative) for relative in files}
    for relative, source in sources.items():
        check(balanced_braces(source), f"{relative}: unbalanced braces or quote")

    for relative in (
        "history/units/NAM_resource_war.txt",
        "history/units/EFL_nam_resource_war.txt",
        "history/units/AZH_nam_resource_war.txt",
        "history/units/SLF_nam_resource_war.txt",
    ):
        source = sources[relative]
        defined_templates = set(
            re.findall(
                r'division_template\s*=\s*\{\s*name\s*=\s*"([^"]+)"',
                source,
                re.DOTALL,
            )
        )
        # The three national armies reuse their campaign-start templates.
        tag = Path(relative).stem.split("_", 1)[0]
        if tag in {"NAM", "EFL", "AZH"}:
            defined_templates |= set(
                re.findall(
                    r'division_template\s*=\s*\{\s*name\s*=\s*"([^"]+)"',
                    sources[f"history/units/{tag}.txt"],
                )
            )
        referenced_templates = set(
            re.findall(
                r'division_template\s*=\s*"([^"]+)"',
                source,
            )
        )
        check(
            referenced_templates <= defined_templates,
            f"{relative}: dynamically loaded OOB references templates it does not define: "
            f"{sorted(referenced_templates - defined_templates)}",
        )
        check(
            re.search(
                r'(?m)^\s*(?:name|division_template)\s*=\s*[^"\s{}]+\s+[^#{}]+$', source
            )
            is None,
            f"{relative}: unquoted multiword template or division name",
        )

    effects = sources["common/scripted_effects/ADISCORD_nam_resource_war_effects.txt"]
    triggers = sources[
        "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt"
    ]
    ai = sources["common/ai_strategy/ADISCORD_nam_resource_war_ai.txt"]
    on_actions = read_country_on_actions(
        "common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt", 'nam'
    )
    debug_categories = sources[
        "common/decisions/categories/ADISCORD_scenario_debug_categories.txt"
    ]
    debug_decisions = sources["common/decisions/ADISCORD_scenario_debug_decisions.txt"]
    prewar_categories = sources[
        "common/decisions/categories/ADISCORD_nam_resource_war_categories.txt"
    ]
    prewar_decisions = sources[
        "common/decisions/ADISCORD_nam_resource_war_decisions.txt"
    ]
    news = sources["events/ADISCORD_nam_resource_war_events.txt"]
    collapse_events = sources["events/ADISCORD_vorkerland_events.txt"]
    ideas = sources["common/ideas/ADISCORD_nam_resource_war_ideas.txt"]
    equipment_source = sources["common/units/equipment/ADISCORD_convoy_equipment.txt"]
    naval_units = sources["common/units/ADISCORD_naval_units.txt"]
    script_enums = sources["common/script_enums.txt"]
    slf_oob = sources["history/units/SLF_nam_resource_war.txt"]

    check('SLF = "countries/SLF.txt"' in sources[files[0]], "SLF tag is not registered")
    check(
        not (
            ROOT / "history" / "countries" / "SLF - Svetlogorsk Liberation Front.txt"
        ).exists()
        and not (
            ROOT / "history" / "countries" / "SLF - Svetlogorsk Republic.txt"
        ).exists(),
        "obsolete SLF Liberation Front/Republic country-history filename remains",
    )
    check(
        re.search(
            r"(?m)^\s*capital\s*=\s*688\s*$",
            sources["history/countries/SLF - Svetlogorsk Uprising.txt"],
        )
        is not None,
        "SLF history capital must be compact internal uprising state 688",
    )
    check(
        not (ROOT / "events" / "ADISCORD_nam_resource_war_news.txt").exists(),
        "NAM news must be merged into the main resource-war event file",
    )
    check(
        not (
            ROOT
            / "common"
            / "scripted_effects"
            / "ADISCORD_nam_resource_war_debug_effects.txt"
        ).exists(),
        "NAM debug entry points must be merged into the main resource-war effect file",
    )
    check(
        all(
            effect in effects
            for effect in (
                "ADISCORD_nam_debug_start_resource_war",
                "ADISCORD_nam_debug_resolve_coalition_victory",
                "ADISCORD_nam_debug_resolve_nam_victory",
            )
        ),
        "merged NAM effects are missing compact debug entry points",
    )
    check(
        "ADISCORD_nam_resource_war_prepare_independence" not in effects,
        "one-shot NAM independence wrapper must be inlined into resource-war start",
    )
    nam_readiness = named_block(
        named_block(triggers, "ADISCORD_nam_resource_war_ready"), "NAM"
    )
    check(
        "has_war = no" in nam_readiness and "is_subject = no" not in nam_readiness,
        "resource-war scheduling still blocks before the start effect can free a subject NAM",
    )
    readiness = named_block(triggers, "ADISCORD_nam_resource_war_ready")
    check(
        readiness.count("has_global_flag = ADISCORD_fresh_campaign_contract_v1") == 1,
        "resource-war readiness is not restricted to a fresh campaign",
    )
    for state_id in (67, 688, 689, 690):
        check(
            f"controls_state = {state_id}" in readiness,
            f"resource-war readiness must require NAM control of state {state_id}",
        )
    efl_readiness = named_block(readiness, "EFL")
    azh_readiness = named_block(readiness, "AZH")
    check(
        all(
            f"controls_state = {state_id}" in efl_readiness
            for state_id in (68, 70, 691)
        ),
        "resource-war readiness must require EFL control of all three mainland states",
    )
    check(
        all(f"controls_state = {state_id}" in azh_readiness for state_id in (69, 692)),
        "resource-war readiness must require AZH control of both mainland states",
    )
    start = named_block(effects, "ADISCORD_nam_resource_war_start")
    start_outer_open = start.find("{")
    start_outer_close = start.rfind("}")
    start_guard = re.search(r"\bif\s*=\s*\{", start[start_outer_open + 1 :])
    if start_guard is None:
        check(False, "resource-war start lacks its outer readiness guard")
    else:
        guard_header = start_outer_open + 1 + start_guard.start()
        guard_open = start.find("{", guard_header)
        guard_close = matching_brace(start, guard_open)
        check(
            not without_comments(start[start_outer_open + 1 : guard_header]).strip()
            and guard_close >= 0
            and not without_comments(
                start[guard_close + 1 : start_outer_close]
            ).strip(),
            "resource-war start has mutations outside its sole readiness guard",
        )
    readiness_position = start.find("ADISCORD_nam_resource_war_ready = yes")
    for mutation in (
        "set_autonomy = { target = NAM autonomy_state = autonomy_free }",
        "leave_faction = yes",
        "clr_global_flag = ADISCORD_nam_resource_war_scheduled",
        "ADISCORD_nam_resource_war_begin_hostilities = yes",
    ):
        check(
            readiness_position >= 0 and start.find(mutation) > readiness_position,
            f"resource-war start mutation escapes readiness: {mutation}",
        )
    check(
        "declare_war_on" not in start and "load_oob" not in start,
        "resource-war wrapper must delegate military setup to hostilities",
    )

    hostilities = named_block(effects, "ADISCORD_nam_resource_war_begin_hostilities")
    for mutation in (
        "set_global_flag = ADISCORD_nam_resource_war_started",
        "country_event = { id = ADISCORD_nam_resource_war.3 hours = 1 }",
        'load_oob = "NAM_resource_war"',
        "create_faction_from_template = {",
        "declare_war_on = { target = NAM type = annex_everything }",
    ):
        check(
            mutation in hostilities,
            f"hostility path lost required mutation: {mutation}",
        )
    check(
        start.count("ADISCORD_nam_resource_war_begin_hostilities = yes") == 1
        and "ADISCORD_nam_resource_war_resolve_peaceful_withdrawal" not in start
        and "random_list" not in start,
        "resource-war entry must always begin hostilities once readiness is satisfied",
    )
    schedule = named_block(effects, "ADISCORD_nam_resource_war_schedule")
    for token in (
        "has_global_flag = ADISCORD_fresh_campaign_contract_v1",
        "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
        "NOT = { has_global_flag = ADISCORD_nam_resource_war_scheduled }",
        "NOT = { has_global_flag = ADISCORD_nam_resource_war_started }",
        "NOT = { has_global_flag = ADISCORD_nam_resource_war_resolved }",
        "NOT = { has_global_flag = ADISCORD_nam_resource_war_retry_used }",
        "country_exists = NAM",
        "country_exists = EFL",
        "country_exists = AZH",
        "set_global_flag = ADISCORD_nam_resource_war_scheduled",
        "id = ADISCORD_nam_resource_war.1",
        "days = 420",
        "random_days = 60",
    ):
        check(
            schedule.count(token) == 1,
            f"bounded resource-war schedule lacks exact token: {token}",
        )
    check(
        schedule.find("set_global_flag = ADISCORD_nam_resource_war_scheduled")
        < schedule.find("id = ADISCORD_nam_resource_war.1"),
        "resource-war schedule does not record its one-shot guard before queueing .1",
    )

    collapse_two = next(
        (
            block
            for block in typed_blocks(collapse_events, "country_event")
            if re.search(r"\bid\s*=\s*ADISCORD_vorkerland_collapse\.2\b", block)
        ),
        "",
    )
    producer = "ADISCORD_nam_resource_war_schedule = yes"
    check(bool(collapse_two), "collapse event .2 is missing")
    check(
        collapse_events.count(producer) == 1 and collapse_two.count(producer) == 1,
        "fresh collapse .2 must be the unique resource-war schedule producer",
    )
    check(
        collapse_two.find("set_global_flag = ADISCORD_vorkerland_collapse_wars_started")
        < collapse_two.find(producer),
        "collapse .2 queues the resource war before recording wars_started",
    )

    entry_event = next(
        (
            block
            for block in typed_blocks(news, "country_event")
            if re.search(r"\bid\s*=\s*ADISCORD_nam_resource_war\.1\b", block)
        ),
        "",
    )
    entry_immediate = named_block(entry_event, "immediate")
    retry_calls = re.findall(
        r"country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_nam_resource_war\.1\b",
        entry_immediate,
    )
    check(
        len(retry_calls) == 3,
        "resource-war .1 must contain one protocol deferral, one bought delay and one delayed self-retry",
    )
    for token, expected in (
        ("NOT = { has_global_flag = ADISCORD_nam_resource_war_retry_used }", 1),
        ("set_global_flag = ADISCORD_nam_resource_war_retry_used", 1),
        ("NOT = { has_global_flag = ADISCORD_nam_resource_war_protocol_deferred }", 1),
        ("set_global_flag = ADISCORD_nam_resource_war_protocol_deferred", 1),
        ("NOT = { has_global_flag = ADISCORD_nam_resource_war_time_deferred }", 1),
        ("set_global_flag = ADISCORD_nam_resource_war_time_deferred", 1),
        ("clr_global_flag = ADISCORD_nam_resource_war_scheduled", 1),
        ("days = 365", 1),
        ("days = 75", 1),
        ("days = 120", 1),
        ("random_days = 90", 1),
    ):
        check(
            entry_immediate.count(token) == expected,
            f"resource-war .1 has non-exact bounded retry token: {token}",
        )
    retry_guard = entry_immediate.find(
        "NOT = { has_global_flag = ADISCORD_nam_resource_war_retry_used }"
    )
    retry_setter = entry_immediate.find(
        "set_global_flag = ADISCORD_nam_resource_war_retry_used"
    )
    deferral_guard = entry_immediate.find(
        "NOT = { has_global_flag = ADISCORD_nam_resource_war_protocol_deferred }"
    )
    deferral_setter = entry_immediate.find(
        "set_global_flag = ADISCORD_nam_resource_war_protocol_deferred"
    )
    check(
        retry_guard
        < retry_setter
        < entry_immediate.find("id = ADISCORD_nam_resource_war.1", retry_setter),
        "resource-war .1 self-retry is not protected by its permanent one-retry guard",
    )
    check(
        deferral_guard
        < deferral_setter
        < entry_immediate.find("id = ADISCORD_nam_resource_war.1", deferral_setter)
        < retry_guard,
        "the protocol deferral of .1 is not a single guarded reschedule",
    )
    runtime_entry = "\n".join((effects, news, on_actions, collapse_events))
    check(
        runtime_entry.count("set_global_flag = ADISCORD_nam_resource_war_retry_used")
        == 1
        and "clr_global_flag = ADISCORD_nam_resource_war_retry_used"
        not in runtime_entry,
        "resource-war retry guard is not a single permanent setter",
    )
    check(
        runtime_entry.count("set_global_flag = ADISCORD_nam_resource_war_scheduled")
        == 1,
        "resource-war scheduled guard has multiple producers",
    )
    check(
        "ADISCORD_nam_resource_war_schedule = yes" not in entry_event,
        "resource-war .1 recursively calls the initial schedule effect",
    )
    for recurring in (
        "on_startup",
        "on_daily",
        "on_weekly",
        "on_monthly",
        "on_yearly",
        "every_country",
    ):
        check(
            re.search(rf"(?m)^\s*{recurring}\s*=", on_actions) is None,
            f"resource-war entry retains recurring hook {recurring}",
        )
    check(
        "ADISCORD_nam_resource_war.1" not in on_actions,
        "resource-war .1 remains scheduled from on_actions",
    )
    faction_creation = re.compile(
        r"create_faction_from_template\s*=\s*\{\s*"
        r"template\s*=\s*faction_template_ADISCORD_standard\s+"
        r"name\s*=\s*faction_eflor_azhar_restitution_alliance\s*\}",
        re.DOTALL,
    )
    check(
        faction_creation.search(hostilities) is not None,
        "resource-war hostility path does not create the permanent EFL-AZH faction",
    )
    check(
        hostilities.count("add_to_faction = AZH") == 1,
        "EFL must add AZH to the wartime resource faction exactly once",
    )
    check(
        (start + hostilities).count("leave_faction = yes") == 3,
        "NAM, EFL, and AZH must clear obsolete faction ties before the new faction is formed",
    )

    # The declaration belongs to hostilities: EFL declares, or NAM after a first
    # strike, and AZH joins the same war unless the faction call already did.
    efl_declaration = (
        "EFL = { declare_war_on = { target = NAM type = annex_everything } }"
    )
    nam_declaration = (
        "NAM = { declare_war_on = { target = EFL type = annex_everything } }"
    )
    azh_join_pattern = re.compile(
        r"AZH\s*=\s*\{\s*if\s*=\s*\{\s*limit\s*=\s*\{\s*NOT\s*=\s*\{\s*has_war_with\s*=\s*NAM\s*\}\s*\}\s*"
        r"add_to_war\s*=\s*\{\s*"
        r"targeted_alliance\s*=\s*EFL\s+enemy\s*=\s*NAM\s+"
        r"hostility_reason\s*=\s*asked_to_join\s+single_target_only\s*=\s*yes\s*\}\s*\}\s*\}",
        re.DOTALL,
    )
    check(
        efl_declaration in hostilities and nam_declaration in hostilities,
        "hostilities must declare the single war from EFL or, after a first strike, from NAM",
    )
    check(
        hostilities.count("declare_war_on") == 2
        and "has_country_flag = NAM_rw_first_strike" in hostilities,
        "the first-strike declarer must be the only alternative to the EFL declaration",
    )
    check(
        azh_join_pattern.search(hostilities) is not None,
        "AZH does not join EFL's existing war against NAM",
    )
    check(
        "AZH = { declare_war_on = { target = NAM" not in hostilities,
        "AZH still creates an independent second war against NAM",
    )
    check(
        "azh_neutral" not in hostilities
        and "AZH = { ADISCORD_nam_resource_war_reserve_major = yes }" in hostilities
        and "add_claim_by = AZH" in hostilities,
        "AZH must always enter the faction, the war, the claims and major status",
    )

    create_position = hostilities.find("create_faction_from_template")
    declare_position = hostilities.find(nam_declaration)
    join_position = hostilities.find("add_to_war")
    check(
        -1 not in (create_position, declare_position, join_position)
        and create_position < declare_position < join_position,
        "faction creation, the declaration, and AZH war entry are in the wrong order",
    )
    # The victory treaty carves border slivers from both principals: 720, 721
    # and 701 from Eflor, 722 from a belligerent Azhar, never the core 68/691.
    victory_award = named_block(effects, "ADISCORD_nam_resource_war_resolve_nam_victory")
    check(
        all(
            f"{state_id} = {{ NAM_rw_award_border_state = yes }}" in victory_award
            for state_id in (720, 721, 701, 722)
        )
        and "69 = { add_claim_by = NAM }" in victory_award
        and "transfer_state = 691" not in victory_award
        and "NAM = { transfer_state = 68 }" not in effects,
        "NAM victory must award the border slivers 720, 721, 701 and 722",
    )
    award = named_block(effects, "NAM_rw_award_border_state")
    check(
        has_script_fragment(award, "NAM = { transfer_state = PREV } remove_core_of = EFL add_core_of = NAM set_state_controller_to = NAM")
        and has_script_fragment(award, "NAM = { transfer_state = PREV } remove_core_of = AZH add_core_of = NAM set_state_controller_to = NAM"),
        "border awards must move ownership, cores and control from the defeated principal",
    )
    check(
        "NAM_rw_punish_defeated_coalition = yes" in victory_award
        and "idea = NAM_ruined_economy" in named_block(effects, "NAM_rw_apply_punishment")
        and "idea = NAM_army_of_shame" in named_block(effects, "NAM_rw_apply_punishment")
        and "days = 730" in named_block(effects, "NAM_rw_apply_punishment"),
        "a NAM victory must punish each defeated principal with both timed spirits",
    )
    check(
        "228 = { add_core_of = NAM" not in effects
        and "231 = { add_core_of = NAM" not in effects,
        "NAM victory must not turn its island colonies back into NAM cores",
    )
    coalition_treaty = named_block(effects, "ADISCORD_nam_resource_war_resolve_coalition_victory")
    exile = named_block(effects, "NAM_rw_settle_island_exile")
    move_capital = named_block(effects, "NAM_rw_exile_move_capital")
    check(
        all(f"transfer_state = {state}" not in coalition_treaty for state in range(225, 232))
        and "NAM_rw_can_go_into_exile = yes" in coalition_treaty
        and "NAM_rw_settle_island_exile = yes" in coalition_treaty
        and "annex_country = { target = NAM transfer_troops = no }" in coalition_treaty
        and all(f"state = {state}" in named_block(triggers, "NAM_rw_island_state") for state in range(225, 232)),
        "the coalition treaty must leave the islands to an exiled NAM and annex only a NAM without islands",
    )
    check(
        "load_focus_tree" not in exile
        and -1
        < exile.find("set_global_flag = ADISCORD_nam_resource_war_island_exile")
        < exile.find("id = ADISCORD_nam_resource_war.81")
        and -1
        < move_capital.find("set_capital = { state = 228 }")
        < move_capital.find("set_capital = { state = 230 }"),
        "the island exile must leave the tree to the council of .100 and move the capital to 228 first",
    )
    check(
        "days = 420" in effects
        and "days = 720" not in effects
        and "timeout_resolution" in effects,
        "war needs the 420-day deterministic anti-stalemate deadline",
    )
    # The timeout is settled by the oil score of the fields NAM still controls.
    timeout = named_block(effects, "ADISCORD_nam_resource_war_timeout_resolution")
    oil_score = named_block(effects, "NAM_rw_compute_oil_score")
    for state_id, oil in ((67, 80), (688, 12), (689, 36), (690, 24), (719, 12)):
        check(
            has_script_fragment(
                oil_score,
                f"if = {{ limit = {{ NAM = {{ controls_state = {state_id} }} }} "
                f"add_to_temp_variable = {{ var = NAM_rw_oil_score value = {oil} }} }}",
            ),
            f"oil score lacks state {state_id} worth {oil}",
        )
    resolution_order = [
        timeout.find("value = 100 compare = greater_than_or_equals"),
        timeout.find("ADISCORD_nam_resource_war_resolve_nam_victory = yes"),
        timeout.find("value = 36 compare = greater_than_or_equals"),
        timeout.find("ADISCORD_nam_resource_war_resolve_compromise = yes"),
        timeout.find("ADISCORD_nam_resource_war_resolve_coalition_victory = yes"),
    ]
    check(
        "NAM_rw_compute_oil_score = yes" in timeout
        and -1 not in resolution_order
        and resolution_order == sorted(resolution_order)
        and "controls_state = 67" not in timeout,
        "timeout must settle by oil score: >= 100 victory or standoff, 36-99 compromise, < 36 partition",
    )
    for equipment_id, amount, producer in (
        ("infantry_equipment", 20000, "NAM"),
        ("infantry_equipment", 30000, "EFL"),
        ("infantry_equipment", 18000, "AZH"),
        ("infantry_equipment", 18000, "SLF"),
        ("ADISCORD_squad_weapons_equipment_0", 80, "NAM"),
        ("ADISCORD_squad_weapons_equipment_0", 100, "EFL"),
        ("ADISCORD_squad_weapons_equipment_0", 20, "SLF"),
    ):
        check(
            f"type = {equipment_id} amount = {amount} producer = {producer}" in effects,
            f"incorrect resource-war stockpile for {producer}: expected {amount} {equipment_id}",
        )
    check(
        ai.count("manual_attack = yes") == 5 and ai.count("priority = 1500") >= 6,
        "coalition attack or NAM three-front defence AI is incomplete",
    )
    for strategy in re.findall(r"ai_strategy\s*=\s*\{([^{}]*)\}", ai, re.DOTALL):
        if "type = front_control" not in strategy:
            continue
        ratio_match = re.search(r"\bratio\s*=\s*([0-9.]+)", strategy)
        check(
            ratio_match is not None, "NAM front_control strategy lacks a coverage ratio"
        )
        if ratio_match is not None:
            check(
                float(ratio_match.group(1)) < 1.0,
                f"NAM front_control strategy uses unreachable ratio {ratio_match.group(1)}",
            )
    for strategy_suffix, tag, ratio in (
        ("eflor", "EFL", "0.01"),
        ("azhar", "AZH", "0.01"),
        ("rebel", "SLF", "0.01"),
    ):
        strategy_name = f"ADISCORD_nam_resource_war_nam_{strategy_suffix}_front"
        strategy = named_block(ai, strategy_name)
        check(
            f"tag = {tag} ratio = {ratio}" in strategy
            and "execution_type = careful" in strategy
            and "manual_attack = no" in strategy,
            f"{strategy_name} is not a cautious NAM defence allocation",
        )

    hidden_ideas = named_block(ideas, "hidden_ideas")
    last_line = named_block(ideas, "ADISCORD_nam_last_line_administration")
    check(
        "ADISCORD_nam_last_line_administration" in hidden_ideas,
        "NAM last-line administration is not a hidden idea",
    )
    for token in ("army_defence_factor = 0.20", "army_org_factor = 0.10"):
        check(token in last_line, f"NAM last-line administration lacks {token}")

    emergency = named_block(effects, "ADISCORD_nam_refresh_emergency_defence")
    for token in (
        "is_ai = yes",
        "ADISCORD_nam_resource_war_active = yes",
        "surrender_progress > 0.60",
        "surrender_progress < 0.45",
        "add_ideas = ADISCORD_nam_last_line_administration",
        "remove_ideas = ADISCORD_nam_last_line_administration",
        "surrender_progress > 0.40",
        "NOT = { has_country_flag = ADISCORD_nam_emergency_reserve_called }",
        "set_country_flag = ADISCORD_nam_emergency_reserve_called",
        "add_manpower = 7000",
        "type = infantry_equipment amount = 15000 producer = NAM",
    ):
        check(token in emergency, f"NAM emergency defence lacks bounded token: {token}")
    check(
        emergency.count("create_unit = {") == 2,
        "NAM emergency defence must create exactly two reserve divisions",
    )
    check(
        "random" not in emergency, "NAM emergency defence reserve must be deterministic"
    )

    state_control = named_block(on_actions, "on_state_control_changed")
    for token in (
        "ADISCORD_nam_resource_war_active = yes",
        "ROOT = { tag = NAM }",
        "FROM = { tag = NAM }",
    ):
        check(token in state_control, f"NAM state-control refresh lacks {token}")
    check(
        state_control.count("ADISCORD_nam_refresh_emergency_defence = yes") == 1,
        "NAM state-control hook must call emergency refresh exactly once",
    )
    cleanup = named_block(effects, "ADISCORD_nam_resource_war_clear_temporary_support")
    check(
        "remove_ideas = ADISCORD_nam_last_line_administration" in cleanup,
        "NAM outcome cleanup leaves the last-line idea active",
    )
    # The underground decides the uprising: >= 60 always, 30-59 a 50/50 roll,
    # below 30 never. An effective compact is checked first.
    uprising_call = "id = ADISCORD_nam_resource_war.2 days = 45 random_days = 30"
    underground_order = [
        hostilities.find("NAM_compact_effective = yes"),
        hostilities.find("var = NAM_underground value = 60 compare = greater_than_or_equals"),
        hostilities.find("var = NAM_underground value = 30 compare = greater_than_or_equals"),
        hostilities.find(f"50 = {{ country_event = {{ {uprising_call} }} }}"),
        hostilities.find("50 = { set_global_flag = ADISCORD_nam_resource_war_SLF_defeated }"),
    ]
    check(
        -1 not in underground_order
        and underground_order == sorted(underground_order)
        and hostilities.count("random_list = {") == 1
        and hostilities.count(uprising_call) == 2,
        "Svetlogorsk uprising must follow the underground thresholds "
        "with the intended 45-75 day response window",
    )

    check(
        "ADISCORD_nam_prewar_defence_category" not in prewar_categories
        and "ADISCORD_nam_fortify_" not in prewar_decisions,
        "retired one-off fortification decisions or their category remain",
    )
    line_decision = named_block(prewar_decisions, "NAM_prepare_line")
    check(
        "targets = { 67 688 689 690 719 700 }" in line_decision
        and "custom_cost_text = NAM_cost_line" in line_decision
        and "cost = 0" in line_decision
        and "days_remove = 35" in line_decision
        and "NOT = { has_political_power < 30 }" in line_decision
        and "value = 100 compare = greater_than_or_equals" in line_decision
        and "NAM_line_slot_free = yes" in line_decision
        and "has_decision" not in line_decision,
        "NAM_prepare_line lacks its exact price, slot or state-flag escrow contract",
    )
    for effect_name in ("NAM_line_complete", "NAM_line_release"):
        check(
            "has_state_flag = NAM_line_in_progress" in named_block(effects, effect_name),
            f"{effect_name} must settle only a line holding its state escrow",
        )
    # A completed line fortifies every border province (level 1, level 2 on
    # border victory points) through the native selector, never a fixed list.
    line_complete = named_block(effects, "NAM_line_complete")
    check(
        re.search(r"province\s*=\s*\d+", line_complete) is None
        and has_script_fragment(
            line_complete,
            "add_building_construction = { type = bunker level = 1 instant_build = yes "
            "province = { all_provinces = yes limit_to_border = yes } }",
        )
        and has_script_fragment(
            line_complete,
            "add_building_construction = { type = bunker level = 1 instant_build = yes "
            "province = { all_provinces = yes limit_to_border = yes limit_to_victory_point > 0 } }",
        ),
        "defence lines must fortify every border province through the native selector",
    )
    check(
        "any_neighbor_state = { NOT = { is_owned_by = ROOT } }"
        in named_block(line_decision, "visible"),
        "defence lines may be offered only for states with a foreign land border",
    )

    # Paid mobilisation: custom price, exact boundaries, escrow counters and a
    # refund path before the war.
    order_prices = {
        "NAM_order_resource_guard": ("NAM_order_guard_paid", 25, 200, 9600),
        "NAM_order_field_infantry": ("NAM_order_infantry_paid", 15, 100, 6300),
        "NAM_order_motor_column": ("NAM_order_motor_paid", 25, 250, 4600),
        "NAM_order_coastal_battalion": ("NAM_order_coastal_paid", 10, 50, 3300),
    }
    refund = named_block(effects, "NAM_refund_mobilisation_orders")
    delivery = named_block(effects, "NAM_deliver_mobilisation_orders")
    for decision_name, (counter, pp, treasury, manpower) in order_prices.items():
        decision = named_block(prewar_decisions, decision_name)
        complete = named_block(decision, "complete_effect")
        check(
            "cost = 0" in decision
            and "custom_cost_text = NAM_cost_order_" in decision
            and f"NOT = {{ has_political_power < {pp} }}" in decision
            and f"value = {treasury} compare = greater_than_or_equals" in decision
            and f"NOT = {{ has_manpower < {manpower} }}" in decision
            and "NAM_order_can_place = yes" in decision,
            f"{decision_name} lacks its exact custom-cost contract",
        )
        check(
            complete.count(f"add_political_power = -{pp}") == 1
            and complete.count(f"add_manpower = -{manpower}") == 1
            and complete.count(f"var = NAM_treasury_amount value = {treasury}") == 1
            and complete.count("NAM_spend_treasury = yes") == 1
            and complete.count(f"add_to_variable = {{ var = {counter} value = 1 }}") == 1,
            f"{decision_name} must debit each currency exactly once into its escrow",
        )
        check(
            counter in refund
            and counter in delivery
            and f"add_manpower = {manpower}" in refund,
            f"{decision_name} escrow is not settled by refund and delivery",
        )
    check(
        "NAM_deliver_mobilisation_orders = yes" in hostilities
        and hostilities.find('load_oob = "NAM_resource_war"')
        < hostilities.find("NAM_deliver_mobilisation_orders = yes"),
        "paid orders must be delivered at hostilities after the OOB defines templates",
    )
    check(
        "NAM_rw_close_preparation = yes" in entry_event
        and "NAM_refund_mobilisation_orders = yes"
        in named_block(effects, "NAM_rw_close_preparation"),
        "a stopped war entry must refund the paid orders",
    )
    order_cap_trigger = named_block(triggers, "NAM_order_can_place")
    check(
        "var = NAM_order_cap value = NAM_orders_paid compare = greater_than"
        in order_cap_trigger
        and "var = NAM_orders_paid value = 6 compare = less_than" in order_cap_trigger,
        "mobilisation orders must respect NAM_order_cap and the ceiling of six",
    )

    # Restitution clock and the field missions.
    clamp = named_block(effects, "NAM_rw_tension_clamp")
    check(
        "id = ADISCORD_nam_resource_war.20" in clamp
        and "id = ADISCORD_nam_resource_war.21" in clamp
        and "NAM_rw_war_window_open = yes" in clamp
        and "id = ADISCORD_nam_resource_war.1 days = 7 random_days = 14" in clamp,
        "the restitution clamp must own the notes, ultimatum and war thresholds",
    )
    window = named_block(triggers, "NAM_rw_war_window_open")
    check(
        "days > 299" in window and "days > 664" in window,
        "the war window must keep the 300-day minimum and the protocol's 365-day delay",
    )
    tokens = read("common/synchronized_dynamic_tokens/ADISCORD_tokens.txt")
    for mission in ("NAM_hold_field_67", "NAM_hold_field_689", "NAM_hold_field_690"):
        mission_block = named_block(prewar_decisions, mission)
        check(
            "available = { hidden_trigger = { always = no } }" in mission_block
            and "days_mission_timeout = 120" in mission_block
            and "timeout_effect" in mission_block,
            f"{mission} must be a 120-day timeout-only mission",
        )
        check(
            re.search(rf"(?m)^{mission}\s*$", tokens) is not None,
            f"{mission} is not registered in the synchronized token file",
        )
    check(
        "tag = RHM" in ai
        and "id = EFL" in ai
        and "tag = MZR" in ai
        and "id = AZH" in ai,
        "the two profitable volunteer routes are incomplete",
    )
    check(
        "tag = KDR" not in ai and "tag = SDR" not in ai,
        "non-beneficiary southern states were incorrectly mobilised",
    )
    check(
        "skip_default_capitulation" in on_actions
        and len(typed_blocks(on_actions, "on_capitulation")) == 1
        and len(typed_blocks(on_actions, "on_capitulation_immediate")) == 1,
        "bespoke capitulation routing is incomplete",
    )
    check(
        news.count("news_event = {") == 8,
        "world news must contain war start, uprising/suppression, the compromise, "
        "two terminal outcomes and the two ends of the great war of return",
    )

    news_blocks = typed_blocks(news, "news_event")
    for event_id in (
        "ADISCORD_nam_resource_news.1",
        "ADISCORD_nam_resource_news.2",
        "ADISCORD_nam_resource_news.3",
        "ADISCORD_nam_resource_news.5",
        "ADISCORD_nam_resource_news.6",
        "ADISCORD_nam_resource_news.7",
    ):
        definitions = [
            block
            for block in news_blocks
            if re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block)
        ]
        check(len(definitions) == 1, f"{event_id} must have exactly one definition")
        if definitions:
            # Campaign dispatch guards prevent repeats; major broadcasts must
            # remain deliverable to every recipient, without a global one-shot.
            check(
                "is_triggered_only = yes" in definitions[0]
                and "fire_only_once = no" in definitions[0]
                and "major = yes" in definitions[0]
                and "hidden = yes" not in definitions[0],
                f"{event_id} must be visible major and triggered-only, without a global one-shot",
            )

    all_script_sources = {
        path.relative_to(ROOT).as_posix(): path.read_text(
            encoding="utf-8-sig", errors="strict"
        )
        for root_name in ("common", "events", "history")
        for path in (ROOT / root_name).rglob("*.txt")
    }
    expected_news_calls = {
        "ADISCORD_nam_resource_news.1": "ADISCORD_nam_resource_war_begin_hostilities",
        "ADISCORD_nam_resource_news.2": "ADISCORD_nam_resource_war_resolve_coalition_victory",
        "ADISCORD_nam_resource_news.3": "ADISCORD_nam_resource_war_resolve_nam_victory",
        "ADISCORD_nam_resource_news.5": "ADISCORD_nam_resource_war_start_mainland_rebellion",
        "ADISCORD_nam_resource_news.6": "ADISCORD_nam_resource_war_mark_rebels_defeated",
        "ADISCORD_nam_resource_news.7": "ADISCORD_nam_resource_war_resolve_compromise",
    }
    for event_id, effect_name in expected_news_calls.items():
        call_pattern = re.compile(
            rf"news_event\s*=\s*\{{\s*id\s*=\s*{re.escape(event_id)}(?:\s|\}})",
            re.DOTALL,
        )
        definition_sites = [
            relative
            for relative, source in all_script_sources.items()
            if relative.startswith("events/")
            and any(
                re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block)
                for block in typed_blocks(source, "news_event")
            )
        ]
        check(
            definition_sites == ["events/ADISCORD_nam_resource_war_events.txt"],
            f"{event_id} has missing or duplicate definitions: {definition_sites}",
        )
        call_sites = [
            relative
            for relative, source in all_script_sources.items()
            if not relative.startswith("events/") and call_pattern.search(source)
        ]
        check(
            call_sites
            == ["common/scripted_effects/ADISCORD_nam_resource_war_effects.txt"],
            f"{event_id} has missing or duplicate/delayed call sites: {call_sites}",
        )
        effect_block = named_block(effects, effect_name)
        check(
            call_pattern.search(effect_block) is not None,
            f"{event_id} is not called by its production outcome {effect_name}",
        )
    for effect_name in (
        "ADISCORD_nam_resource_war_resolve_coalition_victory",
        "ADISCORD_nam_resource_war_resolve_nam_victory",
        "ADISCORD_nam_resource_war_resolve_standoff",
        "ADISCORD_nam_resource_war_resolve_compromise",
    ):
        outcome = named_block(effects, effect_name)
        check(
            "ADISCORD_nam_resource_war_active = yes" in outcome
            and "set_global_flag = ADISCORD_nam_resource_war_resolved" in outcome,
            f"{effect_name} lacks the active-war/single-resolution guard",
        )
    check(
        "ADISCORD_nam_resource_war_start = yes"
        in named_block(effects, "ADISCORD_nam_debug_start_resource_war"),
        "debug start does not smoke the production opening-news path",
    )
    check(
        "ADISCORD_nam_resource_war_resolve_coalition_victory = yes"
        in named_block(effects, "ADISCORD_nam_debug_resolve_coalition_victory"),
        "debug coalition action does not smoke its production outcome-news path",
    )
    check(
        "ADISCORD_nam_resource_war_resolve_nam_victory = yes"
        in named_block(effects, "ADISCORD_nam_debug_resolve_nam_victory"),
        "debug NAM action does not smoke its production outcome-news path",
    )
    scenario_debug_category = named_block(
        debug_categories, "ADISCORD_scenario_debug_category"
    )
    check(
        has_script_fragment(scenario_debug_category, "allowed = { always = yes }")
        and has_script_fragment(scenario_debug_category, "visible = { is_debug = yes }"),
        "shared scenario debug category must allow country switching and remain debug-only",
    )
    check(
        "ADISCORD_nam_resource_war_resolve_compromise = yes"
        in named_block(effects, "ADISCORD_nam_debug_resolve_compromise"),
        "debug compromise action does not smoke its production outcome-news path",
    )
    for decision_name in (
        "ADISCORD_nam_debug_start_resource_war",
        "ADISCORD_nam_debug_resolve_coalition_victory",
        "ADISCORD_nam_debug_resolve_nam_victory",
        "ADISCORD_nam_debug_resolve_compromise",
        "ADISCORD_nam_debug_add_tension",
    ):
        decision = named_block(debug_decisions, decision_name)
        decision_tags = set(
            re.findall(
                r"\btag\s*=\s*([A-Z0-9]{3})\b",
                named_block(decision, "allowed"),
            )
        )
        check(
            decision_tags == {"NAM", "EFL", "AZH", "SLF"},
            f"NAM debug decision {decision_name} has wrong allowed tags: {sorted(decision_tags)}",
        )
    obsolete_uprising_tokens = (
        "ADISCORD_nam_resource_war_resolve_uprising_victory",
        "ADISCORD_nam_debug_resolve_uprising_victory",
        "ADISCORD_nam_resource_news.4",
        "set_cosmetic_tag = SLF_svetlogorsk_republic",
        "SLF_svetlogorsk_republic_proclaimed",
    )
    terminal_sources = "\n".join((effects, on_actions, debug_decisions, news))
    for token in obsolete_uprising_tokens:
        check(
            token not in terminal_sources,
            f"obsolete surviving-SLF route remains: {token}",
        )

    capitulation = named_block(on_actions, "on_capitulation_immediate")
    coalition_route = re.search(
        r"ROOT\s*=\s*\{\s*tag\s*=\s*NAM\b.*?"
        r"FROM\s*=\s*\{\s*OR\s*=\s*\{([^}]*)\}.*?"
        r"ADISCORD_nam_resource_war_resolve_coalition_victory\s*=\s*yes",
        capitulation,
        re.DOTALL,
    )
    check(
        coalition_route is not None
        and all(
            f"tag = {tag}" in coalition_route.group(1) for tag in ("EFL", "AZH", "SLF")
        ),
        "NAM defeat by EFL, AZH, or SLF must use the coalition settlement",
    )
    record_capitulation = named_block(
        effects, "ADISCORD_nam_resource_war_record_capitulation"
    )
    check(
        "ADISCORD_nam_resource_war_defender_capitulation = yes" in record_capitulation
        and "flag = ADISCORD_nam_capitulation_reserved" in record_capitulation,
        "NAM shared capitulation recorder lacks its current-war gate or receipt",
    )
    for hook in ("on_capitulation_immediate", "on_capitulation"):
        check(
            "ROOT = { ADISCORD_nam_resource_war_record_capitulation = yes }"
            in named_block(on_actions, hook),
            f"NAM {hook} does not dispatch the shared capitulation recorder",
        )

    # Compromise peace: the rump NAM survives with its islands, the coalition
    # takes the fields it holds, and a year of tribute begins.
    check(
        "ADISCORD_nam_resource_war_resolve_peaceful_withdrawal" not in effects
        and "ADISCORD_nam_resource_war_peaceful_partition" not in effects,
        "the dead peaceful-withdrawal settlement must be removed",
    )
    compromise = named_block(effects, "ADISCORD_nam_resource_war_resolve_compromise")
    for token in (
        "set_global_flag = ADISCORD_nam_resource_war_resolved",
        "set_global_flag = ADISCORD_nam_resource_war_compromise",
        "clr_global_flag = ADISCORD_nam_resource_war_started",
        "VAL_cancel_nam_concession = yes",
        "VAL_settle_resource_aid = yes",
        "ADISCORD_nam_resource_war_end_all_wars = yes",
        "ADISCORD_nam_resource_war_clear_temporary_support = yes",
        "NAM_rw_start_tribute = yes",
        "tree = NAM_defeated_focus",
        "keep_completed = no",
        "annex_country = { target = SLF transfer_troops = no }",
        "ADISCORD_nam_resource_news.7",
    ):
        check(token in compromise, f"compromise peace lacks {token}")
    for state_id in (67, 689, 690, 719):
        check(
            f"{state_id} = {{ NAM_rw_compromise_cede_field = yes }}" in compromise,
            f"compromise peace does not settle field {state_id} by its controller",
        )
    check(
        "annex_country = { target = NAM" not in compromise
        and all(f"transfer_state = {state}" not in compromise for state in range(225, 232)),
        "compromise peace must keep NAM and its island states",
    )
    check(
        compromise.find("NAM_rw_compromise_cede_field = yes")
        < compromise.find("ADISCORD_nam_resource_war_end_all_wars = yes"),
        "compromise transfers must read wartime control before white peace",
    )
    nam_victory_tree = named_block(effects, "ADISCORD_nam_resource_war_resolve_nam_victory")
    check(
        "tree = NAM_postwar_focus" in nam_victory_tree
        and "keep_completed = yes" in nam_victory_tree,
        "NAM victory must load the post-war tree and keep completed focuses",
    )
    tribute = named_block(effects, "NAM_rw_start_tribute")
    check(
        "flag = NAM_rw_tribute" in tribute and "days = 365" in tribute,
        "tribute must be the 365-day NAM_rw_tribute country flag",
    )

    coalition_victory = named_block(
        effects, "ADISCORD_nam_resource_war_resolve_coalition_victory"
    )
    efl_settlement = named_block(coalition_victory, "EFL")
    for state_id in (67, 688, 689, 690, 700, 719):
        check(
            f"{state_id} = {{ NAM_rw_cede_mainland_state = yes }}" in coalition_victory,
            f"coalition treaty does not cede mainland state {state_id}",
        )
    cede = named_block(effects, "NAM_rw_cede_mainland_state")
    check(
        has_script_fragment(
            cede,
            "AZH = { transfer_state = PREV } remove_core_of = NAM add_core_of = AZH add_claim_by = NAM set_state_controller_to = AZH",
        )
        and has_script_fragment(
            cede,
            "EFL = { transfer_state = PREV } remove_core_of = NAM add_core_of = EFL add_claim_by = NAM set_state_controller_to = EFL",
        )
        and all(f"state = {state_id}" in cede for state_id in (689, 690, 700, 719)),
        "mainland cession must give Azhar the southern fields and the harbour and Eflor the rest",
    )
    check(
        "annex_country = { target = SLF transfer_troops = no }" in efl_settlement,
        "EFL does not eliminate the temporary SLF uprising",
    )
    check(
        has_script_fragment(
            coalition_victory,
            "688 = { remove_core_of = SLF if = { limit = { is_owned_by = EFL } remove_core_of = NAM add_core_of = EFL add_claim_by = NAM set_state_controller_to = EFL } }",
        ),
        "state 688 cleanup is incomplete",
    )

    nam_victory = named_block(effects, "ADISCORD_nam_resource_war_resolve_nam_victory")
    check(
        "annex_country = { target = SLF transfer_troops = no }" in nam_victory,
        "NAM victory does not eliminate a surviving SLF uprising",
    )
    check(
        "transfer_state = 688" in nam_victory
        and has_script_fragment(
            nam_victory,
            "688 = { remove_core_of = SLF add_core_of = NAM set_state_controller_to = NAM }",
        ),
        "NAM victory does not restore state 688 and remove its temporary SLF core",
    )

    for outcome in (coalition_victory, nam_victory):
        check(
            all(
                token not in outcome
                for token in (
                    "leave_faction = yes",
                    "remove_from_faction",
                    "dismantle_faction",
                )
            ),
            "NAM resolution must not dismantle the permanent EFL-AZH faction",
        )

    mainland_rebellion = named_block(
        effects, "ADISCORD_nam_resource_war_start_mainland_rebellion"
    )
    for token in (
        "transfer_state = 688",
        "set_capital = { state = 688 }",
        "688 = { add_core_of = SLF",
        "declare_war_on = { target = NAM",
    ):
        check(
            has_script_fragment(mainland_rebellion, token),
            f"mainland Svetlogorsk rebellion is missing {token}",
        )
    slf_spawn_scope = named_block(mainland_rebellion, "SLF")
    check(
        "transfer_state = 688" in slf_spawn_scope,
        "compact state 688 must be transferred inside the SLF recipient scope",
    )
    check(
        "transfer_state = 70" not in mainland_rebellion
        and "set_capital = { state = 70 }" not in mainland_rebellion
        and "70 = { add_core_of = SLF" not in effects,
        "SLF must not receive, core, or use EFL state 70 as its capital",
    )
    check(
        "ADISCORD_nam_resource_war_start_island_rebellion" not in effects,
        "obsolete island-rebellion effect still exists",
    )
    check(
        "transfer_state = 67"
        not in named_block(
            effects, "ADISCORD_nam_resource_war_start_mainland_rebellion"
        ),
        "the rebellion must not remove NAM's only mainland core",
    )
    slf_core_states = set(
        re.findall(
            r"(?m)^\s*(\d+)\s*=\s*\{[^{}]*add_core_of\s*=\s*SLF",
            mainland_rebellion,
        )
    )
    check(
        slf_core_states == {"688"},
        f"SLF must core only compact internal state 688, found {sorted(slf_core_states)}",
    )
    defeat = named_block(effects, "ADISCORD_nam_resource_war_mark_rebels_defeated")
    check(
        "NAM = { transfer_state = 688 }" in defeat
        and has_script_fragment(
            defeat, "688 = { remove_core_of = SLF set_state_controller_to = NAM }"
        ),
        "defeated uprising must return state 688 and remove only its temporary SLF core",
    )
    for state_id in range(225, 232):
        check(
            f"transfer_state = {state_id}" not in mainland_rebellion,
            f"the opening uprising still receives island state {state_id}",
        )

    restitution_coalition = named_block(ideas, "ADISCORD_nam_restitution_coalition")
    check(
        "picture = generic_war_preparation" in restitution_coalition,
        "restitution coalition must use the registered generic_war_preparation picture",
    )

    public_sources = "\n".join(
        (
            effects,
            news,
            ideas,
            slf_oob,
            sources["docs/lore/countries.md"],
        )
    )
    check(
        "ADISCORD_nam_insurgent_columns = {" in ideas,
        "SLF insurgent-column national spirit is missing",
    )
    check(
        "ADISCORD_nam_republican_volunteer_columns" not in public_sources,
        "obsolete republican SLF spirit key remains",
    )
    for obsolete in (
        "Союз свободных островов",
        "островные освободительные",
        "островного восстания",
        "Island Liberation Column",
        "Svetlogorsk Republican Corps",
        "Svetlogorsk Republic",
    ):
        check(
            obsolete.casefold() not in public_sources.casefold(),
            f"obsolete island-union concept remains in public content: {obsolete}",
        )

    check(
        "ADISCORD_coastal_patrol_ship = {" in equipment_source
        and "ADISCORD_coastal_patrol_ship_1 = {" in equipment_source,
        "coastal patrol ship archetype/equipment is missing",
    )
    patrol_archetype = named_block(equipment_source, "ADISCORD_coastal_patrol_ship")
    patrol_variant = named_block(equipment_source, "ADISCORD_coastal_patrol_ship_1")
    check(
        re.search(r"(?m)^\s*type\s*=\s*screen_ship\s*$", patrol_archetype) is not None,
        "coastal patrol archetype must use the engine ship category screen_ship",
    )
    check(
        re.search(r"(?m)^\s*type\s*=\s*\{\s*screen_ship\s*\}\s*$", patrol_variant)
        is not None,
        "coastal patrol variant must use the engine ship category screen_ship",
    )
    equipment_bonus_enum = named_block(script_enums, "script_enum_equipment_bonus_type")
    for equipment_id in (
        "ADISCORD_coastal_patrol_ship",
        "ADISCORD_coastal_patrol_ship_1",
    ):
        check(
            re.search(rf"(?m)^\s*{equipment_id}\s*$", equipment_bonus_enum) is not None,
            f"{equipment_id} is missing from script_enum_equipment_bonus_type",
        )
    patrol_subunit = named_block(naval_units, "ADISCORD_coastal_patrol_vessel")
    check(
        "map_icon_category = ship" in patrol_subunit
        and "type = { screen_ship }" in patrol_subunit
        and "need = { ADISCORD_coastal_patrol_ship = 1 }" in patrol_subunit,
        "custom coastal patrol subunit is missing or does not consume its ship archetype",
    )
    check(
        "critical_parts = { destroyed_ammo_storage broken_propeller on_fire rudder_jammed }"
        in patrol_subunit
        and "critical_part_damage_chance_mult = 1" in patrol_subunit,
        "coastal patrol subunit must declare exercise critical parts",
    )
    crit_table = read("common/units/critical_parts/00_critical_parts.txt")
    for part in (
        "destroyed_ammo_storage",
        "broken_propeller",
        "on_fire",
        "rudder_jammed",
    ):
        check(
            re.search(rf"(?m)^\s*{part}\s*=\s*\{{", crit_table) is not None,
            f"missing critical part {part}",
        )
    fleet_contracts = (
        ("NAM", "history/units/NAM.txt", 4, 30, 16716, 700, 1, 688),
        ("EFL", "history/units/EFL.txt", 3, 20, 6495, 70, 2, 70),
        ("AZH", "history/units/AZH.txt", 2, 15, 493, 692, 1, 692),
    )
    for (
        tag,
        relative,
        ships,
        convoys,
        port,
        state_id,
        port_level,
        dockyard_state_id,
    ) in fleet_contracts:
        oob = sources[relative]
        check(oob.count("fleet = {") == 1, f"{tag} must have exactly one coastal fleet")
        check(
            oob.count("definition = ADISCORD_coastal_patrol_vessel") == ships,
            f"{tag} coastal fleet must contain exactly {ships} patrol ships",
        )
        check(
            f"naval_base = {port}" in oob and f"location = {port}" in oob,
            f"{tag} fleet is not based at verified coastal province {port}",
        )
        check(
            f"type = convoy_1 amount = {convoys} producer = {tag}" in oob,
            f"{tag} must receive exactly {convoys} starting convoys",
        )
        state = state_source(state_id)
        check(
            re.search(
                rf"(?ms)^\s*{port}\s*=\s*\{{.*?naval_base\s*=\s*{port_level}\b", state
            )
            is not None,
            f"state {state_id} lacks level-{port_level} naval base at province {port}",
        )
        dockyard_state = state_source(dockyard_state_id)
        check(
            re.search(r"(?m)^\s*dockyard\s*=\s*1\s*$", dockyard_state) is not None,
            f"state {dockyard_state_id} lacks its single proportional dockyard",
        )

    uprising_state = state_source(688)
    check(
        re.search(r"(?ms)^\s*689\s*=\s*\{.*?naval_base\s*=\s*2\b", uprising_state)
        is not None,
        "state 688 lacks the level-2 Svetlogorsk port at spawn province 689",
    )
    check(
        slf_oob.count("location = 689") == 3,
        "all three SLF divisions must spawn at Svetlogorsk province 689",
    )

    starting_armies = {
        "NAM": ("history/units/NAM.txt", [176, 6099, 8058], 3),
        "EFL": ("history/units/EFL.txt", [259, 8057, 6495, 6331], 4),
        "AZH": ("history/units/AZH.txt", [367, 493, 8234], 3),
    }
    for tag, (
        relative,
        expected_locations,
        expected_divisions,
    ) in starting_armies.items():
        units = named_block(sources[relative], "units")
        locations = [
            int(value)
            for value in re.findall(
                r"division\s*=\s*\{.*?\blocation\s*=\s*(\d+)", units, re.DOTALL
            )
        ]
        check(
            units.count("division = {") == expected_divisions,
            f"{tag} must begin with {expected_divisions} deliberately weak divisions",
        )
        check(
            locations == expected_locations,
            f"{tag} starting divisions are not distributed across owned states: {locations}",
        )

    fleet_oobs = {
        path.name
        for path in (ROOT / "history" / "units").glob("*.txt")
        if "fleet = {" in path.read_text(encoding="utf-8-sig", errors="strict")
    }
    check(
        fleet_oobs
        == {"NAM.txt", "EFL.txt", "AZH.txt", "NOD.txt", "STP.txt", "VAL.txt"},
        f"starting fleets must match NAM/EFL/AZH/NOD/STP/VAL, found {sorted(fleet_oobs)}",
    )
    technology_manifest = json.loads(
        read("tools/data/adiscord_starting_technology_profiles.json")
    )
    for tag, relative in (
        ("NAM", "history/countries/NAM - NamestnikLand.txt"),
        ("EFL", "history/countries/EFL - Eflor.txt"),
        ("AZH", "history/countries/AZH - Azhar Black Basin.txt"),
    ):
        history = sources[relative]
        check(
            "set_technology = {" not in history,
            f"{tag} history duplicates the generated starting technology system",
        )
        country_profile = technology_manifest["countries"].get(tag, {})
        check(
            "naval" in country_profile.get("profiles", ()),
            f"{tag} generated starting profile lacks naval continuity",
        )
        for technology in (
            "ADISCORD_tech_coastal_patrols",
            "ADISCORD_tech_convoy_routing",
        ):
            check(
                technology in country_profile.get("technologies_2160", ()),
                f"{tag} generated profile lacks proportional naval technology {technology}",
            )

    check(owner_of_state(67) == "NAM", "state 67 is no longer the NAM resource basin")
    check(
        owner_of_state(688) == "NAM",
        "state 688 must begin as a NAM core before the internal uprising",
    )
    check(
        owner_of_state(689) == "NAM", "state 689 must begin as NAM's South Coast district"
    )
    check(
        owner_of_state(700) == "NAM", "state 700 must begin as NAM's residual port city"
    )
    check(
        owner_of_state(690) == "NAM", "state 690 must begin as NAM's Dryriver district"
    )
    check(
        re.search(
            r"(?m)^\s*capital\s*=\s*700\s*$",
            sources["history/countries/NAM - NamestnikLand.txt"],
        )
        is not None,
        "NAM history capital must be residual port state 700",
    )
    check(
        owner_of_state(68) == "EFL"
        and owner_of_state(70) == "EFL"
        and owner_of_state(691) == "EFL",
        "EFL is not NAM's actual western neighbour",
    )
    check(
        owner_of_state(69) == "AZH" and owner_of_state(692) == "AZH",
        "AZH is not NAM's actual eastern neighbour",
    )
    expected_resources = {
        67: {"oil": 80, "chromium": 6},
        688: {"oil": 12, "chromium": 1},
        689: {"oil": 36, "chromium": 5},
        690: {"oil": 24, "chromium": 3},
        719: {"oil": 12},
    }
    for state_id, resources in expected_resources.items():
        state = state_source(state_id)
        for resource, amount in resources.items():
            check(
                re.search(rf"(?m)^\s*{resource}\s*=\s*{amount}\s*$", state) is not None,
                f"state {state_id} must contain {amount} {resource}",
            )
    check(
        sum(resources["oil"] for resources in expected_resources.values()) == 164
        and sum(resources.get("chromium", 0) for resources in expected_resources.values())
        == 15,
        "NAM resource redistribution changed the theatre's total deposits",
    )
    azh_resources = {69: {"oil": 2, "chromium": 1}, 692: {"oil": 1, "chromium": 1}}
    for state_id, resources in azh_resources.items():
        state = state_source(state_id)
        for resource, amount in resources.items():
            check(
                re.search(rf"(?m)^\s*{resource}\s*=\s*{amount}\s*$", state) is not None,
                f"state {state_id} must contain {amount} {resource}",
            )
    check(
        re.search(r"(?m)^\s*arms_factory\s*=\s*1\s*$", state_source(67)) is not None
        and re.search(r"(?m)^\s*arms_factory\s*=", state_source(688)) is None,
        "NAM military industry was not moved out of the uprising district",
    )

    nam_war_oob = sources["history/units/NAM_resource_war.txt"]
    check(
        [
            int(value)
            for value in re.findall(r"(?m)^\s*location\s*=\s*(\d+)\s*$", nam_war_oob)
        ]
        == [4912, 8058, 2299],
        "NAM wartime baseline must be one guard and two infantry divisions on the field fronts",
    )
    starting_templates = sources["history/units/NAM.txt"]
    order_templates = named_block(effects, "NAM_order_ensure_templates")
    unlock_templates = named_block(effects, "NAM_order_unlock_templates")
    template_sources = (
        ("Capital Guard", starting_templates, 78, 9, ("engineer", "artillery")),
        ("Line Infantry Brigade", starting_templates, 3, 6, ("engineer",)),
        ("Motor Column", order_templates, 5, 4, ("engineer", "artillery")),
        ("Coastal Battalion", order_templates, 6, 3, ("artillery",)),
    )
    for template, owner, counter, battalions, support in template_sources:
        definitions = [
            block for block in typed_blocks(owner, "division_template")
            if f'name = "{template}"' in block
        ]
        check(len(definitions) == 1, f"{template} must have one owning definition")
        definition = definitions[0] if definitions else ""
        check(
            f'template_counter = {counter}' in definition
            and "is_locked = yes" in definition
            and f'\\"{template}\\"' in effects
            and f'division_template = "{template}"' in unlock_templates
            and f'name = "{template}"' not in nam_war_oob,
            f"{template} must keep its distinct icon, fixed order composition and settlement unlock",
        )
        unit = "ADISCORD_mechanized_infantry" if template == "Motor Column" else "infantry"
        regiments = named_block(definition, "regiments")
        companies = named_block(definition, "support")
        check(
            regiments.count(f"{unit} = {{") == battalions
            and regiments.count("x =") == battalions
            and all(f"{company} = {{" in companies for company in support)
            and companies.count("x =") == len(support),
            f"{template} must retain the composition covered by its fixed order price",
        )
        if owner == starting_templates:
            check(
                "force_allow_recruiting = yes" in definition
                and f'name = "{template}"' not in order_templates,
                f"{template} must remain recruitable and be reused without a mobilisation duplicate",
            )
    check(
        "check_variable = { NAM_order_coastal_paid > 0 }" in order_templates
        and "check_variable = { NAM_order_motor_paid > 0 }" in order_templates
        and "template_counter = 34" in named_block(effects, "NAM_marine_ensure_template"),
        "specialist templates must be created for paid orders and marines must have their own icon",
    )
    check(
        not re.search(r'name = "NAM (?:Resource|Coastal|Motor|Island)', effects),
        "NAM templates must not expose a technical country prefix",
    )

    expected_victory_points = {
        67: {6099: 3},
        68: {259: 5, 6150: 2},
        69: {367: 5, 8234: 2},
        70: {2986: 2, 6495: 4},
        688: {16721: 3, 1710: 2},
        689: {},
        690: {8058: 2, 9016: 2},
        691: {},
        692: {493: 3, 5039: 2},
        700: {16716: 5},
        701: {16717: 5},
        719: {},
        720: {8057: 3},
        721: {},
        722: {},
    }
    for state_id, points in expected_victory_points.items():
        state = state_source(state_id)
        actual_points = [
            (int(province), int(value))
            for province, value in re.findall(
                r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", without_comments(state)
            )
        ]
        check(
            sorted(actual_points) == sorted(points.items()),
            f"state {state_id} must have exactly these victory points: {points}, found {actual_points}",
        )
    check(
        sum(sum(expected_victory_points[state].values()) for state in (67, 688, 689, 690, 700, 719))
        == 17,
        "NAM mainland VP total must be 17",
    )
    check(
        sum(sum(expected_victory_points[state].values()) for state in (68, 70, 691, 701, 720, 721))
        == 21,
        "EFL mainland VP total must be 21",
    )
    check(
        sum(sum(expected_victory_points[state].values()) for state in (69, 692, 722)) == 12,
        "AZH mainland VP total must be 12",
    )

    localisation = (
        ROOT / "localisation" / "russian" / "ADISCORD_nam_resource_war_l_russian.yml"
    )
    raw_loc = localisation.read_bytes() if localisation.exists() else b""
    check(
        raw_loc.startswith(b"\xef\xbb\xbf"),
        "Russian localisation must retain UTF-8 BOM",
    )
    loc = raw_loc.decode("utf-8-sig") if raw_loc else ""
    check(
        'faction_eflor_azhar_restitution_alliance: "Эфлорско-ажарский союз"' in loc,
        "missing Russian localisation for the permanent EFL-AZH faction",
    )
    check(
        'SLF: "Светлогорское восстание"' in loc,
        "SLF public name must be Svetlogorsk Uprising",
    )
    check(
        'SLF_humanism: "Светлогорское восстание"' in loc,
        "SLF ideology name must remain an uprising before victory",
    )
    check(
        'SLF_humanism_party: "Временный штаб восстания"' in loc,
        "SLF party must be the Provisional Uprising Headquarters",
    )
    for obsolete in (
        "Союз свободных островов",
        "островные освободительные",
        "островного восстания",
        "Республиканские добровольческие",
    ):
        check(
            obsolete.casefold() not in loc.casefold(),
            f"obsolete island-union localisation remains: {obsolete}",
        )
    for key in (
        "SLF_Yaroslav_Veter",
        "ADISCORD_coastal_patrol_vessel",
        "ADISCORD_coastal_patrol_ship",
        "ADISCORD_coastal_patrol_ship_1",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_training_factor",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_mission_factor",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_combat_factor",
        "ADISCORD_nam_resource_news.1.t",
        "ADISCORD_nam_resource_news.1.d",
        "ADISCORD_nam_resource_news.1.a",
        "ADISCORD_nam_resource_news.2.t",
        "ADISCORD_nam_resource_news.2.d",
        "ADISCORD_nam_resource_news.2.a",
        "ADISCORD_nam_resource_news.3.t",
        "ADISCORD_nam_resource_news.3.d",
        "ADISCORD_nam_resource_news.3.a",
        "ADISCORD_nam_debug_start_resource_war",
        "ADISCORD_nam_debug_resolve_coalition_victory",
        "ADISCORD_nam_debug_resolve_nam_victory",
        "ADISCORD_nam_debug_resolve_compromise",
        "ADISCORD_nam_debug_add_tension",
        "NAM_restitution",
        "NAM_restitution_desc",
        "NAM_mobilisation",
        "NAM_mobilisation_desc",
        "NAM_prepare_line",
        "NAM_prepare_line_desc",
        "NAM_cost_line",
        "NAM_cost_line_blocked",
        "NAM_cost_line_tooltip",
        "NAM_cost_order_guard",
        "NAM_cost_order_guard_blocked",
        "NAM_cost_order_guard_tooltip",
        "NAM_cost_order_infantry",
        "NAM_cost_order_infantry_blocked",
        "NAM_cost_order_infantry_tooltip",
        "NAM_cost_order_motor",
        "NAM_cost_order_motor_blocked",
        "NAM_cost_order_motor_tooltip",
        "NAM_cost_order_coastal",
        "NAM_cost_order_coastal_blocked",
        "NAM_cost_order_coastal_tooltip",
        "ADISCORD_nam_resource_news.7.t",
        "ADISCORD_nam_resource_news.7.d",
        "ADISCORD_nam_resource_news.1.d_strike",
    ):
        check(
            re.search(rf"(?m)^\s*{re.escape(key)}:", loc) is not None,
            f"missing localisation key {key}",
        )
    check(
        "ADISCORD_nam_resource_news.4" not in loc,
        "obsolete uprising-victory news localisation remains",
    )
    check(
        "ADISCORD_nam_debug_resolve_uprising_victory" not in loc,
        "obsolete uprising-victory debug localisation remains",
    )
    check(
        loc.count("§RDEBUG:§!") == 9,
        "all nine debug entry points need the red DEBUG prefix",
    )
    for veter_key in (
        "ADISCORD_nam_resource_war.2.d",
        "ADISCORD_nam_resource_news.5.d",
        "ADISCORD_nam_resource_news.6.d",
    ):
        value = re.search(rf'(?m)^\s*{re.escape(veter_key)}:\d*\s*"(.*)"\s*$', loc)
        check(
            value is not None and "Ярослав Вебер" in value.group(1),
            f"{veter_key} must name Yaroslav Weber",
        )

    check_oil_monopoly(
        effects,
        triggers,
        on_actions,
        prewar_decisions,
        prewar_categories,
        news,
        hostilities,
    )
    check_ladder(
        effects,
        triggers,
        on_actions,
        prewar_decisions,
        prewar_categories,
        news,
        hostilities,
    )
    check_settlement(
        effects,
        triggers,
        prewar_decisions,
        prewar_categories,
        news,
        loc,
    )
    check_colony_and_exile(
        effects,
        triggers,
        on_actions,
        prewar_decisions,
        prewar_categories,
        news,
        loc,
    )
    check_exile_revolution(
        effects,
        triggers,
        on_actions,
        prewar_decisions,
        prewar_categories,
        news,
        loc,
    )

    for relative, size in (
        ("gfx/flags/SLF.tga", (82, 52)),
        ("gfx/flags/medium/SLF.tga", (41, 26)),
        ("gfx/flags/small/SLF.tga", (10, 7)),
    ):
        path = ROOT / relative
        check(path.exists(), f"missing {relative}")
        if path.exists():
            with Image.open(path) as image:
                check(
                    image.size == size, f"{relative}: expected {size}, got {image.size}"
                )

    if ISSUES:
        print("NAM resource-war validation failed:")
        for issue in ISSUES:
            print(f"- {issue}")
        return 1
    print("NAM resource-war validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
