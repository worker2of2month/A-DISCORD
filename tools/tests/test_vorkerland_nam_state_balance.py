from __future__ import annotations

import codecs
import re
import unittest
from pathlib import Path

from tools.builders import build_adiscord_map_buildings as map_buildings
from tools.builders import build_adiscord_new_states as builder
from tools.builders import build_adiscord_strategic_regions as regions


VORKERLAND_GENERATED_STATES = set(range(306, 329)) - {326}
NAM_SVETLOGORSK_STATE_ID = 688
NAM_SVETLOGORSK_PROVINCES = {689, 3127, 4025, 8635, 9211, 10967}
NAM_RESIDUAL_CITY_STATE_ID = 689
NAM_RESIDUAL_CITY_PROVINCES = {176, 2038, 2299, 7618, 7639, 8358}
NAM_ORIGINAL_MAINLAND_PROVINCES = {
    176, 334, 461, 689, 1015, 1710, 2038, 2231, 2299, 2935,
    3127, 4025, 4287, 4321, 4912, 6099, 6961, 7324, 7618, 7639,
    8058, 8351, 8358, 8445, 8635, 8888, 9016, 9116, 9211, 9641,
    10909, 10967, 11069, 11696, 11926, 11942, 12480, 12668, 12982,
}


def state_source(state_id: int) -> str:
    return builder.state_path(state_id).read_text(encoding="utf-8-sig", errors="strict")


