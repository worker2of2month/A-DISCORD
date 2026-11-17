"""Static checks for SHL story text: event localisation, the Book of Furnaces chain and news IDs."""

import json
import re
import unittest
from itertools import product
from pathlib import Path

from tools.tests import test_adiscord_shl_furnaces as furnaces
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
EVENTS_PATH = ROOT / "events/ADISCORD_SHL_events.txt"
SCRIPTED_LOC_PATH = ROOT / "common/scripted_localisation/ADISCORD_SHL_scripted_loc.txt"
REGISTRY_PATH = ROOT / "tools/data/adiscord_event_ids.json"
LANGUAGES = ("russian", "english")
BOOK_CHAPTERS = range(1, 6)
NEWS_IDS = tuple(f"ADISCORD_SHL_news.{number}" for number in range(1, 12))
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
            "SHL_cabinet_story_city": ("Мехран Арбин",),
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
        visible = block(decision, "visible")
        self.assertEqual([e.key for e in visible], ["OR"])
        self.assertEqual(
            [(e.key, e.value) for e in visible[0].value],
            [("has_completed_focus", "SHL_quarter_listening"), ("has_completed_focus", "SHL_written_fire")],
        )
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
        self.assertEqual(writes, {"SHL_unrest": "5"})
        # Every house gains 3 loyalty, so the derived pressure falls by 3.
        loyalty = [scalar(e.value, "value") for e in hidden
                   if e.key == "set_variable" and scalar(e.value, "var") == "SHL_loyalty_delta"]
        self.assertEqual(loyalty, ["3"])
        self.assertEqual(scalar(hidden, "SHL_change_all_loyalty"), "yes")
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


CATEGORIES_PATH = ROOT / "common/decisions/categories/ADISCORD_decision_categories_SHL.txt"


class MainTrunkCampaignTests(unittest.TestCase):
    """Both sides of the quarters pair open the Voice of the Furnaces campaigns."""

    @classmethod
    def setUpClass(cls):
        FurnaceLifeTests.setUpClass.__func__(cls)

    def test_heralds_and_listening_each_grant_one_slot_and_open_the_category(self):
        honour = block(self.campaigns["SHL_campaign_honour_of_crests"], "visible")
        self.assertEqual([e.key for e in honour], ["OR"])
        self.assertEqual(
            {(e.key, e.value) for e in honour[0].value},
            {("has_completed_focus", "SHL_heralds_table"), ("has_completed_focus", "SHL_r_safir_cabinet")},
        )
        categories = parse_clausewitz(CATEGORIES_PATH.read_text(encoding="utf-8"))
        visible = block(block(categories, "SHL_public_campaigns"), "visible")
        self.assertIn(("has_completed_focus", "SHL_heralds_table"), [(e.key, e.value) for e in block(visible, "OR")])
        for focus_id in ("SHL_quarter_listening", "SHL_heralds_table"):
            reward = block(self.focuses[focus_id], "completion_reward")
            grants = [e for e in walk(reward) if e.key == "ADISCORD_campaign_slot_grant"]
            self.assertEqual(len(grants), 1, focus_id)


TOKENS_PATH = ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt"
SHL_AI_PATH = ROOT / "common/ai_strategy/ADISCORD_SHL_ai.txt"
PEACE_ON_ACTIONS_PATH = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
SHL_ON_ACTIONS_PATH = ROOT / "common/on_actions/03_ADISCORD_SHL_on_actions.txt"
FRONT_MISSIONS = ("SHL_kyz_front_hold", "SHL_kyz_front_lost", "SHL_glp_front_hold", "SHL_glp_front_lost")
FRONT_PREDICATES = ("SHL_kyz_front_ours", "SHL_kyz_front_theirs", "SHL_glp_front_ours", "SHL_glp_front_theirs")
# Objective districts of each limited war: the enemy's land, then Shahrabad's.
QANAT_FRONT = (("280", "284"), ("287", "288", "289"))
RATION_FRONT = (("280", "284"), ("707", "287", "288", "289"))
PORT_FRONT = (("297", "299", "708"), ("296", "733", "293", "295"))


class FrontMachine(furnaces.ScriptMachine):
    """The furnace machine plus the native building levels read by the front battery."""

    def matches(self, items, scope, target=None):
        rest = []
        results = []
        index = 0
        while index < len(items):
            entry = items[index]
            if not entry.key and entry.value in ("arms_factory", "infrastructure") and items[index + 1].value == ">":
                results.append(self.state_buildings[(scope, entry.value)] > float(items[index + 2].value))
                index += 3
            else:
                rest.append(entry)
                index += 1
        return all(results) and super().matches(rest, scope, target)


