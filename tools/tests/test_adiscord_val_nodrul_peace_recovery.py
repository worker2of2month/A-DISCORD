from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt"


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

    def test_joint_shabrat_campaign_keeps_its_own_settlement(self) -> None:
        self.assertIn("has_country_flag = VAL_joint_nod_campaign_with_sts", self.reconcile)
        self.assertIn("NOD = { exists = yes has_war_with = VAL has_war_with = STS has_capitulated = yes }", self.reconcile)
        self.assertIn("VAL_settle_joint_nod_shabrat_victory = yes", self.reconcile)

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
