#!/usr/bin/env python3
"""Static semantic checks for the A-DISCORD economy/AI integration."""

from __future__ import annotations

import re
import sys
from pathlib import Path


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


def validate() -> list[str]:
    issues: list[str] = []
    effects = strip_comments(read("common/scripted_effects/ADISCORD_economy_effects.txt"))
    modifier_effects = strip_comments(
        read("common/scripted_effects/ADISCORD_economy_modifier_effects.txt")
    )
    triggers = strip_comments(read("common/scripted_triggers/ADISCORD_economy_triggers.txt"))
    on_actions = strip_comments(read("common/on_actions/00_ADISCORD_on_actions.txt"))
    default_ai = strip_comments(read("common/ai_strategy/default.txt"))
    economy_ai = strip_comments(read("common/ai_strategy/ADISCORD_economy_ai.txt"))
    gui = strip_comments(read("interface/ADISCORD_economy.gui"))
    interface_gfx = strip_comments(read("interface/ADISCORD_economy.gfx"))
    scripted_gui = strip_comments(read("common/scripted_guis/ADISCORD_economy_scripted_gui.txt"))
    scripted_loc = strip_comments(read("common/scripted_localisation/ADISCORD_economy_scripted_loc.txt"))
    ideas = strip_comments(read("common/ideas/ADISCORD_economy_ideas.txt"))
    buildings = strip_comments(read("common/buildings/00_buildings.txt"))
    dynamic_modifiers = strip_comments(
        read("common/dynamic_modifiers/ADISCORD_economy_dynamic_modifiers.txt")
    )
    localisation = read("localisation/russian/ADISCORD_economy_l_russian.yml")

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

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
        "ADISCORD_economy_calculate_debt_capacity",
        "ADISCORD_economy_calculate_debt_ratio",
        "ADISCORD_economy_calculate_creditworthiness",
        "ADISCORD_economy_calculate_interest_rate",
        "ADISCORD_economy_calculate_debt_service_amount",
        "ADISCORD_economy_update_macro_confidence",
    ]
    positions = [macro.find(step) for step in ordered_steps]
    require(all(position >= 0 for position in positions), "macro pass is missing a required derived calculation")
    require(positions == sorted(positions), "macro pass is not ordered deterministically")
    for step in ordered_steps:
        require(macro.count(step) == 1, f"macro pass calls {step} more than once")

    policy = block(effects, "ADISCORD_economy_ai_monthly_policy")
    require("else_if" in policy, "AI monthly policy is not an exclusive ordered decision chain")
    require("ADISCORD_economy_increase_army_spending" in policy, "AI never restores army spending")
    require("ADISCORD_economy_increase_construction_spending" in policy, "AI never restores construction spending")
    require("ADISCORD_economy_increase_social_spending" in policy, "AI never restores social spending")

    emission = block(effects, "ADISCORD_economy_expand_money_emission")
    require("ADISCORD_economy_treasury" in emission, "money emission creates no liquidity")
    require("ADISCORD_economy_current_month_action_income" in effects, "ledger lacks action-income accounting")
    reduce_emission = block(effects, "ADISCORD_economy_reduce_money_emission")
    require("ADISCORD_economy_recent_money_printing" in reduce_emission,
            "emission can be expanded and reversed in the same accounting month")
    require("ADISCORD_economy_has_treasury_room_35" in block(triggers, "ADISCORD_economy_can_expand_money_emission"),
            "money emission can charge penalties when the treasury has no room")
    require("ADISCORD_economy_has_debt_room_58" in block(triggers, "ADISCORD_economy_can_take_debt"),
            "internal borrowing can charge penalties for a zero-sized loan")
    require("ADISCORD_economy_has_debt_room_64" in block(triggers, "ADISCORD_economy_can_take_external_loan"),
            "external borrowing can charge penalties for a zero-sized loan")

    apply_balance = block(effects, "ADISCORD_economy_apply_weekly_balance")
    require("ADISCORD_economy_last_period_cap_writeoff" in apply_balance,
            "treasury-cap overflow is not recorded in the ledger")
    require(apply_balance.find("ADISCORD_economy_last_period_cap_writeoff") < apply_balance.find("ADISCORD_economy_treasury_after_tick"),
            "treasury is snapshotted before cap overflow is recorded")
    require("value = ADISCORD_economy_last_period_cap_writeoff" in apply_balance,
            "cap writeoff is missing from the accounting identity")
    require("ADISCORD_economy_last_period_unfunded_deficit" in apply_balance,
            "unfunded deficit is not recorded in the weekly ledger")
    require("value = ADISCORD_economy_last_period_unfunded_deficit" in apply_balance,
            "treasury-floor adjustment is missing from the accounting identity")
    require(apply_balance.find("value = ADISCORD_economy_last_period_unfunded_deficit")
            < apply_balance.find("ADISCORD_economy_last_period_unexplained_delta"),
            "unexplained delta is calculated before the treasury-floor adjustment")
    require("ADISCORD_economy_final_deficit_pressure_factor_bp" in apply_balance,
            "unfunded-deficit pressure ignores its custom modifier")

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

    for cooldown in (
        "ADISCORD_economy_tax_change_cooldown",
        "ADISCORD_economy_army_budget_change_cooldown",
        "ADISCORD_economy_construction_budget_change_cooldown",
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
    require("local_building_slots_factor = 0.05" in block(buildings, "ADISCORD_business_center"),
            "business center lacks its distinct commercial-slot role")
    require("local_building_slots_factor = 0.02" in block(buildings, "ADISCORD_science_center"),
            "science center still duplicates the stronger commercial/industrial state role")
    require("local_factory_energy_consumption = 0.20" in block(buildings, "ADISCORD_industrial_cluster"),
            "industrial cluster lacks its visible heavy-industry energy burden")
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

    construction_expenses = block(effects, "ADISCORD_economy_calculate_construction_expenses")
    require("num_of_available_civilian_factories" in construction_expenses,
            "construction expenses ignore actual assigned civilian capacity")
    military_factory_expenses = block(effects, "ADISCORD_economy_calculate_military_factory_expenses")
    require("num_of_available_military_factories" in military_factory_expenses,
            "military-industry expenses ignore actual assigned factories")
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

    migration = block(effects, "ADISCORD_economy_migrate_schema")
    require("value = 11 compare = less_than" in migration,
            "economy save migration was not advanced to schema 11")
    require("ADISCORD_economy_recalculate_policy_modifiers = yes" in migration,
            "schema 11 does not initialize weekly policy caches for existing saves")
    require("ADISCORD_economy_was_at_war" in migration
            and "ADISCORD_economy_postwar_demobilization_months" in migration,
            "schema 11 does not initialize postwar demobilization state")
    weekly_budget = block(effects, "ADISCORD_economy_calculate_weekly_budget")
    require("ADISCORD_economy_safe_reserve value = ADISCORD_economy_weekly_expenses" in weekly_budget
            and "ADISCORD_economy_safe_reserve min = 50 max = 250" in weekly_budget,
            "schema 11 reserve target does not reuse the O(1) weekly forecast")
    for settlement_name in ("ADISCORD_economy_apply_weekly_balance", "ADISCORD_economy_apply_monthly_balance"):
        settlement = block(effects, settlement_name)
        require("ADISCORD_economy_auto_borrow_temp" in settlement
                and "ADISCORD_economy_auto_loan_enabled" not in settlement,
                f"{settlement_name} still allows hidden save state to disable deficit borrowing")
    for retired_name in (
        "ADISCORD_economy_auto_loan_enabled",
        "ADISCORD_economy_toggle_auto_loan",
        "ADISCORD_economy_gui_page",
        "ADISCORD_economy_research_spending_mode",
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
    require('position = { x = -420 y = -280 }' in gui and re.search(r"Orientation\s*=\s*CENTER", gui, re.I),
            "economy dashboard is not centered for common screen resolutions")
    require("size = { width = 840 height = 560 }" in gui,
            "economy dashboard no longer fits the supported 1366x768 layout envelope")
    require("ADISCORD_economy_header_art" not in gui,
            "economy dashboard still uses the broken decorative header sprite")
    require(len(re.findall(r'name\s*=\s*"ADISCORD_economy_(?:tax|army|construction|social)_step_[1-5]"', gui)) == 20,
            "economy dashboard does not expose four complete five-step scales")
    require(len(re.findall(r'name\s*=\s*"ADISCORD_economy_(?:tax|army|construction|social)_active_marker"', gui)) == 4,
            "economy dashboard does not expose one active marker per budget scale")
    require(re.search(r'buttonText\s*=\s*"[+-]"', gui) is None,
            "economy dashboard still uses blank text +/- controls")
    require("GFX_button_123x34" not in gui,
            "economy dashboard still uses the button sprite that clips compact policy controls")
    require(not (ROOT / "common/decisions/ADISCORD_economy_decisions.txt").exists(),
            "economy actions have returned to the decisions menu")
    require(not (ROOT / "common/decisions/categories/ADISCORD_economy_categories.txt").exists(),
            "economy decision category still exists")
    require(not (ROOT / "common/decisions/ADISCORD_society_development_debug_decisions.txt").exists(),
            "society-development debug decisions are exposed at game start")
    require(not (ROOT / "common/decisions/categories/ADISCORD_society_development_debug_categories.txt").exists(),
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
        r'name\s*=\s*"(ADISCORD_economy_(?:tax|army|construction|social)_(?:decrease|increase))"', gui
    ))
    expected_regulators = {
        f"ADISCORD_economy_{category}_{direction}"
        for category in ("tax", "army", "construction", "social")
        for direction in ("decrease", "increase")
    }
    require(visible_regulators == expected_regulators,
            "economy UI must expose exactly eight compact arrow budget controls")
    for category in ("tax", "army", "construction", "social"):
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
    require('pdx_tooltip = "ADISCORD_economy_budget_breakdown_tt"' in gui,
            "balance KPI lacks the requested income/expense breakdown tooltip")
    require('name = "ADISCORD_economy_topbar_icon"' in gui
            and 'spriteType = "GFX_ADISCORD_treasury_icon"' in gui,
            "topbar lacks the compact treasury icon")
    require('name = "ADISCORD_economy_topbar_value"' in gui
            and 'text = "ADISCORD_economy_topbar_treasury_value"' in gui,
            "topbar lacks the numeric-only treasury value")
    require('name = "GFX_ADISCORD_treasury_icon"' in interface_gfx,
            "temporary treasury icon sprite is not registered")

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
