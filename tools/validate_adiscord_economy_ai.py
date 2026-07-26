#!/usr/bin/env python3
"""Static semantic checks for the A-DISCORD economy/AI integration."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
    triggers = strip_comments(read("common/scripted_triggers/ADISCORD_economy_triggers.txt"))
    on_actions = strip_comments(read("common/on_actions/00_ADISCORD_on_actions.txt"))
    default_ai = strip_comments(read("common/ai_strategy/default.txt"))
    economy_ai = strip_comments(read("common/ai_strategy/ADISCORD_economy_ai.txt"))
    gui = strip_comments(read("interface/ADISCORD_economy.gui"))
    interface_gfx = strip_comments(read("interface/ADISCORD_economy.gfx"))
    scripted_gui = strip_comments(read("common/scripted_guis/ADISCORD_economy_scripted_gui.txt"))
    scripted_loc = strip_comments(read("common/scripted_localisation/ADISCORD_economy_scripted_loc.txt"))
    localisation = read("localisation/russian/ADISCORD_economy_l_russian.yml")

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require("ADISCORD_economy_schema_version" in effects, "economy lacks a schema-versioned migration")
    require("ADISCORD_economy_migrate_schema" in effects, "economy lacks ADISCORD_economy_migrate_schema")

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
    for state in ("healthy", "stressed", "crisis", "recovery"):
        require(f"ADISCORD_economy_ai_is_{state}" in triggers, f"missing AI economy trigger for {state}")

    monthly = block(effects, "ADISCORD_economy_monthly_update")
    yearly = block(effects, "ADISCORD_economy_yearly_update")
    require("ADISCORD_economy_update_ai_state" in monthly, "monthly update does not refresh AI state")
    require("ADISCORD_economy_apply_yearly_balance" in yearly, "secondary yearly economy lacks aggregate fiscal semantics")
    require("ADISCORD_economy_full_refresh = yes" not in monthly.split("ADISCORD_economy_building_recount_months", 1)[0],
            "monthly update performs an unconditional building scan")
    require("ADISCORD_economy_full_refresh_if_needed" in monthly,
            "monthly update lacks a dirty-state building refresh")
    require("ADISCORD_economy_tick_budget_cooldowns" in monthly,
            "monthly update does not release budget-control cooldowns")
    require(monthly.find("ADISCORD_economy_apply_monthly_balance") < monthly.find("ADISCORD_economy_tick_budget_cooldowns"),
            "budget cooldowns expire before the selected policy is charged")

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

    emission = block(effects, "ADISCORD_economy_expand_money_emission")
    require("ADISCORD_economy_treasury" in emission, "money emission creates no liquidity")
    require("ADISCORD_economy_current_month_action_income" in effects, "ledger lacks action-income accounting")
    reduce_emission = block(effects, "ADISCORD_economy_reduce_money_emission")
    require("ADISCORD_economy_recent_money_printing" in reduce_emission,
            "emission can be expanded and reversed in the same accounting month")

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
    ):
        require(cooldown in effects and cooldown in triggers, f"budget control lacks cooldown {cooldown}")

    army_expenses = block(effects, "ADISCORD_economy_calculate_army_expenses")
    require("has_army_manpower" in army_expenses, "army upkeep is disconnected from fielded manpower")
    require(re.search(r"has_army_manpower\s*=\s*\{\s*size\s*>", army_expenses) is not None,
            "army-upkeep manpower thresholds do not use the engine-supported comparison syntax")
    resource_income = block(effects, "ADISCORD_economy_calculate_resource_income")
    recount = block(effects, "ADISCORD_economy_recount_economic_buildings")
    require("ADISCORD_economy_resource_endowment" in resource_income,
            "strategic rent ignores the country's resource endowment")
    require("resource@steel" in recount and "resource@oil" in recount and "resource@coal" in recount,
            "owned-state refresh does not build a real resource-endowment index")
    require("check_variable = { resource@steel >" in recount,
            "resource-endowment checks do not use the engine-supported state resource syntax")
    require("damaged_building_level@industrial_complex" in recount,
            "bombing disruption is not connected to actual damaged industry")
    require("ADISCORD_economy_public_investment_stock" in effects,
            "reserve investment has no persistent productive-capital stock")

    require("value = 3 compare = less_than" in block(effects, "ADISCORD_economy_migrate_schema"),
            "economy save migration was not advanced for the tabbed GUI state")
    require("ADISCORD_economy_gui_page" in effects,
            "economy does not initialize and persist the selected dashboard page")
    require("clamp_variable = { var = ADISCORD_economy_gui_page min = 0 max = 2 }" in effects,
            "dashboard page state is not clamped to the three valid pages")

    require('name = "ADISCORD_economy_dashboard_window"' in gui, "economy dashboard window is missing")
    require('position = { x = -460 y = -340 }' in gui and re.search(r"Orientation\s*=\s*CENTER", gui, re.I),
            "economy dashboard is not centered for common screen resolutions")
    require("size = { width = 920 height = 700 }" in gui,
            "economy dashboard no longer fits the supported 1366x768 layout envelope")
    require("ADISCORD_economy_header_art" not in gui,
            "economy dashboard still uses the broken decorative header sprite")
    require("GFX_ADISCORD_economy_slider_button" not in gui,
            "economy dashboard still uses the clipped custom tab indicator sprite")
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
    require(gui.count("position = { x = -445 y = -155 }") == 3,
            "economy content pages are not aligned below the KPI row")
    require(gui.count("size = { width = 890 height = 500 }") == 3,
            "economy content pages do not fit below the rebuilt navigation area")
    require('name = "ADISCORD_economy_budget_model"' not in gui,
            "budget page still duplicates the long model summary and overlaps its controls")
    require("ADISCORD_economy_overview_refresh_click" in scripted_gui,
            "read-only overview page lacks the engine binding needed for reliable registration")

    page_indexes = {"overview": 0, "budget": 1, "operations": 2}
    for page, page_index in page_indexes.items():
        page_name = f"ADISCORD_economy_{page}_page"
        page_script_name = f"ADISCORD_economy_{page}_script"
        page_script = block(scripted_gui, page_script_name)
        require(f'name = "{page_name}"' in gui, f"economy dashboard lacks its {page} page container")
        require(f'window_name = "{page_name}"' in page_script,
                f"economy dashboard does not bind the {page} page as a separate window")
        require("ADISCORD_economy_window_is_open = yes" in page_script,
                f"economy dashboard can show the {page} page while the shell is closed")
        require(
            re.search(
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*ADISCORD_economy_gui_page\s+value\s*=\s*{page_index}\s+compare\s*=\s*equals\s*\}}",
                page_script,
            )
            is not None,
            f"economy dashboard does not exclusively gate the {page} page",
        )
        require(f"ADISCORD_economy_tab_{page}_click" in scripted_gui, f"economy dashboard lacks a {page} tab action")

        tab_match = re.search(
            rf'name\s*=\s*"ADISCORD_economy_tab_{page}"\s+'
            rf'quadTextureSprite\s*=\s*"GFX_generic_box_smallest"',
            gui,
        )
        require(tab_match is not None,
                f"economy dashboard {page} tab does not use the stable vanilla button sprite")

    gui_buttons = set(re.findall(r'buttonType\s*=\s*\{.*?name\s*=\s*"(ADISCORD_economy_[^"]+)"', gui, re.S))
    require(bool(gui_buttons), "economy dashboard contains no discoverable interactive buttons")
    for button_name in sorted(gui_buttons):
        require(f"{button_name}_click" in scripted_gui, f"GUI button {button_name} has no scripted click effect")
        guarded = (
            "_tax_burden_" in button_name
            or "_army_budget_" in button_name
            or "_construction_budget_" in button_name
            or "_action_" in button_name
            or "_tab_" in button_name
        )
        if guarded and button_name != "ADISCORD_economy_action_toggle_auto_loan":
            require(f"{button_name}_click_enabled" in scripted_gui,
                    f"GUI button {button_name} gives no disabled-state feedback")

    for action in ("early_repay_debt", "war_taxes"):
        require(f'ADISCORD_economy_action_{action}' in gui,
                f"the dashboard does not expose the {action} economy operation")
        require(f"ADISCORD_economy_gui_try_{action}" in effects,
                f"the dashboard operation {action} has no guarded GUI effect")

    localisation_keys = set(re.findall(r"(?m)^\s*([A-Za-z0-9_.-]+):", localisation))
    for match in re.finditer(r'(?:text|buttonText|pdx_tooltip)\s*=\s*"([^"]+)"', gui):
        key = match.group(1)
        if key in {"CLOSE", "X", "1", "2", "3", "4", "5"}:
            continue
        require(key in localisation_keys, f"economy GUI references missing localisation key {key}")
    custom_sprites = set(re.findall(r'"(GFX_ADISCORD_economy_[^"]+)"', gui))
    for sprite in custom_sprites:
        require(f'name = "{sprite}"' in interface_gfx, f"economy GUI references undefined sprite {sprite}")
    require("GetADISCORDEconomyAdviceLoc" in scripted_loc,
            "economy dashboard has no contextual policy recommendation")

    monthly_on_action = block(block(on_actions, "on_actions"), "on_monthly")
    require("every_country" not in monthly_on_action, "on_monthly contains a global country scan")

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
