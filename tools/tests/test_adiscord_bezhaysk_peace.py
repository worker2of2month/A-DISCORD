from pathlib import Path
from tools.lib.on_actions import read_scripted_peace
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BezhayskPeaceTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_val_explicitly_calls_every_current_vassal_on_the_defensive_side(self):
        from tools.tests.test_adiscord_val_refugees import load
        from tools.tests.test_adiscord_stp_preparation import scalar
        effect = load("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")["ADISCORD_bezhaysk_join_val_campaign"]
        self.assertEqual({e.key for e in effect}, {"BLD", "BHG", "BGT", "BBV", "BCM"})
        for scope in effect:
            body = scope.value[0].value
            war = next(e.value for e in body if e.key == "add_to_war")
            self.assertEqual(scalar(war, "targeted_alliance"), "BJK")
            self.assertEqual(scalar(war, "enemy"), "VAL")
        from tools.builders.build_adiscord_val_operations_map import BJK_STATES, MAP_TAGS
        self.assertLessEqual({4, 5, 6, 7, 9, 31, 41}, set(BJK_STATES))
        self.assertLessEqual({"BJK", "BLD", "BHG", "BGT", "BBV", "BCM"}, set(MAP_TAGS))

    def test_both_campaigns_record_their_authored_war(self) -> None:
        stp = self.read("events/ADISCORD_STP_events.txt")
        val = self.read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        self.assertIn("set_country_flag = ADISCORD_bezhaysk_campaign_active", stp)
        self.assertIn("set_country_flag = ADISCORD_bezhaysk_campaign_active", val)

    def test_capitulation_router_uses_runtime_receipts_not_focus_history(self) -> None:
        source = self.read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        immediate = source.split("# BEGIN bezhaysk:on_capitulation_immediate", 1)[1].split(
            "# END bezhaysk:on_capitulation_immediate", 1
        )[0]
        self.assertIn("has_country_flag = ADISCORD_bezhaysk_campaign_active", immediate)
        for focus_id in (
            "VAL_Bezhaysk_Operation",
            "STP_pw_party_bezhaysk_campaign",
            "STP_pw_take_bezhaysk",
        ):
            self.assertNotIn(f"has_completed_focus = {focus_id}", immediate)

        late = source.split("# BEGIN bezhaysk:on_capitulation\n", 1)[1].split(
            "# END bezhaysk:on_capitulation", 1
        )[0]
        self.assertIn("has_country_flag = ADISCORD_bezhaysk_capitulation_pending", late)
        self.assertNotIn("has_war_with", late)
        self.assertNotIn("has_completed_focus", late)
        self.assertNotIn("is_subject_of", late)
        self.assertNotIn("is_in_faction_with", late)

    def test_capitulation_router_handles_all_authored_routes(self) -> None:
        router = read_scripted_peace(ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt", "bezhaysk")
        for effect in (
            "ADISCORD_bezhaysk_settle_sts_victory = yes",
            "ADISCORD_bezhaysk_settle_stp_victory = yes",
            "ADISCORD_bezhaysk_settle_val_victory = yes",
            "ADISCORD_bezhaysk_settle_val_nod_joint_victory = yes",
            "ADISCORD_bezhaysk_settle_forest_val_victory = yes",
            "ADISCORD_bezhaysk_settle_forest_nod_victory = yes",
        ):
            self.assertIn(effect, router)
        self.assertEqual(router.count("set_global_flag = skip_default_capitulation"), 7)

    def test_settlement_covers_the_feudal_bloc(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(f"target = {tag}", effects)
        self.assertIn("white_peace = BJK", effects)

    def test_party_has_an_authored_bezhaysk_settlement(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        start = effects.index("ADISCORD_bezhaysk_settle_stp_victory = {")
        end = effects.index("ADISCORD_bezhaysk_settle_val_victory = {")
        settlement = effects[start:end]
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(f"annex_country = {{ target = {tag} transfer_troops = no }}", settlement)
        self.assertIn("set_country_flag = STP_pw_party_bezhaysk_victory", settlement)

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
        router = read_scripted_peace(ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt", "bezhaysk")
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

    def test_joint_award_is_selected_before_white_peace(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        start = effects.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = {")
        end = effects.index("ADISCORD_bezhaysk_settle_forest_val_victory = {")
        joint = effects[start:end]
        for tag, capital in (
            ("BLD", 31),
            ("BHG", 5),
            ("BGT", 4),
            ("BBV", 7),
            ("BCM", 9),
            ("BJK", 41),
        ):
            package_start = joint.index(f"limit = {{ {tag} = {{ exists = yes")
            package = joint[package_start:]
            controller = package.index(f"{capital} = {{ controller =")
            first_peace = package.index("white_peace =")
            self.assertLess(controller, first_peace, tag)

    def test_feudal_faction_is_dismantled_before_new_overlords(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        for name in (
            "ADISCORD_bezhaysk_settle_val_victory = {",
            "ADISCORD_bezhaysk_settle_val_nod_joint_victory = {",
        ):
            start = effects.index(name)
            end = effects.find("\nADISCORD_", start + len(name))
            block = effects[start:] if end == -1 else effects[start:end]
            self.assertIn("dismantle_faction = yes", block)
            self.assertLess(block.index("dismantle_faction = yes"), block.index("set_autonomy = {"))

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
