"""Arithmetic fixtures for weekly purchasing power; not an engine simulation."""
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_economy_weekly_contracts import (
    EconomyScriptFixture, EFFECTS, MODIFIER_EFFECTS, TRIGGERS, parse_clausewitz,
)

ROOT = Path(__file__).resolve().parents[2]
P = "ADISCORD_economy_"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def walk(entries):
    for node in entries:
        yield node
        if isinstance(node.value, list):
            yield from walk(node.value)


def focus_entries(text, focus_id):
    for node in walk(parse_clausewitz(text)):
        if node.key == "focus" and any(child.key == "id" and child.value == focus_id for child in node.value):
            return node.value
    raise AssertionError(f"missing focus: {focus_id}")


def deltas(entries):
    values = {}
    for node in walk(entries):
        if node.key == "add_to_variable":
            fields = {child.key: child.value for child in node.value}
            if fields.get("var", "").startswith("STP_pw_"):
                values[fields["var"]] = values.get(fields["var"], 0) + float(fields["value"])
    return values


def budget_fixture(civ=25, mil=15, centers=4, resources=15, level=4, model="mixed"):
    source = EFFECTS + MODIFIER_EFFECTS + TRIGGERS
    facts = {"has_war": False, "has_army_manpower": True, "has_idea": False}
    # True for every cumulative manpower threshold represents a 250,000-person
    # field army. The fixture therefore does not obtain its surplus by disarming.
    for key in set(re.findall(r"\bADISCORD_\w+development_(?:at_least|exact)_\d+", source)):
        boundary = int(key.rsplit("_", 1)[1])
        facts[key] = level >= boundary if "_at_least_" in key else level == boundary
    for key in set(re.findall(r"\bADISCORD_economy_model_is_\w+", source)):
        facts[key] = key == P + "model_is_" + model
    for key in set(re.findall(r"\bADISCORD_economy_cached_has_\w+", source)):
        facts[key] = False
    fixture = EconomyScriptFixture(facts=facts)
    fixture.definitions.update({node.key: node.value for node in parse_clausewitz(MODIFIER_EFFECTS)})
    fixture.run(P + "reset_final_factor_variables")
    values = fixture.scopes["A"]
    for key, value in {
        "cached_civilian_factories": civ, "cached_available_civilian_factories": 0,
        "cached_military_factories": mil, "cached_available_military_factories": 0,
        "cached_naval_factories": 3, "resource_endowment": resources,
        "cached_resource_trade_law_factor": 1, "cached_army_organization_factor": 1,
        "investment_confidence": 60, "state_financial_control": 70,
        "tax_burden_mode": 3, "army_spending_mode": 3,
        "social_spending_mode": 3, "research_spending_mode": 3,
        "public_investment_stock": 2, "debt": 300, "interest_rate": 10,
    }.items():
        values[P + key] = value
    values.update({"ADISCORD_business_center_count": centers, "ADISCORD_science_center_count": 2,
                   "ADISCORD_industrial_cluster_count": 3, "ADISCORD_social_system_development_level": level,
                   "ADISCORD_state_development_level": level, "num_deployed_planes": 100, "num_ships": 8})
    return fixture


def calculate(fixture):
    for name in ("calculate_income", "calculate_debt_service_amount", "calculate_expenses",
                 "calculate_monthly_balance", "calculate_weekly_budget"):
        fixture.run(P + name)
    return fixture.scopes["A"]


