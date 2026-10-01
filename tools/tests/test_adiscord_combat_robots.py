from __future__ import annotations

import re
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from tools.builders import build_adiscord_technology_system as technologies
from tools.validators import validate_tc
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
PROJECT = "ADISCORD_sp_combat_robots"
UNIT = "ADISCORD_combat_robots"
EQUIPMENT = "ADISCORD_combat_robot_equipment"
SOUND = "ADISCORD_crimson_metal_scrape"


def read_script(path: str):
    return parse_clausewitz((ROOT / path).read_text(encoding="utf-8-sig"))


def value(entries, key):
    matches = [entry.value for entry in entries if entry.key == key]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {key}, found {len(matches)}")
    return matches[0]


def named_blocks(entries, kind):
    return {
        value(entry.value, "name"): entry.value
        for entry in entries
        if entry.key == kind
    }


class CombatRobotTests(unittest.TestCase):
    def test_project_is_universal_and_its_research_path_is_reachable(self):
        project = value(read_script("common/special_projects/projects/land_projects.txt"), PROJECT)
        self.assertFalse({entry.key for entry in project} & {"allowed", "visible", "special_project_parent"})
        prerequisites = value(value(project, "available"), "FROM")
        self.assertEqual({entry.key for entry in prerequisites}, {"has_tech"})
        required = [entry.value for entry in prerequisites]
        self.assertEqual(len(required), 2)
        for tech in technologies.technology_prerequisite_closure(required):
            self.assertIn(tech, technologies.TECH_POSITION_BY_ID)
        self.assertEqual(value(project, "specialization"), "specialization_land")
        self.assertEqual(value(project, "prototype_time"), "sp_time.prototype.long")
        self.assertEqual(value(project, "complexity"), "sp_complexity.large")
        output = value(project, "project_output")
        self.assertEqual([entry.value for entry in value(output, "enable_subunits")], [UNIT])
        self.assertEqual([entry.value for entry in value(output, "enable_equipments")], [EQUIPMENT + "_1"])
        for unlocks in technologies.ENABLE_SUBUNITS.values():
            self.assertNotIn(UNIT, unlocks)

    def test_research_generates_land_breakthroughs_before_the_project(self):
        for branch in technologies.BRANCHES:
            for index in range(len(branch.techs)):
                rendered = technologies.render_technology(branch, index)
                marker = "special_project_specialization = { specialization_land }"
                self.assertEqual(marker in rendered, branch.key in {"computing", "production"})
        for tech in ("ADISCORD_tech_hardened_computers", "ADISCORD_tech_automated_assembly"):
            branch, index = technologies.TECH_POSITION_BY_ID[tech]
            self.assertIn("special_project_specialization", technologies.render_technology(branch, index))

    def test_robot_supply_requires_its_own_locked_equipment(self):
        units = value(read_script("common/units/ADISCORD_land_units.txt"), "sub_units")
        robots = value(units, UNIT)
        self.assertEqual(value(robots, "active"), "no")
        self.assertNotIn("category_all_infantry", [entry.value for entry in value(robots, "categories")])
        requirements = {entry.key: int(entry.value) for entry in value(robots, "need")}
        self.assertEqual(requirements, {EQUIPMENT: 100, "support_equipment": 20})
        equipment = value(read_script("common/units/equipment/ADISCORD_infantry_equipment.txt"), "equipments")
        archetype = value(equipment, EQUIPMENT)
        variant = value(equipment, EQUIPMENT + "_1")
        self.assertEqual(value(archetype, "is_archetype"), "yes")
        self.assertEqual(value(archetype, "is_buildable"), "no")
        self.assertEqual(value(variant, "active"), "no")
        self.assertEqual(value(variant, "archetype"), EQUIPMENT)
        equipment_enum = value(read_script("common/script_enums.txt"), "script_enum_equipment_bonus_type")
        self.assertTrue({EQUIPMENT, EQUIPMENT + "_1"} <= {entry.value for entry in equipment_enum})
        self.assertGreater(float(value(archetype, "build_cost_ic")), 0)
        assault = value(units, "ADISCORD_assault_infantry")
        self.assertEqual(value(assault, "sprite"), "infantry")
        self.assertIn("infantry_equipment", {entry.key for entry in value(assault, "need")})
        self.assertNotIn(EQUIPMENT, {entry.key for entry in value(assault, "need")})

    def test_robot_model_owns_the_state_sounds_and_country_alias(self):
        entities = named_blocks(read_script("gfx/entities/zz_ADISCORD_country_infantry.asset"), "entity")
        model = entities[UNIT + "_entity"]
        self.assertEqual(value(entities["VAL_" + UNIT + "_entity"], "clone"), UNIT + "_entity")
        mesh_definitions = [
            child
            for entry in read_script("gfx/entities/ADISCORD_country_infantry.gfx")
            if entry.key == "objectTypes"
            for child in entry.value
        ]
        meshes = named_blocks(mesh_definitions, "pdxmesh")
        self.assertTrue((ROOT / value(meshes[value(model, "pdxmesh")], "file")).is_file())
        triggered = set()
        for state in (entry.value for entry in model if entry.key == "state"):
            for event in (entry.value for entry in state if entry.key == "event"):
                sound = value(value(event, "sound"), "soundeffect")
                if sound == SOUND:
                    self.assertEqual(value(event, "trigger_once"), "yes")
                    triggered.add(value(state, "name"))
        self.assertEqual(triggered, {"idle", "move", "attack", "defend", "support_attack", "retreat"})
        for name, entity in entities.items():
            if name != UNIT + "_entity":
                self.assertNotIn(SOUND, repr(entity), name)

    def test_scrape_routes_to_voice_volume_without_distance_attenuation(self):
        definitions = read_script("sound/assets_adiscord_soundeffects.asset")
        effect = named_blocks(definitions, "soundeffect")[SOUND]
        self.assertEqual(value(effect, "is3d"), "no")
        self.assertEqual(value(effect, "loop"), "no")
        categories = [entry.value for entry in definitions if entry.key == "category"]
        self.assertTrue(any(
            value(category, "name") == "Voices"
            and SOUND in [entry.value for entry in value(category, "soundeffects")]
            for category in categories
        ))
        sounds = named_blocks(read_script("sound/assets_adiscord_sounds.asset"), "sound")
        samples = [entry.value for entry in value(effect, "sounds")]
        self.assertEqual(len(samples), 2)
        for sample in samples:
            path = ROOT / "sound" / value(sounds[sample], "file")
            with wave.open(str(path), "rb") as audio:
                self.assertEqual(audio.getcomptype(), "NONE")
                self.assertGreater(audio.getnframes(), 0)
                self.assertTrue(any(audio.readframes(audio.getnframes())))

    def test_localisation_loads_complete_values_for_project_unit_and_equipment(self):
        expected = {PROJECT, PROJECT + "_desc", UNIT, UNIT + "_desc"}
        for equipment in (EQUIPMENT, EQUIPMENT + "_1"):
            expected.update({equipment, equipment + "_desc", equipment + "_short"})
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_special_projects_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(lines[0], f"l_{language}:")
            keys = set()
            for line in lines[1:]:
                match = re.fullmatch(r' ([A-Za-z0-9_]+):0 "(?:[^"\\]|\\.)+"', line)
                self.assertIsNotNone(match, line)
                self.assertNotIn(match[1], keys)
                keys.add(match[1])
            self.assertEqual(keys, expected)

    def test_leftover_check_allows_native_land_research_but_rejects_stale_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            technology = root / "common/technologies/test.txt"
            technology.parent.mkdir(parents=True)
            with patch.object(validate_tc, "ROOT", root):
                technology.write_text("special_project_specialization = { specialization_land }\n", encoding="utf-8")
                self.assertEqual(validate_tc.check_special_project_leftovers(20), ([], 0))
                for invalid in (
                    "special_project_specialization = { specialization_air }",
                    "PROJECT = sp_land_cruiser",
                    "is_special_project_completed = sp_land_cruiser",
                    "sp:sp_land_cruiser = { }",
                ):
                    with self.subTest(invalid=invalid):
                        technology.write_text(invalid + "\n", encoding="utf-8")
                        self.assertEqual(validate_tc.check_special_project_leftovers(20)[1], 1)


if __name__ == "__main__":
    unittest.main()
