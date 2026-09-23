"""Source-executing regressions for productive income and recovery focus routes.

These fixtures check script arithmetic and authored routes, not the native game.
"""
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_economy_weekly_contracts import (
    EconomyScriptFixture, EFFECTS, MODIFIER_EFFECTS, TRIGGERS, block,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
P = "ADISCORD_economy_"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def focus(text, identifier):
    for tree in parse_clausewitz(text):
        if tree.key != "focus_tree":
            continue
        for node in tree.value:
            if node.key == "focus" and any(c.key == "id" and c.value == identifier for c in node.value):
                return node.value
    raise AssertionError(f"missing focus {identifier}")


def walk(entries, previews=False):
    for node in entries:
        if not previews and node.key == "effect_tooltip":
            continue
        yield node
        if isinstance(node.value, list):
            yield from walk(node.value, previews)


def income_fixture(civilian=25, military=12, resources=10, business=2):
    source = EFFECTS + MODIFIER_EFFECTS
    facts = {name: False for name in re.findall(
        r"\b(ADISCORD_(?:economy_(?:cached_has_|model_is_)\w+|\w+_development_(?:at_least|exact)_\d))\s*=\s*yes", source)}
    facts[P + "model_is_mixed"] = True
    fixture = EconomyScriptFixture(facts=facts)
    fixture.definitions.update({n.key: n.value for n in parse_clausewitz(MODIFIER_EFFECTS)})
    v = fixture.scopes["A"]
    for name in set(re.findall(r"\bADISCORD_\w+_factor_bp\b", source)):
        v[name] = 100
    v.update({P + "cached_civilian_factories": civilian,
              P + "cached_military_factories": military,
              P + "resource_endowment": resources,
              P + "cached_resource_trade_law_factor": 1,
              P + "state_financial_control": 50,
              P + "investment_confidence": 50,
              P + "tax_burden_mode": 3,
              P + "monthly_expenses": 18,
              P + "treasury": 100,
              "ADISCORD_business_center_count": business})
    return fixture


class EconomyRefreshCadenceTests(unittest.TestCase):
    def fixture(self, human=True, opened=False):
        # Isolate periodic pressure/AI work; execute the actual refresh routing,
        # law caches and treasury-cap arithmetic against fixed native inputs.
        isolated = (
            "initialize_country", "update_postwar_demobilization", "clear_one_month_action_ideas",
            "recount_economic_buildings", "refresh_ai_assistance", "update_bombing_disruption",
            "calculate_income", "calculate_macro_indicators", "calculate_expenses",
            "calculate_monthly_balance", "update_ai_state", "ai_monthly_policy", "ai_yearly_policy",
            "update_monthly_budget_trend", "apply_tax_burden_side_effects", "update_fiscal_stress",
            "update_inflation", "update_casualty_delta", "update_war_fatigue",
            "tick_postwar_demobilization", "update_demographic_fatigue", "update_workforce_drain",
            "update_stretched", "update_public_investment_stock", "calculate_development_multiplier",
            "check_economic_development_upgrade", "refresh_spending_ideas", "clear_recent_action_flags",
            "tick_budget_cooldowns", "clamp_all_variables", "light_update", "refresh_policy_previews",
            "update_gui", "set_simulation_tier",
        )
        facts = {name: False for name in re.findall(
            r"\b(ADISCORD_(?:economy_has_\w+|\w+_development_(?:at_least|at_most|exact)_\d))\s*=\s*yes",
            MODIFIER_EFFECTS + block(EFFECTS, P + "update_model_and_cycle"))}
        facts.update({P + "should_show_player_ui": human, "is_ai": not human,
                      P + "has_idea_free_trade": True, P + "has_idea_economic_system_mixed": True})
        f = EconomyScriptFixture(facts=facts, stubs=tuple(P + name for name in isolated))
        f.definitions.update({n.key: n.value for n in parse_clausewitz(MODIFIER_EFFECTS)})
        f.scopes["A"].update({P + "show_window": int(opened), P + "treasury": 1234,
                              "ADISCORD_state_development_level": 3,
                              "ADISCORD_economic_development_level": 2,
                              "ADISCORD_business_center_count": 1})
        return f

    def test_refresh_prices_policy_once_with_clean_dirty_and_quarterly_sources(self):
        for effect, months, dirty in (("monthly_update", 0, 0), ("monthly_update", 0, 1),
                                      ("monthly_update", 2, 0), ("monthly_update", 2, 1),
                                      ("yearly_update", 0, 0), ("open_window", 0, 0)):
            with self.subTest(effect=effect, months=months, dirty=dirty):
                f = self.fixture()
                f.scopes["A"].update({P + "building_recount_months": months,
                                      P + "needs_full_refresh": dirty})
                f.run(P + effect)
                self.assertEqual(f.calls.count(P + "recalculate_policy_modifiers"), 1)
                self.assertEqual(f.scopes["A"][P + "cached_resource_trade_law_factor"], 1.25)
                self.assertEqual(f.scopes["A"][P + "model"], 2)
                self.assertEqual(f.scopes["A"][P + "treasury"], 1234)
                if dirty or months == 2 or effect != "monthly_update":
                    self.assertEqual(f.scopes["A"][P + "treasury_cap"], 3100)
                    self.assertEqual(f.scopes["A"][P + "needs_full_refresh"], 0)

    def test_periodic_previews_run_only_for_open_human_window(self):
        for effect in ("monthly_update", "yearly_update"):
            for human, opened in ((False, False), (False, True), (True, False), (True, True)):
                with self.subTest(effect=effect, human=human, opened=opened):
                    f = self.fixture(human, opened)
                    f.run(P + effect)
                    self.assertEqual(f.calls.count(P + "refresh_policy_previews"), int(human and opened))

    def test_opening_window_refreshes_previews_before_display_without_paying_cash(self):
        f = self.fixture(opened=False)
        f.run(P + "open_window")
        self.assertEqual(f.calls.count(P + "refresh_policy_previews"), 1)
        self.assertLess(f.calls.index(P + "light_update"), f.calls.index(P + "refresh_policy_previews"))
        self.assertLess(f.calls.index(P + "refresh_policy_previews"), f.calls.index(P + "update_gui"))
        self.assertEqual(f.scopes["A"][P + "show_window"], 1)
        self.assertEqual(f.scopes["A"][P + "treasury"], 1234)

    def test_clean_month_keeps_damage_on_existing_cache_before_policy_refresh(self):
        for dirty, expected_disruption in ((0, 2), (1, 1)):
            with self.subTest(dirty=dirty):
                f = self.fixture()
                f.stubs.remove(P + "update_bombing_disruption")
                f.scopes["A"].update({P + "needs_full_refresh": dirty,
                                      P + "damaged_industry_score": 1,
                                      P + "final_bombing_disruption_resistance_factor_bp": 100,
                                      P + "static_bombing_disruption_resistance_bonus_bp": 100})
                f.run(P + "monthly_update")
                self.assertEqual(f.scopes["A"][P + "bombing_disruption_level"], expected_disruption)
                self.assertEqual(f.scopes["A"][P + "final_bombing_disruption_resistance_factor_bp"], 200)


class ProductiveIncomeTests(unittest.TestCase):
    def test_medium_civilian_economy_has_an_investable_weekly_surplus(self):
        f = income_fixture()
        f.run(P + "calculate_income")
        f.run(P + "calculate_weekly_budget")
        v = f.scopes["A"]
        self.assertGreaterEqual(v[P + "monthly_income"], 40)
        self.assertGreaterEqual(v[P + "weekly_balance"], 5)

    def test_an_extra_civilian_factory_has_material_recurring_revenue(self):
        results = []
        for count in (25, 26):
            f = income_fixture(civilian=count)
            f.run(P + "calculate_income")
            results.append(f.scopes["A"][P + "monthly_income"])
        self.assertGreaterEqual(results[1] - results[0], 0.9)
        self.assertLess(results[1] - results[0], 2)

    def test_business_center_is_an_income_investment(self):
        results = []
        for count in (0, 1):
            f = income_fixture(business=count)
            f.run(P + "calculate_income")
            results.append(f.scopes["A"][P + "monthly_income"])
        self.assertGreater(results[1] - results[0], 2.5)

    def test_no_resources_still_means_no_resource_rent(self):
        f = income_fixture(resources=0)
        f.run(P + "calculate_income")
        self.assertEqual(f.scopes["A"][P + "resource_income"], 0)

    def test_tax_preview_matches_full_recalculation_at_every_level(self):
        for level in range(1, 6):
            with self.subTest(level=level):
                cached = income_fixture()
                cached.run(P + "calculate_income")
                cached.scopes["A"][P + "tax_burden_mode"] = level
                cached.run(P + "recalculate_tax_dependent_income")
                full = income_fixture()
                full.scopes["A"][P + "tax_burden_mode"] = level
                full.run(P + "calculate_income")
                self.assertAlmostEqual(cached.scopes["A"][P + "monthly_income"],
                                       full.scopes["A"][P + "monthly_income"])

    def test_repeated_forecasts_do_not_multiply_income_or_pay_cash(self):
        f = income_fixture()
        f.run(P + "calculate_income")
        first = f.scopes["A"][P + "monthly_income"]
        for _ in range(10):
            f.run(P + "calculate_income")
        self.assertAlmostEqual(f.scopes["A"][P + "monthly_income"], first)
        self.assertEqual(f.scopes["A"][P + "treasury"], 100)


class DebtRepaymentGateTests(unittest.TestCase):
    def test_standard_repayment_requires_full_500_treasury_chunk(self):
        triggers = read("common/scripted_triggers/ADISCORD_economy_triggers.txt")
        effects = read("common/scripted_effects/ADISCORD_economy_effects.txt")
        gui = read("common/scripted_guis/ADISCORD_economy_scripted_gui.txt")
        ru = read("localisation/russian/ADISCORD_economy_l_russian.yml")
        en = read("localisation/english/ADISCORD_economy_l_english.yml")

        gate = block(triggers, "ADISCORD_economy_has_treasury_500")
        self.assertIn("value = 500", gate)
        self.assertIn("compare = greater_than_or_equals", gate)

        gui_try = block(effects, "ADISCORD_economy_gui_try_repay_debt")
        repay = block(effects, "ADISCORD_economy_repay_debt")
        self.assertIn("ADISCORD_economy_has_treasury_500 = yes", gui_try)
        self.assertIn("ADISCORD_economy_has_treasury_500 = yes", repay)
        self.assertNotIn("ADISCORD_economy_has_treasury_50 = yes", gui_try)
        self.assertNotIn("ADISCORD_economy_has_treasury_50 = yes", repay)
        self.assertNotIn("value = ADISCORD_economy_treasury", repay)

        self.assertIn(
            "ADISCORD_economy_action_repay_debt_click_enabled = { ADISCORD_economy_should_show_player_ui = yes ADISCORD_economy_has_treasury_500 = yes ADISCORD_economy_has_debt = yes }",
            gui,
        )
        self.assertIn("Требует §Y500§! в казне", ru)
        self.assertIn("Requires §Y500§! treasury", en)


class NorthernCampaignRouteTests(unittest.TestCase):
    def test_frontier_does_not_require_participation_in_the_stelander_crisis(self):
        nodes = focus(read("common/national_focus/ADISCORD_national_focus_VAL.txt"), "VAL_frontier_conference")
        alternatives = [{c.value for c in n.value if c.key == "focus"}
                        for n in nodes if n.key == "prerequisite"]
        self.assertIn({"VAL_The_Steel_Contract", "VAL_Market_Roads_North"}, alternatives)
        self.assertTrue(any(n.key == "VAL_frontier_postwar" for n in walk(nodes)))

    def test_demand_and_offensive_share_a_force_quality_gate_not_24_divisions(self):
        text = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for identifier in ("VAL_frontier_demand_CIN", "VAL_frontier_demand_ERT",
                           "VAL_frontier_begin_offensive"):
            with self.subTest(identifier=identifier):
                body = block(text, identifier)
                self.assertNotIn("num_divisions < 24", body)
                self.assertIn("VAL_ai_frontier_force_ready = no", body)
        gate = block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"),
                     "VAL_ai_frontier_force_ready")
        for token in ("has_army_manpower", "has_equipment", "has_capitulated = no", "is_subject = no"):
            self.assertIn(token, gate)

    def test_security_plan_pays_for_one_ultimatum_and_only_unlocks_scripted_war(self):
        nodes = focus(read("common/national_focus/ADISCORD_national_focus_VAL.txt"), "VAL_frontier_security_plan")
        self.assertTrue(any(n.key == "add_political_power" and float(n.value) >= 75 for n in walk(nodes)))
        self.assertFalse(any(n.key == "set_rule" for n in walk(nodes)))


