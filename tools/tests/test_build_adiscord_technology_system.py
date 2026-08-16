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
    @staticmethod
    def _folder_positions(rendered: str) -> dict[str, tuple[int, int]]:
        return {
            folder: (int(x), int(y))
            for folder, x, y in re.findall(
                r"folder\s*=\s*\{\s*name\s*=\s*([A-Za-z0-9_]+)\s*"
                r"position\s*=\s*\{\s*x\s*=\s*(\d+)\s*y\s*=\s*(\d+)",
                rendered,
                flags=re.DOTALL,
            )
        }

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
                "anti_tank_infantry",
                "night_combat",
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

    def test_infantry_antitank_and_night_programmes_are_compact_real_dags(self) -> None:
        branches = generator.BRANCH_BY_KEY
        self.assertGreaterEqual(len(branches["anti_tank_infantry"].techs), 12)
        self.assertGreaterEqual(len(branches["night_combat"].techs), 12)

        for key in ("anti_tank_infantry", "night_combat"):
            with self.subTest(branch=key):
                graph = generator.BRANCH_GRAPHS[key]
                self.assertTrue(any(len(targets) > 1 for targets in graph.successors))
                self.assertTrue(any(len(parents) > 1 for parents in graph.dependencies))
                self.assertGreater(len(set(graph.lanes)), 1)

        night = branches["night_combat"]
        night_icons = {
            generator.icon_for_technology(night, index)
            for index in range(len(night.techs))
        }
        self.assertGreaterEqual(len(night_icons), 6)
        self.assertTrue(all(icon.startswith("ADISCORD_night_") for icon in night_icons))
        for icon in night_icons:
            size = generator.technology_icon_size(icon)
            self.assertIsNotNone(size)
            self.assertLessEqual(size[0], 72)
            self.assertLessEqual(size[1], 72)
        self.assertTrue(all(tech.id not in generator.ENABLE_EQUIPMENT for tech in night.techs))

        antitank = branches["anti_tank_infantry"]
        rendered_effects = "\n".join(
            effect
            for index in range(len(antitank.techs))
            for effect in generator.effects_for(antitank, index)
        )
        self.assertIn("category_all_infantry", rendered_effects)
        self.assertIn("hard_attack", rendered_effects)
        self.assertIn("ap_attack", rendered_effects)

    def test_infantry_and_armor_trunks_are_dense_in_the_live_campaign(self) -> None:
        branches = {branch.key: branch for branch in generator.BRANCHES}
        for key in (
            "small_arms",
            "squad_weapons",
            "protection",
            "special_forces",
        ):
            with self.subTest(branch=key):
                branch = branches[key]
                self.assertGreaterEqual(len(branch.techs), 16)
                live_years = sorted({year for year in branch.years if 2160 <= year <= 2175})
                self.assertGreaterEqual(len(live_years), 10)
                self.assertLessEqual(
                    max(right - left for left, right in zip(live_years, live_years[1:])),
                    3,
                )

    def test_armor_and_mechanized_programmes_have_modern_warfare_density(self) -> None:
        branches = generator.BRANCH_BY_KEY
        for key in ("recon_armor", "combat_armor", "heavy_armor"):
            with self.subTest(branch=key):
                self.assertGreaterEqual(len(branches[key].techs), 20)
                graph = generator.BRANCH_GRAPHS[key]
                self.assertTrue(any(len(targets) > 1 for targets in graph.successors))
                self.assertTrue(any(len(parents) > 1 for parents in graph.dependencies))

        mechanized = branches["mechanized_mobility"]
        self.assertGreaterEqual(len(mechanized.techs), 9)
        graph = generator.BRANCH_GRAPHS["mechanized_mobility"]
        self.assertTrue(any(len(targets) > 1 for targets in graph.successors))
        self.assertTrue(any(len(parents) > 1 for parents in graph.dependencies))

    def test_other_warfare_tabs_restore_full_programmes_and_real_forks(self) -> None:
        branches = generator.BRANCH_BY_KEY
        synthesis_branches = (
            "field_support",
            "logistics",
            "rail",
            "anti_tank",
            "anti_air",
            "air_support",
            "strategic_air",
            "naval_support",
            "surface_fleet",
            "subsurface",
        )
        for key in synthesis_branches:
            with self.subTest(branch=key):
                self.assertEqual(len(branches[key].techs), 20)
                graph = generator.BRANCH_GRAPHS[key]
                self.assertEqual(set(graph.lanes), {0, 1, 2})
                self.assertTrue(any(len(targets) > 1 for targets in graph.successors))
                self.assertTrue(any(len(parents) > 1 for parents in graph.dependencies))

        for key in ("artillery", "fighter"):
            with self.subTest(branch=key):
                self.assertEqual(len(branches[key].techs), 20)
                graph = generator.BRANCH_GRAPHS[key]
                self.assertEqual(set(graph.lanes), {0, 1, 2})
                self.assertTrue(any(len(targets) > 1 for targets in graph.successors))
                self.assertIn(key, generator.XOR_INDEX_GROUPS_BY_BRANCH)

    def test_civil_and_electronics_programmes_have_visible_parallel_routes(self) -> None:
        for key in ("reconstruction", "resources", "signals", "power"):
            with self.subTest(branch=key):
                graph = generator.BRANCH_GRAPHS[key]
                self.assertEqual(set(graph.lanes), {0, 1, 2})
                self.assertTrue(any(len(targets) > 1 for targets in graph.successors))
                self.assertTrue(any(len(parents) > 1 for parents in graph.dependencies))

    def test_dense_horizontal_trunks_keep_their_authored_chronology(self) -> None:
        for key in (
            "small_arms",
            "squad_weapons",
            "protection",
            "special_forces",
            "recon_armor",
            "heavy_armor",
        ):
            with self.subTest(branch=key):
                branch = generator.BRANCH_BY_KEY[key]
                legacy = generator.LEGACY_BRANCH_BY_KEY[key]
                authored_year = {
                    tech.key: year
                    for tech, year in zip(legacy.techs, legacy.years, strict=True)
                }
                self.assertEqual(
                    branch.years,
                    tuple(authored_year[tech.key] for tech in branch.techs),
                )

    def test_horizontal_technology_positions_follow_the_left_grid_contract(self) -> None:
        small_arms = generator.BRANCH_BY_KEY["small_arms"]
        positions = {
            index: self._folder_positions(generator.render_technology(small_arms, index))[
                "infantry_folder"
            ]
            for index in (0, 3, 15)
        }
        self.assertEqual(
            positions,
            {
                0: (1, 0),
                3: (2, 15),
                15: (1, 57),
            },
        )

        armor = generator.BRANCH_BY_KEY["recon_armor"]
        for index in (0, len(armor.techs) // 2, len(armor.techs) - 1):
            positions = self._folder_positions(generator.render_technology(armor, index))
            self.assertEqual(positions["armour_folder"], positions["nsb_armour_folder"])

    def test_horizontal_programmes_share_visual_fork_and_merge_columns(self) -> None:
        branch = generator.BRANCH_BY_KEY["combat_armor"]
        graph = generator.BRANCH_GRAPHS[branch.key]

        fork_targets = graph.successors[2]
        self.assertEqual(len(fork_targets), 3)
        self.assertGreater(len({branch.years[index] for index in fork_targets}), 1)
        self.assertEqual(
            {
                generator.technology_grid_position(branch, index)[1]
                for index in fork_targets
            },
            {generator.technology_grid_position(branch, fork_targets[0])[1]},
        )

        merge_parents = tuple(
            index
            for index, targets in enumerate(graph.successors)
            if 15 in targets
        )
        self.assertEqual(len(merge_parents), 3)
        self.assertGreater(len({branch.years[index] for index in merge_parents}), 1)
        self.assertEqual(
            {
                generator.technology_grid_position(branch, index)[1]
                for index in merge_parents
            },
            {generator.technology_grid_position(branch, merge_parents[0])[1]},
        )

        for source, targets in enumerate(graph.successors):
            source_column = generator.technology_grid_position(branch, source)[1]
            for target in targets:
                self.assertLess(
                    source_column,
                    generator.technology_grid_position(branch, target)[1],
                )

    def test_personal_antitank_branch_fits_inside_two_visual_rows(self) -> None:
        graph = generator.BRANCH_GRAPHS["anti_tank_infantry"]

        self.assertEqual(set(graph.lanes), {0, 1})
        self.assertTrue(any(len(targets) > 1 for targets in graph.successors))
        self.assertTrue(any(len(parents) > 1 for parents in graph.dependencies))

    def test_validator_accepts_generator_visual_positions(self) -> None:
        for branch in generator.BRANCHES:
            for index, tech in enumerate(branch.techs):
                with self.subTest(technology=tech.id):
                    self.assertEqual(
                        validator.EXPECTED_TECH_GRID_POSITIONS[tech.id],
                        generator.technology_grid_position(branch, index),
                    )

    def test_main_land_programmes_have_real_forks_and_syntheses(self) -> None:
        expected_synthesis_parent_counts = {
            "small_arms": {15: 3},
            "squad_weapons": {11: 2, 14: 2},
            "protection": {15: 3},
            "special_forces": {15: 3},
            "recon_armor": {19: 3},
            "combat_armor": {15: 3},
            "heavy_armor": {19: 3},
        }
        for key, expected_syntheses in expected_synthesis_parent_counts.items():
            with self.subTest(branch=key):
                graph = generator.BRANCH_GRAPHS[key]
                self.assertEqual(set(graph.lanes), {0, 1, 2})
                self.assertTrue(any(len(targets) >= 2 for targets in graph.successors))
                parent_counts = {
                    target: sum(target in targets for targets in graph.successors)
                    for target in expected_syntheses
                }
                self.assertEqual(parent_counts, expected_syntheses)
                self.assertEqual(
                    {index for index, parents in enumerate(graph.dependencies) if parents},
                    set(expected_syntheses),
                )

        self.assertEqual(generator.XOR_INDEX_GROUPS_BY_BRANCH["combat_armor"], ((16, 17),))

    def test_horizontal_folder_grid_aligns_years_and_stacks_programmes(self) -> None:
        rendered = generator.render_folder("infantry_folder")
        year_positions = [
            (int(x), int(y))
            for x, y in re.findall(
                r'name = "ADISCORD_infantry_folder_year_\d+"\s*'
                r"position = \{ x = (\d+) y = (\d+) \}",
                rendered,
            )
        ]
        self.assertEqual(len(year_positions), len(generator.YEARS))
        self.assertEqual(len({y for _, y in year_positions}), 1)
        self.assertTrue(
            all(right - left >= 3 * generator.GRID_SLOT for left, right in zip(
                (x for x, _ in year_positions),
                (x for x, _ in year_positions[1:]),
            ))
        )

        grid_positions = [
            (int(x), int(y))
            for x, y in re.findall(
                r'name = "ADISCORD_tech_[A-Za-z0-9_]+_tree"\s*'
                r"position = \{ x = (\d+) y = (\d+) \}",
                rendered,
            )
        ]
        self.assertGreaterEqual(len(grid_positions), 5)
        self.assertEqual(len({x for x, _ in grid_positions}), 1)
        self.assertEqual([y for _, y in grid_positions], sorted(y for _, y in grid_positions))

        horizontal_formats = re.findall(
            r'gridboxtype\s*=\s*\{.*?name = "ADISCORD_tech_[A-Za-z0-9_]+_tree"'
            r'.*?format = "([A-Z]+)"',
            rendered,
            flags=re.DOTALL,
        )
        self.assertEqual(horizontal_formats, ["LEFT"] * len(grid_positions))
        horizontal_slot_heights = [
            int(height)
            for height in re.findall(
                r'name = "ADISCORD_tech_[A-Za-z0-9_]+_tree".*?'
                r'slotsize = \{ width = \d+ height = (\d+) \}',
                rendered,
                flags=re.DOTALL,
            )
        ]
        self.assertEqual(len(horizontal_slot_heights), len(grid_positions))
        self.assertTrue(all(height >= 96 for height in horizontal_slot_heights))

        vertical = generator.render_folder("support_folder")
        vertical_formats = re.findall(
            r'gridboxtype\s*=\s*\{.*?name = "ADISCORD_tech_[A-Za-z0-9_]+_tree"'
            r'.*?format = "([A-Z]+)"',
            vertical,
            flags=re.DOTALL,
        )
        self.assertTrue(vertical_formats)
        self.assertEqual(vertical_formats, ["UP"] * len(vertical_formats))

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
        self.assertEqual(payload["active_country_count"], 69)
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

    def test_mechanized_programme_is_dense_and_unlocks_three_generations(self) -> None:
        branches = {branch.key: branch for branch in generator.BRANCHES}
        programme = branches.get("mechanized_mobility")
        self.assertIsNotNone(programme)
        self.assertEqual(len(programme.techs), 12)
        self.assertEqual(
            programme.years,
            (2160, 2162, 2164, 2166, 2166, 2168, 2170, 2170, 2172, 2172, 2174, 2175),
        )
        self.assertEqual(
            [
                tech.id
                for tech in programme.techs
                if tech.id in generator.ENABLE_EQUIPMENT
            ],
            [
                "ADISCORD_tech_armored_carrier_program",
                "ADISCORD_tech_infantry_combat_vehicle_program",
                "ADISCORD_tech_networked_mechanized_cells",
            ],
        )
        self.assertEqual(
            generator.ENABLE_EQUIPMENT[programme.techs[0].id],
            ("ADISCORD_armored_carrier_2163",),
        )
        self.assertEqual(
            generator.ENABLE_SUBUNITS[programme.techs[0].id],
            ("ADISCORD_mechanized_infantry",),
        )

    def test_only_strongest_starting_powers_receive_armored_core(self) -> None:
        expected = {"IVN", "VAD", "WRK"}
        actual = {
            tag
            for tag, profiles in generator.STARTING_COUNTRY_TECH_PROFILES.items()
            if "armored_core" in profiles
        }
        self.assertEqual(actual, expected)
        profile = set(generator.STARTING_TECH_PROFILES["armored_core"])
        self.assertIn("ADISCORD_tech_armored_carrier_program", profile)
        self.assertIn("ADISCORD_tech_semi_autonomous_combat_modules", profile)

    def test_small_arms_and_personal_antitank_use_real_engineering_names(self) -> None:
        small_arms = generator.BRANCH_BY_KEY["small_arms"]
        self.assertEqual(
            [tech.ru for tech in small_arms.techs],
            [
                "Прецизионная нарезка каналов стволов",
                "Обтюрация казённой части",
                "Унитарный металлический патрон",
                "Нитроцеллюлозные метательные составы",
                "Лазерное измерение дальности",
                "Промежуточные патроны",
                "Высокопрочные ствольные стали",
                "Самозарядная автоматика",
                "Вычислительное определение баллистической поправки",
                "Газоотводная автоматика",
                "Запирание поворотным затвором",
                "Интегрированные электронно-оптические прицелы",
                "Хромирование и износостойкие покрытия ствола",
                "Оптимизация импульса отдачи",
                "Полимерные и гибридные гильзы",
                "Программируемые боеприпасы",
            ],
        )

        anti_tank = generator.BRANCH_BY_KEY["anti_tank_infantry"]
        self.assertEqual(anti_tank.ru, "Индивидуальные противотанковые средства")
        self.assertEqual(
            [tech.ru for tech in anti_tank.techs],
            [
                "Бутылочные зажигательные смеси",
                "Динамитные и ранцевые подрывные заряды",
                "Ручные кумулятивные противотанковые гранаты",
                "Крупнокалиберные противотанковые ружья",
                "Командное наведение по проводной линии",
                "Безоткатные противотанковые системы",
                "Полуавтоматическое наведение по линии визирования",
                "Реактивные гранатомёты с кумулятивной боевой частью",
                "Инфракрасное самонаведение верхней атаки",
                "Тандемные кумулятивные боевые части",
                "Барражирующие противотанковые боеприпасы",
                "Кооперативное мультиспектральное целеуказание",
            ],
        )

    def test_weapon_technologies_have_authored_technical_descriptions(self) -> None:
        keys = {
            tech.key
            for branch_key in ("small_arms", "anti_tank_infantry")
            for tech in generator.BRANCH_BY_KEY[branch_key].techs
        }
        descriptions = getattr(generator, "TECHNICAL_TECH_DESCRIPTIONS", {})
        self.assertEqual(keys, keys & set(descriptions))

        for language in ("russian", "english"):
            rendered = "\n".join(generator.generated_localisation(language))
            language_index = 0 if language == "russian" else 1
            for key in keys:
                with self.subTest(language=language, technology=key):
                    self.assertIn(
                        descriptions[key][language_index],
                        rendered,
                    )

    def test_service_weapon_milestones_unlock_nine_ordered_generations(self) -> None:
        equipment_ids = (
            "infantry_equipment_0",
            "ADISCORD_infantry_equipment_2156",
            "ADISCORD_infantry_equipment_2163",
            "ADISCORD_infantry_equipment_2168",
            "ADISCORD_infantry_equipment_2170",
            "ADISCORD_infantry_equipment_2178",
            "ADISCORD_infantry_equipment_2183",
            "ADISCORD_infantry_equipment_2193",
            "ADISCORD_infantry_equipment_2200",
        )
        milestone_keys = (
            "postwar_weapon_standardization",
            "refurbished_receivers",
            "sealed_receiver_assemblies",
            "smart_recoil_compensators",
            "smart_optics",
            "modular_rifle_kits",
            "programmable_ammunition",
            "coil_assisted_service_rifles",
            "networked_service_rifles",
        )
        icon_keys = (
            "reclaimed_arsenal",
            "recovered_service_rifle",
            "standardized_battle_rifle",
            "transitional_modular_weapon",
            "suppressed_assault_system",
            "networked_smart_rifle",
            "programmable_munition_weapon",
            "advanced_impulse_weapon",
            "resilient_combat_network_weapon",
        )
        blocks = validator.collect_equipment_blocks()

        self.assertTrue(set(equipment_ids) <= set(blocks))
        for previous, current in zip(equipment_ids, equipment_ids[1:]):
            self.assertRegex(blocks[current], rf"\bparent\s*=\s*{previous}\b")
        for tier, (tech_key, equipment_id, icon_key) in enumerate(
            zip(milestone_keys, equipment_ids, icon_keys, strict=True),
            start=1,
        ):
            tech_id = f"ADISCORD_tech_{tech_key}"
            self.assertEqual(generator.ENABLE_EQUIPMENT.get(tech_id), (equipment_id,))
            self.assertEqual(
                generator.EQUIPMENT_UNLOCK_ICONS.get(tech_id),
                f"ADISCORD_weapon_{tier:02d}_{icon_key}",
            )

    def test_infantry_equipment_visual_levels_mark_real_weapon_generations(self) -> None:
        equipment_ids = (
            "infantry_equipment_0",
            "ADISCORD_infantry_equipment_2156",
            "ADISCORD_infantry_equipment_2163",
            "ADISCORD_infantry_equipment_2168",
            "ADISCORD_infantry_equipment_2170",
            "ADISCORD_infantry_equipment_2178",
            "ADISCORD_infantry_equipment_2183",
            "ADISCORD_infantry_equipment_2193",
            "ADISCORD_infantry_equipment_2200",
        )
        blocks = validator.collect_equipment_blocks()
        actual_levels = [
            int(re.search(r"\bvisual_level\s*=\s*(\d+)", blocks[equipment]).group(1))
            for equipment in equipment_ids
        ]

        self.assertEqual(actual_levels, [0, 1, 2, 2, 2, 3, 3, 3, 3])

    def test_custom_uniform_countries_have_late_automatic_entities(self) -> None:
        asset = (
            ROOT / "gfx" / "entities" / "zz_ADISCORD_country_infantry.asset"
        ).read_text(encoding="utf-8")
        blocks = {}
        for match in re.finditer(r"(?m)^\s*entity\s*=\s*\{", asset):
            block = validator.extract_block(asset, match.start())
            name = re.search(r'\bname\s*=\s*"([A-Za-z0-9_]+)"', block)
            if name:
                blocks[name.group(1)] = block

        expected_clones = {
            "STP_infantry_3_entity": "STP_infantry_2_entity",
            "NOD_infantry_3_entity": "STP_infantry_3_entity",
            "VAL_infantry_3_entity": "VAL_infantry_2_entity",
        }
        for entity, parent in expected_clones.items():
            with self.subTest(entity=entity):
                self.assertIn(entity, blocks)
                self.assertRegex(blocks[entity], rf'\bclone\s*=\s*"{parent}"')

    def test_squad_weapon_milestones_unlock_nine_ordered_generations(self) -> None:
        equipment_ids = (
            "ADISCORD_squad_weapons_equipment_0",
            "ADISCORD_squad_weapons_equipment_2156",
            "ADISCORD_squad_weapons_equipment_2163",
            "ADISCORD_squad_weapons_equipment_2168",
            "ADISCORD_squad_weapons_equipment_2170",
            "ADISCORD_squad_weapons_equipment_2178",
            "ADISCORD_squad_weapons_equipment_2183",
            "ADISCORD_squad_weapons_equipment_2193",
            "ADISCORD_squad_weapons_equipment_2200",
        )
        milestone_keys = (
            "belt_fed_recovery",
            "squad_grenade_launchers",
            "portable_at_cells",
            "recoilless_squad_launchers",
            "field_ew_units",
            "remote_weapon_tripods",
            "autonomous_support_weapons",
            "robotic_heavy_weapon_teams",
            "swarm_fireteams",
        )
        icon_keys = (
            "recovered_fire_support",
            "belt_fed_sections",
            "standardized_heavy_weapons",
            "modular_support_weapons",
            "sensor_linked_fireteams",
            "programmable_support_systems",
            "networked_precision_support",
            "autonomous_fire_control",
            "swarm_coordinated_support",
        )
        blocks = validator.collect_equipment_blocks()

        self.assertTrue(set(equipment_ids) <= set(blocks))
        for previous, current in zip(equipment_ids, equipment_ids[1:]):
            self.assertRegex(blocks[current], rf"\bparent\s*=\s*{previous}\b")
        for tier, (tech_key, equipment_id, icon_key) in enumerate(
            zip(milestone_keys, equipment_ids, icon_keys, strict=True),
            start=1,
        ):
            tech_id = f"ADISCORD_tech_{tech_key}"
            self.assertEqual(generator.ENABLE_EQUIPMENT[tech_id], (equipment_id,))
            self.assertEqual(
                generator.EQUIPMENT_UNLOCK_ICONS[tech_id],
                f"ADISCORD_squad_{tier:02d}_{icon_key}",
            )

    def test_weapon_generation_names_are_concrete_and_generated_in_both_languages(self) -> None:
        expected_ids = {
            "infantry_equipment_0",
            "ADISCORD_infantry_equipment_2156",
            "ADISCORD_infantry_equipment_2163",
            "ADISCORD_infantry_equipment_2168",
            "ADISCORD_infantry_equipment_2170",
            "ADISCORD_infantry_equipment_2178",
            "ADISCORD_infantry_equipment_2183",
            "ADISCORD_infantry_equipment_2193",
            "ADISCORD_infantry_equipment_2200",
            "ADISCORD_squad_weapons_equipment_0",
            "ADISCORD_squad_weapons_equipment_2156",
            "ADISCORD_squad_weapons_equipment_2163",
            "ADISCORD_squad_weapons_equipment_2168",
            "ADISCORD_squad_weapons_equipment_2170",
            "ADISCORD_squad_weapons_equipment_2178",
            "ADISCORD_squad_weapons_equipment_2183",
            "ADISCORD_squad_weapons_equipment_2193",
            "ADISCORD_squad_weapons_equipment_2200",
        }
        self.assertEqual(set(generator.LAND_EQUIPMENT_LOCALISATION), expected_ids)
        for language in ("russian", "english"):
            rendered = "\n".join(generator.generated_localisation(language))
            for equipment_id in expected_ids:
                self.assertIn(f" {equipment_id}:0 ", rendered)
                self.assertIn(f" {equipment_id}_short:0 ", rendered)
                self.assertIn(f" {equipment_id}_desc:0 ", rendered)
        self.assertIn("БТ-63 «Рёв»", "\n".join(generator.generated_localisation("russian")))
        self.assertNotIn("Утильн", "\n".join(generator.generated_localisation("russian")))

    def test_service_weapon_descriptions_name_their_engineering_change(self) -> None:
        expected_terms = {
            "infantry_equipment_0": "нарез",
            "ADISCORD_infantry_equipment_2156": "обтюрац",
            "ADISCORD_infantry_equipment_2163": "промежуточ",
            "ADISCORD_infantry_equipment_2168": "самозаряд",
            "ADISCORD_infantry_equipment_2170": "лазер",
            "ADISCORD_infantry_equipment_2178": "газоотвод",
            "ADISCORD_infantry_equipment_2183": "хром",
            "ADISCORD_infantry_equipment_2193": "отдач",
            "ADISCORD_infantry_equipment_2200": "программируем",
        }
        for equipment_id, term in expected_terms.items():
            with self.subTest(equipment=equipment_id):
                description = generator.LAND_EQUIPMENT_LOCALISATION[equipment_id][4].lower()
                self.assertIn(term, description)
                self.assertNotRegex(description, r"сетев|распределён|огневой контур")

    def test_armor_station_names_describe_turret_installations(self) -> None:
        rendered = "\n".join(generator.generated_localisation("russian"))

        self.assertIn(
            'ADISCORD_tech_remote_weapon_stations:0 "Дистанционно управляемые башенные установки"',
            rendered,
        )
        self.assertIn(
            'ADISCORD_tech_unmanned_weapon_stations:0 "Необитаемые башенные установки"',
            rendered,
        )
        self.assertNotIn("боевые модули", rendered.lower())


if __name__ == "__main__":
    unittest.main()
