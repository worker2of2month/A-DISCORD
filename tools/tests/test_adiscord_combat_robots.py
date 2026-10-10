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
SOUND = "ADISCORD_robot_"


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
    def test_debug_trial_unlocks_robot_production_before_equipped_spawn(self):
        effect = value(read_script("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_spawn_crimson_trial")
        guarded = value(effect, "if")
        guard = value(guarded, "limit")
        self.assertEqual(value(guard, "is_debug"), "yes")
        self.assertEqual(value(guard, "is_ai"), "no")
        unlocks = [entry.value for entry in guarded if entry.key == "if"
                   and any(child.key == "complete_special_project" for child in entry.value)]
        self.assertEqual(len(unlocks), 1)
        unlock = unlocks[0]
        self.assertEqual(value(unlock, "complete_special_project"), "sp:" + PROJECT)
        self.assertEqual(value(value(value(unlock, "limit"), "NOT"), "is_special_project_completed"),
                         "sp:" + PROJECT)
        unlock_index = next(i for i, entry in enumerate(guarded) if entry.value == unlock)
        spawn_index = next(i for i, entry in enumerate(guarded) if entry.key == "capital_scope")
        self.assertLess(unlock_index, spawn_index)
        spawn = value(value(guarded, "capital_scope"), "create_unit")
        payload = parse_clausewitz(value(spawn, "division"))
        self.assertEqual(float(value(payload, "start_equipment_factor")), 1)
        self.assertEqual(float(value(payload, "start_manpower_factor")), 1)

    def test_project_is_universal_and_its_research_path_is_reachable(self):
        project = value(read_script("common/special_projects/projects/land_projects.txt"), PROJECT)
        self.assertFalse({entry.key for entry in project} & {"allowed", "visible", "special_project_parent"})
        prerequisites = value(value(project, "available"), "FROM")
        self.assertEqual({entry.key for entry in prerequisites}, {"custom_trigger_tooltip"})
        required = [value(entry.value, "has_tech") for entry in prerequisites]
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
        for state in (entry.value for entry in model if entry.key == "state"):
            name = value(state, "name")
            events = [entry.value for entry in state if entry.key == "event"]
            used = [value(value(event, "sound"), "soundeffect") for event in events]
            expected = set() if name == "death" else {SOUND + "idle"}
            if name in {"move", "retreat"}:
                expected |= {SOUND + "start", SOUND + "step"}
                steps = [e for e in events if value(value(e, "sound"), "soundeffect") == SOUND + "step"]
                self.assertEqual(len(steps), 2)
                self.assertEqual({value(e, "node") for e in steps}, {"left_foot", "right_foot"})
                for step in steps:
                    self.assertFalse(any(e.key == "trigger_once" for e in step))
                    self.assertLess(float(value(step, "time")), 40 / 24)
            if name in {"attack", "defend", "support_attack"}:
                expected.add(SOUND + "burst")
            self.assertEqual(set(used), expected, name)
            for event in (entry.value for entry in state if entry.key == "event"):
                sound = value(value(event, "sound"), "soundeffect")
                if sound in {SOUND + "idle", SOUND + "start"}:
                    self.assertEqual(value(event, "trigger_once"), "yes")
                    self.assertEqual(float(value(event, "time")), 0)
        for name, entity in entities.items():
            if name != UNIT + "_entity":
                self.assertNotIn(SOUND, repr(entity), name)
        weapon = entities["ADISCORD_combat_robot_weapon_entity"]
        self.assertIn(value(weapon, "pdxmesh"), meshes)
        self.assertNotIn("infantry_mg_attack", repr(weapon))
        self.assertFalse(any(entry.key == "clone" for entry in weapon))
        self.assertIn("ADISCORD_combat_robot_weapon_entity", repr(model))
        for state in (entry.value for entry in weapon if entry.key == "state"):
            if value(state, "name") in {"attack", "defend", "support_attack"}:
                self.assertEqual(float(value(state, "state_time")), 96 / 30)
                self.assertEqual(value(state, "looping"), "yes")
                self.assertFalse(any(entry.key == "animation" for entry in state))

    def test_robot_audio_is_spatial_and_replaces_the_old_scrapes(self):
        import numpy as np

        definitions = read_script("sound/assets_adiscord_soundeffects.asset")
        effects = {name: effect for name, effect in named_blocks(definitions, "soundeffect").items()
                   if name.startswith(SOUND)}
        self.assertEqual(set(effects), {SOUND + name for name in ("idle", "start", "step", "burst")})
        self.assertNotIn("ADISCORD_crimson_metal_scrape", repr(definitions))
        categories = [entry.value for entry in definitions if entry.key == "category"]
        self.assertTrue(any(
            value(category, "name") == "Battle"
            and set(effects) <= {entry.value for entry in value(category, "soundeffects")}
            for category in categories
        ))
        sounds = named_blocks(read_script("sound/assets_adiscord_sounds.asset"), "sound")
        self.assertNotIn("ADISCORD_crimson_metal_scrape", repr(sounds))
        samples = set()
        for name, effect in effects.items():
            self.assertEqual(value(effect, "is3d"), "yes")
            self.assertEqual(value(effect, "loop"), "yes" if name.endswith("idle") else "no")
            self.assertLessEqual(int(value(effect, "max_audible")), 4)
            samples.update(entry.value for entry in value(effect, "sounds"))
        self.assertEqual(len(samples), 5)
        for sample in samples:
            path = ROOT / "sound" / value(sounds[sample], "file")
            with wave.open(str(path), "rb") as audio:
                self.assertEqual(audio.getcomptype(), "NONE")
                self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 2, 44100))
                pcm = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(float) / 32768
                self.assertGreater(np.sqrt(np.mean(pcm ** 2)), .015)
                self.assertLess(np.max(np.abs(pcm)), .9)
                if "idle" in sample:
                    self.assertLess(abs(pcm[0] - pcm[-1]), .01)
                    frequencies = np.fft.rfftfreq(len(pcm), 1 / 44100)
                    power = np.abs(np.fft.rfft(pcm)) ** 2
                    self.assertLess(power[frequencies > 350].sum() / power.sum(), .01)
                else:
                    self.assertEqual((pcm[0], pcm[-1]), (0, 0))
        for filename in ("special_1.wav", "special_2.wav"):
            self.assertFalse((ROOT / "sound/special units" / filename).exists())

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
            self.assertLessEqual(expected, keys)

    def test_leftover_check_allows_native_land_research_but_rejects_stale_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            technology = root / "common/technologies/test.txt"
            technology.parent.mkdir(parents=True)
            projects = root / "common/special_projects/projects/land_projects.txt"
            projects.parent.mkdir(parents=True)
            projects.write_text(PROJECT + " = { specialization = specialization_land }\n", encoding="utf-8")
            with patch.object(validate_tc, "ROOT", root):
                technology.write_text("special_project_specialization = { specialization_land }\n", encoding="utf-8")
                self.assertEqual(validate_tc.check_special_project_leftovers(20), ([], 0))
                for valid in (
                    "complete_special_project = sp:" + PROJECT,
                    "limit = { NOT = { is_special_project_completed = sp:" + PROJECT + " } }",
                ):
                    technology.write_text(valid + "\n", encoding="utf-8")
                    self.assertEqual(validate_tc.check_special_project_leftovers(20), ([], 0))
                for invalid in (
                    "special_project_specialization = { specialization_air }",
                    "PROJECT = sp_land_cruiser",
                    "is_special_project_completed = sp_land_cruiser",
                    "sp:sp_land_cruiser = { }",
                    "complete_special_project = sp:ADISCORD_missing_project",
                    "complete_special_project = sp:" + PROJECT + " is_special_project_completed = sp:missing",
                ):
                    with self.subTest(invalid=invalid):
                        technology.write_text(invalid + "\n", encoding="utf-8")
                        self.assertEqual(validate_tc.check_special_project_leftovers(20)[1], 1)


if __name__ == "__main__":
    unittest.main()
