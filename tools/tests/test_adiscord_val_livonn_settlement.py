"""Regression contracts for Kefreyt's Livonn postwar settlement."""
from tools.lib.on_actions import read_scripted_peace
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

    def test_livonn_cannot_be_taken_from_stelander_or_another_client(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, matches_conditions
        triggers = entries("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        eligible = block(triggers, "VAL_livonn_available_for_administration")
        for owner in ("STP", "STS", "NOD", "VAL", "SRP", "OCA"):
            with self.subTest(owner=owner):
                facts = {("45", "is_owned_by", owner): True,
                         ("45", "VAL_occidian_state_available", "yes"): True}
                self.assertEqual(matches_conditions(eligible, facts, "45"), owner in {"VAL", "SRP", "OCA"})
        form = block(triggers, "VAL_can_form_occidian_administration")
        self.assertFalse(any(e.key == "45" for e in form), "Livonn must not block creation without it")
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        self.assertIn("limit = { 45 = { VAL_livonn_available_for_administration = yes } } transfer_state = 45", effects)
        settlement = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt").split("VAL_cw_settle_republics = {", 1)[1].split("STP_cw_poll_nod_intervention", 1)[0]
        self.assertIn("45 = { is_owned_by = SRP OR = { is_controlled_by = SRP is_controlled_by = VAL } }", settlement)

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
        hook = read_scripted_peace(Path("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt").with_name('09_ADISCORD_scripted_peace_on_actions.txt'), 'livonn')
        self.assertIn("on_capitulation = {", hook)
        self.assertIn("ROOT = { tag = SRP }", hook)
        self.assertIn("VAL = {", hook)
        self.assertIn("VAL_cw_stage_livonn_settlement = yes", hook)
        self.assertIn("on_weekly_VAL = {", hook)

    def test_player_gets_two_mutually_exclusive_decisions_when_contract_exists(self):
        category = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        self.assertIn("VAL_frontier = {", category)
        self.assertIn("has_country_flag = VAL_cw_livonn_settlement_pending", category)
        self.assertIn("VAL_honor_livonn_agreement = {", decisions)
        self.assertIn("VAL_keep_livonn = {", decisions)
        self.assertIn("VAL_cw_honor_livonn_agreement = yes", decisions)
        self.assertIn("VAL_cw_retain_livonn = yes", decisions)

    def test_localisation_exists_in_both_languages(self):
        ru = source_section(read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml"), "livonn_settlement_localisation")
        en = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")
        for key in (
            "VAL_livonn_settlement_category:",
            "VAL_honor_livonn_agreement:",
            "VAL_keep_livonn:",
        ):
            self.assertIn(key, ru)
            self.assertIn(key, en)


if __name__ == "__main__":
    unittest.main()
