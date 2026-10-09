from __future__ import annotations

import json
import re
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tools.builders import build_adiscord_technology_system as generator
from tools.builders import build_adiscord_technology_ui_assets as ui_builder
from tools.validators import validate_adiscord_tech_doctrine as validator


ROOT = Path(__file__).resolve().parents[2]
LEGACY_MANIFEST = ROOT / "tools" / "data" / "adiscord_technology_legacy_manifest.json"
STARTING_PROFILE_MANIFEST = (
    ROOT / "tools" / "data" / "adiscord_starting_technology_profiles.json"
)


class EquipmentProductionProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.equipment = validator.collect_equipment_blocks()

    def production_requirements(self, equipment_id):
        block = self.equipment[equipment_id]
        archetype = re.search(r"\barchetype = (\w+)", block)[1]
        base = self.equipment[archetype]
        cost = re.search(r"\bbuild_cost_ic = ([\d.]+)", block)
        cost = cost or re.search(r"\bbuild_cost_ic = ([\d.]+)", base)
        resources = re.search(r"\bresources = \{([^}]+)\}", block)
        resources = resources or re.search(r"\bresources = \{([^}]+)\}", base)
        return Decimal(cost[1]), {
            name: int(value)
            for name, value in re.findall(r"(\w+) = (\d+)", resources[1])
        }

    def test_successive_models_increase_cost_without_reducing_materials(self):
        pairs = []
        for equipment_id, block in self.equipment.items():
            parent = re.search(r"\bparent = (\w+)", block)
            if parent is None:
                continue
            # The expendable light drone is a separate role, with lower payload
            # and protection than the manned CAS frame used for its unlock.
            if equipment_id == "ADISCORD_drone_airframe_2183":
                continue
            pairs.append((parent[1], equipment_id))
        pairs.append(("ADISCORD_fighter_airframe_2166", "ADISCORD_interceptor_airframe_2183"))
        for previous, current in pairs:
            old_cost, old_resources = self.production_requirements(previous)
            new_cost, new_resources = self.production_requirements(current)
            with self.subTest(previous=previous, current=current):
                self.assertGreater(new_cost, old_cost)
                self.assertGreaterEqual(sum(new_resources.values()), sum(old_resources.values()))
                for name, amount in old_resources.items():
                    self.assertGreaterEqual(new_resources.get(name, 0), amount, name)

    def test_advanced_weapon_families_consume_both_rare_materials(self):
        late_models = (
            "ADISCORD_squad_weapons_equipment_2200",
            "ADISCORD_support_equipment_2200",
            "ADISCORD_railway_gun_equipment_2200",
            "ADISCORD_anti_tank_equipment_2183",
            "ADISCORD_artillery_equipment_2183",
            "ADISCORD_heavy_combat_platform_2200",
            "ADISCORD_networked_ifv_2183",
            "ADISCORD_attack_airframe_2175",
            "ADISCORD_cv_fighter_2175",
            "ADISCORD_cv_bomber_2175",
            "ADISCORD_bomber_2172",
            "ADISCORD_naval_aircraft_2172",
            "ADISCORD_submarine_2175",
            "ADISCORD_escort_ship_2175",
        )
        for equipment_id in late_models:
            _, resources = self.production_requirements(equipment_id)
            with self.subTest(equipment=equipment_id):
                self.assertGreater(resources.get("rare_components", 0), 0)
                self.assertGreater(resources.get("rare_alloys", 0), 0)


class AssaultRifleBranchTests(unittest.TestCase):
    def test_ammunition_connects_to_rifles_in_one_native_row(self):
        foundation = generator.BRANCH_BY_KEY["small_arms"]
        rifles = generator.BRANCH_BY_KEY["assault_rifles"]
        last = generator.render_technology(foundation, len(foundation.techs) - 1)
        self.assertIn(f"leads_to_tech = {rifles.techs[0].id}", last)
        folder = generator.render_folder("infantry_folder")
        self.assertIn(f'name = "{foundation.techs[0].id}_tree"', folder)
        self.assertNotIn(f'name = "{rifles.techs[0].id}_tree"', folder)
        titles = []
        for branch in (foundation, rifles):
            title = re.search(
                rf'name = "ADISCORD_branch_{branch.key}"\s*'
                r'position = \{ x = (\d+) y = (\d+) \}', folder
            )
            self.assertIsNotNone(title)
            titles.append(tuple(map(int, title.groups())))
        self.assertEqual(titles[0][1], titles[1][1])
        self.assertGreater(titles[1][0], titles[0][0])

    def test_rifle_production_progresses_to_rare_materials(self):
        text = (ROOT / "common/units/equipment/ADISCORD_infantry_equipment.txt").read_text(encoding="utf-8")
        previous_cost = 0
        previous_resources = {}
        previous_attack_per_cost = 0
        for year in (2156, 2163, 2168, 2170, 2178, 2183, 2193, 2200):
            match = re.search(rf"\bADISCORD_infantry_equipment_{year}\s*=\s*\{{", text)
            block = validator.extract_block(text, match.start())
            cost = float(re.search(r"build_cost_ic = ([\d.]+)", block)[1])
            attack = float(re.search(r"\bsoft_attack = ([\d.]+)", block)[1])
            resource_block = re.search(r"resources = \{([^}]+)\}", block)[1]
            resources = {name: int(value) for name, value in re.findall(r"(\w+) = (\d+)", resource_block)}
            with self.subTest(year=year):
                self.assertGreater(cost, previous_cost)
                for name, amount in previous_resources.items():
                    self.assertGreaterEqual(resources.get(name, 0), amount)
                self.assertEqual(resources.get("rare_components", 0) > 0, year >= 2183)
                self.assertEqual(resources.get("rare_alloys", 0) > 0, year >= 2193)
                if year >= 2163:
                    self.assertGreaterEqual(attack / cost, previous_attack_per_cost)
                    previous_attack_per_cost = attack / cost
            previous_cost = cost
            previous_resources = resources

    def test_every_rifle_model_has_a_distinct_price_and_material_step(self):
        path = ROOT / "common/units/equipment/ADISCORD_infantry_equipment.txt"
        text = path.read_text(encoding="utf-8")
        equipment_ids = ["infantry_equipment_0"] + [
            f"ADISCORD_infantry_equipment_{year}"
            for year in (2156, 2163, 2168, 2170, 2178, 2183, 2193, 2200)
        ]
        previous_cost = Decimal(0)
        previous_resources = {}
        for equipment_id in equipment_ids:
            match = re.search(rf"\b{equipment_id}\s*=\s*\{{", text)
            block = validator.extract_block(text, match.start())
            cost = Decimal(re.search(r"build_cost_ic = ([\d.]+)", block)[1])
            resource_match = re.search(r"resources = \{([^}]+)\}", block)
            with self.subTest(equipment=equipment_id):
                self.assertEqual(cost, cost.quantize(Decimal("0.01")))
                self.assertGreaterEqual(cost - previous_cost, Decimal("0.01"))
                self.assertIsNotNone(resource_match)
                resources = {
                    name: int(value)
                    for name, value in re.findall(r"(\w+) = (\d+)", resource_match[1])
                }
                for name, amount in previous_resources.items():
                    self.assertGreaterEqual(resources.get(name, 0), amount)
                self.assertGreater(sum(resources.values()), sum(previous_resources.values()))
                previous_cost = cost
                previous_resources = resources

    def test_rifle_branch_requires_the_full_ammunition_foundation(self):
        self.assertTrue("assault_rifles" in generator.BRANCH_BY_KEY)
        rifles = generator.BRANCH_BY_KEY["assault_rifles"]
        foundation = generator.BRANCH_BY_KEY["small_arms"]
        self.assertIn("assault_rifles", generator.MAIN_BRANCH_KEYS_BY_FOLDER["infantry_folder"])
        self.assertEqual(rifles.ru, "Штурмовые винтовки")
        self.assertEqual(rifles.years[0], 2162)
        self.assertEqual(rifles.techs[0].key, "sealed_receiver_assemblies")
        required = set(generator.technology_prerequisite_closure((rifles.techs[0].id,)))
        self.assertTrue({tech.id for tech in foundation.techs} <= required)
        self.assertEqual(generator.ENABLE_EQUIPMENT[rifles.techs[0].id], ("ADISCORD_infantry_equipment_2163",))
        for name, profile in generator.STARTING_TECH_PROFILES.items():
            if name != "late_2183":
                self.assertFalse({tech.id for tech in rifles.techs} & set(profile), name)
        rendered = generator.render_folder("infantry_folder")
        self.assertIn("ADISCORD_branch_assault_rifles", rendered)


class ShabratUniformIconTests(unittest.TestCase):
    def test_uniform_names_match_research_production_and_three_visual_stages(self):
        names = generator.country_uniform_names("russian")
        expected = [
            "КП-50 «Дозор»", "КП-55 «Рубеж»", "КП-62 «Бастион»",
            *[f"КП-62 «Бастион» М{index}" for index in range(1, 7)],
        ]
        technologies = [
            tech for tech, icon in generator.EQUIPMENT_UNLOCK_ICONS.items()
            if icon.startswith("ADISCORD_weapon_")
        ]
        for tech, name in zip(technologies, expected, strict=True):
            equipment = generator.ENABLE_EQUIPMENT[tech][0]
            self.assertEqual(names[f"STS_{tech}"], name)
            self.assertEqual(names[f"STS_{equipment}"], name)
        self.assertEqual(len(names), 27)
        self.assertEqual(len(generator.country_uniform_names("english")), 27)

    def test_uniform_localisation_preserves_bom_authored_content_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for language in ("russian", "english"):
                path = root / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
                path.parent.mkdir(parents=True)
                path.write_text(f'l_{language}:\n STP_authored:0 "Keep this"\n', encoding="utf-8-sig")
            with patch.object(generator, "ROOT", root):
                first = generator.country_uniform_localisation_outputs()
                for path, content in first.items():
                    self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
                    self.assertIn(' STP_authored:0 "Keep this"', content.decode("utf-8-sig"))
                    path.write_bytes(content)
                self.assertEqual(generator.country_uniform_localisation_outputs(), first)

    def test_every_service_unlock_has_one_shabrat_uniform_card(self):
        text = generator.country_uniform_gfx_entries()
        sprites = dict(re.findall(
            r'name = "(GFX_STS_[^"]+)"\s+textureFile = "([^"]+)"', text
        ))
        unlocks = [
            tech for tech, icon in generator.EQUIPMENT_UNLOCK_ICONS.items()
            if icon.startswith("ADISCORD_weapon_")
        ]
        self.assertEqual(len(unlocks), 9)
        self.assertEqual(len(sprites), 9)
        early_families = {
            "ADISCORD_tech_postwar_weapon_standardization": "01_reclaimed_arsenal",
            "ADISCORD_tech_refurbished_receivers": "02_recovered_service_rifle",
        }
        for tech in unlocks:
            family = early_families.get(tech, "03_standardized_battle_rifle")
            self.assertEqual(
                sprites[f"GFX_STS_{tech}_medium"],
                f"gfx/interface/technologies/ADISCORD_STS_weapon_{family}.dds",
            )
        self.assertEqual(sum("weapon_03_" in path for path in sprites.values()), 7)

    def test_partial_uniform_routes_preserve_other_sprites_and_are_idempotent(self):
        current = (ROOT / "interface/ADISCORD_technologies.gfx").read_text(encoding="utf-8")
        updated = generator.with_country_uniform_gfx(current)
        self.assertEqual(generator.with_country_uniform_gfx(updated), updated)
        pattern = r'\t# BEGIN ADISCORD country uniform cards\n.*?\t# END ADISCORD country uniform cards\n'
        self.assertEqual(
            re.sub(pattern, "", current, flags=re.DOTALL),
            re.sub(pattern, "", updated, flags=re.DOTALL),
        )

    def test_khan_cards_cover_research_and_production_with_three_stages(self):
        sprites = dict(re.findall(
            r'name = "(GFX_RUS_[^"]+)"\s+textureFile = "([^"]+)"',
            generator.country_uniform_gfx_entries(),
        ))
        self.assertEqual(len(sprites), 18)
        textures = set()
        for tech, icon in generator.EQUIPMENT_UNLOCK_ICONS.items():
            if not icon.startswith("ADISCORD_weapon_"):
                continue
            texture = sprites[f"GFX_RUS_{tech}_medium"]
            for equipment in generator.ENABLE_EQUIPMENT[tech]:
                self.assertEqual(sprites[f"GFX_RUS_{equipment}_medium"], texture)
            textures.add(texture)
        self.assertEqual(len(textures), 3)

    def test_supplied_infantry_cards_preserve_pixels_and_have_no_frame_split(self):
        from io import BytesIO
        from PIL import Image

        for path, content in generator.infantry_card_outputs().items():
            self.assertEqual(path.read_bytes(), content, str(path))
            if path.suffix == ".dds":
                source = ROOT / "tools/assets/source/country_uniforms" / (path.stem + ".png")
                with Image.open(source) as original, Image.open(BytesIO(content)) as decoded:
                    self.assertEqual(decoded.size, (176, 72))
                    self.assertEqual(original.tobytes(), decoded.convert("RGBA").tobytes())
            else:
                text = content.decode("utf-8")
                for block in re.findall(r'[Ss]priteType\s*=\s*\{[^{}]*\}', text):
                    if 'technologies/ADISCORD_power_shield_equipment.dds' in block:
                        self.assertNotIn("noOfFrames", block)


