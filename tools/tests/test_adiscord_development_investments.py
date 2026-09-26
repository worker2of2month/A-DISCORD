from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "common/decisions/ADISCORD_economy_projects.txt"
CATEGORIES = ROOT / "common/decisions/categories/ADISCORD_economy_projects.txt"
RU = ROOT / "localisation/russian/ADISCORD_economy_l_russian.yml"
EN = ROOT / "localisation/english/ADISCORD_economy_l_english.yml"


def named_block(text: str, name: str) -> str:
    marker = f"{name} = {{"
    start = text.index(marker)
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"Unclosed block: {name}")


class DevelopmentInvestmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decisions = DECISIONS.read_text(encoding="utf-8")
        cls.categories = CATEGORIES.read_text(encoding="utf-8")

    def test_category_is_available_to_stelander_successors_and_kefreyt(self) -> None:
        category = named_block(self.categories, "ADISCORD_development_investments")
        for tag in ("STP", "STS", "VAL"):
            self.assertIn(f"tag = {tag}", category)
        self.assertIn("has_variable = ADISCORD_economy_treasury", category)

    def test_four_investments_use_existing_development_growth_api(self) -> None:
        specs = {
            "ADISCORD_invest_army_development": (
                "ADISCORD_army_development_at_least_5",
                "ADISCORD_army_development_investment_count",
                "ADISCORD_increase_army_development_monthly_growth",
            ),
            "ADISCORD_invest_state_development": (
                "ADISCORD_state_development_at_least_5",
                "ADISCORD_state_development_investment_count",
                "ADISCORD_increase_state_development_monthly_growth",
            ),
            "ADISCORD_invest_economic_development": (
                "ADISCORD_economic_development_at_least_5",
                "ADISCORD_economic_development_investment_count",
                "ADISCORD_increase_economic_development_monthly_growth",
            ),
            "ADISCORD_invest_society_development": (
                "ADISCORD_society_development_at_least_5",
                "ADISCORD_society_development_investment_count",
                "ADISCORD_increase_society_development_monthly_growth",
            ),
        }
        for decision_id, (cap, counter, effect) in specs.items():
            with self.subTest(decision=decision_id):
                decision = named_block(self.decisions, decision_id)
                self.assertIn(f"NOT = {{ {cap} = yes }}", decision)
                self.assertIn(f"var = {counter} value = 4 compare = less_than", decision)
                self.assertEqual(decision.count("ADISCORD_economy_spend_250 = yes"), 1)
                self.assertEqual(decision.count(f"{effect} = yes"), 1)
                self.assertEqual(decision.count(f"var = {counter} value = 1"), 1)
                self.assertIn("custom_cost_trigger = { ADISCORD_economy_can_spend_250 = yes }", decision)
                self.assertIn("custom_cost_text = ADISCORD_development_investment_cost_250", decision)
                self.assertIn("fire_only_once = no", decision)
                self.assertIn("days_re_enable = 180", decision)

    def test_cost_localisation_is_complete_and_russian_keeps_bom(self) -> None:
        self.assertTrue(RU.read_bytes().startswith(b"\xef\xbb\xbf"))
        for path in (RU, EN):
            text = path.read_text(encoding="utf-8-sig")
            for suffix in ("", "_blocked", "_tooltip"):
                key = f"ADISCORD_development_investment_cost_250{suffix}"
                match = re.search(rf"^ {re.escape(key)}:0? \"([^\"]+)\"$", text, re.M)
                self.assertIsNotNone(match, f"{path}: missing {key}")
                self.assertIn("250", match.group(1))
                self.assertIn("£ADISCORD_economy_treasury_texticon", match.group(1))


if __name__ == "__main__":
    unittest.main()
