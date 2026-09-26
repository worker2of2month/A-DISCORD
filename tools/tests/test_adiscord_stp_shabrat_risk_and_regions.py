from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from tools.lib.focus_sources import read_focus_source
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
FOCUS = ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
SCRIPTED_LOC = ROOT / "common/scripted_localisation/ADISCORD_STP_scripted_loc.txt"
LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
REPLACE_LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"


def read(path: Path) -> str:
    return read_focus_source(path)


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        return ""
    start = source.find("{", match.start())
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unclosed block: {name}")


def focus_block(source: str, focus_id: str) -> str:
    marker = re.search(rf"(?m)^\s*id\s*=\s*{re.escape(focus_id)}\s*$", source)
    if marker is None:
        return ""
    start = source.rfind("focus = {", 0, marker.start())
    if start < 0:
        return ""
    opening = source.find("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unclosed focus: {focus_id}")


class ShabratRiskAndRegionalTransferTests(unittest.TestCase):
    def test_overwhelming_resistance_is_a_transfer_basis(self) -> None:
        triggers = read(TRIGGERS)
        overwhelming = named_block(triggers, "STP_region_resistance_overwhelming")
        goes_to = named_block(triggers, "STP_cw_region_goes_to_resistance")

        self.assertIn("STP_region_resistance_entrenched = yes", overwhelming)
        self.assertIn(
            "var = STP_resistance_influence value = 90 compare = greater_than_or_equals",
            overwhelming,
        )
        self.assertIn("STP_region_resistance_overwhelming = yes", goes_to)

    def test_niansas_has_a_focus_unlocked_local_seizure_route(self) -> None:
        triggers = read(TRIGGERS)
        decisions = read(DECISIONS)
        positive = named_block(triggers, "STP_cw_shabrat_positive_legitimacy")
        goes_to = named_block(triggers, "STP_cw_region_goes_to_resistance")
        decision = named_block(decisions, "STP_cw_secure_niansas_administration")

        self.assertIn(
            "power_balance_value = { id = STP_shabrat_election_legitimacy value > 0 }",
            positive,
        )
        self.assertIn("state = 3", goes_to)
        self.assertIn("has_state_flag = STP_niansas_transfer_secured", goes_to)
        self.assertIn("has_completed_focus = STP_cw_repair_niansas", decision)
        self.assertIn("STP_cw_shabrat_positive_legitimacy = yes", decision)
        self.assertIn("STP_region_resistance_entrenched = yes", decision)
        self.assertIn("targets = { 3 }", decision)
        self.assertIn("days_remove = 14", decision)
        self.assertIn("set_state_flag = STP_niansas_transfer_secured", decision)

    def test_false_trail_is_the_first_ai_response_to_inspections(self) -> None:
        decisions = read(DECISIONS)
        false_trail = named_block(decisions, "STP_prepare_false_trail")
        ai = named_block(false_trail, "ai_will_do")

        self.assertIn("base = 40", ai)
        self.assertIn(
            "var = STP_party_suspicion value = 50 compare = greater_than_or_equals",
            ai,
        )
        self.assertIn(
            "var = STP_party_suspicion value = 70 compare = greater_than_or_equals",
            ai,
        )
        self.assertIn(
            "var = STP_party_suspicion value = 90 compare = greater_than_or_equals",
            ai,
        )
        self.assertNotRegex(
            ai,
            r"factor\s*=\s*0[\s\S]*?STP_party_suspicion\s+value\s*=\s*80",
        )

    def test_shabrat_ai_limits_suspicion_without_worldwide_inspection_lock(self) -> None:
        triggers = read(TRIGGERS)
        decisions = read(DECISIONS)
        gate = named_block(triggers, "STP_cw_shabrat_ai_risk_allowed")

        self.assertIn(
            "var = STP_party_suspicion value = 65 compare = less_than",
            gate,
        )
        self.assertNotIn("STP_cw_any_inspection_active", gate)

        risky = (
            "STP_cw_raise_district_network",
            "STP_cw_prepare_rifle_cache",
            "STP_recruit_regional_official",
            "STP_bargain_with_local_councils",
            "STP_region_unique_operation_2",
            "STP_region_unique_operation_3",
            "STP_region_unique_operation_29",
            "STP_region_unique_operation_45",
            "STP_region_unique_operation_46",
            "STP_region_unique_operation_53",
            "STP_cw_sabotage_capital",
            "STP_cw_sabotage_party_industry",
        )
        for decision_id in risky:
            with self.subTest(decision=decision_id):
                block = named_block(decisions, decision_id)
                ai = named_block(block, "ai_will_do")
                self.assertTrue(ai, f"{decision_id} lacks ai_will_do")
                self.assertIn(
                    "modifier = { factor = 0 NOT = { STP_cw_shabrat_ai_risk_allowed = yes } }",
                    ai,
                )

    def test_ai_prefers_buying_silence_over_exposing_the_cabinet(self) -> None:
        focuses = read(FOCUS)
        silence = named_block(focus_block(focuses, "STP_cw_buy_silence"), "ai_will_do")
        expose = named_block(focus_block(focuses, "STP_cw_expose_the_cabinet"), "ai_will_do")

        self.assertIn("base = 16", silence)
        self.assertIn("base = 1", expose)

    def test_party_elections_tooltip_documents_all_suspicion_thresholds(self) -> None:
        loc = read(LOC)
        match = re.search(
            r'(?m)^\s*STP_shabrat_election_bop_category_desc:\s*"([^"]*)"',
            loc,
        )
        self.assertIsNotNone(match)
        text = match.group(1)
        for token in ("60%", "70%", "90%", "100%", "40 дней", "Шабрат", "вторая комиссия", "арест"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_region_tooltips_explain_why_the_forecast_is_still_party(self) -> None:
        scripted_loc = read(SCRIPTED_LOC)
        loc = read(LOC)
        reason = named_block(scripted_loc, "defined_text")
        self.assertIn("name = STPGetCivilWarForecastReason", scripted_loc)
        for state in (2, 3, 29, 45, 46, 53):
            self.assertIn(f"[{state}.STPGetCivilWarForecastReason]", loc)
        self.assertIn("STP_CW_FORECAST_REASON_ADMINISTRATION", loc)
        self.assertIn("STP_CW_FORECAST_REASON_COUNTERINTELLIGENCE", loc)
        self.assertIn("STP_CW_FORECAST_REASON_NIANSAS_ROUTE", loc)
        self.assertIn("STP_CW_FORECAST_REASON_OVERWHELMING", loc)

    def test_niansas_override_tooltips_match_the_new_contract(self) -> None:
        loc = read(REPLACE_LOC)
        for token in (
            "90%",
            "Дорога через Ниансас",
            "положительного перевеса легитимности",
            "Перехватить областное управление",
        ):
            with self.subTest(token=token):
                self.assertIn(token, loc)


if __name__ == "__main__":
    unittest.main()
