from collections import defaultdict
import copy
import re
import unittest
from unittest.mock import patch

from PIL import Image

from tools.builders import build_adiscord_map_buildings as map_buildings
from tools.builders import build_adiscord_northern_countries as northern
from tools.builders import build_adiscord_strategic_regions as geography
from tools.builders.build_adiscord_northern_countries import build_profiles
from tools.validators.validate_adiscord_northern_countries import validate


class NorthernCountryContractsTest(unittest.TestCase):
    def test_island_countries_have_ocean_supply_on_each_detached_territory(self):
        root = map_buildings.ROOT
        types, colors = geography.load_province_definitions()
        physical = geography.load_province_adjacency(
            types, colors, include_special_adjacencies=False
        )
        land = {province for province, kind in types.items() if kind == "land"}
        landmasses = sorted(
            geography.connected_components(land, physical), key=len, reverse=True
        )
        # The map has two continental landmasses; smaller shared islands also
        # need ports for each country's independently owned territory.
        mainland = set().union(*landmasses[:2])
        routes = {province: set(neighbours) for province, neighbours in physical.items()}
        for line in (root / "map/adjacencies.csv").read_text(encoding="utf-8-sig").splitlines():
            fields = line.split(";")
            if (
                len(fields) >= 3 and fields[0].isdigit() and fields[1].isdigit()
                and fields[2] in {"sea", "land"}
            ):
                first, second = map(int, fields[:2])
                routes[first].add(second)
                routes[second].add(first)

        territories = defaultdict(set)
        ports = defaultdict(set)
        state_by_province = map_buildings.load_state_by_province()
        for path in (root / "history/states").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            owner = re.search(r"\bowner\s*=\s*(\w+)", source)[1]
            provinces = re.search(r"\bprovinces\s*=\s*\{([^}]+)", source)[1]
            territories[owner].update(map(int, re.findall(r"\d+", provinces)))
            ports[owner].update(
                int(province) for province, level in re.findall(
                    r"(\d+)\s*=\s*\{\s*naval_base\s*=\s*(\d+)", source
                ) if int(level) > 0
            )

        anchor_seas = defaultdict(set)
        rgb_to_province = map_buildings.load_province_by_color()
        with Image.open(root / "map/provinces.bmp") as image:
            for line in (root / "map/buildings.txt").read_text(encoding="utf-8-sig").splitlines():
                fields = line.split(";")
                if len(fields) != 7 or fields[1] != "naval_base_spawn":
                    continue
                x = map_buildings._pixel_coordinate(fields[2], image.width)
                y = image.height - 1 - map_buildings._pixel_coordinate(fields[4], image.height)
                province = rgb_to_province[image.getpixel((x, y))]
                if int(fields[0]) == state_by_province.get(province):
                    anchor_seas[province].add(int(fields[6]))

        for tag, provinces in territories.items():
            if provinces & mainland:
                continue
            for component in geography.connected_components(provinces, routes):
                ocean_coast = {
                    province for province in component
                    if any(types[neighbour] == "sea" for neighbour in physical[province])
                }
                # An island inside a lake has no ocean supply route.
                if not ocean_coast:
                    continue
                with self.subTest(tag=tag, territory=min(component)):
                    local_ports = component & ports[tag]
                    self.assertTrue(local_ports, f"{tag}: no port on {sorted(component)}")
                    for province in local_ports:
                        self.assertIn(province, ocean_coast)
                        self.assertTrue(any(
                            sea in physical[province] and types[sea] == "sea"
                            for sea in anchor_seas[province]
                        ), f"{tag}: port {province} has no native anchor facing its sea")

    def test_northern_country_contract(self):
        self.assertEqual([], validate())

    def test_starting_factories_fit_native_state_categories(self):
        profiles, _principal_provinces = build_profiles()
        native_slots = {"pastoral": 1, "rural": 2, "town": 4, "large_town": 5}
        for state_id, profile in profiles.items():
            with self.subTest(state_id=state_id):
                factories = profile["civilian"] + profile["military"]
                self.assertLessEqual(factories, native_slots[profile["category"]])

    def test_validator_rejects_starting_factory_overflow(self):
        profiles, principal_provinces = build_profiles()
        profiles[425]["category"] = "rural"
        profiles[425]["civilian"] = 2
        profiles[425]["military"] = 1
        with patch(
            "tools.validators.validate_adiscord_northern_countries.build_profiles",
            return_value=(profiles, principal_provinces),
        ):
            issues = validate()
        self.assertIn(
            "state 425 has 3 starting factories but rural supports only 2 shared slots",
            issues,
        )