class AircraftTechnologyIconTests(unittest.TestCase):
    def test_cas_card_conversion_preserves_pixels_and_only_outputs_cas_textures(self):
        from io import BytesIO
        from PIL import Image

        outputs = generator.aircraft_icon_outputs("cas")
        textures = {path: content for path, content in outputs.items() if path.suffix == ".dds"}
        self.assertEqual(len(textures), 9)
        for path, content in textures.items():
            self.assertTrue(path.name.startswith("ADISCORD_aircraft_cas_"))
            source = ROOT / "tools/assets/source/country_cas" / (path.stem.removeprefix("ADISCORD_") + ".png")
            with Image.open(source) as original, Image.open(BytesIO(content)) as decoded:
                self.assertEqual(decoded.size, (176, 72))
                self.assertEqual(decoded.convert("RGBA").tobytes(), original.tobytes())

    def test_quote_serialization_preserves_apostrophes_and_existing_escapes(self):
        value = 'UCAV-83 \'Magpie\': the crew\'s "aircraft".\\nNext line.'
        expected = r''' model:0 "UCAV-83 \"Magpie\": the crew's \"aircraft\".\nNext line."'''
        line = generator.localisation_entry("model", value)
        self.assertEqual(line, expected)
        self.assertEqual(generator.localisation_entry("model", line.split('"', 1)[1][:-1]), line)

    def test_model_quotes_are_ascii_and_localisation_values_remain_parseable(self):
        from tools.validators.validate_adiscord_english_localisation import ENTRY

        for language in ("russian", "english"):
            lines = generator.generated_localisation(language)
            for names in (generator.country_aircraft_names(language), generator.country_uniform_names(language)):
                data = generator.with_country_names(
                    f"l_{language}:\n".encode("utf-8-sig"), "Models", names,
                )
                lines.extend(data.decode("utf-8-sig").splitlines()[2:-1])
            for line in filter(str.strip, lines):
                with self.subTest(language=language, line=line[:80]):
                    self.assertIsNotNone(ENTRY.fullmatch(line))
                    self.assertNotRegex(line, "[«»“”„]")
            self.assertTrue(any('\\"' in line for line in lines))

    def test_crew_served_unlock_names_match_the_produced_model(self):
        from tools.validators.validate_adiscord_english_localisation import ENTRY

        for language, index in (("russian", 0), ("english", 1)):
            entries = {
                match[1]: match[2].replace('\\"', '"')
                for line in generator.generated_localisation(language)
                if (match := ENTRY.fullmatch(line))
            }
            for tech in generator.BRANCH_BY_KEY["squad_weapons"].techs:
                for equipment in generator.ENABLE_EQUIPMENT.get(tech.id, ()):
                    name = generator.LAND_EQUIPMENT_LOCALISATION[equipment][index]
                    name = name.translate(str.maketrans({char: '"' for char in "«»“”„"}))
                    self.assertEqual(entries[tech.id], name)

    def test_production_type_subtitle_matches_propeller_and_jet_cards(self):
        expected = {
            "ADISCORD_fighter_airframe_2163": ("Винтовой истребитель", "Propeller Fighter"),
            "ADISCORD_cas_airframe_2170": ("Винтовой штурмовик", "Propeller Attack Aircraft"),
            "ADISCORD_vtol_airframe_2170": ("Реактивный штурмовик", "Jet Attack Aircraft"),
        }
        outputs = generator.country_equipment_localisation_outputs()
        for language, index in (("russian", 0), ("english", 1)):
            path = ROOT / f"localisation/{language}/ADISCORD_technology_doctrine_l_{language}.yml"
            partial = outputs[path].decode("utf-8-sig")
            full = "\n".join(generator.generated_localisation(language))
            for equipment, names in expected.items():
                for text in (partial, full):
                    self.assertIn(f' {equipment}:0 "{names[index]}"', text)
                    self.assertIn(f' {equipment}_short:0 "{names[index]}"', text)

    def test_aircraft_names_follow_cards_and_match_the_unlocked_equipment(self):
        for language in ("russian", "english"):
            names = generator.country_aircraft_names(language)
            self.assertEqual(len(names), 300)
            for tech, equipment in generator.ENABLE_EQUIPMENT.items():
                for item in equipment:
                    if item not in generator.AIRCRAFT_CARD_TIERS:
                        continue
                    for tag in generator.COUNTRY_AIRCRAFT_CARD_FAMILIES:
                        self.assertEqual(names[f"{tag}_{tech}"], names[f"{tag}_{item}"])
                        self.assertEqual(names[f"{tag}_{tech}_desc"], names[f"{tag}_{item}_desc"])
                    self.assertEqual(names[f"NOD_{item}"], names[f"STP_{item}"])
                    self.assertEqual(names[f"STS_{item}"], names[f"SRP_{item}"])
            for tag in generator.COUNTRY_AIRCRAFT_CARD_FAMILIES:
                for item in ("ADISCORD_fighter_airframe_2163", "ADISCORD_cas_airframe_2170"):
                    self.assertIn("Винтовой" if language == "russian" else "Propeller", names[f"{tag}_{item}_desc"])
                    self.assertIn("-50", names[f"{tag}_{item}"])

    def test_country_name_sections_preserve_surrounding_sections(self):
        original = b'\xef\xbb\xbfl_english:\r\n original:0 "Kept"\r\n'
        first = generator.with_country_names(original, "First", {"A": "One"})
        both = generator.with_country_names(first, "Second", {"B": "Two"})
        self.assertEqual(generator.with_country_names(both, "First", {"A": "One"}), both)
        self.assertTrue(both.startswith(original))

    def test_country_aircraft_repeat_the_third_card_in_research_and_production(self):
        text = (ROOT / "interface/ADISCORD_technologies.gfx").read_text(encoding="utf-8")
        sprites = dict(re.findall(
            r'name = "([^"]+)"\s+textureFile = "([^"]+)"', text
        ))
        routes = (
            ("reclaimed_jet_platforms", "fighter_airframe_2163", 1),
            ("high_altitude_interceptors", "fighter_airframe_2161", 2),
            ("thrust_vectoring", "fighter_airframe_2166", 3),
            ("low_observable_inlet_geometry", "interceptor_airframe_2183", 3),
            ("loyal_wingmen", "fighter_airframe_2170", 3),
            ("distributed_interceptor_swarms", "fighter_airframe_2175", 3),
            ("battlefield_attack_aircraft", "cas_airframe_2170", 1),
            ("vtol_assault_frames", "vtol_airframe_2170", 2),
            ("precision_glide_bomb_kits", "attack_airframe_2163", 3),
            ("drone_air_wings", "drone_airframe_2183", 3),
            ("autonomous_strike_wings", "attack_airframe_2170", 3),
            ("persistent_sensor_strike_loops", "attack_airframe_2175", 3),
        )
        for tag, family in (("VAL", "VAL"), ("NOD", "party"), ("STP", "party"), ("STS", "STS"), ("SRP", "STS")):
            for tech, equipment, tier in routes:
                prefix = "aircraft" if equipment.startswith(("fighter", "interceptor")) else "aircraft_cas"
                texture = f"gfx/interface/technologies/ADISCORD_{prefix}_{family}_{tier}.dds"
                for key in (f"ADISCORD_tech_{tech}", f"ADISCORD_{equipment}"):
                    with self.subTest(country=tag, key=key):
                        self.assertEqual(sprites.get(f"GFX_{tag}_{key}_medium"), texture)


class AssaultInfantryTechnologyTests(unittest.TestCase):
    def test_independent_branch_opens_assault_infantry_in_2162(self):
        self.assertIn("assault_infantry", generator.BRANCH_BY_KEY)
        branch = generator.BRANCH_BY_KEY["assault_infantry"]
        self.assertEqual(branch.years, (2162, 2163, 2164, 2166, 2169, 2172))
        self.assertIn(branch.key, generator.MAIN_BRANCH_KEYS_BY_FOLDER["infantry_folder"])
        self.assertIn("enable_subunits = { ADISCORD_assault_infantry }", generator.render_technology(branch, 0))
        unlocks = [key for key, units in generator.ENABLE_SUBUNITS.items() if "ADISCORD_assault_infantry" in units]
        self.assertEqual(unlocks, [branch.techs[0].id])
        for index, tech in enumerate(branch.techs):
            self.assertEqual(
                set(generator.technology_prerequisite_closure((tech.id,))),
                {item.id for item in branch.techs[:index + 1]},
            )
            for profile in generator.STARTING_TECH_PROFILES.values():
                self.assertNotIn(tech.id, profile)
            self.assertNotIn(tech.id, generator.ALLOW)
            self.assertEqual(generator.xor_siblings(branch, index), ())
        gui = generator.render_folder("infantry_folder")
        self.assertIn('name = "ADISCORD_branch_assault_infantry"', gui)
        self.assertIn(f'name = "{branch.techs[0].id}_tree"', gui)

    def test_approved_rewards_apply_only_to_assault_infantry(self):
        self.assertIn("assault_infantry", generator.BRANCH_BY_KEY)
        branch = generator.BRANCH_BY_KEY["assault_infantry"]
        totals = {}
        for index, tech in enumerate(branch.techs):
            effects = generator.effects_for(branch, index)
            for effect in effects:
                self.assertRegex(effect, r"^ADISCORD_assault_infantry = \{[^{}]+\}$")
                for modifier, amount in re.findall(r"(\w+) = (-?[0-9.]+)", effect):
                    totals[modifier] = totals.get(modifier, Decimal(0)) + Decimal(amount)
            self.assertEqual(bool(effects), index > 0)
        self.assertEqual(totals, {
            "breakthrough": Decimal("0.10"),
            "soft_attack": Decimal("0.08"),
            "max_organisation": Decimal(2),
            "supply_consumption": Decimal("-0.05"),
        })

    def test_assault_consumers_follow_the_battalion_unlock(self):
        self.assertIn("assault_infantry", generator.BRANCH_BY_KEY)
        root = generator.BRANCH_BY_KEY["assault_infantry"].techs[0].id
        for name in (
            "common/ai_templates/ADISCORD_land_templates.txt",
            "common/ai_strategy/ADISCORD_technology_doctrine_ai.txt",
            "common/doctrines/subdoctrines/land/ADISCORD_land_subdoctrines.txt",
            "common/doctrines/subdoctrines/special_forces/ADISCORD_special_forces_subdoctrines.txt",
        ):
            text = (ROOT / name).read_text(encoding="utf-8-sig")
            self.assertIn(f"has_tech = {root}", text, name)
            self.assertNotIn("has_tech = ADISCORD_tech_remote_weapon_tripods", text, name)
        for name in ("focus_trees/VAL/main/focuses.txt", "common/national_focus/ADISCORD_national_focus_VAL.txt"):
            text = (ROOT / name).read_text(encoding="utf-8-sig")
            reward = text.split("id = VAL_Armored_Assault_Corps", 1)[1]
            self.assertIn(f"{root} = 1", reward)
            self.assertIn("ADISCORD_tech_remote_weapon_tripods = 1", reward)

    def test_generated_branch_has_complete_localisation_and_art(self):
        branch = generator.BRANCH_BY_KEY["assault_infantry"]
        script = (ROOT / "common/technologies/ADISCORD_infantry.txt").read_bytes()
        self.assertFalse(script.startswith(b"\xef\xbb\xbf"))
        gfx = (ROOT / "interface/ADISCORD_technologies.gfx").read_text(encoding="utf-8")
        for index, tech in enumerate(branch.techs):
            self.assertIn(generator.render_technology(branch, index), script.decode("utf-8").replace("\r\n", "\n"))
            self.assertIn(f'name = "GFX_{tech.id}_medium"', gfx)
            self.assertIsNotNone(generator.technology_icon_size(generator.icon_for_technology(branch, index)))
        for language in ("russian", "english"):
            data = (ROOT / f"localisation/{language}/ADISCORD_technology_doctrine_l_{language}.yml").read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            text = data.decode("utf-8-sig").replace("\r\n", "\n")
            for tech in branch.techs:
                for suffix in ("", "_desc"):
                    self.assertEqual(len(re.findall(rf'(?m)^ {tech.id}{suffix}:0 "[^"\n]+"$', text)), 1)

    def test_validator_checks_small_assault_upgrades_in_their_actual_scope(self):
        branch = generator.BRANCH_BY_KEY["assault_infantry"]
        _, blocks = validator.collect_technologies()
        ids = {tech.id for tech in branch.techs}
        issues = validator.check_post_2160_research_balance(blocks)
        self.assertFalse([issue for issue in issues if any(key in issue for key in ids)])
        for index in (1, 2, 4):
            tech = branch.techs[index]
            block = generator.render_technology(branch, index)
            modifier, amount = re.search(r"(\w+) = (-?[0-9.]+)", tech.effects[0]).groups()
            mutations = (
                block.replace(f"{modifier} = {amount}", ""),
                block.replace(f"{modifier} = {amount}", f"{modifier} = 0"),
                block.replace(f"{modifier} = {amount}", f"{modifier} = {-Decimal(amount)}"),
                block.replace("ADISCORD_assault_infantry =", "infantry ="),
            )
            for mutation in mutations:
                with self.subTest(technology=tech.id, mutation=mutation):
                    issues = validator.check_post_2160_research_balance({**blocks, tech.id: mutation})
                    self.assertTrue(any(tech.id in issue for issue in issues))


