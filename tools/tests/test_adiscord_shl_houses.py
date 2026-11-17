"""Static checks for the SHL character registry; the native loader and UI need a fresh game."""

import json
import re
import unittest
from itertools import product
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
# Advisor trait of each house head; every trait is authored for one house.
HOUSE_TRAITS = {
    "SHL_Khosrow_Arbin": "SHL_house_arbin_qanat_masters",
    "SHL_Darius_Safir": "SHL_house_safir_purse",
    "SHL_Golshan_Loran": "SHL_house_loran_golden_gate",
    "SHL_Kamran_Nur": "SHL_house_nur_mediators",
    "SHL_Tahmuras_Bayrat": "SHL_house_bayrat_ore_lords",
    "SHL_Fereydun_Kerdan": "SHL_house_kerdan_sea_road",
    "SHL_Shirin_Sharim": "SHL_house_sharim_heavy_shifts",
    "SHL_Rauf_Darban": "SHL_house_darban_engineers",
    "SHL_Behruz_Veyran": "SHL_house_veyran_guards",
}
TRAITS = ROOT / "common/country_leader/ADISCORD_traits_SHL.txt"
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

    def test_each_house_head_carries_its_own_localised_trait(self):
        defined = {entry.key for entry in block(parse_clausewitz(read(TRAITS)), "leader_traits")}
        english = set()
        for path in (ROOT / "localisation/english").glob("*.yml"):
            english.update(LOCALISATION_KEY.findall(read(path)))
        self.assertEqual(len(set(HOUSE_TRAITS.values())), len(HOUSE_TRAITS))
        for name, trait in HOUSE_TRAITS.items():
            with self.subTest(character=name):
                advisor = block(self.characters[name], "advisor")
                self.assertEqual([e.value for e in block(advisor, "traits")], [trait])
                self.assertIn(trait, defined)
                for keys in (self.russian_keys, english):
                    self.assertTrue(trait in keys, trait)
                    self.assertTrue(trait + "_desc" in keys, trait + "_desc")

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
    "ADISCORD_shl_debug_house_walkout",
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


def without_leading_tooltips(items):
    """Drop the explanatory custom_effect_tooltip lines that open a debug effect block."""
    index = 0
    while index < len(items) and items[index].key == "custom_effect_tooltip":
        index += 1
    return items[index:]


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
                # Line endings follow the working copy's autocrlf state; only the BOM is a contract.
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)
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
        effect = block(self.decisions["ADISCORD_shl_debug_advance_cycle"], "complete_effect")
        actual = [e.key for e in without_leading_tooltips(effect)]
        self.assertEqual(actual, expected)
        self.assertNotIn("SHL_cycle_pending", str([e.value for e in walk(self.decisions["ADISCORD_shl_debug_advance_cycle"])]))

    def test_house_demand_shortcut_reaches_the_demand_threshold(self):
        body = self.decisions["ADISCORD_shl_debug_house_demand"]
        effect = without_leading_tooltips(block(body, "complete_effect"))
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
        # Each epilogue gate pairs the victory flag with its own course, so the
        # flag opens only the ratified course's epilogue.
        for course, value in (("houses", 1), ("cities", 2), ("directorate", 3), ("regency", 4), ("commune", 5)):
            with self.subTest(course=course):
                entries = parse_clausewitz(read(ROOT / f"focus_trees/SHL/{course}/focuses.txt"))
                gates = [block(e.value, "allow_branch") for e in entries if e.key == "focus"]
                epilogue = [
                    gate for gate in gates
                    if ("has_global_flag", "ADISCORD_south_hegemon_SHL") in [(e.key, e.value) for e in gate]
                ]
                self.assertEqual(len(epilogue), 6)
                for gate in epilogue:
                    self.assertEqual(
                        [(e.key, scalar(e.value, "var"), scalar(e.value, "value")) for e in gate if e.key == "check_variable"],
                        [("check_variable", "SHL_political_course", str(value))],
                    )
                    self.assertEqual(len(gate), 2)


