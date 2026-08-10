from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tools.builders import build_adiscord_technology_system as generator
from tools.validators import validate_adiscord_tech_doctrine as validator


ROOT = Path(__file__).resolve().parents[2]
LEGACY_MANIFEST = ROOT / "tools" / "data" / "adiscord_technology_legacy_manifest.json"
STARTING_PROFILE_MANIFEST = ROOT / "tools" / "data" / "adiscord_starting_technology_profiles.json"


class CompactTechnologyTreeContractTests(unittest.TestCase):
    def test_legacy_manifest_covers_the_pre_redesign_tree(self) -> None:
        payload = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
        rows = payload["technologies"]
        ids = [row["id"] for row in rows]
        self.assertEqual(payload["technology_count"], 625)
        self.assertEqual(len(ids), 625)
        self.assertEqual(len(ids), len(set(ids)))

    def test_visible_tabs_expose_only_the_approved_main_trunks(self) -> None:
        expected = {
            "industry_folder": {
                "production",
                "industry_organization",
                "reconstruction",
                "resources",
            },
            "electronics_folder": {"signals", "computing", "power"},
            "infantry_folder": {
                "small_arms",
                "squad_weapons",
                "protection",
                "special_forces",
            },
            "support_folder": {"field_support", "logistics", "rail"},
            "artillery_folder": {"artillery", "anti_tank", "anti_air"},
            "armour_folder": {"recon_armor", "combat_armor", "heavy_armor"},
            "air_techs_folder": {"fighter", "air_support", "strategic_air"},
            "naval_folder": {"naval_support", "surface_fleet", "subsurface"},
        }
        actual = getattr(generator, "MAIN_BRANCH_KEYS_BY_FOLDER", {})
        self.assertEqual(actual, expected)
        self.assertTrue(all(len(branches) <= 6 for branches in actual.values()))

    def test_long_encryption_and_uniform_applied_diamonds_are_gone(self) -> None:
        branches = {branch.key: branch for branch in generator.BRANCHES}
        # Three recovered-baseline nodes plus eight live capability steps are
        # still compact while preserving the scripted radio/encryption IDs.
        self.assertLessEqual(len(branches["signals"].techs), 11)
        side_keys = getattr(generator, "SIDE_PROGRAMME_KEYS", set())
        self.assertEqual(
            side_keys,
            {
                "combat_medicine",
                "combat_engineering",
                "counter_drone_warfare",
                "air_mobility",
                "riverine_warfare",
                "unmanned_ground_systems",
                "officer_training",
            },
        )
        self.assertTrue(all(len(branches[key].techs) <= 3 for key in side_keys))

    def test_xor_lifetime_is_explicit_and_rare(self) -> None:
        expected = {
            "production": "temporary",
            "industry_organization": "permanent",
            "computing": "temporary",
            "artillery": "permanent",
            "combat_armor": "permanent",
            "fighter": "permanent",
        }
        actual = getattr(generator, "XOR_KIND_BY_BRANCH", {})
        self.assertEqual(actual, expected)
        self.assertLessEqual(len(actual), 6)

    def test_industrial_volume_has_an_energy_price(self) -> None:
        branches = {branch.key: branch for branch in generator.BRANCHES}
        organization = branches.get("industry_organization")
        self.assertIsNotNone(organization)
        effects = [
            entry
            for index in range(len(organization.techs))
            for entry in generator.effects_for(organization, index)
        ]
        self.assertTrue(any("industrial_capacity_factory" in entry for entry in effects))
        self.assertTrue(any("factory_energy_consumption" in entry for entry in effects))
        self.assertTrue(any("industry_air_damage_factor" in entry for entry in effects))

        concentrated_notes = generator.technology_description_notes(organization, 1, False)
        self.assertTrue(any("Energy price:" in note for note in concentrated_notes))
        self.assertTrue(any("Permanent specialization choice:" in note for note in concentrated_notes))
        self.assertFalse(any("common line continues" in note for note in concentrated_notes))

    def test_every_legacy_id_has_one_migration_outcome(self) -> None:
        payload = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
        legacy_ids = {row["id"] for row in payload["technologies"]}
        migrations = getattr(generator, "TECHNOLOGY_ID_MIGRATIONS", {})
        self.assertEqual(set(migrations), legacy_ids)
        self.assertTrue(
            all(entry["status"] in {"preserved", "replaced", "removed"} for entry in migrations.values())
        )
        current_ids = {tech.id for branch in generator.BRANCHES for tech in branch.techs}
        for old_id, entry in migrations.items():
            if entry["status"] == "preserved":
                self.assertIn(old_id, current_ids)
                self.assertEqual(entry["replacement"], old_id)
            elif entry["status"] == "replaced":
                self.assertNotEqual(entry["replacement"], old_id)
                self.assertIn(entry["replacement"], current_ids)
            else:
                self.assertIsNone(entry["replacement"])

    def test_every_2160_state_owner_has_an_explicit_starting_profile(self) -> None:
        owners = set()
        for path in (ROOT / "history" / "states").glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            owners.update(re.findall(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})\s*$", text))
        assignments = generator.STARTING_COUNTRY_TECH_PROFILES
        self.assertEqual(set(assignments), owners)
        valid_profiles = set(generator.STARTING_TECH_PROFILES) - {"common", "late_2183"}
        for tag, profiles in assignments.items():
            self.assertEqual(len(profiles), len(set(profiles)), tag)
            self.assertTrue(set(profiles) <= valid_profiles, tag)

    def test_starting_profiles_are_closed_and_respect_permanent_xor(self) -> None:
        for profile, tech_ids in generator.STARTING_TECH_PROFILES.items():
            granted = set(tech_ids)
            for tech_id in tech_ids:
                branch, index = generator.TECH_POSITION_BY_ID[tech_id]
                for parent_index, successors in enumerate(
                    generator.BRANCH_GRAPHS[branch.key].successors
                ):
                    if index in successors:
                        self.assertIn(branch.techs[parent_index].id, granted, profile)
                for dependency in generator.EXTRA_TECH_DEPENDENCIES.get(tech_id, ()):
                    self.assertIn(dependency, granted, profile)
            for branch_key, kind in generator.XOR_KIND_BY_BRANCH.items():
                if kind != "permanent":
                    continue
                branch = generator.BRANCH_BY_KEY[branch_key]
                for group in generator.XOR_INDEX_GROUPS_BY_BRANCH[branch_key]:
                    choices = {branch.techs[index].id for index in group}
                    self.assertFalse(choices <= granted, f"{profile}: {sorted(choices)}")

    def test_starting_profile_manifest_is_machine_readable_and_bounded(self) -> None:
        payload = json.loads(STARTING_PROFILE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(payload["active_country_count"], 68)
        self.assertEqual(set(payload["countries"]), set(generator.STARTING_COUNTRY_TECH_PROFILES))
        self.assertEqual(
            set(generator.STARTING_COUNTRY_TECH_PROFILE_RATIONALE),
            set(generator.STARTING_COUNTRY_TECH_PROFILES),
        )
        self.assertEqual(
            {tag for tag, profiles in generator.STARTING_COUNTRY_TECH_PROFILES.items() if not profiles},
            {"COF", "EXZ", "PWR"},
        )
        for tag, entry in payload["countries"].items():
            self.assertGreaterEqual(len(entry["rationale"]), 24, tag)
            self.assertGreaterEqual(entry["evidence"]["states"], 1, tag)
        self.assertLess(
            len(generator.STARTING_TECH_PROFILES["late_2183"]),
            len({tech.id for branch in generator.BRANCHES for tech in branch.techs}) // 4,
        )

    def test_starting_profile_manifest_evidence_matches_live_sources(self) -> None:
        payload = json.loads(STARTING_PROFILE_MANIFEST.read_text(encoding="utf-8"))
        observed = generator.collect_starting_country_profile_evidence()
        self.assertEqual(
            {tag: entry["evidence"] for tag, entry in payload["countries"].items()},
            observed,
        )

    def test_resource_building_icon_strip_matches_gfx_and_dds_capacity(self) -> None:
        capacity, issues = validator.building_icon_strip_capacity()
        self.assertEqual(issues, [])
        self.assertEqual(capacity, 42)
        buildings = validator.collect_building_blocks()
        frames = {
            building: int(re.search(r"\bicon_frame\s*=\s*(\d+)", buildings[building]).group(1))
            for building in (
                "ADISCORD_metallurgical_complex",
                "ADISCORD_electrolysis_complex",
                "ADISCORD_strategic_mining_complex",
                "ADISCORD_thermal_power_complex",
            )
        }
        self.assertEqual(frames, {
            "ADISCORD_metallurgical_complex": 35,
            "ADISCORD_electrolysis_complex": 36,
            "ADISCORD_strategic_mining_complex": 37,
            "ADISCORD_thermal_power_complex": 38,
        })
        self.assertLessEqual(max(frames.values()), capacity)

    def test_land_profile_is_not_an_automatic_armor_package(self) -> None:
        land = set(generator.STARTING_TECH_PROFILES["land"])
        self.assertNotIn("ADISCORD_tech_remote_weapon_stations", land)
        self.assertNotIn("ADISCORD_tech_light_suspension", land)
        self.assertNotIn("ADISCORD_tech_reinforced_powertrains", land)


if __name__ == "__main__":
    unittest.main()
