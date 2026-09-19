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


if __name__ == "__main__":
    unittest.main()
