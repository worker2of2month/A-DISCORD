from __future__ import annotations

import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return read_focus_source(ROOT / relative, encoding="utf-8-sig")


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


def focus_block(source: str, focus_id: str) -> str:
    for match in re.finditer(r"(?m)^\s*focus\s*=\s*\{", source):
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
                    block = source[match.start():index + 1]
                    if re.search(rf"(?m)^\s*id\s*=\s*{re.escape(focus_id)}\s*$", block):
                        return block
                    break
    raise AssertionError(f"missing focus: {focus_id}")


class KefreytRefugeeBalanceTests(unittest.TestCase):
    def test_val_manpower_focus_filter_is_registered_and_applied(self) -> None:
        filter_id = "FOCUS_FILTER_VAL_MANPOWER"
        gfx = read("interface/ADISCORD_national_focus.gfx")
        self.assertIn(f'GFX_{filter_id}', gfx)
        self.assertIn('gfx/interface/focusview/filter/manpower_icon.dds', gfx)

        for language in ("english", "russian"):
            loc = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            self.assertIn(f"{filter_id}:0", loc)

        main = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        defeated = read("common/national_focus/ADISCORD_national_focus_VAL_defeated.txt")
        for focus_id in (
            "VAL_The_Contract_State",
            "VAL_Gromovs_Assault_Tables",
            "VAL_Morns_Supply_Trains",
            "VAL_Field_Surgeons",
            "VAL_Dead_Villages_Still_Count",
            "VAL_Reserve_Battalions",
            "VAL_Company_Service_Code",
            "VAL_Operational_Reserves",
        ):
            self.assertIn(filter_id, focus_block(main, focus_id))
        self.assertIn(filter_id, focus_block(defeated, "VAL_defeat_Veterans_Register"))

    def setUp(self) -> None:
        self.decisions = read("common/decisions/ADISCORD_VAL_logistics_market_decisions.txt")
        self.effects = read("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt")
        self.ideas = read("common/ideas/ADISCORD_VAL_logistics_market_ideas.txt")

    def test_admissions_are_cheaper_repeatable_and_less_punishing(self) -> None:
        for suffix in ("vorkerland", "stelander", "nodrul", "north", "perimeter"):
            body = named_block(self.decisions, f"VAL_accept_{suffix}_refugees")
            self.assertIn("ADISCORD_economy_can_spend_100 = yes", body)
            self.assertIn("custom_cost_text = VAL_logistics_cost_100", body)
            self.assertIn("days_re_enable = 90", body)
            self.assertIn("ADISCORD_economy_spend_100 = yes", body)
            self.assertIn("var = VAL_black_market_pressure_change value = 3", body)
            self.assertNotIn("ADISCORD_economy_spend_250", body)
            self.assertNotIn("days_re_enable = 365", body)

    def test_refugee_training_turns_ten_thousand_people_into_manpower(self) -> None:
        decision = named_block(self.decisions, "VAL_train_refugee_volunteers")
        self.assertIn("value = 1 compare = greater_than_or_equals", decision)
        self.assertIn("custom_cost_text = VAL_refugee_training_cost", decision)
        self.assertIn("var = VAL_refugee_training_escrow value = 1", decision)
        self.assertIn("var = VAL_displaced_population value = -1", decision)

        finish = named_block(self.effects, "VAL_finish_refugee_training")
        self.assertIn("add_manpower = 10000", finish)
        self.assertNotIn("add_manpower = 5000", finish)

    def test_population_market_has_three_additional_people_levers(self) -> None:
        bounties = named_block(self.decisions, "VAL_offer_settlement_bounties")
        self.assertIn("ADISCORD_economy_can_spend_250 = yes", bounties)
        self.assertIn("ADISCORD_economy_spend_250 = yes", bounties)
        self.assertIn("var = VAL_displaced_population value = 3", bounties)
        self.assertIn("days_re_enable = 90", bounties)

        naturalize = named_block(self.decisions, "VAL_naturalize_refugee_households")
        self.assertIn("var = VAL_displaced_population value = -2", naturalize)
        self.assertIn("var = VAL_local_volunteer_pool value = 1", naturalize)
        self.assertIn("cost = 50", naturalize)
        self.assertIn("days_re_enable = 45", naturalize)

        emergency = named_block(self.decisions, "VAL_emergency_service_contracts")
        for token in (
            "ADISCORD_economy_can_spend_500 = yes",
            "ADISCORD_economy_spend_500 = yes",
            "command_power < 25",
            "infantry_equipment < 10000",
            "var = VAL_local_volunteer_pool value = -1",
            "add_manpower = 10000",
            "add_stability = -0.01",
            "days_re_enable = 90",
        ):
            self.assertIn(token, emergency)

    def test_housing_and_labour_are_worth_using(self) -> None:
        housing = named_block(self.decisions, "VAL_expand_refugee_housing")
        self.assertIn("ADISCORD_economy_can_spend_250 = yes", housing)
        self.assertIn("ADISCORD_economy_spend_250 = yes", housing)
        self.assertIn("var = VAL_housing_deposit value = 250", housing)

        labour = named_block(self.ideas, "VAL_refugee_contract_labor")
        for token in (
            "production_speed_buildings_factor = 0.12",
            "ADISCORD_economy_civilian_factory_income_factor = 0.08",
            "stability_factor = -0.01",
        ):
            self.assertIn(token, labour)

        strain = named_block(self.ideas, "VAL_refugee_strain")
        for token in (
            "ADISCORD_economy_social_expense_factor = 0.07",
            "consumer_goods_factor = 0.01",
            "stability_factor = -0.02",
        ):
            self.assertIn(token, strain)

    def test_population_ui_is_short_and_matches_balance(self) -> None:
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_logistics_market_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
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
            self.assertIn("VAL_refugee_training_cost:", loc)
            self.assertIn("VAL_refugee_training_cost_tooltip:", loc)


if __name__ == "__main__":
    unittest.main()