class AmphibiousTechnologyTests(unittest.TestCase):
    def test_progression_requires_research_and_preserves_transport_access(self):
        branch = generator.BRANCH_BY_KEY["amphibious_operations"]
        self.assertEqual(branch.years, (2160, 2161, 2162, 2163, 2164, 2166, 2169, 2172, 2175))
        for index, tech in enumerate(branch.techs):
            for profile in generator.STARTING_TECH_PROFILES.values():
                self.assertNotIn(tech.id, profile)
            required = set(generator.technology_prerequisite_closure((tech.id,)))
            self.assertEqual(required, {
                "ADISCORD_tech_restored_dockyards",
                *(item.id for item in branch.techs[:index + 1]),
            })
            self.assertEqual(generator.xor_siblings(branch, index), ())
            self.assertNotIn(tech.id, generator.ALLOW)
        dockyards, index = generator.TECH_POSITION_BY_ID["ADISCORD_tech_restored_dockyards"]
        self.assertIn("naval_invasion_capacity = 100", generator.render_technology(dockyards, index))

    def test_rendered_rewards_preserve_approved_totals(self):
        branch = generator.BRANCH_BY_KEY["amphibious_operations"]
        totals = {}
        for index, tech in enumerate(branch.techs):
            rendered = generator.render_technology(branch, index)
            prefix = re.split(r"(?m)^\s*(?:path|dependencies|research_cost)\s*=", rendered)[0]
            for modifier, value in re.findall(r"\b(\w+) = (-?[0-9.]+)", prefix):
                totals[modifier] = totals.get(modifier, Decimal(0)) + Decimal(value)
            self.assertNotIn("on_research_complete", rendered)
            self.assertIn(rendered, (ROOT / "common/technologies/ADISCORD_naval.txt").read_text(encoding="utf-8"))
        self.assertEqual(totals, {
            "naval_invasion_division_cap": Decimal(4),
            "naval_invasion_plan_cap": Decimal(2),
            "naval_invasion_prep_days": Decimal(-20),
            "amphibious_invasion": Decimal("0.15"),
            "naval_invasion_penalty": Decimal("-0.05"),
        })

    def test_branch_has_native_icons_localisation_and_both_naval_layouts(self):
        branch = generator.BRANCH_BY_KEY["amphibious_operations"]
        self.assertEqual(branch.folders, ("naval_folder", "mtgnavalsupportfolder"))
        for folder in branch.folders:
            gui = generator.render_folder(folder)
            self.assertIn('name = "ADISCORD_branch_amphibious_operations"', gui)
            self.assertIn(f'name = "{branch.techs[0].id}_tree"', gui)
            for year in branch.years:
                label_id = (
                    str(year)
                    if folder in generator.HORIZONTAL_FOLDERS
                    else f"amphibious_operations_{year}"
                )
                self.assertIn(f'name = "ADISCORD_{folder}_year_{label_id}"', gui)
        for index, tech in enumerate(branch.techs):
            self.assertEqual(generator.icon_for_technology(branch, index), tech.icon)
            self.assertIn(tech.key, generator.TECHNICAL_TECH_DESCRIPTIONS)
            for language in ("russian", "english"):
                source = "\n".join(generator.generated_localisation(language))
                self.assertRegex(source, rf'(?m)^ {tech.id}_desc:0 "[^"\n]+"$')

    def test_validator_rejects_missing_zero_or_harmful_single_rewards(self):
        branch = generator.BRANCH_BY_KEY["amphibious_operations"]
        _, blocks = validator.collect_technologies()
        issues = validator.check_post_2160_research_balance(blocks)
        self.assertFalse([issue for issue in issues if "ADISCORD_tech_amphibious_" in issue])
        for index, tech in enumerate(branch.techs[:7]):
            rendered = generator.render_technology(branch, index)
            effect = tech.effects[0]
            modifier, value = effect.split(" = ")
            for replacement in ("", f"{modifier} = 0", f"{modifier} = {-Decimal(value)}"):
                with self.subTest(technology=tech.id, replacement=replacement):
                    invalid = {**blocks, tech.id: rendered.replace(effect, replacement)}
                    issues = validator.check_post_2160_research_balance(invalid)
                    self.assertTrue(any(tech.id in issue and "numeric gameplay effects" in issue for issue in issues))


