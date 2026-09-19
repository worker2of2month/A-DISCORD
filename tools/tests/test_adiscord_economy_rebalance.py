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


class NorthernCampaignRouteTests(unittest.TestCase):
    def test_frontier_does_not_require_participation_in_the_stelander_crisis(self):
        nodes = focus(read("common/national_focus/ADISCORD_national_focus_VAL.txt"), "VAL_frontier_conference")
        alternatives = [{c.value for c in n.value if c.key == "focus"}
                        for n in nodes if n.key == "prerequisite"]
        self.assertIn({"VAL_The_Steel_Contract", "VAL_Market_Roads_North"}, alternatives)
        self.assertTrue(any(n.key == "VAL_frontier_postwar" for n in walk(nodes)))

    def test_demand_and_offensive_share_a_force_quality_gate_not_24_divisions(self):
        text = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for identifier in ("VAL_frontier_demand_CIN", "VAL_frontier_demand_OSF",
                           "VAL_frontier_demand_APH", "VAL_frontier_demand_ERT",
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
    twelve ships. Monthly interest is six. No focus/flat-income bonuses apply.
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
        self.assertEqual(business - base, 100)
        self.assertEqual(science - base, 40)
        large = building_budget_fixture(business=30, science=6).scopes['A'][P + 'treasury_cap']
        self.assertGreater(large, 3000)
        self.assertLessEqual(large, 5000)

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


if __name__ == "__main__":
    unittest.main()
