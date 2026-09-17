from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ON_ACTION = ROOT / "common/on_actions/05_ADISCORD_vorkerland_stalemate_on_actions.txt"


class VorkerlandCentralWarVarianceTests(unittest.TestCase):
    def test_ai_showdown_rolls_one_bounded_operational_initiative(self) -> None:
        self.assertTrue(ON_ACTION.is_file(), "missing central-war balance controller")
        source = ON_ACTION.read_text(encoding="utf-8-sig")

        self.assertIn("on_war_relation_added", source)
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
            source,
        )
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_initiative_selected }",
            source,
        )
        self.assertEqual(
            source.count(
                "set_global_flag = ADISCORD_vorkerland_central_initiative_selected"
            ),
            1,
        )

        # The balance roll is observer-only. A human claimant should never receive
        # or fight against a hidden random campaign handicap from this controller.
        for tag in ("WKR", "VAD", "TVA"):
            self.assertRegex(
                source,
                rf"{tag}\s*=\s*\{{\s*exists\s*=\s*yes\s+is_ai\s*=\s*yes\s*\}}",
            )

        # VAD is the observed dominant baseline, so the intervention deliberately
        # favours either challenger without excluding VAD from the roll entirely.
        weights = {
            "WKR": 40,
            "VAD": 20,
            "TVA": 40,
        }
        for tag, weight in weights.items():
            branch = re.search(
                rf"{weight}\s*=\s*\{{(?:(?!\n\s*\d+\s*=\s*\{{).)*?"
                rf"{tag}\s*=\s*\{{(?:(?!\n\s*\d+\s*=\s*\{{).)*?"
                r"add_timed_idea\s*=\s*\{\s*"
                r"idea\s*=\s*ADISCORD_vorkerland_northern_operational_initiative\s+"
                r"days\s*=\s*210\s*\}",
                source,
                re.DOTALL,
            )
            self.assertIsNotNone(branch, f"missing {weight}% initiative branch for {tag}")
            self.assertIn(
                f"set_country_flag = ADISCORD_vorkerland_central_initiative_{tag.lower()}",
                branch.group(0),
            )

        self.assertNotIn("annex_country", source)
        self.assertNotIn("white_peace", source)
        self.assertNotIn("set_capitulation", source)


if __name__ == "__main__":
    unittest.main()
