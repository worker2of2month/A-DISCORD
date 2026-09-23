from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    opening = source.find("{", match.start())
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    raise AssertionError(f"unterminated block: {name}")


class KefreytRefugeeBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decisions = read("common/decisions/ADISCORD_VAL_logistics_market_decisions.txt")
        cls.effects = read("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt")
        cls.ideas = read("common/ideas/ADISCORD_VAL_logistics_market_ideas.txt")

    def test_admissions_are_cheap_bounded_and_repeatable(self) -> None:
        for suffix in ("vorkerland", "stelander", "nodrul", "north", "perimeter"):
            body = named_block(self.decisions, f"VAL_accept_{suffix}_refugees")
            self.assertIn("ADISCORD_economy_can_spend_100 = yes", body)
            self.assertIn("custom_cost_text = VAL_logistics_cost_100", body)
            self.assertIn("days_re_enable = 90", body)
            self.assertIn("ADISCORD_economy_spend_100 = yes", body)
            self.assertIn("var = VAL_black_market_pressure_change value = 3", body)
            self.assertIn(f"var = VAL_refugee_{suffix}_admitted value = 3 compare = less_than", body)

    def test_training_keeps_the_stronger_main_balance(self) -> None:
        decision = named_block(self.decisions, "VAL_train_refugee_volunteers")
        for token in (
            "var = VAL_displaced_population value = 1 compare = greater_than_or_equals",
            "has_political_power < 50",
            "infantry_equipment < 2500",
            "add_political_power = -50",
            "amount = -2500",
            "var = VAL_refugee_training_escrow value = 1",
            "var = VAL_displaced_population value = -1",
        ):
            self.assertIn(token, decision)
        finish = named_block(self.effects, "VAL_finish_refugee_training")
        self.assertIn("add_manpower = 10000", finish)

    def test_housing_labour_and_strain_are_useful(self) -> None:
        housing = named_block(self.decisions, "VAL_expand_refugee_housing")
        self.assertIn("ADISCORD_economy_spend_250 = yes", housing)
        finish = named_block(self.effects, "VAL_finish_housing")
        self.assertIn("var = VAL_refugee_housing value = 30", finish)

        labour = named_block(self.ideas, "VAL_refugee_contract_labor")
        self.assertIn("production_speed_buildings_factor = 0.12", labour)
        self.assertIn("ADISCORD_economy_civilian_factory_income_factor = 0.08", labour)
        self.assertNotIn("stability_factor", labour)

        strain = named_block(self.ideas, "VAL_refugee_strain")
        self.assertIn("ADISCORD_economy_social_expense_factor = 0.07", strain)
        self.assertIn("consumer_goods_factor = 0.01", strain)
        self.assertIn("stability_factor = -0.02", strain)

    def test_population_text_is_compact_and_matches_balance(self) -> None:
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_logistics_market_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), language)
            loc = path.read_text(encoding="utf-8-sig")
            for key in (
                "VAL_population_markets_desc",
                "VAL_accept_vorkerland_refugees_desc",
                "VAL_accept_stelander_refugees_desc",
                "VAL_accept_nodrul_refugees_desc",
                "VAL_accept_north_refugees_desc",
                "VAL_accept_perimeter_refugees_desc",
            ):
                line = next(row for row in loc.splitlines() if row.startswith(f" {key}:"))
                self.assertNotIn("—", line)
                self.assertNotIn(";", line)
                self.assertLess(len(line), 430)
            self.assertIn("§Y90", loc)
            self.assertIn("§G+12%§!", loc)
            self.assertIn("§G+8%§!", loc)


if __name__ == "__main__":
    unittest.main()
