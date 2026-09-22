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

    def test_capitulation_router_handles_stelander_and_kefreyt(self) -> None:
        router = self.read("common/on_actions/10_ADISCORD_bezhaysk_peace_on_actions.txt")
        self.assertIn("ADISCORD_bezhaysk_settle_sts_victory = yes", router)
        self.assertIn("ADISCORD_bezhaysk_settle_val_victory = yes", router)
        self.assertEqual(router.count("set_global_flag = skip_default_capitulation"), 2)

    def test_settlement_covers_the_feudal_bloc(self) -> None:
        effects = self.read("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(f"target = {tag}", effects)
        self.assertIn("white_peace = BJK", effects)

    def test_bezhaysk_starting_faction_uses_real_hachoesia_tag(self) -> None:
        history = self.read("history/countries/BJK - Besjaysk.txt")
        self.assertIn("add_to_faction = BHG", history)
        self.assertNotIn("add_to_faction = BHD", history)


if __name__ == "__main__":
    unittest.main()