class RecoveryRewardTests(unittest.TestCase):
    def test_shabrat_reforms_have_native_delta_previews_and_real_fiscal_gains(self):
        source = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        total = 0
        for suffix in ("count_the_cost", "reopen_tax_offices", "repair_workshops", "stabilize_currency", "recovery_budget"):
            identifier = "STP_pc_economy_" + suffix
            nodes = focus(source, identifier)
            self.assertTrue(any(n.key == "effect_tooltip" for n in walk(nodes, previews=True)), identifier)
            for node in walk(nodes):
                if node.key == "add_to_variable":
                    fields = {c.key: c.value for c in node.value}
                    if fields.get("var") == "STP_pw_ADISCORD_economy_overall_income_factor":
                        total += float(fields["value"])
        self.assertGreaterEqual(total, 0.35 - 1e-9)

    def test_kefreite_fiscal_reforms_are_persistent_not_one_off_money(self):
        text = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        for identifier in ("VAL_Contract_Accounting_Office", "VAL_Export_Clearing_House", "VAL_Industrial_Mobilization_Plan"):
            nodes = focus(text, identifier)
            changes = [
                {child.key: child.value for child in node.value}
                for node in walk(nodes)
                if node.key == "add_to_variable"
            ]
            expected_deltas = {
                "VAL_fiscal_administration_investment": "0.10",
                "VAL_fiscal_admin_savings": "-0.05",
            }
            for variable, expected in expected_deltas.items():
                self.assertTrue(
                    any(change.get("var") == variable and change.get("value") == expected
                        for change in changes), identifier,
                )
            self.assertTrue(
                any(node.key == "VAL_refresh_contract_modifier" and node.value == "yes"
                    for node in walk(nodes)), identifier,
            )
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        self.assertIn("VAL_fiscal_administration_investment", block(effects, "VAL_refresh_contract_modifier"))

    def test_mixed_fiscal_and_industry_previews_reject_a_wrong_delta(self):
        from tools.validators.validate_adiscord_val_rework import validate_val_preview_ideas
        ideas = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        dynamic = read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        sources = {"focuses": focuses, "effects": effects}
        self.assertEqual(validate_val_preview_ideas(ideas, sources, dynamic, effects)[1], [])
        source_delta = "var = VAL_fiscal_admin_savings value = -0.05"
        self.assertEqual(focuses.count(source_delta), 3)
        sources["focuses"] = focuses.replace(source_delta, "var = VAL_fiscal_admin_savings value = -0.10", 1)
        issues = validate_val_preview_ideas(ideas, sources, dynamic, effects)[1]
        self.assertTrue(any("VAL_fiscal_administration_delta does not match actual" in issue for issue in issues))



