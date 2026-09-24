"""Regression contract for Shabrat's active postwar gameplay."""
from tools.lib.on_actions import read_country_on_actions
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    marker = name + " = {"
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
    raise AssertionError(f"unclosed block {name}")


def event_block(text: str, event_id: str) -> str:
    pos = text.index(f"id = {event_id}")
    start = text.rfind("country_event = {", 0, pos)
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unclosed event {event_id}")


class ShabratPostwarInteractivityTests(unittest.TestCase):
    def test_defeated_nodrul_can_receive_hegemony_terms(self):
        triggers = read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        government = named_block(triggers, "STP_pc_nod_government_exists")
        for token in (
            "has_capitulated = no",
            "has_country_flag = NOD_cw_defeated",
            "has_country_flag = STP_pc_defeated_by_sts",
        ):
            self.assertIn(token, government)

        offer = named_block(triggers, "STP_pc_can_offer_nod_terms")
        current = named_block(triggers, "STP_pc_nod_offer_current")
        self.assertIn("NOD = { STP_pc_nod_government_exists = yes", offer)
        self.assertIn("STP_pc_nod_government_exists = yes", current)


    def test_postwar_nodrul_defeat_is_recorded_before_white_peace(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        settlement = named_block(effects, "STP_pc_begin_settlement")
        branch_start = settlement.index("STP_pc_this_opponent value = 2")
        branch = settlement[branch_start:]
        self.assertIn("NOD = { set_country_flag = STP_pc_defeated_by_sts }", branch)
        self.assertLess(
            branch.index("NOD = { set_country_flag = STP_pc_defeated_by_sts }"),
            branch.index("white_peace = NOD"),
        )

    def test_reconstruction_minigame_has_three_metrics_and_completion_gate(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        init = named_block(effects, "STP_pw_reconcile_postwar_interactivity")
        for token in (
            "STP_pw_reconstruction_momentum",
            "STP_pw_public_confidence",
            "STP_pw_regional_cohesion",
        ):
            self.assertIn(token, init)

        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        for decision in (
            "STP_pw_reconstruction_emergency_repairs",
            "STP_pw_reconstruction_district_congresses",
            "STP_pw_reconstruction_publish_war_accounts",
            "STP_pw_reconstruction_veteran_housing",
            "STP_pw_complete_first_reconstruction_plan",
        ):
            self.assertIn(decision + " = {", decisions)
        completion = named_block(decisions, "STP_pw_complete_first_reconstruction_plan")
        for metric in (
            "STP_pw_reconstruction_momentum",
            "STP_pw_public_confidence",
            "STP_pw_regional_cohesion",
        ):
            self.assertIn(metric, completion)
            self.assertIn("value = 70", completion)
        self.assertIn("STP_pw_reconstruction_drive_completed", completion)

    def test_propaganda_uses_shared_slot_system_and_feeds_minigame(self):
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        for decision in (
            "STP_pw_campaign_country_is_being_built",
            "STP_pw_campaign_one_steland",
            "STP_pw_campaign_engineers_of_peace",
            "STP_pw_campaign_victory_means_normal_life",
        ):
            block = named_block(decisions, decision)
            self.assertIn("ADISCORD_has_campaign_slot = yes", block)
            self.assertIn("ADISCORD_campaign_slot_consume = yes", block)
            self.assertIn("ADISCORD_campaign_slot_release = yes", block)
            self.assertTrue(
                any(metric in block for metric in (
                    "STP_pw_reconstruction_momentum",
                    "STP_pw_public_confidence",
                    "STP_pw_regional_cohesion",
                )),
                decision,
            )

    def test_postwar_categories_and_localisation_exist(self):
        categories = read("common/decisions/categories/ADISCORD_decision_categories_STP.txt")
        self.assertIn("STP_postwar_reconstruction_drive = {", categories)
        self.assertIn("STP_postwar_propaganda_campaigns = {", categories)

        loc_path = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
        raw = loc_path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        lines = raw.decode("utf-8-sig").splitlines()
        keys = [
            "STP_pw_price_50",
            "STP_pw_price_50_blocked",
            "STP_pw_price_50_tooltip",
            "STP_postwar_reconstruction_drive",
            "STP_postwar_reconstruction_drive_desc",
            "STP_postwar_propaganda_campaigns",
            "STP_pw_reconstruction_emergency_repairs",
            "STP_pw_reconstruction_district_congresses",
            "STP_pw_reconstruction_publish_war_accounts",
            "STP_pw_reconstruction_veteran_housing",
            "STP_pw_complete_first_reconstruction_plan",
            "STP_pw_campaign_country_is_being_built",
            "STP_pw_campaign_one_steland",
            "STP_pw_campaign_engineers_of_peace",
            "STP_pw_campaign_victory_means_normal_life",
        ]
        for key in keys:
            found = [line for line in lines if line.lstrip().startswith(key + ":")]
            self.assertEqual(len(found), 1, key)
            self.assertRegex(found[0], r'^\s*' + key + r':\d* "[^\r\n]+"$')
            self.assertNotIn("\ufffd", found[0])

    def test_postwar_pacing_keeps_routine_focuses_at_28_days_or_less(self):
        focus = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        expected_costs = {
            "STP_pc_shabrat_cabinet": 4,
            "STP_pc_shabrat_politics": 4,
            "STP_pc_two_borders": 4,
            "STP_pc_war_ledgers": 4,
            "STP_pc_shared_archive_policy": 4,
            "STP_pc_heg_unity": 4,
            "STP_pc_heg_emergency": 4,
            "STP_pc_heg_subordinate": 4,
            "STP_pc_heg_limit_parties": 4,
            "STP_pc_heg_val_audit": 4,
            "STP_pc_heg_val_terms": 4,
            "STP_pc_heg_val_force": 4,
            "STP_pc_heg_nod_break": 3,
            "STP_pc_heg_nod_force": 3,
            "STP_pc_lib_assembly": 4,
            "STP_pc_lib_institutions": 4,
            "STP_pc_lib_prepare_neighbors": 4,
            "STP_pc_lib_local_contacts": 4,
            "STP_pc_lib_crisis": 4,
            "STP_pc_lib_war": 4,
            "STP_pc_development_reopen_universities": 4,
            "STP_pc_development_national_research_institutes": 5,
        }
        for focus_id, expected in expected_costs.items():
            pos = focus.index(f"id = {focus_id}")
            start = focus.rfind("\n\tfocus = {", 0, pos) + 1
            end = focus.index("\n\t}", pos) + 3
            block = focus[start:end]
            self.assertIn(f"cost = {expected}", block, focus_id)

    def test_dual_ultimatum_defeat_closes_both_external_wars(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        cleanup = named_block(effects, "STP_close_competing_ultimatum_wars_after_defeat")
        self.assertIn("has_war_with = VAL", cleanup)
        self.assertIn("white_peace = VAL", cleanup)
        self.assertIn("has_war_with = NOD", cleanup)
        self.assertIn("white_peace = NOD", cleanup)
        self.assertIn("VAL_stelander_truce", cleanup)

        settlement = named_block(effects, "STP_pc_begin_settlement")
        defeat = settlement[settlement.index("STP_pc_cap_side value = 3"):]
        self.assertIn("STP_close_competing_ultimatum_wars_after_defeat = yes", defeat)
        victory_prefix = settlement[:settlement.index("STP_pc_cap_side value = 3")]
        self.assertNotIn("STP_close_competing_ultimatum_wars_after_defeat = yes", victory_prefix)

    def test_postwar_initialization_is_event_driven(self):
        on_actions = read_country_on_actions("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander')
        weekly = named_block(on_actions, "on_weekly_STS")
        self.assertNotIn("STP_pw_reconcile_postwar_interactivity = yes", weekly)
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.assertIn("STP_pw_reconcile_postwar_interactivity = yes", named_block(effects, "STP_cw_finish_mobilization"))


if __name__ == "__main__":
    unittest.main()
