"""Static contracts for the debug-only airborne battleship trial."""

import hashlib
import json
from pathlib import Path
import re
import unittest
import wave

from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return parse_clausewitz((ROOT / path).read_text(encoding="utf-8-sig"))


def value(entries, key):
    matches = [entry.value for entry in entries if entry.key == key]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {key}, found {len(matches)}")
    return matches[0]


def children(entries, key):
    return [entry.value for entry in entries if entry.key == key]


class ZeppelinIntegrationTests(unittest.TestCase):
    def test_trial_is_debug_only_human_val_and_repeatable(self):
        categories = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        category = value(categories, "VAL_rework_debug")
        self.assertEqual(value(value(category, "visible"), "is_debug"), "yes")
        decisions = value(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_rework_debug")
        decision = value(decisions, "VAL_debug_spawn_zeppelin_trial")
        self.assertEqual(value(value(decision, "allowed"), "tag"), "VAL")
        visible = value(decision, "visible")
        self.assertEqual(value(visible, "is_debug"), "yes")
        self.assertEqual(value(visible, "is_ai"), "no")
        self.assertEqual(value(decision, "cost"), "0")
        self.assertEqual(value(decision, "fire_only_once"), "no")
        self.assertGreaterEqual(int(value(decision, "days_re_enable")), 1)
        self.assertEqual(value(value(decision, "ai_will_do"), "factor"), "0")
        availability = value(decision, "available")
        self.assertEqual(value(availability, "has_capitulated"), "no")
        capital = value(availability, "capital_scope")
        self.assertEqual(value(capital, "is_owned_by"), "VAL")
        self.assertEqual(value(capital, "is_controlled_by"), "VAL")

    def test_spawn_reuses_locked_template_and_fills_one_ship(self):
        effect = value(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_spawn_zeppelin_trial")
        guarded = value(effect, "if")
        guard = value(guarded, "limit")
        self.assertEqual(value(guard, "tag"), "VAL")
        self.assertEqual(value(guard, "is_debug"), "yes")
        self.assertEqual(value(guard, "is_ai"), "no")
        capital_guard = value(guard, "capital_scope")
        self.assertEqual(value(capital_guard, "is_owned_by"), "VAL")
        self.assertEqual(value(capital_guard, "is_controlled_by"), "VAL")
        template_guard = value(guarded, "if")
        template = value(template_guard, "division_template")
        name = value(template, "name")
        self.assertEqual(value(value(value(template_guard, "limit"), "NOT"), "has_template"), name)
        self.assertEqual(value(template, "is_locked"), "yes")
        self.assertEqual(value(template, "override_model"), "ADISCORD_zeppelin_entity")
        self.assertEqual(len(value(template, "regiments")), 1)
        self.assertEqual(value(template, "regiments")[0].key, "ADISCORD_zeppelin")
        spawn = value(value(guarded, "capital_scope"), "create_unit")
        self.assertEqual(value(spawn, "owner"), "VAL")
        self.assertEqual(value(spawn, "allow_spawning_on_enemy_provs"), "no")
        payload = parse_clausewitz(value(spawn, "division"))
        self.assertEqual(value(payload, "division_template"), name)
        self.assertEqual(float(value(payload, "start_equipment_factor")), 1)
        self.assertEqual(float(value(payload, "start_manpower_factor")), 1)
        unit = value(value(read("common/units/ADISCORD_land_units.txt"), "sub_units"), "ADISCORD_zeppelin")
        self.assertEqual(value(value(unit, "need"), "ADISCORD_zeppelin_equipment"), "1")
        self.assertEqual(value(unit, "active"), "no")
        equipment = value(read("common/units/equipment/ADISCORD_air_equipment.txt"), "equipments")
        variant = value(equipment, "ADISCORD_zeppelin_equipment_1")
        self.assertEqual(value(variant, "archetype"), "ADISCORD_zeppelin_equipment")
        self.assertEqual(value(variant, "active"), "yes")
        production = value(variant, "can_be_produced")
        self.assertEqual(value(production, "is_debug"), "yes")
        self.assertEqual(value(production, "tag"), "VAL")

    def test_all_land_states_resolve_to_verified_native_assets(self):
        entities = read("gfx/entities/ADISCORD_zeppelin.asset")
        entity = next(e for e in children(entities, "entity") if value(e, "name") == "ADISCORD_zeppelin_entity")
        self.assertEqual(value(entity, "pdxmesh"), "ADISCORD_zeppelin_mesh")
        self.assertGreater(float(value(entity, "scale")), .1)
        self.assertLess(float(value(entity, "scale")), .5)
        states = {value(s, "name"): value(s, "animation") for s in children(entity, "state")}
        self.assertTrue({"idle", "move", "retreat", "training", "attack", "support_attack", "defend", "death"} <= states.keys())
        mesh = value(value(read("gfx/entities/ADISCORD_zeppelin.gfx"), "objectTypes"), "pdxmesh")
        animations = {value(a, "id"): value(a, "type") for a in children(mesh, "animation")}
        self.assertTrue(set(states.values()) <= animations.keys())
        folder = ROOT / Path(value(mesh, "file")).parent
        registered = {value(a.value, "name"): value(a.value, "file")
                      for a in read(str(folder.relative_to(ROOT) / "animation.asset")) if a.key == "animation"}
        self.assertTrue(set(animations.values()) <= registered.keys())
        report = json.loads((ROOT / "tools/assets/source/zeppelin/verification.json").read_text())
        for name, expected in report["files"].items():
            if name.endswith(".blend"):
                continue
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), expected, name)
        for filename in registered.values():
            self.assertTrue((folder / filename).is_file(), filename)

    def test_localisation_is_loadable_in_both_languages(self):
        keys = {"VAL_debug_spawn_zeppelin_trial", "VAL_debug_spawn_zeppelin_trial_desc",
                "VAL_spawn_zeppelin_trial_tt", "ADISCORD_zeppelin", "ADISCORD_zeppelin_desc",
                "ADISCORD_zeppelin_equipment", "ADISCORD_zeppelin_equipment_1"}
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            entries = dict(re.findall(r'^\s*([\w.]+):(?:\d+)?\s*"([^"\n]*)"\s*$',
                                      path.read_text(encoding="utf-8-sig"), re.MULTILINE))
            self.assertTrue(keys <= entries.keys(), keys - entries.keys())
            self.assertTrue(entries["VAL_debug_spawn_zeppelin_trial"].startswith("§RDEBUG:§! "))

    def test_equipment_types_are_registered_in_native_enum(self):
        enumeration = value(read("common/script_enums.txt"), "script_enum_equipment_bonus_type")
        names = {entry.value for entry in enumeration}
        self.assertTrue({"ADISCORD_zeppelin_equipment", "ADISCORD_zeppelin_equipment_1"} <= names)

    def test_engine_starts_once_per_state_and_salvo_matches_recoil(self):
        entities = children(read("gfx/entities/ADISCORD_zeppelin.asset"), "entity")
        entity = next(e for e in entities if value(e, "name") == "ADISCORD_zeppelin_entity")
        for state in children(entity, "state"):
            name = value(state, "name")
            events = [event for event in children(state, "event") if children(event, "sound")]
            if name == "death":
                self.assertFalse(events, "A removed ship must not start another engine loop")
                continue
            engine = "ADISCORD_zeppelin_engine_move" if name in ("move", "retreat") else "ADISCORD_zeppelin_engine_hover"
            engine_events = [event for event in events if value(value(event, "sound"), "soundeffect") == engine]
            self.assertEqual(len(engine_events), 1, name)
            self.assertEqual(value(engine_events[0], "trigger_once"), "yes")
            starts = [event for event in events if value(value(event, "sound"), "soundeffect") == "ADISCORD_zeppelin_engine_start"]
            if name in ("move", "retreat"):
                self.assertEqual(len(starts), 1)
                self.assertEqual(value(starts[0], "trigger_once"), "yes")
                self.assertEqual(float(value(starts[0], "time")), 0)
                self.assertEqual(float(value(engine_events[0], "time")), 0,
                                 "The propeller loop must cover the movement transition immediately")
            else:
                self.assertFalse(starts)
            shots = [event for event in events if value(value(event, "sound"), "soundeffect") == "ADISCORD_zeppelin_salvo"]
            if name in ("attack", "support_attack", "defend"):
                self.assertEqual(len(shots), 1)
                self.assertEqual(float(value(shots[0], "time")), .5)
                self.assertFalse(children(shots[0], "trigger_once"), "A salvo must repeat each firing cycle")
            else:
                self.assertFalse(shots, name)
        for alias in entities:
            if value(alias, "name") != "ADISCORD_zeppelin_entity":
                self.assertFalse(children(alias, "state"), "Clones must inherit, not double the sound events")

    def test_spatial_audio_is_capped_and_only_engines_loop(self):
        definitions = read("sound/adiscord_zeppelin.asset")
        category = value(definitions, "category")
        self.assertEqual(value(category, "name"), "Battle")
        effects = {value(e, "name"): e for e in children(definitions, "soundeffect")}
        self.assertEqual(set(effects), {e.value for e in value(category, "soundeffects")})
        self.assertEqual(len(effects), 4)
        for name, effect in effects.items():
            engine = name.endswith(("_hover", "_move"))
            self.assertEqual(value(effect, "loop"), "yes" if engine else "no")
            self.assertEqual(value(effect, "is3d"), "yes")
            self.assertEqual(value(effect, "falloff"), "falloff_100")
            self.assertLessEqual(int(value(effect, "max_audible")), 4)
            self.assertEqual(value(effect, "max_audible_behaviour"), "fail")
            if engine:
                self.assertEqual(value(effect, "random_sound_when_looping"), "no")
                self.assertGreater(float(value(effect, "fade_out")), 0)
        self.assertLess(float(value(effects["ADISCORD_zeppelin_engine_hover"], "volume")),
                        float(value(effects["ADISCORD_zeppelin_engine_move"], "volume")))

    def test_particles_follow_muzzles_and_exhausts_without_loop_accumulation(self):
        report = json.loads((ROOT / "tools/assets/source/zeppelin/verification.json").read_text())
        locators = report["locators"]
        self.assertEqual(len([name for name in locators if "_muzzle_" in name]), 18)
        self.assertEqual(len([name for name in locators if name.startswith("exhaust_")]), 6)
        entity = children(read("gfx/entities/ADISCORD_zeppelin.asset"), "entity")[0]
        registry = value(read("gfx/entities/ADISCORD_zeppelin.gfx"), "objectTypes")
        registered = {value(p, "name"): value(p, "type") for p in children(registry, "pdxparticle")}
        particles = {value(p, "name"): p for p in children(read("gfx/particles/ADISCORD_zeppelin.asset"), "particle")}
        self.assertEqual(set(registered.values()), set(particles))
        for state in children(entity, "state"):
            name = value(state, "name")
            events = [e for e in children(state, "event") if children(e, "particle")]
            exhaust = [e for e in events if value(e, "particle").endswith("_exhaust_particle")]
            flashes = [e for e in events if value(e, "particle").endswith("_flash_particle")]
            smoke = [e for e in events if value(e, "particle").endswith("_smoke_particle")]
            self.assertEqual(len(exhaust), 0 if name == "death" else 6)
            self.assertEqual(len(flashes), 18 if name in ("attack", "support_attack", "defend") else 0)
            self.assertEqual(len(smoke), len(flashes) // 3)
            for event in events:
                self.assertIn(value(event, "particle"), registered)
                self.assertIn(value(event, "node"), locators)
            for event in exhaust:
                self.assertEqual(value(event, "trigger_once"), "yes")
                self.assertEqual(value(event, "keep_particle"), "no")
                self.assertEqual(float(value(event, "time")), 0)
            for event in flashes + smoke:
                self.assertFalse(children(event, "trigger_once"))
                self.assertEqual(float(value(event, "time")), .5)
                self.assertEqual(value(event, "keep_particle"), "yes")
        for particle in particles.values():
            for emitter in children(particle, "subsystem"):
                self.assertLessEqual(int(value(emitter, "max_amount")), 12)
                self.assertNotIn("ground", value(emitter, "name"))
                self.assertFalse(children(emitter, "sound"))

    def test_sound_samples_resolve_decode_and_have_clean_boundaries(self):
        import numpy as np

        definitions = read("sound/adiscord_zeppelin.asset")
        samples = {value(e, "name"): value(e, "file") for e in children(definitions, "sound")}
        used = {e.value for effect in children(definitions, "soundeffect") for e in value(effect, "sounds")}
        self.assertEqual(len(used), 4)
        self.assertEqual(used, samples.keys())
        for name in used:
            with wave.open(str(ROOT / "sound" / samples[name]), "rb") as sample:
                self.assertEqual(sample.getframerate(), 44100)
                self.assertEqual(sample.getsampwidth(), 2)
                self.assertEqual(sample.getnchannels(), 1)
                pcm = np.frombuffer(sample.readframes(sample.getnframes()), dtype="<i2").astype(float) / 32768
                self.assertGreater(np.sqrt(np.mean(pcm ** 2)), .025)
                self.assertLess(np.max(np.abs(pcm)), .9)
                if name.endswith(("_hover_sample", "_move_sample")):
                    self.assertLess(abs(pcm[0] - pcm[-1]), .01)
                else:
                    self.assertLess(abs(pcm[0]), .001)
                    self.assertLess(abs(pcm[-1]), .001)


if __name__ == "__main__":
    unittest.main()