def building_budget_fixture(business=12, clusters=4, science=2):
    """Mixed economy, development 3, 250k army, active industry, normal budgets.

    Engine inputs: 60 civilian/30 military factories, four dockyards, 300 planes,
    twelve ships and 250 battalions. Monthly interest is six. No focus/flat-income bonuses apply.
    This executes authored arithmetic, not a native game campaign.
    """
    f = income_fixture(civilian=60, military=30, resources=10, business=business)
    for name in tuple(f.facts):
        match = re.search(r'_development_(at_least|exact)_(\d)$', name)
        if match:
            f.facts[name] = int(match[2]) <= 3 if match[1] == 'at_least' else int(match[2]) == 3
    # Every authored manpower threshold is below this scenario's 250,000 soldiers.
    f.facts.update({'has_army_manpower': True, 'has_war': False})
    values = f.scopes['A']
    values.update({
        'ADISCORD_industrial_cluster_count': clusters,
        'ADISCORD_science_center_count': science,
        'ADISCORD_state_development_level': 3,
        'ADISCORD_economic_development_level': 3,
        'ADISCORD_social_system_development_level': 3,
        'num_deployed_planes': 300,
        'num_ships': 12,
        'num_battalions': 250,
        P + 'cached_army_organization_factor': 1,
        P + 'cached_available_civilian_factories': 0,
        P + 'cached_available_military_factories': 0,
        P + 'cached_naval_factories': 4,
        P + 'army_spending_mode': 3,
        P + 'social_spending_mode': 3,
        P + 'research_spending_mode': 3,
        P + 'debt_service': 6,
        P + 'debt': 600,
        P + 'accounting_period_treasury_start': 100,
    })
    f.run(P + 'calculate_income')
    f.run(P + 'calculate_expenses')
    f.run(P + 'calculate_monthly_balance')
    f.run(P + 'calculate_weekly_budget')
    f.run(P + 'recalculate_treasury_cap')
    return f


class BuildingIncomeTests(unittest.TestCase):
    def test_developed_building_economy_exceeds_100_net_per_week(self):
        f = building_budget_fixture()
        values = f.scopes['A']
        self.assertGreater(values[P + 'monthly_expenses'], 40)
        self.assertEqual(values[P + 'debt_service'], 6)
        self.assertEqual(values[P + 'final_overall_income_factor_bp'], 100)
        self.assertEqual(values.get(P + 'final_weekly_income_bonus', 0), 0)
        self.assertGreaterEqual(values[P + 'weekly_balance'], 100)

    def test_business_center_adds_at_least_six_net_weekly_without_low_caps(self):
        for count in (0, 4, 12, 24):
            with self.subTest(existing_centers=count):
                before = building_budget_fixture(business=count).scopes['A']
                after = building_budget_fixture(business=count + 1).scopes['A']
                self.assertGreaterEqual(after[P + 'weekly_balance'] - before[P + 'weekly_balance'], 6)

    def test_industrial_cluster_adds_at_least_two_net_weekly_without_low_caps(self):
        for count in (0, 4, 12, 24):
            with self.subTest(existing_clusters=count):
                before = building_budget_fixture(clusters=count).scopes['A']
                after = building_budget_fixture(clusters=count + 1).scopes['A']
                self.assertGreaterEqual(after[P + 'weekly_balance'] - before[P + 'weekly_balance'], 2)

    def test_large_network_tax_preview_matches_full_calculation_and_never_pays(self):
        for level in range(1, 6):
            cached = building_budget_fixture(business=25, clusters=15)
            cached.scopes['A'][P + 'tax_burden_mode'] = level
            cached.run(P + 'recalculate_tax_dependent_income')
            full = building_budget_fixture(business=25, clusters=15)
            full.scopes['A'][P + 'tax_burden_mode'] = level
            full.run(P + 'calculate_income')
            self.assertAlmostEqual(cached.scopes['A'][P + 'monthly_income'], full.scopes['A'][P + 'monthly_income'])
            self.assertEqual(cached.scopes['A'][P + 'treasury'], 100)

    def test_large_weekly_surplus_reaches_cash_exactly_thirteen_times(self):
        f = building_budget_fixture()
        f.stubs.update(P + suffix for suffix in (
            'update_debt_state_after_settlement', 'queue_debt_notification',
        ))
        balance = f.scopes['A'][P + 'weekly_balance']
        self.assertGreaterEqual(balance, 100)
        for _ in range(13):
            f.run(P + 'apply_weekly_balance')
        self.assertAlmostEqual(f.scopes['A'][P + 'treasury'], 100 + 13 * balance)
        self.assertAlmostEqual(f.scopes['A'][P + 'last_period_unexplained_delta'], 0)
        self.assertEqual(f.scopes['A'][P + 'debt'], 600)

    def test_no_custom_buildings_does_not_get_a_free_weekly_bonus(self):
        f = building_budget_fixture(business=0, clusters=0, science=0)
        self.assertLess(f.scopes['A'][P + 'weekly_balance'], 25)
        self.assertEqual(f.scopes['A'][P + 'treasury'], 100)


    def test_science_network_has_large_but_bounded_native_research_bonuses(self):
        ideas = read('common/ideas/ADISCORD_economy_ideas.txt')
        for tier, expected in enumerate((0.05, 0.10, 0.15, 0.20), 1):
            body = block(ideas, P + f'science_network_{tier}')
            self.assertAlmostEqual(float(re.search(r'research_speed_factor\s*=\s*([\d.]+)', body)[1]), expected)

    def test_science_keeps_its_research_cost_instead_of_becoming_a_cash_printer(self):
        before = building_budget_fixture(science=0).scopes['A']
        after = building_budget_fixture(science=1).scopes['A']
        self.assertAlmostEqual(after[P + 'monthly_balance'] - before[P + 'monthly_balance'], -0.62)

    def test_storage_scales_with_the_economic_building_network(self):
        base = building_budget_fixture(business=0, science=0).scopes['A'][P + 'treasury_cap']
        business = building_budget_fixture(business=1, science=0).scopes['A'][P + 'treasury_cap']
        science = building_budget_fixture(business=0, science=1).scopes['A'][P + 'treasury_cap']
        self.assertEqual(business - base, 400)
        self.assertEqual(science - base, 160)
        large = building_budget_fixture(business=30, science=6).scopes['A'][P + 'treasury_cap']
        self.assertGreater(large, 12000)
        self.assertLessEqual(large, 20000)

    def test_ai_growth_targets_do_not_remove_crisis_or_peacetime_guards(self):
        text = read('common/ai_strategy/ADISCORD_economy_ai.txt')
        healthy = block(text, 'ADISCORD_ai_healthy_civilian_growth')
        for required in ('ADISCORD_economy_ai_is_healthy = yes', 'has_war = no', 'ADISCORD_economy_surplus_streak'):
            self.assertIn(required, healthy)
        self.assertIn('building_target id = ADISCORD_business_center value = 8', healthy)
        self.assertIn('building_target id = ADISCORD_science_center value = 2', healthy)
        self.assertIn('building_target id = ADISCORD_industrial_cluster value = 4', healthy)
        for name in ('ADISCORD_ai_fiscal_crisis', 'ADISCORD_ai_fiscal_stress'):
            body = block(text, name)
            for building in ('business_center', 'science_center', 'industrial_cluster'):
                self.assertIn('building_target id = ADISCORD_' + building + ' value = 0', body)



