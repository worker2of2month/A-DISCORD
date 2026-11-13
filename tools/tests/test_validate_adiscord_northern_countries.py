from collections import defaultdict
import re
import unittest
from unittest.mock import patch

from PIL import Image

from tools.builders import build_adiscord_map_buildings as map_buildings
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


if __name__ == "__main__":
    unittest.main()
