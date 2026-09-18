"""Regression contracts for Kefreyt's Livonn postwar settlement."""
from pathlib import Path
import unittest

from tools.lib.paths import source_section

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    file = ROOT / path
    return file.read_text(encoding="utf-8-sig") if file.exists() else ""


class ValLivonnSettlement(unittest.TestCase):
    def test_kefreyt_stages_livonn_only_after_occidian_administration_owns_it(self):
        effects = source_section(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "livonn_settlement_effects")
        stage = effects.split("VAL_cw_stage_livonn_settlement = {", 1)[1].split("VAL_cw_honor_livonn_agreement = {", 1)[0]
        self.assertIn("VAL_form_occidian_administration = yes", stage)
        self.assertIn("45 = { is_owned_by = OCA is_controlled_by = OCA }", stage)
        self.assertNotIn("transfer_state = 45", stage)
        self.assertIn("set_country_flag = VAL_cw_livonn_settlement_pending", stage)

    def test_honor_choice_returns_only_livonn_to_shabrat_side(self):
        effects = source_section(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "livonn_settlement_effects")
        honor = effects.split("VAL_cw_honor_livonn_agreement = {", 1)[1].split("VAL_cw_retain_livonn = {", 1)[0]
        self.assertIn("STS = { transfer_state = 45 }", honor)
        self.assertIn("45 = { remove_core_of = OCA set_state_controller_to = STS }", honor)
        self.assertIn("set_country_flag = VAL_cw_livonn_agreement_honored", honor)

    def test_keep_choice_retains_livonn(self):
        effects = source_section(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "livonn_settlement_effects")
        keep = effects.split("VAL_cw_retain_livonn = {", 1)[1]
        self.assertIn("45 = { set_state_controller_to = OCA }", keep)
        self.assertIn("set_country_flag = VAL_cw_livonn_retained", keep)
        self.assertNotIn("STS = { transfer_state = 45 }", keep)

    def test_runtime_hook_stages_after_srp_defeat_with_fallback(self):
        hook = read("common/on_actions/09_ADISCORD_VAL_livonn_settlement_on_actions.txt")
        self.assertIn("on_capitulation = {", hook)
        self.assertIn("ROOT = { tag = SRP }", hook)
        self.assertIn("VAL = {", hook)
        self.assertIn("VAL_cw_stage_livonn_settlement = yes", hook)
        self.assertIn("on_weekly_VAL = {", hook)

    def test_player_gets_two_mutually_exclusive_decisions_when_contract_exists(self):
        category = source_section(read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt"), "livonn_settlement_categories")
        decisions = source_section(read("common/decisions/ADISCORD_VAL_decisions.txt"), "livonn_settlement_decisions")
        self.assertIn("VAL_livonn_settlement_category = {", category)
        self.assertIn("has_country_flag = VAL_cw_livonn_settlement_pending", category)
        self.assertIn("VAL_honor_livonn_agreement = {", decisions)
        self.assertIn("VAL_keep_livonn = {", decisions)
        self.assertIn("VAL_cw_honor_livonn_agreement = yes", decisions)
        self.assertIn("VAL_cw_retain_livonn = yes", decisions)

    def test_localisation_exists_in_both_languages(self):
        ru = source_section(read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml"), "livonn_settlement_localisation")
        en = read("localisation/english/ADISCORD_VAL_livonn_settlement_l_english.yml")
        for key in (
            "VAL_livonn_settlement_category:",
            "VAL_honor_livonn_agreement:",
            "VAL_keep_livonn:",
        ):
            self.assertIn(key, ru)
            self.assertIn(key, en)


if __name__ == "__main__":
    unittest.main()