class ReserveInvestmentTests(unittest.TestCase):
    def fixture(self, cash=2000, balance=0, fund=0, ai=False):
        f = EconomyScriptFixture(facts={"is_ai": ai}, stubs=(
            P + "update_debt_state_after_settlement", P + "queue_debt_notification",
            P + "mark_dirty", "country_event"))
        f.scopes["A"].update({P + "treasury": cash, P + "treasury_cap": 2000,
            P + "accounting_period_treasury_start": cash, P + "weekly_balance": balance,
            P + "overflow_investment_fund": fund})
        return f

    def week(self, f):
        f.run(P + "apply_weekly_balance")
        f.run(P + "update_overflow_investments")

    def test_overflow_pays_weeks_without_debiting_treasury_twice(self):
        f = self.fixture(balance=25)
        self.week(f)
        v = f.scopes["A"]
        self.assertEqual(v[P + "treasury"], 2000)
        self.assertEqual(v[P + "overflow_investment_fund"], 15)
        self.assertEqual(v[P + "last_period_cap_writeoff"], 25)
        self.assertEqual(v[P + "last_period_unexplained_delta"], 0)
        self.assertTrue(v["idea@" + P + "overflow_investments"])
        self.assertEqual(f.calls.count("country_event"), 1)
        v[P + "weekly_balance"] = -5
        self.week(f)
        self.assertEqual(v[P + "treasury"], 1995)
        self.assertEqual(v[P + "overflow_investment_fund"], 5)
        self.week(f)
        self.assertFalse(v["idea@" + P + "overflow_investments"])
        self.assertEqual(v[P + "overflow_investment_fund"], 5)
        self.assertEqual(f.calls.count("country_event"), 1)

    def test_fractional_overflow_accumulates_until_a_full_week_is_paid(self):
        f = self.fixture(balance=9.5)
        self.week(f)
        v = f.scopes["A"]
        self.assertNotIn("idea@" + P + "overflow_investments", v)
        self.assertEqual(v[P + "overflow_investment_fund"], 9.5)
        v[P + "weekly_balance"] = 0.5
        self.week(f)
        self.assertTrue(v["idea@" + P + "overflow_investments"])
        self.assertEqual(v[P + "overflow_investment_fund"], 0)
        self.assertEqual(v[P + "last_period_unexplained_delta"], 0)

    def test_exact_cap_does_not_create_an_unfunded_bonus(self):
        f = self.fixture()
        self.week(f)
        self.assertEqual(f.scopes["A"][P + "overflow_investment_fund"], 0)
        self.assertNotIn("country_event", f.calls)
        self.assertNotIn("idea@" + P + "overflow_investments", f.scopes["A"])

    def test_reactivation_obeys_notification_cooldown_and_ai_is_silent(self):
        for ai in (False, True):
            f = self.fixture(fund=10, ai=ai)
            self.week(f)
            self.week(f)
            f.scopes["A"][P + "overflow_investment_fund"] = 10
            self.week(f)
            self.assertEqual(f.calls.count("country_event"), 0 if ai else 1)
            self.assertTrue(f.scopes["A"]["idea@" + P + "overflow_investments"])

    def test_capacity_recalculation_cannot_spend_or_duplicate_reserves(self):
        f = self.fixture(cash=2100, fund=7)
        v = f.scopes["A"]
        v[P + "final_treasury_capacity_factor_bp"] = 100
        for _ in range(3):
            f.run(P + "recalculate_treasury_cap")
        self.assertEqual(v[P + "treasury"], 2100)
        self.assertEqual(v[P + "overflow_investment_fund"], 7)
        self.week(f)
        self.assertEqual(v[P + "overflow_investment_fund"], 97)
        self.assertEqual(v[P + "last_period_unexplained_delta"], 0)

    def test_capacity_ceiling_and_minimum_follow_fourfold_scale(self):
        for count, factor, expected in ((0, 25, 1200), (0, 100, 2000), (100, 250, 20000)):
            f = self.fixture()
            f.scopes["A"].update({"ADISCORD_business_center_count": count,
                                   P + "final_treasury_capacity_factor_bp": factor})
            f.run(P + "recalculate_treasury_cap")
            self.assertEqual(f.scopes["A"][P + "treasury_cap"], expected)

    def test_regular_programs_require_and_charge_one_hundred(self):
        for name, gate in (("invest_reserves", "can_expand_public_capital"),
                           ("civilian_investment_action", "can_use_civilian_stimulus"),
                           ("military_investment_action", "can_use_military_investment")):
            f = EconomyScriptFixture(facts={P + gate: True,
                **{P + "model_is_" + model: False for model in (
                    "decentralized_market", "mixed", "technocratic", "oligarchic_clan",
                    "state_coordinated", "planned_bureaucratic")}}, stubs=(
                P + "initialize_country", P + "mark_dirty", P + "check_economic_development_upgrade", "add_timed_idea"))
            f.scopes["A"][P + "treasury"] = 100
            f.run(P + name)
            self.assertEqual(f.scopes["A"][P + "treasury"], 0)
            self.assertEqual(f.scopes["A"][P + "current_month_action_costs"], 100)
        for name in ("can_invest_reserves", "can_use_military_investment"):
            entries = parse_clausewitz(block(TRIGGERS, P + name))
            money_gate = [n for n in entries if n.key == "check_variable"
                          and any(c.value == P + "treasury" for c in n.value)]
            self.assertEqual(len(money_gate), 1)
            f = self.fixture(cash=99.99)
            self.assertFalse(f.condition(money_gate))
            f.scopes["A"][P + "treasury"] = 100
            self.assertTrue(f.condition(money_gate))


class PostwarProgramPriceTests(unittest.TestCase):
    PRICES = {
        "party_restore_ministries": 540, "party_reopen_port": 1080, "party_refit_guard": 900,
        "party_return_specialists": 540, "party_security_reserve": 540,
        "party_standard_order": 900, "party_frontier_exercise": 540,
        "restore_services": 720, "restart_workshops": 1080, "integrate_veterans": 540,
        "army_procurement": 900, "air_procurement": 1080, "border_dossier": 360,
    }

    def test_affordability_payment_accounting_and_localised_prices_agree(self):
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        loc = read("localisation/russian/ADISCORD_STP_l_russian.yml")
        for name, price in self.PRICES.items():
            with self.subTest(program=name):
                body = block(decisions, "STP_pw_" + name)
                f = EconomyScriptFixture()
                f.scopes["A"][P + "treasury"] = price - 0.01
                gate = parse_clausewitz(block(body, "custom_cost_trigger"))
                self.assertFalse(f.condition(gate))
                f.scopes["A"][P + "treasury"] = price
                self.assertTrue(f.condition(gate))
                transaction = [n for n in walk(parse_clausewitz(block(body, "complete_effect")))
                               if n.key in ("subtract_from_variable", "add_to_variable", "set_variable")
                               and any(c.key == "var" and c.value in (
                                   P + "treasury", P + "current_month_action_costs", "STP_pw_project_deposit")
                                   for c in n.value)]
                f.execute(transaction, "A", None, "A")
                self.assertEqual(f.scopes["A"][P + "treasury"], 0)
                self.assertEqual(f.scopes["A"][P + "current_month_action_costs"], price)
                if "STP_pw_project_deposit" in f.scopes["A"]:
                    self.assertEqual(f.scopes["A"]["STP_pw_project_deposit"], price)
                self.assertIn("custom_cost_text = STP_pw_price_" + str(price), body)
                for suffix in ("", "_blocked", "_tooltip"):
                    line = next(line for line in loc.splitlines()
                                if line.startswith(" STP_pw_price_" + str(price) + suffix + ":"))
                    self.assertIn(str(price) + "§!", line)

    def test_old_and_new_project_receipts_finish_and_refund_once(self):
        source = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        for effect in ("STP_pw_finish_project", "STP_pw_party_finish_project"):
            entries = parse_clausewitz(block(source, effect))
            # Isolate receipt alternatives from ownership and political engine predicates.
            alternatives = next(n for n in walk(entries) if n.key == "OR"
                                and any(c.key == "AND" for c in n.value))
            for branch in alternatives.value:
                kind = next(n for n in branch.value if n.key == "check_variable")
                kind_value = float(next(c.value for c in kind.value if c.key == "value"))
                receipts = next(n for n in branch.value if n.key == "OR")
                accepted = [float(next(c.value for c in n.value if c.key == "value"))
                            for n in receipts.value]
                self.assertEqual(accepted[3], accepted[2] * 1.2)
                self.assertEqual(accepted[0], accepted[2] * 9)
                for paid in accepted:
                    f = EconomyScriptFixture(stubs=(P + "mark_dirty",))
                    f.definitions.update({n.key: n.value for n in parse_clausewitz(source)})
                    v = f.scopes["A"]
                    v.update({"STP_pw_project_deposit": paid, "STP_pw_project_kind": kind_value,
                              P + "treasury": 0})
                    self.assertTrue(f.condition([receipts]))
                    f.run("STP_pw_cancel_project")
                    f.run("STP_pw_cancel_project")
                    self.assertEqual(v[P + "treasury"], paid)
                    self.assertEqual(v[P + "current_month_action_income"], paid)
                    self.assertNotIn("STP_pw_project_deposit", v)
                    self.assertNotIn("STP_pw_project_kind", v)


