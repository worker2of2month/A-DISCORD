from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt"
ON_ACTIONS = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_VAL_decisions.txt"
EVENTS = ROOT / "events/ADISCORD_VAL_contract_events.txt"


def named_block(text: str, name: str) -> str:
    marker = f"{name} = {{"
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
    raise AssertionError(f"Unclosed block: {name}")


class KefreytNodrulPeaceRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = EFFECTS.read_text(encoding="utf-8")
        cls.reconcile = named_block(cls.source, "VAL_final_crisis_reconcile")

    def test_old_pre_stelander_final_war_is_closed(self) -> None:
        self.assertIn("VAL_stelander_dominated = no", self.reconcile)
        self.assertIn("NOD = { has_country_flag = VAL_final_war_member }", self.reconcile)
        self.assertIn("NOD = { NOT = { has_country_flag = VAL_frontier_guarantor } }", self.reconcile)
        self.assertIn("NOT = { has_country_flag = VAL_joint_nod_campaign_with_sts }", self.reconcile)
        self.assertIn("white_peace = VAL", self.reconcile)

    def test_missed_final_capitulation_is_recovered(self) -> None:
        self.assertIn("VAL_stelander_dominated = yes", self.reconcile)
        self.assertGreaterEqual(self.reconcile.count("has_country_flag = VAL_final_war_member has_capitulated = yes"), 3)
        self.assertGreaterEqual(self.reconcile.count("set_country_flag = VAL_final_defeat_pending"), 3)
        self.assertIn("VAL_finalize_reserved_settlements = yes", self.reconcile)

    def test_joint_shabrat_campaign_recovers_from_receipt_after_war_cleanup(self) -> None:
        self.assertIn("has_country_flag = VAL_joint_nod_campaign_with_sts", self.reconcile)
        self.assertIn("NOT = { has_country_flag = VAL_joint_nod_settlement_completed }", self.reconcile)
        self.assertIn("has_country_flag = VAL_joint_nod_campaign_target", self.reconcile)
        self.assertIn("has_capitulated = yes", self.reconcile)
        self.assertNotIn("NOD = { exists = yes has_war_with = VAL has_war_with = STS has_capitulated = yes }", self.reconcile)
        self.assertIn("VAL_settle_joint_nod_shabrat_victory = yes", self.reconcile)

    def test_frontier_partner_can_receive_nodrul_capitulation_credit(self) -> None:
        router = ON_ACTIONS.read_text(encoding="utf-8")
        router = router.split("# BEGIN kefreyt:on_capitulation_immediate", 1)[1]
        router = router.split("# END kefreyt:on_capitulation_immediate", 1)[0]
        compact_router = " ".join(router.split())
        self.assertIn(
            "OR = { FROM = { VAL_final_campaign_ally = yes } capital_scope = { controller = { VAL_final_campaign_ally = yes } } }",
            compact_router,
        )

        ally = named_block(TRIGGERS.read_text(encoding="utf-8"), "VAL_final_campaign_ally")
        self.assertIn("tag = VAL", ally)
        self.assertIn("is_subject_of = VAL", ally)
        self.assertIn("tag = TFF", ally)
        self.assertIn("is_subject_of = TFF", ally)
        self.assertIn("VAL_frontier_partner_available = yes", ally)
        self.assertIn("has_country_flag = VAL_nod_frontier_agreement", ally)

        triggers = TRIGGERS.read_text(encoding="utf-8")
        available = named_block(triggers, "VAL_final_crisis_available")
        launchable = named_block(triggers, "VAL_can_launch_final_campaign")
        for block in (available, launchable):
            self.assertIn("is_subject_of = STP", block)
            self.assertIn("STP = { is_subject_of = VAL }", block)

    def test_party_victory_nested_nodrul_is_released_before_final_war(self) -> None:
        release = named_block(self.source, "VAL_release_party_nodrul_for_final_campaign")
        self.assertIn("NOD = { exists = yes has_capitulated = no is_subject_of = STP }", release)
        self.assertIn("STP = { exists = yes has_capitulated = no is_subject_of = VAL }", release)
        self.assertIn("target = NOD", release)
        self.assertIn("autonomy_state = autonomy_free", release)
        self.assertIn("end_wars = no", release)

        launch = named_block(self.source, "VAL_final_crisis_launch")
        execute = named_block(self.source, "VAL_final_crisis_execute_launch")
        self.assertIn("VAL_release_party_nodrul_for_final_campaign = yes", launch)
        self.assertIn("id = val_rework.122 days = 1", launch)
        self.assertNotIn("declare_war_on = { target = STP", launch)
        self.assertIn("declare_war_on = { target = NOD type = annex_everything }", execute)

        decision = named_block(DECISIONS.read_text(encoding="utf-8"), "VAL_campaign_against_nod")
        self.assertIn("AND = { tag = NOD is_subject_of = STP }", decision)
        self.assertIn("VAL_release_party_nodrul_for_final_campaign = yes", decision)

        all_events = EVENTS.read_text(encoding="utf-8")
        marker = "id = val_rework.122"
        start = all_events.index(marker)
        event_start = all_events.rfind("country_event = {", 0, start)
        event = named_block(all_events[event_start:], "country_event")
        self.assertIn("VAL_final_party_nod_release_pending", event)
        self.assertIn("VAL_final_crisis_execute_launch = yes", event)

    def test_party_victory_settlement_breaks_stale_stp_overlordship(self) -> None:
        install = named_block(self.source, "VAL_install_nodrul_administration")
        self.assertIn("is_subject_of = STP", install)
        self.assertIn("STP = { is_subject_of = VAL }", install)
        self.assertIn("autonomy_state = autonomy_free", install)
        self.assertLess(
            install.index("autonomy_state = autonomy_free"),
            install.index("VAL_nodrul_administration_pending"),
        )

    def test_nodrul_settlement_closes_bezhaysk_war_before_capitulation(self) -> None:
        install = named_block(self.source, "VAL_install_nodrul_administration")
        settle = named_block(self.source, "VAL_settle_nodrul_bezhaysk_war")
        self.assertIn("VAL_settle_nodrul_bezhaysk_war = yes", install)
        self.assertIn("has_war_with = BJK", settle)
        self.assertIn("has_country_flag = ADISCORD_bezhaysk_campaign_active", settle)
        self.assertNotIn("has_completed_focus = VAL_Bezhaysk_Operation", settle)
        self.assertIn("white_peace = BJK", settle)


if __name__ == "__main__":
    unittest.main()