def sample_geography(planned=(), villages=None):
    """A two-state settlement table in the schema of the MON geography data."""
    return {
        "schema": 1,
        "settlements": [
            {"state": 469, "kind": "city", "parent": 2845, "value": 20, "name": "Монтера"},
            {"state": 469, "kind": "district", "parent": 2845},
            {"state": 460, "kind": "city", "parent": 6028, "value": 8, "name": "Вальд"},
            {"state": 469, "kind": "village", "province": (villages or {}).get("Фаллен"), "value": 2, "name": "Фаллен"},
            {"state": 460, "kind": "village", "province": (villages or {}).get("Корвель"), "value": 1, "name": "Корвель"},
            {"state": 469, "kind": "village", "province": (villages or {}).get("Коронный тракт"), "value": 1, "name": "Коронный тракт"},
        ],
        "planned": {"provinces": [dict(entry) for entry in planned]},
    }


class MonSettlementTableTest(unittest.TestCase):
    PLANNED = (
        {"province": 90001, "rgb": [1, 2, 3], "state": 469, "parent": 2845, "kind": "remainder"},
        {"province": 90002, "rgb": [1, 2, 4], "state": 469, "parent": 2845, "kind": "district"},
        {"province": 90003, "rgb": [1, 2, 5], "state": 460, "parent": 6028, "kind": "remainder"},
    )

    def test_cities_come_first_and_unplaced_villages_are_skipped(self):
        points = northern.mon_settlement_points(
            sample_geography(villages={"Коронный тракт": 693, "Корвель": 268})
        )
        self.assertEqual(
            points,
            (
                (469, 2845, 20, "Монтера"),
                (460, 6028, 8, "Вальд"),
                (460, 268, 1, "Корвель"),
                (469, 693, 1, "Коронный тракт"),
            ),
        )

    def test_planned_provinces_join_their_own_state_once_on_the_map(self):
        table = sample_geography(planned=self.PLANNED)
        self.assertEqual({}, northern.mon_planned_provinces(table, {2845, 6028}))
        planned = northern.mon_planned_provinces(table, {90001, 90002, 90003})
        self.assertEqual({469: {90001, 90002}, 460: {90003}}, planned)
        with self.assertRaisesRegex(RuntimeError, "partly on the map"):
            northern.mon_planned_provinces(table, {90001})
        shells = {
            469: (469, (2845, 693), "climate"),
            460: (460, (6028,), "climate"),
            425: (425, (212,), "climate"),
        }
        lists = northern.state_province_lists(shells, planned)
        self.assertEqual((693, 2845, 90001, 90002), lists[469])
        self.assertEqual((6028, 90003), lists[460])
        self.assertEqual((212,), lists[425])

    def test_planned_province_kinds_are_explicit(self):
        table = sample_geography(planned=({**self.PLANNED[0], "kind": "donor"},))
        with self.assertRaisesRegex(RuntimeError, "unknown kind"):
            northern.mon_planned_ids(table)

    def test_victory_points_must_lie_in_their_state_once(self):
        scope = northern.MONTAR_STATES
        lists = {state_id: (state_id,) for state_id in scope}
        cities = {state_id: state_id for state_id in scope}
        with self.assertRaisesRegex(RuntimeError, "outside state 469"):
            northern.check_mon_settlements(lists, cities, ((469, 460, 1, "Корвель"),), scope)
        with self.assertRaisesRegex(RuntimeError, "already holds"):
            northern.check_mon_settlements(
                lists, cities, ((469, 469, 20, "Монтера"), (469, 469, 1, "Фаллен")), scope
            )
        with self.assertRaisesRegex(RuntimeError, "one city per state"):
            northern.check_mon_settlements(lists, {469: 469}, (), scope)

    def test_localisation_names_every_rendered_point(self):
        _profiles, principal = build_profiles()
        points = northern.mon_settlement_points(
            sample_geography(villages={"Фаллен": 693})
        )
        localisation = northern.victory_point_localisation(principal, points)
        self.assertEqual("Монтера", localisation["VICTORY_POINTS_2845"])
        self.assertEqual("Фаллен", localisation["VICTORY_POINTS_693"])
        self.assertNotIn("VICTORY_POINTS_268", localisation)
        with self.assertRaisesRegex(RuntimeError, "named both"):
            northern.victory_point_localisation(principal, ((460, 6028, 8, "Другой"),))

    def test_english_village_names_wait_for_their_province(self):
        specification = {
            "entries": {"VICTORY_POINTS_2845": {"russian": "Монтера", "english": "Montera"}},
            "village_names": {"Фаллен": "Fallen"},
        }
        localisation = {
            "VICTORY_POINTS_2845": "Монтера",
            "VICTORY_POINTS_693": "Фаллен",
            "VICTORY_POINTS_268": "Корвель",
        }
        gaps = northern.english_name_gaps(specification, localisation)
        self.assertEqual(2, len(gaps))
        self.assertIn("'Fallen' is promoted by --apply", gaps[0])
        self.assertEqual(
            ["VICTORY_POINTS_693"],
            northern.promote_village_names(specification, localisation),
        )
        self.assertEqual(
            {"russian": "Фаллен", "english": "Fallen"},
            specification["entries"]["VICTORY_POINTS_693"],
        )
        self.assertEqual(
            ["VICTORY_POINTS_268 (Корвель) has no English pair"],
            northern.english_name_gaps(specification, localisation),
        )

    def test_reviewed_english_pairs_cover_every_rendered_settlement(self):
        import json

        catalogue = json.loads(northern.ENGLISH_NAMES.read_text(encoding="utf-8"))
        specification = northern.english_specification(catalogue)
        table = northern.load_mon_geography()
        scope = northern.geography_scope_states(table) & northern.EXPECTED_STATES
        for state_id, province_id, _value, name in northern.mon_settlement_points(table):
            if state_id not in scope:
                continue
            with self.subTest(province=province_id):
                review = specification["entries"][f"VICTORY_POINTS_{province_id}"]
                self.assertEqual(name, review["russian"])
        for entry in table["settlements"]:
            if entry["kind"] == "village":
                self.assertIn(entry["name"], specification["village_names"])

    def test_placed_villages_render_after_the_cities_and_other_states_stay_unchanged(self):
        baseline, _principal = build_profiles()
        table = copy.deepcopy(northern.load_mon_geography())
        cities = northern.mon_city_parents(table)
        second_cities = {
            entry["state"]: entry["parent"] for entry in table["stage2"]["settlements"]
        }
        for entry in table["settlements"]:
            if entry["kind"] == "village":
                entry["province"] = None
        placed = {}
        for entry in table["settlements"]:
            # Leave the second village of each state unplaced.
            if entry["kind"] != "village" or entry["state"] in placed:
                continue
            state_id = entry["state"]
            entry["province"] = next(
                province
                for province in baseline[state_id]["provinces"]
                if province not in (cities[state_id], second_cities.get(state_id))
            )
            placed[state_id] = entry["province"]
        with patch.object(northern, "load_mon_geography", return_value=table):
            profiles, principal = build_profiles()
        for state_id in northern.MONTAR_STATES:
            with self.subTest(state=state_id):
                self.assertEqual(cities[state_id], principal[state_id])
                expected = [cities[state_id]]
                if state_id in second_cities:
                    expected.append(second_cities[state_id])
                expected.append(placed[state_id])
                points = profiles[state_id]["victory_points"]
                self.assertEqual(expected, [province for province, _value, _name in points])
        rendered = northern.render_state(469, profiles[469])
        self.assertIn(
            "\t\tvictory_points = { 2845 20 }\n"
            f"\t\tvictory_points = {{ {second_cities[469]} 3 }}\n"
            f"\t\tvictory_points = {{ {placed[469]} 2 }}\n",
            rendered,
        )
        for state_id in set(profiles) - set(northern.MONTAR_STATES):
            self.assertEqual(
                northern.render_state(state_id, baseline[state_id]),
                northern.render_state(state_id, profiles[state_id]),
            )