class BudgetAndLawBalanceTests(unittest.TestCase):
    def test_budget_switching_replaces_the_bonus_without_stacking_or_paying_cash(self):
        for budget in ("army", "research", "social"):
            f = EconomyScriptFixture()
            v = f.scopes["A"]
            v[P + "treasury"] = 137
            for level in (5, 3, 4, 1, 5, 5):
                v[P + budget + "_spending_mode"] = level
                f.run(P + "refresh_" + budget + "_policy_idea")
                active = [n for n in range(1, 6) if v.get("idea@" + P + budget + "_spending_" + str(n))]
                self.assertEqual(active, [level])
                self.assertEqual(v[P + "treasury"], 137)

    def test_law_replacement_queues_one_refresh_and_preserves_cash(self):
        refreshes = ("recalculate_policy_modifiers", "recalculate_treasury_cap",
                     "update_model_and_cycle", "light_update", "calculate_development_multiplier",
                     "refresh_policy_previews", "update_gui")
        f = EconomyScriptFixture(facts={P + "has_current_schema": True,
                                        P + "should_show_player_ui": True},
                                 stubs=(P + "mark_dirty", "country_event",
                                        *(P + name for name in refreshes)))
        v = f.scopes["A"]
        v.update({P + "treasury": 137, P + "debt": 250, P + "show_window": 1})
        for _ in range(4):
            f.run(P + "queue_law_refresh")
        self.assertEqual(f.calls.count("country_event"), 1)
        self.assertEqual(f.calls.count(P + "mark_dirty"), 1)
        f.run(P + "refresh_after_law_change")
        self.assertFalse(v[P + "law_refresh_pending"])
        actual = [name for name in f.calls if name in {P + n for n in refreshes}]
        self.assertEqual(actual, [P + n for n in refreshes])
        self.assertEqual(v[P + "treasury"], 137)
        self.assertEqual(v[P + "debt"], 250)
        f.run(P + "queue_law_refresh")
        self.assertEqual(f.calls.count("country_event"), 2)

    def test_law_refresh_does_not_initialize_excluded_saves(self):
        f = EconomyScriptFixture(facts={P + "has_current_schema": False})
        f.run(P + "queue_law_refresh")
        f.run(P + "refresh_after_law_change")
        self.assertNotIn("country_event", f.calls)
        self.assertNotIn(P + "treasury", f.scopes["A"])
        self.assertFalse(f.scopes["A"][P + "law_refresh_pending"])

    def test_all_selectable_law_categories_refresh_on_addition_and_removal(self):
        count = 0
        for filename in ("ADISCORD_laws.txt", "_economic.txt", "_manpower.txt"):
            for root in parse_clausewitz(read("common/ideas/" + filename)):
                if root.key != "ideas":
                    continue
                for category in root.value:
                    if not isinstance(category.value, list):
                        continue
                    for law in category.value:
                        if not isinstance(law.value, list) or not any(n.key == "cost" for n in law.value):
                            continue
                        if law.key in ("undisturbed_isolation", "isolation"):
                            continue
                        count += 1
                        for hook in ("on_add", "on_remove"):
                            body = next(n.value for n in law.value if n.key == hook)
                            hidden = next(n.value for n in body if n.key == "hidden_effect")
                            self.assertTrue(any(n.key == P + "queue_law_refresh" and n.value == "yes" for n in hidden), law.key)
        self.assertEqual(count, 116)

    def test_recruitment_shares_stay_bounded_and_emergency_laws_retain_costs(self):
        source = read("common/ideas/_manpower.txt")
        for law,share in (("disarmed_nation", 0.01), ("volunteer_only", 0.015),
                          ("limited_conscription", 0.025), ("extensive_conscription", 0.05),
                          ("service_by_requirement", 0.10), ("all_adults_serve", 0.20),
                          ("scraping_the_barrel", 0.25)):
            entries = parse_clausewitz(block(source, law))
            mods = {n.key: float(n.value) for n in next(n.value for n in entries if n.key == "modifier")}
            self.assertEqual(mods["conscription"], share)
            if share >= 0.10:
                self.assertLess(mods["industrial_capacity_factory"], 0)
                self.assertLess(mods["production_speed_buildings_factor"], 0)
                self.assertGreater(mods["training_time_factor"], 0)
            self.assertEqual(next(n.value for n in entries if n.key == "cost"), "150")


class StartingLawAndPriceTierTests(unittest.TestCase):
    def test_custom_categories_keep_one_default_and_all_choices_have_localisation_and_icons(self):
        categories = parse_clausewitz(read("common/ideas/ADISCORD_laws.txt"))[0].value
        gfx = "\n".join(p.read_text(encoding="utf-8-sig") for p in (ROOT / "interface").glob("*.gfx"))
        names = set(re.findall(r'name\s*=\s*"([^"\n]+)"', gfx))
        locs = [read("localisation/" + lang + "/ADISCORD_laws_l_" + lang + ".yml")
                for lang in ("russian", "english")]
        for category in categories:
            laws = [n for n in category.value if isinstance(n.value, list)
                    and any(c.key == "cost" for c in n.value)]
            self.assertEqual(len(laws), 6, category.key)
            self.assertEqual(sum(any(c.key == "default" and c.value == "yes" for c in law.value)
                                 for law in laws), 1, category.key)
            for law in laws:
                icon = next(n.value for n in law.value if n.key == "picture")
                self.assertIn("GFX_idea_" + icon, names, law.key)
                for loc in locs:
                    for suffix in ("", "_desc"):
                        self.assertRegex(loc, r'(?m)^ ' + law.key + suffix + r':\s*"[^"\n]+"$')

    def test_starting_profiles_select_at_most_one_law_per_category(self):
        categories = parse_clausewitz(read("common/ideas/ADISCORD_laws.txt"))[0].value
        law_category = {law.key: category.key for category in categories
                        for law in category.value if isinstance(law.value, list)
                        and any(n.key == "cost" for n in law.value)}
        profiles = []
        for tag in ("STP", "NOD", "VAL", "IVN", "WRK"):
            path = next((ROOT / "history/countries").glob(tag + " - *.txt"))
            nodes = parse_clausewitz(path.read_text(encoding="utf-8-sig"))
            ids = [item.value for node in nodes if node.key == "add_ideas" and isinstance(node.value, list)
                   for item in node.value if not isinstance(item.value, list)]
            selected = [key for key in ids if key in law_category]
            categories = [law_category[key] for key in selected]
            self.assertGreaterEqual(len(selected), 8, tag)
            self.assertEqual(len(categories), len(set(categories)), tag)
            profiles.append(frozenset(selected))
        self.assertEqual(len(set(profiles)), 5)

    def test_other_countries_keep_their_five_cash_tiers(self):
        tiers = {50, 100, 250, 500, 1000}
        used = set()
        for path in (ROOT / "common/decisions").glob("*.txt"):
            if path.name == "ADISCORD_STP_decisions.txt":
                continue
            text = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r'(subtract_from_variable|add_to_variable)\s*=\s*\{\s*'
                                     r'var\s*=\s*ADISCORD_economy_treasury\s+value\s*=\s*(-?[\d.]+)', text):
                amount = float(match[2])
                if match[1] == "subtract_from_variable" or amount < 0:
                    self.assertIn(abs(amount), tiers, str(path))
                    used.add(abs(amount))
            for match in re.finditer(r'ADISCORD_economy_(?:can_)?spend_(\d+)\s*=\s*yes', text):
                self.assertIn(int(match[1]), tiers, str(path))
        self.assertTrue(used.issubset(tiers))


