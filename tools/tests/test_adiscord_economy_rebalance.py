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
        v.update({P + "treasury": 137, P + "debt": 250})
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


if __name__ == "__main__":
    unittest.main()