class MaterialEconomyBalanceTests(unittest.TestCase):
    def test_developed_economy_can_clear_one_hundred_with_normal_budgets(self):
        fixture = budget_fixture(civ=35, mil=15, centers=6, resources=20)
        values = calculate(fixture)
        self.assertGreaterEqual(values[P + "weekly_balance"], 100)
        self.assertGreater(values[P + "weekly_expenses"], 20)
        self.assertEqual(values[P + "final_weekly_income_bonus"], 0)

    def test_shabrat_recovery_has_a_sustainable_hundred_path(self):
        fixture = budget_fixture()
        focus_text = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        bonus = {}
        for suffix in ("count_the_cost", "reopen_tax_offices", "repair_workshops", "stabilize_currency", "recovery_budget"):
            for key, value in deltas(focus_entries(focus_text, "STP_pc_economy_" + suffix)).items():
                bonus[key] = bonus.get(key, 0) + value
        values = fixture.scopes["A"]
        for key in ("overall_income", "admin_expense"):
            values[P + "final_" + key + "_factor_bp"] += bonus.get("STP_pw_" + P + key + "_factor", 0) * 100
        calculate(fixture)
        self.assertGreaterEqual(values[P + "weekly_balance"], 100)
        self.assertGreater(values[P + "weekly_expenses"], 20)
        self.assertEqual(values[P + "final_weekly_income_bonus"], 0)

    def test_tax_preview_and_repeated_refresh_do_not_duplicate_scaled_income(self):
        fixture = budget_fixture()
        before = calculate(fixture)[P + "monthly_income"]
        for mode in (2, 4, 3):
            fixture.scopes["A"][P + "tax_burden_mode"] = mode
            fixture.run(P + "recalculate_tax_dependent_income")
            cached = fixture.scopes["A"][P + "monthly_income"]
            fixture.run(P + "calculate_income")
            self.assertAlmostEqual(cached, fixture.scopes["A"][P + "monthly_income"])
        self.assertAlmostEqual(before, fixture.scopes["A"][P + "monthly_income"])
        calculate(fixture)
        first = fixture.scopes["A"][P + "weekly_balance"]
        calculate(fixture)
        self.assertAlmostEqual(first, fixture.scopes["A"][P + "weekly_balance"])

    def test_austerity_saves_real_money_and_interest_is_not_rescaled(self):
        fixture = budget_fixture()
        normal = calculate(fixture)[P + "weekly_balance"]
        self.assertAlmostEqual(fixture.scopes["A"][P + "debt_service"], 2.5)
        for key in ("army", "research", "social"):
            fixture.scopes["A"][P + key + "_spending_mode"] = 2
        reduced = calculate(fixture)[P + "weekly_balance"]
        self.assertGreater(reduced - normal, 8)
        self.assertAlmostEqual(fixture.scopes["A"][P + "debt_service"], 2.5)
        self.assertAlmostEqual(fixture.scopes["A"][P + "monthly_balance"] * 3 / 13, reduced)

    def test_small_economy_is_not_given_a_flat_hundred(self):
        values = calculate(budget_fixture(civ=3, mil=2, centers=0, resources=1, level=1, model="fragmented"))
        self.assertLess(values[P + "weekly_balance"], 20)

    def test_each_shabrat_reform_has_an_exact_native_delta_preview(self):
        focuses = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        ideas = parse_clausewitz(read("common/ideas/ADISCORD_STP_civil_war_ideas.txt"))
        for suffix in ("count_the_cost", "reopen_tax_offices", "repair_workshops", "stabilize_currency", "recovery_budget"):
            focus_id = "STP_pc_economy_" + suffix
            entries = focus_entries(focuses, focus_id)
            preview = focus_id + "_delta"
            self.assertTrue(any(node.key == "effect_tooltip" and any(n.key == "add_ideas" and n.value == preview for n in walk(node.value)) for node in walk(entries)))
            idea = next(node for node in walk(ideas) if node.key == preview)
            modifier = next(node.value for node in idea.value if node.key == "modifier")
            actual = {node.key: float(node.value) for node in modifier}
            expected = {key.removeprefix("STP_pw_"): value for key, value in deltas(entries).items()}
            self.assertEqual(actual, expected)

    def test_val_recovery_returns_four_weekly_per_stage_and_does_not_compound(self):
        fixture = EconomyScriptFixture(facts={"has_country_flag": True, "has_dynamic_modifier": False},
            stubs=("effect_tooltip", "custom_effect_tooltip", "remove_ideas", "add_dynamic_modifier", "remove_dynamic_modifier", "force_update_dynamic_modifier", P + "mark_dirty"))
        fixture.definitions.update({node.key: node.value for node in parse_clausewitz(read("common/scripted_effects/ADISCORD_VAL_effects.txt"))})
        for stage in range(7):
            fixture.scopes["A"]["VAL_economic_recovery_steps"] = stage
            fixture.run("VAL_refresh_industrial_economy")
            self.assertEqual(fixture.scopes["A"].get("VAL_industrial_weekly_income", 0), stage * 4)
            fixture.run("VAL_refresh_industrial_economy")
            self.assertEqual(fixture.scopes["A"]["VAL_industrial_weekly_income"], stage * 4)
        dynamic_paths = list((ROOT / "common/dynamic_modifiers").glob("*VAL*"))
        dynamic = "\n".join(path.read_text(encoding="utf-8-sig") for path in dynamic_paths)
        definitions = {node.key: node.value for node in parse_clausewitz(dynamic)}
        for name in ("VAL_contract_industry", "VAL_economic_collapse", "VAL_economic_miracle"):
            self.assertIn((P + "weekly_income", "VAL_industrial_weekly_income"), [(n.key,n.value) for n in definitions[name]])

    def test_val_ultimatum_and_war_share_readiness_instead_of_24_divisions(self):
        decisions = parse_clausewitz(read("common/decisions/ADISCORD_VAL_decisions.txt"))
        for target in ("CIN", "OSF", "APH", "ERT"):
            decision = next(node for node in walk(decisions) if node.key == "VAL_frontier_demand_" + target)
            ai = next(node for node in decision.value if node.key == "ai_will_do")
            self.assertTrue(any(n.key == "VAL_ai_frontier_ready" for n in walk(ai.value)))
            self.assertFalse(any(n.key == P + "ai_is_crisis" for n in walk(ai.value)))
        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        options = [node for node in walk(events) if node.key == "option" and any(n.key == "name" and n.value == "val_rework.111.war" for n in node.value)]
        self.assertEqual(len(options), 1)
        ai = next(node for node in options[0].value if node.key == "ai_chance")
        self.assertTrue(any(n.key == "VAL_ai_frontier_ready" for n in walk(ai.value)))


if __name__ == "__main__":
    unittest.main()