def regional_geography():
    """A MON state with a second city and a neighbour region, in the Stage 2 schema."""

    def planned(province, state, parent, kind):
        return {"province": province, "rgb": [1, 2, province % 256], "state": state, "parent": parent, "kind": kind}

    table = sample_geography(
        planned=(planned(90001, 469, 2845, "remainder"),),
        villages={"Фаллен": 693},
    )
    table["states"] = [469, 460]
    table["stage2"] = {
        "settlements": [
            {"state": 469, "kind": "city", "parent": 11523, "value": 3, "name": "Фалленбрюк", "name_en": "Fallenbruck"},
        ],
        "planned": {
            "provinces": [
                planned(90101, 423, 4630, "remainder"),
                planned(90102, 423, 5797, "district"),
                planned(90103, 423, 9794, "part"),
                planned(90104, 469, 90001, "part"),
            ],
        },
    }
    table["regions"] = {
        "TMR": {
            "states": [423, 455],
            "settlements": [
                {"state": 423, "kind": "city", "parent": 5797, "value": 10, "name": "Тимер", "name_en": "Timer"},
                {"state": 423, "kind": "district", "parent": 5797},
                {"state": 455, "kind": "city", "parent": 1757, "value": 5, "name": "Орваль", "name_en": "Orval"},
                {"state": 423, "kind": "town", "province": 4630, "value": 2, "name": "Мейдар", "name_en": "Meidar"},
            ],
        },
    }
    return table


