from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ON_ACTIONS = ROOT / "common/on_actions/ZZ_ADISCORD_default_capitulation_on_actions.txt"


def read() -> str:
    return ON_ACTIONS.read_text(encoding="utf-8-sig")


class VorkerlandClaimantCleanupTests(unittest.TestCase):
    def test_reserved_losing_claimant_is_consumed_by_the_live_winner(self) -> None:
        source = " ".join(read().split())
        self.assertIn(
            "has_country_flag = ADISCORD_vorkerland_claimant_cleanup_reserved",
            source,
        )
        self.assertGreaterEqual(
            source.count("annex_country = { target = ROOT transfer_troops = yes }"),
            5,
        )
        for route in (
            "ADISCORD_vorkerland_is_main_claimant = yes",
            "is_subject = yes",
            "OVERLORD = {",
            "tag = WTD",
            "TVA = {",
            "tag = VLA",
            "WKR = {",
            "tag = SOL",
            "VAD = {",
            "tag = WRK",
        ):
            with self.subTest(route=route):
                self.assertIn(route, source)

    def test_tva_aligned_ostfort_is_annexed_before_defeated_tva(self) -> None:
        source = " ".join(read().split())
        aligned = "has_country_flag = ADISCORD_vorkerland_worx_aligned_technocrats"
        ostfort_annex = "annex_country = { target = WTD transfer_troops = no }"
        self.assertIn("ROOT = { tag = TVA", source)
        self.assertIn(aligned, source)
        self.assertIn(ostfort_annex, source)
        self.assertLess(
            source.index(ostfort_annex),
            source.index("annex_country = { target = ROOT transfer_troops = yes }"),
        )

    def test_tva_authored_technocrat_satellites_do_not_become_orphans(self) -> None:
        source = " ".join(read().split())
        self.assertIn(
            "has_country_flag = ADISCORD_vorkerland_joined_worx_directorate",
            source,
        )
        self.assertIn(
            "annex_country = { target = TGD transfer_troops = no }",
            source,
        )


if __name__ == "__main__":
    unittest.main()
