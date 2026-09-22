from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    path = ROOT / relative
    return path.read_text(encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    depth = 0
    quoted = False
    escaped = False
    for index in range(match.end() - 1, len(text)):
        char = text[index]
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
                return text[match.start(): index + 1]
    raise AssertionError(f"unclosed block {name}")


class ValStelanderEqualAllianceTests(unittest.TestCase):
    def test_recognition_returns_all_stelander_cores(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        refund = named_block(effects, "VAL_return_stelander_cores")
        self.assertIn("every_owned_state", refund)
        self.assertIn("is_core_of = STP", refund)
        self.assertIn("is_core_of = STS", refund)
        self.assertIn("transfer_state_to = STP", refund)
        self.assertIn("transfer_state_to = STS", refund)

    def test_equal_alliance_is_a_real_subbranch_after_ultimatum(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        for focus_id in (
            "VAL_Equal_Powers_Pact",
            "VAL_Joint_General_Staff",
            "VAL_Cross_Border_Contracts",
            "VAL_Two_States_One_Frontier",
        ):
            self.assertEqual(focuses.count(f"id = {focus_id}"), 1, focus_id)
        start = focuses.index("id = VAL_Equal_Powers_Pact")
        pact = focuses[start:start + 4000]
        self.assertIn("prerequisite = { focus = VAL_Stelander_Ultimatum }", pact)
        self.assertIn("has_country_flag = VAL_stelander_equal_recognition", pact)
        self.assertIn("ai_will_do = { base = 1 }", pact)

    def test_stelander_ai_rarely_accepts_alliance(self) -> None:
        events = read("events/ADISCORD_VAL_contract_events.txt")
        event_start = events.index("id = val_contract.354")
        event = events[event_start:event_start + 3000]
        self.assertIn("ai_chance = { base = 90 }", event)
        self.assertIn("base = 10", event)
        self.assertIn("factor = 0 has_country_leader = { character = STP_maksim_shabrat }", event)

    def test_alliance_blocks_kefreyt_final_crisis_against_stelander(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        crisis = named_block(triggers, "VAL_final_crisis_available")
        self.assertIn("NOT = { has_country_flag = VAL_stelander_equal_alliance }", crisis)

    def test_alliance_formation_preserves_equal_sovereignty(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        formation = named_block(effects, "VAL_form_equal_stelander_alliance")
        self.assertIn("create_faction_from_template", formation)
        self.assertIn("add_to_faction = STS", formation)
        self.assertIn("add_to_faction = STP", formation)
        self.assertNotIn("puppet =", formation)
        self.assertNotIn("set_autonomy", formation)

    def test_treaty_marks_recognition_on_both_sides(self) -> None:
        events = read("events/ADISCORD_VAL_contract_events.txt")
        start = events.index("id = val_contract.343")
        treaty = events[start:start + 5000]
        self.assertIn("VAL_return_stelander_cores = yes", treaty)
        self.assertGreaterEqual(treaty.count("set_country_flag = VAL_stelander_equal_recognition"), 2)

    def test_event_id_and_localisation_are_registered(self) -> None:
        ledger = read("tools/data/adiscord_event_ids.json")
        self.assertIn('"id": "val_contract.354"', ledger)
        for path in (
            "localisation/english/ADISCORD_VAL_stelander_alliance_l_english.yml",
            "localisation/russian/ADISCORD_VAL_stelander_alliance_l_russian.yml",
        ):
            loc = read(path)
            self.assertIn("val_contract.354.t:", loc)
            self.assertIn("VAL_Equal_Powers_Pact:", loc)


if __name__ == "__main__":
    unittest.main()
