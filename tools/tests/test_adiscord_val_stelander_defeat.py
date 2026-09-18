"""Regression contract for Kefreyt's terminal defeat by Shabrat."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


class ValStelanderDefeatTests(unittest.TestCase):
    def test_defeat_transition_replaces_solgalov_and_tree(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        start = effects.index("VAL_enter_stelander_defeat = {")
        body = effects[start:start + 6000]
        for token in (
            "set_country_flag = VAL_stelander_defeated",
            "set_country_flag = VAL_cw_defeated",
            "set_country_flag = VAL_cw_settled",
            "retire_character = VAL_Valera_Solgalov",
            "promote_character = { character = VAL_Commanders_Council ideology = contractual_etatism }",
            "load_focus_tree = { tree = VAL_defeated_focus keep_completed = no }",
            "mark_focus_tree_layout_dirty = yes",
        ):
            self.assertIn(token, body)

    def test_shabrat_victory_enters_defeat_state_before_white_peace(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        start = effects.index("STP_pc_begin_settlement = {")
        body = effects[start:effects.index("\nSTP_pc_clear_settlement = {", start)]
        branch = body[body.index("STP_pc_this_opponent value = 1"):]
        self.assertIn("VAL = { VAL_enter_stelander_defeat = yes }", branch)
        self.assertLess(branch.index("VAL = { VAL_enter_stelander_defeat = yes }"),
                        branch.index("white_peace = VAL"))

    def test_defeated_kefreyt_cannot_reopen_old_campaigns(self):
        triggers = read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt") + "\n" + read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        self.assertGreaterEqual(triggers.count("NOT = { has_country_flag = VAL_stelander_defeated }"), 3)
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for decision in ("VAL_campaign_against_stelander", "VAL_campaign_against_nod", "VAL_cw_begin_mobilization"):
            pos = decisions.index(decision + " = {")
            body = decisions[pos:pos + 2600]
            self.assertIn("VAL_stelander_defeated", body)

    def test_defeated_tree_contains_no_war_reentry(self):
        focus = read("common/national_focus/ADISCORD_national_focus_VAL_defeated.txt")
        self.assertIn("id = VAL_defeated_focus", focus)
        self.assertIn("has_country_flag = VAL_stelander_defeated", focus)
        for forbidden in (
            "declare_war_on",
            "VAL_campaign_against_stelander",
            "VAL_campaign_against_nod",
            "VAL_stelander_ultimatum",
            "VAL_cw_begin_mobilization",
        ):
            self.assertNotIn(forbidden, focus)

    def test_commanders_council_is_recruited_and_localised(self):
        chars = read("common/characters/VAL.txt")
        history = read("history/countries/VAL - ValeraLand.txt")
        ru = read("localisation/russian/nsb_characters_l_russian.yml")
        en = read("localisation/english/nsb_characters_l_english.yml")
        self.assertIn("VAL_Commanders_Council = {", chars)
        self.assertIn("recruit_character = VAL_Commanders_Council", history)
        self.assertIn('VAL_Commanders_Council: "Совет командиров"', ru)
        self.assertIn('VAL_Commanders_Council: "Council of Commanders"', en)


if __name__ == "__main__":
    unittest.main()
