"""Static checks for SHL story text: event localisation, the Book of Furnaces chain and news IDs."""

import json
import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
EVENTS_PATH = ROOT / "events/ADISCORD_SHL_events.txt"
SCRIPTED_LOC_PATH = ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt"
REGISTRY_PATH = ROOT / "tools/data/adiscord_event_ids.json"
LANGUAGES = ("russian", "english")
BOOK_CHAPTERS = range(1, 6)
NEWS_IDS = tuple(f"ADISCORD_SHL_news.{number}" for number in range(1, 9))
FORBIDDEN = ("–", "—", "«", "»")


def block(items, key):
    return next((e.value for e in items if e.key == key and isinstance(e.value, list)), [])


def scalar(items, key, default=None):
    return next((e.value for e in items if e.key == key), default)


def load_values(language):
    path = ROOT / f"localisation/{language}/ADISCORD_SHL_l_{language}.yml"
    text = path.read_text(encoding="utf-8-sig")
    return dict(re.findall(r'^ ([\w.]+):(?:\d+)? "((?:[^"\\]|\\.)*)"$', text, re.M))


def expand(value):
    return value.replace("\\n", "\n").replace('\\"', '"')


class ShahrabadStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = parse_clausewitz(EVENTS_PATH.read_text(encoding="utf-8"))
        cls.events = {
            scalar(e.value, "id"): e.value
            for e in source if e.key in ("country_event", "news_event")
        }
        cls.values = {language: load_values(language) for language in LANGUAGES}
        cls.scripted_loc = SCRIPTED_LOC_PATH.read_text(encoding="utf-8")

    def description_keys(self, event):
        keys = []
        for entry in event:
            if entry.key != "desc":
                continue
            keys.append(scalar(entry.value, "text") if isinstance(entry.value, list) else entry.value)
        return keys

    def scripted_branches(self, name):
        definition = next(
            e.value for e in parse_clausewitz(self.scripted_loc)
            if e.key == "defined_text" and scalar(e.value, "name") == name
        )
        return [scalar(text.value, "localization_key") for text in definition if text.key == "text"]

    def test_every_visible_event_has_title_and_descriptions_in_both_languages(self):
        for event_id, event in self.events.items():
            if scalar(event, "hidden") == "yes":
                continue
            title = scalar(event, "title")
            keys = self.description_keys(event)
            self.assertTrue(keys, event_id)
            for language in LANGUAGES:
                values = self.values[language]
                self.assertIn(title, values, (event_id, language))
                for key in keys:
                    self.assertIn(key, values, (event_id, language))
                for option in (e.value for e in event if e.key == "option"):
                    self.assertIn(scalar(option, "name"), values, (event_id, language))

    def test_russian_event_descriptions_stay_within_the_authoring_window(self):
        values = self.values["russian"]
        for event_id, event in self.events.items():
            if scalar(event, "hidden") == "yes":
                continue
            for key in self.description_keys(event):
                text = expand(values[key])
                for macro in re.findall(r"\[(SHLGet\w+)\]", text):
                    longest = max(
                        (expand(values[branch]) for branch in self.scripted_branches(macro)),
                        key=lambda value: len(value.encode("utf-8")),
                    )
                    text = text.replace(f"[{macro}]", longest)
                self.assertGreaterEqual(len(text), 400, key)
                self.assertLessEqual(len(text), 3000, key)
                self.assertLess(len(text.encode("utf-8")), 5500, key)

    def test_localisation_files_use_ascii_punctuation_and_keep_english_latin(self):
        for language in LANGUAGES:
            path = ROOT / f"localisation/{language}/ADISCORD_SHL_l_{language}.yml"
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", raw, path)
            text = raw.decode("utf-8-sig")
            for character in FORBIDDEN:
                self.assertNotIn(character, text, (language, character))
        english = self.values["english"]
        for key, value in english.items():
            self.assertIsNone(re.search(r"[Ѐ-ӿ]", value), key)

    def test_cabinet_handover_names_the_course_leaders(self):
        values = self.values["russian"]
        # Name stems: Russian prose declines the names.
        expected = {
            "SHL_cabinet_story_house": ("Джалил", "Нур", "Амин", "Рашад"),
            "SHL_cabinet_story_city": ("Мариам Арбин",),
            "SHL_cabinet_story_state": ("Джалил", "Нур", "Рауф", "Дарбан"),
            "SHL_cabinet_story_regent": ("Дари", "Сафир"),
            "SHL_cabinet_story_commune": ("Салим", "Дарзи"),
        }
        self.assertEqual(
            self.scripted_branches("SHLGetCabinetStory"),
            [*expected, "SHL_cabinet_story_unratified"],
        )
        for key, names in expected.items():
            for name in names:
                self.assertIn(name, values[key], key)

    def test_book_chain_pages_close_and_chapters_offer_a_full_exit(self):
        for chapter in BOOK_CHAPTERS:
            first = self.events[f"ADISCORD_shl_book.{chapter}"]
            last = self.events[f"ADISCORD_shl_book.{chapter + 10}"]
            self.assertEqual(scalar(first, "fire_only_once"), "yes")
            self.assertEqual(scalar(first, "title"), scalar(last, "title"))
            first_options = [e.value for e in first if e.key == "option"]
            last_options = [e.value for e in last if e.key == "option"]
            exits = [o for o in first_options if scalar(o, "name") == "ADISCORD_shl_book.put_away"]
            self.assertEqual(len(exits), 1)
            self.assertEqual([e.key for e in exits[0]], ["name"])
            self.assertEqual(len(last_options), 1)
            self.assertEqual([e.key for e in last_options[0]], ["name"])
            self.assertEqual(scalar(last_options[0], "name"), "ADISCORD_shl_book.close")
            self.assertNotIn("immediate", [e.key for e in first + last])
            continuation = next(o for o in first_options if scalar(o, "name") == "ADISCORD_shl_book.read_on")
            effects = block(continuation, "hidden_effect")
            self.assertEqual([e.key for e in effects], ["country_event"])
            self.assertEqual(scalar(block(effects, "country_event"), "id"), f"ADISCORD_shl_book.{chapter + 10}")

    def test_book_dispatcher_requeues_only_while_chapters_remain(self):
        dispatcher = self.events["ADISCORD_shl_book.99"]
        self.assertEqual(scalar(dispatcher, "hidden"), "yes")
        self.assertEqual([e.key for e in block(dispatcher, "trigger")], ["tag"])
        immediate = block(dispatcher, "immediate")
        branches = [e.value for e in immediate if e.key == "if"]
        self.assertEqual(len(branches), 2)
        reader, requeue = branches
        limit = block(reader, "limit")
        self.assertEqual(scalar(limit, "is_ai"), "no")
        self.assertEqual(scalar(limit, "SHL_country_operable"), "yes")
        fired = []
        for branch in (e.value for e in reader if e.key in ("if", "else_if")):
            check = block(block(branch, "limit"), "check_variable")
            self.assertEqual(scalar(check, "var"), "SHL_book_next")
            fired.append((int(scalar(check, "value")), scalar(block(branch, "country_event"), "id")))
        self.assertEqual(fired, [(n, f"ADISCORD_shl_book.{n}") for n in BOOK_CHAPTERS])
        increment = block(reader, "add_to_variable")
        self.assertEqual((scalar(increment, "var"), scalar(increment, "value")), ("SHL_book_next", "1"))
        guard = block(block(requeue, "limit"), "check_variable")
        self.assertEqual(scalar(guard, "var"), "SHL_book_next")
        self.assertEqual(scalar(guard, "value"), "6")
        self.assertEqual(scalar(guard, "compare"), "less_than")
        callback = block(requeue, "country_event")
        self.assertEqual(scalar(callback, "id"), "ADISCORD_shl_book.99")
        self.assertEqual(scalar(callback, "days"), "90")
        self.assertEqual([e.key for e in requeue], ["limit", "country_event"])

    def test_news_events_are_registered_and_shaped_for_neighbours(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        registered = {entry["id"]: entry for entry in registry["events"]}
        for event_id in (*NEWS_IDS, *(f"ADISCORD_shl_book.{n}" for n in (*BOOK_CHAPTERS, *range(11, 16), 99))):
            self.assertIn(event_id, registered)
            self.assertEqual(registered[event_id]["owner"], "events/ADISCORD_SHL_events.txt")
            self.assertEqual(registered[event_id]["status"], "active")
            self.assertIn(event_id, self.events)
        for event_id in NEWS_IDS:
            event = self.events[event_id]
            # Regional news reaches its readers through show_major, not a
            # country scan in the sending effect.
            self.assertEqual(scalar(event, "major"), "yes")
            self.assertEqual([(e.key, e.value) for e in block(event, "show_major")], [("SHL_southern_news_reader", "yes")])
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertTrue(scalar(event, "picture", "").startswith("GFX_news_event_"))
            options = [e.value for e in event if e.key == "option"]
            self.assertEqual(len(options), 1)
            self.assertEqual([e.key for e in options[0]], ["name"])


EFFECTS_PATH = ROOT / "common/scripted_effects/ADISCORD_SHL_scripted_effects.txt"
DECISIONS_PATH = ROOT / "common/decisions/ADISCORD_SHL_decisions.txt"
MAIN_FOCUS_PATH = ROOT / "focus_trees/SHL/main/focuses.txt"
ARCHIVE_FOCUSES = {
    "ADISCORD_shl_life.1": "SHL_census_of_nine",
    "ADISCORD_shl_life.2": "SHL_school_of_masters",
    "ADISCORD_shl_life.3": "SHL_baryat_mines",
    "ADISCORD_shl_life.4": "SHL_houses_railway",
    "ADISCORD_shl_life.5": "SHL_metal_market",
    "ADISCORD_shl_life.6": "SHL_quarter_listening",
    "ADISCORD_shl_life.7": "SHL_railway_guard",
    "ADISCORD_shl_life.8": "SHL_southern_watch",
}
AMBIENT_IDS = tuple(f"ADISCORD_shl_life.{number}" for number in range(20, 28))
FESTIVAL_ID = "ADISCORD_shl_life.30"
LIFE_IDS = (*ARCHIVE_FOCUSES, *AMBIENT_IDS, FESTIVAL_ID)
TREASURY_VAR = "ADISCORD_economy_treasury"


def walk(items):
    for entry in items:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


def event_calls(items):
    return [scalar(e.value, "id") for e in walk(items) if e.key == "country_event" and isinstance(e.value, list)]


class FurnaceLifeTests(unittest.TestCase):
    """Archive vignettes, the ambient channel and the festival of fire."""

    @classmethod
    def setUpClass(cls):
        ShahrabadStoryTests.setUpClass.__func__(cls)
        cls.effects = {e.key: e.value for e in parse_clausewitz(EFFECTS_PATH.read_text(encoding="utf-8"))}
        cls.effects_text = EFFECTS_PATH.read_text(encoding="utf-8")
        decisions = parse_clausewitz(DECISIONS_PATH.read_text(encoding="utf-8"))
        cls.campaigns = {e.key: e.value for e in block(decisions, "SHL_public_campaigns")}
        tree = block(parse_clausewitz(MAIN_FOCUS_PATH.read_text(encoding="utf-8")), "focus_tree")
        cls.focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}

    def options(self, event_id):
        return [e.value for e in self.events[event_id] if e.key == "option"]

    def test_life_events_are_registered_and_localised_in_both_languages(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        registered = {entry["id"]: entry for entry in registry["events"]}
        for event_id in LIFE_IDS:
            self.assertIn(event_id, registered)
            self.assertEqual(registered[event_id]["owner"], "events/ADISCORD_SHL_events.txt")
            self.assertEqual(registered[event_id]["status"], "active")
            self.assertIn(event_id, self.events)
            event = self.events[event_id]
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertEqual([(e.key, e.value) for e in block(event, "trigger")], [("tag", "SHL"), ("is_ai", "no")])
            self.assertTrue(scalar(event, "picture", "").startswith("GFX_event_adiscord_"))
            for language in LANGUAGES:
                values = self.values[language]
                self.assertIn(scalar(event, "title"), values, (event_id, language))
                self.assertIn(scalar(event, "desc"), values, (event_id, language))
                for option in self.options(event_id):
                    self.assertIn(scalar(option, "name"), values, (event_id, language))
                    tooltip = scalar(option, "custom_effect_tooltip")
                    if tooltip:
                        self.assertIn(tooltip, values, (event_id, language))

    def test_archive_vignettes_fire_once_from_exactly_the_eight_focuses(self):
        for event_id, focus_id in ARCHIVE_FOCUSES.items():
            event = self.events[event_id]
            self.assertEqual(scalar(event, "fire_only_once"), "yes", event_id)
            options = self.options(event_id)
            self.assertEqual(len(options), 1, event_id)
            self.assertEqual([e.key for e in options[0]], ["name"], event_id)
            reward = block(self.focuses[focus_id], "completion_reward")
            hooks = [e.value for e in reward if e.key == "hidden_effect" and event_calls(e.value) == [event_id]]
            self.assertEqual(len(hooks), 1, (event_id, focus_id))
            self.assertIs(reward[-1].value, hooks[0], (event_id, focus_id))
            call = block(hooks[0], "country_event")
            self.assertEqual(scalar(call, "hours"), "6")
        archive_ids = set(ARCHIVE_FOCUSES)
        callers = {
            focus_id for focus_id, body in self.focuses.items()
            if archive_ids & set(event_calls(block(body, "completion_reward")))
        }
        self.assertEqual(callers, set(ARCHIVE_FOCUSES.values()))
        for text in (self.effects_text, DECISIONS_PATH.read_text(encoding="utf-8"), EVENTS_PATH.read_text(encoding="utf-8")):
            for event_id in ARCHIVE_FOCUSES:
                self.assertNotIn(f"id = {event_id} ", text)

    def test_life_draw_runs_once_per_cycle_for_a_human_and_respects_the_cooldown(self):
        self.assertEqual(self.effects_text.count("SHL_life_draw = yes"), 1)
        cycle = block(self.effects["SHL_run_cycle"], "if")
        operable = next(e.value for e in cycle if e.key == "if")
        keys = [e.key for e in operable]
        self.assertIn("SHL_life_draw", keys)
        self.assertEqual(keys.index("SHL_life_draw"), keys.index("SHL_crisis_draw") + 1)
        draw = block(self.effects["SHL_life_draw"], "if")
        limit = block(draw, "limit")
        self.assertEqual(scalar(limit, "is_ai"), "no")
        self.assertEqual(scalar(limit, "SHL_country_operable"), "yes")
        self.assertIn(("has_country_flag", "SHL_life_cooldown"), [(e.key, e.value) for e in block(limit, "NOT")])
        outer = block(draw, "random_list")
        self.assertEqual([e.key for e in outer], ["85", "15"])
        self.assertEqual(block(outer, "85"), [])
        inner = block(block(outer, "15"), "random_list")
        fired = []
        for branch in inner:
            self.assertEqual(branch.key, "10")
            fired.extend(event_calls(branch.value))
            for modifier in (e.value for e in branch.value if e.key == "modifier"):
                self.assertEqual(scalar(modifier, "factor"), "0")
        self.assertEqual(fired, list(AMBIENT_IDS))
        # The sandstorm has no condition, so the inner list never empties.
        sandstorm = next(b.value for b in inner if event_calls(b.value) == ["ADISCORD_shl_life.25"])
        self.assertEqual([e.key for e in sandstorm], ["country_event"])

    def test_ambient_events_set_the_cooldown_and_pay_exactly_once(self):
        for event_id in AMBIENT_IDS:
            event = self.events[event_id]
            self.assertEqual(scalar(event, "fire_only_once"), "no", event_id)
            immediate = block(block(event, "immediate"), "hidden_effect")
            flag = block(immediate, "set_country_flag")
            self.assertEqual(scalar(flag, "flag"), "SHL_life_cooldown", event_id)
            self.assertEqual(scalar(flag, "days"), "120", event_id)
            options = self.options(event_id)
            self.assertEqual(len(options), 2, event_id)
            free, paid = options
            self.assertEqual([e.key for e in free], ["name"], event_id)
            trigger = block(paid, "trigger")
            self.assertTrue(trigger, event_id)
            self.assertIsNotNone(scalar(paid, "custom_effect_tooltip"), event_id)
            payload = list(walk(paid))
            treasury_checks = [
                e for e in walk(trigger)
                if e.key == "check_variable" and scalar(e.value, "var") == TREASURY_VAR
            ]
            treasury_debits = [
                e for e in payload
                if e.key == "subtract_from_variable" and scalar(e.value, "var") == TREASURY_VAR
            ]
            power_debits = [e for e in payload if e.key == "add_political_power" and float(e.value) < 0]
            if treasury_checks:
                price = scalar(treasury_checks[0].value, "value")
                self.assertEqual(scalar(treasury_checks[0].value, "compare"), "greater_than_or_equals", event_id)
                self.assertTrue(20 <= int(price) <= 40, (event_id, price))
                self.assertEqual(len(treasury_debits), 1, event_id)
                self.assertEqual(scalar(treasury_debits[0].value, "value"), price, event_id)
                self.assertEqual(power_debits, [], event_id)
                # The debit is guarded by the same price inside hidden_effect.
                guard = block(block(block(paid, "hidden_effect"), "if"), "limit")
                self.assertIn(price, [scalar(e.value, "value") for e in guard if e.key == "check_variable"], event_id)
                self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in payload], event_id)
            else:
                native = [item.value for item in trigger if not item.key]
                compare = [item.value for item in walk(block(trigger, "NOT")) if not item.key]
                self.assertEqual(compare[:2], ["has_political_power", "<"], (event_id, native))
                price = compare[2]
                self.assertTrue(10 <= int(price) <= 20, (event_id, price))
                self.assertEqual(len(power_debits), 1, event_id)
                self.assertEqual(power_debits[0].value, f"-{price}", event_id)
                self.assertEqual(treasury_debits, [], event_id)
            tension_writes = [
                e for e in payload
                if e.key in ("add_to_variable", "subtract_from_variable")
                and scalar(e.value, "var") in ("SHL_unrest", "SHL_city_support", "SHL_house_pressure")
            ]
            if tension_writes:
                self.assertIn("SHL_clamp_tensions", [e.key for e in payload], event_id)
            self.assertNotIn("every_country", [e.key for e in payload], event_id)
            self.assertNotIn("every_state", [e.key for e in payload], event_id)

    def test_festival_of_fire_is_a_priced_annual_decision_with_a_settlement_vignette(self):
        decision = self.campaigns["SHL_festival_of_fire"]
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual(scalar(decision, "custom_cost_text"), "SHL_cost_festival")
        self.assertEqual(scalar(decision, "days_remove"), "14")
        self.assertEqual(scalar(decision, "days_re_enable"), "365")
        self.assertEqual([(e.key, e.value) for e in block(decision, "visible")], [("has_completed_focus", "SHL_quarter_listening")])
        for language in LANGUAGES:
            values = self.values[language]
            for key in ("SHL_festival_of_fire", "SHL_festival_of_fire_desc", "SHL_cost_festival",
                        "SHL_cost_festival_blocked", "SHL_cost_festival_tooltip",
                        "SHL_festival_begin_tt", "SHL_festival_result_tt"):
                self.assertIn(key, values, (key, language))
            self.assertNotIn("ПРОПАГАНДА", values["SHL_festival_of_fire"])
            self.assertNotIn("PROPAGANDA", values["SHL_festival_of_fire"])
            self.assertRegex(values["SHL_cost_festival"], r"^§Y60§! £ADISCORD_economy_treasury_texticon / §Y25§! £political_power_texticon$")
        for container in ("available", "custom_cost_trigger"):
            trigger = block(decision, container)
            check = next(e.value for e in trigger if e.key == "check_variable")
            self.assertEqual((scalar(check, "var"), scalar(check, "value"), scalar(check, "compare")), (TREASURY_VAR, "60", "greater_than_or_equals"))
            self.assertEqual([item.value for item in walk(block(trigger, "NOT")) if not item.key], ["has_political_power", "<", "25"])
        complete = list(walk(block(decision, "complete_effect")))
        debits = [e for e in complete if e.key == "subtract_from_variable" and scalar(e.value, "var") == TREASURY_VAR]
        self.assertEqual([scalar(e.value, "value") for e in debits], ["60"])
        self.assertEqual([e.value for e in complete if e.key == "add_political_power"], ["-25"])
        self.assertIn("ADISCORD_economy_mark_dirty", [e.key for e in complete])
        remove = block(decision, "remove_effect")
        self.assertEqual(scalar(remove, "add_stability"), "0.03")
        hidden = block(remove, "hidden_effect")
        writes = {scalar(e.value, "var"): scalar(e.value, "value") for e in hidden if e.key == "subtract_from_variable"}
        self.assertEqual(writes, {"SHL_unrest": "5", "SHL_house_pressure": "3"})
        self.assertEqual(scalar(hidden, "SHL_clamp_tensions"), "yes")
        self.assertEqual(event_calls(hidden), [FESTIVAL_ID])
        self.assertEqual(event_calls(block(decision, "complete_effect")), [])
        festival = self.events[FESTIVAL_ID]
        options = self.options(FESTIVAL_ID)
        self.assertEqual(len(options), 1)
        self.assertEqual([e.key for e in options[0]], ["name"])
        self.assertNotIn("immediate", [e.key for e in festival])
        ai = block(decision, "ai_will_do")
        gate = block(block(ai, "modifier"), "check_variable")
        self.assertEqual(scalar(block(ai, "modifier"), "factor"), "0")
        self.assertEqual((scalar(gate, "var"), scalar(gate, "value"), scalar(gate, "compare")), (TREASURY_VAR, "400", "less_than_or_equals"))


if __name__ == "__main__":
    unittest.main()