class StelanderPurchasingPowerTests(unittest.TestCase):
    def fixture(self, countries=None, facts=None):
        f = EconomyScriptFixture(countries=countries, facts=facts, stubs=(
            P + "initialize_country", P + "mark_dirty", "add_political_power"))
        for path in ("common/scripted_effects/ADISCORD_STP_scripted_effects.txt",
                     "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"):
            f.definitions.update({n.key: n.value for n in parse_clausewitz(read(path))})
        return f

    def test_prewar_cash_boundaries_and_single_ledger_charge(self):
        for original, price in ((50, 600), (100, 1200), (200, 2400), (500, 6000)):
            f = self.fixture()
            for balance in (price - 0.01, price):
                f.scopes["A"][P + "treasury"] = balance
                gate = f.definitions["STP_cw_can_spend_" + str(price)]
                self.assertEqual(f.condition(gate), balance >= price)
            f.run("STP_cw_spend_" + str(price))
            self.assertEqual(f.scopes["A"][P + "treasury"], 0)
            self.assertEqual(f.scopes["A"][P + "current_month_action_costs"], price)
            self.assertLess(abs((price / 35) / (original / 3) - 1), 0.04)

    def test_assault_training_refunds_legacy_or_recorded_cash_once(self):
        for paid in (500, 6000):
            f = self.fixture()
            f.stubs.add("STP_political_action_slot_release")
            f.scopes["A"]["STP_cw_assault_training_reserved"] = True
            if paid == 6000:
                f.scopes["A"]["STP_cw_assault_training_deposit"] = paid
            f.run("STP_cw_cancel_assault_training")
            f.run("STP_cw_cancel_assault_training")
            self.assertEqual(f.scopes["A"][P + "treasury"], paid)
            self.assertEqual(f.scopes["A"][P + "current_month_action_income"], paid)
            self.assertNotIn("STP_cw_assault_training_deposit", f.scopes["A"])
            self.assertEqual(f.calls.count("STP_political_action_slot_release"), 1)

    def test_large_focus_grants_survive_capacity_and_ledger_reconciliation(self):
        source = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        for identifier, amount in (("STP_cw_military_committee_fund", 18000),
                                   ("STP_cw_seize_vorkerland_accounts", 3000)):
            f = self.fixture(facts={"STP_uses_campaign_currency_scale": True})
            f.scopes["A"][P + "final_treasury_capacity_factor_bp"] = 100
            reward = next(n.value for n in focus(source, identifier) if n.key == "completion_reward")
            monetary = [n for n in walk(reward) if n.key.startswith("STP_receive_") or
                        (n.key == "add_to_variable" and any(c.key == "var" and c.value in
                         (P + "treasury", P + "current_month_action_income") for c in n.value))]
            f.execute(monetary, "A", None, "A")
            f.run(P + "clamp_all_variables")
            self.assertEqual(f.scopes["A"][P + "treasury"], amount)
            self.assertEqual(f.scopes["A"][P + "current_month_action_income"], amount)
            self.assertGreaterEqual(f.scopes["A"][P + "treasury_cap"], amount)
            f.scopes["A"]["ADISCORD_business_center_count"] = 100
            f.run(P + "recalculate_treasury_cap")
            self.assertEqual(f.scopes["A"][P + "treasury_cap"], 60000)

    def test_postwar_saving_time_stays_within_four_percent(self):
        original = (60, 120, 100, 60, 60, 100, 60, 80, 120, 60, 100, 120, 40)
        for old, new in zip(original, PostwarProgramPriceTests.PRICES.values()):
            self.assertEqual(new, old * 9)
            self.assertLess(abs((new / 26) / (old / 3) - 1), 0.04)

    def test_legacy_and_new_wartime_escrows_refund_the_actual_payment_once(self):
        for name, variable, fraction in (("STP_cw_refund_arsenal_project", "STP_cw_arsenal_deposit", .5),
                                         ("STP_cw_refund_disruption", "STP_cw_disruption_deposit", 1)):
            for paid in (100, 1200):
                f = self.fixture()
                f.scopes["A"][variable] = paid
                f.run(name)
                f.run(name)
                self.assertEqual(f.scopes["A"][P + "treasury"], paid * fraction)
                self.assertEqual(f.scopes["A"][P + "current_month_action_income"], paid * fraction)
                self.assertNotIn(variable, f.scopes["A"])

    def test_northern_deposit_handoff_preserves_old_and_new_money(self):
        for kind, receipts in (("fort", (100, 1200)), ("engineer", (50, 600))):
            variable = "STP_cw_northern_" + kind + "_deposit"
            for paid in receipts:
                f = self.fixture(countries={"STP": {variable: paid}, "STS": {}})
                branches = f.definitions["STP_cw_transfer_preparation_modifiers"]
                branch = next(n for n in branches if n.key == "if" and any(
                    c.key == "limit" and any(x.key == "has_variable" and x.value == variable for x in c.value)
                    for c in n.value))
                f.execute([branch], "STP", None, "STP")
                f.execute([branch], "STP", None, "STP")
                self.assertEqual(f.scopes["STS"][P + "treasury"], paid)
                self.assertEqual(f.scopes["STS"][P + "current_month_action_income"], paid)
                self.assertNotIn(variable, f.scopes["STP"])

    def test_bilateral_compacts_debit_and_credit_the_same_amount(self):
        for recipient, price, settled in (("VAL", 1800, False), ("VAL", 900, True), ("NOD", 1350, False)):
            f = self.fixture(countries={"A": {P + "treasury": price}, recipient: {}},
                             facts={"STP_pw_kefreyt_accounts_settled": settled})
            if settled:
                f.scopes["A"]["STP_pw_kefreyt_accounts_settled"] = True
            gate = f.definitions["STP_pc_can_pay_" + recipient.lower() + "_compact"]
            self.assertTrue(f.condition(gate))
            f.scopes["A"][P + "treasury"] = price - 0.01
            self.assertFalse(f.condition(gate))
            f.scopes["A"][P + "treasury"] = price
            f.run("STP_pc_credit_" + recipient.lower() + "_compact")
            self.assertEqual(f.scopes["A"][P + "treasury"], 0)
            self.assertEqual(f.scopes[recipient][P + "treasury"], price)
            self.assertEqual(f.scopes["A"][P + "current_month_action_costs"], price)
            self.assertEqual(f.scopes[recipient][P + "current_month_action_income"], price)


