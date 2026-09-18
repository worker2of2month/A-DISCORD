"""Regression contract for Shabrat's active postwar gameplay."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    marker = name + " ="
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
        offer = named_block(triggers, "STP_pc_can_offer_nod_terms")
        current = named_block(triggers, "STP_pc_nod_offer_current")
        for block in (offer, current):
            self.assertIn("has_country_flag = NOD_cw_defeated", block)
            self.assertIn("has_country_flag = STP_pc_defeated_by_sts", block)
            self.assertIn("has_capitulated = no", block)

        events = read("events/ADISCORD_STP_events.txt")
        demand = event_block(events, "ADISCORD_STP_pc.18")
        reject = demand[demand.index("name = STP_pc_reject_terms"):]
        reject = reject[:reject.index("\n\toption = {", 1)]
        self.assertIn("STP_pc_nod_offer_kind value = 2", reject)
        self.assertIn("NOD_cw_defeated", reject)
        self.assertIn("STP_pc_defeated_by_sts", reject)

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
            "ADISCORD_campaign_slot_grant = yes",
            "STP_pw_propaganda_slot_1",
            "STP_pw_propaganda_slot_2",
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

        loc = read("localisation/russian/ADISCORD_STP_l_russian.yml")
        for key in (
            "STP_postwar_reconstruction_drive",
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
        ):
            self.assertIn(key + ":", loc)

    def test_existing_saves_reconcile_postwar_gameplay_weekly(self):
        on_actions = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        weekly = named_block(on_actions, "on_weekly_STS")
        self.assertIn("STP_pw_reconcile_postwar_interactivity = yes", weekly)


if __name__ == "__main__":
    unittest.main()