class LimitedWarModelTests(unittest.TestCase):
    """Limited wars with Keizan and Veyr: objectives, armistice grades, terms and return."""

    @classmethod
    def setUpClass(cls):
        source = parse_clausewitz(EVENTS_PATH.read_text(encoding="utf-8"))
        cls.events = {scalar(e.value, "id"): e.value for e in source if e.key in ("country_event", "news_event")}
        cls.effect_entries = parse_clausewitz(furnaces.EFFECT_PATH.read_text(encoding="utf-8"))
        cls.trigger_entries = parse_clausewitz(furnaces.TRIGGER_PATH.read_text(encoding="utf-8"))
        cls.effects = {e.key: e.value for e in cls.effect_entries}

    def setUp(self):
        self.m = FrontMachine(self.effect_entries, self.trigger_entries)
        for state in range(287, 296):
            self.m.variables[str(state)].update({
                "SHL_furnace_stock": 3.0,
                "SHL_furnace_wear": 20.0,
                "SHL_furnace_owner": 0.0,
                "SHL_furnace_running": 1.0,
                "SHL_furnace_training": 0.0,
            })
        self.m.ownership["733"] = "SHL"
        self.m.control["733"] = "SHL"
        self.m.flags["SHL"].add("SHL_furnaces_initialized")
        self.m.variables["SHL"]["SHL_shift_policy"] = 0.0
        self.m.run("SHL_initialize_tensions")
        self.m.run("SHL_refresh_furnaces")

    def country(self):
        return self.m.variables["SHL"]

    def holds(self, name, scope="SHL"):
        return self.m.matches(parse_clausewitz(f"{name} = yes"), scope)

    def start(self, war, sea=False, offensive=False):
        c = self.country()
        if war == "qanat":
            c["SHL_water_crisis"] = 1
            self.m.focuses.add("SHL_qanat_guard")
            self.m.run("SHL_start_qanat_war")
            self.assertEqual(c["SHL_war_kyz"], 1)
        elif war == "ration":
            c["SHL_keizan_state"] = 5
            if offensive:
                self.m.flags["SHL"].add("SHL_kyz_offensive")
            self.m.run("SHL_start_kyz_war")
            self.assertEqual(c["SHL_war_kyz"], 2)
        else:
            c["SHL_veyr_crisis"] = 1
            self.m.focuses.add("SHL_key_to_sea" if sea else "SHL_veyr_ultimatum")
            self.m.run("SHL_start_glp_war")
            self.assertEqual(c["SHL_war_glp"], 1)

    def hold(self, states, holder):
        for state in states:
            self.m.control[str(state)] = holder

    def timeout(self, mission):
        self.m.execute(block(furnaces.decision_definition(mission), "timeout_effect"), "SHL")

    def options(self, event_id):
        return [e.value for e in self.events[event_id] if e.key == "option"]

    def answer(self, event_id, index, scope):
        self.m.execute(block(self.options(event_id)[index], "hidden_effect"), scope)

    def test_neither_side_meets_its_objective_at_declaration(self):
        for war, sea, offensive in (("qanat", False, False), ("port", False, False), ("port", True, False),
                                    ("ration", False, False), ("ration", False, True)):
            with self.subTest(war=war, sea=sea, offensive=offensive):
                self.setUp()
                self.start(war, sea, offensive)
                for name in FRONT_PREDICATES:
                    self.assertFalse(self.holds(name), name)

    def test_front_predicates_are_mutually_exclusive_and_both_reachable(self):
        cases = (
            ("qanat", False, "KYZ", QANAT_FRONT, "SHL_kyz_front_ours", "SHL_kyz_front_theirs"),
            ("ration", False, "KYZ", RATION_FRONT, "SHL_kyz_front_ours", "SHL_kyz_front_theirs"),
            ("port", False, "GLP", PORT_FRONT, "SHL_glp_front_ours", "SHL_glp_front_theirs"),
            ("port", True, "GLP", PORT_FRONT, "SHL_glp_front_ours", "SHL_glp_front_theirs"),
        )
        for war, sea, enemy, (theirs, ours), win, loss in cases:
            with self.subTest(war=war, sea=sea):
                self.setUp()
                self.start(war, sea)
                seen = set()
                states = theirs + ours
                for holders in product(("SHL", enemy), repeat=len(states)):
                    self.hold(states, "SHL")
                    for state, holder in zip(states, holders):
                        self.m.control[state] = holder
                    result = (self.holds(win), self.holds(loss))
                    self.assertNotEqual(result, (True, True), holders)
                    seen.add(result)
                self.assertEqual(seen, {(False, False), (True, False), (False, True)})

    def test_front_check_starts_and_stops_hold_missions_and_ignores_other_occupiers(self):
        self.start("qanat")
        self.hold(("280", "284"), "SHL")
        self.m.run("SHL_queue_front_check")
        self.m.run("SHL_queue_front_check")
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.160"), 1)
        self.assertEqual(self.m.event_days["ADISCORD_SHL.160"], 1)
        self.m.execute(block(self.events["ADISCORD_SHL.160"], "immediate"), "SHL")
        self.assertNotIn("SHL_front_check_pending", self.m.flags["SHL"])
        self.assertEqual(self.m.missions, {"SHL_kyz_front_hold"})
        self.hold(("280",), "VAL")
        self.m.run("SHL_front_check")
        self.assertEqual(self.m.missions, set())
        self.hold(("280", "284", "287"), "KYZ")
        self.m.run("SHL_front_check")
        self.assertEqual(self.m.missions, {"SHL_kyz_front_lost"})
        self.hold(("287",), "VAL")
        self.m.run("SHL_front_check")
        self.assertEqual(self.m.missions, set())

    def test_hold_timeout_resolves_only_while_holding(self):
        for war, mission, objectives, report in (
            ("qanat", "SHL_kyz_front_hold", ("280", "284"), "ADISCORD_SHL.57"),
            ("ration", "SHL_kyz_front_hold", ("280", "284"), "ADISCORD_SHL.73"),
            ("port", "SHL_glp_front_hold", ("297", "299"), "ADISCORD_SHL.66"),
        ):
            with self.subTest(war=war):
                self.setUp()
                self.start(war)
                self.hold(objectives, "SHL")
                self.m.run("SHL_front_check")
                self.assertIn(mission, self.m.missions)
                enemy = "GLP" if war == "port" else "KYZ"
                self.hold(objectives[:1], enemy)
                self.timeout(mission)
                self.assertNotIn(report, self.m.scheduled)
                self.assertTrue(self.holds("SHL_limited_war_active"))
                self.hold(objectives, "SHL")
                self.timeout(mission)
                self.timeout(mission)
                self.assertEqual(self.m.scheduled.count(report), 1)
                # The report's answer pulls the deadline, after its tooltip has shown the old date.
                self.assertNotIn(("ADISCORD_south_pull_clock_war", "SHL"), self.m.calls)
                self.answer(report, 0, "SHL")
                self.assertEqual(self.m.calls.count(("ADISCORD_south_pull_clock_war", "SHL")), 1)
                self.assertFalse(self.holds("SHL_limited_war_active"))
                self.assertEqual(self.m.missions, set())
                self.assertNotIn("ADISCORD_SHL.161", self.m.scheduled)

    def test_enemy_hold_sends_terms_and_records_capped_candidates(self):
        cases = (
            ("qanat", False, "SHL_kyz_front_lost", "KYZ", ("287", "289"), {"287"}, 1),
            ("qanat", True, "SHL_kyz_front_lost", "KYZ", ("287", "289"), set(), 1),
            ("ration", False, "SHL_kyz_front_lost", "KYZ", ("707", "289", "288"), {"707", "289"}, 2),
            ("ration", True, "SHL_kyz_front_lost", "KYZ", ("707", "289"), {"707"}, 2),
            ("port", False, "SHL_glp_front_lost", "GLP", ("296", "733", "293", "295"), {"296", "733", "295"}, 3),
            ("port", True, "SHL_glp_front_lost", "GLP", ("296", "293"), {"296"}, 3),
        )
        for war, garrisons, mission, enemy, taken, candidates, code in cases:
            with self.subTest(war=war, garrisons=garrisons):
                self.setUp()
                if garrisons:
                    self.m.focuses.add("SHL_furnace_garrisons")
                self.start(war)
                self.hold(taken, enemy)
                self.m.run("SHL_front_check")
                self.assertIn(mission, self.m.missions)
                pressure = self.country()["SHL_house_pressure"]
                self.timeout(mission)
                self.assertFalse(self.holds("SHL_limited_war_active"))
                self.assertEqual(self.country()["SHL_terms_war"], code)
                self.assertIn("SHL_terms_pending", self.m.flags["SHL"])
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.161"), 1)
                flagged = {state for state in ("287", "288", "289", "293", "295", "296", "707", "733")
                           if "SHL_terms_candidate" in self.m.flags[state]}
                self.assertEqual(flagged, candidates)
                self.assertGreater(self.country()["SHL_house_pressure"], pressure)
                self.assertNotIn(("ADISCORD_south_pull_clock_war", "SHL"), self.m.calls)
                self.assertFalse(self.m.wars)

    def test_terms_answers_settle_once_and_clear_candidates(self):
        for index, war in ((0, "qanat"), (1, "qanat"), (2, "qanat"), (1, "ration"), (2, "port")):
            with self.subTest(index=index, war=war):
                self.setUp()
                self.start(war)
                enemy = "GLP" if war == "port" else "KYZ"
                taken = {"qanat": ("287", "289"), "ration": ("707", "288"), "port": ("296", "295")}[war]
                self.hold(taken, enemy)
                self.timeout("SHL_glp_front_lost" if war == "port" else "SHL_kyz_front_lost")
                self.answer("ADISCORD_SHL.161", index, enemy)
                self.answer("ADISCORD_SHL.161", index, enemy)
                c = self.country()
                self.assertEqual(c["SHL_last_terms"], index + 1)
                self.assertNotIn("SHL_terms_war", c)
                self.assertNotIn("SHL_terms_pending", self.m.flags["SHL"])
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.162"), 1)
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL_news.10"), 1)
                for state in ("287", "288", "289", "293", "295", "296", "707", "733"):
                    self.assertNotIn("SHL_terms_candidate", self.m.flags[state])
                if index == 0:
                    self.assertEqual((c["SHL_indemnity_due"], c["SHL_indemnity_recipient"]), (240, 1))
                elif index == 1:
                    # One furnace at most: Arbin in the qanat war, Safir beside Zarkhan in the ration war.
                    for ceded in {"qanat": ("287",), "ration": ("707", "288")}[war]:
                        self.assertEqual(self.m.ownership[ceded], "KYZ")
                        self.assertIn("SHL_ceded_state", self.m.flags[ceded])
                    self.assertEqual(self.m.ownership["289"], "SHL")
                elif war == "qanat":
                    self.assertIn("SHL_neutral_to_KYZ", self.m.flags["SHL"])
                    self.assertEqual(c["SHL_water_quota"], 1)
                    self.assertEqual(c["SHL_water_crisis"], 2)
                else:
                    self.assertIn("SHL_neutral_to_GLP", self.m.flags["SHL"])
                    self.assertIn("SHL_veyr_bondage", self.m.ideas)
        # The tithe is not offered while another indemnity is still paid.
        self.country()["SHL_indemnity_due"] = 10
        tithe = block(self.options("ADISCORD_SHL.161")[0], "trigger")
        self.assertFalse(self.m.matches(tithe, "GLP"))

    def test_ration_tithe_is_larger_and_neutrality_pauses_both_disputes(self):
        self.start("ration")
        self.hold(("707", "288"), "KYZ")
        self.timeout("SHL_kyz_front_lost")
        self.assertEqual(self.country()["SHL_kyz_outcome"], 4)
        self.answer("ADISCORD_SHL.161", 0, "KYZ")
        self.assertEqual(self.country()["SHL_indemnity_due"], 320)
        self.m.flags["SHL"].add("SHL_neutral_to_KYZ")
        self.assertFalse(self.holds("SHL_keizan_can_threaten"))
        self.setUp()
        c = self.country()
        c["SHL_water_crisis"] = 1
        c["SHL_veyr_crisis"] = 1
        self.m.focuses.update({"SHL_qanat_guard", "SHL_veyr_ultimatum"})
        self.assertTrue(self.holds("SHL_can_seize_qanats"))
        self.assertTrue(self.holds("SHL_can_strike_veyr"))
        self.m.flags["SHL"].update({"SHL_neutral_to_KYZ", "SHL_neutral_to_GLP"})
        self.assertFalse(self.holds("SHL_can_seize_qanats"))
        self.assertFalse(self.holds("SHL_can_strike_veyr"))

    def test_indemnity_is_paid_per_lit_furnace_and_never_overpaid(self):
        c = self.country()
        self.m.variables["KYZ"]["ADISCORD_economy_treasury"] = 0.0
        c.update({"SHL_indemnity_due": 30.0, "SHL_indemnity_recipient": 1.0, "SHL_last_cycle_income": 0.0})
        self.m.run("SHL_pay_indemnity")
        self.assertEqual(c["ADISCORD_economy_treasury"], 970)
        self.assertEqual(self.m.variables["KYZ"]["ADISCORD_economy_treasury"], 30)
        self.assertEqual(c["SHL_last_cycle_income"], -30)
        self.assertNotIn("SHL_indemnity_due", c)
        self.assertNotIn("SHL_indemnity_recipient", c)
        for office in (False, True):
            with self.subTest(office=office):
                self.setUp()
                c = self.country()
                if office:
                    self.m.focuses.add("SHL_border_settlement_office")
                c.update({"SHL_indemnity_due": 240.0, "SHL_indemnity_recipient": 1.0})
                self.m.control["287"] = "KYZ"
                self.m.variables["288"]["SHL_furnace_running"] = 0.0
                pressure = c["SHL_house_pressure"]
                self.m.run("SHL_pay_indemnity")
                self.assertEqual(c["ADISCORD_economy_treasury"], 1000 - 56)
                self.assertEqual(c["SHL_indemnity_due"], 184)
                self.assertEqual(c["SHL_house_pressure"], pressure + (0 if office else 2))
        self.m.wars.add(frozenset(("SHL", "KYZ")))
        self.m.run("SHL_pay_indemnity")
        self.assertEqual(c["SHL_indemnity_due"], 184)
        self.assertEqual(c["ADISCORD_economy_treasury"], 1000 - 56)
        self.m.wars.clear()
        self.m.countries["KYZ"]["exists"] = False
        self.m.run("SHL_pay_indemnity")
        self.assertNotIn("SHL_indemnity_due", c)
        self.assertEqual(c["ADISCORD_economy_treasury"], 1000 - 56)

    def test_indemnity_buyout_debits_both_currencies_once(self):
        c = self.country()
        decision = furnaces.decision_definition("SHL_settle_indemnity")
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual(scalar(decision, "custom_cost_text"), "SHL_cost_indemnity")
        c.update({"SHL_indemnity_due": 184.0, "SHL_indemnity_recipient": 2.0})
        self.m.variables["GLP"]["ADISCORD_economy_treasury"] = 0.0
        c["ADISCORD_economy_treasury"] = 183.99
        self.assertFalse(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"))
        self.m.run("SHL_buy_out_indemnity")
        self.assertEqual(c["SHL_indemnity_due"], 184)
        c["ADISCORD_economy_treasury"] = 184.0
        self.assertTrue(self.m.matches(block(decision, "custom_cost_trigger"), "SHL"))
        self.m.run("SHL_buy_out_indemnity")
        self.m.run("SHL_buy_out_indemnity")
        self.assertEqual(c["ADISCORD_economy_treasury"], 0)
        self.assertEqual(self.m.values["political_power"], 175)
        self.assertEqual(self.m.variables["GLP"]["ADISCORD_economy_treasury"], 184)
        self.assertNotIn("SHL_indemnity_due", c)

    def test_armistice_grades_follow_holdings_and_repelled_news_needs_zarkhan(self):
        for name, garrisons, held, grade, owners, outcome, news in (
            ("ahead", False, {"280": "SHL"}, 1, {"280": "SHL", "284": "KYZ", "707": "SHL"}, 5, True),
            ("behind", False, {"707": "KYZ", "287": "KYZ"}, 3, {"707": "KYZ", "287": "KYZ", "280": "KYZ"}, 4, False),
            ("even", False, {"280": "SHL", "707": "KYZ"}, 2, {"280": "KYZ", "707": "SHL"}, 5, True),
            ("garrisons", True, {"707": "KYZ", "287": "KYZ"}, 3, {"707": "KYZ", "287": "SHL"}, 4, False),
        ):
            with self.subTest(case=name):
                self.setUp()
                if garrisons:
                    self.m.focuses.add("SHL_furnace_garrisons")
                self.start("ration")
                for state, holder in held.items():
                    self.m.control[state] = holder
                event = self.events["ADISCORD_SHL.72"]
                self.m.execute(block(event, "immediate"), "SHL")
                self.assertEqual(self.country()["SHL_kyz_armistice_grade"], grade)
                matching = [o for o in self.options("ADISCORD_SHL.72") if self.m.matches(block(o, "trigger"), "SHL")]
                self.assertEqual(len(matching), 1)
                self.m.execute(block(matching[0], "hidden_effect"), "SHL")
                for state, owner in owners.items():
                    self.assertEqual(self.m.ownership[state], owner, state)
                self.assertEqual(self.country()["SHL_kyz_outcome"], outcome)
                self.assertEqual("ADISCORD_SHL_news.8" in self.m.scheduled, news)
                self.assertEqual("SHL_revanche_due_KYZ" in self.m.flags["SHL"], grade == 1)
                self.assertNotIn("SHL_kyz_armistice_grade", self.country())
                for state in ("280", "284", "707", "287", "288", "289"):
                    self.assertNotIn("SHL_armistice_held", self.m.flags[state])
                self.assertFalse(self.m.wars)

    def test_qanat_and_port_armistice_transfer_what_each_side_holds(self):
        self.start("qanat")
        self.hold(("280", "285"), "SHL")
        self.m.execute(block(self.events["ADISCORD_SHL.56"], "immediate"), "SHL")
        self.m.run("SHL_qanat_war_armistice")
        self.assertEqual((self.m.ownership["280"], self.m.ownership["285"], self.m.ownership["284"]), ("SHL", "SHL", "KYZ"))
        self.assertEqual(self.m.event_days["ADISCORD_SHL.76"], 365)
        self.setUp()
        self.start("port")
        self.hold(("296", "293", "295"), "GLP")
        self.m.execute(block(self.events["ADISCORD_SHL.65"], "immediate"), "SHL")
        self.assertEqual(self.country()["SHL_glp_armistice_grade"], 3)
        self.m.run("SHL_glp_war_armistice")
        self.assertEqual((self.m.ownership["296"], self.m.ownership["295"], self.m.ownership["293"]), ("GLP", "GLP", "SHL"))
        self.assertNotIn("ADISCORD_SHL.76", self.m.scheduled)

    def test_repeat_qanat_war_is_fought_over_keizan_land(self):
        # A grade-1 armistice left both head wells with Shahrabad and the dispute open.
        for state in ("280", "284"):
            self.m.ownership[state] = "SHL"
            self.m.control[state] = "SHL"
        self.start("qanat")
        for name in FRONT_PREDICATES:
            self.assertFalse(self.holds(name), name)
        self.hold(("285",), "SHL")
        self.assertFalse(self.holds("SHL_kyz_front_ours"))
        self.hold(("286",), "SHL")
        self.assertTrue(self.holds("SHL_kyz_front_ours"))
        self.hold(("285", "286", "287"), "KYZ")
        self.assertTrue(self.holds("SHL_kyz_front_theirs"))
        self.hold(("286",), "SHL")
        self.assertFalse(self.holds("SHL_kyz_front_theirs"))
        for state in ("285", "286"):
            self.assertTrue(self.holds("SHL_limited_war_objective_state", state), state)
        # One head well left with Keizan: that well and the other slot's lower qanat.
        self.setUp()
        self.m.ownership["280"] = "SHL"
        self.m.control["280"] = "SHL"
        self.start("qanat")
        self.assertFalse(self.holds("SHL_kyz_front_ours"))
        self.hold(("284",), "SHL")
        self.assertFalse(self.holds("SHL_kyz_front_ours"))
        self.hold(("285",), "SHL")
        self.assertTrue(self.holds("SHL_kyz_front_ours"))

    def test_lost_border_war_pauses_the_dispute_for_a_year(self):
        for war, enemy, taken, truce, dispute, decision in (
            ("qanat", "KYZ", ("287", "289"), "SHL_border_truce_KYZ", "SHL_qanat_dispute_open", "SHL_can_seize_qanats"),
            ("port", "GLP", ("296", "295"), "SHL_border_truce_GLP", "SHL_veyr_dispute_open", "SHL_can_strike_veyr"),
        ):
            for index in range(3):
                with self.subTest(war=war, answer=index):
                    self.setUp()
                    self.start(war)
                    self.hold(taken, enemy)
                    self.timeout("SHL_glp_front_lost" if war == "port" else "SHL_kyz_front_lost")
                    self.answer("ADISCORD_SHL.161", index, enemy)
                    self.assertIn(truce, self.m.flags["SHL"])
                    self.assertFalse(self.holds(dispute))
                    self.assertFalse(self.holds(decision))
                    # The treaty answer keeps its own two-year pause after the truce lapses.
                    self.m.flags["SHL"].discard(truce)
                    self.assertEqual(self.holds(decision), index != 2)
        for effect, truce in (("SHL_qanat_war_lost", "SHL_border_truce_KYZ"), ("SHL_kyz_war_lost", "SHL_border_truce_KYZ"),
                              ("SHL_glp_war_lost", "SHL_border_truce_GLP")):
            flags = [e for e in walk(self.effects[effect]) if e.key == "set_country_flag" and isinstance(e.value, list)]
            self.assertIn((truce, "365"), [(scalar(e.value, "flag"), scalar(e.value, "days")) for e in flags], effect)

    def test_redemption_refunds_when_the_neighbour_has_nothing_to_return(self):
        c = self.country()
        self.m.ownership["287"] = "KYZ"
        self.m.control["287"] = "KYZ"
        self.m.flags["287"].add("SHL_ceded_state")
        self.m.flag_days["287"]["SHL_ceded_state"] = 365
        self.m.variables["KYZ"]["ADISCORD_economy_treasury"] = 0.0
        self.m.run("SHL_pick_return_neighbour")
        self.m.run("SHL_offer_redemption")
        self.assertEqual((c["ADISCORD_economy_treasury"], self.m.values["political_power"]), (750, 175))
        self.assertTrue(self.holds("SHL_redemption_deliverable"))
        self.m.ownership["287"] = "VAL"
        self.m.control["287"] = "VAL"
        self.assertFalse(self.holds("SHL_redemption_deliverable"))
        self.answer("ADISCORD_SHL.164", 0, "KYZ")
        self.answer("ADISCORD_SHL.164", 0, "KYZ")
        self.assertEqual(self.m.variables["KYZ"]["ADISCORD_economy_treasury"], 0)
        self.assertEqual((c["ADISCORD_economy_treasury"], self.m.values["political_power"]), (1000, 200))
        for name in ("SHL_redemption_deposit", "SHL_redemption_pp", "SHL_return_neighbour"):
            self.assertNotIn(name, c)
        self.assertNotIn("SHL_redemption_pending", self.m.flags["SHL"])
        self.assertNotIn("ADISCORD_SHL.165", self.m.scheduled)
        self.assertEqual(self.m.ownership["287"], "VAL")

    def test_border_war_preparation_follows_the_dispute_gates(self):
        profiles = {e.key: e.value for e in parse_clausewitz(SHL_AI_PATH.read_text(encoding="utf-8"))}
        for name, dispute, truce in (
            ("ADISCORD_SHL_prepare_against_KYZ", "SHL_qanat_dispute_open", "SHL_neutral_to_KYZ"),
            ("ADISCORD_KYZ_prepare_against_SHL", "SHL_qanat_dispute_open", "SHL_neutral_to_KYZ"),
            ("ADISCORD_SHL_prepare_against_GLP", "SHL_veyr_dispute_open", "SHL_neutral_to_GLP"),
            ("ADISCORD_GLP_prepare_against_SHL", "SHL_veyr_dispute_open", "SHL_neutral_to_GLP"),
        ):
            enable = list(walk(block(profiles[name], "enable")))
            self.assertIn((dispute, "yes"), [(e.key, e.value) for e in enable], name)
            self.assertIn(("has_country_flag", truce), [(e.key, e.value) for e in enable], name)
            self.assertNotIn("SHL_water_crisis", [scalar(e.value, "var") for e in enable if e.key == "check_variable"], name)
            self.assertNotIn("SHL_veyr_crisis", [scalar(e.value, "var") for e in enable if e.key == "check_variable"], name)

    def test_front_battery_escrow_delivers_once_and_refunds_on_loss(self):
        decision = furnaces.decision_definition("SHL_front_battery")
        self.assertIn(("has_completed_focus", "SHL_border_foundries"), [(e.key, e.value) for e in block(decision, "visible")])
        self.assertEqual((scalar(decision, "cost"), scalar(decision, "custom_cost_text"), scalar(decision, "days_remove")),
                         ("0", "SHL_cost_front_battery", "14"))
        for founders in (False, True):
            with self.subTest(founders=founders):
                self.setUp()
                c = self.country()
                if founders:
                    self.m.focuses.add("SHL_siege_founders")
                self.start("qanat")
                for state in ("280", "286"):
                    self.m.state_buildings[(state, "infrastructure")] = 2
                    self.m.state_buildings[(state, "arms_factory")] = 1
                c["ADISCORD_economy_treasury"] = 99.99
                self.m.run("SHL_begin_front_battery", target="287")
                self.assertNotIn("SHL_operation", self.m.variables["287"])
                c["ADISCORD_economy_treasury"] = 1000.0
                self.m.run("SHL_begin_front_battery", target="287")
                self.m.run("SHL_begin_front_battery", target="287")
                self.assertEqual(c["ADISCORD_economy_treasury"], 900)
                self.assertEqual(self.m.values["political_power"], 180)
                self.assertEqual(self.m.variables["287"]["SHL_operation"], 13)
                self.m.run("SHL_finish_front_battery", target="287")
                self.m.run("SHL_finish_front_battery", target="287")
                self.assertEqual(self.m.equipment[("SHL", "artillery_equipment")], 48 if founders else 36)
                self.assertEqual(self.m.variables["287"]["SHL_furnace_wear"], 30)
                self.assertNotIn("SHL_operation_deposit", self.m.variables["287"])
                hits = [call for call in self.m.calls if call[0] == "damage_building"]
                self.assertEqual(sorted(hits), sorted([("damage_building", "280"), ("damage_building", "286")] * (2 if founders else 1)))
        # A lost site refunds the escrow and delivers nothing; occupied enemy land is not shelled.
        self.setUp()
        c = self.country()
        self.start("qanat")
        self.m.run("SHL_begin_front_battery", target="289")
        self.m.control["289"] = "KYZ"
        self.m.run("SHL_finish_front_battery", target="289")
        self.assertEqual((c["ADISCORD_economy_treasury"], self.m.values["political_power"]), (1000, 200))
        self.assertEqual(self.m.equipment[("SHL", "artillery_equipment")], 0)
        self.assertNotIn("SHL_operation", self.m.variables["289"])
        self.m.control["289"] = "SHL"
        self.m.state_buildings[("284", "infrastructure")] = 2
        self.m.control["284"] = "SHL"
        self.m.run("SHL_begin_front_battery", target="289")
        self.m.run("SHL_finish_front_battery", target="289")
        self.assertNotIn(("damage_building", "284"), self.m.calls)

    def test_front_battery_sites_follow_the_running_border_war(self):
        self.start("qanat")
        for state, allowed in (("287", True), ("288", True), ("289", True), ("293", False), ("295", False)):
            self.assertEqual(self.holds("SHL_front_battery_site", state), allowed, state)
        self.setUp()
        self.start("port")
        for state, allowed in (("287", False), ("293", True), ("295", True)):
            self.assertEqual(self.holds("SHL_front_battery_site", state), allowed, state)

    def test_return_redemption_escrow_and_refusal_reopens_war_route(self):
        def ceded(age, office=False):
            self.setUp()
            if office:
                self.m.focuses.add("SHL_border_settlement_office")
            self.m.ownership["287"] = "KYZ"
            self.m.control["287"] = "KYZ"
            self.m.flags["287"].add("SHL_ceded_state")
            self.m.flag_days["287"]["SHL_ceded_state"] = age

        ceded(200)
        self.assertFalse(self.holds("SHL_return_offer_ready"))
        ceded(200, office=True)
        self.assertTrue(self.holds("SHL_return_offer_ready"))
        self.m.run("SHL_pick_return_neighbour")
        self.m.run("SHL_offer_redemption")
        self.assertEqual(self.country()["SHL_redemption_deposit"], 200)
        ceded(365)
        c = self.country()
        self.assertTrue(self.holds("SHL_return_offer_ready"))
        self.m.execute(block(self.events["ADISCORD_SHL.163"], "immediate"), "SHL")
        self.assertEqual(c["SHL_return_neighbour"], 1)
        self.m.run("SHL_offer_redemption")
        self.m.run("SHL_offer_redemption")
        self.assertEqual((c["ADISCORD_economy_treasury"], self.m.values["political_power"]), (750, 175))
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.164"), 1)
        self.assertFalse(self.holds("SHL_return_offer_ready"))
        self.answer("ADISCORD_SHL.164", 1, "KYZ")
        self.answer("ADISCORD_SHL.164", 1, "KYZ")
        self.assertEqual((c["ADISCORD_economy_treasury"], self.m.values["political_power"]), (1000, 200))
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.166"), 1)
        self.assertTrue(self.holds("SHL_qanat_dispute_open"))
        self.assertFalse(self.holds("SHL_return_offer_ready"))
        self.assertEqual(self.m.ownership["287"], "KYZ")
        # Acceptance moves the deposit and the district together, once.
        ceded(365)
        c = self.country()
        self.m.variables["KYZ"]["ADISCORD_economy_treasury"] = 0.0
        self.m.run("SHL_pick_return_neighbour")
        self.m.run("SHL_offer_redemption")
        self.answer("ADISCORD_SHL.164", 0, "KYZ")
        self.answer("ADISCORD_SHL.164", 0, "KYZ")
        self.assertEqual(self.m.variables["KYZ"]["ADISCORD_economy_treasury"], 250)
        self.assertEqual(c["ADISCORD_economy_treasury"], 750)
        self.assertEqual(self.m.ownership["287"], "SHL")
        self.assertNotIn("SHL_ceded_state", self.m.flags["287"])
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.165"), 1)
        # An unanswered offer is refunded after its pending flag lapses.
        ceded(365)
        c = self.country()
        self.m.run("SHL_pick_return_neighbour")
        self.m.run("SHL_offer_redemption")
        self.m.flags["SHL"].discard("SHL_redemption_pending")
        self.m.run("SHL_expire_border_offers")
        self.assertEqual((c["ADISCORD_economy_treasury"], self.m.values["political_power"]), (1000, 200))
        self.assertNotIn("SHL_redemption_deposit", c)
        # Accepting the border drops only that neighbour's claim.
        ceded(365)
        self.m.run("SHL_pick_return_neighbour")
        self.answer("ADISCORD_SHL.163", 0, "SHL")
        self.assertNotIn("SHL_ceded_state", self.m.flags["287"])
        self.assertFalse(self.holds("SHL_return_offer_ready"))

    def test_recovered_district_drops_its_old_claim(self):
        self.m.flags["288"].add("SHL_ceded_state")
        self.m.flag_days["288"]["SHL_ceded_state"] = 400
        self.m.run("SHL_expire_border_offers")
        self.assertNotIn("SHL_ceded_state", self.m.flags["288"])

    def test_victory_recovers_ceded_cores(self):
        for war, state, enemy in (("qanat", "287", "KYZ"), ("port", "296", "GLP"), ("ration", "707", "KYZ")):
            with self.subTest(war=war):
                self.setUp()
                if war != "ration":
                    self.m.ownership[state] = enemy
                    self.m.control[state] = enemy
                    self.m.flags[state].add("SHL_ceded_state")
                self.start(war)
                if war == "ration":
                    self.m.ownership["288"] = "KYZ"
                    self.m.flags["288"].add("SHL_ceded_state")
                    state = "288"
                self.m.run({"qanat": "SHL_qanat_war_victory", "port": "SHL_glp_war_victory",
                            "ration": "SHL_kyz_war_victory"}[war])
                self.assertEqual(self.m.ownership[state], "SHL")
                self.assertNotIn("SHL_ceded_state", self.m.flags[state])

    def test_winner_alternatives_hand_the_objectives_back_for_peace(self):
        self.start("qanat")
        self.m.run("SHL_qanat_war_victory")
        option = self.options("ADISCORD_SHL.57")[1]
        self.assertTrue(self.m.matches(block(option, "trigger"), "SHL"))
        self.m.execute(block(option, "hidden_effect"), "SHL")
        for state in ("280", "284", "285", "286"):
            self.assertEqual(self.m.ownership[state], "KYZ")
        self.assertEqual(self.country()["SHL_water_crisis"], 5)
        self.assertIn("SHL_neutral_to_KYZ", self.m.flags["SHL"])
        self.assertNotIn("SHL_revanche_due_KYZ", self.m.flags["SHL"])
        self.assertNotIn("SHL_captured_qanats", self.m.ideas)
        self.setUp()
        self.start("port", sea=True)
        self.m.run("SHL_glp_war_victory")
        option = self.options("ADISCORD_SHL.66")[1]
        self.assertTrue(self.m.matches(block(option, "trigger"), "SHL"))
        self.m.execute(block(option, "hidden_effect"), "SHL")
        for state in ("297", "298", "299", "708"):
            self.assertEqual(self.m.ownership[state], "GLP")
        self.assertIn("SHL_veyr_partner", self.m.flags["SHL"])
        self.assertEqual(self.country()["SHL_veyr_crisis"], 2)
        self.assertNotIn("SHL_revanche_due_GLP", self.m.flags["SHL"])
        for event_id in ("ADISCORD_SHL.57", "ADISCORD_SHL.66", "ADISCORD_SHL.73"):
            for option in self.options(event_id):
                self.assertEqual(scalar(option, "custom_effect_tooltip"), "ADISCORD_south_clock_pull_war_tt", event_id)
                self.assertEqual(scalar(block(option, "hidden_effect"), "ADISCORD_south_pull_clock_war"), "yes", event_id)

    def test_close_effects_zero_guard_before_white_peace_and_clear_front_state(self):
        for name, variable, clear in (("SHL_close_qanat_war", "SHL_war_kyz", "SHL_front_clear_kyz"),
                                      ("SHL_close_kyz_war", "SHL_war_kyz", "SHL_front_clear_kyz"),
                                      ("SHL_close_glp_war", "SHL_war_glp", "SHL_front_clear_glp")):
            body = self.effects[name]
            self.assertEqual((body[0].key, scalar(body[0].value, "var"), scalar(body[0].value, "value")),
                             ("set_variable", variable, "0"), name)
            self.assertIn(clear, [e.key for e in body], name)
        source = PEACE_ON_ACTIONS_PATH.read_text(encoding="utf-8")
        for hook in ("on_peace", "on_puppet", "on_annex"):
            section = source.split(f"# BEGIN shahrabad:{hook}", 1)[1].split(f"# END shahrabad:{hook}", 1)[0]
            for war in ("kyz", "glp"):
                self.assertEqual(section.count(f"SHL = {{ SHL_close_external_{war}_war = yes }}"), 1, (hook, war))
        for war, enemy, missions in (("qanat", "KYZ", ("SHL_kyz_front_hold",)), ("port", "GLP", ("SHL_glp_front_lost",))):
            with self.subTest(war=war):
                self.setUp()
                self.start(war, sea=True)
                self.m.missions.update(missions)
                self.m.flags["280" if war == "qanat" else "297"].add("SHL_armistice_held")
                self.m.countries[enemy]["is_subject"] = True
                self.m.run("SHL_close_external_kyz_war")
                self.m.run("SHL_close_external_glp_war")
                self.assertFalse(self.holds("SHL_limited_war_active"))
                self.assertFalse(self.m.wars)
                self.assertEqual(self.m.missions, set())
                self.assertNotIn("SHL_armistice_held", self.m.flags["280" if war == "qanat" else "297"])
                self.assertNotIn("SHL_war_glp_sea_goal", self.m.flags["SHL"])
        # A neighbour that only disappears leaves the other war untouched.
        self.setUp()
        self.start("port")
        self.m.countries["KYZ"]["exists"] = False
        self.m.run("SHL_close_external_kyz_war")
        self.m.run("SHL_close_external_glp_war")
        self.assertTrue(self.holds("SHL_limited_war_active"))

    def test_annexation_clears_terms_indemnity_and_redemption(self):
        c = self.country()
        c.update({"SHL_indemnity_due": 50.0, "SHL_indemnity_recipient": 1.0, "SHL_terms_war": 1.0,
                  "SHL_redemption_deposit": 250.0, "SHL_redemption_pp": 25.0, "SHL_return_neighbour": 1.0})
        self.m.flags["SHL"].update({"SHL_terms_pending", "SHL_redemption_pending"})
        self.m.flags["287"].add("SHL_terms_candidate")
        self.m.run("SHL_abort_annexed_operations")
        for name in ("SHL_indemnity_due", "SHL_indemnity_recipient", "SHL_terms_war", "SHL_redemption_deposit",
                     "SHL_redemption_pp", "SHL_return_neighbour"):
            self.assertNotIn(name, c)
        self.assertFalse(self.m.flags["SHL"] & {"SHL_terms_pending", "SHL_redemption_pending"})
        self.assertNotIn("SHL_terms_candidate", self.m.flags["287"])

    def test_front_routing_missions_tokens_and_ai_profiles(self):
        self.assertIn("SHL = { SHL_queue_front_check = yes }", SHL_ON_ACTIONS_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("SHL_queue_front_check", PEACE_ON_ACTIONS_PATH.read_text(encoding="utf-8"))
        tokens = TOKENS_PATH.read_text(encoding="utf-8").split()
        resolvers = {"SHL_kyz_front_hold": "SHL_resolve_kyz_hold", "SHL_kyz_front_lost": "SHL_resolve_kyz_loss",
                     "SHL_glp_front_hold": "SHL_resolve_glp_hold", "SHL_glp_front_lost": "SHL_resolve_glp_loss"}
        for mission in FRONT_MISSIONS:
            self.assertEqual(tokens.count(mission), 1, mission)
            definition = furnaces.decision_definition(mission)
            self.assertEqual([(e.key, e.value) for e in walk(block(definition, "available"))],
                             [("hidden_trigger", block(block(definition, "available"), "hidden_trigger")), ("always", "no")])
            self.assertEqual((scalar(definition, "days_mission_timeout"), scalar(definition, "selectable_mission")), ("14", "no"))
            self.assertEqual(scalar(block(block(definition, "timeout_effect"), "hidden_effect"), resolvers[mission]), "yes")
        self.assertNotIn("SHL_secure_cistern_corridor", DECISIONS_PATH.read_text(encoding="utf-8"))
        profiles = {e.key: e.value for e in parse_clausewitz(SHL_AI_PATH.read_text(encoding="utf-8"))}
        for name, variable in (("ADISCORD_SHL_limited_front_kyz", "SHL_war_kyz"), ("ADISCORD_SHL_limited_front_glp", "SHL_war_glp"),
                               ("ADISCORD_KYZ_limited_front_shl", "SHL_war_kyz"), ("ADISCORD_GLP_limited_front_shl", "SHL_war_glp"),
                               ("ADISCORD_SHL_kyz_partner_front", "SHL_war_kyz")):
            enable = list(walk(block(profiles[name], "enable")))
            self.assertIn(variable, [scalar(e.value, "var") for e in enable if e.key == "check_variable"], name)
        for name in ("ADISCORD_SHL_prepare_against_KYZ", "ADISCORD_KYZ_prepare_against_SHL",
                     "ADISCORD_SHL_prepare_against_GLP", "ADISCORD_GLP_prepare_against_SHL"):
            self.assertIn(name, profiles)

    def test_focus_refresh_event_runs_after_the_reward_has_completed(self):
        self.m.run("SHL_queue_focus_refresh")
        self.assertEqual(self.m.scheduled, ["ADISCORD_SHL.167"])
        call = block(self.effects["SHL_queue_focus_refresh"], "country_event")
        self.assertEqual(scalar(call, "hours"), "1")
        event = self.events["ADISCORD_SHL.167"]
        self.assertEqual((scalar(event, "hidden"), scalar(event, "is_triggered_only")), ("yes", "yes"))
        self.assertEqual([(e.key, e.value) for e in block(event, "immediate")], [("SHL_refresh_furnaces", "yes")])
        self.m.focuses.add("SHL_desert_guard_contracts")
        self.m.execute(block(event, "immediate"), "SHL")
        self.assertEqual(self.country()["SHL_guard_price"], 240)
        registry = {entry["id"]: entry for entry in json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["events"]}
        for number in range(160, 168):
            self.assertEqual(registry[f"ADISCORD_SHL.{number}"]["owner"], "events/ADISCORD_SHL_events.txt")
            self.assertIn(f"ADISCORD_SHL.{number}", self.events)
        self.assertIn("ADISCORD_SHL_news.10", registry)
        news = self.events["ADISCORD_SHL_news.10"]
        self.assertEqual([(e.key, e.value) for e in block(news, "show_major")], [("SHL_southern_news_reader", "yes")])


# Defeat chapter: leased districts under each autonomy state of the settlement.
SEAL_TERMS = {
    "autonomy_NAM_economic_contract": ({"288", "291", "293"}, 0.40, 240),
    "autonomy_NAM_oil_charter": ({"287", "288", "291", "293"}, 0.50, 300),
    "autonomy_puppet": ({"287", "288", "290", "291", "293", "295"}, 0.65, 360),
    "autonomy_NAM_namestnik_office": ({str(state) for state in range(287, 296)}, 0.80, 420),
}
SEAL_PEACE_SECTIONS = ("on_capitulation", "on_peace")


class SealMachine(furnaces.ScriptMachine):
    """The furnace machine plus the subject, war and faction effects of the defeat chapter."""

    SPECIAL = {
        "set_autonomy", "puppet", "end_puppet", "leave_faction", "every_enemy_country",
        "every_owned_state", "white_peace", "create_faction_from_template", "remove_dynamic_modifier",
    }

    def __init__(self, effects, triggers):
        super().__init__(effects, triggers)
        self.autonomy = {}
        self.countries["SHL"] = {"exists": True, "is_subject": False, "has_war": False}

    def set_overlord(self, overlord, state=None):
        self.countries["SHL"]["subject_of"] = overlord
        self.countries["SHL"]["is_subject"] = overlord is not None
        self.autonomy["SHL"] = state

    def matches(self, items, scope, target=None):
        rest = []
        results = []
        for entry in items:
            if entry.key == "has_autonomy_state":
                results.append(self.autonomy.get(scope) == entry.value)
            else:
                rest.append(entry)
        return all(results) and super().matches(rest, scope, target)

    def execute(self, items, scope, target=None):
        chunk = []
        for entry in items:
            if entry.key not in self.SPECIAL:
                chunk.append(entry)
                continue
            if chunk:
                super().execute(chunk, scope, target)
                chunk = []
            self.special(entry, scope, target)
        if chunk:
            super().execute(chunk, scope, target)

    def special(self, entry, scope, target):
        key, value = entry.key, entry.value
        self.calls.append((key, scope))
        if key == "set_autonomy":
            self.autonomy[scalar(value, "target")] = scalar(value, "autonomy_state")
        elif key == "puppet":
            subject = scalar(value, "target")
            self.countries[subject]["subject_of"] = scope
            self.countries[subject]["is_subject"] = True
            self.autonomy[subject] = "autonomy_puppet"
        elif key == "end_puppet":
            self.countries[value]["subject_of"] = None
            self.countries[value]["is_subject"] = False
            self.autonomy.pop(value, None)
        elif key == "leave_faction":
            self.factions.pop(scope, None)
        elif key == "create_faction_from_template":
            self.factions[scope] = scope
        elif key == "remove_dynamic_modifier":
            self.dynamic.discard(scalar(value, "modifier") if isinstance(value, list) else value)
        elif key == "white_peace":
            other = self.previous_scope if value == "PREV" else value
            self.wars.discard(frozenset((scope, other)))
        elif key == "every_enemy_country":
            enemies = sorted({tag for war in self.wars if scope in war for tag in war if tag != scope})
            for enemy in enemies:
                saved = self.previous_scope
                self.previous_scope = scope
                if self.matches(block(value, "limit"), enemy, target):
                    self.execute([e for e in value if e.key != "limit"], enemy, target)
                self.previous_scope = saved
        elif key == "every_owned_state":
            for state in sorted(s for s, owner in self.ownership.items() if owner == scope):
                if self.matches(block(value, "limit"), state, target):
                    self.switch_scope([e for e in value if e.key != "limit"], state, scope, target)


class SealChapterTests(unittest.TestCase):
    """Defeat chapter: the lease, petitions, the underground and the rising."""

    @classmethod
    def setUpClass(cls):
        source = parse_clausewitz(EVENTS_PATH.read_text(encoding="utf-8"))
        cls.events = {scalar(e.value, "id"): e.value for e in source if e.key in ("country_event", "news_event")}
        cls.effect_entries = parse_clausewitz(furnaces.EFFECT_PATH.read_text(encoding="utf-8"))
        cls.trigger_entries = parse_clausewitz(furnaces.TRIGGER_PATH.read_text(encoding="utf-8"))
        peace = PEACE_ON_ACTIONS_PATH.read_text(encoding="utf-8")
        cls.peace = {
            name: parse_clausewitz(peace.split(f"# BEGIN shahrabad:{name}", 1)[1].split(f"# END shahrabad:{name}", 1)[0])
            for name in SEAL_PEACE_SECTIONS
        }

    def setUp(self, autonomy="autonomy_NAM_namestnik_office"):
        self.m = SealMachine(self.effect_entries, self.trigger_entries)
        for state in range(287, 296):
            self.m.variables[str(state)].update({
                "SHL_furnace_stock": 3.0,
                "SHL_furnace_wear": 20.0,
                "SHL_furnace_owner": 0.0,
                "SHL_furnace_running": 1.0,
                "SHL_furnace_training": 0.0,
                "SHL_furnace_recipient": 0.0,
            })
        self.m.flags["SHL"].add("SHL_furnaces_initialized")
        self.m.global_flags.add("ADISCORD_south_hegemon_NAM")
        self.c = self.m.variables["SHL"]
        self.c.update({"SHL_shift_policy": 0.0, "SHL_export_mode": 0.0, "SHL_political_course": 0.0})
        self.m.variables["NAM"]["ADISCORD_economy_treasury"] = 0.0
        self.m.run("SHL_initialize_tensions")
        self.m.set_overlord("NAM", autonomy)

    def open(self, autonomy="autonomy_NAM_namestnik_office"):
        self.setUp(autonomy)
        self.m.run("SHL_seal_open_chapter")

    def leased(self):
        return {str(s) for s in range(287, 296) if self.m.variables[str(s)]["SHL_furnace_recipient"] == 4}

    def options(self, event_id):
        return [e.value for e in self.events[event_id] if e.key == "option"]

    def answer(self, event_id, index, scope):
        self.m.execute(block(self.options(event_id)[index], "hidden_effect"), scope)

    def capitulate(self, loser, winner):
        self.m.root_scope = loser
        self.m.execute(self.peace["on_capitulation"], loser, winner)
        self.m.root_scope = "SHL"

    def test_opening_leases_by_autonomy_once(self):
        for autonomy, (sites, share, price) in SEAL_TERMS.items():
            with self.subTest(autonomy=autonomy):
                self.setUp(autonomy)
                self.c.update({"SHL_obligation_kind": 1.0, "SHL_obligation_site": 288.0})
                self.m.flags["291"].add("SHL_quota_site")
                self.m.run("SHL_seal_open_chapter")
                self.m.run("SHL_seal_open_chapter")
                self.assertEqual(self.leased(), sites)
                self.assertAlmostEqual(self.c["SHL_seal_lease_share"], share)
                self.assertAlmostEqual(self.c["SHL_seal_buyback_price"], price)
                self.assertEqual(self.c["SHL_seal_leased_count"], len(sites))
                self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.200"), 1)
                self.assertNotIn("SHL_obligation_kind", self.c)
                self.assertNotIn("SHL_quota_site", self.m.flags["291"])
        # The chapter never opens without Svetlogorye's hegemony over its subject.
        self.setUp()
        self.m.global_flags.discard("ADISCORD_south_hegemon_NAM")
        self.m.run("SHL_seal_open_chapter")
        self.assertEqual(self.leased(), set())
        self.assertNotIn("SHL_seal_chapter_open", self.m.flags["SHL"])

    def test_lease_cycle_pays_exactly_the_share_and_no_goods(self):
        self.open("autonomy_puppet")
        self.m.variables["288"]["SHL_furnace_running"] = 0.0
        treasury = self.c["ADISCORD_economy_treasury"]
        self.m.run("SHL_produce_period")
        # Five lit leased furnaces pay 60 * 0.65 each; the cold one pays nothing.
        self.assertAlmostEqual(self.m.variables["NAM"]["ADISCORD_economy_treasury"], 5 * 39)
        self.assertAlmostEqual(self.c["SHL_seal_cycle_lease"], 5 * 39)
        self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"] - treasury, 3 * 60 + 5 * 21)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 0)
        self.m.run("SHL_produce_period")
        self.assertAlmostEqual(self.c["SHL_seal_cycle_lease"], 5 * 39)
        # A leased furnace accepts no recipient, order or AI allocation.
        self.c["SHL_selected_furnace"] = 4
        self.assertFalse(self.m.matches(self.m.triggers["SHL_can_assign_delivery"], "SHL"))
        self.c["SHL_selected_furnace"] = 3
        self.assertTrue(self.m.matches(self.m.triggers["SHL_can_assign_delivery"], "SHL"))
        for trigger in ("SHL_obligation_site_ready", "SHL_war_order_site_open", "SHL_metal_export_site_free"):
            self.assertFalse(self.m.matches(self.m.triggers[trigger], "290"), trigger)
        self.m.ai = True
        self.c.update({"ADISCORD_economy_treasury": 5000.0, "SHL_unrest": 60.0})
        self.m.run("SHL_ai_allocate_deliveries")
        self.assertEqual(self.leased(), SEAL_TERMS["autonomy_puppet"][0])

    def test_petition_escrow_single_target_and_refunds(self):
        self.open()
        self.c["ADISCORD_economy_treasury"] = 1000.0
        self.m.run("SHL_seal_begin_buy_back", target="288")
        self.m.run("SHL_seal_begin_buy_back", target="289")
        self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], 580)
        self.assertAlmostEqual(self.m.values["political_power"], 175)
        self.assertEqual(self.c["SHL_seal_petition_site"], 288)
        self.assertEqual(self.m.scheduled.count("ADISCORD_SHL.202"), 1)
        # A callback for another furnace settles nothing.
        self.c["SHL_seal_petition_answer"] = 1
        self.m.run("SHL_seal_settle_petition", target="289")
        self.assertEqual(self.c["SHL_seal_petition_site"], 288)
        self.m.run("SHL_seal_settle_petition", target="288")
        self.m.run("SHL_seal_settle_petition", target="288")
        self.assertAlmostEqual(self.m.variables["NAM"]["ADISCORD_economy_treasury"], 420)
        self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], 580)
        self.assertEqual(self.m.variables["288"]["SHL_furnace_recipient"], 0)
        self.assertNotIn("SHL_seal_petition_site", self.c)
        # Refusal and a missing answer refund the price and the power once.
        for answer in (2, None):
            with self.subTest(answer=answer):
                self.open()
                self.c["ADISCORD_economy_treasury"] = 1000.0
                self.m.run("SHL_seal_begin_buy_back", target="289")
                if answer:
                    self.answer("ADISCORD_SHL.202", 1, "NAM")
                self.m.run("SHL_seal_settle_petition", target="289")
                self.m.run("SHL_seal_cancel_petition", target="289")
                self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], 1000)
                self.assertAlmostEqual(self.m.values["political_power"], 200)
                self.assertEqual("SHL_seal_petition_refused" in self.m.flags["289"], answer == 2)
                self.assertEqual(self.m.variables["289"]["SHL_furnace_recipient"], 4)
        # Independence through Svetlogorye's own decision releases the lease and the escrow.
        self.open()
        self.c["ADISCORD_economy_treasury"] = 1000.0
        self.m.run("SHL_seal_begin_buy_back", target="290")
        self.m.set_overlord(None)
        self.m.run("SHL_seal_cycle")
        self.assertAlmostEqual(self.c["ADISCORD_economy_treasury"], 1000)
        self.assertEqual(self.leased(), set())

    def test_service_counts_only_producing_cycles(self):
        self.open("autonomy_NAM_oil_charter")
        self.m.focuses.add("SHL_redeem_by_service")
        self.m.run("SHL_seal_begin_service", target="288")
        self.assertAlmostEqual(self.m.values["political_power"], 175)
        self.answer("ADISCORD_SHL.202", 0, "NAM")
        self.m.run("SHL_seal_settle_petition", target="288")
        self.assertEqual(self.m.variables["288"]["SHL_seal_service_cycles"], 4)
        paid = []
        for running in (1.0, 0.0, 1.0, 1.0, 1.0):
            for state in range(287, 296):
                self.m.variables[str(state)].update({"SHL_furnace_stock": 3.0, "SHL_furnace_wear": 20.0})
            self.m.variables["288"]["SHL_furnace_running"] = running
            before = self.m.variables["NAM"]["ADISCORD_economy_treasury"]
            self.m.run("SHL_produce_period")
            paid.append(self.m.variables["NAM"]["ADISCORD_economy_treasury"] - before)
        # Three other leased furnaces pay 30 each; furnace 288 its whole 60 while it serves.
        self.assertEqual([round(p) for p in paid], [150, 90, 150, 150, 150])
        self.assertEqual(self.m.variables["288"]["SHL_furnace_recipient"], 0)
        self.assertNotIn("SHL_seal_service_cycles", self.m.variables["288"])

    def test_last_redemption_changes_terms(self):
        for autonomy, result in (
            ("autonomy_NAM_namestnik_office", "autonomy_NAM_oil_charter"),
            ("autonomy_puppet", "autonomy_NAM_oil_charter"),
            ("autonomy_NAM_oil_charter", "autonomy_NAM_economic_contract"),
            ("autonomy_NAM_economic_contract", None),
        ):
            with self.subTest(autonomy=autonomy):
                self.open(autonomy)
                self.m.factions.update({"NAM": "NAM", "SHL": "NAM"})
                for state in self.leased():
                    self.m.run("SHL_seal_redeem_site", scope=state)
                self.m.run("SHL_seal_after_redemption")
                self.assertEqual(self.m.autonomy.get("SHL"), result)
                self.assertEqual(self.m.countries["SHL"].get("subject_of"), None if result is None else "NAM")
                self.assertEqual("SHL" in self.m.factions, result is not None)

    def test_heat_growth_clamp_and_raids(self):
        for autonomy, focuses, unrest, growth in (
            ("autonomy_NAM_namestnik_office", {"SHL_cold_ash_cells", "SHL_cold_quarter_couriers"}, 60, 7),
            ("autonomy_puppet", set(), 20, 3),
            ("autonomy_NAM_economic_contract", set(), 20, 2),
        ):
            with self.subTest(autonomy=autonomy):
                self.open(autonomy)
                self.m.focuses.update(focuses)
                self.c.update({"SHL_underground_heat": 10.0, "SHL_unrest": float(unrest)})
                self.m.run("SHL_seal_cycle")
                self.assertEqual(self.c["SHL_underground_heat"], 10 + growth)
                self.c["SHL_underground_heat"] = 98.0
                self.m.run("SHL_cold_grow_heat")
                self.assertEqual(self.c["SHL_underground_heat"], 100)
        roll = block(self.m.effects["SHL_cold_roll_raid"], "if")
        limit = block(roll, "limit")
        self.assertIn(("has_country_flag", "SHL_cold_raid_cooldown"), [(e.key, e.value) for e in block(limit, "NOT")])
        self.assertEqual([e.key for e in block(roll, "random_list")], ["85", "15"])
        raid = self.events["ADISCORD_SHL.203"]
        cooldown = block(block(block(raid, "immediate"), "hidden_effect"), "set_country_flag")
        self.assertEqual((scalar(cooldown, "flag"), scalar(cooldown, "days")), ("SHL_cold_raid_cooldown", "84"))
        self.open()
        self.c.update({"SHL_underground_heat": 50.0, "SHL_cold_cache_cells": 2.0, "SHL_cold_cache_rifles": 1000.0})
        self.answer("ADISCORD_SHL.203", 0, "SHL")
        self.assertEqual((self.c["SHL_cold_cache_cells"], self.c["SHL_cold_cache_rifles"], self.c["SHL_underground_heat"]), (1, 500, 40))
        unrest = self.c["SHL_unrest"]
        self.answer("ADISCORD_SHL.203", 1, "SHL")
        self.assertEqual((self.c["SHL_underground_heat"], self.c["SHL_unrest"]), (20, unrest + 10))

    def rise(self, pledged=("EFL",)):
        self.open()
        self.m.manpower = 4000.0
        self.c.update({"SHL_underground_heat": 85.0, "SHL_cold_cache_cells": 2.0, "SHL_cold_cache_rifles": 600.0})
        self.m.dynamic.add("SHL_cold_fire_dynamic")
        for tag in pledged:
            self.m.flags[tag].add("SHL_cold_pledged")
        self.m.run("SHL_cold_raise_rising")

    def test_rising_order_and_payload(self):
        self.rise()
        order = [call[0] if isinstance(call, tuple) else call for call in self.m.calls]
        sequence = ["end_puppet", "create_faction_from_template", "declare_war_on", "add_to_war"]
        self.assertEqual([name for name in order if name in sequence], sequence)
        self.assertEqual(self.c["SHL_cold_rising"], 1)
        self.assertIsNone(self.m.countries["SHL"]["subject_of"])
        self.assertEqual(self.leased(), set())
        self.assertIn(frozenset(("SHL", "NAM")), self.m.wars)
        self.assertIn(frozenset(("EFL", "NAM")), self.m.wars)
        self.assertEqual(self.m.factions.get("EFL"), "SHL")
        # One levy for the 3000 recruits at hand, rifles for the cell without them.
        self.assertEqual(self.m.unit_owners, [("699", "SHL")])
        self.assertEqual(self.m.manpower, 1000)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 600 + 2700)
        self.assertIn("SHL_cold_added_major", self.m.flags["SHL"])
        self.assertIn("ADISCORD_SHL_news.11", self.m.scheduled)
        # Without a pledge no coalition is formed.
        self.rise(pledged=())
        self.assertNotIn("SHL", self.m.factions)
        self.assertNotIn("create_faction_from_template", [c[0] for c in self.m.calls if isinstance(c, tuple)])

    def test_capitulation_and_external_peace_settle_once(self):
        self.rise()
        self.capitulate("EFL", "NAM")
        self.assertIn("skip_default_capitulation", self.m.global_flags)
        self.assertEqual(self.c["SHL_cold_rising"], 1)
        self.capitulate("NAM", "SHL")
        self.assertEqual(self.c["SHL_cold_rising"], 2)
        self.assertEqual(self.m.wars, set())
        self.assertNotIn("SHL_cold_fire_dynamic", self.m.dynamic)
        self.assertNotIn("SHL_underground_heat", self.c)
        self.assertNotIn("SHL_cold_added_major", self.m.flags["SHL"])
        self.assertNotIn("SHL_cold_pledged", self.m.flags["EFL"])
        self.assertNotIn("SHL", self.m.factions)
        self.capitulate("SHL", "NAM")
        self.assertEqual(self.c["SHL_cold_rising"], 2)
        # A crushed rising returns the namestnik's office and its nine leases.
        self.rise()
        self.m.control["287"] = "NAM"
        self.capitulate("SHL", "NAM")
        self.assertEqual(self.c["SHL_cold_rising"], 3)
        self.assertEqual(self.m.countries["SHL"]["subject_of"], "NAM")
        self.assertEqual(self.m.autonomy["SHL"], "autonomy_NAM_namestnik_office")
        self.assertEqual(self.m.control["287"], "SHL")
        self.assertEqual(self.leased(), SEAL_TERMS["autonomy_NAM_namestnik_office"][0])
        self.assertEqual(self.m.idea_days["SHL_cold_ashes_idea"], 730)
        self.assertNotIn("SHL_underground_heat", self.c)
        # A war closed by another script is decided by the controller of Khazar.
        for controller, result in (("SHL", 2), ("NAM", 3)):
            with self.subTest(controller=controller):
                self.rise()
                self.m.wars.clear()
                self.m.control["699"] = controller
                self.m.execute(self.peace["on_peace"], "SHL")
                self.m.execute(self.peace["on_peace"], "SHL")
                self.assertEqual(self.c["SHL_cold_rising"], result)

    def test_freed_underground_reaches_the_ending_without_a_war(self):
        self.open()
        self.c.update({"SHL_underground_heat": 40.0, "SHL_cold_cache_rifles": 300.0})
        self.m.flags["KYZ"].add("SHL_cold_pledged")
        self.m.set_overlord(None)
        self.m.run("SHL_seal_cycle")
        self.assertEqual(self.c["SHL_cold_rising"], 2)
        self.assertEqual(self.m.equipment[("SHL", "infantry_equipment")], 300)
        self.assertNotIn("SHL_cold_pledged", self.m.flags["KYZ"])
        self.assertEqual(self.leased(), set())


if __name__ == "__main__":
    unittest.main()
