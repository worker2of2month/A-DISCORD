"""Regression contract for Kefreyt's first defeat and the council's separate revanche."""
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
            "recruit_character = VAL_Commanders_Council",
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

    def test_council_revanche_is_separate_from_old_campaigns(self):
        from tools.tests.test_adiscord_stp_preparation import entries, scalar, block
        trees = entries("common/national_focus/ADISCORD_national_focus_VAL_defeated.txt")
        tree = next(e.value for e in trees if e.key == "focus_tree" and scalar(e.value, "id") == "VAL_defeated_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        self.assertIn("VAL_defeat_Revise_The_Settlement", focuses)
        peace = focuses["VAL_defeat_No_Second_Expedition"]
        revenge = focuses["VAL_defeat_Revise_The_Settlement"]
        self.assertEqual(scalar(block(peace, "mutually_exclusive"), "focus"), "VAL_defeat_Revise_The_Settlement")
        self.assertEqual(scalar(block(revenge, "mutually_exclusive"), "focus"), "VAL_defeat_No_Second_Expedition")
        final = focuses["VAL_defeat_Return_To_The_Passes"]
        self.assertIn("VAL_council_begin_revanche", str(final))
        self.assertIn("VAL_council_can_launch_revanche", str(block(final, "available")))
        text = read("common/national_focus/ADISCORD_national_focus_VAL_defeated.txt")
        for old in ("VAL_campaign_against_stelander", "VAL_campaign_against_nod", "VAL_cw_begin_mobilization"):
            self.assertNotIn(old, text)

    def test_revanche_requires_post_defeat_council_and_living_shabrat(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, matches_conditions
        from itertools import product
        triggers = entries("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = block(triggers, "VAL_council_can_prepare_revanche")
        for defeated, council, shabrat, subject, target_exists in product((False, True), repeat=5):
            facts = {
                ("VAL", "has_country_flag", "VAL_stelander_defeated"): defeated,
                ("VAL", "ruling_leader"): "VAL_Commanders_Council" if council else "VAL_Valera_Solgalov",
                ("VAL", "is_subject", "yes"): subject,
                ("VAL", "has_capitulated", "yes"): False,
                ("STS", "exists", "yes"): target_exists,
                ("STS", "STP_pc_founder_rules", "yes"): shabrat,
                ("STS", "has_capitulated", "yes"): False,
                ("STS", "is_subject", "yes"): False,
            }
            self.assertEqual(matches_conditions(gate, facts, "VAL"),
                             defeated and council and shabrat and not subject and target_exists)

    def test_war_entry_marks_the_current_revanche_before_declaring(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, walk, scalar
        effects = entries("common/scripted_effects/ADISCORD_VAL_effects.txt")
        body = block(effects, "VAL_council_begin_revanche")
        ordered = list(walk(body))
        marker = next(i for i, e in enumerate(ordered) if e.key == "set_country_flag" and e.value == "VAL_council_revanche_active")
        war = next(i for i, e in enumerate(ordered) if e.key == "declare_war_on")
        self.assertLess(marker, war)
        self.assertEqual(scalar(ordered[war].value, "target"), "STS")
        self.assertNotIn("clr_country_flag = VAL_stelander_defeated", read("common/scripted_effects/ADISCORD_VAL_effects.txt"))

    def test_first_defeat_and_revanche_select_different_settlements(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, selected_effects
        body = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pc_begin_settlement")
        for revanche in (False, True):
            facts = {
                ("STS", "variable", "STP_pc_cap_side"): 1,
                ("VAL", "has_country_flag", "VAL_council_revanche_active"): revanche,
                ("STS", "has_war_with", "VAL"): True,
            }
            effects = list(selected_effects(body, facts, "STS"))
            self.assertEqual(any(e.key == "STP_pc_annex_defeated_council" for _, e in effects), revanche)
            self.assertEqual(any(e.key == "VAL_enter_stelander_defeat" for _, e in effects), not revanche)

    def test_revanche_defeat_annexes_val_without_making_foreign_states_core(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, walk, scalar
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        body = block(effects, "STP_pc_annex_defeated_council")
        all_nodes = list(walk(body))
        annex = next(e for e in all_nodes if e.key == "annex_country")
        self.assertEqual(scalar(annex.value, "target"), "VAL")
        self.assertEqual(scalar(annex.value, "transfer_troops"), "no")
        self.assertNotIn("add_core_of", {e.key for e in all_nodes})
        self.assertIn("VAL_council_revanche_active", str(body))
        self.assertNotIn("VAL_enter_stelander_defeat", {e.key for e in all_nodes})

    def test_external_peace_clears_revanche_without_reopening_old_routes(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, selected_effects
        body = block(entries("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_council_reconcile_revanche")
        for war in (False, True):
            facts = {("VAL", "has_country_flag", "VAL_council_revanche_active"): True,
                     ("VAL", "has_war_with", "STS"): war}
            selected = list(selected_effects(body, facts, "VAL"))
            self.assertEqual(any(e.key == "clr_country_flag" and e.value == "VAL_council_revanche_active" for _, e in selected), not war)
        hooks = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        self.assertIn("VAL_council_reconcile_revanche = yes", hooks[hooks.index("on_peace = {"):])

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
