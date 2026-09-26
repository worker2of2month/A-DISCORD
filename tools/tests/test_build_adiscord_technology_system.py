from __future__ import annotations

import json
import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tools.builders import build_adiscord_technology_system as generator
from tools.builders import build_adiscord_technology_ui_assets as ui_builder
from tools.validators import validate_adiscord_tech_doctrine as validator


ROOT = Path(__file__).resolve().parents[2]
LEGACY_MANIFEST = ROOT / "tools" / "data" / "adiscord_technology_legacy_manifest.json"
STARTING_PROFILE_MANIFEST = ROOT / "tools" / "data" / "adiscord_starting_technology_profiles.json"


class CompactTechnologyTreeContractTests(unittest.TestCase):
    def test_weapon_programmes_target_registered_subunits(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        units = {}
        for filename in ("ADISCORD_air_units.txt", "ADISCORD_naval_units.txt"):
            source = (ROOT / "common/units" / filename).read_text(encoding="utf-8-sig")
            for root in parse_clausewitz(source):
                for unit in root.value:
                    units[unit.key] = unit.value
        for branch in generator.BRANCHES:
            for index, tech in enumerate(branch.techs):
                if tech.key not in generator.NAVAL_AIR_WEAPON_EFFECTS:
                    continue
                for effect in generator.effects_for(branch, index):
                    for entry in parse_clausewitz(effect):
                        if isinstance(entry.value, list):
                            with self.subTest(technology=tech.id, target=entry.key):
                                self.assertIn(entry.key, set(units))


    @staticmethod
    def _named_gui_block(text: str, kind: str, name: str) -> str:
        for match in re.finditer(rf"\b{kind}\s*=\s*\{{", text):
            block = validator.extract_block(text, match.start())
            if re.search(rf'\bname\s*=\s*"{re.escape(name)}"', block):
                return block
        raise AssertionError(f"Missing {kind}: {name}")

    def test_native_grid_cross_axis_is_centered_beneath_each_branch_title(self) -> None:
        for folder in generator.FOLDER_BACKGROUNDS:
            rendered = generator.render_folder(folder)
            horizontal = folder in generator.HORIZONTAL_FOLDERS
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = self._named_gui_block(rendered, "gridboxtype", branch.techs[0].id + "_tree")
                size = re.search(r"size = \{ width = (\d+) height = (\d+) \}", grid)
                cross_size = int(size[2 if horizontal else 1])
                # Native cross-axis slot zero lies at the gridbox centre.
                centers = [
                    cross_size / 2 + generator.technology_grid_position(branch, i)[0] * 70
                    for i in range(len(branch.techs))
                ]
                half_card = 42 if horizontal else 102
                with self.subTest(folder=folder, branch=branch.key):
                    self.assertEqual((min(centers) + max(centers)) / 2, cross_size / 2)
                    self.assertGreaterEqual(min(centers) - half_card, 0)
                    self.assertLessEqual(max(centers) + half_card, cross_size)

    def test_horizontal_ruler_dates_match_every_technology_start_year(self) -> None:
        for branch in generator.BRANCHES:
            if not generator.HORIZONTAL_FOLDERS.intersection(branch.folders):
                continue
            for index, tech in enumerate(branch.techs):
                text = generator.render_technology(branch, index)
                year = int(re.search(r"\bstart_year = (\d+)", text)[1])
                with self.subTest(technology=tech.id):
                    self.assertEqual(
                        generator.technology_time_slot(branch, index),
                        generator.YEAR_TO_Y[year] * 3,
                    )

    def test_year_label_centres_align_with_native_technology_cells(self) -> None:
        for folder in generator.FOLDER_BACKGROUNDS:
            rendered = generator.render_folder(folder)
            horizontal = folder in generator.HORIZONTAL_FOLDERS
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = self._named_gui_block(rendered, "gridboxtype", branch.techs[0].id + "_tree")
                origin = re.search(r"position = \{ x = (-?\d+) y = (-?\d+) \}", grid)
                for index, year in enumerate(branch.years):
                    label_id = str(year) if horizontal else f"{branch.key}_{year}"
                    label = self._named_gui_block(
                        rendered, "instantTextBoxType", f"ADISCORD_{folder}_year_{label_id}"
                    )
                    pos = re.search(r"position = \{ x = (-?\d+) y = (-?\d+) \}", label)
                    extent = int(re.search(
                        r"maxWidth = (\d+)" if horizontal else r"maxHeight = (\d+)", label
                    )[1])
                    axis = 1 if horizontal else 2
                    cell_center = int(origin[axis]) + generator.technology_time_slot(branch, index) * 70 + 35
                    with self.subTest(folder=folder, technology=branch.techs[index].id):
                        self.assertEqual(int(pos[axis]) + extent / 2, cell_center)
                        self.assertIn(f'text = "{year}"', label)

    def test_ui_validator_rejects_swapped_dates_displaced_labels_and_wrong_titles(self) -> None:
        original = "\n".join(generator.render_folder(folder) for folder in generator.FOLDER_BACKGROUNDS)
        label_a = self._named_gui_block(original, "instantTextBoxType", "ADISCORD_industry_folder_year_production_2150")
        label_b = self._named_gui_block(original, "instantTextBoxType", "ADISCORD_industry_folder_year_production_2155")
        swapped = original.replace(label_a, label_a.replace('text = "2150"', 'text = "2155"'))
        swapped = swapped.replace(label_b, label_b.replace('text = "2155"', 'text = "2150"'))
        displaced = original.replace(label_a, re.sub(r"position = \{ x = -?\d+", "position = { x = 999", label_a))
        title = self._named_gui_block(original, "instantTextBoxType", "ADISCORD_branch_production")
        wrong_title = original.replace(title, title.replace("ADISCORD_TECH_BRANCH_PRODUCTION", "ADISCORD_TECH_BRANCH_RECONSTRUCTION"))
        grid = self._named_gui_block(original, "gridboxtype", "ADISCORD_tech_standardized_machine_tools_tree")
        displaced_grid = original.replace(grid, re.sub(r"position = \{ x = -?\d+", "position = { x = 999", grid))
        mutations = (
            ("swapped", swapped), ("displaced", displaced), ("wrong_title", wrong_title),
            ("displaced_grid", displaced_grid),
            ("missing", original.replace(label_a, "")),
            ("duplicate", original.replace(label_a, label_a + label_a)),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "interface/countrytechtreeview.gui"
            path.parent.mkdir()
            path.write_text(original, encoding="utf-8")
            with patch.object(validator, "ROOT", root):
                self.assertEqual(validator.check_technology_ui_years(), [])
                for name, broken in mutations:
                    with self.subTest(mutation=name):
                        path.write_text(broken, encoding="utf-8")
                        self.assertTrue(validator.check_technology_ui_years())

    def test_gui_regeneration_from_repository_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "interface/countrytechtreeview.gui"
            output.parent.mkdir()
            output.write_bytes((ROOT / "interface/countrytechtreeview.gui").read_bytes())
            with patch.object(generator, "ROOT", root), patch.object(
                generator, "BASE_GAME", root / "uninstalled_game"
            ):
                generator.write_gui()
                first = output.read_bytes()
                generator.write_gui()
                self.assertEqual(output.read_bytes(), first)
            with patch.object(validator, "ROOT", root):
                self.assertEqual(validator.check_technology_ui_years(), [])

    def test_vertical_programmes_do_not_reserve_empty_research_years(self) -> None:
        for branch in generator.BRANCHES:
            if generator.HORIZONTAL_FOLDERS.intersection(branch.folders):
                continue
            rows = sorted({generator.technology_time_slot(branch, i) for i in range(len(branch.techs))})
            with self.subTest(branch=branch.key):
                self.assertEqual(rows[0], 0)
                self.assertTrue(all((b - a) * generator.GRID_SLOT <= 140 for a, b in zip(rows, rows[1:])))

    def test_officer_training_delivers_all_four_leader_attributes(self) -> None:
        branch = generator.BRANCH_BY_KEY['officer_training']
        rendered = '\n'.join(generator.render_technology(branch, i) for i in range(len(branch.techs)))
        self.assertEqual(len(branch.techs), 8)
        for attribute in ('attack', 'defense', 'planning', 'logistics'):
            self.assertIn(f'add_{attribute} = 1', rendered)
        self.assertEqual(rendered.count('on_research_complete ='), 7)

    def test_single_lane_vertical_programme_has_no_empty_side_lane(self) -> None:
        branch = generator.BRANCH_BY_KEY["public_finance"]
        self.assertEqual(generator.technology_grid_position(branch, 0), (0, 0))
        rendered = generator.render_folder("industry_folder")
        self.assertRegex(rendered, rf'name = "{branch.techs[0].id}_tree"\s*position = \{{[^}}]+\}}\s*size = \{{ width = 210 ')

    def test_naval_research_unlocks_multiple_producible_generations(self) -> None:
        blocks = validator.collect_equipment_blocks()
        for key in ('naval_support', 'surface_fleet', 'subsurface'):
            branch = generator.BRANCH_BY_KEY[key]
            unlocked = {equipment for tech in branch.techs for equipment in generator.ENABLE_EQUIPMENT.get(tech.id, ())}
            with self.subTest(branch=key):
                self.assertGreaterEqual(len(unlocked), 4)
                for equipment in unlocked:
                    self.assertIn(equipment, blocks)
                    self.assertNotRegex(blocks[equipment], r'active\s*=\s*yes')

    def test_aircraft_research_opens_bomber_and_maritime_production(self) -> None:
        blocks = validator.collect_equipment_blocks()
        for family in ('ADISCORD_bomber_archetype', 'ADISCORD_naval_aircraft_archetype'):
            variants = {key for key, block in blocks.items() if re.search(rf'archetype\s*=\s*{family}\b', block)}
            self.assertGreaterEqual(len(variants), 3, family)
            unlocks = {equipment for items in generator.ENABLE_EQUIPMENT.values() for equipment in items}
            self.assertTrue(variants <= unlocks, variants - unlocks)

    def test_new_equipment_has_deployable_units_and_native_missions(self) -> None:
        equipment = validator.collect_equipment_blocks()
        units = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "common/units").glob("*.txt"))
        roles = {
            "ADISCORD_cruiser_archetype": ("heavy_cruiser", None),
            "ADISCORD_submarine_archetype": ("submarine", None),
            "ADISCORD_bomber_archetype": ("ADISCORD_tactical_bomber", {"strategic_bomber", "cas", "attack_logistics"}),
            "ADISCORD_naval_aircraft_archetype": ("nav_bomber", {"naval_bomber", "port_strike", "naval_patrol"}),
        }
        for family, (unit, missions) in roles.items():
            match = re.search(rf"\b{unit}\s*=\s*\{{", units)
            self.assertIsNotNone(match, unit)
            unit_block = validator.extract_block(units, match.start())
            self.assertRegex(unit_block, rf"need\s*=\s*\{{\s*{family}\s*=\s*1\s*\}}")
            for key, block in equipment.items():
                if not re.search(rf"\barchetype\s*=\s*{family}\b", block):
                    continue
                self.assertRegex(block, r"\bactive\s*=\s*no\b", key)
                if missions:
                    declared = re.search(r"allow_mission_type\s*=\s*\{([^}]+)\}", block)
                    self.assertIsNotNone(declared, key)
                    self.assertEqual(set(declared[1].split()), missions, key)
                else:
                    self.assertIn("critical_parts", unit_block)
        naval = equipment["ADISCORD_naval_aircraft_2172"]
        self.assertRegex(naval, r"\bnaval_strike_attack\s*=\s*[1-9]")
        self.assertNotRegex(naval, r"\bnaval_attack\s*=")

    def test_new_programmes_are_researched_instead_of_granted_to_every_country(self) -> None:
        common = set(generator.STARTING_TECH_PROFILES["common"])
        self.assertNotIn("ADISCORD_tech_reconstituted_staff_academies", common)
        self.assertNotIn("ADISCORD_tech_twin_engine_aircraft", common)
        self.assertNotIn("ADISCORD_tech_casualty_evacuation", common)
        self.assertIn("ADISCORD_tech_casualty_evacuation", generator.STARTING_TECH_PROFILES["land"])

    def test_cruiser_and_submarine_ai_groups_are_optional_reinforcements(self) -> None:
        taskforces = (ROOT / "common/ai_navy/taskforce/ADISCORD_taskforce_templates.txt").read_text(encoding="utf-8")
        fleets = (ROOT / "common/ai_navy/fleet/ADISCORD_fleet_templates.txt").read_text(encoding="utf-8")
        for taskforce, unit in (("ADISCORD_cruiser_strike", "heavy_cruiser"), ("ADISCORD_submarine_raiding", "submarine")):
            match = re.search(rf"\b{taskforce}\s*=\s*\{{", taskforces)
            self.assertIsNotNone(match, taskforce)
            block = validator.extract_block(taskforces, match.start())
            self.assertRegex(block, rf"min_composition\s*=\s*\{{\s*{unit}\s*=\s*\{{\s*amount\s*=\s*1")
            self.assertRegex(block, r"NOT\s*=\s*\{\s*has_tech\s*=")
            self.assertRegex(fleets, rf"optional_taskforces\s*=\s*\{{[^}}]*\b{taskforce}\s*=\s*1")
            self.assertNotRegex(fleets, rf"required_taskforces\s*=\s*\{{[^}}]*\b{taskforce}\s*=")

    def test_budget_research_has_bounded_consumed_modifiers_and_refreshes_cache(self) -> None:
        branch = generator.BRANCH_BY_KEY.get("public_finance")
        self.assertIsNotNone(branch, "Public finance must be a playable research line")
        definitions = (ROOT / "common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt").read_text(encoding="utf-8-sig")
        consumers = (ROOT / "common/scripted_effects/ADISCORD_economy_modifier_effects.txt").read_text(encoding="utf-8-sig")
        totals: dict[str, float] = {}
        for index, tech in enumerate(branch.techs):
            rendered = generator.render_technology(branch, index)
            modifiers = re.findall(r"(ADISCORD_economy_\w+) = (-?[\d.]+)", rendered)
            self.assertGreaterEqual(len(modifiers), 2, tech.id)
            for name, value in modifiers:
                self.assertIn(name + " = {", definitions)
                self.assertIn("modifier@" + name, consumers)
                totals[name] = totals.get(name, 0) + float(value)
            self.assertEqual(rendered.count("on_research_complete = {"), 1)
            self.assertEqual(rendered.count("ADISCORD_economy_mark_dirty = yes"), 1)
            self.assertNotIn("add_to_variable", rendered)
        self.assertTrue(all(abs(value) <= 0.20 for value in totals.values()), totals)

    def test_rare_material_supply_precedes_equipment_and_has_research_gates(self) -> None:
        buildings = validator.collect_building_blocks()
        equipment = validator.collect_equipment_blocks()
        for resource, building, unlock in (
            ("rare_components", "ADISCORD_rare_components_plant", "ADISCORD_tech_rare_components_industry"),
            ("rare_alloys", "ADISCORD_rare_alloy_foundry", "ADISCORD_tech_rare_alloy_metallurgy"),
        ):
            with self.subTest(resource=resource):
                self.assertIn(unlock, generator.CURRENT_TECH_IDS)
                self.assertIn((building, 1), generator.ENABLE_BUILDINGS[unlock])
                self.assertIn("hide_if_missing_tech = yes", buildings[building])
                branch, index = generator.TECH_POSITION_BY_ID[unlock]
                supply_year = branch.years[index]
                consumers = []
                for tech_id, items in generator.ENABLE_EQUIPMENT.items():
                    for item in items:
                        block = equipment[item]
                        archetype = re.search(r"archetype = (\w+)", block)
                        if "resources =" not in block and archetype:
                            block = equipment[archetype.group(1)]
                        if re.search(rf"\b{resource} = [1-9]", block):
                            consumer_branch, consumer_index = generator.TECH_POSITION_BY_ID[tech_id]
                            consumers.append(item)
                            self.assertLess(supply_year, consumer_branch.years[consumer_index], item)
                self.assertGreater(len(set(consumers)), 4)
                upgrades = [amount for entries in generator.BUILDING_RESOURCE_UPGRADES.values()
                            for target, res, amount in entries if target == building and res == resource]
                self.assertTrue(upgrades)
                self.assertLessEqual(sum(upgrades), 4)

    def test_inherited_material_plants_and_budget_profile_grants_remain_usable(self) -> None:
        unlocks = {"ADISCORD_tech_rare_components_industry", "ADISCORD_tech_rare_alloy_metallurgy"}
        for tag in ("WRK", "RIV"):
            starting = set(generator.STARTING_TECH_PROFILES["common"])
            for profile in generator.STARTING_COUNTRY_TECH_PROFILES[tag]:
                starting.update(generator.STARTING_TECH_PROFILES[profile])
            self.assertTrue(unlocks <= starting, tag)
        branch, index = generator.TECH_POSITION_BY_ID["ADISCORD_tech_predictive_maintenance"]
        rendered = generator.render_technology(branch, index)
        self.assertEqual(rendered.count("on_research_complete = {"), 1)
        self.assertIn("add_tech_bonus = {", rendered)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", rendered)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "common/scripted_effects").mkdir(parents=True)
            with patch.object(generator, "ROOT", root):
                generator.write_starting_technology_effect()
            text = (root / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt").read_text(encoding="utf-8")
        common = validator.extract_block(text, text.index("ADISCORD_grant_technology_profile_common = {"))
        self.assertIn("has_variable = ADISCORD_economy_initialized", common)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", common)

    def test_custom_technology_textures_are_runtime_dds(self) -> None:
        self.assertTrue(generator.CUSTOM_TECH_TEXTURES)
        for key, texture in generator.CUSTOM_TECH_TEXTURES.items():
            with self.subTest(technology=key):
                self.assertTrue(texture.endswith(".dds"), texture)
                path = ROOT / texture
                self.assertTrue(path.is_file(), path)
                self.assertEqual(path.read_bytes()[:4], b"DDS ", path)

    def test_country_uniform_sprites_resolve_to_regional_assets(self) -> None:
        from PIL import Image

        sprites = validator.collect_sprite_names()
        for tag in ("STP", "VAL"):
            regional = {name: texture for name, texture in sprites.items()
                        if name.startswith(f"GFX_{tag}_ADISCORD_tech_")}
            self.assertEqual(len(regional), 9)
            for name, texture in regional.items():
                self.assertEqual(
                    sprites[name.replace(f"GFX_{tag}_", "GFX_", 1)],
                    texture.replace(f"ADISCORD_{tag}_", "ADISCORD_", 1),
                )
                with Image.open(ROOT / texture) as artwork:
                    self.assertEqual(artwork.format, "DDS")
                    self.assertLessEqual(artwork.width, 190)
                    self.assertLessEqual(artwork.height, 84)

    def test_art_and_effects_follow_ids_after_reordering(self) -> None:
        for branch in generator.BRANCHES:
            reordered = replace(branch, techs=branch.techs[::-1], years=branch.years[::-1])
            for index, tech in enumerate(branch.techs):
                other = len(branch.techs) - 1 - index
                self.assertEqual(generator.effects_for(branch, index),
                                 generator.effects_for(reordered, other), tech.id)
                self.assertEqual(generator.icon_for_technology(branch, index),
                                 generator.icon_for_technology(reordered, other), tech.id)

    def test_equipment_family_localisation_replaces_old_names_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for language in ("russian", "english"):
                path = root / "localisation" / language / f"ADISCORD_technology_doctrine_l_{language}.yml"
                path.parent.mkdir(parents=True)
                path.write_text(
                    f'l_{language}:\n infantry_equipment: "Old name"\n unrelated_key: "Keep me"\n',
                    encoding="utf-8-sig",
                )
            with patch.object(generator, "ROOT", root):
                generator.write_localisation()
                first = {path: path.read_bytes() for path in root.rglob("*.yml")}
                generator.write_localisation()
            for path, data in first.items():
                self.assertEqual(path.read_bytes(), data)
                self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
                text = data.decode("utf-8-sig")
                self.assertEqual(len(re.findall(r"^ infantry_equipment:", text, re.MULTILINE)), 1)
                self.assertIn(' unrelated_key: "Keep me"', text)
                self.assertNotIn('"Old name"', text)

    @staticmethod
    def _folder_positions(rendered: str) -> dict[str, tuple[int, int]]:
        return {
            folder: (int(x), int(y))
            for folder, x, y in re.findall(
                r"folder\s*=\s*\{\s*name\s*=\s*([A-Za-z0-9_]+)\s*"
                r"position\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*y\s*=\s*(-?\d+)",
                rendered,
                flags=re.DOTALL,
            )
        }

    def test_system_builder_checks_ui_owned_state_gfx_snapshot_read_only(self) -> None:
        expected = ui_builder.expected_technology_state_gfx_bytes()
        self.assertEqual(generator.expected_technology_state_gfx_bytes(), expected)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "zz_ADISCORD_technology_states.gfx"
            path.write_bytes(expected)
            before = path.read_bytes()
            with patch.object(generator, "TECHNOLOGY_STATE_GFX", path):
                generator.ensure_technology_state_gfx_current()
                self.assertEqual(path.read_bytes(), before)
                path.write_bytes(b"drifted state declaration\n")
                with self.assertRaisesRegex(RuntimeError, "technology state GFX is stale"):
                    generator.ensure_technology_state_gfx_current()
                self.assertEqual(path.read_bytes(), b"drifted state declaration\n")

    def test_legacy_manifest_covers_the_pre_redesign_tree(self) -> None:
        payload = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
        rows = payload["technologies"]
        ids = [row["id"] for row in rows]
        self.assertEqual(payload["technology_count"], 625)
        self.assertEqual(len(ids), 625)
        self.assertEqual(len(ids), len(set(ids)))


    def test_grid_slots_match_the_native_connector_size(self) -> None:
        gui = (generator.BASE_GAME / "interface/countrytechtreeview.gui").read_text(
            encoding="utf-8-sig"
        )
        connector = re.search(
            r'name\s*=\s*"techtree_line_item"\s*'
            r'position\s*=\s*\{[^}]+\}\s*'
            r'size\s*=\s*\{\s*width\s*=\s*(\d+)\s*height\s*=\s*(\d+)\s*\}',
            gui,
        )
        self.assertIsNotNone(connector)
        connector_size = tuple(map(int, connector.groups()))
        for folder in generator.FOLDER_BACKGROUNDS:
            slots = re.findall(
                r'slotsize\s*=\s*\{\s*width\s*=\s*(\d+)\s*height\s*=\s*(\d+)\s*\}',
                generator.render_folder(folder),
            )
            self.assertTrue(slots, folder)
            for size in slots:
                with self.subTest(folder=folder, size=size):
                    self.assertEqual(tuple(map(int, size)), connector_size)

    def test_horizontal_rows_leave_space_around_equipment_cards(self) -> None:
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(encoding="utf-8-sig")
        for folder in generator.HORIZONTAL_FOLDERS:
            item = re.search(
                rf'name\s*=\s*"techtree_{folder}_item"\s*'
                r'position\s*=\s*\{[^}]+\}\s*'
                r'size\s*=\s*\{\s*width\s*=\s*\d+\s*height\s*=\s*(\d+)\s*\}',
                gui,
            )
            self.assertIsNotNone(item, folder)
            card_height = int(item[1])
            rendered = generator.render_folder(folder)
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = re.search(
                    rf'name = "{branch.techs[0].id}_tree".*?'
                    r'slotsize = \{ width = \d+ height = (\d+) \}',
                    rendered,
                    flags=re.DOTALL,
                )
                self.assertIsNotNone(grid, branch.key)
                rows = sorted({
                    self._folder_positions(generator.render_technology(branch, index))[folder][0]
                    * int(grid[1])
                    for index in range(len(branch.techs))
                })
                for first, second in zip(rows, rows[1:]):
                    with self.subTest(folder=folder, branch=branch.key):
                        self.assertGreaterEqual(second - first, card_height + 12)


    def test_validator_accepts_generator_visual_positions(self) -> None:
        for branch in generator.BRANCHES:
            for index, tech in enumerate(branch.techs):
                with self.subTest(technology=tech.id):
                    self.assertEqual(
                        validator.EXPECTED_TECH_GRID_POSITIONS[tech.id],
                        generator.technology_grid_position(branch, index),
                    )


    def test_every_node_fits_inside_its_own_declared_gridbox(self) -> None:
        for folder in generator.FOLDER_BACKGROUNDS:
            rendered = generator.render_folder(folder)
            horizontal = folder in generator.HORIZONTAL_FOLDERS
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = self._named_gui_block(
                    rendered, "gridboxtype", branch.techs[0].id + "_tree"
                )
                size = re.search(r"size = \{ width = (\d+) height = (\d+) \}", grid)
                width, height = int(size[1]), int(size[2])
                for index, tech in enumerate(branch.techs):
                    x, y = generator.technology_grid_position(branch, index)
                    if horizontal:
                        across, down = y * 70 + 35, height / 2 + x * 70
                    else:
                        across, down = width / 2 + x * 70, y * 70 + 35
                    with self.subTest(folder=folder, technology=tech.id):
                        self.assertGreaterEqual(across, 0)
                        self.assertLessEqual(across, width)
                        self.assertGreaterEqual(down, 0)
                        self.assertLessEqual(down, height)

    def test_consecutive_rungs_leave_room_for_their_connector(self) -> None:
        """Adjacent research years must not draw 72px icons 70px apart."""

        for branch in generator.BRANCHES:
            for source, targets in enumerate(
                generator.BRANCH_GRAPHS[branch.key].successors
            ):
                for target in targets:
                    if branch.years[source] == branch.years[target]:
                        continue
                    step = generator.technology_time_slot(
                        branch, target
                    ) - generator.technology_time_slot(branch, source)
                    with self.subTest(branch=branch.key, edge=(source, target)):
                        self.assertGreaterEqual(step, 2)

    def test_vertical_year_labels_sit_on_their_own_node_rows(self) -> None:
        rendered = generator.render_folder("industry_folder")
        label_rows = {
            (branch, int(year)): int(y)
            for branch, year, y in re.findall(
                r'name = "ADISCORD_industry_folder_year_([a-z_]+)_(\d+)"\s*'
                r"position = \{ x = \d+ y = (\d+) \}",
                rendered,
            )
        }
        # The sparse materials programme has four dated rows, not nineteen
        # empty calendar slots. Labels are independent from adjacent industry.
        self.assertEqual(label_rows[("advanced_materials", 2155)], 154)
        self.assertEqual(label_rows[("advanced_materials", 2173)], 574)
        for branch in [b for b in generator.BRANCHES if "industry_folder" in b.folders]:
            for index in range(len(branch.techs)):
                _, y = generator.technology_grid_position(branch, index)
                node_top = generator.GRID_Y + y * generator.GRID_SLOT
                with self.subTest(technology=branch.techs[index].id):
                    self.assertEqual(label_rows[(branch.key, branch.years[index])], node_top + 24)


    def test_only_industry_has_exclusive_research(self) -> None:
        self.assertEqual(generator.XOR_KIND_BY_BRANCH, {
            "production": "temporary", "industry_organization": "permanent",
        })
        _, blocks = validator.collect_technologies()
        self.assertEqual(validator.check_technology_graph_quality(blocks), [])

    def test_research_payoffs_stay_spendable_and_inside_their_category(self) -> None:
        payoffs = getattr(generator, "RESEARCH_PAYOFFS", {})
        self.assertTrue(payoffs)
        for tech_id, (category, bonus, uses) in payoffs.items():
            with self.subTest(technology=tech_id):
                self.assertIn(tech_id, generator.TECH_POSITION_BY_ID)
                branch, index = generator.TECH_POSITION_BY_ID[tech_id]
                # A discount handed out at the end of the tree cannot be spent.
                self.assertLessEqual(branch.years[index], 2174)
                self.assertIn(
                    category,
                    generator.CATEGORY_BY_PROFILE[branch.profile].split(),
                )
                self.assertGreater(bonus, 0)
                self.assertLessEqual(bonus, 0.5)
                self.assertGreaterEqual(uses, 1)

        # Every tab should have a reason to finish a programme, not just industry.
        folders = {
            folder
            for tech_id in payoffs
            for folder in generator.TECH_POSITION_BY_ID[tech_id][0].folders
        }
        self.assertGreaterEqual(len(folders), 5)

    def test_each_technology_keeps_a_single_research_completion_block(self) -> None:
        """A second ``on_research_complete`` would be discarded in silence.

        Clausewitz keeps only one such block per technology, so the building
        upgrades and the research payoff have to share it. The shared block also
        has to sit after the path entries, because the research-balance contract
        counts numeric leaf modifiers only up to the first path.
        """

        for branch in generator.BRANCHES:
            for index, tech in enumerate(branch.techs):
                block = generator.render_technology(branch, index)
                with self.subTest(technology=tech.id):
                    self.assertLessEqual(block.count("on_research_complete"), 1)
                    if "add_tech_bonus" in block and "path =" in block:
                        self.assertLess(
                            block.index("path ="),
                            block.index("on_research_complete"),
                        )

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
        self.assertEqual(payload["active_country_count"], len(payload["countries"]))
        self.assertEqual(set(payload["countries"]), set(generator.STARTING_COUNTRY_TECH_PROFILES))
        self.assertEqual(
            set(generator.STARTING_COUNTRY_TECH_PROFILE_RATIONALE),
            set(generator.STARTING_COUNTRY_TECH_PROFILES),
        )
        self.assertEqual(
            {tag for tag, profiles in generator.STARTING_COUNTRY_TECH_PROFILES.items() if not profiles},
            {"EXZ", "PWR"},
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
        self.assertEqual(len(programme.techs), 8)
        self.assertEqual(
            programme.years,
            (2160, 2162, 2164, 2166, 2168, 2170, 2172, 2175),
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
        expected = {"IVN", "NOD", "WRK"}
        actual = {
            tag
            for tag, profiles in generator.STARTING_COUNTRY_TECH_PROFILES.items()
            if "armored_core" in profiles
        }
        self.assertEqual(actual, expected)
        profile = set(generator.STARTING_TECH_PROFILES["armored_core"])
        self.assertIn("ADISCORD_tech_armored_carrier_program", profile)
        self.assertIn("ADISCORD_tech_semi_autonomous_combat_modules", profile)

    def test_stp_starting_profile_unlocks_its_capital_guard_recon_platform(self) -> None:
        granted = set(generator.STARTING_TECH_PROFILES["common"])
        for profile in generator.STARTING_COUNTRY_TECH_PROFILES["STP"]:
            granted.update(generator.STARTING_TECH_PROFILES[profile])
        self.assertIn("ADISCORD_tech_drone_recon_swarms", granted)


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

        self.assertEqual(actual_levels, [0, 0, 1, 2, 3, 4, 5, 6, 7])

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
        expected_ids.update({"motorized_equipment", "motorized_equipment_1"})
        self.assertEqual(set(generator.LAND_EQUIPMENT_LOCALISATION), expected_ids)
        for language in ("russian", "english"):
            rendered = "\n".join(generator.generated_localisation(language))
            for equipment_id in expected_ids:
                self.assertIn(f" {equipment_id}:0 ", rendered)
                self.assertIn(f" {equipment_id}_short:0 ", rendered)
                self.assertIn(f" {equipment_id}_desc:0 ", rendered)
        russian = "\n".join(generator.generated_localisation("russian"))
        english = "\n".join(generator.generated_localisation("english"))
        self.assertIn("АВ-63 «Рёв»", russian)
        self.assertIn("КОП-70 «Гул»", russian)
        self.assertIn("AR-63 “Roar”", english)
        self.assertIn("FSC-70 “Rumble”", english)
        equipment_names = "\n".join(
            value
            for values in generator.LAND_EQUIPMENT_LOCALISATION.values()
            for value in values[:4]
        )
        self.assertNotIn("БТ-", equipment_names)
        self.assertNotIn("КГ-", equipment_names)
        self.assertNotIn("Утильн", russian)

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


    def test_compact_scope_and_explicit_specializations(self) -> None:
        count = sum(len(branch.techs) for branch in generator.BRANCHES)
        self.assertGreaterEqual(count, 300)
        self.assertLess(count, 595)
        forks = set()
        for branch in generator.BRANCHES:
            graph = generator.BRANCH_GRAPHS[branch.key]
            if any(len(targets) > 1 for targets in graph.successors):
                forks.add(branch.key)
        self.assertTrue({
            "production", "industry_organization", "advanced_materials", "bomber_maritime",
            "small_arms", "squad_weapons", "night_combat", "anti_tank_infantry",
            "protection", "special_forces", "combat_armor", "artillery",
        } <= forks)

    def test_infantry_components_remain_independent_research_programmes(self) -> None:
        for target, unrelated in (
            ("sealed_receiver_assemblies", "smart_optics"),
            ("squad_target_sharing", "counter_illumination_warnings"),
            ("programmable_anti_armor_fuzes", "fire_and_forget_seekers"),
            ("hard_kill_protection_arrays", "adaptive_fire_control"),
            ("counterbattery_radar_links", "assisted_projectiles"),
        ):
            required = generator.technology_prerequisite_closure((f"ADISCORD_tech_{target}",))
            self.assertNotIn(f"ADISCORD_tech_{unrelated}", required)
        integrated = generator.technology_prerequisite_closure(("ADISCORD_tech_networked_service_rifles",))
        self.assertTrue({
            "ADISCORD_tech_coil_assisted_service_rifles",
            "ADISCORD_tech_integrated_target_designation",
            "ADISCORD_tech_hybrid_kinetic_energy_carbines",
        } <= set(integrated))

    def test_infantry_and_armor_retain_horizontal_programme_layouts(self) -> None:
        self.assertTrue({"infantry_folder", "armour_folder"} <= generator.HORIZONTAL_FOLDERS)
        self.assertNotIn("industry_folder", generator.HORIZONTAL_FOLDERS)
        infantry = {b.key for b in generator.BRANCHES if "infantry_folder" in b.folders}
        self.assertIn("special_forces", infantry)
        self.assertEqual(len(generator.BRANCH_BY_KEY["small_arms"].techs), 16)
        for branch in generator.BRANCHES:
            cells = [generator.technology_grid_position(branch, i) for i in range(len(branch.techs))]
            self.assertEqual(len(cells), len(set(cells)), branch.key)

    def test_medicine_and_rail_guns_have_one_semantic_owner(self) -> None:
        medicine = generator.BRANCH_BY_KEY["combat_medicine"]
        self.assertEqual(medicine.folders, ("support_folder",))
        medical_ids = {tech.key for tech in medicine.techs}
        self.assertTrue({"casualty_evacuation", "battlefield_medical_drones",
                         "smart_tourniquet_systems"}.issubset(medical_ids))
        for branch_key in ("protection", "field_support"):
            for tech in generator.BRANCH_BY_KEY[branch_key].techs:
                self.assertNotIn("field_hospital", " ".join(tech.effects))
        rail = generator.BRANCH_BY_KEY["rail"]
        for tech in rail.techs:
            self.assertNotIn("artillery", " ".join(tech.effects))
        guns = generator.BRANCH_BY_KEY["railway_artillery"]
        self.assertEqual(guns.folders, ("artillery_folder",))
        self.assertEqual(
            {equipment for tech in guns.techs
             for equipment in generator.ENABLE_EQUIPMENT.get(tech.id, ())},
            {"railway_gun_equipment_1", "ADISCORD_railway_gun_equipment_2200"},
        )

    def test_every_producible_family_and_building_cap_remains_reachable(self) -> None:
        _, blocks = validator.collect_technologies()
        self.assertEqual(validator.check_equipment_unlocks(
            blocks, validator.collect_equipment_keys()), [])
        self.assertEqual(validator.check_generated_capability_unlock_contract(blocks), [])
        self.assertTrue(set(generator.ENABLE_EQUIPMENT) <= generator.CURRENT_TECH_IDS)
        self.assertTrue(set(generator.ENABLE_SUBUNITS) <= generator.CURRENT_TECH_IDS)
        self.assertTrue(set(generator.ENABLE_BUILDINGS) <= generator.CURRENT_TECH_IDS)
        for building, minimum in (("radar_station", 6), ("rocket_site", 3),
                                  ("anti_air_building", 5), ("synthetic_refinery", 3)):
            caps = [level for entries in generator.ENABLE_BUILDINGS.values()
                    for name, level in entries if name == building]
            self.assertEqual(max(caps), minimum)

    def test_all_technology_cards_use_available_artwork(self) -> None:
        sprites = validator.collect_sprite_names()
        for branch in generator.BRANCHES:
            for tech in branch.techs:
                texture = sprites[f"GFX_{tech.id}_medium"]
                self.assertTrue(validator.texture_has_valid_dimensions(texture), texture)
                self.assertTrue((ROOT / texture).is_file()
                                or (generator.BASE_GAME / texture).is_file(), texture)

    def test_vertical_layout_rejects_wrong_branch_coordinates(self) -> None:
        _, blocks = validator.collect_technologies()
        tech_id = "ADISCORD_tech_postwar_weapon_standardization"
        broken = dict(blocks)
        broken[tech_id] = broken[tech_id].replace(
            "position = { x = 0 y = 0 }", "position = { x = 2 y = 0 }", 1)
        self.assertNotEqual(broken[tech_id], blocks[tech_id])
        self.assertTrue(any(tech_id in issue and "grid position" in issue
                            for issue in validator.check_technology_parser_constraints(broken)))


class RegimentalSupportTests(unittest.TestCase):
    UNLOCKS = {
        "ADISCORD_regimental_fire_support": "ADISCORD_tech_belt_fed_recovery",
        "ADISCORD_regimental_anti_tank": "ADISCORD_tech_portable_at_cells",
        "ADISCORD_regimental_anti_air": "ADISCORD_tech_radar_laying",
        "ADISCORD_regimental_pioneers": "ADISCORD_tech_urban_breaching",
        "ADISCORD_regimental_drone_observers": "ADISCORD_tech_combat_recon_drones",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.units = {}
        for path in (ROOT / "common/units").glob("*.txt"):
            text = validator.read_text(path)
            for key in cls.UNLOCKS:
                match = re.search(rf"\b{key}\s*=\s*\{{", text)
                if match:
                    if key in cls.units:
                        raise AssertionError(f"Duplicate subunit {key}")
                    cls.units[key] = validator.extract_block(text, match.start())

    def test_native_regimental_eligibility_and_real_equipment(self) -> None:
        equipment = validator.collect_equipment_blocks()
        self.assertEqual(set(self.units), set(self.UNLOCKS))
        for key, block in self.units.items():
            with self.subTest(subunit=key):
                for field, value in (("active", "no"), ("regimental", "yes"),
                                     ("divisional", "no"), ("group", "support"),
                                     ("affects_speed", "no"), ("combat_width", "0")):
                    self.assertRegex(block, rf"\b{field}\s*=\s*{value}\b")
                self.assertIn("category_regimental_support_battalions", block)
                self.assertNotIn("category_divisional_support_battalions", block)
                groups = re.search(r"allowed_battalion_groups\s*=\s*\{([^}]+)\}", block)
                self.assertIsNotNone(groups)
                self.assertTrue({"infantry", "mobile", "armor"} <= set(groups[1].split()))
                manpower = int(re.search(r"\bmanpower\s*=\s*(\d+)", block)[1])
                self.assertGreater(manpower, 0)
                self.assertLessEqual(manpower, 240)
                need = re.search(r"\bneed\s*=\s*\{([^}]+)\}", block)[1]
                requirements = dict(re.findall(r"(\w+)\s*=\s*(\d+)", need))
                self.assertNotIn("infantry_equipment", requirements)
                crew_served = int(requirements["ADISCORD_squad_weapons_equipment"])
                other = sum(int(quantity) for archetype, quantity in requirements.items()
                            if archetype != "ADISCORD_squad_weapons_equipment")
                self.assertGreater(crew_served, other)
                for archetype, quantity in requirements.items():
                    self.assertGreater(int(quantity), 0)
                    self.assertIn(archetype, equipment)
                    self.assertRegex(equipment[archetype], r"\bis_archetype\s*=\s*yes")
                    self.assertRegex(equipment[archetype], r"\bbuild_cost_ic\s*=\s*[1-9]|\bbuild_cost_ic\s*=\s*0\.[0-9]*[1-9]")

    def test_unlocks_are_reachable_and_basic_support_is_granted_at_start(self) -> None:
        _, blocks = validator.collect_technologies()
        for key, technology in self.UNLOCKS.items():
            self.assertIn(key, generator.ENABLE_SUBUNITS[technology])
            self.assertRegex(blocks[technology], rf"enable_subunits\s*=\s*\{{[^}}]*\b{key}\b")
            required = generator.technology_prerequisite_closure((technology,))
            self.assertTrue(set(required) <= generator.CURRENT_TECH_IDS)
        self.assertIn(self.UNLOCKS["ADISCORD_regimental_fire_support"],
                      generator.STARTING_TECH_PROFILES["common"])
        for key in ("ADISCORD_regimental_anti_air", "ADISCORD_regimental_anti_tank",
                    "ADISCORD_regimental_pioneers"):
            self.assertIn(self.UNLOCKS[key], generator.STARTING_TECH_PROFILES["land"])

    def test_starting_elite_support_has_eligible_columns_and_unlocked_units(self) -> None:
        from collections import Counter
        from tools.validators import validate_adiscord_division_templates as divisions

        templates, references, issues = divisions.collect_templates_and_references(ROOT)
        self.assertEqual(issues, [])
        supported = [template for template in templates if template.source_kind == "oob"
                     and any(slot.kind == "regimental_support" for slot in template.slots)]
        self.assertEqual(len(supported), 14)
        deployed = 0
        for template in supported:
            with self.subTest(owner=template.owner, template=template.name):
                technologies = set(generator.STARTING_TECH_PROFILES["common"])
                for profile in generator.STARTING_COUNTRY_TECH_PROFILES[template.owner]:
                    technologies.update(generator.STARTING_TECH_PROFILES[profile])
                columns = Counter(slot.x for slot in template.slots if slot.kind == "regiments")
                occupied = set()
                for slot in template.slots:
                    if slot.kind != "regimental_support":
                        continue
                    self.assertIn(slot.x, range(5))
                    self.assertEqual(slot.y, 0)
                    self.assertNotIn(slot.x, occupied)
                    occupied.add(slot.x)
                    self.assertGreaterEqual(columns[slot.x], 3)
                    self.assertIn(self.UNLOCKS[slot.unit], technologies)
                    self.assertNotEqual(slot.unit, "ADISCORD_regimental_drone_observers")
                matching = [reference for reference in references
                            if reference.kind == "oob" and reference.path == template.path
                            and reference.name == template.name]
                self.assertTrue(matching)
                deployed += len(matching)
        self.assertEqual(deployed, 25)

    def test_icons_and_localisation_cover_every_native_size(self) -> None:
        from PIL import Image

        sprites = validator.collect_sprite_names()
        for key in self.UNLOCKS:
            for size in ("medium", "medium_white", "small"):
                texture = sprites[f"GFX_unit_{key}_icon_{size}"]
                path = ROOT / texture
                if not path.is_file():
                    path = generator.BASE_GAME / texture
                with Image.open(path) as atlas:
                    self.assertEqual(atlas.width % 2, 0)
                    self.assertGreater(atlas.height, 0)
            for language in ("russian", "english"):
                path = ROOT / "localisation" / language / f"ADISCORD_technology_doctrine_l_{language}.yml"
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                text = path.read_text(encoding="utf-8-sig")
                for suffix in ("", "_desc"):
                    self.assertEqual(len(re.findall(rf'^ {key}{suffix}:0 "[^"\r\n]+"$', text, re.M)), 1)

    def test_support_roles_receive_their_existing_research_upgrades(self) -> None:
        for branch in ("anti_air", "anti_tank", "special_forces"):
            target = {"anti_air": "category_anti_air", "anti_tank": "category_anti_tank",
                      "special_forces": "category_recon"}[branch]
            self.assertTrue(any(target + " = {" in effect
                                for tech in generator.BRANCH_BY_KEY[branch].techs
                                for effect in tech.effects))
        upgrades = [effect for branch in generator.BRANCHES for tech in branch.techs
                    for effect in tech.effects if effect.startswith("ADISCORD_regimental_pioneers =")]
        self.assertGreaterEqual(len(upgrades), 3)


if __name__ == "__main__":
    unittest.main()