def scalar(source: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([^\s#]+)", source)
    if not match:
        raise AssertionError(f"missing scalar {key}")
    return match.group(1)


def building_level(source: str, building: str) -> int:
    match = re.search(rf"(?m)^\s*{re.escape(building)}\s*=\s*(\d+)\s*$", source)
    if not match:
        return 0
    return int(match.group(1))


def named_block(source: str, name: str, occurrence: int = 0) -> str:
    matches = list(re.finditer(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source))
    if len(matches) <= occurrence:
        raise AssertionError(f"missing block {name}")
    match = matches[occurrence]
    opening = source.find("{", match.start(), match.end())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"unclosed block {name}")


class VorkerlandNamStateBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.states = regions.load_states()
        province_types, colors = regions.load_province_definitions()
        physical = regions.load_province_adjacency(
            province_types, colors, include_special_adjacencies=False
        )
        complete = regions.load_province_adjacency(
            province_types, colors, include_special_adjacencies=True
        )
        cls.physical_state_adjacency = regions.build_state_adjacency(cls.states, physical)
        cls.complete_state_adjacency = regions.build_state_adjacency(cls.states, complete)

    def assert_profile_applied(self, state_id: int, profile: dict[str, object]) -> None:
        source = state_source(state_id)
        self.assertEqual(int(scalar(source, "manpower")), profile["population"])
        self.assertEqual(scalar(source, "state_category"), profile["category"])
        self.assertEqual(float(scalar(source, "local_supplies")), profile["supplies"])
        self.assertGreaterEqual(building_level(source, "infrastructure"), profile["infrastructure"])
        self.assertGreaterEqual(building_level(source, "industrial_complex"), profile.get("civilian", 0))
        self.assertGreaterEqual(building_level(source, "arms_factory"), profile.get("military", 0))

    def test_techgrad_is_a_supplied_megalopolis(self) -> None:
        source = state_source(40)
        self.assert_profile_applied(40, builder.VORKERLAND_LEGACY_PROFILES[40])
        self.assertGreaterEqual(int(scalar(source, "manpower")), 10_000_000)
        self.assertLessEqual(int(scalar(source, "manpower")), 13_000_000)
        self.assertEqual(scalar(source, "state_category"), "megalopolis")
        self.assertNotIn("impassable = yes", source)
        self.assertNotRegex(source, r"buildings_max_level_factor\s*=\s*0(?:\.0+)?\b")
        self.assertNotRegex(source, r"state_category\s*=\s*wasteland\b")

    def test_legacy_vorkerland_periphery_is_populated_and_supplied(self) -> None:
        for state_id, profile in builder.VORKERLAND_LEGACY_PROFILES.items():
            with self.subTest(state=state_id):
                self.assert_profile_applied(state_id, profile)
                source = state_source(state_id)
                self.assertGreater(int(scalar(source, "manpower")), 0)
                self.assertGreaterEqual(float(scalar(source, "local_supplies")), 1.5)
                if state_id != 40:
                    self.assertGreaterEqual(building_level(source, "infrastructure"), 2)
                    self.assertLessEqual(building_level(source, "infrastructure"), 4)

    def test_border_states_are_not_demilitarized(self) -> None:
        for state_id in (90, 91):
            with self.subTest(state=state_id):
                self.assertNotIn("set_demilitarized_zone = yes", state_source(state_id))

    def test_norvane_border_absorbs_the_pwr_wedge(self) -> None:
        self.assertNotIn(3743, self.states[71])
        self.assertIn(3743, self.states[91])
        self.assertFalse(self.states[71] & self.states[91])
        self.assertIn(91, self.physical_state_adjacency[90])

    def test_generated_vorkerland_periphery_has_explicit_profiles(self) -> None:
        self.assertTrue(VORKERLAND_GENERATED_STATES <= builder.STATE_PROFILES.keys())
        for state_id in sorted(VORKERLAND_GENERATED_STATES):
            with self.subTest(state=state_id):
                source = state_source(state_id)
                self.assertGreater(int(scalar(source, "manpower")), 0)
                self.assertGreaterEqual(float(scalar(source, "local_supplies")), 1.5)
                self.assertGreaterEqual(building_level(source, "infrastructure"), 2)
                self.assertLessEqual(building_level(source, "infrastructure"), 4)

    def test_nam_theatre_profiles_are_applied(self) -> None:
        for state_id, profile in builder.NAM_STATE_PROFILES.items():
            with self.subTest(state=state_id):
                self.assert_profile_applied(state_id, profile)
        capital = state_source(NAM_RESIDUAL_CITY_STATE_ID)
        self.assertEqual(scalar(capital, "state_category"), "town")
        self.assertGreaterEqual(float(scalar(capital, "local_supplies")), 3.5)
        self.assertEqual(
            building_level(state_source(67), "arms_factory")
            + building_level(state_source(NAM_SVETLOGORSK_STATE_ID), "arms_factory"),
            1,
        )
        self.assertEqual(building_level(capital, "arms_factory"), 2)

    def test_nam_split_keeps_a_stronghold_spawn_anchor_in_each_state(self) -> None:
        counts: dict[int, int] = {}
        for line in map_buildings.BUILDINGS_PATH.read_text(
            encoding="utf-8-sig", errors="strict"
        ).splitlines():
            fields = line.split(";")
            if len(fields) == 7 and fields[1] == "stronghold_network":
                state_id = int(fields[0])
                counts[state_id] = counts.get(state_id, 0) + 1

        for state_id in (67, NAM_SVETLOGORSK_STATE_ID, NAM_RESIDUAL_CITY_STATE_ID):
            with self.subTest(state=state_id):
                self.assertGreaterEqual(counts.get(state_id, 0), 1)

    def test_svetlogorsk_is_a_compact_internal_nam_state(self) -> None:
        svetlogorsk = NAM_SVETLOGORSK_STATE_ID
        self.assertEqual(self.states[svetlogorsk], NAM_SVETLOGORSK_PROVINCES)
        residual = NAM_RESIDUAL_CITY_STATE_ID
        self.assertEqual(self.states[residual], NAM_RESIDUAL_CITY_PROVINCES)
        self.assertEqual(
            self.states[67] | self.states[svetlogorsk] | self.states[residual],
            NAM_ORIGINAL_MAINLAND_PROVINCES,
        )
        self.assertFalse(self.states[67] & self.states[svetlogorsk])
        self.assertFalse(self.states[67] & self.states[residual])
        self.assertFalse(self.states[svetlogorsk] & self.states[residual])

        province_types, colors = regions.load_province_definitions()
        physical = regions.load_province_adjacency(
            province_types, colors, include_special_adjacencies=False
        )
        for provinces in (self.states[67], self.states[svetlogorsk], self.states[residual]):
            reached = {next(iter(provinces))}
            frontier = list(reached)
            while frontier:
                province = frontier.pop()
                for neighbour in physical[province] & provinces - reached:
                    reached.add(neighbour)
                    frontier.append(neighbour)
            self.assertEqual(reached, provinces)

        self.assertIn(67, self.physical_state_adjacency[svetlogorsk])
        self.assertIn(70, self.physical_state_adjacency[svetlogorsk])
        self.assertEqual(
            self.physical_state_adjacency[svetlogorsk] - {67, 70}, set()
        )
        self.assertEqual(self.physical_state_adjacency[residual], {67, 69})
        self.assertNotIn(residual, self.physical_state_adjacency[svetlogorsk])

    def test_svetlogorsk_split_preserves_nam_population_and_industry(self) -> None:
        mainland = state_source(67)
        svetlogorsk = state_source(NAM_SVETLOGORSK_STATE_ID)
        residual = state_source(NAM_RESIDUAL_CITY_STATE_ID)
        self.assertEqual(int(scalar(mainland, "manpower")), 430_000)
        self.assertEqual(int(scalar(svetlogorsk, "manpower")), 90_000)
        self.assertEqual(int(scalar(residual, "manpower")), 120_000)
        self.assertEqual(
            int(scalar(mainland, "manpower"))
            + int(scalar(svetlogorsk, "manpower"))
            + int(scalar(residual, "manpower")),
            640_000,
        )
        for building, expected in {
            "industrial_complex": 4,
            "arms_factory": 3,
            "air_base": 2,
            "dockyard": 1,
        }.items():
            self.assertEqual(
                building_level(mainland, building)
                + building_level(svetlogorsk, building)
                + building_level(residual, building),
                expected,
            )
        self.assertEqual(building_level(svetlogorsk, "industrial_complex"), 1)
        self.assertEqual(building_level(svetlogorsk, "arms_factory"), 1)
        self.assertEqual(building_level(svetlogorsk, "air_base"), 1)
        self.assertEqual(building_level(svetlogorsk, "dockyard"), 1)
        self.assertEqual(building_level(residual, "industrial_complex"), 1)
        self.assertEqual(building_level(residual, "arms_factory"), 2)
        self.assertEqual(building_level(residual, "air_base"), 0)
        self.assertEqual(building_level(residual, "dockyard"), 0)
        self.assertRegex(mainland, r"(?m)^\s*oil\s*=\s*144\s*$")
        self.assertRegex(mainland, r"(?m)^\s*chromium\s*=\s*13\s*$")
        self.assertNotRegex(svetlogorsk, r"(?m)^\s*(?:oil|chromium)\s*=")
        self.assertRegex(residual, r"(?m)^\s*oil\s*=\s*20\s*$")
        self.assertRegex(residual, r"(?m)^\s*chromium\s*=\s*2\s*$")
        self.assertRegex(residual, r"2038\s*=\s*\{\s*naval_base\s*=\s*1\s*\}")

    def test_residual_nam_city_has_port_supply_capital_and_localisation(self) -> None:
        source = state_source(NAM_RESIDUAL_CITY_STATE_ID)
        self.assertRegex(source, r"(?m)^\s*owner\s*=\s*NAM\s*$")
        self.assertRegex(source, r"(?m)^\s*add_core_of\s*=\s*NAM\s*$")
        self.assertEqual(scalar(source, "state_category"), "town")
        self.assertGreaterEqual(float(scalar(source, "local_supplies")), 3.5)
        self.assertRegex(source, r"victory_points\s*=\s*\{\s*2038\s+5\s*\}")
        self.assertRegex(source, r"2038\s*=\s*\{\s*naval_base\s*=\s*1\s*\}")

        country = (builder.ROOT / "history" / "countries" / "NAM - NamestnikLand.txt").read_text(
            encoding="utf-8-sig"
        )
        self.assertRegex(country, r"(?m)^\s*capital\s*=\s*689\s*$")

        vp_loc = builder.ROOT / "localisation" / "russian" / "victory_points_l_russian.yml"
        state_loc = builder.ROOT / "localisation" / "russian" / "state_names_l_russian.yml"
        self.assertIn('VICTORY_POINTS_2038: "Южная гавань"', vp_loc.read_text(encoding="utf-8-sig"))
        self.assertIn('STATE_689: "Южнобережный округ"', state_loc.read_text(encoding="utf-8-sig"))

        region = next(region for region in regions.BASE_REGIONS if region.region_id == 24)
        self.assertIn(NAM_RESIDUAL_CITY_STATE_ID, region.states)

    def test_nam_defeat_uses_total_coalition_partition_and_cleanup(self) -> None:
        effects = (
            builder.ROOT
            / "common"
            / "scripted_effects"
            / "ADISCORD_nam_resource_war_effects.txt"
        ).read_text(encoding="utf-8-sig")
        on_actions = (
            builder.ROOT
            / "common"
            / "on_actions"
            / "03_ADISCORD_nam_resource_war_on_actions.txt"
        ).read_text(encoding="utf-8-sig")
        debug_decisions = (
            builder.ROOT
            / "common"
            / "decisions"
            / "ADISCORD_scenario_debug_decisions.txt"
        ).read_text(encoding="utf-8-sig")
        news = (
            builder.ROOT / "events" / "ADISCORD_nam_resource_war_events.txt"
        ).read_text(encoding="utf-8-sig")

        terminal_sources = "\n".join((effects, on_actions, debug_decisions, news))
        for obsolete in (
            "ADISCORD_nam_resource_war_resolve_uprising_victory",
            "ADISCORD_nam_debug_resolve_uprising_victory",
            "ADISCORD_nam_resource_news.4",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, terminal_sources)

        capitulation = named_block(on_actions, "on_capitulation")
        self.assertRegex(
            capitulation,
            r"(?s)ROOT\s*=\s*\{\s*tag\s*=\s*NAM\s*\}.*?"
            r"FROM\s*=\s*\{\s*OR\s*=\s*\{\s*tag\s*=\s*EFL\s+tag\s*=\s*AZH\s+tag\s*=\s*SLF\s*\}\s*\}.*?"
            r"ADISCORD_nam_resource_war_resolve_coalition_victory\s*=\s*yes",
        )

        coalition = named_block(
            effects, "ADISCORD_nam_resource_war_resolve_coalition_victory"
        )
        efl = named_block(coalition, "EFL")
        azh = named_block(coalition, "AZH")
        self.assertEqual(
            {int(state) for state in re.findall(r"transfer_state\s*=\s*(\d+)", efl)},
            {67, 225, 228, 230, 231, 688},
        )
        self.assertEqual(
            {int(state) for state in re.findall(r"transfer_state\s*=\s*(\d+)", azh)},
            {226, 227, 229, 689},
        )
        for recipient, state_ids in {
            "EFL": {67, 225, 228, 230, 231, 688},
            "AZH": {226, 227, 229, 689},
        }.items():
            for state_id in state_ids:
                with self.subTest(recipient=recipient, state=state_id):
                    state_block = named_block(coalition, str(state_id))
                    self.assertRegex(state_block, rf"\badd_core_of\s*=\s*{recipient}\b")
                    self.assertRegex(
                        state_block,
                        rf"\bset_state_controller_to\s*=\s*{recipient}\b",
                    )
        self.assertIn(
            "688 = { remove_core_of = SLF remove_core_of = NAM add_core_of = EFL set_state_controller_to = EFL }",
            coalition,
        )
        self.assertIn(
            "689 = { remove_core_of = NAM add_core_of = AZH set_state_controller_to = AZH }",
            coalition,
        )

        debug_categories = (
            builder.ROOT
            / "common"
            / "decisions"
            / "categories"
            / "ADISCORD_scenario_debug_categories.txt"
        ).read_text(encoding="utf-8-sig")
        debug_category = named_block(debug_categories, "ADISCORD_scenario_debug_category")
        self.assertEqual(
            set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", named_block(debug_category, "allowed"))),
            {"WRK", "VAD", "TVA", "IVN", "NAM", "EFL", "AZH", "SLF"},
        )
        for decision_name in (
            "ADISCORD_nam_debug_start_resource_war",
            "ADISCORD_nam_debug_resolve_coalition_victory",
            "ADISCORD_nam_debug_resolve_nam_victory",
        ):
            with self.subTest(decision=decision_name):
                decision = named_block(debug_decisions, decision_name)
                self.assertEqual(
                    set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", named_block(decision, "allowed"))),
                    {"NAM", "EFL", "AZH", "SLF"},
                )
        self.assertIn(
            "annex_country = { target = SLF transfer_troops = no }",
            efl,
        )
        self.assertIn(
            "annex_country = { target = NAM transfer_troops = no }",
            coalition,
        )

        nam_victory = named_block(
            effects, "ADISCORD_nam_resource_war_resolve_nam_victory"
        )
        self.assertIn(
            "annex_country = { target = SLF transfer_troops = no }",
            nam_victory,
        )

    def test_svetlogorsk_has_real_port_supply_and_localisation(self) -> None:
        source = state_source(NAM_SVETLOGORSK_STATE_ID)
        self.assertRegex(source, r"(?m)^\s*owner\s*=\s*NAM\s*$")
        self.assertRegex(source, r"(?m)^\s*add_core_of\s*=\s*NAM\s*$")
        self.assertEqual(scalar(source, "state_category"), "town")
        self.assertGreaterEqual(float(scalar(source, "local_supplies")), 3.0)
        self.assertRegex(source, r"victory_points\s*=\s*\{\s*689\s+3\s*\}")
        self.assertRegex(source, r"689\s*=\s*\{\s*naval_base\s*=\s*2\s*\}")
        self.assertIn(3127, {
            province
            for line in (builder.ROOT / "map" / "railways.txt").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            for province in map(int, line.split()[2:])
        })

        vp_loc = (builder.ROOT / "localisation" / "russian" / "victory_points_l_russian.yml")
        state_loc = (builder.ROOT / "localisation" / "russian" / "state_names_l_russian.yml")
        self.assertTrue(vp_loc.read_bytes().startswith(codecs.BOM_UTF8))
        self.assertTrue(state_loc.read_bytes().startswith(codecs.BOM_UTF8))
        self.assertIn('VICTORY_POINTS_689: "Светлогорск"', vp_loc.read_text(encoding="utf-8-sig"))
        self.assertIn('STATE_688: "Светлогорский округ"', state_loc.read_text(encoding="utf-8-sig"))

        region = next(region for region in regions.BASE_REGIONS if region.region_id == 24)
        self.assertIn(NAM_SVETLOGORSK_STATE_ID, region.states)

    def test_nam_island_holdings_are_non_core_colonies(self) -> None:
        mainland = state_source(67)
        self.assertRegex(mainland, r"(?m)^\s*owner\s*=\s*NAM\s*$")
        self.assertRegex(mainland, r"(?m)^\s*add_core_of\s*=\s*NAM\s*$")

        mainland_component = {67}
        frontier = [67]
        while frontier:
            state_id = frontier.pop()
            for neighbour in self.physical_state_adjacency[state_id] - mainland_component:
                mainland_component.add(neighbour)
                frontier.append(neighbour)

        for state_id in range(225, 232):
            with self.subTest(state=state_id):
                source = state_source(state_id)
                self.assertNotIn(state_id, mainland_component)
                self.assertRegex(source, r"(?m)^\s*owner\s*=\s*NAM\s*$")
                self.assertNotRegex(source, r"(?m)^\s*add_core_of\s*=\s*NAM\s*$")
                self.assertIn("# adiscord_nam_overseas_colony = yes", source)

    def test_nam_coalition_front_can_supply_an_offensive(self) -> None:
        for state_id, profile in builder.NAM_COALITION_FRONT_PROFILES.items():
            with self.subTest(state=state_id):
                self.assert_profile_applied(state_id, profile)
                source = state_source(state_id)
                self.assertGreaterEqual(int(scalar(source, "manpower")), 180_000)
                self.assertLessEqual(int(scalar(source, "manpower")), 350_000)
                self.assertEqual(building_level(source, "infrastructure"), 3)
                self.assertGreaterEqual(float(scalar(source, "local_supplies")), 3.0)
                self.assertGreaterEqual(building_level(source, "industrial_complex"), 1)
                self.assertGreaterEqual(building_level(source, "arms_factory"), 1)
        azhar = state_source(69)
        self.assertEqual(building_level(azhar, "dockyard"), 1)
        self.assertRegex(azhar, r"493\s*=\s*\{\s*naval_base\s*=\s*1\s*\}")

    def test_initial_map_legacy_states_are_populated_and_supplied(self) -> None:
        for state_id in builder.VORKERLAND_INITIAL_MAP_LEGACY_PROFILES:
            with self.subTest(state=state_id):
                # Country-specific profiles may intentionally override a broad
                # theatre baseline (Afrela does so for states 113-114).
                profile = builder.LEGACY_STATE_PROFILES[state_id]
                self.assert_profile_applied(state_id, profile)
                source = state_source(state_id)
                self.assertGreater(int(scalar(source, "manpower")), 0)
                self.assertGreaterEqual(float(scalar(source, "local_supplies")), 1.5)
                self.assertNotIn("impassable = yes", source)
                self.assertNotRegex(source, r"state_category\s*=\s*wasteland\b")
        for state_id in sorted(builder.VORKERLAND_INITIAL_MAP_LEGACY_STATES):
            with self.subTest(initial_map_state=state_id):
                source = state_source(state_id)
                self.assertGreater(int(scalar(source, "manpower")), 0)
                self.assertGreater(float(scalar(source, "local_supplies")), 0.0)

    def test_central_sloboda_and_techlar_are_real_cities(self) -> None:
        central = state_source(104)
        techlar = state_source(105)
        self.assertEqual(scalar(central, "state_category"), "metropolis")
        self.assertGreaterEqual(int(scalar(central, "manpower")), 2_000_000)
        self.assertEqual(scalar(techlar, "state_category"), "megalopolis")
        self.assertGreaterEqual(int(scalar(techlar, "manpower")), 9_000_000)
        self.assertGreaterEqual(float(scalar(central, "local_supplies")), 6.0)
        self.assertGreaterEqual(float(scalar(techlar, "local_supplies")), 10.0)

    def test_vla_has_a_viable_two_front_homeland(self) -> None:
        source = state_source(74)
        profile = builder.VORKERLAND_LEGACY_PROFILES[74]
        self.assert_profile_applied(74, profile)
        self.assertEqual(int(scalar(source, "manpower")), 1_100_000)
        self.assertEqual(scalar(source, "state_category"), "large_town")
        self.assertGreaterEqual(float(scalar(source, "local_supplies")), 4.5)
        self.assertEqual(building_level(source, "industrial_complex"), 3)
        self.assertEqual(building_level(source, "arms_factory"), 2)
        self.assertRegex(source, r"victory_points\s*=\s*\{\s*16585\s+5\s*\}")

        # State 74 has one compact TGD edge and a broader EBA edge. It needs
        # enough troops to cover both, but remains much smaller than either bloc.
        self.assertEqual(
            {
                neighbour
                for neighbour in self.physical_state_adjacency[74]
                if neighbour in {105, 197, 311, 312, 313, 314}
            },
            {105, 197, 311, 312},
        )

    def test_distant_post_approach_is_mountain_terrain(self) -> None:
        terrain_by_province = {
            int(fields[0]): fields[6]
            for line in (builder.ROOT / "map" / "definition.csv").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(fields := line.split(";")) > 6 and fields[0].isdigit()
        }
        self.assertEqual(terrain_by_province.get(10016), "mountain")

    def test_new_city_vps_use_urban_provinces_and_bom_localisation(self) -> None:
        urban_provinces = {
            int(fields[0])
            for line in (builder.ROOT / "map" / "definition.csv").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(fields := line.split(";")) > 6
            and fields[0].isdigit()
            and fields[6] == "urban"
        }
        for state_id, points in builder.VORKERLAND_LEGACY_VICTORY_POINTS.items():
            source = state_source(state_id)
            for province_id, value in points:
                with self.subTest(state=state_id, province=province_id):
                    self.assertIn(province_id, self.states[state_id])
                    self.assertIn(province_id, urban_provinces)
                    self.assertRegex(
                        source,
                        rf"victory_points\s*=\s*\{{\s*{province_id}\s+{value}\s*\}}",
                    )
        localisation_path = (
            builder.ROOT / "localisation" / "russian" / "victory_points_l_russian.yml"
        )
        self.assertTrue(localisation_path.read_bytes().startswith(codecs.BOM_UTF8))
        localisation = localisation_path.read_text(encoding="utf-8-sig")
        for province_id, name in builder.VORKERLAND_VICTORY_POINT_NAMES.items():
            self.assertIn(f'VICTORY_POINTS_{province_id}: "{name}"', localisation)
        state_names_path = (
            builder.ROOT / "localisation" / "russian" / "state_names_l_russian.yml"
        )
        self.assertTrue(state_names_path.read_bytes().startswith(codecs.BOM_UTF8))
        state_names = state_names_path.read_text(encoding="utf-8-sig")
        for state_id, name in builder.VORKERLAND_STATE_NAMES.items():
            self.assertIn(f'STATE_{state_id}: "{name}"', state_names)

    def test_remote_central_cities_have_valid_land_connections(self) -> None:
        # The Unity Tower urban pocket remains physically connected to WRK's state 32.
        self.assertIn(32, self.physical_state_adjacency[40])
        # TGD's new state 105 is a real peripheral junction: VLA owns 74 and
        # EBA owns 311/312 after the collapse partition.
        self.assertEqual(self.physical_state_adjacency[105], {74, 311, 312})
        # Central Sloboda is a physical enclave between the Solar states. It is
        # deliberately not attached to EGC by a visible map-crossing corridor.
        self.assertEqual(self.physical_state_adjacency[104], {76, 198, 307})
        self.assertNotIn(81, self.physical_state_adjacency[104])
        self.assertNotIn(81, self.complete_state_adjacency[104])
        adjacency_text = (builder.ROOT / "map" / "adjacencies.csv").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("central_sloboda_corridor", adjacency_text)

    def test_macri_has_a_real_capital_and_enough_units_for_two_fronts(self) -> None:
        capital = state_source(197)
        self.assertRegex(capital, r"victory_points\s*=\s*\{\s*16623\s+10\s*\}")
        eba_oob = (builder.ROOT / "history" / "units" / "EBA_vorkerland_collapse.txt").read_text(
            encoding="utf-8-sig"
        )
        self.assertEqual(eba_oob.count("division = {"), 4)
        self.assertEqual(eba_oob.count('division_template = "EBA Collapse Militia"'), 4)

        effects = (builder.ROOT / "common" / "scripted_effects" / "ADISCORD_vorkerland_collapse_effects.txt").read_text(
            encoding="utf-8-sig"
        )
        setup_match = re.search(
            r"(?ms)^ADISCORD_vorkerland_setup_eba\s*=\s*\{(.*?)(?=^ADISCORD_[A-Za-z0-9_]+\s*=\s*\{|\Z)",
            effects,
        )
        self.assertIsNotNone(setup_match)
        setup = setup_match.group(1)
        self.assertRegex(setup, r"\badd_manpower\s*=\s*(?:[89]\d{3}|\d{5,})\b")
        rifles = re.search(
            r"add_equipment_to_stockpile\s*=\s*\{[^{}]*type\s*=\s*infantry_equipment_0[^{}]*amount\s*=\s*(\d+)",
            setup,
        )
        self.assertIsNotNone(rifles)
        self.assertGreaterEqual(int(rifles.group(1)), 800)

    def test_pwr_psd_front_keeps_its_supply_hub_and_railways(self) -> None:
        supply_nodes = {
            int(fields[1])
            for line in (builder.ROOT / "map" / "supply_nodes.txt").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(fields := line.split()) >= 2
        }
        self.assertIn(2339, self.states[194])
        self.assertIn(2339, supply_nodes)
        railways = [
            [int(value) for value in line.split()[2:]]
            for line in (builder.ROOT / "map" / "railways.txt").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(line.split()) >= 3
        ]
        connected_lines = [line for line in railways if 2339 in line]
        self.assertGreaterEqual(len(connected_lines), 2)
        self.assertTrue(any(8032 in line or 7129 in line for line in connected_lines))

    def test_all_ivanland_owned_core_states_have_logistics_profiles(self) -> None:
        owned_and_core = set()
        for path in builder.STATE_DIR.glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            state_match = re.search(r"\bid\s*=\s*(\d+)", source)
            if not state_match:
                continue
            if re.search(r"(?m)^\s*owner\s*=\s*IVN\s*$", source) and re.search(
                r"(?m)^\s*add_core_of\s*=\s*IVN\s*$", source
            ):
                owned_and_core.add(int(state_match.group(1)))
        self.assertEqual(set(builder.IVANLAND_STATE_PROFILES), owned_and_core)
        total_population = sum(
            int(profile["population"])
            for profile in builder.IVANLAND_STATE_PROFILES.values()
        )
        self.assertGreaterEqual(total_population, 13_500_000)
        self.assertLessEqual(total_population, 14_100_000)
        for state_id, profile in builder.IVANLAND_STATE_PROFILES.items():
            with self.subTest(state=state_id):
                self.assert_profile_applied(state_id, profile)
                source = state_source(state_id)
                self.assertGreater(int(scalar(source, "manpower")), 0)
                self.assertGreaterEqual(float(scalar(source, "local_supplies")), 2.0)
                self.assertGreaterEqual(building_level(source, "infrastructure"), 2)
                self.assertNotRegex(source, r"state_category\s*=\s*wasteland\b")

    def test_ivanland_reserve_hub_and_railway_are_preserved(self) -> None:
        supply_nodes = {
            int(fields[1])
            for line in (builder.ROOT / "map" / "supply_nodes.txt").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(fields := line.split()) >= 2
        }
        self.assertIn(16568, self.states[25])
        self.assertIn(16568, supply_nodes)
        railways = [
            [int(value) for value in line.split()[2:]]
            for line in (builder.ROOT / "map" / "railways.txt").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(line.split()) >= 3
        ]
        connected_lines = [line for line in railways if 16568 in line]
        self.assertGreaterEqual(len(connected_lines), 2)
        self.assertTrue(any(11815 in line and 6010 in line for line in connected_lines))

    def test_all_afrela_owned_core_states_have_moderate_profiles(self) -> None:
        owned_and_core = set()
        for path in builder.STATE_DIR.glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig", errors="strict")
            state_match = re.search(r"\bid\s*=\s*(\d+)", source)
            if not state_match:
                continue
            if re.search(r"(?m)^\s*owner\s*=\s*PIV\s*$", source) and re.search(
                r"(?m)^\s*add_core_of\s*=\s*PIV\s*$", source
            ):
                owned_and_core.add(int(state_match.group(1)))
        self.assertEqual(set(builder.AFRELA_STATE_PROFILES), owned_and_core)
        total_population = sum(
            int(profile["population"])
            for profile in builder.AFRELA_STATE_PROFILES.values()
        )
        self.assertGreaterEqual(total_population, 7_000_000)
        self.assertLessEqual(total_population, 7_300_000)
        self.assertEqual(
            sum(int(profile.get("civilian", 0)) for profile in builder.AFRELA_STATE_PROFILES.values()),
            12,
        )
        self.assertEqual(
            sum(int(profile.get("military", 0)) for profile in builder.AFRELA_STATE_PROFILES.values()),
            5,
        )
        for state_id, profile in builder.AFRELA_STATE_PROFILES.items():
            with self.subTest(state=state_id):
                self.assert_profile_applied(state_id, profile)
                source = state_source(state_id)
                self.assertGreater(int(scalar(source, "manpower")), 0)
                self.assertGreaterEqual(float(scalar(source, "local_supplies")), 1.5)
                self.assertGreaterEqual(building_level(source, "infrastructure"), 2)
                self.assertNotRegex(source, r"state_category\s*=\s*wasteland\b")
        self.assertLessEqual(
            int(builder.AFRELA_STATE_PROFILES[232]["population"]), 150_000
        )

    def test_afrela_settlements_have_generated_vps_and_bom_names(self) -> None:
        expected_points = {
            52: ((4218, 12),),
            113: ((5162, 4),),
            114: ((7920, 4),),
            232: ((11546, 1),),
            326: ((16626, 5),),
        }
        self.assertEqual(builder.AFRELA_LEGACY_VICTORY_POINTS, expected_points)
        definition = {
            int(fields[0]): fields[4]
            for line in (builder.ROOT / "map" / "definition.csv").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(fields := line.split(";")) > 4 and fields[0].isdigit()
        }
        for state_id, points in expected_points.items():
            source = state_source(state_id)
            self.assertGreater(int(scalar(source, "manpower")), 0)
            for province_id, value in points:
                with self.subTest(state=state_id, province=province_id):
                    self.assertIn(province_id, self.states[state_id])
                    self.assertEqual(definition[province_id], "land")
                    self.assertRegex(
                        source,
                        rf"victory_points\s*=\s*\{{\s*{province_id}\s+{value}\s*\}}",
                    )
        localisation_path = (
            builder.ROOT / "localisation" / "russian" / "victory_points_l_russian.yml"
        )
        self.assertTrue(localisation_path.read_bytes().startswith(codecs.BOM_UTF8))
        localisation = localisation_path.read_text(encoding="utf-8-sig")
        for province_id, name in builder.AFRELA_VICTORY_POINT_NAMES.items():
            self.assertIn(f'VICTORY_POINTS_{province_id}: "{name}"', localisation)

    def test_afrela_mainland_hub_and_railway_are_preserved(self) -> None:
        supply_nodes = {
            int(fields[1])
            for line in (builder.ROOT / "map" / "supply_nodes.txt").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(fields := line.split()) >= 2
        }
        self.assertIn(4218, self.states[52])
        self.assertIn(4218, supply_nodes)
        railways = [
            [int(value) for value in line.split()[2:]]
            for line in (builder.ROOT / "map" / "railways.txt").read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if len(line.split()) >= 3
        ]
        self.assertTrue(any(4218 in line and 16626 in line for line in railways))
        mainland = {52, 113, 114, 326}
        reached = {52}
        while True:
            expanded = reached | {
                neighbour
                for state_id in reached
                for neighbour in self.physical_state_adjacency[state_id]
                if neighbour in mainland
            }
            if expanded == reached:
                break
            reached = expanded
        self.assertEqual(reached, mainland)
        self.assertEqual(self.physical_state_adjacency[232], set())

    def test_state_generator_cannot_overwrite_hand_authored_flags(self) -> None:
        generator_source = Path(builder.__file__).read_text(
            encoding="utf-8-sig", errors="strict"
        )
        self.assertNotIn("def build_flags", generator_source)
        self.assertNotRegex(generator_source, r'ROOT\s*/\s*["\']gfx["\']\s*/\s*["\']flags["\']')
        self.assertNotIn(".tga", generator_source.lower())

    def test_special_legacy_map_data_survives_rebalance(self) -> None:
        self.assertIn("victory_points = { 16428 150 }", state_source(40))
        self.assertIn("bunker = 1", state_source(72))
        self.assertIn("owner = NAM", state_source(67))


if __name__ == "__main__":
    unittest.main()
