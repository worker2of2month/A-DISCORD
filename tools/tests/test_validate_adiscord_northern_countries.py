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
        lists = {state_id: (state_id,) for state_id in northern.COUNTRIES["MON"]["states"]}
        cities = {state_id: state_id for state_id in northern.COUNTRIES["MON"]["states"]}
        with self.assertRaisesRegex(RuntimeError, "outside state 469"):
            northern.check_mon_settlements(lists, cities, ((469, 460, 1, "Корвель"),))
        with self.assertRaisesRegex(RuntimeError, "already holds"):
            northern.check_mon_settlements(
                lists, cities, ((469, 469, 20, "Монтера"), (469, 469, 1, "Фаллен"))
            )
        with self.assertRaisesRegex(RuntimeError, "one city per state"):
            northern.check_mon_settlements(lists, {469: 469}, ())

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

    def test_reviewed_english_pairs_cover_every_city_and_village(self):
        import json

        catalogue = json.loads(northern.ENGLISH_NAMES.read_text(encoding="utf-8"))
        specification = northern.english_specification(catalogue)
        table = northern.load_mon_geography()
        for entry in table["settlements"]:
            if entry["kind"] == "city":
                review = specification["entries"][f"VICTORY_POINTS_{entry['parent']}"]
                self.assertEqual(entry["name"], review["russian"])
            elif entry["kind"] == "village":
                self.assertIn(entry["name"], specification["village_names"])

    def test_placed_villages_render_after_the_city_and_other_states_stay_unchanged(self):
        baseline, _principal = build_profiles()
        table = copy.deepcopy(northern.load_mon_geography())
        cities = northern.mon_city_parents(table)
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
                if province != cities[state_id]
            )
            placed[state_id] = entry["province"]
        with patch.object(northern, "load_mon_geography", return_value=table):
            profiles, principal = build_profiles()
        for state_id in northern.COUNTRIES["MON"]["states"]:
            with self.subTest(state=state_id):
                self.assertEqual(cities[state_id], principal[state_id])
                points = profiles[state_id]["victory_points"]
                self.assertEqual(cities[state_id], points[0][0])
                self.assertEqual(placed[state_id], points[1][0])
                self.assertEqual(2, len(points))
        rendered = northern.render_state(469, profiles[469])
        self.assertIn(
            "\t\tvictory_points = { 2845 20 }\n"
            f"\t\tvictory_points = {{ {placed[469]} 2 }}\n",
            rendered,
        )
        for state_id in set(profiles) - set(northern.COUNTRIES["MON"]["states"]):
            self.assertEqual(
                northern.render_state(state_id, baseline[state_id]),
                northern.render_state(state_id, profiles[state_id]),
            )


if __name__ == "__main__":
    unittest.main()
