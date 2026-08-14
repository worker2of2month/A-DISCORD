from __future__ import annotations

import re
import unittest

from tools.builders import build_adiscord_new_states as builder
from tools.lib.adiscord_vorkerland_theatre_manifest import (
    UNITY_TOWER_NAME,
    UNITY_TOWER_PROVINCE,
    UNITY_TOWER_STATE,
    UNITY_TOWER_VALUE,
    VORKERLAND_PROTECTED_LANDMARK_VPS,
    VORKERLAND_THEATRE_PACKAGES,
    VORKERLAND_THEATRE_PACKAGE_TOTALS,
    VORKERLAND_THEATRE_RETIRED_VP_IDS,
    VORKERLAND_THEATRE_VICTORY_POINTS,
    VORKERLAND_THEATRE_VP_NAME_OVERRIDES,
)
from tools.validators import validate_adiscord_new_states as validator


class VorkerlandNewStateOutcomeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        validator.ERRORS.clear()

    def tearDown(self) -> None:
        validator.ERRORS.clear()

    def test_expansion_and_reunification_contract_passes(self) -> None:
        validator.validate_vorkerland_expansion()
        self.assertEqual(validator.ERRORS, [])

    def test_legacy_scalar_rewrite_removes_duplicate_declarations(self) -> None:
        source = "state={\n\tlocal_supplies = 6.0\n\tlocal_supplies=10\n\thistory = { }\n}\n"
        updated = builder.set_scalar(source, "local_supplies", "6.0")
        self.assertEqual(
            re.findall(
                r"(?m)^[ \t]*local_supplies[ \t]*=[ \t]*[^\s#]+[ \t]*$",
                updated,
            ),
            ["\tlocal_supplies = 6.0"],
        )
        self.assertEqual(builder.set_scalar(updated, "local_supplies", "6.0"), updated)

    def test_nden_has_two_exact_theatre_victory_points(self) -> None:
        self.assertEqual(
            VORKERLAND_THEATRE_VICTORY_POINTS[27],
            ((16614, 3), (5090, 3)),
        )
        state = builder.state_path(27).read_text(encoding="utf-8-sig")
        self.assertEqual(
            tuple(
                (int(province_id), int(value))
                for province_id, value in re.findall(
                    r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", state
                )
            ),
            VORKERLAND_THEATRE_VICTORY_POINTS[27],
        )

    def test_exact_vp_replacement_removes_extras_and_is_idempotent(self) -> None:
        source = (
            "state={\n\tprovinces={ 10 20 }\n\thistory={\n"
            "\t\tvictory_points={ 10 99 }\n"
            "\t\tvictory_points = { 30 7 }\n\t}\n}\n"
        )
        expected = ((10, 3), (20, 5))
        updated = builder.replace_history_victory_points(source, expected)
        self.assertEqual(
            re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", updated),
            [("10", "3"), ("20", "5")],
        )
        self.assertEqual(builder.replace_history_victory_points(updated, expected), updated)

    def test_theatre_package_totals_are_exact(self) -> None:
        actual = {
            package: sum(
                value
                for state_id in states
                for _province_id, value in VORKERLAND_THEATRE_VICTORY_POINTS[state_id]
            )
            for package, states in VORKERLAND_THEATRE_PACKAGES.items()
        }
        self.assertEqual(actual, VORKERLAND_THEATRE_PACKAGE_TOTALS)

    def test_unity_tower_is_an_irremovable_landmark(self) -> None:
        protected = {UNITY_TOWER_STATE: ((UNITY_TOWER_PROVINCE, UNITY_TOWER_VALUE),)}
        self.assertEqual(VORKERLAND_PROTECTED_LANDMARK_VPS, protected)
        self.assertEqual(
            VORKERLAND_THEATRE_VICTORY_POINTS[UNITY_TOWER_STATE],
            protected[UNITY_TOWER_STATE],
        )
        self.assertNotIn(UNITY_TOWER_PROVINCE, VORKERLAND_THEATRE_RETIRED_VP_IDS)
        self.assertEqual(
            VORKERLAND_THEATRE_VP_NAME_OVERRIDES[UNITY_TOWER_PROVINCE],
            UNITY_TOWER_NAME,
        )
        self.assertEqual(VORKERLAND_THEATRE_PACKAGE_TOTALS["WKR"], 58)

        state = builder.state_path(UNITY_TOWER_STATE).read_text(encoding="utf-8-sig")
        self.assertIn("impassable = yes", state)
        self.assertEqual(
            re.findall(
                rf"victory_points\s*=\s*\{{\s*{UNITY_TOWER_PROVINCE}\s+(\d+)\s*\}}",
                state,
            ),
            [str(UNITY_TOWER_VALUE)],
        )
        localisation = (
            builder.ROOT / "localisation/russian/victory_points_l_russian.yml"
        ).read_text(encoding="utf-8-sig")
        self.assertEqual(
            re.findall(
                rf'(?m)^\s*VICTORY_POINTS_{UNITY_TOWER_PROVINCE}:(?:\d+)?\s*"([^"]*)"\s*$',
                localisation,
            ),
            [UNITY_TOWER_NAME],
        )

    def test_theatre_victory_point_validation_passes(self) -> None:
        validator.validate_states()
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

    def test_phase_six_immediately_forms_wrk_from_every_winner(self) -> None:
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