class EasternGeographyTableTest(unittest.TestCase):
    def test_scope_is_keyed_by_state_across_all_regions(self):
        self.assertEqual({469, 460, 423, 455}, northern.geography_scope_states(regional_geography()))

    def test_neighbour_cities_are_principal_and_second_cities_are_not(self):
        table = regional_geography()
        self.assertEqual(
            {469: 2845, 460: 6028, 423: 5797, 455: 1757}, northern.mon_city_parents(table)
        )
        self.assertEqual(
            (
                (469, 2845, 20, "Монтера"),
                (460, 6028, 8, "Вальд"),
                (469, 11523, 3, "Фалленбрюк"),
                (423, 5797, 10, "Тимер"),
                (455, 1757, 5, "Орваль"),
                (469, 693, 2, "Фаллен"),
                (423, 4630, 2, "Мейдар"),
            ),
            northern.mon_settlement_points(table),
        )

    def test_each_plan_stage_reaches_the_map_whole(self):
        table = regional_geography()
        self.assertEqual({}, northern.mon_planned_provinces(table, {2845}))
        self.assertEqual(
            {469: {90001}}, northern.mon_planned_provinces(table, {90001})
        )
        self.assertEqual(
            {469: {90001, 90104}, 423: {90101, 90102, 90103}},
            northern.mon_planned_provinces(table, {90001, 90101, 90102, 90103, 90104}),
        )
        with self.assertRaisesRegex(RuntimeError, "Stage 2 province plan is only partly"):
            northern.mon_planned_provinces(table, {90001, 90101})
        entries = northern.mon_planned_entries(table, {90001, 90101, 90102, 90103, 90104})
        self.assertEqual(
            {90001: 2845, 90101: 4630, 90102: 5797, 90103: 9794, 90104: 2845},
            northern.mon_planned_roots(entries),
        )

    def test_a_later_stage_joins_once_planned_and_adopts_its_city(self):
        table = regional_geography()
        table["regions"]["WRK"] = {
            "stage": 3,
            "states": [32],
            "settlements": [{"state": 32, "kind": "adopt", "province": None}],
        }
        self.assertNotIn(32, northern.geography_scope_states(table))
        self.assertNotIn(32, northern.mon_city_parents(table))
        table["regions"]["WRK"]["settlements"][0]["province"] = 16428
        table["stages"] = [
            {"stage": 3, "provinces": [{"province": 90201, "rgb": [1, 2, 3], "state": 32, "parent": 6192, "kind": "part"}]}
        ]
        self.assertIn(32, northern.geography_scope_states(table))
        self.assertEqual(16428, northern.mon_city_parents(table)[32])
        planned = northern.mon_planned_provinces(table, {90001, 90201})
        self.assertEqual({90201}, set(planned[32]))
        with self.assertRaisesRegex(RuntimeError, "Stage 3 province plan is only partly"):
            table["stages"][0]["provinces"].append(
                {"province": 90202, "rgb": [1, 2, 4], "state": 32, "parent": 6192, "kind": "part"}
            )
            northern.mon_planned_provinces(table, {90001, 90201})

    def test_a_planned_province_appears_once(self):
        table = regional_geography()
        table["stage2"]["planned"]["provinces"].append(dict(table["planned"]["provinces"][0]))
        with self.assertRaisesRegex(RuntimeError, "more than one plan entry"):
            northern.mon_planned_ids(table)

    def test_planned_province_may_not_sit_in_another_state(self):
        shells = {469: (469, (2845,), "climate"), 460: (460, (6028, 90001), "climate")}
        with self.assertRaisesRegex(RuntimeError, "already in state 460"):
            northern.state_province_lists(shells, {469: frozenset({90001})})

    def test_scope_states_take_their_settlements_and_other_states_the_manifest(self):
        points = northern.mon_settlement_points(regional_geography())
        country = {
            "states": (423, 455, 409),
            "capital": 423,
            "capital_name": "Тимер",
            "secondary_vps": ((455, "Орваль", 5), (409, "Иверан", 3)),
        }
        principal = {423: 9794, 455: 12300, 409: 3309}
        victory_points = northern.scope_victory_points(
            "TMR", country, principal, points, frozenset({423, 455})
        )
        self.assertEqual(
            {
                423: [(5797, 10, "Тимер"), (4630, 2, "Мейдар")],
                455: [(1757, 5, "Орваль")],
                409: [(3309, 3, "Иверан")],
            },
            victory_points,
        )
        with self.assertRaisesRegex(RuntimeError, "named Тимер in the geography table"):
            northern.scope_victory_points(
                "TMR", {**country, "capital_name": "Другой"}, principal, points, frozenset({423, 455})
            )

    def test_country_names_follow_its_settlements_in_table_order(self):
        points = northern.mon_settlement_points(regional_geography())
        localisation: dict[str, str] = {}
        country = {
            "states": (423, 455, 409),
            "capital": 423,
            "capital_name": "Тимер",
            "secondary_vps": ((409, "Иверан", 3),),
        }
        northern.add_country_victory_point_names(
            localisation, country, {423: 9794, 455: 12300, 409: 3309}, points
        )
        self.assertEqual(
            [
                ("VICTORY_POINTS_5797", "Тимер"),
                ("VICTORY_POINTS_1757", "Орваль"),
                ("VICTORY_POINTS_4630", "Мейдар"),
                ("VICTORY_POINTS_3309", "Иверан"),
            ],
            list(localisation.items()),
        )

    def test_rendered_geography_states_hold_every_table_point(self):
        table = northern.load_mon_geography()
        scope = northern.geography_scope_states(table) & northern.EXPECTED_STATES
        profiles, principal = build_profiles()
        expected: dict[int, list[int]] = defaultdict(list)
        for state_id, province_id, _value, _name in northern.mon_settlement_points(table):
            if state_id in scope:
                expected[state_id].append(province_id)
        cities = northern.mon_city_parents(table)
        for state_id in scope:
            with self.subTest(state=state_id):
                self.assertEqual(cities[state_id], principal[state_id])
                self.assertEqual(
                    expected[state_id],
                    [province for province, _value, _name in profiles[state_id]["victory_points"]],
                )


if __name__ == "__main__":
    unittest.main()