SITES = tuple(str(state) for state in range(287, 296))
START_LOYALTY = dict(zip(SITES, (72, 90, 88, 95, 82, 75, 68, 85, 65)))
# House -> (state, loyalty price, treasury price, political power price).
FAVOURS = {
    "arbin": ("287", 15, 40, 0),
    "safir": ("288", 20, 0, 25),
    "loran": ("289", 15, 0, 20),
    "nur": ("290", 10, 0, 30),
    "bayrat": ("291", 15, 30, 0),
    "kerdan": ("292", 15, 40, 0),
    "sharim": ("293", 15, 50, 0),
    "darban": ("294", 15, 40, 0),
    "veyran": ("295", 20, 60, 0),
}
PRESSURE_WRITE = re.compile(
    r"(?:add_to|subtract_from|set|clamp|multiply|divide)_variable = \{ var = SHL_house_pressure\b"
)
BALANCE = "SHL_conclave_balance"


def walk_values(items):
    for entry in items:
        yield entry
        if isinstance(entry.value, list):
            yield from walk_values(entry.value)


class HouseLoyaltyTests(unittest.TestCase):
    """Per-house loyalty on the furnace states and the derived national pressure."""

    @classmethod
    def setUpClass(cls):
        from tools.tests import test_adiscord_shl_furnaces as furnaces

        cls.furnaces = furnaces
        cls.effect_entries = parse_clausewitz(read(SHL_EFFECTS))
        cls.trigger_entries = parse_clausewitz(read(ROOT / "common/scripted_triggers/ADISCORD_SHL_scripted_triggers.txt"))
        cls.events = {
            scalar(e.value, "id"): e.value
            for e in parse_clausewitz(read(SHL_EVENTS)) if e.key == "country_event"
        }

    def setUp(self):
        self.m = self.furnaces.ScriptMachine(self.effect_entries, self.trigger_entries)
        for state in SITES:
            self.m.variables[state].update({
                "SHL_furnace_stock": 3.0,
                "SHL_furnace_wear": 20.0,
                "SHL_furnace_owner": 0.0,
                "SHL_furnace_running": 1.0,
                "SHL_furnace_training": 0.0,
                "SHL_furnace_recipient": 0.0,
            })
        self.m.flags["SHL"].add("SHL_furnaces_initialized")
        self.m.power_balance[BALANCE] = 0.0
        self.c = self.m.variables["SHL"]
        self.c.update({"SHL_shift_policy": 0.0, "SHL_packet_price": 25.0, "SHL_selected_furnace": 1.0})
        self.m.run("SHL_initialize_tensions")
        self.m.run("SHL_refresh_furnaces")

    def loyalty(self, state):
        return self.m.variables[state]["SHL_house_loyalty"]

    def seat(self, value):
        for state in SITES:
            self.m.variables[state]["SHL_house_loyalty"] = float(value)
        self.m.run("SHL_refresh_house_pressure")

    def options(self, event_id):
        return [e.value for e in self.events[event_id] if e.key == "option"]

    def test_starting_loyalties_keep_the_starting_pressure_of_20(self):
        self.assertEqual({state: self.loyalty(state) for state in SITES}, START_LOYALTY)
        self.assertEqual(self.c["SHL_house_pressure"], 20)
        self.assertEqual(self.c["SHL_loyalty_houses"], 9)
        self.assertNotIn("SHL_loyalty_sum", self.c)

    def test_pressure_has_a_single_writer_in_every_source(self):
        sources = [
            *(ROOT / "common/scripted_effects").glob("*.txt"),
            *(ROOT / "common/scripted_triggers").glob("*.txt"),
            *(ROOT / "common/decisions").rglob("*.txt"),
            *(ROOT / "common/scripted_guis").glob("*.txt"),
            *(ROOT / "common/on_actions").glob("*.txt"),
            *(ROOT / "common/characters").glob("*.txt"),
            *(ROOT / "events").glob("*.txt"),
            *(ROOT / "focus_trees").rglob("focuses.txt"),
        ]
        writers = []
        for path in sources:
            text = read(path)
            for match in PRESSURE_WRITE.finditer(text):
                owner = list(re.finditer(r"^(\w+) = \{", text[:match.start()], re.M))
                writers.append((path.relative_to(ROOT).as_posix(), owner[-1].group(1) if owner else None))
        self.assertTrue(writers)
        self.assertEqual(
            {writer for writer in writers if writer[1] != "SHL_refresh_house_pressure"},
            set(),
        )
        self.assertEqual({path for path, _ in writers}, {"common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"})

    def test_a_change_to_every_house_moves_the_pressure_exactly_and_lost_land_leaves_the_mean(self):
        self.seat(50)
        self.c["SHL_loyalty_delta"] = -10
        self.m.run("SHL_change_all_loyalty")
        self.assertEqual(self.c["SHL_house_pressure"], 60)
        self.assertNotIn("SHL_loyalty_delta", self.c)
        self.m.ownership["287"] = "KYZ"
        self.m.variables["287"]["SHL_house_loyalty"] = 0.0
        self.c["SHL_loyalty_delta"] = 5
        self.m.run("SHL_change_all_loyalty")
        self.assertEqual(self.loyalty("287"), 0)
        self.assertEqual(self.c["SHL_loyalty_houses"], 8)
        self.assertEqual(self.c["SHL_house_pressure"], 55)
        self.c["SHL_political_course"] = 5
        self.m.run("SHL_refresh_house_pressure")
        self.assertEqual(self.c["SHL_house_pressure"], 0)

    def test_a_site_change_touches_only_that_house_and_clamps(self):
        self.seat(50)
        self.c.update({"SHL_loyalty_site": 291, "SHL_loyalty_delta": 90})
        self.m.run("SHL_change_site_loyalty")
        self.assertEqual(self.loyalty("291"), 100)
        self.assertEqual([self.loyalty(state) for state in SITES if state != "291"], [50] * 8)
        self.assertAlmostEqual(self.c["SHL_house_pressure"], 50 - 50 / 9)
        self.assertNotIn("SHL_loyalty_site", self.c)

    def test_every_production_rate_equals_its_forecast(self):
        for course, owner, shift, recipient in product((0, 1), (0, 1, 2), (0, 1, 2), (0, 1, 2, 3)):
            with self.subTest(course=course, owner=owner, shift=shift, recipient=recipient):
                self.setUp()
                self.c.update({"SHL_political_course": course, "SHL_shift_policy": shift})
                self.m.variables["287"].update({"SHL_furnace_owner": owner, "SHL_furnace_recipient": recipient})
                self.m.run("SHL_refresh_furnaces")
                forecast = self.c["SHL_delivery_crests_1"]
                before = self.loyalty("287")
                self.m.run("SHL_produce_site", scope="287")
                self.assertEqual(self.loyalty("287") - before, forecast)
                # A crest pays three times the national figure; the houses and
                # the regency raise it by half.
                base = 0
                if recipient == 3:
                    base = ((18, 27, 9) if course == 1 else (12, 18, 6))[shift]
                if owner == 0:
                    base += (1, -1, -2, 0)[recipient] + (0, -2, 1)[shift]
                self.assertEqual(forecast, base)

    def test_the_totals_line_forecasts_the_pressure_change(self):
        # Mid-scale loyalties keep clamping out of the comparison.
        self.seat(50)
        for state, recipient in zip(SITES, (3, 3, 0, 1, 2, 0, 3, 1, 2)):
            self.m.variables[state]["SHL_furnace_recipient"] = recipient
        self.m.variables["288"]["SHL_furnace_owner"] = 1
        self.m.run("SHL_refresh_furnaces")
        forecast = self.c["SHL_preview_crests"]
        before = self.c["SHL_house_pressure"]
        self.m.run("SHL_produce_period")
        self.m.run("SHL_refresh_house_pressure")
        self.assertAlmostEqual(before - self.c["SHL_house_pressure"], forecast)

    def test_idle_worn_and_occupied_houses_lose_loyalty(self):
        for state in SITES:
            self.m.variables[state]["SHL_house_loyalty"] = 50.0
        self.m.variables["287"]["SHL_furnace_stock"] = 0.0
        self.m.variables["288"].update({"SHL_furnace_stock": 0.0, "SHL_furnace_owner": 1.0})
        self.m.variables["289"]["SHL_furnace_wear"] = 58.0
        self.m.control["290"] = "MZR"
        self.m.variables["291"]["SHL_furnace_owner"] = 2.0
        self.m.control["291"] = "MZR"
        self.m.run("SHL_produce_period")
        changes = {state: self.loyalty(state) - 50 for state in ("287", "288", "289", "290", "291", "292")}
        # Idle -3, worn -3 after the cycle's +1 export, occupied -5 for any owner.
        self.assertEqual(changes, {"287": -3, "288": 0, "289": -2, "290": -5, "291": -5, "292": 1})

    def test_extinction_and_crest_votes_follow_the_house(self):
        self.assertEqual(self.c["SHL_crest_support"], 9)
        self.m.variables["287"]["SHL_house_loyalty"] = 54.0
        self.m.flags["288"].add("SHL_house_opposed")
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_crest_support"], 7)
        self.assertEqual(self.c["SHL_house_votes"], 8)
        before = self.loyalty("289")
        self.m.run("SHL_extinguish_site", scope="289")
        self.assertEqual(self.loyalty("289"), before - 10)
        self.assertEqual(self.m.variables["289"]["SHL_furnace_owner"], 1)

    def test_walkout_picks_the_least_loyal_house_once_and_times_out_into_opposition(self):
        self.m.variables["293"]["SHL_house_loyalty"] = 35.0
        self.m.variables["295"]["SHL_house_loyalty"] = 30.0
        self.m.variables["294"]["SHL_house_loyalty"] = 20.0
        self.m.variables["294"]["SHL_furnace_owner"] = 1.0
        self.m.run("SHL_house_walkout_tick")
        self.m.run("SHL_house_walkout_tick")
        self.assertEqual(self.c["SHL_walkout_site"], 295)
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.141"), 1)
        start, buyback = self.options("ADISCORD_SHL.141")
        self.assertEqual(scalar(start, "name"), "ADISCORD_SHL.141.a")
        self.m.execute(block(start, "hidden_effect"), "SHL")
        self.assertEqual(self.m.missions, {"SHL_house_walkout"})
        mission = self.furnaces.decision_definition("SHL_house_walkout")
        self.assertEqual(scalar(mission, "days_mission_timeout"), "56")
        goal = block(mission, "available")
        self.assertFalse(self.m.matches(goal, "SHL"))
        self.m.execute(block(mission, "timeout_effect"), "SHL")
        self.assertIn("SHL_house_opposed", self.m.flags["295"])
        self.assertEqual(self.c["SHL_walkout_site"], 0)
        # Darban's furnace belongs to the city, so seven houses still vote.
        self.assertEqual(self.c["SHL_house_votes"], 7)
        self.assertEqual(self.m.power_balance[BALANCE], 0.05)
        # The opposed house is no longer asked to walk out; the next one is.
        self.m.missions.clear()
        self.m.run("SHL_house_walkout_tick")
        self.assertEqual(self.c["SHL_walkout_site"], 293)
        # An opposed house that regains 55 returns before its 180 days end.
        self.m.variables["295"]["SHL_house_loyalty"] = 55.0
        self.m.run("SHL_house_return_tick")
        self.assertNotIn("SHL_house_opposed", self.m.flags["295"])
        self.assertEqual(self.m.power_balance[BALANCE], 0.0)
        self.assertEqual(self.c["SHL_house_votes"], 8)

    def test_walkout_goal_settlement_and_buyback(self):
        self.m.variables["295"]["SHL_house_loyalty"] = 30.0
        self.m.run("SHL_house_walkout_tick")
        start, buyback = self.options("ADISCORD_SHL.141")
        self.m.execute(block(start, "hidden_effect"), "SHL")
        mission = self.furnaces.decision_definition("SHL_house_walkout")
        self.m.variables["295"]["SHL_house_loyalty"] = 55.0
        self.assertTrue(self.m.matches(block(mission, "available"), "SHL"))
        self.m.execute(block(mission, "complete_effect"), "SHL")
        self.assertEqual(self.loyalty("295"), 60)
        self.assertEqual(self.c["SHL_walkout_site"], 0)
        # A furnace taken from the house also ends the walkout.
        self.m.variables["295"]["SHL_house_loyalty"] = 30.0
        self.m.missions.clear()
        self.m.run("SHL_house_walkout_tick")
        self.m.variables["295"]["SHL_furnace_owner"] = 2.0
        self.assertTrue(self.m.matches(block(mission, "available"), "SHL"))
        # The buyback charges both prices once, or starts the mission on a shortfall.
        for treasury, paid in ((100.0, True), (99.99, False)):
            with self.subTest(treasury=treasury):
                self.setUp()
                self.m.variables["295"]["SHL_house_loyalty"] = 30.0
                self.m.run("SHL_house_walkout_tick")
                self.c["ADISCORD_economy_treasury"] = treasury
                self.m.execute(block(buyback, "hidden_effect"), "SHL")
                self.assertEqual(self.c["ADISCORD_economy_treasury"], 0 if paid else treasury)
                self.assertEqual(self.m.values["political_power"], 175 if paid else 200)
                self.assertEqual(self.loyalty("295"), 50 if paid else 30)
                self.assertEqual(self.m.missions, set() if paid else {"SHL_house_walkout"})
                self.assertEqual(self.c["SHL_walkout_site"], 0 if paid else 295)

    def test_commune_and_annexation_close_the_walkout(self):
        for closer in ("SHL_commit_commune_course", "SHL_abort_annexed_operations"):
            with self.subTest(closer=closer):
                self.setUp()
                self.m.variables["295"]["SHL_house_loyalty"] = 30.0
                self.m.run("SHL_house_walkout_tick")
                self.m.run("SHL_start_house_walkout")
                self.m.variables["292"]["SHL_duty_paid_cycles"] = 1.0
                self.m.run(closer)
                self.assertEqual(self.m.missions, set())
                self.assertEqual(self.c["SHL_walkout_site"], 0)
                if closer == "SHL_commit_commune_course":
                    self.assertEqual(self.c["SHL_house_pressure"], 0)
                else:
                    self.assertNotIn("SHL_duty_paid_cycles", self.m.variables["292"])

    def test_every_favour_charges_once_delivers_and_waits_168_days(self):
        for house, (state, loyalty, treasury, power) in FAVOURS.items():
            with self.subTest(house=house):
                self.setUp()
                self.m.focuses.add("SHL_house_ledgers")
                self.c.update({"SHL_veyr_crisis": 1.0, "SHL_water_crisis": 1.0})
                for site in SITES:
                    self.m.variables[site].update({"SHL_furnace_stock": 2.0, "SHL_furnace_wear": 40.0})
                self.m.variables["295"]["SHL_furnace_wear"] = 70.0
                self.m.run("SHL_refresh_furnaces")
                before = {
                    "treasury": self.c["ADISCORD_economy_treasury"],
                    "power": self.m.values["political_power"],
                    "loyalty": self.loyalty(state),
                    "divisions": self.m.divisions,
                }
                self.m.run(f"SHL_grant_favour_{house}")
                self.m.run(f"SHL_grant_favour_{house}")
                self.assertEqual(self.loyalty(state), before["loyalty"] - loyalty)
                self.assertGreaterEqual(before["loyalty"] - 20, 40)
                self.assertEqual(self.m.values["political_power"], before["power"] - power)
                expected_treasury = before["treasury"] - treasury
                if house == "safir":
                    expected_treasury += 120
                elif house == "loran":
                    expected_treasury += 9 * 30
                self.assertEqual(self.c["ADISCORD_economy_treasury"], expected_treasury)
                self.assertIn("ADISCORD_economy_mark_dirty", self.m.calls)
                result = {
                    "arbin": lambda: [self.m.variables[s]["SHL_furnace_wear"] for s in ("287", "288", "289")] == [25, 25, 25],
                    "safir": lambda: True,
                    "loran": lambda: True,
                    "nur": lambda: self.loyalty("295") == START_LOYALTY["295"] + 20,
                    "bayrat": lambda: sum(self.m.variables[s]["SHL_furnace_stock"] for s in SITES) == 21,
                    "kerdan": lambda: self.m.variables["292"]["SHL_duty_paid_cycles"] == 2 and self.c["SHL_income_deduction"] == 0,
                    "sharim": lambda: self.m.variables["295"]["SHL_furnace_training"] == 1 and self.c["SHL_unrest"] == 20,
                    "darban": lambda: self.m.variables["295"]["SHL_furnace_wear"] == 40,
                    "veyran": lambda: self.m.divisions == before["divisions"] + 1,
                }[house]
                self.assertTrue(result(), house)
                age = self.m.flag_days[state]
                self.assertIn("SHL_favour_given", self.m.flags[state])
                ready = parse_clausewitz("SHL_favour_ready = yes")
                self.m.variables[state]["SHL_house_loyalty"] = 80.0
                age["SHL_favour_given"] = 167
                self.assertFalse(self.m.matches(ready, state))
                age["SHL_favour_given"] = 168
                self.assertTrue(self.m.matches(ready, state))

    def test_kerdan_pays_the_veyr_duty_for_exactly_two_productions(self):
        self.m.focuses.add("SHL_house_ledgers")
        self.c["SHL_veyr_crisis"] = 1.0
        self.m.run("SHL_refresh_furnaces")
        self.assertEqual(self.c["SHL_income_deduction"], 5)
        self.m.run("SHL_grant_favour_kerdan")
        incomes = []
        for _ in range(3):
            self.m.run("SHL_produce_period")
            incomes.append(self.c["SHL_last_cycle_income"])
        self.assertEqual(incomes, [540, 540, 495])
        self.assertNotIn("SHL_duty_paid_cycles", self.m.variables["292"])

    def test_decision_button_and_activation_read_the_same_checks(self):
        decisions = {}
        for category in parse_clausewitz(read(SHL_DECISIONS)):
            for decision in category.value if isinstance(category.value, list) else ():
                if decision.key.startswith("SHL_favour_"):
                    decisions[decision.key] = decision.value
        self.assertEqual(sorted(decisions), sorted(f"SHL_favour_{house}" for house in FAVOURS))
        activate = next(e.value for e in self.effect_entries if e.key == "SHL_activate_selected_favour")
        branches = [e.value for e in walk_values(activate) if e.key == "if" and block(e.value, "limit")
                    and any(c.key == "activate_targeted_decision" for c in e.value)]
        self.assertEqual(len(branches), 9)
        # The cached button reads only inputs that raise SHL_gui_dirty: the
        # house and the situation, never the price or the cooldown's age.
        triggers = {e.key: e.value for e in self.trigger_entries}
        selected = triggers["SHL_selected_favour_house_ready"]
        self.assertEqual([(e.key, e.value) for e in selected if e.key != "OR"],
                         [("SHL_house_favours_open", "yes"), ("SHL_selected_favour_open", "yes")])
        selected_branches = block(selected, "OR")
        self.assertEqual([(e.key, e.value) for e in triggers["SHL_favour_ready"]][0], ("SHL_favour_house_willing", "yes"))
        willing = repr(triggers["SHL_favour_house_willing"])
        for live in ("SHL_favour_given", "has_political_power", "ADISCORD_economy_treasury"):
            self.assertNotIn(live, willing)
        for index, (house, (state, *_)) in enumerate(FAVOURS.items(), 1):
            with self.subTest(house=house):
                body = decisions[f"SHL_favour_{house}"]
                self.assertEqual(scalar(body, "cost"), "0")
                self.assertEqual(scalar(body, "custom_cost_text"), f"SHL_cost_favour_{house}")
                self.assertEqual([e.value for e in block(body, "targets")], [state])
                available = {e.key for e in walk_values(block(body, "available")) if e.value == "yes"}
                self.assertLessEqual({"SHL_favour_ready", f"SHL_favour_{house}_price"}, available)
                expected = {f"check_variable:{index}", f"{state}:SHL_favour_ready",
                            f"SHL_favour_{house}_price", f"SHL_favour_{house}_open"}

                def parts(limit):
                    found = set()
                    for entry in limit:
                        if entry.key == "check_variable":
                            found.add(f"check_variable:{scalar(entry.value, 'value')}")
                        elif entry.key.isdigit():
                            found.add(f"{entry.key}:{entry.value[0].key}")
                        else:
                            found.add(entry.key)
                    return found

                self.assertEqual(parts(block(branches[index - 1], "limit")), expected)
                self.assertEqual(parts(selected_branches[index - 1].value),
                                 {f"check_variable:{index}", f"{state}:SHL_favour_house_willing"})
                target = block(branches[index - 1], "activate_targeted_decision")
                self.assertEqual((scalar(target, "target"), scalar(target, "decision")), (state, f"SHL_favour_{house}"))
                grant = next(e.value for e in self.effect_entries if e.key == f"SHL_grant_favour_{house}")
                guard = parts(block(grant[0].value, "limit"))
                self.assertEqual(guard, expected - {f"check_variable:{index}"} | {"SHL_house_favours_open"})
        gui = read(ROOT / "common/scripted_guis/ADISCORD_SHL_scripted_gui.txt")
        self.assertIn("SHL_house_favour_button_click_enabled = { SHL_selected_favour_house_ready = yes }", gui)
        self.assertIn("SHL_house_favour_button_click = { SHL_activate_selected_favour = yes }", gui)
        window = read(ROOT / "interface/ADISCORD_SHL.gui")
        for name in ("SHL_panel_house_loyalty", "SHL_house_favour_button"):
            self.assertIn(f'name = "{name}"', window)

    def test_walkout_event_and_mission_are_registered(self):
        registry = json.loads(read(ROOT / "tools/data/adiscord_event_ids.json"))
        entries = registry["events"] if isinstance(registry, dict) else registry
        ids = {entry["id"] for entry in entries}
        self.assertIn("ADISCORD_SHL.141", ids)
        tokens = read(ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt").split()
        self.assertIn("SHL_house_walkout", tokens)


if __name__ == "__main__":
    unittest.main()
