from __future__ import annotations

import re
import unittest

from tools.validators import validate_adiscord_new_states as validator


class VorkerlandNewStateOutcomeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        validator.ERRORS.clear()

    def tearDown(self) -> None:
        validator.ERRORS.clear()

    def test_expansion_and_reunification_contract_passes(self) -> None:
        validator.validate_vorkerland_expansion()
        self.assertEqual(validator.ERRORS, [])

    def test_worker_outcome_marks_wartime_wkr_before_final_wrk_formation(self) -> None:
        maps = validator.text(
            validator.ROOT
            / "common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt"
        )
        worker_map = validator.block(maps, "ADISCORD_vorkerland_apply_worker_map")
        self.assertRegex(
            worker_map,
            r"\bWKR\s*=\s*\{\s*set_country_flag\s*=\s*"
            r"ADISCORD_vorkerland_central_unifier\s*\}",
        )
        self.assertNotRegex(
            worker_map,
            r"(?s)\bWRK\s*=\s*\{.*?ADISCORD_vorkerland_central_unifier",
        )
        self.assertIn("ADISCORD_vorkerland_begin_reunification = yes", worker_map)
        for forbidden in ("transfer_state", "annex_country", "puppet =", "set_autonomy"):
            self.assertNotIn(forbidden, worker_map)

        phase_effects = validator.text(
            validator.ROOT / "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt"
        )
        formation = validator.block(
            phase_effects, "ADISCORD_vorkerland_form_wrk_from_wkr"
        )
        self.assertIn("change_tag_from = WKR", formation)
        self.assertIn("ADISCORD_vorkerland_finalize_wrk_formation = yes", formation)

    def test_phase_six_dispatches_every_surviving_claimant_to_final_wrk(self) -> None:
        phase_events = validator.text(
            validator.ROOT / "events/ADISCORD_vorkerland_phase_events.txt"
        )
        phase_six = validator.event_block(
            phase_events, "ADISCORD_vorkerland_phase.6"
        )
        for tag, effect in (
            ("WKR", "ADISCORD_vorkerland_form_wrk_from_wkr"),
            ("VAD", "ADISCORD_vorkerland_form_wrk_from_vad"),
            ("TVA", "ADISCORD_vorkerland_form_wrk_from_tva"),
        ):
            with self.subTest(tag=tag):
                self.assertRegex(
                    phase_six,
                    rf"(?s)\b{tag}\s*=\s*\{{.*?{re.escape(effect)}\s*=\s*yes"
                    r".*?ADISCORD_vorkerland_phase\.7",
                )


if __name__ == "__main__":
    unittest.main()
