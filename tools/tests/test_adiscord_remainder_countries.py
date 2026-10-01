"""Country loading and maritime supply contracts for the remaining land."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.lib import adiscord_remainder_countries as countries
from tools.builders import build_adiscord_technology_system as technology
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]


class RemainderCountryTests(unittest.TestCase):
    def test_all_land_states_have_registered_starting_owners(self):
        registered = set()
        for path in (ROOT / "common/country_tags").glob("*.txt"):
            registered.update(re.findall(r'(?m)^([A-Z0-9]{3})\s*=\s*"', path.read_text(encoding="utf-8-sig")))
        for path in (ROOT / "history/states").glob("*.txt"):
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8-sig")
                owner = re.search(r"\bowner\s*=\s*(\w+)", source)
                self.assertIsNotNone(owner)
                self.assertIn(owner[1], registered)

    def test_country_partition_capitals_and_total_population(self):
        claimed = [s for row in countries.COUNTRIES.values() for s in row["states"]]
        self.assertEqual(len(claimed), 49)
        self.assertEqual(len(claimed), len(set(claimed)))
        self.assertEqual(len(countries.COUNTRIES), 11)
        profiles = countries.profiles()
        for tag, row in countries.COUNTRIES.items():
            with self.subTest(tag=tag):
                self.assertEqual(countries.STATE_OWNERS[row["capital"]], tag)
                self.assertEqual(sum(profiles[s]["population"] for s in row["states"]), row["population"])
                self.assertGreater(row["population"], row["divisions"] * 3000)
                self.assertIn(tag, technology.STARTING_COUNTRY_TECH_PROFILES)
                self.assertFalse(Path(f"{tag}.txt").is_reserved())
                for key in ("civilian", "military", "dockyard"):
                    self.assertEqual(sum(profiles[s][key] for s in row["states"]), row[key])

    def test_state_population_is_idempotent_and_preserves_geography(self):
        for state_id in countries.STATE_OWNERS:
            with self.subTest(state=state_id):
                source = countries.state_path(state_id).read_text(encoding="utf-8")
                rendered = countries.populate_state(source, state_id)
                self.assertEqual(rendered, source)
                self.assertEqual(countries.populate_state(rendered, state_id), source)
                entries = parse_clausewitz(source)
                self.assertEqual([entry.key for entry in entries], ["state"])
                state = entries[0].value
                self.assertEqual(sum(entry.key == "history" for entry in state), 1)
                history = next(entry.value for entry in state if entry.key == "history")
                self.assertEqual([entry.value for entry in history if entry.key == "owner"], [countries.STATE_OWNERS[state_id]])
                self.assertEqual([entry.value for entry in history if entry.key == "add_core_of"], [countries.STATE_OWNERS[state_id]])
                # The geography builder produces a bare shell on a full rebuild.
                bare = source.split(countries.MARKER)[0] + "}\n"
                bare = re.sub(r"manpower\s*=\s*\d+", "manpower = 1", bare)
                self.assertEqual(countries.populate_state(bare, state_id), source)

    def test_starting_forces_and_ports_are_on_owned_land(self):
        _, definitions = countries.load_definition()
        for tag, row in countries.COUNTRIES.items():
            provinces = set().union(*(countries.profiles()[s]["provinces"] for s in row["states"]))
            source = (ROOT / f"history/units/{tag}.txt").read_text(encoding="utf-8")
            locations = list(map(int, re.findall(r"\blocation\s*=\s*(\d+)", source)))
            self.assertEqual(len(locations), row["divisions"])
            self.assertTrue(set(locations) <= provinces)
            history = (ROOT / f"history/countries/{tag} - {tag}.txt").read_text(encoding="utf-8")
            self.assertRegex(history, r"set_convoys\s*=\s*[1-9]\d*")
            for state_id in row["states"]:
                profile = countries.profiles()[state_id]
                if any(definitions[p]["coastal"] for p in profile["provinces"]):
                    self.assertTrue(profile["ports"], state_id)
                self.assertTrue(set(profile["ports"]) <= profile["provinces"])
                state = countries.state_path(state_id).read_text(encoding="utf-8")
                category = re.search(r"state_category\s*=\s*(\w+)", state)[1]
                capacity = {"rural": 2, "town": 4, "city": 6}[category]
                self.assertLessEqual(sum(profile[key] for key in ("civilian", "military", "dockyard")), capacity)

    def test_generated_files_and_localisation_encodings_are_current(self):
        self.assertEqual(countries.synchronize(), [])
        for path, expected in countries.country_outputs().items():
            with self.subTest(path=path.name):
                actual = path.read_bytes()
                self.assertEqual(actual, expected)
                if path.suffix == ".yml":
                    self.assertTrue(actual.startswith(b"\xef\xbb\xbf"))
                elif path.suffix == ".txt":
                    self.assertFalse(actual.startswith(b"\xef\xbb\xbf"))
                    parse_clausewitz(actual.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