class BattalionArmyUpkeepTests(unittest.TestCase):
    def calculate(self, battalions, mode=3, war=False, divisions=20):
        f = income_fixture()
        f.facts.update({"has_war": war, "has_army_manpower": False})
        f.scopes["A"].update({
            "tag": "VAL", "num_battalions": battalions, "num_divisions": divisions,
            P + "army_spending_mode": mode,
            P + "cached_army_organization_factor": 1,
            P + "cached_army_organization_flat_expense": 0,
        })
        f.run(P + "calculate_army_expenses")
        return f

    def test_upkeep_tracks_each_battalion_without_manpower_thresholds(self):
        for count in (0, 1, 9, 10, 100, 999, 1000):
            with self.subTest(count=count):
                f = self.calculate(count)
                self.assertAlmostEqual(f.scopes["A"][P + "army_expenses"], count * .1)

    def test_reorganizing_same_battalions_does_not_change_base_upkeep(self):
        costs = [self.calculate(100, divisions=d).scopes["A"][P + "army_expenses"]
                 for d in (5, 10, 20)]
        self.assertEqual(costs, [10, 10, 10])

    def test_war_funding_and_weekly_conversion_apply_once(self):
        for mode, factor in ((1, .25), (2, .6), (3, 1), (4, 1.3), (5, 1.7)):
            for war in (False, True):
                f = self.calculate(100, mode, war)
                expected = 10 * factor * (1.25 if war else 1)
                self.assertAlmostEqual(f.scopes["A"][P + "army_expenses"], expected)
                f.run(P + "sum_expenses")
                f.run(P + "calculate_weekly_budget")
                self.assertAlmostEqual(f.scopes["A"][P + "weekly_expenses"], expected * 3 / 13)

    def test_recount_and_cached_policy_preview_do_not_accumulate(self):
        f = self.calculate(100)
        f.scopes["A"]["num_battalions"] = 200
        f.run(P + "calculate_army_expenses")
        f.run(P + "calculate_army_expenses")
        self.assertAlmostEqual(f.scopes["A"][P + "army_expenses"], 20)
        f.scopes["A"].update({P + "policy_preview_uses_cached_base_temp": 1,
                              "num_battalions": 999, P + "army_spending_mode": 4})
        f.run(P + "calculate_army_expenses")
        self.assertAlmostEqual(f.scopes["A"][P + "army_expenses"], 26)
        self.assertEqual(f.scopes["A"][P + "army_battalion_count"], 200)

    def test_national_premium_reaches_weekly_budget(self):
        f = self.calculate(100)
        f.scopes["A"][P + "final_army_expense_factor_bp"] = 125
        f.run(P + "apply_expense_modifier_factors")
        f.run(P + "sum_expenses")
        f.run(P + "calculate_weekly_budget")
        self.assertAlmostEqual(f.scopes["A"][P + "army_expenses"], 12.5)
        self.assertAlmostEqual(f.scopes["A"][P + "weekly_expenses"], 12.5 * 3 / 13)


class ValMercenaryPayrollTests(unittest.TestCase):
    def fixture(self, authority=35):
        f = EconomyScriptFixture(facts={"has_dynamic_modifier": True},
                                 stubs=("force_update_dynamic_modifier", P + "mark_dirty"))
        f.definitions.update({n.key: n.value for n in parse_clausewitz(
            read("common/scripted_effects/ADISCORD_VAL_effects.txt"))})
        f.scopes["A"]["VAL_contract_authority"] = authority
        return f

    def test_base_premium_preserves_authority_discounts_without_stacking(self):
        for authority, discount in ((10, 0), (35, 0), (60, .03), (80, .05), (95, .07)):
            f = self.fixture(authority)
            for _ in range(3):
                f.run("VAL_refresh_contract_modifier")
                self.assertAlmostEqual(f.scopes["A"]["VAL_contract_army_expense_factor"], .25 - discount)

    def test_late_reforms_remove_only_premium_and_survive_tree_change(self):
        f = self.fixture(95)
        reform = f.definitions["VAL_reform_mercenary_payroll"]
        payload = next(n.value for n in reform if n.key == "hidden_effect")
        f.scopes["A"]["VAL_paid_loyalty"] = True
        for step in range(1, 11):
            f.execute(payload, "A", None, "A")
            f.run("VAL_refresh_contract_modifier")
            expected = .25 - min(step, 5) * .05 - .07 - .03
            self.assertAlmostEqual(f.scopes["A"]["VAL_contract_army_expense_factor"], expected)
            if step == 3:
                f.scopes["A"]["VAL_stelander_defeated"] = True
        self.assertIn(P + "mark_dirty", f.calls)

    def test_both_defeat_routes_reach_all_five_reforms(self):
        text = read("common/national_focus/ADISCORD_national_focus_VAL_defeated.txt")
        for branch in ("VAL_defeat_Technical_Institute", "VAL_defeat_Return_To_The_Passes"):
            visited = set()

            def visit(identifier):
                if identifier in visited:
                    return
                visited.add(identifier)
                for node in focus(text, identifier):
                    if node.key != "prerequisite":
                        continue
                    choices = [n.value for n in node.value if n.key == "focus"]
                    visit(branch if branch in choices else choices[0])

            visit("VAL_defeat_Recovered_State")
            reforms = [identifier for identifier in visited if any(
                n.key == "VAL_reform_mercenary_payroll" and n.value == "yes"
                for n in walk(focus(text, identifier)))]
            self.assertEqual(len(reforms), 5, (branch, reforms))

    def test_load_migrates_recorded_reforms_once_before_refresh(self):
        f = self.fixture()
        original_condition = f.condition
        completed = set()

        def condition(entries, scope="A", previous=None, root="A"):
            return all(n.value in completed if n.key == "has_completed_focus"
                       else original_condition([n], scope, previous, root) for n in entries)

        f.condition = condition
        completed.update(n.value for n in walk(f.definitions["VAL_migrate_mercenary_payroll"])
                         if n.key == "has_completed_focus")
        self.assertEqual(len(completed), 10)
        f.run("VAL_migrate_mercenary_payroll")
        self.assertAlmostEqual(f.scopes["A"]["VAL_contract_payroll_relief"], -.25)
        completed.clear()
        f.run("VAL_migrate_mercenary_payroll")
        self.assertAlmostEqual(f.scopes["A"]["VAL_contract_payroll_relief"], -.25)
        f.scopes["A"].pop("VAL_contract_payroll_relief")
        completed.update(("VAL_State_Contract", "VAL_defeat_Staff_College"))
        f.run("VAL_migrate_mercenary_payroll")
        self.assertAlmostEqual(f.scopes["A"]["VAL_contract_payroll_relief"], -.1)
        startup = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        self.assertLess(startup.index("VAL_migrate_mercenary_payroll = yes"),
                        startup.index("VAL_initialize_contract_authority = yes"))


