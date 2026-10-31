"""Static checks for the SHL character registry; the native loader and UI need a fresh game."""

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
CHARACTERS = ROOT / "common/characters/SHL.txt"
SHARED_CHARACTERS = ROOT / "common/characters/ADISCORD_southern_desert_characters.txt"
HISTORY = ROOT / "history/countries/SHL - Shahrabad League.txt"
RUSSIAN = ROOT / "localisation/russian"
STATE_NAMES = {
    "russian": RUSSIAN / "state_names_l_russian.yml",
    "english": ROOT / "localisation/replace/state_names_l_english.yml",
}
HOUSE_HEADS = {
    "SHL_Khosrow_Arbin": "287",
    "SHL_Darius_Safir": "288",
    "SHL_Golshan_Loran": "289",
    "SHL_Kamran_Nur": "290",
    "SHL_Tahmuras_Bayrat": "291",
    "SHL_Fereydun_Kerdan": "292",
    "SHL_Shirin_Sharim": "293",
    "SHL_Rauf_Darban": "294",
    "SHL_Behruz_Veyran": "295",
}
COURSE_HEADS = ("SHL_Mariam_Arbin", "SHL_Rauf_Darban", "SHL_Salima_Darzi", "SHL_Amin_Rashad")
DEFINITION = re.compile(r"^\t(\w+) = \{", re.M)
LOCALISATION_KEY = re.compile(r"^\s+(\S+?):\d*\s+\"", re.M)


def read(path):
    return path.read_text(encoding="utf-8-sig")


def block(items, key):
    return next((e.value for e in items if e.key == key and isinstance(e.value, list)), [])


def scalar(items, key, default=None):
    return next((e.value for e in items if e.key == key), default)


def characters():
    return {entry.key: entry.value for entry in block(parse_clausewitz(read(CHARACTERS)), "characters")}


def sprite_names():
    names = set()
    for path in (ROOT / "interface").glob("*.gfx"):
        names.update(re.findall(r"name\s*=\s*\"(GFX_\w+)\"", read(path)))
    return names


class ShlHouseCharacterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.characters = characters()
        cls.russian_keys = set()
        for path in RUSSIAN.glob("*.yml"):
            cls.russian_keys.update(LOCALISATION_KEY.findall(read(path)))

    def test_every_character_has_a_russian_name(self):
        for name, body in self.characters.items():
            with self.subTest(character=name):
                self.assertIn(scalar(body, "name", name), self.russian_keys)

    def test_shared_southern_file_keeps_no_shl_character(self):
        remaining = [
            name for name in DEFINITION.findall(read(SHARED_CHARACTERS))
            if name.startswith("SHL_") or name.startswith("ADISCORD_staff_SHL_")
        ]
        self.assertEqual(remaining, [])

    def test_every_recruited_character_is_defined_exactly_once(self):
        recruited = re.findall(r"^recruit_character = (\w+)\s*$", read(HISTORY), re.M)
        self.assertTrue(recruited)
        definitions = {}
        for path in (ROOT / "common/characters").glob("*.txt"):
            for name in DEFINITION.findall(read(path)):
                definitions.setdefault(name, []).append(path.name)
        for name in recruited:
            with self.subTest(character=name):
                self.assertEqual(definitions.get(name), ["SHL.txt"])
        self.assertEqual(len(recruited), len(set(recruited)))
        for name in (*HOUSE_HEADS, *COURSE_HEADS):
            self.assertIn(name, recruited)

    def test_house_heads_read_their_own_furnace_state(self):
        for name, state in HOUSE_HEADS.items():
            with self.subTest(character=name):
                advisor = block(self.characters[name], "advisor")
                self.assertTrue(advisor)
                furnace = block(block(advisor, "available"), state)
                self.assertTrue(furnace, state)
                self.assertEqual(scalar(furnace, "is_owned_by"), "SHL")
                checks = {
                    scalar(e.value, "var"): scalar(e.value, "value")
                    for e in furnace if e.key == "check_variable"
                }
                self.assertEqual(checks, {"SHL_furnace_owner": "0", "SHL_furnace_running": "1"})
                other_states = [
                    e.key for e in block(advisor, "available")
                    if e.key.isdigit() and e.key != state
                ]
                self.assertEqual(other_states, [])

    def test_advisor_seats_use_registered_slots_tokens_and_sprites(self):
        slots = set(re.findall(r"slot = (\w+)", read(ROOT / "common/idea_tags/00_idea.txt")))
        sprites = sprite_names()
        tokens = []
        for name, body in self.characters.items():
            portraits = block(body, "portraits")
            for group in portraits:
                for entry in group.value:
                    # Staff icons named GFX_idea_* are inherited from the base game.
                    if entry.value.startswith("GFX_idea_"):
                        continue
                    with self.subTest(character=name, sprite=entry.value):
                        self.assertIn(entry.value, sprites)
            advisor = block(body, "advisor")
            if not advisor:
                continue
            with self.subTest(character=name):
                self.assertIn(scalar(advisor, "slot"), slots)
                tokens.append(scalar(advisor, "idea_token"))
                self.assertEqual(scalar(advisor, "removal_cost"), "0")
                self.assertTrue(any(scalar(group.value, "small") for group in portraits), name)
        self.assertEqual(len(tokens), len(set(tokens)))

    def test_course_heads_keep_their_cabinet_ideas_as_the_course_seat(self):
        ministers = read(ROOT / "common/ideas/ADISCORD_ministers_all_countries.txt")
        for name in COURSE_HEADS:
            with self.subTest(character=name):
                idea = "minister_" + name
                self.assertIn(idea + " = {", ministers)
                available = block(block(self.characters[name], "advisor"), "available")
                guards = [
                    scalar(e.value, "has_idea") for e in available
                    if e.key == "NOT" and scalar(e.value, "has_idea")
                ]
                self.assertEqual(guards, [idea])
        leader = block(self.characters["SHL_Mariam_Arbin"], "country_leader")
        self.assertEqual(scalar(leader, "ideology"), "pragmatism_ideology")

    def test_state_290_is_named_nuran(self):
        for language, path in STATE_NAMES.items():
            with self.subTest(language=language):
                text = read(path)
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)
                value = re.search(r"^ STATE_290: \"([^\"]+)\"", text, re.M).group(1)
                self.assertNotEqual(value, "Хазар")
                self.assertNotEqual(value, "Khazar")
                self.assertEqual(value, "Нуран" if language == "russian" else "Nuran")


