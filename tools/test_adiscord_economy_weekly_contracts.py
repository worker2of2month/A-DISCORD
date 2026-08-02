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
    def test_weekly_pulse_is_country_scoped_and_applies_once(self):
        weekly = block(ON_ACTIONS, "on_weekly")
        self.assertIn("ADISCORD_economy_should_weekly_update", weekly)
        self.assertEqual(weekly.count("ADISCORD_economy_weekly_update = yes"), 1)
        for forbidden in ("every_country", "every_owned_state", "all_owned_state"):
            self.assertNotIn(forbidden, weekly)

    def test_weekly_eligibility_reuses_player_and_primary_tiers(self):
        weekly_trigger = block(TRIGGERS, "ADISCORD_economy_should_weekly_update")
        self.assertIn("ADISCORD_economy_is_player_tier_country = yes", weekly_trigger)
        self.assertIn("ADISCORD_economy_is_primary_tier_country = yes", weekly_trigger)
        self.assertNotIn("ADISCORD_economy_is_secondary_tier_country", weekly_trigger)

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
        for forbidden in (
            "ADISCORD_economy_full_refresh",
            "ADISCORD_economy_recount_economic_buildings",
            "every_country",
            "every_owned_state",
            "all_owned_state",
        ):
            self.assertNotIn(forbidden, weekly)

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

    def test_schema_six_preserves_existing_treasury(self):
        migration = block(EFFECTS, "ADISCORD_economy_migrate_schema")
        self.assertIn("value = 6", migration)
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
        self.assertIn("ADISCORD_economy_last_period_unexplained_delta", ECONOMY_LOC)
        self.assertNotIn(
            "Фактическое изменение казны происходит раз в месяц", ECONOMY_LOC
        )

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


if __name__ == "__main__":
    unittest.main()