class CompactTechnologyTreeContractTests(unittest.TestCase):
    def test_synthetic_branches_require_research_and_progress_independently(self):
        rubber = generator.BRANCH_BY_KEY["synthetic_rubber"]
        oil = generator.BRANCH_BY_KEY["synthetic_oil"]
        self.assertEqual(rubber.years, (2160, 2163, 2166, 2169, 2172, 2175))
        self.assertEqual(oil.years, (2161, 2163, 2166, 2169, 2172, 2175))
        for branch in (rubber, oil):
            self.assertEqual(branch.folders, ("industry_folder",))
            for index, tech in enumerate(branch.techs):
                for profile in generator.STARTING_TECH_PROFILES.values():
                    self.assertNotIn(tech.id, profile)
                self.assertNotIn(tech.id, generator.ALLOW)
                self.assertEqual(generator.xor_siblings(branch, index), ())
                required = set(generator.technology_prerequisite_closure((tech.id,)))
                expected = {item.id for item in branch.techs[:index + 1]}
                if branch is oil:
                    expected.add(rubber.techs[0].id)
                self.assertEqual(required, expected)
        root = generator.render_technology(oil, 0)
        self.assertIn(f"{rubber.techs[0].id} = 1", root)

    def test_synthetic_output_is_native_and_does_not_stack_with_old_unlocks(self):
        buildings = validator.collect_building_blocks()
        plant = buildings["synthetic_refinery"]
        self.assertRegex(plant, r"\bbase_cost\s*=\s*14500\b")
        self.assertRegex(plant, r"\blocal_resources_rubber\s*=\s*1\b")
        self.assertRegex(plant, r"\bfuel_gain_from_states\s*=\s*2\.0\b")
        self.assertRegex(plant, r"\bstate_max\s*=\s*3\b")
        caps = {}
        yields = {"rubber": {}, "oil": {}}
        for tech_id, entries in generator.ENABLE_BUILDINGS.items():
            for building, level in entries:
                if building == "synthetic_refinery":
                    branch, index = generator.TECH_POSITION_BY_ID[tech_id]
                    self.assertEqual(branch.key, "synthetic_rubber")
                    caps[branch.years[index]] = level
        for tech_id, entries in generator.BUILDING_RESOURCE_UPGRADES.items():
            for building, resource, amount in entries:
                if building != "synthetic_refinery":
                    continue
                branch, index = generator.TECH_POSITION_BY_ID[tech_id]
                self.assertEqual(branch.key, f"synthetic_{resource}")
                yields[resource][branch.years[index]] = amount
                rendered = generator.render_technology(branch, index)
                self.assertEqual(rendered.count("on_research_complete = {"), 1)
                self.assertEqual(rendered.count("modify_building_resources = {"), 1)
                self.assertIn(f"resource = {resource}", rendered)
                self.assertIn("show_effect_as_desc = yes", rendered)
                self.assertNotIn("every_state", rendered)
                self.assertNotIn("add_resource", rendered)
        self.assertEqual(caps, {2160: 1, 2166: 2, 2172: 3})
        self.assertEqual(yields["rubber"], {2163: 1, 2169: 1, 2175: 1})
        self.assertEqual(yields["oil"], {2161: 1, 2166: 1, 2172: 1})
        for tech_id, amount in (
            ("ADISCORD_tech_rare_earth_solvent_loops", 2),
            ("ADISCORD_tech_strategic_element_reclamation", 1),
        ):
            self.assertEqual(
                generator.BUILDING_RESOURCE_UPGRADES[tech_id],
                (("ADISCORD_electrolysis_complex", "aluminium", amount),),
            )

    def test_synthetic_fuel_upgrades_do_not_masquerade_as_oil(self):
        oil = generator.BRANCH_BY_KEY["synthetic_oil"]
        total = Decimal(0)
        for index, tech in enumerate(oil.techs):
            rendered = generator.render_technology(oil, index)
            if index % 2:
                self.assertNotIn("modify_building_resources", rendered)
                values = re.findall(r"\bfuel_gain_factor_from_states = ([\d.]+)", rendered)
                self.assertEqual(len(values), 1)
                total += Decimal(values[0])
            else:
                self.assertIn("resource = oil", rendered)
                self.assertNotIn("fuel_gain_factor", rendered)
        self.assertEqual(total, Decimal("0.30"))

    def test_synthetic_ui_and_ai_explain_and_bound_the_investment(self):
        gui = generator.render_folder("industry_folder")
        for branch_key in ("synthetic_rubber", "synthetic_oil"):
            branch = generator.BRANCH_BY_KEY[branch_key]
            self.assertIn(f'name = "ADISCORD_branch_{branch_key}"', gui)
            self.assertIn(f'name = "{branch.techs[0].id}_tree"', gui)
            for index, tech in enumerate(branch.techs):
                self.assertIn(f"year_{branch_key}_{branch.years[index]}", gui)
                self.assertIn(tech.key, generator.TECHNICAL_TECH_DESCRIPTIONS)
                self.assertEqual(generator.icon_for_technology(branch, index), tech.icon)
                ai = "\n".join(generator.ai_will_do_for(branch, index))
                self.assertIn("factor = 0.30 ADISCORD_economy_ai_is_crisis = yes", ai)
                self.assertIn("num_of_civilian_factories < 5", ai)
                self.assertNotIn("factor = 1.35 ADISCORD_economy_ai_is_crisis", ai)
                self.assertGreaterEqual(generator.research_cost_for(branch, index, (), ()), 1.35)
                for is_ru in (False, True):
                    notes = " ".join(generator.technology_description_notes(branch, index, is_ru))
                    if tech.id in generator.ENABLE_BUILDINGS:
                        level = generator.ENABLE_BUILDINGS[tech.id][0][1]
                        self.assertIn(str(level), notes)
                    if tech.id in generator.BUILDING_RESOURCE_UPGRADES:
                        self.assertIn("+1", notes)
                        resource = generator.BUILDING_RESOURCE_UPGRADES[tech.id][0][1]
                        self.assertIn(f"£resources_strip|{3 if resource == 'rubber' else 1}", notes)

    def test_synthetic_validator_rejects_missing_zero_and_wrong_output(self):
        _, blocks = validator.collect_technologies()
        synthetic_ids = {
            tech.id
            for branch in generator.BRANCHES
            if branch.key in {"synthetic_rubber", "synthetic_oil"}
            for tech in branch.techs
        }
        initial = validator.check_post_2160_research_balance(blocks)
        self.assertFalse([issue for issue in initial if any(key in issue for key in synthetic_ids)])
        for tech_id in synthetic_ids:
            original = blocks[tech_id]
            if tech_id in generator.BUILDING_RESOURCE_UPGRADES:
                marker = original.index("on_research_complete = {")
                callback = validator.extract_block(original, marker)
                invalid = (
                    original.replace(callback, ""),
                    original.replace("amount = 1", "amount = 0"),
                    original.replace("amount = 1", "amount = 9"),
                    original.replace("amount = 1", "amount = 1.5"),
                    original.replace("modify_building_resources", "unused_resource_reward"),
                )
            elif "fuel_gain_factor_from_states" in original:
                invalid = (
                    re.sub(r"fuel_gain_factor_from_states = [0-9.]+", "", original),
                    re.sub(r"fuel_gain_factor_from_states = [0-9.]+", "fuel_gain_factor_from_states = 0", original),
                )
            else:
                continue
            for mutated in invalid:
                with self.subTest(technology=tech_id, mutation=mutated):
                    issues = validator.check_post_2160_research_balance({**blocks, tech_id: mutated})
                    self.assertTrue(any(tech_id in issue and "numeric gameplay effects" in issue for issue in issues))

    def test_small_arms_requires_three_modifications_between_models(self):
        branches = [generator.BRANCH_BY_KEY[key] for key in ("small_arms", "assault_rifles")]
        techs = tuple(tech for branch in branches for tech in branch.techs)
        models = [
            index for index, tech in enumerate(techs)
            if tech.id in generator.ENABLE_EQUIPMENT
        ]
        self.assertEqual(models, list(range(0, 33, 4)))
        for index, tech in enumerate(techs):
            required = set(generator.technology_prerequisite_closure((tech.id,)))
            self.assertTrue({t.id for t in techs[:index]} <= required)
        for branch in branches:
            graph = generator.BRANCH_GRAPHS[branch.key]
            self.assertEqual(len(set(graph.lanes)), 1)
            for index in range(len(branch.techs)):
                expected = (index + 1,) if index + 1 < len(branch.techs) else ()
                self.assertEqual(graph.successors[index], expected)
                self.assertEqual(generator.xor_siblings(branch, index), ())

    def test_small_arms_preserves_total_rewards_and_research_budget(self):
        branches = [generator.BRANCH_BY_KEY[key] for key in ("small_arms", "assault_rifles")]
        totals = {}
        for tech in (tech for branch in branches for tech in branch.techs):
            for effect in tech.effects:
                for name, value in re.findall(r"(\w+) = (0\.\d+)", effect):
                    totals[name] = totals.get(name, Decimal(0)) + Decimal(value)
        self.assertEqual(totals, {
            "soft_attack": Decimal("0.264"),
            "defense": Decimal("0.148"),
            "breakthrough": Decimal("0.128"),
            "coordination_bonus": Decimal("0.068"),
            "land_night_attack": Decimal("0.012"),
        })
        cost = sum(
            generator.research_cost_for(branch, index, (), ())
            for branch in branches
            for index in range(len(branch.techs))
        )
        self.assertGreaterEqual(cost, 44)
        self.assertLessEqual(cost, 45)
        self.assertTrue(
            {tech.id for tech in branches[0].techs[:4]}
            <= set(generator.STARTING_TECH_PROFILES["common"])
        )

    def test_weapon_modifications_keep_work_after_bonus_and_saved_research(self):
        branches = [generator.BRANCH_BY_KEY[key] for key in ("small_arms", "assault_rifles")]
        # Pricing envelope: 110 base points, a 50% discount, +50% speed
        # and a full 30-day bank must still leave at least two weeks of work.
        for branch, index, tech in (
            (branch, index, tech)
            for branch in branches
            for index, tech in enumerate(branch.techs)
        ):
            if tech.id in generator.ENABLE_EQUIPMENT:
                continue
            with self.subTest(technology=tech.id):
                rendered = generator.render_technology(branch, index)
                cost = float(re.search(r"research_cost = ([\d.]+)", rendered).group(1))
                self.assertGreaterEqual(cost * 110 * 0.5 / 1.5 - 30, 14)

    def test_same_year_weapon_modifications_have_separate_dated_cells(self):
        branch = generator.BRANCH_BY_KEY["small_arms"]
        slots = generator.horizontal_visual_slots(branch)
        self.assertTrue(all(a < b for a, b in zip(slots, slots[1:])))
        rendered = generator.render_folder("infantry_folder")
        for occurrence, index in enumerate(range(4)):
            label_id = "2150" if occurrence == 0 else f"2150_{occurrence}"
            label = self._named_gui_block(
                rendered, "instantTextBoxType", f"ADISCORD_infantry_folder_year_{label_id}"
            )
            self.assertIn('text = "2150"', label)
            self.assertEqual(slots[index], occurrence * 3)

    def test_shared_squad_weapon_progression_has_no_country_gate(self):
        for branch in generator.BRANCHES:
            for index, tech in enumerate(branch.techs):
                equipment = generator.ENABLE_EQUIPMENT.get(tech.id, ())
                if not any(
                    item.startswith("ADISCORD_squad_weapons_equipment_")
                    for item in equipment
                ):
                    continue
                with self.subTest(technology=tech.id):
                    rendered = generator.render_technology(branch, index)
                    self.assertNotRegex(rendered, r"\b(?:tag|original_tag)\s*=")

    def test_starting_support_weapons_have_producible_equipment(self):
        for key, equipment in (
            ("salvaged_at_guns", "ADISCORD_anti_tank_equipment_2163"),
            ("improvised_air_defense", "ADISCORD_anti_air_equipment_2163"),
        ):
            self.assertIn(
                equipment, generator.ENABLE_EQUIPMENT.get(f"ADISCORD_tech_{key}", ())
            )

    def test_railway_gun_rewards_use_equipment_bonus_effect(self):
        branch = generator.BRANCH_BY_KEY["railway_artillery"]
        for index, tech in enumerate(branch.techs):
            rendered = generator.render_technology(branch, index)
            self.assertNotRegex(rendered, r"(?m)^\t\trailway_gun\s*=")
            self.assertIn("add_equipment_bonus = {", rendered)
            self.assertIn("railway_gun_equipment = {", rendered)

    def test_railway_gun_equipment_has_an_active_map_unit(self):
        text = validator.read_text(ROOT / "common/units/ADISCORD_land_units.txt")
        match = re.search(r"(?m)^\s*railway_gun\s*=\s*\{", text)
        self.assertIsNotNone(match, "Railway gun equipment needs a map subunit")
        block = validator.extract_block(text, match.start())
        self.assertRegex(block, r"\bactive\s*=\s*yes\b")
        self.assertRegex(block, r"\btype\s*=\s*\{\s*railway_gun\s*\}")
        self.assertRegex(
            block, r"\bneed\s*=\s*\{\s*railway_gun_equipment\s*=\s*1\s*\}"
        )
        equipment = validator.collect_equipment_blocks()
        for model in ("railway_gun_equipment_1", "ADISCORD_railway_gun_equipment_2200"):
            self.assertRegex(
                equipment[model], r"\barchetype\s*=\s*railway_gun_equipment\b"
            )

    def test_validator_requires_the_railway_gun_map_unit(self):
        defined = validator.collect_defined_subunits() - {"railway_gun"}
        with patch.object(validator, "collect_defined_subunits", return_value=defined):
            self.assertIn(
                "missing required engine/operation subunit railway_gun",
                validator.check_required_unit_definitions(),
            )

    def test_reconstruction_expands_shared_factory_capacity(self):
        expected = {
            "drone_construction_cartography": "0.10",
            "modular_rebuilding": "0.10",
            "prefabricated_districts": "0.10",
        }
        found = {}
        for branch in generator.BRANCHES:
            for index, tech in enumerate(branch.techs):
                if tech.key in expected:
                    effects = generator.effects_for(branch, index)
                    self.assertIn(
                        "global_building_slots_factor = " + expected[tech.key], effects
                    )
                    found[tech.key] = True
        self.assertEqual(set(found), set(expected))

    def test_weapon_programmes_target_registered_subunits(self):
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )

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
                grid = self._named_gui_block(
                    rendered, "gridboxtype", generator.technology_tree_root(branch) + "_tree"
                )
                size = re.search(r"size = \{ width = (\d+) height = (\d+) \}", grid)
                cross_size = int(size[2 if horizontal else 1])
                # Native cross-axis slot zero lies at the gridbox centre.
                centers = [
                    cross_size / 2
                    + generator.technology_grid_position(branch, i)[0] * 70
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
                        generator.horizontal_year_columns(branch.folders[0]).index(
                            (year, generator.technology_year_occurrence(branch, index))
                        ) * 3,
                    )

    def test_year_label_centres_align_with_native_technology_cells(self) -> None:
        for folder in generator.FOLDER_BACKGROUNDS:
            rendered = generator.render_folder(folder)
            horizontal = folder in generator.HORIZONTAL_FOLDERS
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = self._named_gui_block(
                    rendered, "gridboxtype", generator.technology_tree_root(branch) + "_tree"
                )
                origin = re.search(r"position = \{ x = (-?\d+) y = (-?\d+) \}", grid)
                for index, year in enumerate(branch.years):
                    occurrence = generator.technology_year_occurrence(branch, index)
                    label_id = (
                        (str(year) if occurrence == 0 else f"{year}_{occurrence}")
                        if horizontal else f"{branch.key}_{year}"
                    )
                    label = self._named_gui_block(
                        rendered,
                        "instantTextBoxType",
                        f"ADISCORD_{folder}_year_{label_id}",
                    )
                    pos = re.search(r"position = \{ x = (-?\d+) y = (-?\d+) \}", label)
                    extent = int(
                        re.search(
                            r"maxWidth = (\d+)" if horizontal else r"maxHeight = (\d+)",
                            label,
                        )[1]
                    )
                    axis = 1 if horizontal else 2
                    cell_center = (
                        int(origin[axis])
                        + generator.technology_time_slot(branch, index) * 70
                        + 35
                    )
                    with self.subTest(folder=folder, technology=branch.techs[index].id):
                        self.assertEqual(int(pos[axis]) + extent / 2, cell_center)
                        self.assertIn(f'text = "{year}"', label)

    def test_ui_validator_rejects_swapped_dates_displaced_labels_and_wrong_titles(
        self,
    ) -> None:
        original = "\n".join(
            generator.render_folder(folder) for folder in generator.FOLDER_BACKGROUNDS
        )
        label_a = self._named_gui_block(
            original,
            "instantTextBoxType",
            "ADISCORD_industry_folder_year_production_2150",
        )
        label_b = self._named_gui_block(
            original,
            "instantTextBoxType",
            "ADISCORD_industry_folder_year_production_2155",
        )
        swapped = original.replace(
            label_a, label_a.replace('text = "2150"', 'text = "2155"')
        )
        swapped = swapped.replace(
            label_b, label_b.replace('text = "2155"', 'text = "2150"')
        )
        displaced = original.replace(
            label_a, re.sub(r"position = \{ x = -?\d+", "position = { x = 999", label_a)
        )
        title = self._named_gui_block(
            original, "instantTextBoxType", "ADISCORD_branch_production"
        )
        wrong_title = original.replace(
            title,
            title.replace(
                "ADISCORD_TECH_BRANCH_PRODUCTION", "ADISCORD_TECH_BRANCH_RECONSTRUCTION"
            ),
        )
        grid = self._named_gui_block(
            original, "gridboxtype", "ADISCORD_tech_standardized_machine_tools_tree"
        )
        displaced_grid = original.replace(
            grid, re.sub(r"position = \{ x = -?\d+", "position = { x = 999", grid)
        )
        mutations = (
            ("swapped", swapped),
            ("displaced", displaced),
            ("wrong_title", wrong_title),
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
            output.write_bytes(
                (ROOT / "interface/countrytechtreeview.gui").read_bytes()
            )
            with (
                patch.object(generator, "ROOT", root),
                patch.object(generator, "BASE_GAME", root / "uninstalled_game"),
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
            rows = sorted(
                {
                    generator.technology_time_slot(branch, i)
                    for i in range(len(branch.techs))
                }
            )
            with self.subTest(branch=branch.key):
                self.assertEqual(rows[0], 0)
                self.assertTrue(
                    all(
                        (b - a) * generator.GRID_SLOT <= 140
                        for a, b in zip(rows, rows[1:])
                    )
                )

    def test_officer_training_delivers_all_four_leader_attributes(self) -> None:
        branch = generator.BRANCH_BY_KEY['officer_training']
        rendered = '\n'.join(
            generator.render_technology(branch, i) for i in range(len(branch.techs))
        )
        self.assertEqual(len(branch.techs), 8)
        for attribute in ('attack', 'defense', 'planning', 'logistics'):
            self.assertIn(f'add_{attribute} = 1', rendered)
        self.assertEqual(rendered.count('on_research_complete ='), 7)

    def test_single_lane_vertical_programme_has_no_empty_side_lane(self) -> None:
        branch = generator.BRANCH_BY_KEY["public_finance"]
        self.assertEqual(generator.technology_grid_position(branch, 0), (0, 0))
        rendered = generator.render_folder("industry_folder")
        self.assertRegex(
            rendered,
            rf'name = "{branch.techs[0].id}_tree"\s*position = \{{[^}}]+\}}\s*size = \{{ width = 210 ',
        )

    def test_naval_research_unlocks_multiple_producible_generations(self) -> None:
        blocks = validator.collect_equipment_blocks()
        for key in generator.NAVAL_HULL_BRANCH_KEYS:
            branch = generator.BRANCH_BY_KEY[key]
            unlocked = {
                equipment
                for tech in branch.techs
                for equipment in generator.ENABLE_EQUIPMENT.get(tech.id, ())
            }
            with self.subTest(branch=key):
                self.assertGreaterEqual(len(unlocked), 4)
                for equipment in unlocked:
                    self.assertIn(equipment, blocks)
                    self.assertNotRegex(blocks[equipment], r'active\s*=\s*yes')

    def test_ship_classes_have_dedicated_native_art_and_one_unlock_per_hull(self):
        from PIL import Image

        equipment = validator.collect_equipment_blocks()
        unlock_counts = {}
        for unlocked in generator.ENABLE_EQUIPMENT.values():
            for item in unlocked:
                unlock_counts[item] = unlock_counts.get(item, 0) + 1
        for kind, (_, _, _, _, family, _) in generator.NAVAL_HULL_CLASSES.items():
            branch = generator.BRANCH_BY_KEY[f"{kind}_hulls"]
            hulls = [(i, tech) for i, tech in enumerate(branch.techs) if "_hull_" in tech.key]
            self.assertEqual(tuple(branch.years[i] for i, _ in hulls), (2155, 2163, 2170, 2175))
            self.assertEqual(branch.folders, ("naval_folder", "mtgnavalfolder"))
            for tier, (i, tech) in enumerate(hulls):
                model = f"ADISCORD_{family}_{branch.years[i]}"
                self.assertEqual(unlock_counts[model], 1, model)
                self.assertIn(model, generator.ENABLE_EQUIPMENT[tech.id])
                self.assertFalse(tech.effects, tech.id)
                self.assertEqual(generator.icon_for_technology(branch, i), tech.icon)
                self.assertIn(tech.icon, generator.NAVAL_HULL_ART)
                with Image.open(ROOT / f"gfx/interface/technologies/{tech.icon}.dds") as image:
                    self.assertEqual(image.size, (176, 72))
                    self.assertIsNotNone(image.convert("RGBA").getchannel("A").getbbox())
                if tier:
                    self.assertIn(
                        f"parent = ADISCORD_{family}_{generator.NAVAL_HULL_YEARS[tier - 1]}", equipment[model]
                    )
                self.assertIn(tech.id, generator.render_technology(branch, i))
        for key in ("naval_support", "surface_fleet", "subsurface"):
            branch = generator.BRANCH_BY_KEY[key]
            self.assertIn("mtgnavalsupportfolder", branch.folders)
            self.assertNotIn("mtgnavalfolder", branch.folders)
            for tech in branch.techs:
                self.assertNotIn(tech.id, generator.ENABLE_EQUIPMENT)

    def test_carrier_generations_unlock_usable_air_groups(self):
        equipment = validator.collect_equipment_blocks()
        air_units = (ROOT / "common/units/ADISCORD_air_units.txt").read_text(encoding="utf-8")
        enum = (ROOT / "common/script_enums.txt").read_text(encoding="utf-8")
        for year in generator.NAVAL_HULL_YEARS:
            unlocked = generator.ENABLE_EQUIPMENT[f"ADISCORD_tech_carrier_hull_{year}"]
            self.assertEqual(unlocked, (f"ADISCORD_carrier_{year}",))
            self.assertRegex(equipment[f"ADISCORD_carrier_{year}"], r"carrier_size = [4-9]|carrier_size = 10")
            for family in ("cv_fighter", "cv_bomber"):
                model = f"ADISCORD_{family}_{year}"
                aircraft_tech = f"ADISCORD_tech_{family}_research_{year}"
                self.assertEqual(generator.ENABLE_EQUIPMENT[aircraft_tech], (model,))
                self.assertIn("carrier_capable = yes", equipment[model])
                self.assertIn(model, enum)
                self.assertIn(f"ADISCORD_{family}_archetype = 1", air_units)
        self.assertIn("naval_strike_attack", equipment["ADISCORD_cv_bomber_2155"])
        self.assertIn("ai_type = cv_naval_bomber", equipment["ADISCORD_cv_bomber_archetype"])
        self.assertIn("air_superiority", equipment["ADISCORD_cv_fighter_2155"])
        self.assertEqual(air_units.count("carrier_air_wing_size = 10"), 2)

    def test_naval_programmes_branch_without_blocking_hull_replacement(self):
        for kind, programmes in generator.NAVAL_SIDE_PROGRAMMES.items():
            branch = generator.BRANCH_BY_KEY[f"{kind}_hulls"]
            graph = generator.BRANCH_GRAPHS[branch.key]
            indices = {tech.key: i for i, tech in enumerate(branch.techs)}
            hulls = [indices[f"{kind}_hull_{year}"] for year in generator.NAVAL_HULL_YEARS]
            self.assertGreater(len(set(graph.lanes)), 1)
            self.assertGreater(len(graph.successors[hulls[0]]), 1)
            self.assertEqual(sum(not targets for targets in graph.successors), int(kind != "carrier") + len(programmes))
            for earlier, later in zip(hulls, hulls[1:]):
                self.assertIn(later, graph.successors[earlier])
                self.assertFalse(graph.dependencies[later])
            for programme in programmes:
                for earlier, later in zip(programme, programme[1:]):
                    self.assertIn(indices[later], graph.successors[indices[earlier]])
        self.assertEqual(
            generator.horizontal_year_columns("naval_folder"),
            generator.horizontal_year_columns("mtgnavalfolder"),
        )

    def test_naval_refits_preserve_their_original_effects_and_prices(self):
        for key, (origin, old_index) in generator.NAVAL_UPGRADE_ORIGINS.items():
            branch, index = generator.TECH_POSITION_BY_ID[f"ADISCORD_tech_{key}"]
            self.assertEqual(branch.techs[index].effects, origin.techs[old_index].effects)
            self.assertEqual(branch.years[index], origin.years[old_index])
            self.assertEqual(
                generator.research_cost_for(branch, index, (), ()),
                generator.research_cost_for(origin, old_index, (), ()),
            )
        for year in generator.NAVAL_HULL_YEARS:
            for family in ("cv_fighter", "cv_bomber"):
                branch, index = generator.TECH_POSITION_BY_ID[f"ADISCORD_tech_{family}_research_{year}"]
                graph = generator.BRANCH_GRAPHS[branch.key]
                parents = [branch.techs[i].id for i, targets in enumerate(graph.successors) if index in targets]
                self.assertIn(f"ADISCORD_tech_carrier_hull_{year}", parents)
                if year != generator.NAVAL_HULL_YEARS[0]:
                    self.assertEqual(len(graph.dependencies[index]), 2)

    def test_new_ship_classes_are_not_granted_to_every_country(self):
        common = set(generator.STARTING_TECH_PROFILES["common"])
        naval = set(generator.STARTING_TECH_PROFILES["naval"])
        for kind in generator.NAVAL_HULL_CLASSES:
            root = f"ADISCORD_tech_{kind}_hull_2155"
            self.assertNotIn(root, common)
            self.assertEqual(root in naval, kind in {"destroyer", "heavy_cruiser", "submarine"})
        gui = generator.render_folder("mtgnavalfolder")
        self.assertEqual(gui.count("gridboxtype = {"), 6)
        self.assertNotIn('name = "ADISCORD_branch_naval_support"', gui)

    def test_aircraft_research_opens_bomber_and_maritime_production(self) -> None:
        blocks = validator.collect_equipment_blocks()
        for family in (
            'ADISCORD_bomber_archetype',
            'ADISCORD_naval_aircraft_archetype',
        ):
            variants = {
                key
                for key, block in blocks.items()
                if re.search(rf'archetype\s*=\s*{family}\b', block)
            }
            self.assertGreaterEqual(len(variants), 3, family)
            unlocks = {
                equipment
                for items in generator.ENABLE_EQUIPMENT.values()
                for equipment in items
            }
            self.assertTrue(variants <= unlocks, variants - unlocks)

    def test_new_equipment_has_deployable_units_and_native_missions(self) -> None:
        equipment = validator.collect_equipment_blocks()
        units = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "common/units").glob("*.txt")
        )
        roles = {
            "ADISCORD_cruiser_archetype": ("heavy_cruiser", None),
            "ADISCORD_submarine_archetype": ("submarine", None),
            "ADISCORD_bomber_archetype": (
                "ADISCORD_tactical_bomber",
                {"strategic_bomber", "cas", "attack_logistics"},
            ),
            "ADISCORD_naval_aircraft_archetype": (
                "nav_bomber",
                {"naval_bomber", "port_strike", "naval_patrol"},
            ),
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

    def test_new_programmes_are_researched_instead_of_granted_to_every_country(
        self,
    ) -> None:
        common = set(generator.STARTING_TECH_PROFILES["common"])
        self.assertNotIn("ADISCORD_tech_reconstituted_staff_academies", common)
        self.assertNotIn("ADISCORD_tech_twin_engine_aircraft", common)
        self.assertNotIn("ADISCORD_tech_casualty_evacuation", common)
        self.assertIn(
            "ADISCORD_tech_casualty_evacuation",
            generator.STARTING_TECH_PROFILES["land"],
        )

    def test_cruiser_and_submarine_ai_groups_are_optional_reinforcements(self) -> None:
        taskforces = (
            ROOT / "common/ai_navy/taskforce/ADISCORD_taskforce_templates.txt"
        ).read_text(encoding="utf-8")
        fleets = (ROOT / "common/ai_navy/fleet/ADISCORD_fleet_templates.txt").read_text(
            encoding="utf-8"
        )
        for taskforce, unit in (
            ("ADISCORD_cruiser_strike", "heavy_cruiser"),
            ("ADISCORD_submarine_raiding", "submarine"),
        ):
            match = re.search(rf"\b{taskforce}\s*=\s*\{{", taskforces)
            self.assertIsNotNone(match, taskforce)
            block = validator.extract_block(taskforces, match.start())
            self.assertRegex(
                block, rf"min_composition\s*=\s*\{{\s*{unit}\s*=\s*\{{\s*amount\s*=\s*1"
            )
            self.assertRegex(block, r"NOT\s*=\s*\{\s*has_tech\s*=")
            self.assertRegex(
                fleets, rf"optional_taskforces\s*=\s*\{{[^}}]*\b{taskforce}\s*=\s*1"
            )
            self.assertNotRegex(
                fleets, rf"required_taskforces\s*=\s*\{{[^}}]*\b{taskforce}\s*="
            )

    def test_budget_research_has_bounded_consumed_modifiers_and_refreshes_cache(
        self,
    ) -> None:
        branch = generator.BRANCH_BY_KEY.get("public_finance")
        self.assertIsNotNone(branch, "Public finance must be a playable research line")
        definitions = (
            ROOT
            / "common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt"
        ).read_text(encoding="utf-8-sig")
        consumers = (
            ROOT / "common/scripted_effects/ADISCORD_economy_modifier_effects.txt"
        ).read_text(encoding="utf-8-sig")
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

    def test_rare_material_supply_precedes_equipment_and_has_research_gates(
        self,
    ) -> None:
        buildings = validator.collect_building_blocks()
        equipment = validator.collect_equipment_blocks()
        for resource, building, unlock in (
            (
                "rare_components",
                "ADISCORD_rare_components_plant",
                "ADISCORD_tech_rare_components_industry",
            ),
            (
                "rare_alloys",
                "ADISCORD_rare_alloy_foundry",
                "ADISCORD_tech_rare_alloy_metallurgy",
            ),
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
                            consumer_branch, consumer_index = (
                                generator.TECH_POSITION_BY_ID[tech_id]
                            )
                            consumers.append(item)
                            self.assertLess(
                                supply_year, consumer_branch.years[consumer_index], item
                            )
                self.assertGreater(len(set(consumers)), 4)
                upgrades = [
                    amount
                    for entries in generator.BUILDING_RESOURCE_UPGRADES.values()
                    for target, res, amount in entries
                    if target == building and res == resource
                ]
                self.assertTrue(upgrades)
                self.assertLessEqual(sum(upgrades), 4)

    def test_inherited_material_plants_and_budget_profile_grants_remain_usable(
        self,
    ) -> None:
        unlocks = {
            "ADISCORD_tech_rare_components_industry",
            "ADISCORD_tech_rare_alloy_metallurgy",
        }
        for tag in ("WRK", "RIV"):
            starting = set(generator.STARTING_TECH_PROFILES["common"])
            for profile in generator.STARTING_COUNTRY_TECH_PROFILES[tag]:
                starting.update(generator.STARTING_TECH_PROFILES[profile])
            self.assertTrue(unlocks <= starting, tag)
        branch, index = generator.TECH_POSITION_BY_ID[
            "ADISCORD_tech_predictive_maintenance"
        ]
        rendered = generator.render_technology(branch, index)
        self.assertEqual(rendered.count("on_research_complete = {"), 1)
        self.assertIn("add_tech_bonus = {", rendered)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", rendered)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "common/scripted_effects").mkdir(parents=True)
            with patch.object(generator, "ROOT", root):
                generator.write_starting_technology_effect()
            text = (
                root
                / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt"
            ).read_text(encoding="utf-8")
        common = validator.extract_block(
            text, text.index("ADISCORD_grant_technology_profile_common = {")
        )
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
            service_sprites = {
                f"GFX_{tag}_{tech}_medium"
                for tech, icon in generator.EQUIPMENT_UNLOCK_ICONS.items()
                if icon.startswith("ADISCORD_weapon_")
            }
            regional = {
                name: texture
                for name, texture in sprites.items()
                if name in service_sprites
            }
            self.assertEqual(set(regional), service_sprites)
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
            reordered = replace(
                branch, techs=branch.techs[::-1], years=branch.years[::-1]
            )
            for index, tech in enumerate(branch.techs):
                other = len(branch.techs) - 1 - index
                self.assertEqual(
                    generator.effects_for(branch, index),
                    generator.effects_for(reordered, other),
                    tech.id,
                )
                self.assertEqual(
                    generator.icon_for_technology(branch, index),
                    generator.icon_for_technology(reordered, other),
                    tech.id,
                )

    def test_equipment_family_localisation_replaces_old_names_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for language in ("russian", "english"):
                path = (
                    root
                    / "localisation"
                    / language
                    / f"ADISCORD_technology_doctrine_l_{language}.yml"
                )
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
                self.assertEqual(
                    len(re.findall(r"^ infantry_equipment:", text, re.MULTILINE)), 1
                )
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
                with self.assertRaisesRegex(
                    RuntimeError, "technology state GFX is stale"
                ):
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
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(
            encoding="utf-8-sig"
        )
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
                    rf'name = "{generator.technology_tree_root(branch)}_tree".*?'
                    r'slotsize = \{ width = \d+ height = (\d+) \}',
                    rendered,
                    flags=re.DOTALL,
                )
                self.assertIsNotNone(grid, branch.key)
                rows = sorted(
                    {
                        self._folder_positions(
                            generator.render_technology(branch, index)
                        )[folder][0]
                        * int(grid[1])
                        for index in range(len(branch.techs))
                    }
                )
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
                    rendered, "gridboxtype", generator.technology_tree_root(branch) + "_tree"
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
                    self.assertEqual(
                        label_rows[(branch.key, branch.years[index])], node_top + 24
                    )

    def test_only_industry_has_exclusive_research(self) -> None:
        self.assertEqual(
            generator.XOR_KIND_BY_BRANCH,
            {
                "production": "temporary",
                "industry_organization": "permanent",
            },
        )
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
        self.assertTrue(
            any("industrial_capacity_factory" in entry for entry in effects)
        )
        self.assertTrue(any("factory_energy_consumption" in entry for entry in effects))
        self.assertTrue(any("industry_air_damage_factor" in entry for entry in effects))

        concentrated_notes = generator.technology_description_notes(
            organization, 1, False
        )
        self.assertTrue(any("Energy price:" in note for note in concentrated_notes))
        self.assertTrue(
            any(
                "Permanent specialization choice:" in note
                for note in concentrated_notes
            )
        )
        self.assertFalse(
            any("common line continues" in note for note in concentrated_notes)
        )

    def test_every_legacy_id_has_one_migration_outcome(self) -> None:
        payload = json.loads(LEGACY_MANIFEST.read_text(encoding="utf-8"))
        legacy_ids = {row["id"] for row in payload["technologies"]}
        migrations = getattr(generator, "TECHNOLOGY_ID_MIGRATIONS", {})
        self.assertEqual(set(migrations), legacy_ids)
        self.assertTrue(
            all(
                entry["status"] in {"preserved", "replaced", "removed"}
                for entry in migrations.values()
            )
        )
        current_ids = {
            tech.id for branch in generator.BRANCHES for tech in branch.techs
        }
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
                    self.assertFalse(
                        choices <= granted, f"{profile}: {sorted(choices)}"
                    )

    def test_starting_profile_manifest_is_machine_readable_and_bounded(self) -> None:
        payload = json.loads(STARTING_PROFILE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(payload["active_country_count"], len(payload["countries"]))
        self.assertEqual(
            set(payload["countries"]), set(generator.STARTING_COUNTRY_TECH_PROFILES)
        )
        self.assertEqual(
            set(generator.STARTING_COUNTRY_TECH_PROFILE_RATIONALE),
            set(generator.STARTING_COUNTRY_TECH_PROFILES),
        )
        self.assertEqual(
            {
                tag
                for tag, profiles in generator.STARTING_COUNTRY_TECH_PROFILES.items()
                if not profiles
            },
            {"EXZ", "PWR", "RSV"},
        )
        for tag, entry in payload["countries"].items():
            self.assertGreaterEqual(len(entry["rationale"]), 24, tag)
            self.assertGreaterEqual(entry["evidence"]["states"], 1, tag)
        self.assertLess(
            len(generator.STARTING_TECH_PROFILES["late_2183"]),
            len({tech.id for branch in generator.BRANCHES for tech in branch.techs})
            // 4,
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
            building: int(
                re.search(r"\bicon_frame\s*=\s*(\d+)", buildings[building]).group(1)
            )
            for building in (
                "ADISCORD_metallurgical_complex",
                "ADISCORD_electrolysis_complex",
                "ADISCORD_strategic_mining_complex",
                "ADISCORD_thermal_power_complex",
            )
        }
        self.assertEqual(
            frames,
            {
                "ADISCORD_metallurgical_complex": 35,
                "ADISCORD_electrolysis_complex": 36,
                "ADISCORD_strategic_mining_complex": 37,
                "ADISCORD_thermal_power_complex": 38,
            },
        )
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

    def test_stp_starting_profile_unlocks_its_capital_guard_recon_platform(
        self,
    ) -> None:
        granted = set(generator.STARTING_TECH_PROFILES["common"])
        for profile in generator.STARTING_COUNTRY_TECH_PROFILES["STP"]:
            granted.update(generator.STARTING_TECH_PROFILES[profile])
        self.assertIn("ADISCORD_tech_drone_recon_swarms", granted)

    def test_weapon_technologies_have_authored_technical_descriptions(self) -> None:
        keys = {
            tech.key
            for branch_key in ("small_arms", "assault_rifles", "anti_tank_infantry")
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

    def test_infantry_equipment_visual_levels_mark_real_weapon_generations(
        self,
    ) -> None:
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

    def test_weapon_generation_names_are_concrete_and_generated_in_both_languages(
        self,
    ) -> None:
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
        expected_ids.update({
            "ADISCORD_power_shield_equipment",
            "ADISCORD_power_shield_equipment_1",
            "ADISCORD_power_shield_equipment_2",
            "ADISCORD_power_shield_equipment_3",
        })
        self.assertEqual(set(generator.LAND_EQUIPMENT_LOCALISATION), expected_ids)
        for language in ("russian", "english"):
            rendered = "\n".join(generator.generated_localisation(language))
            for equipment_id in expected_ids:
                self.assertIn(f" {equipment_id}:0 ", rendered)
                self.assertIn(f" {equipment_id}_short:0 ", rendered)
                self.assertIn(f" {equipment_id}_desc:0 ", rendered)
        russian = "\n".join(generator.generated_localisation("russian"))
        english = "\n".join(generator.generated_localisation("english"))
        self.assertIn(r'АВ-63 \"Рёв\"', russian)
        self.assertIn(r'КОП-70 \"Гул\"', russian)
        self.assertIn(r'AR-63 \"Roar\"', english)
        self.assertIn(r'FSC-70 \"Rumble\"', english)
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
                description = generator.LAND_EQUIPMENT_LOCALISATION[equipment_id][
                    4
                ].lower()
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
        self.assertTrue(
            {
                "production",
                "industry_organization",
                "advanced_materials",
                "bomber_maritime",
                "squad_weapons",
                "night_combat",
                "anti_tank_infantry",
                "protection",
                "special_forces",
                "combat_armor",
                "artillery",
            }
            <= forks
        )

    def test_infantry_components_remain_independent_research_programmes(self) -> None:
        for target, unrelated in (
            ("sealed_receiver_assemblies", "smart_optics"),
            ("squad_target_sharing", "counter_illumination_warnings"),
            ("programmable_anti_armor_fuzes", "fire_and_forget_seekers"),
            ("hard_kill_protection_arrays", "adaptive_fire_control"),
            ("counterbattery_radar_links", "assisted_projectiles"),
        ):
            required = generator.technology_prerequisite_closure(
                (f"ADISCORD_tech_{target}",)
            )
            self.assertNotIn(f"ADISCORD_tech_{unrelated}", required)
        integrated = generator.technology_prerequisite_closure(
            ("ADISCORD_tech_networked_service_rifles",)
        )
        self.assertTrue(
            {
                "ADISCORD_tech_coil_assisted_service_rifles",
                "ADISCORD_tech_integrated_target_designation",
                "ADISCORD_tech_hybrid_kinetic_energy_carbines",
            }
            <= set(integrated)
        )

    def test_infantry_and_armor_retain_horizontal_programme_layouts(self) -> None:
        self.assertTrue(
            {"infantry_folder", "armour_folder"} <= generator.HORIZONTAL_FOLDERS
        )
        self.assertNotIn("industry_folder", generator.HORIZONTAL_FOLDERS)
        infantry = {b.key for b in generator.BRANCHES if "infantry_folder" in b.folders}
        self.assertIn("special_forces", infantry)
        self.assertEqual(len(generator.BRANCH_BY_KEY["small_arms"].techs), 8)
        self.assertEqual(len(generator.BRANCH_BY_KEY["assault_rifles"].techs), 25)
        for branch in generator.BRANCHES:
            cells = [
                generator.technology_grid_position(branch, i)
                for i in range(len(branch.techs))
            ]
            self.assertEqual(len(cells), len(set(cells)), branch.key)

    def test_medicine_and_rail_guns_have_one_semantic_owner(self) -> None:
        medicine = generator.BRANCH_BY_KEY["combat_medicine"]
        self.assertEqual(medicine.folders, ("support_folder",))
        medical_ids = {tech.key for tech in medicine.techs}
        self.assertTrue(
            {
                "casualty_evacuation",
                "battlefield_medical_drones",
                "smart_tourniquet_systems",
            }.issubset(medical_ids)
        )
        for branch_key in ("protection", "field_support"):
            for tech in generator.BRANCH_BY_KEY[branch_key].techs:
                self.assertNotIn("field_hospital", " ".join(tech.effects))
        rail = generator.BRANCH_BY_KEY["rail"]
        for tech in rail.techs:
            self.assertNotIn("artillery", " ".join(tech.effects))
        guns = generator.BRANCH_BY_KEY["railway_artillery"]
        self.assertEqual(guns.folders, ("artillery_folder",))
        self.assertEqual(
            {
                equipment
                for tech in guns.techs
                for equipment in generator.ENABLE_EQUIPMENT.get(tech.id, ())
            },
            {"railway_gun_equipment_1", "ADISCORD_railway_gun_equipment_2200"},
        )

    def test_every_producible_family_and_building_cap_remains_reachable(self) -> None:
        _, blocks = validator.collect_technologies()
        self.assertEqual(
            validator.check_equipment_unlocks(
                blocks, validator.collect_equipment_keys()
            ),
            [],
        )
        self.assertEqual(
            validator.check_generated_capability_unlock_contract(blocks), []
        )
        self.assertTrue(set(generator.ENABLE_EQUIPMENT) <= generator.CURRENT_TECH_IDS)
        self.assertTrue(set(generator.ENABLE_SUBUNITS) <= generator.CURRENT_TECH_IDS)
        self.assertTrue(set(generator.ENABLE_BUILDINGS) <= generator.CURRENT_TECH_IDS)
        for building, minimum in (
            ("radar_station", 6),
            ("rocket_site", 3),
            ("anti_air_building", 5),
            ("synthetic_refinery", 3),
        ):
            caps = [
                level
                for entries in generator.ENABLE_BUILDINGS.values()
                for name, level in entries
                if name == building
            ]
            self.assertEqual(max(caps), minimum)

    def test_all_technology_cards_use_available_artwork(self) -> None:
        sprites = validator.collect_sprite_names()
        for branch in generator.BRANCHES:
            for tech in branch.techs:
                texture = sprites[f"GFX_{tech.id}_medium"]
                self.assertTrue(
                    validator.texture_has_valid_dimensions(texture), texture
                )
                self.assertTrue(
                    (ROOT / texture).is_file()
                    or (generator.BASE_GAME / texture).is_file(),
                    texture,
                )

    def test_vertical_layout_rejects_wrong_branch_coordinates(self) -> None:
        _, blocks = validator.collect_technologies()
        tech_id = "ADISCORD_tech_postwar_weapon_standardization"
        broken = dict(blocks)
        broken[tech_id] = broken[tech_id].replace(
            "position = { x = 0 y = 0 }", "position = { x = 2 y = 0 }", 1
        )
        self.assertNotEqual(broken[tech_id], blocks[tech_id])
        self.assertTrue(
            any(
                tech_id in issue and "grid position" in issue
                for issue in validator.check_technology_parser_constraints(broken)
            )
        )


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
                for field, value in (
                    ("active", "no"),
                    ("regimental", "yes"),
                    ("divisional", "no"),
                    ("group", "support"),
                    ("affects_speed", "no"),
                    ("combat_width", "0"),
                ):
                    self.assertRegex(block, rf"\b{field}\s*=\s*{value}\b")
                self.assertIn("category_regimental_support_battalions", block)
                self.assertNotIn("category_divisional_support_battalions", block)
                groups = re.search(r"allowed_battalion_groups\s*=\s*\{([^}]+)\}", block)
                self.assertIsNotNone(groups)
                self.assertTrue(
                    {"infantry", "mobile", "armor"} <= set(groups[1].split())
                )
                manpower = int(re.search(r"\bmanpower\s*=\s*(\d+)", block)[1])
                self.assertGreater(manpower, 0)
                self.assertLessEqual(manpower, 240)
                need = re.search(r"\bneed\s*=\s*\{([^}]+)\}", block)[1]
                requirements = dict(re.findall(r"(\w+)\s*=\s*(\d+)", need))
                self.assertNotIn("infantry_equipment", requirements)
                crew_served = int(requirements["ADISCORD_squad_weapons_equipment"])
                other = sum(
                    int(quantity)
                    for archetype, quantity in requirements.items()
                    if archetype != "ADISCORD_squad_weapons_equipment"
                )
                self.assertGreater(crew_served, other)
                for archetype, quantity in requirements.items():
                    self.assertGreater(int(quantity), 0)
                    self.assertIn(archetype, equipment)
                    self.assertRegex(equipment[archetype], r"\bis_archetype\s*=\s*yes")
                    self.assertRegex(
                        equipment[archetype],
                        r"\bbuild_cost_ic\s*=\s*[1-9]|\bbuild_cost_ic\s*=\s*0\.[0-9]*[1-9]",
                    )

    def test_unlocks_are_reachable_and_basic_support_is_granted_at_start(self) -> None:
        _, blocks = validator.collect_technologies()
        for key, technology in self.UNLOCKS.items():
            self.assertIn(key, generator.ENABLE_SUBUNITS[technology])
            self.assertRegex(
                blocks[technology], rf"enable_subunits\s*=\s*\{{[^}}]*\b{key}\b"
            )
            required = generator.technology_prerequisite_closure((technology,))
            self.assertTrue(set(required) <= generator.CURRENT_TECH_IDS)
        self.assertIn(
            self.UNLOCKS["ADISCORD_regimental_fire_support"],
            generator.STARTING_TECH_PROFILES["common"],
        )
        for key in (
            "ADISCORD_regimental_anti_air",
            "ADISCORD_regimental_anti_tank",
            "ADISCORD_regimental_pioneers",
        ):
            self.assertIn(self.UNLOCKS[key], generator.STARTING_TECH_PROFILES["land"])

    def test_starting_elite_support_has_eligible_columns_and_unlocked_units(
        self,
    ) -> None:
        from collections import Counter
        from tools.validators import validate_adiscord_division_templates as divisions

        templates, references, issues = divisions.collect_templates_and_references(ROOT)
        self.assertEqual(issues, [])
        supported = [
            template
            for template in templates
            if template.source_kind == "oob"
            and any(slot.kind == "regimental_support" for slot in template.slots)
        ]
        self.assertEqual(len(supported), 14)
        deployed = 0
        for template in supported:
            with self.subTest(owner=template.owner, template=template.name):
                technologies = set(generator.STARTING_TECH_PROFILES["common"])
                for profile in generator.STARTING_COUNTRY_TECH_PROFILES[template.owner]:
                    technologies.update(generator.STARTING_TECH_PROFILES[profile])
                columns = Counter(
                    slot.x for slot in template.slots if slot.kind == "regiments"
                )
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
                    self.assertNotEqual(
                        slot.unit, "ADISCORD_regimental_drone_observers"
                    )
                matching = [
                    reference
                    for reference in references
                    if reference.kind == "oob"
                    and reference.path == template.path
                    and reference.name == template.name
                ]
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
                path = (
                    ROOT
                    / "localisation"
                    / language
                    / f"ADISCORD_technology_doctrine_l_{language}.yml"
                )
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                text = path.read_text(encoding="utf-8-sig")
                for suffix in ("", "_desc"):
                    self.assertEqual(
                        len(re.findall(rf'^ {key}{suffix}:0 "[^"\r\n]+"$', text, re.M)),
                        1,
                    )

    def test_support_roles_receive_their_existing_research_upgrades(self) -> None:
        for branch in ("anti_air", "anti_tank", "special_forces"):
            target = {
                "anti_air": "category_anti_air",
                "anti_tank": "category_anti_tank",
                "special_forces": "category_recon",
            }[branch]
            self.assertTrue(
                any(
                    target + " = {" in effect
                    for tech in generator.BRANCH_BY_KEY[branch].techs
                    for effect in tech.effects
                )
            )
        upgrades = [
            effect
            for branch in generator.BRANCHES
            for tech in branch.techs
            for effect in tech.effects
            if effect.startswith("ADISCORD_regimental_pioneers =")
        ]
        self.assertGreaterEqual(len(upgrades), 3)



class InfantryRoleAndShieldTests(unittest.TestCase):
    @staticmethod
    def read(path):
        return (ROOT / path).read_text(encoding="utf-8-sig")

    @staticmethod
    def block(text, key):
        match = re.search(r"(?m)^\s*" + re.escape(key) + r"\s*=\s*\{", text)
        if match is None:
            raise AssertionError(f"Missing block: {key}")
        return validator.extract_block(text, match.start())

    def test_squad_training_covers_actual_formations_without_full_rifle_only_bonus(self):
        from tools.validators import validate_adiscord_division_templates as templates
        units, issues = templates._collect_subunits(ROOT)
        self.assertEqual(issues, [])
        affected = {
            name for name, unit in units.items()
            if "category_all_infantry" in unit.categories and name != "fake_intel_unit"
        }
        self.assertEqual(set(generator.SQUAD_WEAPON_TRAINING_SCALE), affected)
        branch = generator.BRANCH_BY_KEY["squad_weapons"]
        totals = {name: Decimal(0) for name in affected}
        for index in range(len(branch.techs)):
            effects = "\n".join(generator.effects_for(branch, index))
            self.assertNotIn("category_all_infantry", effects)
            for name in affected:
                if name + " = {" not in effects:
                    continue
                block = self.block(effects, name)
                value = re.search(r"\bsoft_attack = ([0-9.]+)", block)
                if value:
                    totals[name] += Decimal(value[1])
        self.assertLess(totals["ADISCORD_militia"], totals["ADISCORD_territorial"])
        self.assertLess(totals["ADISCORD_territorial"], totals["ADISCORD_urban_breacher"])
        self.assertLess(totals["ADISCORD_urban_breacher"], totals["infantry"])
        self.assertEqual(totals["infantry"], Decimal("0.476"))
        for unit in ("ADISCORD_assault_infantry", "mountaineers", "ADISCORD_marine_infantry", "ADISCORD_mechanized_infantry"):
            self.assertEqual(totals[unit], totals["infantry"])

    def test_shield_upgrades_follow_the_project_granted_base_technology(self):
        branch = generator.BRANCH_BY_KEY["power_shields"]
        self.assertEqual(branch.years, (2163, 2166, 2169, 2172, 2175))
        self.assertEqual(branch.folders, (generator.SPECIAL_TECHNOLOGY_FOLDER,))
        self.assertIn("power_shields", generator.MAIN_BRANCH_KEYS_BY_FOLDER[generator.SPECIAL_TECHNOLOGY_FOLDER])
        self.assertNotIn("power_shields", generator.MAIN_BRANCH_KEYS_BY_FOLDER["infantry_folder"])
        for index, tech in enumerate(branch.techs):
            if index == 0:
                self.assertEqual(generator.ALLOW[tech.id], (
                    "is_special_project_completed = sp:ADISCORD_sp_power_shields",
                ))
            else:
                self.assertNotIn(tech.id, generator.ALLOW)
                self.assertEqual(generator.research_allow_for(branch, index), (
                    "has_tech = ADISCORD_tech_kefreyt_shield_special_forces",
                ))
            self.assertEqual(generator.xor_siblings(branch, index), ())
            for profile in generator.STARTING_TECH_PROFILES.values():
                self.assertNotIn(tech.id, profile)
            self.assertEqual(
                set(generator.technology_prerequisite_closure((tech.id,))),
                {item.id for item in branch.techs[:index + 1]},
            )
        root = generator.render_technology(branch, 0)
        self.assertIn("enable_subunits = { ADISCORD_urban_breacher }", root)
        self.assertIn("ADISCORD_power_shield_equipment_1", root)
        self.assertNotIn("kefreyt_shield_special_forces", self.read("common/technologies/ADISCORD_VAL_marines.txt"))

    def test_shield_project_unlocks_its_technology_without_circular_prerequisites(self):
        from tools.tests.test_adiscord_combat_robots import read_script, value

        project = value(read_script("common/special_projects/projects/land_projects.txt"),
                        "ADISCORD_sp_power_shields")
        available = value(value(project, "available"), "FROM")
        required = [entry.value for entry in available if entry.key == "has_tech"]
        base = "ADISCORD_tech_kefreyt_shield_special_forces"
        closure = generator.technology_prerequisite_closure(required)
        self.assertNotIn(base, closure)
        self.assertTrue(set(required) <= generator.TECH_POSITION_BY_ID.keys())
        source = self.block(self.read("common/special_projects/projects/land_projects.txt"),
                            "ADISCORD_sp_power_shields")
        self.assertRegex(source, r"date\s*>\s*2162\.12\.31")
        self.assertEqual(value(available, "has_capitulated"), "no")
        self.assertEqual(value(project, "specialization"), "specialization_land")
        self.assertEqual(value(value(project, "breakthrough_cost"), "specialization_land"), "1")
        self.assertEqual(value(project, "prototype_time"), "sp_time.prototype.medium")
        output = value(value(project, "project_output"), "country_effects")
        self.assertEqual(value(value(output, "set_technology"), base), "1")
        for forbidden in ("create_unit", "add_equipment_to_stockpile", "complete_special_project"):
            self.assertNotIn(forbidden, repr(output))
        root = generator.render_technology(generator.BRANCH_BY_KEY["power_shields"], 0)
        self.assertIn("is_special_project_completed = sp:ADISCORD_sp_power_shields", root)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_special_projects_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in ("ADISCORD_sp_power_shields", "ADISCORD_sp_power_shields_desc",
                        "ADISCORD_power_shields_template_tt"):
                self.assertEqual(len(re.findall(r"^ " + key + ":0 ", text, re.M)), 1)

    def test_national_focus_rewards_complete_the_project_before_equipment_delivery(self):
        from tools.tests.test_adiscord_combat_robots import read_script, value

        project_id = "sp:ADISCORD_sp_power_shields"
        for path, name, delivery in (
            ("common/scripted_effects/ADISCORD_VAL_effects.txt", "VAL_raise_shield_special_forces", "create_unit"),
            ("common/scripted_effects/ADISCORD_STP_scripted_effects.txt", "STP_pw_open_shield_corps", "add_equipment_to_stockpile"),
        ):
            effect = self.block(self.read(path), name)
            self.assertIn("NOT = {", effect)
            self.assertIn("is_special_project_completed = " + project_id, effect)
            self.assertIn("complete_special_project = " + project_id, effect)
            self.assertNotIn("set_technology", effect)
            self.assertLess(effect.index("complete_special_project"), effect.index(delivery))
        project = value(read_script("common/special_projects/projects/land_projects.txt"),
                        "ADISCORD_sp_power_shields")
        output = value(value(project, "project_output"), "country_effects")
        generic = value(output, "if")
        excluded = value(value(value(generic, "limit"), "NOT"), "OR")
        self.assertEqual({entry.value for entry in excluded if entry.key == "tag"}, {"VAL", "STP", "STS"})

    def test_project_and_national_templates_are_complete_recruitable_city_formations(self):
        from tools.validators import validate_adiscord_division_templates as templates

        actual, _, _ = templates.collect_templates_and_references(ROOT)
        units, issues = templates._collect_subunits(ROOT)
        self.assertEqual(issues, [])
        archetypes, issues = templates._collect_equipment_archetypes(ROOT)
        self.assertEqual(issues, [])
        for name in ("Shield Assault Division", "Stelander Shield Brigade", "Kefreyt Shield Special Forces"):
            matches = [item for item in actual if item.name == name]
            self.assertEqual(len(matches), 1, name)
            template = matches[0]
            self.assertFalse(template.is_locked, name)
            shields = [slot for slot in template.slots if slot.kind == "regiments"]
            self.assertEqual(len(shields), 10, name)
            self.assertEqual({slot.unit for slot in shields}, {"ADISCORD_urban_breacher"})
            support = {slot.unit for slot in template.slots if slot.kind == "support"}
            self.assertTrue({"engineer", "artillery"} <= support, name)
            self.assertLessEqual(len(support), 5, name)
            computed, issues = templates._compute_template(template, units, archetypes, {})
            self.assertEqual(issues, [], name)
            self.assertEqual(computed.equipment["ADISCORD_power_shield_equipment"], 200, name)
            self.assertGreater(computed.organization, 45, name)
            if name != "Kefreyt Shield Special Forces":
                self.assertEqual(computed.manpower, 10600, name)

    def test_balance_validator_counts_distributed_training_without_hiding_bad_payloads(self):
        branch = generator.BRANCH_BY_KEY["squad_weapons"]
        _, blocks = validator.collect_technologies()
        initial = validator.check_post_2160_research_balance(blocks)
        ids = {tech.id for tech in branch.techs}
        self.assertFalse([issue for issue in initial if any(key in issue for key in ids)])
        tech = branch.techs[0]
        block = blocks[tech.id]
        role = self.block(block, "ADISCORD_territorial")
        mutations = (
            block.replace(role, ""),
            block.replace(role, role + "\n" + role),
            block.replace(role, re.sub(r"soft_attack = [0-9.]+", "soft_attack = 1", role)),
            block.replace(role, role + " armor_value = 0.5 "),
            block.replace(role, role + " } category_all_infantry = { soft_attack = 0.1 "),
            block.replace(role, role + " } fake_intel_unit = { soft_attack = 0.1 "),
        )
        for mutation in mutations:
            issues = validator.check_post_2160_research_balance({**blocks, tech.id: mutation})
            self.assertTrue(any(
                tech.id in issue and "invalid distributed training" in issue
                for issue in issues
            ))

    def test_shield_generations_require_both_rare_resources_and_preserve_rifle_visuals(self):
        equipment = validator.collect_equipment_blocks()
        archetype = equipment["ADISCORD_power_shield_equipment"]
        self.assertIn("is_buildable = no", archetype)
        self.assertNotIn("active = yes", archetype)
        prices = []
        for tier, year in enumerate((2163, 2169, 2175), 1):
            block = equipment[f"ADISCORD_power_shield_equipment_{tier}"]
            self.assertIn(f"year = {year}", block)
            self.assertIn("archetype = ADISCORD_power_shield_equipment", block)
            self.assertNotIn("active = yes", block)
            effective = archetype if tier == 1 else block
            for resource in ("rare_components", "rare_alloys"):
                self.assertRegex(effective, rf"\b{resource} = [1-9]")
            prices.append(float(re.search(r"build_cost_ic = ([0-9.]+)", effective)[1]))
            self.assertNotIn("visual_level", block + archetype)
            self.assertNotIn("armor_value", block + archetype)
        self.assertEqual(prices, sorted(set(prices)))
        unit = self.block(self.read("common/units/ADISCORD_land_units.txt"), "ADISCORD_urban_breacher")
        self.assertIn("ADISCORD_power_shield_equipment = 20", unit)
        self.assertIn("ADISCORD_power_shield_equipment", self.block(unit, "essential"))

    def test_every_shield_generation_protects_and_improves_with_its_price(self):
        equipment = validator.collect_equipment_blocks()
        base = equipment["ADISCORD_power_shield_equipment"]
        previous = {"defense": 0, "breakthrough": 0, "build_cost_ic": 0}
        for tier in (1, 2, 3):
            model = equipment[f"ADISCORD_power_shield_equipment_{tier}"]
            for stat in previous:
                pattern = rf"\b{stat} = ([0-9.]+)"
                match = re.search(pattern, model) or re.search(pattern, base)
                self.assertIsNotNone(match, (tier, stat))
                current = float(match[1])
                self.assertGreater(current, previous[stat], (tier, stat))
                previous[stat] = current

    def test_infantry_roles_retain_cost_and_combat_tradeoffs(self):
        source = self.read("common/units/ADISCORD_land_units.txt")
        units = {name: self.block(source, name) for name in (
            "ADISCORD_militia", "ADISCORD_territorial", "infantry",
            "ADISCORD_assault_infantry", "ADISCORD_urban_breacher",
        )}
        def stat(unit, key, default=0):
            match = re.search(r"(?m)^\t\t" + key + r" = (-?[0-9.]+)", units[unit])
            return float(match[1]) if match else default
        self.assertLess(stat("ADISCORD_territorial", "max_organisation"), stat("infantry", "max_organisation"))
        self.assertLess(stat("ADISCORD_territorial", "supply_consumption"), stat("infantry", "supply_consumption"))
        self.assertLess(stat("ADISCORD_territorial", "soft_attack"), stat("infantry", "soft_attack"))
        self.assertGreater(stat("ADISCORD_assault_infantry", "soft_attack"), stat("ADISCORD_urban_breacher", "soft_attack"))
        self.assertGreater(stat("ADISCORD_urban_breacher", "breakthrough"), stat("ADISCORD_assault_infantry", "breakthrough"))
        self.assertGreater(stat("ADISCORD_urban_breacher", "supply_consumption"), stat("ADISCORD_assault_infantry", "supply_consumption"))
        self.assertGreater(stat("ADISCORD_urban_breacher", "training_time"), stat("ADISCORD_assault_infantry", "training_time"))

    def test_city_terrain_preserves_assault_roles_and_armored_penalties(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = self.read("common/units/ADISCORD_land_units.txt")
        units = parse_clausewitz(source)[0].value
        expected = {
            "ADISCORD_urban_breacher": {"attack": 0.65, "defence": 0.60},
            "ADISCORD_assault_infantry": {"attack": 0.10},
            "STP_taran": {"attack": 0.20, "movement": -0.20},
            "ADISCORD_mechanized_infantry": {"attack": -0.10},
            "ADISCORD_combat_platform": {"attack": -0.15},
            "ADISCORD_heavy_platform": {
                "attack": -0.35,
                "defence": -0.15,
                "movement": -0.25,
            },
            "ADISCORD_regimental_pioneers": {"attack": 0.03},
        }
        for terrain in ("urban", "vorkernsberg"):
            affected = {}
            for unit in units:
                modifiers = [entry for entry in unit.value if entry.key == terrain]
                if not modifiers:
                    continue
                self.assertEqual(len(modifiers), 1, unit.key)
                affected[unit.key] = {
                    stat.key: float(stat.value) for stat in modifiers[0].value
                }
            self.assertEqual(affected, expected, terrain)
        terrain_source = self.read("common/terrain/00_terrain.txt")
        self.assertIn("attack = -0.7", self.block(terrain_source, "vorkernsberg"))
        self.assertIn(";vorkernsberg;", self.read("map/definition.csv"))

    def test_city_terrain_preserves_shield_doctrine_reward(self):
        from tools.builders import build_adiscord_doctrine_system as doctrines

        rendered = doctrines.render_schools("special_forces")
        reward = self.block(
            rendered,
            "ADISCORD_special_forces_shield_formations_covered_crossings",
        )
        unit = self.block(reward, "ADISCORD_urban_breacher")
        for terrain in ("urban", "vorkernsberg"):
            self.assertEqual(
                self.block(unit, terrain).strip(),
                "attack = 0.06",
            )

    def test_city_terrain_counts_for_commander_experience_and_modifiers(self):
        source = self.read("common/unit_leader/00_traits.txt")
        specialist = self.block(source, "urban_assault_specialist")
        gain_xp = self.block(specialist, "gain_xp")
        alternatives = self.block(gain_xp, "OR")
        self.assertEqual(
            re.findall(r"is_fighting_in_terrain\s*=\s*(\w+)", alternatives),
            ["urban", "vorkernsberg"],
        )
        for name, expected in (
            ("urban_assault_specialist", {"movement": 0.05, "attack": 0.1, "defence": 0.1}),
            ("expert_improviser", {"movement": 0.1}),
        ):
            modifier = self.block(self.block(source, name), "modifier")
            for terrain in ("urban", "vorkernsberg"):
                values = re.findall(r"(\w+)\s*=\s*(-?[0-9.]+)", self.block(modifier, terrain))
                self.assertEqual({key: float(value) for key, value in values}, expected)

    def test_new_icon_frames_are_different_in_every_supported_size(self):
        from PIL import Image
        from tools.assets.source import build_infantry_icons as icons
        for path, expected in icons.outputs().items():
            self.assertEqual(path.read_bytes(), expected, str(path))
        source = self.read("interface/ADISCORD_subuniticons.gfx") + self.read("interface/modifiericons_texticons.gfx")
        for size in ("medium", "medium_white", "small"):
            pixels = []
            for unit in ("territorial", "assault_infantry", "marine_infantry"):
                match = re.search(r'spriteType\s*=\s*\{[^{}]*name = "GFX_unit_ADISCORD_' + unit + '_icon_' + size + r'"[^{}]*\}', source)
                self.assertIsNotNone(match)
                self.assertIn("noOfFrames = 2", match[0])
                texture = re.search(r'texturefile = "([^"]+)"', match[0])[1]
                self.assertIn(f"/ADISCORD_{unit}_icon", texture)
                path = ROOT / texture
                if not path.exists():
                    path = generator.BASE_GAME / texture
                with Image.open(path) as image:
                    self.assertEqual(image.width % 2, 0)
                    self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
                    pixels.append([
                        image.crop((frame * image.width // 2, 0, (frame + 1) * image.width // 2, image.height)).tobytes()
                        for frame in range(2)
                    ])
            for frame in range(2):
                self.assertEqual(len({unit[frame] for unit in pixels}), len(pixels))

    def test_national_shield_kit_matches_actual_template_and_is_guarded_once(self):
        from tools.validators import validate_adiscord_division_templates as templates
        source = self.read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        effect = self.block(source, "STP_pw_open_shield_corps")
        self.assertIn("NOT = { has_idea = STP_pw_shield_corps }", effect)
        self.assertIn("date > 2162.12.31", effect)
        self.assertNotIn("add_manpower", effect)
        self.assertNotIn("create_unit", effect)
        self.assertNotIn("override_model", effect)
        actual, _, _ = templates.collect_templates_and_references(ROOT)
        template = next(item for item in actual if item.name == "Stelander Shield Brigade")
        units, _ = templates._collect_subunits(ROOT)
        archetypes, _ = templates._collect_equipment_archetypes(ROOT)
        computed, issues = templates._compute_template(template, units, archetypes, {})
        self.assertEqual(issues, [])
        self.assertEqual(computed.manpower, 10600)
        equipment = validator.collect_equipment_blocks()
        deliveries = {}
        for block in re.findall(r"add_equipment_to_stockpile = \{([^{}]+)\}", effect):
            model = re.search(r"type = (\w+)", block)[1]
            amount = int(re.search(r"amount = (\d+)", block)[1])
            archetype = re.search(r"archetype = (\w+)", equipment[model])[1]
            deliveries[archetype] = deliveries.get(archetype, 0) + amount
        self.assertEqual(deliveries, computed.equipment)
        idea = self.block(self.read("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "STP_pw_shield_corps")
        capacity = int(re.search(r"special_forces_min = (\d+)", idea)[1])
        shield_count = sum(slot.unit == "ADISCORD_urban_breacher" for slot in template.slots)
        self.assertEqual(capacity, shield_count)
        focus = self.read("common/national_focus/ADISCORD_STP_civil_war.txt")
        from tools.tests.test_adiscord_val_focus_layout import focus_block
        for faction, tag in (("party", "STP"), ("republic", "STS")):
            block = focus_block(focus, f"STP_pw_{faction}_shield_corps")
            self.assertIn(f"tag = {tag}", block)
            self.assertIn("date > 2162.12.31", block)
            self.assertIn("STP_pw_open_shield_corps = yes", block)

    def test_kefreyt_capacity_is_a_focus_reward_after_its_funded_spawn(self):
        source = self.read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        refresh = self.block(source, "VAL_refresh_contract_modifier")
        self.assertIn("has_country_flag = VAL_shield_special_forces_raised", refresh)
        self.assertNotIn("has_tech = ADISCORD_tech_kefreyt_shield_special_forces", refresh)
        effect = self.block(source, "VAL_raise_shield_special_forces")
        self.assertLess(effect.index("set_country_flag = VAL_shield_special_forces_raised"), effect.index("VAL_refresh_contract_modifier = yes"))
        self.assertIn("date > 2162.12.31", effect)

    def test_shield_models_preserve_native_contract_and_all_weapon_tiers(self):
        from tools.assets.source import build_shield_infantry as models
        outputs = models.outputs()
        for path, expected in outputs.items():
            self.assertEqual(path.read_bytes(), expected, str(path))
        self.assertNotEqual(outputs[models.MODEL / "STP_shield.mesh"], outputs[models.MODEL / "STS_shield.mesh"])
        entities = self.read("gfx/entities/zz_ADISCORD_shield_infantry.asset")
        for tag in ("STP", "STS"):
            for level in range(8):
                suffix = "" if level == 0 else f"_{level + 1}"
                self.assertIn(f'"{tag}_ADISCORD_urban_breacher{suffix}_entity"', entities)
        self.assertEqual(len(list(models.MODEL.glob("urban_breacher_*.anim"))), 13)

    def test_shield_localisation_has_its_own_role_and_valid_encoding(self):
        for language in ("russian", "english"):
            lines = generator.generated_localisation(language)
            shields = [line for line in lines if re.match(r" ADISCORD_power_shield_equipment(?:_[123])?(?:_short)?:", line)]
            self.assertEqual(len(shields), 8)
            for line in shields:
                self.assertNotRegex(line, r"Личн|Personal|Групп|Crew-served")
            for tech in generator.BRANCH_BY_KEY["power_shields"].techs:
                self.assertIn(tech.key, generator.TECHNICAL_TECH_DESCRIPTIONS)
        for name in ("ADISCORD_STP", "ADISCORD_VAL_decisions", "ADISCORD_technology_doctrine"):
            data = (ROOT / f"localisation/russian/{name}_l_russian.yml").read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            for line in data.decode("utf-8-sig").splitlines():
                if line.startswith(" STP_pw_") or line.startswith(" ADISCORD_power_shield"):
                    self.assertTrue(line.rstrip().endswith('"'))

    def test_shield_ai_only_prioritizes_replenishment_without_extra_factory_minima(self):
        policy = self.block(self.read("common/ai_strategy/default.txt"), "ADISCORD_power_shield_replenishment")
        self.assertIn("has_tech = ADISCORD_tech_kefreyt_shield_special_forces", policy)
        self.assertIn("stockpile_ratio", policy)
        self.assertIn("archetype = ADISCORD_power_shield_equipment", policy)
        self.assertIn("abort_when_not_enabled = yes", policy)
        self.assertNotIn("equipment_production_min_factories", policy)

class SpecialTechnologyFolderTests(unittest.TestCase):
    def test_existing_tabs_keep_their_native_positions_and_hit_areas(self):
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(encoding="utf-8")
        native = (generator.BASE_GAME / "interface/countrytechtreeview.gui").read_text(encoding="utf-8-sig")
        actual = validator.extract_named_container(gui, "folder_tabs")
        expected = validator.extract_named_container(native, "folder_tabs")
        for contract in ui_builder.FOLDER_TAB_CONTRACTS:
            actual = actual.replace(f'"{contract.target_name}"', f'"{contract.source_name}"')
        actual = actual.replace("\n\n" + generator.render_special_technology_tab(), "")
        self.assertEqual(actual, expected)

    def test_unconfigured_special_research_is_locked_by_default(self):
        branch = replace(
            generator.BRANCH_BY_KEY["field_support"],
            folders=(generator.SPECIAL_TECHNOLOGY_FOLDER,),
        )
        for index in range(len(branch.techs)):
            rendered = generator.render_technology(branch, index)
            self.assertIn("always = no", rendered)
            self.assertIn("tooltip = ADISCORD_special_technology_locked_tt", rendered)

    def test_special_research_is_absent_from_all_starting_profiles(self):
        for branch in generator.BRANCHES:
            if generator.SPECIAL_TECHNOLOGY_FOLDER not in branch.folders:
                continue
            for profile in generator.STARTING_TECH_PROFILES.values():
                self.assertTrue(set(profile).isdisjoint(tech.id for tech in branch.techs))
            for index in range(len(branch.techs)):
                self.assertTrue(generator.research_allow_for(branch, index))

    def test_visible_tab_has_registered_folder_and_both_native_item_templates(self):
        folder = generator.SPECIAL_TECHNOLOGY_FOLDER
        tags = (ROOT / "common/technology_tags/ADISCORD_technology.txt").read_text(encoding="utf-8")
        self.assertEqual(tags, generator.technology_folder_tags())
        self.assertNotIn("available", tags)
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(encoding="utf-8")
        for name in (folder, f"{folder}_tab", f"techtree_{folder}_item", f"techtree_{folder}_small_item"):
            self.assertEqual(gui.count(f'name = "{name}"'), 1, name)
        special_tab = generator.render_special_technology_tab().replace(
            '"GFX_secret_weapons_folder_tab"',
            '"GFX_ADISCORD_technology_folder_special"',
        )
        self.assertIn(special_tab, gui)
        infantry = validator.extract_named_container(gui, "infantry_folder")
        special = validator.extract_named_container(gui, folder)
        self.assertNotIn("shield", infantry)
        self.assertIn('name = "ADISCORD_tech_kefreyt_shield_special_forces_tree"', special)
        for language in ("russian", "english"):
            source = (ROOT / f"localisation/{language}/ADISCORD_technology_doctrine_l_{language}.yml").read_bytes()
            self.assertTrue(source.startswith(b"\xef\xbb\xbf"))
            self.assertIn(f" {folder}:0", source.decode("utf-8-sig"))


class HazardInfantryTests(unittest.TestCase):
    TAGS = ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA")
    UNIT = "ADISCORD_hazard_infantry"
    read = staticmethod(InfantryRoleAndShieldTests.read)
    block = staticmethod(InfantryRoleAndShieldTests.block)

    def test_research_unlock_and_profile_include_real_prerequisites(self):
        tech = "ADISCORD_tech_radiation_patrols"
        self.assertIn(self.UNIT, generator.ENABLE_SUBUNITS[tech])
        profile = set(generator.STARTING_TECH_PROFILES["hazard_infantry"])
        self.assertIn(tech, profile)
        self.assertIn("ADISCORD_tech_sealed_combat_suits", profile)
        self.assertEqual(profile, set(generator.technology_prerequisite_closure(profile)))
        self.assertNotIn(tech, generator.STARTING_TECH_PROFILES["common"])
        source = self.read("common/scripted_effects/ADISCORD_technology_baseline_effects.txt")
        effect = self.block(source, "ADISCORD_grant_technology_profile_hazard_infantry")
        for prerequisite in profile:
            self.assertIn(prerequisite + " = 1", effect)

    def test_specialist_is_costly_and_has_only_supported_local_terrain_bonuses(self):
        source = self.read("common/units/ADISCORD_land_units.txt")
        unit = self.block(source, self.UNIT)
        terrain = self.block(unit, "contaminated")
        self.assertIn("special_forces = yes", unit)
        self.assertIn("active = no", unit)
        self.assertIn("manpower = 1000", unit)
        self.assertIn("training_time = 150", unit)
        self.assertIn("support_equipment", self.block(unit, "essential"))
        self.assertEqual(set(re.findall(r"\b(\w+)\s*=", terrain)), {"attack", "defence", "movement"})
        for stat, minimum in (("attack", 0.5), ("defence", 0.4), ("movement", 0.6)):
            self.assertGreaterEqual(float(re.search(rf"\b{stat} = ([0-9.]+)", terrain)[1]), minimum)
        self.assertNotIn("reliability_factor", unit)
        self.assertNotIn("attrition =", unit)
        self.assertNotIn("armor_value", unit)

    def test_each_zone_country_gets_technology_before_its_only_starting_division(self):
        from tools.validators import validate_adiscord_division_templates as templates
        units, issues = templates._collect_subunits(ROOT)
        self.assertEqual(issues, [])
        definitions, references, _ = templates.collect_templates_and_references(ROOT)
        source = self.read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        for tag in self.TAGS:
            with self.subTest(tag=tag):
                effect = self.block(source, f"ADISCORD_vorkerland_setup_{tag.lower()}")
                profile = "ADISCORD_grant_technology_profile_hazard_infantry = yes"
                oob = f'load_oob = "{tag}_vorkerland_collapse"'
                self.assertLess(effect.index("ADISCORD_grant_2150_technology_baseline"), effect.index(profile))
                self.assertLess(effect.index(profile), effect.index(oob))
                filename = f"history/units/{tag}_vorkerland_collapse.txt"
                deployed = [r for r in references if r.path == filename and r.kind == "oob"]
                self.assertEqual(len(deployed), 1)
                mixed = next(t for t in definitions if t.path == filename and t.name == deployed[0].name)
                battalions = [slot.unit for slot in mixed.slots]
                self.assertEqual(battalions.count(self.UNIT), 2)
                self.assertEqual(battalions.count("ADISCORD_militia"), 1)
                self.assertEqual(sum(units[u].manpower for u in battalions), 3000)
                available = [t for t in definitions if t.path == filename and t.name == "CBRN Protection Detachment"]
                self.assertEqual(len(available), 1)
                self.assertEqual([s.unit for s in available[0].slots], [self.UNIT] * 3)
                # Issued reserves cover the new 30% equipment shortfall and leave spares.
                self.assertRegex(effect, r"type = support_equipment_1\s+amount = 40")
                self.assertRegex(effect, r"type = ADISCORD_squad_weapons_equipment_0\s+amount = 24")
        placeholder = self.read("history/countries/EXZ - Exclusion Zone.txt")
        self.assertNotIn("hazard_infantry", placeholder)
        self.assertNotIn("load_oob", placeholder)

    def test_new_and_replaced_oob_templates_have_consistent_audits(self):
        from tools.validators import validate_adiscord_division_templates as templates
        issues = templates.validate(ROOT)
        relevant = [issue for issue in issues if any(
            f"{tag}_vorkerland_collapse" in issue or f"oob_{tag.lower()}_" in issue
            for tag in self.TAGS
        )]
        self.assertEqual(relevant, [])

    def test_model_has_native_bindings_at_every_weapon_level(self):
        from tools.assets.source import build_northern_infantry as models
        asset = self.read("gfx/entities/zz_ADISCORD_country_infantry.asset")
        gfx = self.read("gfx/entities/ADISCORD_country_infantry.gfx")
        entities = {
            re.search(r'name\s*=\s*"([^"]+)"', block)[1]: block
            for block in models.blocks(asset, "entity")
        }
        for level in range(8):
            suffix = "" if level == 0 else f"_{level + 1}"
            key = self.UNIT + suffix + "_entity"
            self.assertEqual(asset.count(f'name = "{key}"'), 1)
            body = entities[key]
            self.assertIn(f'ADISCORD_infantry_weapon_{level}_right_entity', body)
            self.assertEqual(len(list(models.blocks(body, "attach"))), 4)
            if level > 1:
                self.assertIn('clone = "ADISCORD_hazard_infantry_2_entity"', body)
                body += entities[self.UNIT + "_2_entity"]
            else:
                self.assertNotIn("clone =", body)
            for token in ("cigarette", "lighter", 'animation = "long_idle'):
                self.assertNotIn(token, body)
            for state in ("attack", "defend", "support_attack", "move", "retreat", "death", "idle", "training"):
                self.assertIn(f'name = "{state}"', body)
        for pose in ("rifle", "mg"):
            key = f"ADISCORD_HAZ_field_{pose}_mesh"
            self.assertEqual(gfx.count(f'name = "{key}"'), 1)
        self.assertNotIn('name = "HAZ_infantry_entity"', asset)
        for path, content in models.bindings().items():
            self.assertEqual(path.read_bytes(), content)
        self.assertTrue((ROOT / "tools/assets/source/ADISCORD_hazard_infantry.blend").is_file())

    def test_badges_and_localisation_load_in_every_size(self):
        from PIL import Image
        sprites = validator.collect_sprite_names()
        for size, dimensions in (("medium", (152, 42)), ("medium_white", (60, 12)), ("small", (60, 12))):
            path = ROOT / sprites[f"GFX_unit_{self.UNIT}_icon_{size}"]
            with Image.open(path) as icon:
                self.assertEqual(icon.size, dimensions)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_technology_doctrine_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for suffix in ("", "_desc"):
                self.assertEqual(len(re.findall(rf'^ {self.UNIT}{suffix}:0 "[^"\r\n]+"$', text, re.M)), 1)


if __name__ == "__main__":
    unittest.main()
