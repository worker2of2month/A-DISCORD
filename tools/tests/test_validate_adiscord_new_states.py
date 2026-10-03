from __future__ import annotations

import re
import shutil
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

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


EXPECTED_DIRTY_REPUBLIC_POPULATION = {
    49: 650_000,
    51: 380_000,
    125: 120_000,
    152: 650_000,
    153: 300_000,
    154: 250_000,
    155: 300_000,
    165: 140_000,
    166: 140_000,
    167: 200_000,
    168: 160_000,
    169: 650_000,
    171: 200_000,
    172: 140_000,
    173: 650_000,
    176: 220_000,
    177: 650_000,
    178: 140_000,
    180: 140_000,
    181: 650_000,
    182: 170_000,
    183: 140_000,
    184: 170_000,
    185: 110_000,
    187: 200_000,
    188: 170_000,
    189: 200_000,
    190: 170_000,
    191: 220_000,
    192: 170_000,
    193: 250_000,
    203: 140_000,
    204: 110_000,
    205: 140_000,
    206: 110_000,
    207: 140_000,
    208: 140_000,
    209: 140_000,
    210: 170_000,
    211: 200_000,
    212: 170_000,
    213: 250_000,
    214: 110_000,
    215: 170_000,
    216: 140_000,
    217: 170_000,
    219: 170_000,
    220: 200_000,
    221: 140_000,
    222: 200_000,
    224: 220_000,
}


def _without_population(source: str) -> str:
    return re.sub(
        r"(?m)^(\s*manpower\s*=\s*)\d+(\s*)$",
        r"\1<population>\2",
        source,
    )


class ShahrabadPopulationTests(unittest.TestCase):
    def test_all_starting_states_sum_to_twenty_million_and_plan_is_current(self):
        actual = {}
        for path in (builder.ROOT / "history/states").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            if re.search(r"\bowner\s*=\s*SHL\b", source):
                state_id = int(re.search(r"\bid\s*=\s*(\d+)", source)[1])
                actual[state_id] = int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1])
        self.assertEqual(actual, builder.SHL_POPULATION)
        self.assertEqual(sum(actual.values()), 20_000_000)
        self.assertEqual(actual[699], 4_000_000)
        for path, expected in builder.shahrabad_population_plan().items():
            self.assertEqual(path.read_bytes(), expected)

    def test_other_generation_modes_preserve_demographic_profile(self):
        for state_id in range(287, 297):
            self.assertEqual(builder.population(state_id, "SHL"), builder.SHL_POPULATION[state_id])
        for plan in (builder.coastal_city_state_plan(), builder.southern_settlement_plan()):
            for path, payload in plan.items():
                if path.parent.name != "states":
                    continue
                source = payload.decode("utf-8-sig")
                match = re.search(r"\bid\s*=\s*(\d+)", source)
                if match is not None and int(match[1]) in builder.SHL_POPULATION:
                    state_id = int(match[1])
                    self.assertEqual(int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1]), builder.SHL_POPULATION[state_id])


class DirtyRepublicPopulationTests(unittest.TestCase):
    def test_profile_population_and_non_population_metadata_are_exact(self):
        self.assertEqual(
            set(builder.DIRTY_REPUBLIC_STATE_PROFILES),
            set(EXPECTED_DIRTY_REPUBLIC_POPULATION),
        )
        self.assertEqual(sum(EXPECTED_DIRTY_REPUBLIC_POPULATION.values()), 11_930_000)
        self.assertEqual(
            builder.DIRTY_REPUBLIC_STATE_PROFILES[125]["population"], 120_000
        )
        self.assertEqual(
            builder.DIRTY_REPUBLIC_STATE_PROFILES[168]["population"], 160_000
        )
        for state_id, expected_population in EXPECTED_DIRTY_REPUBLIC_POPULATION.items():
            with self.subTest(state=state_id):
                profile = builder.DIRTY_REPUBLIC_STATE_PROFILES[state_id]
                source = builder.state_path(state_id).read_text(encoding="utf-8-sig")
                self.assertEqual(profile["population"], expected_population)
                self.assertEqual(
                    int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1]),
                    expected_population,
                )
                self.assertEqual(
                    re.search(r"\bstate_category\s*=\s*(\w+)", source)[1],
                    profile["category"],
                )
                self.assertEqual(
                    float(re.search(r"\blocal_supplies\s*=\s*([\d.]+)", source)[1]),
                    profile["supplies"],
                )
                for field, building in (("infrastructure", "infrastructure"),
                                        ("civilian", "industrial_complex"),
                                        ("military", "arms_factory"),
                                        ("air_base", "air_base")):
                    expected_level = int(profile.get(field, 0))
                    levels = [
                        int(value)
                        for value in re.findall(
                            rf"(?m)^\s*{building}\s*=\s*(\d+)\s*$", source
                        )
                    ]
                    self.assertEqual(sum(levels), expected_level, field)
                self.assertEqual(
                    ("impassable = yes" in source),
                    state_id in builder.IMPASSABLE_LEGACY_STATE_IDS,
                )

    def test_profile_regeneration_changes_only_population(self):
        state_ids = set(EXPECTED_DIRTY_REPUBLIC_POPULATION)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            originals = {}
            for state_id in state_ids:
                source_path = builder.state_path(state_id)
                destination = target / source_path.name
                shutil.copy2(source_path, destination)
                originals[state_id] = source_path.read_text(encoding="utf-8-sig")
            with patch.object(builder, "STATE_DIR", target):
                builder.apply_legacy_state_profiles(state_ids)
            for state_id, original in originals.items():
                generated = (target / builder.state_path(state_id).name).read_text(
                    encoding="utf-8-sig"
                )
                self.assertEqual(
                    _without_population(generated), _without_population(original)
                )


class VorkerlandNewStateOutcomeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        validator.ERRORS.clear()

    def tearDown(self) -> None:
        validator.ERRORS.clear()

    def test_expansion_and_reunification_contract_passes(self) -> None:
        validator.validate_vorkerland_expansion()
        self.assertEqual(validator.ERRORS, [])

    def test_legacy_scalar_rewrite_removes_duplicate_declarations(self) -> None:
        source = (
            "state={\n\tlocal_supplies = 6.0\n\tlocal_supplies=10\n\thistory = { }\n}\n"
        )
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

    def test_disconnected_urban_settlements_receive_victory_points(self) -> None:
        expected = {
            310: ((16588, 1),),
            318: ((16642, 3), (16624, 1)),
        }
        for state_id, expected_vps in expected.items():
            with self.subTest(state=state_id):
                self.assertEqual(
                    VORKERLAND_THEATRE_VICTORY_POINTS.get(state_id),
                    expected_vps,
                )
                state = builder.state_path(state_id).read_text(encoding="utf-8-sig")
                actual_vps = tuple(
                    (int(province_id), int(value))
                    for province_id, value in re.findall(
                        r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}",
                        state,
                    )
                )
                self.assertEqual(actual_vps, expected_vps)

    def test_every_settlement_state_has_a_victory_point(self) -> None:
        terrain: dict[int, str] = {}
        kind: dict[int, str] = {}
        for line in (
            (builder.ROOT / "map/definition.csv")
            .read_text(encoding="utf-8-sig")
            .splitlines()
        ):
            fields = line.split(";")
            if len(fields) > 6 and fields[0].isdigit():
                terrain[int(fields[0])] = fields[6]
                kind[int(fields[0])] = fields[4]
        offenders = {}
        for path in sorted((builder.ROOT / "history/states").glob("*.txt*")):
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            match = re.search(r"provinces\s*=\s*\{([^}]*)\}", source, re.DOTALL)
            if match is None or "victory_points" in source:
                continue
            settlements = sorted(
                province_id
                for province_id in map(int, re.findall(r"\d+", match.group(1)))
                if terrain.get(province_id) in validator.SETTLEMENT_TERRAINS
                and kind.get(province_id) == "land"
            )
            if settlements:
                offenders[path.name] = settlements
        self.assertEqual(offenders, {})

    def test_settlement_cluster_victory_points_are_minor_urban_markers(self) -> None:
        expected = {
            73: ((16703, 1),),
            144: ((16694, 1),),
            145: ((16691, 3),),
            194: ((16697, 3),),
            199: ((16690, 3), (16696, 1), (16704, 1)),
        }
        self.assertEqual(builder.SETTLEMENT_CLUSTER_VICTORY_POINTS, expected)
        self.assertEqual(builder.SETTLEMENT_CLUSTER_CENTRES, {329: (16524, 1)})
        localisation = (
            builder.ROOT / "localisation/russian/victory_points_l_russian.yml"
        ).read_text(encoding="utf-8-sig")
        for state_id, points in expected.items():
            with self.subTest(state=state_id):
                state = builder.state_path(state_id).read_text(encoding="utf-8-sig")
                actual = {
                    int(province_id): int(value)
                    for province_id, value in re.findall(
                        r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", state
                    )
                }
                for province_id, value in points:
                    self.assertEqual(actual.get(province_id), value)
                    self.assertEqual(
                        len(
                            re.findall(
                                rf'(?m)^\s*VICTORY_POINTS_{province_id}:\s*"[^"]+"',
                                localisation,
                            )
                        ),
                        1,
                    )

    def test_ivanland_manifest_victory_points_are_approved_settlements(self) -> None:
        manifest_provinces = {
            province_id
            for points in builder.IVANLAND_OVERHAUL_VICTORY_POINTS.values()
            for province_id, _value in points
        }
        self.assertTrue(
            manifest_provinces <= validator.APPROVED_NON_URBAN_SETTLEMENT_VPS
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
        self.assertEqual(
            builder.replace_history_victory_points(updated, expected), updated
        )

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
        self.assertEqual(VORKERLAND_THEATRE_PACKAGE_TOTALS["WKR"], 62)

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
            validator.ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
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
        for forbidden in (
            "transfer_state",
            "annex_country",
            "puppet =",
            "set_autonomy",
        ):
            self.assertNotIn(forbidden, worker_map)

        phase_effects = validator.text(
            validator.ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        )
        formation = validator.block(
            phase_effects, "ADISCORD_vorkerland_form_wrk_from_wkr"
        )
        self.assertIn("change_tag_from = WKR", formation)
        self.assertIn("ADISCORD_vorkerland_finalize_wrk_formation = yes", formation)

    def test_phase_six_immediately_forms_wrk_from_every_winner(self) -> None:
        phase_events = validator.text(
            validator.ROOT / "events/ADISCORD_vorkerland_events.txt"
        )
        phase_six = validator.event_block(phase_events, "ADISCORD_vorkerland_phase.6")
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


class NorthernStartingStateContracts(unittest.TestCase):
    def setUp(self) -> None:
        from tools.validators import validate_adiscord_core_state_balance as core

        self.core = core
        core.ERRORS.clear()

    def tearDown(self) -> None:
        self.core.ERRORS.clear()

    def test_campaign_states_match_population_industry_and_geography_contract(
        self,
    ) -> None:
        self.core.validate()
        self.assertEqual(self.core.ERRORS, [])

    def test_placeholder_population_and_unapproved_settlement_values_are_rejected(
        self,
    ) -> None:
        from unittest.mock import patch

        original = self.core.read_text

        def broken_state(path):
            text = original(path)
            if path.name == "14-Flaem-Prana.txt":
                text = re.sub(r"(manpower\s*=\s*)\d+", r"\g<1>1253", text)
                text = re.sub(
                    r"victory_points\s*=\s*\{\s*75\s+\d+\s*\}",
                    "victory_points = { 75 99 }",
                    text,
                )
            return text

        with patch.object(self.core, "read_text", side_effect=broken_state):
            self.core.validate()
        self.assertTrue(
            any("state 14: expected manpower" in error for error in self.core.ERRORS)
        )
        self.assertTrue(
            any("settlement VP 75 must equal 5" in error for error in self.core.ERRORS)
        )

    def test_offshore_lighthouse_does_not_become_a_campaign_victory_point(self) -> None:
        from unittest.mock import patch

        original = self.core.read_text

        def island_objective(path):
            text = original(path)
            if path.name == "303-303.txt":
                text = re.sub(
                    r"(owner\s*=\s*TFF)", r"\1\n\t\tvictory_points = { 3261 1 }", text
                )
            return text

        with patch.object(self.core, "read_text", side_effect=island_objective):
            self.core.validate()
        self.assertTrue(
            any(
                "northern state 303: expected exact campaign VPs ()" in error
                for error in self.core.ERRORS
            )
        )


class NudgeMetadataTests(unittest.TestCase):
    def test_shell_recovery_preserves_membership_and_economy(self):
        for state_id in (241, 282, 290, 688, 689, 690):
            with self.subTest(state=state_id), tempfile.TemporaryDirectory() as directory:
                original_path = builder.state_path(state_id)
                original = original_path.read_text(encoding="utf-8")
                opening, closing = builder.named_block(original, "history")
                start = original.rfind("history", 0, opening)
                shell = original[:start] + original[closing + 1:]
                target = Path(directory) / original_path.name
                target.write_text(shell, encoding="utf-8")
                with patch.object(builder, "STATE_DIR", Path(directory)):
                    planned = builder.state_metadata_plan({state_id})[target]
                    self.assertEqual(planned.decode("utf-8"), original)
                    target.write_bytes(planned)
                    self.assertEqual(builder.state_metadata_plan({state_id})[target], planned)

    def test_metadata_rejects_manifest_that_would_change_new_borders(self):
        path = builder.state_path(241)
        original = path.read_bytes()
        with patch.dict(builder.EXTRA_PROVINCES_BY_STATE, {241: (99999,)}):
            with self.assertRaisesRegex(RuntimeError, "would change province membership"):
                builder.state_metadata_plan({241})
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
