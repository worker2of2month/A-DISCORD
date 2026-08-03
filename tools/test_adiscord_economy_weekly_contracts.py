import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
BUILDINGS = (ROOT / "common" / "buildings" / "00_buildings.txt").read_text(
    encoding="utf-8-sig"
)
ECONOMY_AI = (
    ROOT / "common" / "ai_strategy" / "ADISCORD_economy_ai.txt"
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


class WeeklyEconomyContracts(unittest.TestCase):
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

    def test_weekly_update_has_no_full_refresh_or_map_scan(self):
        weekly = block(EFFECTS, "ADISCORD_economy_weekly_update")
        self.assertEqual(weekly.count("ADISCORD_economy_apply_weekly_balance = yes"), 1)
        self.assertIn("ADISCORD_economy_prepare_weekly_country = yes", weekly)
        self.assertNotIn("ADISCORD_economy_initialize_country = yes", weekly)
        for forbidden in (
            "ADISCORD_economy_full_refresh",
            "ADISCORD_economy_recount_economic_buildings",
            "every_country",
            "every_owned_state",
            "all_owned_state",
        ):
            self.assertNotIn(forbidden, weekly)

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
            self.assertIn("ADISCORD_economy_refresh_spending_ideas = yes", action)

    def test_player_is_notified_when_a_deficit_triggers_automatic_borrowing(self):
        settlement = block(EFFECTS, "ADISCORD_economy_apply_weekly_balance")
        auto_borrow = settlement[
            settlement.index("ADISCORD_economy_auto_borrow_temp value = 0.1") :
        ]
        self.assertIn("is_ai = no", auto_borrow)
        self.assertIn(
            "country_event = { id = ADISCORD_economy.1 }", auto_borrow
        )

        event_path = ROOT / "events" / "ADISCORD_economy_events.txt"
        self.assertTrue(event_path.is_file())
        event_text = event_path.read_text(encoding="utf-8-sig")
        notification = block(event_text, "country_event")
        self.assertIn("id = ADISCORD_economy.1", notification)
        self.assertIn("is_triggered_only = yes", notification)
        self.assertIn("title = ADISCORD_economy.1.t", notification)
        self.assertIn("desc = ADISCORD_economy.1.d", notification)

        for key in (
            "ADISCORD_economy.1.t",
            "ADISCORD_economy.1.d",
            "ADISCORD_economy.1.a",
        ):
            self.assertRegex(ECONOMY_LOC, rf"(?m)^\s*{re.escape(key)}:\d*\s+")
        self.assertIn("ADISCORD_economy_last_auto_borrowing", ECONOMY_LOC)

    def test_schema_seven_preserves_existing_treasury(self):
        migration = block(EFFECTS, "ADISCORD_economy_migrate_schema")
        self.assertIn("value = 7", migration)
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
        self.assertIn("ADISCORD_economy_last_period_unfunded_deficit", ECONOMY_LOC)
        self.assertIn("ADISCORD_economy_last_period_unexplained_delta", ECONOMY_LOC)
        self.assertNotIn(
            "Фактическое изменение казны происходит раз в месяц", ECONOMY_LOC
        )

    def test_unfunded_deficit_is_a_known_accounting_adjustment(self):
        settlement = block(EFFECTS, "ADISCORD_economy_apply_weekly_balance")
        field = "ADISCORD_economy_last_period_unfunded_deficit"
        self.assertIn(f"var = {field} value = 0", settlement)
        self.assertIn(f"var = {field} value = ADISCORD_economy_last_uncovered_deficit", settlement)
        expected_start = settlement.find("ADISCORD_economy_accounting_expected_treasury_after_temp")
        adjustment = settlement.find(f"value = {field}", expected_start)
        unexplained = settlement.find("ADISCORD_economy_last_period_unexplained_delta", expected_start)
        self.assertGreater(adjustment, expected_start)
        self.assertGreater(unexplained, adjustment)

    def test_unfunded_deficit_pressure_respects_modifier_factor(self):
        settlement = block(EFFECTS, "ADISCORD_economy_apply_weekly_balance")
        uncovered = settlement.find("ADISCORD_economy_last_uncovered_deficit value = 0")
        pressure_factor = settlement.find(
            "ADISCORD_economy_final_deficit_pressure_factor_bp", uncovered
        )
        self.assertGreater(pressure_factor, uncovered)

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

    def test_ai_building_targets_are_bounded_by_fiscal_state(self):
        expected = {
            "ADISCORD_ai_fiscal_crisis": (0, 0, 0),
            "ADISCORD_ai_fiscal_stress": (0, 0, 0),
            "ADISCORD_ai_fiscal_recovery": (1, 0, 0),
            "ADISCORD_ai_healthy_civilian_growth": (2, 1, 1),
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
            r"building_target\s+id\s*=\s*ADISCORD_industrial_cluster\s+value\s*=\s*2\b",
        )

    def test_building_tooltips_lead_with_role_and_budget_impact(self):
        self.assertNotIn("Строятся в обычном меню", ECONOMY_LOC)
        for key, role, budget in (
            ("ADISCORD_business_center_desc", "Роль: доход", "+0,90"),
            ("ADISCORD_science_center_desc", "Роль: исследования", "-0,42"),
            ("ADISCORD_industrial_cluster_desc", "Роль: производство", "+0,08"),
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
        self.assertEqual(len(modifier_keys), 42)
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