DEBUG_DECISIONS = ROOT / "common/decisions/ADISCORD_scenario_debug_decisions.txt"
DEBUG_LOCALISATION = {
    "russian": RUSSIAN / "ADISCORD_scenario_debug_l_russian.yml",
    "english": ROOT / "localisation/english/ADISCORD_scenario_debug_l_english.yml",
}
SHL_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"
SHL_EVENTS = ROOT / "events/ADISCORD_SHL_events.txt"
SHL_DECISIONS = ROOT / "common/decisions/ADISCORD_SHL_decisions.txt"
SHL_DEBUG_DECISIONS = (
    "ADISCORD_shl_debug_fund_treasury",
    "ADISCORD_shl_debug_balance_crests",
    "ADISCORD_shl_debug_balance_quarters",
    "ADISCORD_shl_debug_ratify_houses",
    "ADISCORD_shl_debug_ratify_cities",
    "ADISCORD_shl_debug_ratify_directorate",
    "ADISCORD_shl_debug_regency",
    "ADISCORD_shl_debug_commune",
    "ADISCORD_shl_debug_house_demand",
    "ADISCORD_shl_debug_life_vignette",
    "ADISCORD_shl_debug_south_hegemon",
    "ADISCORD_shl_debug_advance_cycle",
)
COURSE_COMMITS = {
    "ADISCORD_shl_debug_ratify_houses": "SHL_commit_house_course",
    "ADISCORD_shl_debug_ratify_cities": "SHL_commit_city_course",
    "ADISCORD_shl_debug_ratify_directorate": "SHL_commit_state_course",
    "ADISCORD_shl_debug_regency": "SHL_commit_regency_course",
    "ADISCORD_shl_debug_commune": "SHL_commit_commune_course",
}
# Native effects and triggers the debug block calls with a bare `= yes`.
NATIVE_BOOLEANS = {"mark_focus_tree_layout_dirty", "is_ai"}
LOCALISATION_VALUE = re.compile(r'^\s*([A-Za-z0-9_.]+):\d*\s*"((?:[^"\\]|\\.)*)"', re.M)
TOP_LEVEL_DEFINITION = re.compile(r"^(\w+) = \{", re.M)


def walk(items):
    for entry in items:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


def boolean_calls(items):
    return [e.key for e in walk(items) if e.value == "yes" and not isinstance(e.value, list)]


class ShahrabadDebugDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decisions = {}
        cls.category_of = {}
        for category in parse_clausewitz(read(DEBUG_DECISIONS)):
            if not isinstance(category.value, list):
                continue
            for decision in category.value:
                if isinstance(decision.value, list) and decision.key.startswith("ADISCORD_shl_debug_"):
                    cls.decisions[decision.key] = decision.value
                    cls.category_of[decision.key] = category.key
        cls.effects = {}
        for path in (ROOT / "common/scripted_effects").glob("*.txt"):
            for entry in parse_clausewitz(read(path)):
                if isinstance(entry.value, list):
                    cls.effects[entry.key] = entry.value
        cls.triggers = set()
        for path in (ROOT / "common/scripted_triggers").glob("*.txt"):
            cls.triggers.update(TOP_LEVEL_DEFINITION.findall(read(path)))
        cls.localised = {
            language: dict(LOCALISATION_VALUE.findall(read(path)))
            for language, path in DEBUG_LOCALISATION.items()
        }
        cls.shl_effects_text = read(SHL_EFFECTS)
        cls.shl_events_text = read(SHL_EVENTS)

    def test_every_shortcut_exists_once_inside_a_debug_category(self):
        self.assertEqual(sorted(self.decisions), sorted(SHL_DEBUG_DECISIONS))
        for name, category in self.category_of.items():
            with self.subTest(decision=name):
                self.assertIn("debug", category.lower())
        self.assertEqual(read(DEBUG_DECISIONS).count("ADISCORD_shl_debug_fund_treasury = {"), 1)
        self.assertFalse(DEBUG_DECISIONS.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_shortcuts_are_free_repeatable_shl_only_and_ignored_by_ai(self):
        for name, body in self.decisions.items():
            with self.subTest(decision=name):
                self.assertEqual(scalar(body, "cost"), "0")
                self.assertEqual(scalar(body, "fire_only_once"), "no")
                self.assertEqual([e.key for e in block(body, "allowed")], ["tag"])
                self.assertEqual(scalar(block(body, "allowed"), "tag"), "SHL")
                self.assertEqual(scalar(block(body, "ai_will_do"), "factor"), "0")
                self.assertTrue(block(body, "complete_effect"))

    def test_names_and_descriptions_carry_the_red_prefix_in_both_languages(self):
        for language, path in DEBUG_LOCALISATION.items():
            values = self.localised[language]
            with self.subTest(language=language):
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)
                self.assertNotIn(b"\n", path.read_bytes().replace(b"\r\n", b""))
            for name in SHL_DEBUG_DECISIONS:
                with self.subTest(language=language, decision=name):
                    self.assertTrue(values[name].startswith("§RDEBUG:§! "), values.get(name))
                    self.assertTrue(values.get(name + "_desc"))
                    for text in (values[name], values[name + "_desc"]):
                        self.assertNotRegex(text, "[–—«»]")
            tooltips = [
                scalar(e.value, "tooltip") for body in self.decisions.values()
                for e in walk(body) if e.key == "custom_trigger_tooltip"
            ]
            self.assertTrue(tooltips)
            for key in tooltips:
                with self.subTest(language=language, tooltip=key):
                    self.assertTrue(values.get(key))

    def test_called_effects_triggers_events_and_ids_exist(self):
        for name, body in self.decisions.items():
            with self.subTest(decision=name):
                for call in boolean_calls(block(body, "complete_effect")):
                    if call not in NATIVE_BOOLEANS:
                        self.assertIn(call, self.effects, call)
                for section in ("visible", "available"):
                    for call in boolean_calls(block(body, section)):
                        if call not in NATIVE_BOOLEANS:
                            self.assertIn(call, self.triggers, call)
                for entry in walk(body):
                    if entry.key == "country_event":
                        self.assertIn(f"id = {scalar(entry.value, 'id')}\n", self.shl_events_text)
                    elif entry.key in ("has_power_balance", "add_power_balance_value"):
                        self.assertRegex(read(ROOT / "common/bop/SHL.txt"), rf"(?m)^{scalar(entry.value, 'id')} = \{{")
                    elif entry.key == "has_active_mission":
                        self.assertIn(f"\t{entry.value} = {{", read(SHL_DECISIONS))
                    elif entry.key in ("has_idea", "remove_ideas"):
                        self.assertIn(f"\t\t{entry.value} = {{", read(ROOT / "common/ideas/ADISCORD_southern_desert_ideas.txt"))
                    elif entry.key in ("set_variable", "add_to_variable"):
                        self.assertIn(f"var = {scalar(entry.value, 'var')}", self.shl_effects_text)
                    elif entry.key == "clr_country_flag":
                        self.assertIn(f"flag = {entry.value} ", self.shl_events_text)
                    elif entry.key == "has_country_flag":
                        self.assertIn(f"has_country_flag = {entry.value}", self.shl_effects_text)

    def test_course_shortcuts_call_their_guarded_commit_effects(self):
        for name, commit in COURSE_COMMITS.items():
            with self.subTest(decision=name):
                body = self.decisions[name]
                self.assertIn(commit, boolean_calls(block(body, "complete_effect")))
                guard = block(self.effects[commit][0].value, "limit")
                self.assertTrue(guard, commit)
                course_checks = [
                    scalar(e.value, "value") for e in walk(guard)
                    if e.key == "check_variable" and scalar(e.value, "var") == "SHL_political_course"
                ]
                self.assertTrue(course_checks, commit)
        for name in ("ADISCORD_shl_debug_ratify_houses", "ADISCORD_shl_debug_ratify_cities", "ADISCORD_shl_debug_ratify_directorate"):
            visible = block(self.decisions[name], "visible")
            checks = [e for e in walk(visible) if e.key == "check_variable"]
            self.assertEqual([(scalar(c.value, "value"), scalar(c.value, "compare")) for c in checks], [("0", "equals")])
            self.assertIn("remove_ideas", [e.key for e in walk(block(self.decisions[name], "complete_effect"))])
        for name in ("ADISCORD_shl_debug_regency", "ADISCORD_shl_debug_commune"):
            visible = block(self.decisions[name], "visible")
            checks = [e for e in walk(visible) if e.key == "check_variable"]
            self.assertEqual([(scalar(c.value, "value"), scalar(c.value, "compare")) for c in checks], [("4", "less_than")])
            self.assertNotIn("remove_ideas", [e.key for e in walk(block(self.decisions[name], "complete_effect"))])

    def test_advance_cycle_mirrors_the_run_cycle_body_without_the_clock(self):
        run_cycle = self.effects["SHL_run_cycle"]
        outer = next(e for e in run_cycle if e.key == "if")
        inner = next(e for e in outer.value if e.key == "if")
        expected = [e.key for e in inner.value if e.key != "limit"]
        actual = [e.key for e in block(self.decisions["ADISCORD_shl_debug_advance_cycle"], "complete_effect")]
        self.assertEqual(actual, expected)
        self.assertNotIn("SHL_cycle_pending", str([e.value for e in walk(self.decisions["ADISCORD_shl_debug_advance_cycle"])]))

    def test_house_demand_shortcut_reaches_the_demand_threshold(self):
        body = self.decisions["ADISCORD_shl_debug_house_demand"]
        effect = block(body, "complete_effect")
        forced = next(scalar(e.value, "value") for e in effect if e.key == "set_variable" and scalar(e.value, "var") == "SHL_demand_cycle")
        threshold = re.search(r"var = SHL_demand_cycle value = (\d+) compare = greater_than_or_equals", self.shl_effects_text).group(1)
        self.assertGreaterEqual(int(forced) + 1, int(threshold))
        self.assertEqual([e.key for e in effect], ["set_variable", "SHL_house_demand_tick"])
        missions = [e.value for e in walk(block(body, "available")) if e.key == "has_active_mission"]
        self.assertEqual(missions, ["SHL_house_demand"])

    def test_south_hegemon_flags_unlock_the_postwar_sections_of_every_course_tree(self):
        body = self.decisions["ADISCORD_shl_debug_south_hegemon"]
        flags = [e.value for e in block(body, "complete_effect") if e.key == "set_global_flag"]
        self.assertEqual(sorted(flags), ["ADISCORD_south_final_resolved", "ADISCORD_south_hegemon_SHL"])
        self.assertEqual(sorted(e.value for e in walk(block(body, "visible")) if e.key == "has_global_flag"), sorted(flags))
        self.assertIn("mark_focus_tree_layout_dirty", [e.key for e in block(body, "complete_effect")])
        for course in ("houses", "cities", "directorate", "regency", "commune"):
            with self.subTest(course=course):
                source = read(ROOT / f"focus_trees/SHL/{course}/focuses.txt")
                self.assertIn("allow_branch = { has_global_flag = ADISCORD_south_hegemon_SHL }", source)


if __name__ == "__main__":
    unittest.main()
