from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BezhayskPeaceTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_both_campaigns_record_their_authored_war(self) -> None:
        stp = self.read("events/ADISCORD_STP_events.txt")
        val = self.read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        self.assertIn("set_country_flag = ADISCORD_bezhaysk_campaign_active", stp)
        self.assertIn("set_country_flag = ADISCORD_bezhaysk_campaign_active", val)

    def test_capitulation_router_handles_all_authored_routes(self) -> None:
        router = self.read("common/on_actions/10_ADISCORD_bezhaysk_peace_on_actions.txt")
        for effect in (
            "ADISCORD_bezhaysk_settle_sts_victory = yes",
            "ADISCORD_bezhaysk_settle_val_victory = yes",
            "ADISCORD_bezhaysk_settle_val_nod_joint_victory = yes",
            "ADISCORD_bezhaysk_settle_forest_val_victory = yes",
            "ADISCORD_bezhaysk_settle_forest_nod_victory = yes",
        ):
            self.assertIn(effect, router)
        self.assertEqual(router.count("set_global_flag = skip_default_capitulation"), 5)

    def test_settlement_covers_the_feudal_bloc(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(f"target = {tag}", effects)
        self.assertIn("white_peace = BJK", effects)

    def test_kefreyt_uses_contract_clients_instead_of_direct_annexation(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        start = effects.index("ADISCORD_bezhaysk_settle_val_victory = {")
        end = effects.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = {")
        settlement = effects[start:end]
        self.assertNotIn("annex_country", settlement)
        self.assertGreaterEqual(
            settlement.count("autonomy_state = autonomy_VAL_contract_administration"),
            6,
        )

    def test_joint_kefreyt_nodrul_settlement_is_prioritized(self) -> None:
        router = self.read("common/on_actions/10_ADISCORD_bezhaysk_peace_on_actions.txt")
        joint = router.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = yes")
        single_val = router.index("ADISCORD_bezhaysk_settle_val_victory = yes")
        self.assertLess(joint, single_val)
        self.assertIn("has_war_together_with = NOD", router)
        self.assertIn("ADISCORD_bezhaysk_joint_default_nod", router)
        self.assertIn("ADISCORD_bezhaysk_joint_default_val", router)

    def test_joint_settlement_keeps_feudal_holdings_as_client_states(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        start = effects.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = {")
        joint = effects[start:]
        self.assertNotIn("annex_country", joint)
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(f"target = {tag}", joint)
        for capital in (41, 31, 5, 4, 7, 9):
            self.assertIn(f"{capital} = {{ controller =", joint)
        self.assertIn("autonomy_state = autonomy_VAL_contract_administration", joint)
        self.assertIn("autonomy_state = autonomy_NOD_protected_administration", joint)
        self.assertGreaterEqual(joint.count("set_country_flag = ADISCORD_bezhaysk_joint_settlement"), 2)

    def test_nodrul_has_a_distinct_protected_administration_level(self) -> None:
        autonomy = self.read("common/autonomous_states/ADISCORD_contract_clients.txt")
        self.assertIn("id = autonomy_NOD_protected_administration", autonomy)
        self.assertIn("allowed_levels_filter = { autonomy_NOD_protected_administration }", autonomy)
        self.assertIn("use_overlord_color = no", autonomy)

    def test_grandfather_lishay_can_be_taken_in_a_separate_late_campaign(self) -> None:
        state = self.read("history/states/14-Flaem-Prana.txt")
        decisions = self.read("common/decisions/ADISCORD_bezhaysk_decisions.txt")
        self.assertIn("victory_points = { 75 5 }", state)
        self.assertIn("owner = COF", state)
        self.assertIn("ADISCORD_bezhaysk_subjugate_forest_val", decisions)
        self.assertIn("ADISCORD_bezhaysk_subjugate_forest_nod", decisions)
        self.assertEqual(decisions.count("declare_war_on = { target = COF type = annex_everything }"), 2)

    def test_bezhaysk_starting_faction_uses_real_hachoesia_tag(self) -> None:
        history = self.read("history/countries/BJK - Besjaysk.txt")
        self.assertIn("add_to_faction = BHG", history)
        self.assertNotIn("add_to_faction = BHD", history)


if __name__ == "__main__":
    unittest.main()
