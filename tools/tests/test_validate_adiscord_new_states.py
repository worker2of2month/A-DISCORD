from __future__ import annotations

import re
import shutil
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.builders import build_adiscord_new_states as builder
from tools.lib.adiscord_planned_geography import PlannedGeography, PlannedProvince, planned_geography
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
    merge_planned_victory_points,
    package_total_errors,
)
from tools.validators import validate_adiscord_new_states as validator
from tools.tests.test_adiscord_shl_furnaces import block, focus_definition, shared_definitions, walk_entries


EXPECTED_DIRTY_REPUBLIC_POPULATION = {
    49: 650_000,
    51: 140_000,
    710: 70_000,
    711: 120_000,
    712: 130_000,
    125: 1,
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


class ReactorResourceTests(unittest.TestCase):
    def test_resource_generation_is_scoped_and_idempotent(self):
        self.assertTrue(callable(getattr(builder, "update_reactor_resources", None)))
        state_ids = {176, 177, 187, 188, 189, 192}
        with tempfile.TemporaryDirectory() as temporary:
            state_dir = Path(temporary)
            original = {}
            for state_id in state_ids | {125}:
                source = builder.state_path(state_id).read_text(encoding="utf-8-sig")
                source = re.sub(r"\s*resources\s*=\s*\{[^}]*\}", "", source)
                path = state_dir / f"{state_id}-fixture.txt"
                path.write_text(source, encoding="utf-8", newline="\n")
                original[path] = path.read_bytes()
            with patch.object(builder, "STATE_DIR", state_dir):
                self.assertEqual(builder.update_reactor_resources(False), 1)
                self.assertEqual({p: p.read_bytes() for p in original}, original)
                self.assertEqual(builder.update_reactor_resources(True), 0)
                generated = {p: p.read_bytes() for p in original}
                self.assertEqual(builder.update_reactor_resources(False), 0)
                self.assertEqual(builder.update_reactor_resources(True), 0)
                self.assertEqual({p: p.read_bytes() for p in original}, generated)
            for path, source in original.items():
                actual = path.read_text(encoding="utf-8")
                without_resources = re.sub(r"\s*resources\s*=\s*\{[^}]*\}", "", actual)
                self.assertEqual(without_resources, source.decode("utf-8"))
                if path.name.startswith("125-"):
                    self.assertEqual(path.read_bytes(), source)
                else:
                    resources = re.search(r"resources\s*=\s*\{([^}]*)\}", actual)[1]
                    self.assertNotRegex(resources, r"\b(?:oil|rubber|coal)\s*=")


class ShahrabadPopulationTests(unittest.TestCase):
    def test_all_starting_states_sum_to_thirty_million_and_plan_is_current(self):
        actual = {}
        for path in (builder.ROOT / "history/states").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            if re.search(r"\bowner\s*=\s*SHL\b", source):
                state_id = int(re.search(r"\bid\s*=\s*(\d+)", source)[1])
                actual[state_id] = int(re.search(r"\bmanpower\s*=\s*(\d+)", source)[1])
        self.assertEqual(actual, builder.SHL_POPULATION)
        self.assertEqual(sum(actual.values()), 30_000_000)
        self.assertEqual(actual[699], 6_000_000)
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


class ShahrabadSplitTests(unittest.TestCase):
    """The four hinterland states conserve their parents' people, deposits and borders."""

    ORIGINAL_POPULATION = {288: 3_600_000, 289: 1_650_000, 291: 2_400_000, 295: 2_250_000}
    ORIGINAL_RESOURCES = {
        288: {},
        289: {"tungsten": 6},
        291: {"steel": 16, "chromium": 6},
        295: {"chromium": 4},
    }
    ORIGINAL_CIVILIAN = {288: 2, 289: 0, 291: 1, 295: 0}
    # Furnace cities (and their painted sectors) that the scripts address through
    # the parent state id, so they must never move to a child.
    FURNACE_PROVINCES = {288: {16738, 16790, 16791, 16792, 834}, 291: {7825}}

    @staticmethod
    def file_provinces(state_id: int) -> set[int]:
        return set(builder.state_file_provinces(builder.state_path(state_id)))

    def test_children_partition_their_parents_exactly(self):
        for parent, (child, original, carved) in builder.SHL_SPLIT_FAMILIES.items():
            self.assertTrue(set(carved) < set(original))
            self.assertEqual(self.file_provinces(parent) | self.file_provinces(child), set(original))
            self.assertTrue(self.file_provinces(parent).isdisjoint(self.file_provinces(child)))
            self.assertEqual(self.file_provinces(child), set(carved))
            self.assertEqual(builder.state_path(child).name, builder.SHL_SPLIT_FILENAMES[child])
            self.assertTrue(self.FURNACE_PROVINCES.get(parent, set()) <= self.file_provinces(parent))
            self.assertIn(child, builder.SHL_STATES)
            self.assertEqual(builder.STARTING_OWNERS[child], "SHL")
            self.assertIn(child, builder.GENERATED_STATE_NAMES)
            self.assertIn(child, builder.REGIONAL_SETTLEMENTS)

    def test_population_industry_and_deposits_are_conserved(self):
        for parent, (child, _original, _carved) in builder.SHL_SPLIT_FAMILIES.items():
            self.assertEqual(
                builder.SHL_POPULATION[parent] + builder.SHL_POPULATION[child],
                self.ORIGINAL_POPULATION[parent],
            )
            combined: dict[str, int] = {}
            for state_id in (parent, child):
                for resource, amount in builder.SHL_RESOURCES.get(state_id, {}).items():
                    combined[resource] = combined.get(resource, 0) + amount
            self.assertEqual(combined, self.ORIGINAL_RESOURCES[parent])
            civilian = sum(
                builder.SHL_INDUSTRY.get(state_id, {}).get("industrial_complex", 0)
                for state_id in (parent, child)
            )
            self.assertEqual(civilian, self.ORIGINAL_CIVILIAN[parent])
            self.assertEqual(builder.SHL_INDUSTRY.get(child, {}).get("arms_factory", 0), 0)
            self.assertEqual(builder.category(child), "rural")
        self.assertEqual(sum(builder.SHL_POPULATION.values()), 30_000_000)
        self.assertEqual(sum(sum(deposit.values()) for deposit in builder.SHL_RESOURCES.values()), 54)

    def test_every_shahrabad_state_has_a_named_town_and_the_plan_is_current(self):
        definitions = {
            int(row[0]): row[4]
            for line in (builder.ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines()
            if len(row := line.split(";")) > 4 and row[0].isdigit()
        }
        districts = {builder.SOUTHERN_CAPITAL_DISTRICTS[294][0]}
        russian = (builder.ROOT / "localisation/russian/victory_points_l_russian.yml").read_text(encoding="utf-8-sig")
        english = (builder.ROOT / "localisation/english/victory_points_l_english.yml").read_text(encoding="utf-8-sig")
        for state_id in (*builder.SHL_STATES, 699, *districts):
            source = builder.state_path(state_id).read_text(encoding="utf-8-sig")
            points = re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", source)
            self.assertTrue(points, f"state {state_id} has no victory point")
            provinces = builder.state_file_provinces(builder.state_path(state_id))
            if len(provinces) >= 11:
                self.assertGreaterEqual(len(points), 2, f"state {state_id} needs a second settlement")
            for province, value, name in builder.REGIONAL_SETTLEMENTS.get(state_id, ()):
                self.assertIn(province, provinces)
                self.assertEqual(definitions[province], "land")
                self.assertIn((str(province), str(value)), points)
                self.assertRegex(russian, rf'(?m)^\s*VICTORY_POINTS_{province}:\s*"{re.escape(name)}"')
                self.assertRegex(english, rf'(?m)^\s*VICTORY_POINTS_{province}:\s*".+"')
        self.assertEqual(builder.REGIONAL_SETTLEMENTS[730][0][1], 2)
        for path, expected in builder.shahrabad_split_plan().items():
            self.assertEqual(path.read_bytes(), expected, str(path))
        for path, expected in builder.shahrabad_population_plan().items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def test_split_rejects_unreviewed_province_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            for state_id in builder.SHL_STATES:
                shutil.copy(builder.state_path(state_id), state_dir / builder.state_path(state_id).name)
            shutil.copy(builder.state_path(707), state_dir / builder.state_path(707).name)
            drifted = state_dir / builder.state_path(289).name
            drifted.write_text(
                builder.replace_state_provinces(
                    drifted.read_text(encoding="utf-8"), (*builder.SHL_LORAN_SANDS_PROVINCES, 1149)
                ),
                encoding="utf-8",
            )
            with patch.object(builder, "STATE_DIR", state_dir):
                with self.assertRaisesRegex(RuntimeError, "state 289: Shahrabad split manifest drifted"):
                    builder.shahrabad_split_plan()


class DirtyRepublicPopulationTests(unittest.TestCase):
    def test_profile_population_and_non_population_metadata_are_exact(self):
        self.assertEqual(
            set(builder.DIRTY_REPUBLIC_STATE_PROFILES),
            set(EXPECTED_DIRTY_REPUBLIC_POPULATION),
        )
        self.assertEqual(sum(EXPECTED_DIRTY_REPUBLIC_POPULATION.values()), 11_890_001)
        self.assertEqual(
            builder.DIRTY_REPUBLIC_STATE_PROFILES[125]["population"], 1
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

    def test_nden_has_exact_theatre_victory_points(self) -> None:
        # The town of Nordtal takes one point of the Nden package from 5090.
        self.assertEqual(
            VORKERLAND_THEATRE_VICTORY_POINTS[27],
            ((16614, 3), (5090, 2), (6850, 1)),
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
            318: ((16642, 2), (16624, 1), (16603, 1)),
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
            199: ((16690, 3), (16696, 1)),
            # Dry Klyuch is the centre of the half cut from 199.
            738: ((16704, 3),),
        }
        self.assertEqual(builder.SETTLEMENT_CLUSTER_VICTORY_POINTS, expected)
        self.assertIn((16697, 3), VORKERLAND_THEATRE_VICTORY_POINTS[325])
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

    def test_western_war_theatre_settlements_are_named_objectives(self) -> None:
        corridor_states = (71, 90, 91, 93, 94, 194, 195, 196, 322, 328)
        settlements = {
            **{
                state_id: builder.REGIONAL_SETTLEMENTS[state_id]
                for state_id in corridor_states
            },
            **builder.IVANLAND_RURAL_SETTLEMENTS,
        }
        # A rural marker never takes a carved city or its parent province.
        carved = set(builder.IVANLAND_CITY_PROVINCES) | set(
            builder.IVANLAND_CITY_PROVINCES.values()
        )
        localisation = {
            language: (
                builder.ROOT / f"localisation/{language}/victory_points_l_{language}.yml"
            ).read_text(encoding="utf-8-sig")
            for language in ("russian", "english")
        }
        for state_id, points in settlements.items():
            with self.subTest(state=state_id):
                path = builder.state_path(state_id)
                state = path.read_text(encoding="utf-8-sig")
                provinces = builder.state_file_provinces(path)
                actual = dict(
                    re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", state)
                )
                for province, value, name in points:
                    self.assertIn(province, provinces)
                    self.assertNotIn(province, carved)
                    self.assertEqual(actual.get(str(province)), str(value))
                    self.assertRegex(
                        localisation["russian"],
                        rf'(?m)^\s*VICTORY_POINTS_{province}:\s*"{re.escape(name)}"',
                    )
                    self.assertRegex(
                        localisation["english"],
                        rf'(?m)^\s*VICTORY_POINTS_{province}:\s*".+"',
                    )
        # The Itoran mandates and the corridor successors keep their capitals.
        for state_id, province in ((90, 5135), (91, 4007), (194, 2339), (195, 8032), (196, 7129)):
            self.assertEqual(builder.REGIONAL_SETTLEMENTS[state_id][0][0], province)
        # Rural markers follow the city points; planned Stage 2 towns follow them.
        for state_id, points in builder.IVANLAND_RURAL_SETTLEMENTS.items():
            overhaul = builder.IVANLAND_OVERHAUL_VICTORY_POINTS[state_id]
            planned = len(builder.IVANLAND_PLANNED_SETTLEMENTS.get(state_id, ()))
            self.assertEqual(
                overhaul[len(overhaul) - planned - len(points):len(overhaul) - planned],
                tuple((province, value) for province, value, _name in points),
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

    def test_generated_capitals_reject_missing_and_incorrect_victory_points(self):
        original = validator.text
        for state_id, province, value in ((69, 16893, 25), (47, 3129, 10), (593, 915, 10)):
            path = builder.state_path(state_id)
            source = original(path)
            pattern = rf"victory_points\s*=\s*\{{\s*{province}\s+{value}\s*\}}"
            for replacement in ("", f"victory_points = {{ {province} 99 }}"):
                mutated, count = re.subn(pattern, replacement, source)
                self.assertEqual(count, 1)
                validator.ERRORS.clear()
                with self.subTest(state=state_id, replacement=replacement), patch.object(
                    validator, "text", side_effect=lambda requested: mutated if requested == path else original(requested)
                ):
                    validator.validate_states()
                    self.assertTrue(any(
                        error.startswith(f"state {state_id}: expected exact generated VPs")
                        for error in validator.ERRORS
                    ))

    def test_worker_outcome_marks_wartime_wkr_before_it_unifies_vorkerland(self) -> None:
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
        # WKR keeps its own country: it takes over the nation target and the
        # delayed settlement annexes only the defeated claimants.
        unification = validator.block(
            phase_effects, "ADISCORD_vorkerland_unify_under_wkr"
        )
        self.assertRegex(
            unification,
            r"\A\s*clear_global_event_target = ADISCORD_vorkerland_nation\s+"
            r"save_global_event_target_as = ADISCORD_vorkerland_nation\b",
        )
        self.assertNotIn("change_tag_from", unification)
        self.assertNotIn("annex_country", unification)
        self.assertTrue(
            unification.rstrip().endswith(
                "country_event = { id = ADISCORD_vorkerland_phase.7 hours = 1 }"
            )
        )
        settlement = validator.block(
            phase_effects, "ADISCORD_vorkerland_settle_unification_under_wkr"
        )
        self.assertNotIn("change_tag_from", settlement)
        self.assertEqual(
            sorted(re.findall(r"annex_country = \{ target = (\w+)", settlement)),
            ["TVA", "VAD"],
        )
        self.assertIn("ADISCORD_vorkerland_finalize_unified_territory = yes", settlement)

    def test_phase_six_unifies_vorkerland_in_the_scope_of_every_winner(self) -> None:
        phase_events = validator.text(
            validator.ROOT / "events/ADISCORD_vorkerland_events.txt"
        )
        phase_six = validator.event_block(phase_events, "ADISCORD_vorkerland_phase.6")
        for tag, effect in (
            ("WKR", "ADISCORD_vorkerland_unify_under_wkr"),
            ("VAD", "ADISCORD_vorkerland_unify_under_vad"),
            ("TVA", "ADISCORD_vorkerland_unify_under_tva"),
        ):
            with self.subTest(tag=tag):
                self.assertEqual(
                    re.findall(
                        rf"(\S+)\s*=\s*\{{\s*{re.escape(effect)}\s*=\s*yes\s*\}}",
                        phase_six,
                    ),
                    [tag],
                )

    def test_unification_contract_rejects_a_handoff_into_wrk(self) -> None:
        effects_path = (
            validator.ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        )
        events_path = validator.ROOT / "events/ADISCORD_vorkerland_events.txt"
        queue = "country_event = { id = ADISCORD_vorkerland_phase.7 hours = 1 }"
        rebinding = "save_global_event_target_as = ADISCORD_vorkerland_nation"
        cases = (
            (
                effects_path,
                "ADISCORD_vorkerland_unify_under_vad = {",
                [(queue, f"{queue}\n\tchange_tag_from = VAD")],
                (
                    "ADISCORD_vorkerland_unify_under_vad: VAD must keep its own tag",
                    "ADISCORD_vorkerland_unify_under_vad must end by queueing the "
                    "phase.7 settlement",
                ),
            ),
            (
                effects_path,
                "ADISCORD_vorkerland_unify_under_tva = {",
                [(f"\t{rebinding}\n", "")],
                (
                    "ADISCORD_vorkerland_unify_under_tva: must open by rebinding the "
                    "nation target to TVA",
                ),
            ),
            (
                effects_path,
                "ADISCORD_vorkerland_settle_unification_under_wkr = {",
                [
                    (
                        "annex_country = { target = VAD transfer_troops = yes }",
                        "annex_country = { target = WKR transfer_troops = yes }",
                    )
                ],
                (
                    "ADISCORD_vorkerland_settle_unification_under_wkr: must not annex "
                    "the winner WKR",
                ),
            ),
            (
                events_path,
                "\tid = ADISCORD_vorkerland_phase.6\n",
                [
                    (
                        "TVA = {\n\t\t\t\tADISCORD_vorkerland_unify_under_tva = yes",
                        "WRK = {\n\t\t\t\tADISCORD_vorkerland_unify_under_tva = yes",
                    )
                ],
                ("phase.6 does not unify Vorkerland in the scope of surviving TVA",),
            ),
        )
        read_source = validator.text
        for path, anchor, replacements, expected in cases:
            # The anchor opens the block under test; each replacement applies
            # to its first occurrence after that point.
            head, separator, tail = read_source(path).partition(anchor)
            self.assertTrue(separator, anchor)
            for old, new in replacements:
                self.assertIn(old, tail)
                tail = tail.replace(old, new, 1)
            mutated = head + separator + tail

            def served(requested, path=path, mutated=mutated):
                return mutated if requested == path else read_source(requested)

            validator.ERRORS.clear()
            with self.subTest(expected=expected[0]), patch.object(
                validator, "text", side_effect=served
            ):
                validator.validate_vorkerland_expansion()
                for diagnostic in expected:
                    self.assertIn(diagnostic, validator.ERRORS)


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

    def test_updated_airfields_and_dockyards_remain_required(self):
        original = self.core.read_text
        for state_id, building, value in ((14, "air_base", 2), (30, "dockyard", 3), (48, "dockyard", 2)):
            path = builder.state_path(state_id)
            source = original(path)
            mutated, count = re.subn(
                rf"(?m)^(\s*{building}\s*=\s*){value}\s*$",
                r"\g<1>0",
                source,
            )
            self.assertEqual(count, 1)
            self.core.ERRORS.clear()
            with self.subTest(state=state_id, building=building), patch.object(
                self.core, "read_text", side_effect=lambda requested: mutated if requested == path else original(requested)
            ):
                self.core.validate()
                self.assertTrue(any(
                    error.startswith(f"state {state_id}: wrong direct buildings")
                    for error in self.core.ERRORS
                ))

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
    def test_grey_belt_shell_recovery_keeps_new_khan_border(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "49-PLACEHOLDER.txt"
            target.write_text(
                'state={\n\tid=49\n\tname="STATE_49"\n\tprovinces={ 16546 }\n}\n',
                encoding="utf-8",
            )
            with patch.object(builder, "STATE_DIR", Path(directory)):
                planned = builder.state_metadata_plan({49})[target]
                text = planned.decode("utf-8")
                self.assertIn("owner = EXZ", text)
                self.assertIn("industrial_complex = 2", text)
                self.assertIn("arms_factory = 1", text)
                self.assertIn("steel = 4", text)
                self.assertIn("victory_points = { 16546 5 }", text)
                self.assertNotIn("16639", text)
                target.write_bytes(planned)
                self.assertEqual(builder.state_metadata_plan({49})[target], planned)

    def test_shell_recovery_preserves_membership_and_economy(self):
        for state_id in (241, 282, 290, 688, 689, 690, 719, 720, 721, 722):
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


class MazarBorderTests(unittest.TestCase):
    SHL_SCRIPTS = (
        "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt",
        "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt",
        "common/decisions/ADISCORD_SHL_decisions.txt",
        "events/ADISCORD_SHL_events.txt",
        "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt",
    )

    def test_veir_holds_the_coast_and_cistern_scripts_read_dalir(self) -> None:
        for state_id, owner in ((264, "GLP"), (273, "GLP"), (268, "MZR"), (269, "MZR")):
            self.assertEqual(builder.STARTING_OWNERS[state_id], owner)
            source = builder.state_path(state_id).read_text(encoding="utf-8-sig")
            self.assertIn(f"owner = {owner}", source)
            self.assertIn(f"add_core_of = {owner}", source)
            self.assertNotIn("add_core_of = MZR" if owner == "GLP" else "add_core_of = GLP", source)
        for relative in self.SHL_SCRIPTS:
            source = (builder.ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"(?<![\d.])273(?![\d.])", source), [], relative)


class DamirTransferTests(unittest.TestCase):
    def test_damir_starts_as_an_eflor_town_with_both_settlements(self) -> None:
        self.assertEqual(builder.STARTING_OWNERS[240], "EFL")
        self.assertNotIn(240, builder.KDR_STATES)
        source = builder.state_path(240).read_text(encoding="utf-8-sig")
        self.assertIn("owner = EFL", source)
        self.assertIn("add_core_of = EFL", source)
        self.assertNotIn("KDR", source)
        self.assertRegex(source, r"victory_points\s*=\s*\{\s*16722\s+25\s*\}")
        self.assertRegex(source, r"victory_points\s*=\s*\{\s*16743\s+10\s*\}")
        self.assertEqual(builder.REGIONAL_SETTLEMENTS[240], ((16743, 10, "Нижний Дамир"), (3483, 2, "Эсман")))
        for path, expected in builder.state_metadata_plan({240}).items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def test_kadir_road_stations_are_naret_and_ravat(self) -> None:
        stations = {"234", "242"}
        for focus, effect in (("SHL_south_great_road", "add_claim_by"),
                              ("SHL_h_road_stations", "add_building_construction")):
            reward = block(focus_definition(focus), "completion_reward")
            targets = {
                entry.key for entry in walk_entries(reward)
                if entry.key.isdigit() and any(child.key == effect for child in entry.value)
            }
            self.assertEqual(targets, stations, focus)
        name = "SHL_sell_road_stations"
        sale = shared_definitions("common/scripted_effects/ADISCORD_SHL_scripted_effects.txt", (name,))[name]
        self.assertCountEqual([entry.value for entry in walk_entries(sale) if entry.key == "transfer_state"], stations)


# Province ids that scripts, OOBs, ports and hubs address directly. A planned
# split keeps the parent id on one piece, so these never leave their states.
SECTION_7_LITERAL_PROVINCES = frozenset({
    12227, 16400, 16397, 6192, 6713, 3248,
    16428,
    16568, 4443, 8243, 11944, 10730, 11841, 2553, 5986, 18994,
    16622,
})
SECTION_7_OOB_TAGS = ("WRK", "VAD", "TVA", "IVN", "IIA", "PWR", "ROM", "TRU", "VLA", "ZAO", "SOL", "WCG", "KRM", "LMN")
FIRST_SYNTHETIC_PROVINCE = 90_000


def section_7_literals() -> frozenset[int]:
    from tools.lib.adiscord_starting_navies import STARTING_NAVIES

    ports = {STARTING_NAVIES[tag].port for tag in ("IVN", "IIA", "WRK")}
    locations = set()
    for path in sorted((builder.ROOT / "history/units").glob("*.txt")):
        if path.stem.split("_", 1)[0] in SECTION_7_OOB_TAGS and not path.stem.endswith("_air"):
            locations.update(map(int, re.findall(r"\blocation\s*=\s*(\d+)", path.read_text(encoding="utf-8-sig"))))
    return SECTION_7_LITERAL_PROVINCES | ports | locations


def rural_province(state_id: int) -> int:
    """Return a listed province of the state that holds no VP, for a synthetic split."""
    path = builder.state_path(state_id)
    victory_points = {province for province, _value in builder.history_victory_points(path.read_text(encoding="utf-8"))}
    return min(builder.state_file_provinces(path) - victory_points - section_7_literals())


class EastGeographyPlanTests(unittest.TestCase):
    """Synthetic applied plans: the narrow mode appends, names and redistributes exactly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.owned = builder.state_history_states()
        cls.temp = tempfile.TemporaryDirectory()
        cls.state_dir = Path(cls.temp.name)
        for path in builder.STATE_DIR.glob("*.txt"):
            shutil.copy(path, cls.state_dir / path.name)
        cls.eyr_town = rural_province(102)
        cls.pwr_city = rural_province(71)
        cls.ivn_city = rural_province(713)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def synthetic_data(self) -> tuple[dict, dict, frozenset[int]]:
        """Return an IVN manifest, an east geography with a `stages` list and the defined ids."""
        ivn = {
            "schema": 1,
            "stage2": {
                "first_id": FIRST_SYNTHETIC_PROVINCE,
                "provinces": [
                    {"province": FIRST_SYNTHETIC_PROVINCE, "parent": self.ivn_city, "state": 713, "kind": "remainder"},
                ],
                "cities": {str(self.ivn_city): self.ivn_city},
                "settlements": [
                    {"state": 713, "kind": "city", "parent": self.ivn_city, "value": 3,
                     "name": "Синтетический Пущанск", "name_en": "Synthetic Pushchansk"},
                ],
            },
        }
        east = {
            "schema": 1,
            "stages": [
                {
                    "first_id": FIRST_SYNTHETIC_PROVINCE + 1,
                    "provinces": [
                        {"province": FIRST_SYNTHETIC_PROVINCE + 1, "parent": self.eyr_town, "state": 102, "kind": "remainder"},
                        {"province": FIRST_SYNTHETIC_PROVINCE + 2, "parent": self.pwr_city, "state": 71, "kind": "remainder"},
                        {"province": FIRST_SYNTHETIC_PROVINCE + 3, "parent": FIRST_SYNTHETIC_PROVINCE + 2, "state": 71, "kind": "part"},
                        {"province": FIRST_SYNTHETIC_PROVINCE + 4, "parent": 16622, "state": 72, "kind": "part"},
                    ],
                    "cities": {str(self.pwr_city): self.pwr_city},
                    "towns": {str(self.eyr_town): self.eyr_town},
                },
            ],
            "regions": {
                "EYR": {
                    "states": [75, 106, 102],
                    "settlements": [
                        {"state": 102, "kind": "town", "parent": self.eyr_town, "value": 2,
                         "name": "Синтетический Йорсен", "name_en": "Synthetic Yorsen"},
                    ],
                    "vp_overrides": {"16594": 8},
                },
                "PWR": {
                    "states": [71, 72],
                    "settlements": [
                        {"state": 71, "kind": "city", "parent": self.pwr_city, "value": 4,
                         "name": "Синтетический Тракт", "name_en": "Synthetic Trakt"},
                        {"state": 72, "kind": "adopt", "province": 16622},
                    ],
                },
            },
        }
        defined = frozenset(builder.definition_land_provinces() | set(range(FIRST_SYNTHETIC_PROVINCE, FIRST_SYNTHETIC_PROVINCE + 5)))
        return ivn, east, defined

    def synthetic_plan(self) -> PlannedGeography:
        ivn, east, defined = self.synthetic_data()
        return planned_geography(ivn, east, defined).for_states(self.owned)

    def plan(self, planned: PlannedGeography, land: frozenset[int] | None = None) -> dict[Path, bytes]:
        land = land or frozenset(builder.definition_land_provinces() | {entry.province for entry in planned.provinces})
        with patch.object(builder, "STATE_DIR", self.state_dir), patch.object(
            builder, "definition_land_provinces", return_value=land
        ):
            return builder.east_geography_plan(planned)

    def state_text(self, outputs: dict[Path, bytes], state_id: int) -> str:
        with patch.object(builder, "STATE_DIR", self.state_dir):
            path = builder.state_path(state_id)
        return outputs.get(path, path.read_bytes()).decode("utf-8")

    @staticmethod
    def listed(source: str) -> list[int]:
        opening, closing = builder.named_block(source, "provinces")
        return list(map(int, re.findall(r"\d+", source[opening:closing])))

    def test_empty_plan_changes_nothing(self) -> None:
        self.assertEqual(builder.east_geography_plan(PlannedGeography()), {})
        ivn, east, defined = self.synthetic_data()
        unplanned = frozenset(defined - set(range(FIRST_SYNTHETIC_PROVINCE, FIRST_SYNTHETIC_PROVINCE + 5)))
        self.assertEqual(planned_geography(ivn, east, unplanned), PlannedGeography())
        self.assertEqual(planned_geography({}, {"schema": 1}, defined), PlannedGeography())
        if not builder.PLANNED_GEOGRAPHY.provinces:
            self.assertEqual(builder.east_geography_plan(), {})

    def test_a_partly_defined_stage_is_rejected(self) -> None:
        ivn, east, defined = self.synthetic_data()
        with self.assertRaisesRegex(RuntimeError, "East stage 1 province plan is only partly on the map"):
            planned_geography(ivn, east, defined - {FIRST_SYNTHETIC_PROVINCE + 3})

    def test_older_planned_layers_are_read_when_stages_are_absent(self) -> None:
        ivn, east, defined = self.synthetic_data()
        layered = {key: value for key, value in east.items() if key != "stages"}
        layered["planned"] = east["stages"][0]
        self.assertEqual(planned_geography(ivn, layered, defined), planned_geography(ivn, east, defined))

    def test_appended_provinces_join_their_state_exactly_once(self) -> None:
        planned = self.synthetic_plan()
        outputs = self.plan(planned)
        expected = {
            713: {FIRST_SYNTHETIC_PROVINCE},
            102: {FIRST_SYNTHETIC_PROVINCE + 1},
            71: {FIRST_SYNTHETIC_PROVINCE + 2, FIRST_SYNTHETIC_PROVINCE + 3},
            72: {FIRST_SYNTHETIC_PROVINCE + 4},
        }
        everywhere = []
        for path in self.state_dir.glob("*.txt"):
            everywhere.extend(self.listed(outputs.get(path, path.read_bytes()).decode("utf-8")))
        for state_id, children in expected.items():
            listed = self.listed(self.state_text(outputs, state_id))
            for child in children:
                self.assertEqual(listed.count(child), 1, (state_id, child))
                self.assertEqual(everywhere.count(child), 1, child)
        self.assertIn(16622, self.listed(self.state_text(outputs, 72)))

    def test_plan_is_idempotent(self) -> None:
        planned = self.synthetic_plan()
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            for path in self.state_dir.glob("*.txt"):
                shutil.copy(path, state_dir / path.name)
            land = frozenset(builder.definition_land_provinces() | {entry.province for entry in planned.provinces})
            with patch.object(builder, "STATE_DIR", state_dir), patch.object(
                builder, "definition_land_provinces", return_value=land
            ):
                first = builder.east_geography_plan(planned)
                for path, data in first.items():
                    if path.parent == state_dir:
                        path.write_bytes(data)
                second = builder.east_geography_plan(planned)
            for path, data in second.items():
                if path.parent == state_dir:
                    self.assertEqual(path.read_bytes(), data, path.name)

    def test_victory_points_follow_their_tables_and_keep_package_totals(self) -> None:
        planned = self.synthetic_plan()
        outputs = self.plan(planned)
        vps = {state_id: builder.history_victory_points(self.state_text(outputs, state_id)) for state_id in (102, 71, 713)}
        authored = dict(builder.AUTHORED_THEATRE_VICTORY_POINTS[102])
        self.assertEqual(
            vps[102],
            ((16594, 8), *((province, authored[province]) for province in (16580, 16575, 16570, 4841)), (self.eyr_town, 2)),
        )
        self.assertEqual(vps[71][-1], (self.pwr_city, 4))
        self.assertEqual(vps[713][-1], (self.ivn_city, 3))
        merged = builder.theatre_victory_points(planned)
        self.assertEqual(package_total_errors(merged), [])
        self.assertEqual(merged[UNITY_TOWER_STATE], VORKERLAND_PROTECTED_LANDMARK_VPS[UNITY_TOWER_STATE])
        localisation = next(data for path, data in outputs.items() if path.name == "victory_points_l_russian.yml")
        for settlement in planned.vp_settlements():
            self.assertIn(
                f' VICTORY_POINTS_{settlement.province}: "{settlement.name}"\n', localisation.decode("utf-8-sig")
            )

    def test_overrides_that_move_a_package_total_are_refused(self) -> None:
        ivn, east, defined = self.synthetic_data()
        east["regions"]["EYR"]["vp_overrides"] = {}
        planned = planned_geography(ivn, east, defined).for_states(self.owned)
        with self.assertRaisesRegex(RuntimeError, "Vorkerland package EYR: expected VP total 43, found 45"):
            self.plan(planned)
        with self.assertRaisesRegex(ValueError, "cannot change the Unity Tower VP"):
            merge_planned_victory_points(builder.AUTHORED_THEATRE_VICTORY_POINTS, (), {UNITY_TOWER_PROVINCE: 3})
        with self.assertRaisesRegex(ValueError, "outside the theatre"):
            merge_planned_victory_points(builder.AUTHORED_THEATRE_VICTORY_POINTS, (), {12241: 3})

    def test_carved_settlements_are_approved_urban_victory_points(self) -> None:
        self.assertLessEqual(builder.PLANNED_URBAN_SETTLEMENTS, validator.APPROVED_NON_URBAN_SETTLEMENT_VPS)
        terrains = {
            int(fields[0]): fields[6]
            for line in (builder.ROOT / "map/definition.csv").read_text(encoding="utf-8-sig").splitlines()
            if len(fields := line.split(";")) > 6 and fields[0].isdigit()
        }
        state_id, province = next(
            (state_id, province)
            for state_id in sorted(self.owned)
            if state_id not in builder.REGIONAL_SETTLEMENTS
            and state_id not in builder.NAM_ARCHIPELAGO_STATE_NAMES
            for province in sorted(builder.state_file_provinces(builder.state_path(state_id)))
            if terrains.get(province) in builder.CITY_TERRAINS
        )
        table = {state_id: ((province, 2, "Синтетический посад"),)}
        with patch.object(builder, "REGIONAL_SETTLEMENTS", table):
            with self.assertRaisesRegex(RuntimeError, f"urban VP {province}: expected at least 10 points"):
                builder.regional_settlement_plan()
            with patch.object(builder, "PLANNED_URBAN_SETTLEMENTS", frozenset({province})):
                builder.regional_settlement_plan()

    def test_a_planned_split_never_removes_a_literal_province(self) -> None:
        owners = builder.state_file_owners()
        literals = sorted(
            province
            for province in section_7_literals() - {UNITY_TOWER_PROVINCE}
            if owners.get(province) in self.owned
        )
        self.assertIn(6713, literals)
        self.assertIn(16568, literals)
        entries = [
            PlannedProvince(FIRST_SYNTHETIC_PROVINCE + index, province, owners[province], "remainder", "east", "test")
            for index, province in enumerate(literals)
        ]
        outputs = self.plan(PlannedGeography(tuple(entries)))
        for entry in entries:
            listed = self.listed(self.state_text(outputs, entry.state))
            self.assertEqual(listed.count(entry.parent), 1, entry.parent)
            self.assertEqual(listed.count(entry.province), 1, entry.province)

    def test_unity_tower_and_foreign_parents_are_refused(self) -> None:
        tower = PlannedProvince(FIRST_SYNTHETIC_PROVINCE, UNITY_TOWER_PROVINCE, UNITY_TOWER_STATE, "part", "east", "test")
        with self.assertRaisesRegex(RuntimeError, "cut from the Unity Tower province"):
            self.plan(PlannedGeography((tower,)))
        foreign = PlannedProvince(FIRST_SYNTHETIC_PROVINCE, 16622, 71, "part", "east", "test")
        with self.assertRaisesRegex(RuntimeError, "has a parent 16622 outside the state"):
            self.plan(PlannedGeography((foreign,)))
        sea = PlannedProvince(FIRST_SYNTHETIC_PROVINCE, 16622, 72, "part", "east", "test")
        with self.assertRaisesRegex(RuntimeError, "is not land"):
            self.plan(PlannedGeography((sea,)), land=builder.definition_land_provinces())

    def test_an_existing_victory_point_must_be_adopted(self) -> None:
        ivn, east, defined = self.synthetic_data()
        # Old Highway (12241) lies in the half the state split cuts from 71.
        east["regions"]["PWR"]["settlements"][0]["parent"] = 12241
        with self.assertRaisesRegex(RuntimeError, "state 734: planned city 12241 already holds an authored VP"):
            self.plan(builder.split_planned_geography(planned_geography(ivn, east, defined).for_states(self.owned)))
        with self.assertRaisesRegex(ValueError, "state 102: a planned settlement repeats a theatre VP"):
            merge_planned_victory_points(builder.AUTHORED_THEATRE_VICTORY_POINTS, ((102, 16594, 2),), {})

    def test_renderers_keep_planned_provinces(self) -> None:
        child = FIRST_SYNTHETIC_PROVINCE
        real = builder.PLANNED_STATE_PROVINCES
        planned = {**real, 306: frozenset({child}), 713: real.get(713, frozenset()) | {child + 1}}
        with patch.object(builder, "PLANNED_STATE_PROVINCES", planned):
            self.assertIn(child + 1, builder.ivanland_state_provinces(713))
            self.assertIn(child, self.listed(builder.render_state(306, builder.STARTING_OWNERS[306])))
        # The split check compares the Itoran state files with the plan applied to them.
        with patch.object(builder, "PLANNED_STATE_PROVINCES", {**real, 306: frozenset({child})}):
            builder.validate_ivanland_split_inputs()

    def test_waiting_english_names_are_promoted_once_rendered(self) -> None:
        planned = self.synthetic_plan()
        town = next(entry for entry in planned.vp_settlements() if entry.state == 102)
        key = f"VICTORY_POINTS_{town.province}"
        specification = {"entries": {}, "village_names": {town.name: town.name_en}}
        localisation = f' {key}: "{town.name}"\n'
        town_only = PlannedGeography(settlements=(town,))
        gaps = builder.promote_planned_names(specification, town_only, "", apply=True)
        self.assertEqual(len(gaps), 1)
        self.assertIn("run --apply-east-geography first", gaps[0])
        gaps = builder.promote_planned_names(specification, town_only, localisation, apply=False)
        self.assertIn("is promoted by --apply", gaps[0])
        self.assertEqual(builder.promote_planned_names(specification, town_only, localisation, apply=True), [])
        self.assertEqual(specification["entries"][key], {"russian": town.name, "english": town.name_en})


class StateSplitTests(unittest.TestCase):
    """The six state splits after the stage 3 geography."""

    def test_split_rules_conserve_totals(self) -> None:
        self.assertEqual(builder.split_amount(800_000, 0.52, 10_000), 420_000)
        self.assertEqual(builder.split_amount(190_000, 0.473, 10_000), 90_000)
        self.assertEqual(
            builder.split_factory_levels({"industrial_complex": 1, "arms_factory": 2}),
            {"industrial_complex": 1, "arms_factory": 0, "dockyard": 0},
        )
        self.assertEqual(
            builder.split_factory_levels({"industrial_complex": 2, "arms_factory": 2}),
            {"industrial_complex": 1, "arms_factory": 0, "dockyard": 0},
        )
        self.assertEqual(builder.split_factory_levels({"industrial_complex": 1})["industrial_complex"], 0)
        self.assertEqual(builder.split_factory_levels({"arms_factory": 2})["arms_factory"], 1)
        self.assertEqual(builder.split_category(380_000, 2, True, "town"), "town")
        self.assertEqual(builder.split_category(680_000, 1, False, "large_town"), "town")
        self.assertEqual(builder.split_category(800_000, 1, True, "town"), "town")
        self.assertEqual(builder.split_category(290_000, 1, False, "town"), "rural")
        for parent, child in ((73, 736), (80, 737)):
            whole = sum(builder.VORKERLAND_STATE_RESOURCES[state_id]["steel"] for state_id in (parent, child))
            self.assertEqual(whole, {73: 6, 80: 8}[parent])

    def test_profiles_split_the_whole_state(self) -> None:
        whole = {71: 800_000, 194: 850_000, 73: 1_300_000, 80: 1_350_000, 199: 750_000, 693: 190_000}
        for child, split in builder.STATE_SPLITS.items():
            parent = split["parent"]
            with self.subTest(state=child):
                profiles = builder.LEGACY_STATE_PROFILES
                self.assertEqual(profiles[parent]["population"] + profiles[child]["population"], whole[parent])
                self.assertEqual(profiles[child]["population"] % 10_000, 0)
                self.assertEqual(profiles[child]["infrastructure"], profiles[parent]["infrastructure"])
                self.assertEqual(profiles[child]["supplies"], profiles[parent]["supplies"])

    def test_provinces_follow_the_cut_and_planned_parts_their_root(self) -> None:
        self.assertEqual(builder.split_half(71, 12241), 734)
        self.assertEqual(builder.split_half(71, 16591), 71)
        self.assertEqual(builder.split_half(734, 16591), 71)
        self.assertEqual(builder.split_half(199, 12930), 199)
        self.assertEqual(builder.split_half(306, 16643), 306)
        roots = {FIRST_SYNTHETIC_PROVINCE: 258, FIRST_SYNTHETIC_PROVINCE + 1: 16591}
        with patch.object(builder, "PLANNED_ROOTS", roots):
            self.assertEqual(builder.split_half(71, FIRST_SYNTHETIC_PROVINCE), 734)
            self.assertEqual(builder.split_half(71, FIRST_SYNTHETIC_PROVINCE + 1), 71)

    def test_victory_points_follow_their_provinces(self) -> None:
        rimat_fields = {province: value for province, value, _name in builder.REGIONAL_SETTLEMENTS[734]}
        self.assertEqual(rimat_fields, {12241: 1, 258: 3})
        self.assertNotIn(12241, {province for province, _value, _name in builder.AUTHORED_REGIONAL_SETTLEMENTS[71]})
        self.assertEqual(builder.IVANLAND_OVERHAUL_VICTORY_POINTS[739], ((16695, 3),))
        self.assertNotIn(16695, dict(builder.IVANLAND_OVERHAUL_VICTORY_POINTS[693]))
        self.assertIn(739, builder.IVANLAND_ISLAND_STATES)
        self.assertIn(739, builder.IVANLAND_SPLIT_FAMILIES[128])
        for child, split in builder.STATE_SPLITS.items():
            with self.subTest(state=child):
                self.assertEqual(builder.GENERATED_STATE_NAMES[child], split["name"])
                self.assertTrue(split["filename"].startswith(f"{child}-"))

    def test_plan_cuts_each_family_into_its_two_halves(self) -> None:
        outputs = builder.state_split_plan()
        sources = {
            int(path.name.split("-", 1)[0]): data.decode("utf-8")
            for path, data in outputs.items()
            if path.suffix == ".txt"
        }
        for child, split in builder.STATE_SPLITS.items():
            parent = split["parent"]
            with self.subTest(state=child):
                halves = {state_id: validator_provinces(sources[state_id]) for state_id in (parent, child)}
                self.assertFalse(halves[parent] & halves[child])
                self.assertTrue(set(split["provinces"]) <= halves[child])
                self.assertIn(f"victory_points = {{ {split['centre']} 3 }}", sources[child])
        names = next(data for path, data in outputs.items() if path.suffix == ".yml")
        self.assertTrue(names.startswith(b"\xef\xbb\xbf"))
        for child, split in builder.STATE_SPLITS.items():
            self.assertIn(f' STATE_{child}: "{split["name"]}"'.encode("utf-8"), names)


def validator_provinces(source: str) -> set[int]:
    match = re.search(r"provinces\s*=\s*\{([^}]*)\}", source)
    return set(map(int, re.findall(r"\d+", match.group(1))))


if __name__ == "__main__":
    unittest.main()