class NodrulDivisionEconomyTests(unittest.TestCase):
    def fixture(self, divisions=38, civilian=9, military=12, war=False,
                stress=0, crisis=0, tag="NOD", mode=3):
        f = income_fixture(civilian=civilian, military=military)
        f.facts.update({"has_army_manpower": True, "has_war": war,
                        "is_ai": True, "has_capitulated": False})
        f.scopes["A"].update({
            "tag": tag, "num_divisions": divisions,
            P + "army_spending_mode": mode,
            P + "cached_army_organization_factor": 1,
            P + "cached_army_organization_flat_expense": 0,
            P + "fiscal_stress": stress, P + "debt_crisis_level": crisis,
            P + "initialized": 1, P + "schema_version": 15,
        })
        return f

    def calculate(self, **kwargs):
        f = self.fixture(**kwargs)
        f.run(P + "calculate_army_expenses")
        return f

    def test_each_additional_division_costs_money_at_equal_fielded_manpower(self):
        costs = [self.calculate(divisions=d).scopes["A"][P + "army_expenses"]
                 for d in (20, 21, 33, 34, 80, 81)]
        self.assertAlmostEqual(costs[1] - costs[0], 0.5)
        self.assertAlmostEqual(costs[3] - costs[2], 2.5)
        self.assertAlmostEqual(costs[5] - costs[4], 2.5)

    def test_starting_industry_allows_33_in_peace_and_39_in_war(self):
        for war, cap in ((False, 33), (True, 39)):
            with self.subTest(war=war):
                v = self.calculate(war=war).scopes["A"]
                self.assertEqual(v.get(P + "nod_division_capacity"), cap)
                self.assertEqual(v.get(P + "nod_division_count"), 38)
                self.assertEqual(v.get(P + "nod_excess_divisions"), max(38-cap, 0))

    def test_stress_and_debt_reduce_capacity_once_not_cumulatively(self):
        for stress, crisis, cap in ((44.99, 1, 33), (45, 0, 27), (0, 2, 27),
                                    (74.99, 2, 27), (75, 0, 21), (0, 3, 21),
                                    (100, 4, 21)):
            with self.subTest(stress=stress, crisis=crisis):
                v = self.calculate(stress=stress, crisis=crisis).scopes["A"]
                self.assertEqual(v.get(P + "nod_division_capacity"), cap)

    def test_capacity_has_a_floor_and_war_does_not_remove_the_ceiling(self):
        for factories, war, crisis, cap in ((0, False, 4, 12), (0, True, 4, 12),
                                            (100, False, 0, 48), (100, True, 0, 54),
                                            (100, True, 4, 42)):
            with self.subTest(factories=factories, war=war, crisis=crisis):
                self.assertEqual(self.calculate(civilian=factories, military=0,
                                 war=war, crisis=crisis).scopes["A"].get(P + "nod_division_capacity"), cap)

    def test_low_funding_does_not_raise_capacity_and_previews_do_not_erase_pressure(self):
        for level, factor in ((1, .25), (2, .6), (3, 1), (4, 1.3), (5, 1.7)):
            with self.subTest(level=level):
                live = self.calculate(divisions=50, mode=level)
                baseline = self.calculate(divisions=50, mode=3)
                v = live.scopes["A"]
                self.assertEqual(v.get(P + "nod_division_capacity"), 33)
                self.assertAlmostEqual(v[P + "army_expenses"],
                                       baseline.scopes["A"][P + "army_expenses"] * factor)
                before = dict(v)
                v[P + "policy_preview_uses_cached_base_temp"] = 1
                v["num_divisions"] = 200
                live.run(P + "calculate_army_expenses")
                self.assertAlmostEqual(v[P + "army_expenses"], before[P + "army_expenses"])
                for key in ("nod_division_capacity", "nod_division_count", "nod_excess_divisions"):
                    self.assertEqual(v.get(P + key), before.get(P + key))

    def test_recalculation_is_idempotent_and_consumes_current_division_count(self):
        f = self.calculate(divisions=50)
        first = dict(f.scopes["A"])
        for _ in range(5):
            f.run(P + "calculate_army_expenses")
        self.assertEqual(f.scopes["A"], first)
        f.scopes["A"]["num_divisions"] = 20
        f.run(P + "calculate_army_expenses")
        self.assertEqual(f.scopes["A"].get(P + "nod_division_count"), 20)
        self.assertEqual(f.scopes["A"].get(P + "nod_excess_divisions"), 0)
        self.assertLess(f.scopes["A"][P + "army_expenses"], first[P + "army_expenses"])
        self.assertEqual(f.scopes["A"][P + "treasury"], 100)

    def test_new_cost_reaches_the_weekly_budget_without_double_charging(self):
        f = self.calculate(divisions=34)
        f.run(P + "sum_expenses")
        f.run(P + "calculate_weekly_budget")
        v = f.scopes["A"]
        self.assertAlmostEqual(v[P + "weekly_expenses"], v[P + "army_expenses"] * 3 / 13)
        self.assertEqual(v[P + "treasury"], 100)

    def test_other_countries_keep_their_existing_army_cost_curve(self):
        for tag in ("VAL", "STP", "STS", "WRK", "YPR"):
            with self.subTest(tag=tag):
                small = self.calculate(tag=tag, divisions=20).scopes["A"]
                large = self.calculate(tag=tag, divisions=100).scopes["A"]
                self.assertEqual(small[P + "army_expenses"], large[P + "army_expenses"])
                self.assertNotIn(P + "nod_division_capacity", large)

    def test_ai_stops_expansion_at_capacity_but_can_replace_losses(self):
        text = read("common/ai_strategy/ADISCORD_economy_ai.txt")
        strategies = {n.key: n.value for n in parse_clausewitz(text)}
        self.assertIn("NOD_economy_army_capacity_reached", strategies)
        stop = strategies["NOD_economy_army_capacity_reached"]
        enables = next(n.value for n in stop if n.key == "enable")
        self.assertEqual(next(n.value for n in stop if n.key == "abort_when_not_enabled"), "yes")
        weights = [{c.key: c.value for c in n.value} for n in stop if n.key == "ai_strategy"]
        self.assertIn({"type": "ai_wanted_divisions_factor", "value": "-1000"}, weights)
        for d, expected in ((32, False), (33, True), (80, True)):
            f = self.calculate(divisions=d)
            self.assertEqual(f.condition(enables), expected)
        for overrides in ({"tag": "VAL"}, {"is_ai": False}, {"has_capitulated": True}):
            f = self.calculate(divisions=80)
            if "tag" in overrides:
                f.scopes["A"].update(overrides)
            else:
                f.facts.update(overrides)
            self.assertFalse(f.condition(enables))
        f = self.fixture(divisions=80)
        self.assertFalse(f.condition(enables), "No zero-cap lock before first economy refresh")

    def test_ai_brakes_before_the_cap_without_stacking_the_stop_policy(self):
        strategies = {n.key: n.value for n in parse_clausewitz(read("common/ai_strategy/ADISCORD_economy_ai.txt"))}
        self.assertIn("NOD_economy_army_capacity_approaching", strategies)
        gate = next(n.value for n in strategies["NOD_economy_army_capacity_approaching"] if n.key == "enable")
        for divisions, expected in ((28, False), (29, True), (32, True), (33, False)):
            self.assertEqual(self.calculate(divisions=divisions).condition(gate), expected)

    def test_capacity_details_are_connected_to_the_existing_army_tooltip(self):
        script = read("common/scripted_localisation/ADISCORD_economy_scripted_loc.txt")
        self.assertIn("name = GetADISCORDEconomyNodDivisionCapacityLoc", script)
        for language in ("english", "russian"):
            path = ROOT / f"localisation/{language}/ADISCORD_economy_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            row = re.search(r"^ ADISCORD_economy_army_controls_tt:.*$", text, re.M).group()
            self.assertIn("[GetADISCORDEconomyNodDivisionCapacityLoc]", row)
            for key in ("nod_division_capacity", "nod_division_count", "nod_excess_divisions"):
                self.assertIn("[?" + P + key + "|0]", text)

    def test_existing_starting_forces_are_not_destroyed_or_rebuilt_by_the_cap(self):
        effect = block(read("common/scripted_effects/ADISCORD_economy_effects.txt"),
                       P + "calculate_army_expenses")
        for forbidden in ("destroy_unit", "delete_units", "load_oob", "every_unit", "every_country", "every_state"):
            self.assertNotIn(forbidden, effect)


if __name__ == "__main__":
    unittest.main()
