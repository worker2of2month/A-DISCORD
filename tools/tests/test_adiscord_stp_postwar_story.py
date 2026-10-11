from __future__ import annotations

import json
import re
import unittest
from dataclasses import replace
from pathlib import Path
from tools.lib.focus_sources import read_focus_source

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import (
    block, scalar, walk, matches_conditions, selected_effects,
)


ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "events/ADISCORD_STP_events.txt"
POSTWAR_LOCALISATION = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
LEDGER = ROOT / "tools/data/adiscord_event_ids.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


def event_block(text: str, event_id: str) -> str:
    marker = f"\tid = {event_id}\n"
    start = text.index(marker)
    next_event = text.find("\ncountry_event = {", start + len(marker))
    next_news = text.find("\nnews_event = {", start + len(marker))
    candidates = [pos for pos in (next_event, next_news) if pos != -1]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


class FounderCourseChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.event = next(
            node.value for node in parse_clausewitz(read(EVENTS))
            if node.key == "country_event"
            and scalar(node.value, "id") == "ADISCORD_STP_pc.12"
        )
        source = read(ROOT / "focus_trees/STP/postwar/shabrat/focuses.txt")
        cls.focuses = {
            scalar(node.value, "id"): node.value
            for node in parse_clausewitz(source)
            if node.key == "focus"
        }

    def test_answer_opens_only_its_focus_without_completing_it(self):
        options = [node.value for node in self.event if node.key == "option"]
        for answer, expected in ((None, None), (0, "hegemony"), (1, "freedom")):
            facts = {
                ("STS", "STP_pc_focus_available", "yes"): True,
                ("STS", "STP_pc_founder_rules", "yes"): True,
                ("STS", "STP_pc_founder_choice_pending", "yes"): True,
            }
            if answer is not None:
                effects = list(selected_effects(
                    block(options[answer], "hidden_effect"), facts, "STS"
                ))
                self.assertEqual([effect.key for _, effect in effects], ["set_variable"])
                for scope, effect in effects:
                    variable = scalar(effect.value, "var")
                    facts[(scope, "variable", variable)] = float(
                        scalar(effect.value, "value")
                    )
            for route in ("hegemony", "freedom"):
                focus = self.focuses[f"STP_pc_{route}_open"]
                with self.subTest(answer=answer, route=route):
                    self.assertEqual(
                        matches_conditions(block(focus, "available"), facts, "STS"),
                        route == expected,
                    )
                    self.assertEqual(scalar(focus, "cost"), "3")
                    self.assertFalse(any(node.key == "bypass" for node in focus))

    def test_answer_and_timeout_cannot_replace_a_settled_choice(self):
        trigger = block(parse_clausewitz(read(
            ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
        )), "STP_pc_founder_choice_pending")
        facts = {
            ("STS", "STP_pc_founder_rules", "yes"): True,
            ("STS", "has_completed_focus", "STP_pc_shabrat_politics"): True,
        }
        self.assertTrue(matches_conditions(trigger, facts, "STS"))
        for blocker in (
            ("has_variable", "STP_pc_founder_choice"),
            ("has_country_flag", "STP_pc_course_locked"),
            ("has_completed_focus", "STP_pc_hegemony_open"),
            ("has_completed_focus", "STP_pc_freedom_open"),
        ):
            self.assertFalse(matches_conditions(
                trigger, facts | {("STS", *blocker): True}, "STS"
            ))
        options = [node.value for node in self.event if node.key == "option"]
        self.assertEqual(scalar(options[0], "name"), "ADISCORD_STP_pc.12.a")
        self.assertEqual(scalar(self.event, "timeout_days"), "14")
        self.assertEqual(scalar(self.event, "fire_only_once"), "yes")
        for option in options[:2]:
            self.assertEqual(
                scalar(block(option, "trigger"), "STP_pc_founder_choice_pending"),
                "yes",
            )
            settled = {("STS", "STP_pc_founder_choice_pending", "yes"): False}
            self.assertEqual(list(selected_effects(
                block(option, "hidden_effect"), settled, "STS"
            )), [])
        self.assertEqual(
            scalar(block(options[2], "trigger"), "STP_pc_founder_choice_pending"),
            "no",
        )
        self.assertEqual({node.key for node in options[2]}, {"name", "trigger"})

    def test_scene_is_dispatched_once_and_absent_sotnikov_has_a_description(self):
        reward = block(self.focuses["STP_pc_shabrat_politics"], "completion_reward")
        calls = [node.value for node in walk(reward) if node.key == "country_event"]
        self.assertEqual([scalar(call, "id") for call in calls], ["ADISCORD_STP_pc.12"])
        descriptions = [node.value for node in self.event if node.key == "desc"]
        for available, key in ((True, "d"), (False, "absent")):
            facts = {("STS", "STP_cw_sotnikov_available", "yes" if available else "no"): True}
            selected = [
                scalar(desc, "text") for desc in descriptions
                if matches_conditions(block(desc, "trigger"), facts, "STS")
            ]
            self.assertEqual(selected, [f"ADISCORD_STP_pc.12.{key}"])

    def test_native_focus_gates_match_the_authored_choice(self):
        def content(entries):
            return [
                (node.key, content(node.value) if isinstance(node.value, list) else node.value)
                for node in entries
            ]

        source = read(ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt")
        tree = block(parse_clausewitz(source), "focus_tree")
        for route in ("hegemony", "freedom"):
            focus_id = f"STP_pc_{route}_open"
            matches = [
                node.value for node in tree if node.key == "focus"
                and scalar(node.value, "id") == focus_id
            ]
            self.assertEqual(len(matches), 1)
            self.assertEqual(content(matches[0]), content(self.focuses[focus_id]))

    def test_choice_text_is_bilingual_loadable_and_within_page_limits(self):
        keys = [
            f"ADISCORD_STP_pc.12.{suffix}"
            for suffix in ("t", "d", "absent", "a", "b", "c", "a_tt", "b_tt")
        ]
        keys += [
            "STP_pc_founder_hegemony_chosen_tt",
            "STP_pc_founder_freedom_chosen_tt",
            "STP_pc_shabrat_politics_tt",
        ]
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = read(path)
            values = {}
            for line in text.splitlines():
                match = re.fullmatch(r'\s*([^\s:]+):\d*\s*"((?:[^"\\]|\\.)*)"', line)
                if match:
                    values[match[1]] = match[2]
            for key in keys:
                with self.subTest(language=language, key=key):
                    self.assertEqual(text.count(f"\n {key}:"), 1)
                    value = values[key].replace(r"\n", "\n")
                    self.assertLessEqual(len(value), 3000)
                    self.assertLessEqual(len(value.encode("utf-8")), 5500)
                    self.assertNotRegex(value, "[\u2013\u2014]")
                    self.assertNotIn("§Y", value)


class ShabratPostwarStoryTests(unittest.TestCase):
    def test_story_localisation_has_one_canonical_owner(self) -> None:
        for filename in (
            "ADISCORD_STP_story_l_russian.yml",
            "ADISCORD_STP_postwar_story_l_russian.yml",
        ):
            self.assertFalse(
                (ROOT / "localisation/replace" / filename).exists(), filename
            )
        self.assertTrue(POSTWAR_LOCALISATION.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_story_events_are_registered_and_trigger_from_postwar_focus_completion(
        self,
    ) -> None:
        events = read(EVENTS)
        ledger = json.loads(read(LEDGER))
        focus_source = read(
            ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt"
        )
        focuses = {
            next(field.value for field in node.value if field.key == "id"): node.value
            for tree in parse_clausewitz(focus_source)
            if tree.key == "focus_tree"
            for node in tree.value
            if node.key == "focus"
        }

        def dispatches(entries, hidden=False):
            for node in entries:
                if node.key == "effect_tooltip":
                    continue
                if node.key == "country_event":
                    yield {field.key: field.value for field in node.value}, hidden
                elif isinstance(node.value, list):
                    yield from dispatches(
                        node.value, hidden or node.key == "hidden_effect"
                    )

        expected = {
            "ADISCORD_STP_pw.1": "STP_pw_republic_new_republic",
            "ADISCORD_STP_pw.2": "STP_pw_republic_civil_records",
            "ADISCORD_STP_pw.3": "STP_pw_republic_civil_charter",
            "ADISCORD_STP_pw.4": "STP_pw_republic_homes_for_returnees",
            "ADISCORD_STP_pw.5": "STP_pw_republic_army_register",
        }

        self.assertIn("add_namespace = ADISCORD_STP_pw", events)
        ledger_ids = {entry["id"] for entry in ledger["events"]}
        for event_id, focus_id in expected.items():
            self.assertEqual(events.count(f"id = {event_id}"), 1)
            block = event_block(events, event_id)
            self.assertIn("tag = STS", block)
            self.assertIn(f"has_completed_focus = {focus_id}", block)
            self.assertIn("fire_only_once = yes", block)
            self.assertIn("is_triggered_only = yes", block)
            self.assertNotIn("mean_time_to_happen", block)
            reward = next(
                node.value
                for node in focuses[focus_id]
                if node.key == "completion_reward"
            )
            calls = [
                (payload, hidden)
                for payload, hidden in dispatches(reward)
                if payload.get("id") == event_id
            ]
            self.assertEqual(calls, [({"id": event_id, "days": "1"}, True)])
            self.assertIn(event_id, ledger_ids)

    def test_story_events_have_complete_russian_localisation(self) -> None:
        loc = read(POSTWAR_LOCALISATION)
        expected_keys = (
            "ADISCORD_STP_pw.1.t",
            "ADISCORD_STP_pw.1.d",
            "ADISCORD_STP_pw.1.a",
            "ADISCORD_STP_pw.2.t",
            "ADISCORD_STP_pw.2.d",
            "ADISCORD_STP_pw.2.a",
            "ADISCORD_STP_pw.3.t",
            "ADISCORD_STP_pw.3.d",
            "ADISCORD_STP_pw.3.a",
            "ADISCORD_STP_pw.3.b",
            "ADISCORD_STP_pw.4.t",
            "ADISCORD_STP_pw.4.d",
            "ADISCORD_STP_pw.4.a",
            "ADISCORD_STP_pw.5.t",
            "ADISCORD_STP_pw.5.d",
            "ADISCORD_STP_pw.5.a",
        )
        for key in expected_keys:
            self.assertEqual(loc.count(f"\n {key}:"), 1, key)


class CampaignEpilogueTests(unittest.TestCase):
    """Route selection and delivery contracts; native popup timing is not simulated."""

    @classmethod
    def setUpClass(cls):
        cls.events = {}
        for path in (EVENTS, ROOT / "events/ADISCORD_VAL_contract_events.txt"):
            cls.events.update({
                scalar(node.value, "id"): node.value
                for node in parse_clausewitz(read(path))
                if node.key == "country_event"
            })
        cls.ids = [f"ADISCORD_STP_ch.{n}" for n in range(60, 66)] + [
            "ADISCORD_STP_pc.60", "ADISCORD_STP_pc.61", "ADISCORD_STP_pc.62",
            "val_rework.139",
        ]

    def descriptions(self, event_id, facts, scope):
        return [
            scalar(node.value, "text")
            for node in self.events[event_id] if node.key == "desc"
            and matches_conditions(block(node.value, "trigger"), facts, scope)
        ]

    def test_all_party_outcomes_have_exactly_one_epilogue_description(self):
        for index, route in enumerate(("houses", "festival", "staff", "trade", "security", "regent")):
            event_id = f"ADISCORD_STP_ch.{60 + index}"
            for side in ("a", "b"):
                with self.subTest(route=route, side=side):
                    facts = {("STP", "has_completed_focus", f"STP_pe_{route}_ending_{side}"): True}
                    self.assertEqual(self.descriptions(event_id, facts, "STP"), [f"{event_id}.{side}_desc"])
            # The sole original answer also handles the unattended event timeout.
            original = self.events[f"ADISCORD_STP_ch.{52 + index}"]
            options = [node.value for node in original if node.key == "option"]
            self.assertEqual(len(options), 1)
            calls = [scalar(node.value, "id") for node in walk(block(options[0], "hidden_effect")) if node.key == "country_event"]
            self.assertEqual(calls, [event_id])

    def test_kefreyt_mixed_partners_use_republics_and_all_other_cases_have_one_text(self):
        for independent, dependent, expected in (
            (True, False, "republics"), (True, True, "republics"),
            (False, True, "administrations"), (False, False, "d"),
        ):
            facts = {
                ("VAL", "VAL_nw_has_independent_partner", "yes"): independent,
                ("VAL", "VAL_nw_has_independent_partner", "no"): not independent,
                ("VAL", "VAL_nw_has_contract_administration", "yes"): dependent,
                ("VAL", "VAL_nw_has_contract_administration", "no"): not dependent,
            }
            self.assertEqual(self.descriptions("val_rework.139", facts, "VAL"), [f"val_rework.139.{expected}"])
        option = block(self.events["val_rework.129"], "option")
        self.assertEqual(scalar(block(block(option, "hidden_effect"), "country_event"), "id"), "val_rework.139")

    def test_hegemony_requires_settled_relations_and_handles_allies_and_bypassed_wars(self):
        trigger = block(self.events["ADISCORD_STP_pc.60"], "trigger")
        facts = {
            ("STS", "is_ai", "no"): True,
            ("STS", "has_country_flag", "STP_heg_administrations_unlocked"): True,
            ("STS", "variable", "STP_pc_course"): 1,
        }
        # Removed countries permit the bypassed-war route without fake focus completion.
        self.assertTrue(matches_conditions(trigger, facts, "STS"))
        for tag in ("NOD", "YPR", "TFF", "VAL"):
            focus = "STP_pc_heg_final_kefreyt" if tag == "VAL" else "STP_pc_heg_final_north"
            for relation in ("is_subject_of", "is_in_faction_with"):
                with self.subTest(tag=tag, relation=relation):
                    case = dict(facts)
                    case[(tag, "exists", "yes")] = True
                    self.assertFalse(matches_conditions(trigger, case, "STS"))
                    case[(tag, relation, "STS")] = True
                    self.assertEqual(matches_conditions(trigger, case, "STS"), relation == "is_subject_of")
                    case[("STS", "has_completed_focus", focus)] = True
                    self.assertTrue(matches_conditions(trigger, case, "STS"))
                    case[("STS", "has_war_with", tag)] = True
                    self.assertFalse(matches_conditions(trigger, case, "STS"))
        facts[("STS", "has_country_flag", "STP_epilogue_shown")] = True
        self.assertFalse(matches_conditions(trigger, facts, "STS"))

    def test_allied_kefreyt_epilogue_does_not_require_a_war_focus(self):
        trigger = block(self.events["ADISCORD_STP_pc.60"], "trigger")
        facts = {
            ("STS", "is_ai", "no"): True,
            ("STS", "has_country_flag", "STP_heg_administrations_unlocked"): True,
            ("STS", "variable", "STP_pc_course"): 1,
            ("VAL", "exists", "yes"): True,
            ("VAL", "is_in_faction_with", "STS"): True,
        }
        self.assertFalse(matches_conditions(trigger, facts, "STS"))
        facts["STS", "has_completed_focus", "STP_pc_heg_final_north"] = True
        self.assertTrue(matches_conditions(trigger, facts, "STS"))
        facts["STS", "has_war_with", "VAL"] = True
        self.assertFalse(matches_conditions(trigger, facts, "STS"))

    def test_succession_outcomes_are_disjoint_and_every_answer_queues_the_epilogue(self):
        for course, leader, expected in (
            (3, "STP_grigory_sotnikov", "directory"),
            (3, "STP_Leonid_Barchel", "directory"),
            (4, "STP_ilya_gornin", "gornin"),
            (4, "STP_vera_tikh", "vera"),
            (4, "STP_maksim_shabrat", "shabrat"),
            (4, "STP_grigory_sotnikov", "retained"),
        ):
            facts = {
                ("STS", "variable", "STP_pc_course"): course,
                ("STS", "ruling_leader"): leader,
            }
            self.assertEqual(self.descriptions("ADISCORD_STP_pc.62", facts, "STS"), [f"ADISCORD_STP_pc.62.{expected}"])
        options = [node.value for node in self.events["ADISCORD_STP_pc.7"] if node.key == "option"]
        playable = [option for option in options if any(node.key == "hidden_effect" for node in option)]
        self.assertEqual(len(playable), 4)
        for option in playable:
            hidden = block(option, "hidden_effect")
            self.assertEqual([scalar(node.value, "id") for node in walk(hidden) if node.key == "country_event"], ["ADISCORD_STP_pc.62"])
            outer = block(hidden, "if")
            self.assertFalse(matches_conditions(block(outer, "limit"), {("STS", "has_variable", "STP_pc_charter_cabinet"): True}, "STS"))
            condition = block(block(outer, "if"), "limit")
            self.assertTrue(matches_conditions(condition, {("STS", "variable", "STP_pc_course"): 4}, "STS"))
            self.assertFalse(matches_conditions(condition, {("STS", "variable", "STP_pc_course"): 2}, "STS"))
        closed = [option for option in options if option not in playable]
        self.assertEqual(len(closed), 1)
        self.assertEqual({node.key for node in closed[0]}, {"name", "trigger"})

    def test_epilogues_are_one_shot_human_only_and_have_no_gameplay_rewards(self):
        for event_id in self.ids:
            event = self.events[event_id]
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertEqual(scalar(event, "fire_only_once"), "yes")
            self.assertEqual(scalar(block(event, "trigger"), "is_ai"), "no")
            self.assertEqual({node.key for node in block(event, "option")}, {"name", "custom_effect_tooltip"})
        focuses = {
            scalar(node.value, "id"): node.value
            for node in parse_clausewitz(read(ROOT / "focus_trees/STP/postwar/shabrat/focuses.txt"))
            if node.key == "focus"
        }
        for focus in ("STP_pc_heg_administrations", "STP_pc_heg_final_north", "STP_pc_heg_final_kefreyt"):
            self.assertIn("STP_pw_queue_hegemony_epilogue", {node.key for node in walk(block(focuses[focus], "completion_reward"))})
        for focus, event_id in (("STP_pc_lib_coalition", "ADISCORD_STP_pc.61"), ("STP_pc_sot_keep_command", "ADISCORD_STP_pc.62")):
            self.assertIn(event_id, [scalar(node.value, "id") for node in walk(block(focuses[focus], "completion_reward")) if node.key == "country_event"])

    def test_localised_pages_expand_within_limits_and_keep_bom(self):
        for language in ("russian", "english"):
            localisation = {}
            for country in ("STP", "VAL_decisions"):
                path = ROOT / f"localisation/{language}/ADISCORD_{country}_l_{language}.yml"
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                for line in read(path).splitlines():
                    match = re.fullmatch(r'\s*([^\s:]+):\d*\s*"((?:[^"\\]|\\.)*)"', line)
                    if match:
                        localisation[match[1]] = match[2]
            def expand(value):
                return re.sub(r"\$([^$]+)\$", lambda match: expand(localisation[match[1]]), value).replace(r"\n", "\n")
            for event_id in self.ids:
                event = self.events[event_id]
                keys = [scalar(event, "title"), scalar(block(event, "option"), "name"), scalar(block(event, "option"), "custom_effect_tooltip")]
                keys += [scalar(node.value, "text") for node in event if node.key == "desc"]
                for key in keys:
                    with self.subTest(language=language, key=key):
                        value = expand(localisation[key])
                        self.assertLessEqual(len(value), 3000)
                        self.assertLessEqual(len(value.encode("utf-8")), 5500)
                        self.assertNotRegex(value, "[\u2013\u2014]")
                        self.assertNotIn("§Y", value)


class CharterCabinetTests(unittest.TestCase):
    """Parsed authoring contracts; these scenarios do not simulate the native loader."""

    CANDIDATES = {
        "sotnikov": (1, "STP_grigory_sotnikov", "humanism", "steland_liberationism"),
        "shabrat": (2, "STP_maksim_shabrat", "chauvinism", "national_legitimism"),
        "tikhoreva": (3, "STP_vera_tikh", "utilitarism", "utilitarism_ideology"),
    }
    PROGRAMMES = {
        "sotnikov": ("reintegration", "civil_return"),
        "shabrat": ("civic_grants", "district_grants"),
        "tikhoreva": ("procurement", "open_tenders"),
    }

    @classmethod
    def setUpClass(cls):
        cls.focuses = {
            scalar(node.value, "id"): node.value
            for node in parse_clausewitz(read(
                ROOT / "focus_trees/STP/postwar/shabrat/focuses.txt"
            )) if node.key == "focus"
        }
        cls.events = {
            scalar(node.value, "id"): node.value
            for node in parse_clausewitz(read(EVENTS)) if node.key == "country_event"
        }
        cls.triggers = parse_clausewitz(read(
            ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
        ))
        cls.effects = parse_clausewitz(read(
            ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
        ))
        cls.decisions = parse_clausewitz(read(
            ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
        ))
        cls.ideas = block(block(parse_clausewitz(read(
            ROOT / "common/ideas/ADISCORD_STP_civil_war_ideas.txt"
        )), "ideas"), "country")

    def facts(self, candidate=None, course=2, pending=False):
        facts = {
            ("STS", "variable", "STP_pc_course"): course,
            ("STS", "has_country_flag", "STP_cw_postwar"): True,
            ("STS", "has_country_flag", "STP_pc_course_locked"): True,
            ("STS", "has_completed_focus", "STP_pc_freedom_open"): True,
            ("STS", "STP_pc_focus_available", "yes"): True,
            ("STS", "STP_pc_charter_choice_pending", "yes"): pending,
            ("STS", "STP_pc_charter_choice_pending", "no"): not pending,
            ("STS", "STP_cw_sotnikov_available", "yes"): True,
            ("STS", "STP_pc_founder_rules", "yes"): candidate in (None, "shabrat"),
            ("STS", "has_character", "STP_vera_tikh"): True,
        }
        for name in self.CANDIDATES:
            facts["STS", f"STP_pc_charter_{name}_current", "yes"] = name == candidate
        facts["STS", "STP_pc_charter_government_current", "yes"] = candidate is not None
        if candidate is not None:
            cabinet, character, _, _ = self.CANDIDATES[candidate]
            facts["STS", "variable", "STP_pc_charter_cabinet"] = cabinet
            facts["STS", "has_variable", "STP_pc_charter_cabinet"] = True
            facts["STS", "ruling_leader"] = character
        return facts

    def cabinet_effects(self, entries, facts):
        """Resolve only registered character conditions and the shared cabinet call."""
        characters = {values[1] for values in self.CANDIDATES.values()}

        def conditions(items):
            resolved = []
            for node in items:
                if node.key in characters and isinstance(node.value, list):
                    result = matches_conditions(node.value, facts, node.key)
                    resolved.append(replace(node, key="always", value="yes" if result else "no"))
                elif isinstance(node.value, list):
                    resolved.append(replace(node, value=conditions(node.value)))
                else:
                    resolved.append(node)
            return resolved

        def with_limits(items):
            return [
                replace(node, value=conditions(node.value) if node.key == "limit" else with_limits(node.value))
                if isinstance(node.value, list) else node
                for node in items
            ]

        for scope, node in selected_effects(with_limits(entries), facts, "STS"):
            if node.key == "STP_pc_charter_confirm_government":
                self.assertEqual(node.value, "yes")
                yield from selected_effects(block(self.effects, node.key), facts, scope)
            else:
                yield scope, node

    def test_choice_dispatches_from_freedom_open_once_before_programmes(self):
        calls = []
        for focus_id, focus in self.focuses.items():
            for node in walk(block(focus, "completion_reward")):
                if node.key == "country_event" and scalar(node.value, "id") == "ADISCORD_STP_pc.5":
                    calls.append((focus_id, scalar(node.value, "hours")))
        self.assertEqual(calls, [("STP_pc_freedom_open", "1")])
        lock = block(self.focuses["STP_pc_lib_lock"], "completion_reward")
        self.assertIn("STP_pc_lock_freedom", {node.key for node in walk(lock)})
        for candidate in self.CANDIDATES:
            effects = [node for _, node in selected_effects(block(self.effects, "STP_pc_lock_freedom"), self.facts(candidate), "STS")]
            self.assertEqual([node.key for node in effects], ["set_variable", "set_country_flag"])
            self.assertEqual(scalar(block(effects, "set_variable"), "var"), "STP_pc_course")
            self.assertEqual(scalar(block(effects, "set_variable"), "value"), "2")
        self.assertFalse(any(node.key == "complete_national_focus" for node in walk(lock)))
        event = self.events["ADISCORD_STP_pc.5"]
        self.assertEqual(scalar(event, "fire_only_once"), "yes")
        self.assertEqual(scalar(event, "is_triggered_only"), "yes")
        self.assertEqual(scalar(event, "timeout_days"), "14")
        self.assertEqual(scalar(block(event, "trigger"), "STP_pc_charter_choice_pending"), "yes")
        self.assertNotIn("complete_national_focus", {node.key for node in walk(event)})

    def test_pending_choice_rejects_repeat_and_non_charter_routes(self):
        trigger = block(self.triggers, "STP_pc_charter_choice_pending")
        self.assertTrue(matches_conditions(trigger, self.facts(pending=True), "STS"))
        self.assertFalse(matches_conditions(trigger, self.facts(pending=True), "STP"))
        for candidate in self.CANDIDATES:
            self.assertFalse(matches_conditions(trigger, self.facts(candidate), "STS"))
        missing = self.facts()
        missing["STS", "has_completed_focus", "STP_pc_freedom_open"] = False
        self.assertFalse(matches_conditions(trigger, missing, "STS"))
        absent_founder = self.facts()
        absent_founder["STS", "STP_pc_founder_rules", "yes"] = False
        self.assertFalse(matches_conditions(trigger, absent_founder, "STS"))

    def test_choice_default_and_missing_candidate_have_safe_options(self):
        event = self.events["ADISCORD_STP_pc.5"]
        options = [node.value for node in event if node.key == "option"]
        self.assertEqual(len(options), 4)
        default = options[0]
        names = {}
        for option in options:
            appointments = [node.key for node in walk(option) if node.key.startswith("STP_pc_charter_install_")]
            if appointments:
                self.assertEqual(len(appointments), 1)
                names[appointments[0].removeprefix("STP_pc_charter_install_")] = option
        self.assertEqual(set(names), set(self.CANDIDATES))
        self.assertIs(names["shabrat"], default)
        self.assertTrue(matches_conditions(block(default, "trigger"), self.facts(pending=True), "STS"))
        absent = self.facts(pending=True)
        absent["STS", "STP_cw_sotnikov_available", "yes"] = False
        self.assertFalse(matches_conditions(block(names["sotnikov"], "trigger"), absent, "STS"))
        self.assertTrue(matches_conditions(block(default, "trigger"), absent, "STS"))
        for available, suffix in ((True, "d"), (False, "absent")):
            facts = self.facts(pending=True)
            facts["STS", "STP_cw_sotnikov_available", "yes"] = available
            facts["STS", "STP_cw_sotnikov_available", "no"] = not available
            descriptions = [scalar(node.value, "text") for node in event if node.key == "desc" and matches_conditions(block(node.value, "trigger"), facts, "STS")]
            self.assertEqual(descriptions, [f"ADISCORD_STP_pc.5.{suffix}"])
        stale = [option for option in options if option not in names.values()]
        self.assertEqual(len(stale), 1)
        self.assertEqual({node.key for node in stale[0]}, {"name", "trigger"})
        self.assertTrue(matches_conditions(block(stale[0], "trigger"), self.facts("shabrat"), "STS"))
        for option in names.values():
            self.assertFalse(matches_conditions(block(option, "trigger"), self.facts("shabrat"), "STS"))

    def test_appointments_set_exact_mandate_and_registered_leader_without_recruitment(self):
        for candidate, (cabinet, character, party, ideology) in self.CANDIDATES.items():
            with self.subTest(candidate=candidate):
                effect = block(self.effects, f"STP_pc_charter_install_{candidate}")
                selected = list(self.cabinet_effects(effect, self.facts(pending=True)))
                nodes = [node for _, node in selected]
                assignments = {
                    scalar(node.value, "var"): scalar(node.value, "value")
                    for node in nodes if node.key == "set_variable"
                }
                self.assertEqual(assignments["STP_pc_charter_cabinet"], str(cabinet))
                self.assertEqual(assignments["STP_pc_course"], "2")
                self.assertIn("STP_pc_course_locked", [node.value for node in nodes if node.key == "set_country_flag"])
                promotions = [node.value for node in nodes if node.key == "promote_character"]
                self.assertTrue(any(scalar(value, "character") == character and scalar(value, "ideology") == ideology for value in promotions))
                politics = [node.value for node in nodes if node.key == "set_politics"]
                self.assertTrue(any(scalar(value, "ruling_party") == party for value in politics))
                self.assertNotIn("recruit_character", {node.key for node in walk(effect)})
                self.assertEqual(list(self.cabinet_effects(effect, self.facts("shabrat"))), [])
                if candidate == "sotnikov":
                    absent = self.facts(pending=True)
                    absent["STS", "STP_cw_sotnikov_available", "yes"] = False
                    self.assertEqual(list(self.cabinet_effects(effect, absent)), [])
                elif candidate == "tikhoreva":
                    absent = self.facts(pending=True)
                    absent["STS", "has_character", character] = False
                    self.assertEqual(list(self.cabinet_effects(effect, absent)), [])
                    arrested = self.facts(pending=True)
                    arrested[character, "has_character_flag", "STP_cw_arrested"] = True
                    self.assertEqual(list(self.cabinet_effects(effect, arrested)), [])

    def test_serving_cabinet_requires_matching_mandate_and_character(self):
        for candidate, (_, character, _, _) in self.CANDIDATES.items():
            trigger = block(self.triggers, f"STP_pc_charter_{candidate}_current")
            self.assertTrue(matches_conditions(trigger, self.facts(candidate), "STS"))
            for other in self.CANDIDATES:
                if candidate != other:
                    self.assertFalse(matches_conditions(trigger, self.facts(other), "STS"))
            facts = self.facts(candidate)
            facts["STS", "ruling_leader"] = "STP_ilya_gornin"
            self.assertFalse(matches_conditions(trigger, facts, "STS"), character)
        union = block(self.triggers, "STP_pc_charter_government_current")
        for candidate in self.CANDIDATES:
            self.assertTrue(matches_conditions(union, self.facts(candidate), "STS"))
        self.assertFalse(matches_conditions(union, self.facts(), "STS"))

    def test_charter_preserves_common_route_and_blocks_directory_and_succession(self):
        for candidate in self.CANDIDATES:
            facts = self.facts(candidate)
            for name in ("STP_pc_course_continues", "STP_pc_freedom_continues"):
                self.assertTrue(matches_conditions(block(self.triggers, name), facts, "STS"), (candidate, name))
            self.assertFalse(matches_conditions(block(self.triggers, "STP_pc_hegemony_continues"), facts, "STS"))
            for option in (node.value for node in self.events["ADISCORD_STP_pc.7"] if node.key == "option"):
                hidden = [node.value for node in option if node.key == "hidden_effect"]
                effects = list(selected_effects(hidden[0], facts, "STS")) if hidden else []
                self.assertNotIn("promote_character", {node.key for _, node in effects})
                self.assertNotIn("set_politics", {node.key for _, node in effects})
            directory = self.focuses["STP_pc_sot_chain"]
            self.assertFalse(matches_conditions(block(directory, "allow_branch"), facts, "STS"))
            self.assertFalse(matches_conditions(block(directory, "available"), facts, "STS"))

    def test_each_programme_has_thirty_exclusive_connected_acyclic_focuses(self):
        all_ids = []
        for candidate in self.CANDIDATES:
            prefix = f"STP_pc_charter_{candidate}_"
            route = {key: value for key, value in self.focuses.items() if key.startswith(prefix)}
            self.assertEqual(len(route), 30, candidate)
            root = prefix + "mandate"
            capstone = prefix + "charter_fulfilled"
            children = {key: set() for key in route}
            parents = {}
            for focus_id, focus in route.items():
                all_ids.append(focus_id)
                self.assertIn(scalar(focus, "cost"), {"3", "4"})
                self.assertFalse(any(node.key == "bypass" for node in focus))
                parents[focus_id] = {node.value for entry in focus if entry.key == "prerequisite" for node in entry.value if node.key == "focus"}
                self.assertEqual(parents[focus_id] - route.keys(), {"STP_pc_lib_lock"} if focus_id == root else set())
                for parent in parents[focus_id] & route.keys():
                    children[parent].add(focus_id)
                for current in (None, *self.CANDIDATES):
                    facts = self.facts(current)
                    self.assertEqual(matches_conditions(block(focus, "allow_branch"), facts, "STS"), current == candidate, (focus_id, current))
                    government_gate = [node for node in block(focus, "available") if node.key != "any_owned_state"]
                    self.assertEqual(matches_conditions(government_gate, facts, "STS"), current == candidate, (focus_id, current))
            self.assertEqual(parents[root], {"STP_pc_lib_lock"})
            self.assertEqual([key for key in route if not children[key]], [capstone])
            visited = set()
            active = set()

            def visit(focus_id):
                self.assertNotIn(focus_id, active, f"Cycle at {focus_id}")
                if focus_id in visited:
                    return
                active.add(focus_id)
                for child in children[focus_id]:
                    visit(child)
                active.remove(focus_id)
                visited.add(focus_id)

            visit(root)
            self.assertEqual(visited, set(route))
            merge = route[prefix + "cabinet_review"]
            prerequisites = [node.value for node in merge if node.key == "prerequisite"]
            self.assertEqual(len(prerequisites), 6)
            self.assertTrue(all(len(group) == 1 for group in prerequisites))
        native = block(parse_clausewitz(read(ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt")), "focus_tree")
        native_ids = [scalar(node.value, "id") for node in native if node.key == "focus"]
        for focus_id in all_ids:
            self.assertEqual(native_ids.count(focus_id), 1, focus_id)

    def test_programmes_share_the_charter_area_without_visible_node_collisions(self):
        def position(focus_id):
            focus = self.focuses[focus_id]
            x, y = int(scalar(focus, "x")), int(scalar(focus, "y"))
            anchors = [node.value for node in focus if node.key == "relative_position_id"]
            if anchors:
                anchor_x, anchor_y = position(anchors[0])
                x += anchor_x
                y += anchor_y
            return x, y

        for candidate in self.CANDIDATES:
            facts = self.facts(candidate)
            facts["STS", "STP_pc_freedom_continues", "yes"] = True
            facts["STS", "STP_pc_course_continues", "yes"] = True
            facts["STS", "STP_pc_hegemony_continues", "yes"] = False
            occupied = {}
            for focus_id, focus in self.focuses.items():
                gates = [node.value for node in focus if node.key == "allow_branch"]
                if gates and not matches_conditions(gates[0], facts, "STS"):
                    continue
                point = position(focus_id)
                self.assertNotIn(point, occupied, (candidate, focus_id, occupied.get(point)))
                occupied[point] = focus_id
            prefix = f"STP_pc_charter_{candidate}_"
            programme = [focus_id for focus_id in self.focuses if focus_id.startswith(prefix)]
            ys = [position(focus_id)[1] for focus_id in programme]
            self.assertEqual(min(ys), position("STP_pc_lib_lock")[1] + 1)
            self.assertLessEqual(max(ys), position("STP_pc_lib_coalition")[1] + 3)
            self.assertGreaterEqual(len({position(focus_id)[0] for focus_id in programme}), 7)
            self.assertGreaterEqual(len({scalar(self.focuses[focus_id], "icon") for focus_id in programme}), 12)

    def test_permanent_rewards_have_exact_preview_deltas_and_modest_totals(self):
        for candidate in self.CANDIDATES:
            totals = {}
            for focus_id, focus in self.focuses.items():
                if not focus_id.startswith(f"STP_pc_charter_{candidate}_"):
                    continue
                reward = block(focus, "completion_reward")
                selected = [node for _, node in selected_effects(reward, self.facts(candidate), "STS")]
                increments = {
                    scalar(node.value, "var").removeprefix("STP_pw_"): float(scalar(node.value, "value"))
                    for node in selected if node.key == "add_to_variable" and scalar(node.value, "var").startswith("STP_pw_")
                }
                previews = [node.value for node in reward if node.key == "effect_tooltip"]
                preview_ids = [node.value for preview in previews for node in walk(preview) if node.key == "add_ideas"]
                if increments:
                    self.assertEqual(preview_ids, [focus_id + "_delta"])
                    dummy = block(self.ideas, preview_ids[0])
                    modifiers = {node.key: float(node.value) for node in block(dummy, "modifier")}
                    self.assertEqual(modifiers, increments, focus_id)
                    self.assertIn("STP_pw_refresh_modifier", {node.key for node in selected})
                for node in selected:
                    if node.key == "add_ideas":
                        self.assertFalse(str(node.value).endswith("_delta"), focus_id)
                self.assertTrue(any(node.key not in {"custom_effect_tooltip", "mark_focus_tree_layout_dirty"} for node in selected), focus_id)
                for field, amount in increments.items():
                    totals[field] = totals.get(field, 0) + amount
            for field in ("industrial_capacity_factory", "industrial_capacity_dockyard", "research_speed_factor", "army_org_factor", "production_speed_buildings_factor"):
                self.assertLessEqual(totals.get(field, 0), 0.100001, (candidate, field))
            self.assertGreaterEqual(totals.get("ADISCORD_economy_admin_expense_factor", 0), -0.100001)

    def test_construction_requires_owned_controlled_capacity_and_rechecks_delivery(self):
        def content(items):
            return [(node.key, content(node.value) if isinstance(node.value, list) else node.value) for node in items]

        constructions = 0
        for focus_id, focus in self.focuses.items():
            if not focus_id.startswith("STP_pc_charter_"):
                continue
            reward = block(focus, "completion_reward")
            deliveries = [node.value for node in reward if node.key == "random_owned_controlled_state"]
            if not deliveries:
                continue
            constructions += 1
            self.assertEqual(len(deliveries), 1)
            capacity = block(block(focus, "available"), "any_owned_state")
            self.assertEqual(scalar(capacity, "is_controlled_by"), "ROOT")
            slot = block(capacity, "free_building_slots")
            repeated = block(block(deliveries[0], "limit"), "free_building_slots")
            self.assertEqual(content(slot), content(repeated), focus_id)
            self.assertEqual([node.value for node in slot if not node.key], ["size", ">", "0"])
            construction = block(deliveries[0], "add_building_construction")
            self.assertEqual(scalar(construction, "type"), scalar(slot, "building"))
            self.assertEqual(scalar(construction, "level"), "1")
            self.assertEqual(scalar(construction, "instant_build"), "yes")
            self.assertIn("ADISCORD_economy_mark_dirty", {node.key for node in walk(reward)})
        self.assertGreaterEqual(constructions, 3)

    def test_charter_shabrat_cannot_proclaim_the_old_imperial_union(self):
        requirements = block(self.triggers, "STP_imperial_union_requirements_met")
        decision = block(block(self.decisions, "STP_imperial_union_category"), "STP_proclaim_imperial_union")
        for selected, expected in ((True, False), (False, True)):
            facts = self.facts("shabrat")
            facts["STS", "has_variable", "STP_pc_charter_cabinet"] = selected
            facts["STS", "STP_imperial_union_kefreyt_defeated", "yes"] = True
            self.assertEqual(matches_conditions(requirements, facts, "STS"), expected)
            self.assertEqual(matches_conditions(block(decision, "visible"), facts, "STS"), expected)
            facts["STS", "STP_imperial_union_requirements_met", "yes"] = expected
            self.assertEqual(matches_conditions(block(decision, "available"), facts, "STS"), expected)

    def test_paid_programmes_unlock_at_their_focus_and_recheck_current_government(self):
        definitions = {node.key: node.value for category in self.decisions if isinstance(category.value, list) for node in category.value if isinstance(node.value, list)}
        prices = {"sotnikov": (60, 90), "shabrat": (75, 90), "tikhoreva": (75, 120)}
        for candidate, (suffix, unlock) in self.PROGRAMMES.items():
            decision_id = f"STP_pc_charter_{candidate}_{suffix}"
            focus_id = f"STP_pc_charter_{candidate}_{unlock}"
            decision = definitions[decision_id]
            reward = block(self.focuses[focus_id], "completion_reward")
            self.assertEqual([node.value for node in walk(reward) if node.key == "unlock_decision_tooltip"], [decision_id])
            price, cooldown = prices[candidate]
            self.assertEqual(float(scalar(decision, "cost")), price)
            self.assertEqual(scalar(block(decision, "allowed"), "tag"), "STS")
            self.assertFalse(any(node.key in {"custom_cost_text", "custom_cost_trigger", "days_remove", "cancel_effect"} for node in decision))
            self.assertEqual(int(scalar(decision, "days_re_enable")), cooldown)
            self.assertEqual(scalar(decision, "fire_only_once"), "no")
            for current in (None, *self.CANDIDATES):
                facts = self.facts(current)
                self.assertFalse(matches_conditions(block(decision, "visible"), facts, "STS"))
                facts["STS", "has_completed_focus", focus_id] = True
                self.assertEqual(matches_conditions(block(decision, "visible"), facts, "STS"), current == candidate)
                self.assertEqual(matches_conditions(block(decision, "available"), facts, "STS"), current == candidate)
            complete = block(decision, "complete_effect")
            self.assertNotIn("subtract_from_variable", {node.key for node in walk(complete)})
            paid = self.facts(candidate)
            unpaid = [node for _, node in selected_effects(complete, paid, "STS")]
            self.assertEqual([node.key for node in unpaid], ["add_political_power"])
            self.assertEqual(float(scalar(unpaid, "add_political_power")), price)
            paid["STS", "has_completed_focus", focus_id] = True
            nodes = [node for _, node in selected_effects(complete, paid, "STS")]
            self.assertNotIn("add_political_power", {node.key for node in nodes})
            if candidate == "sotnikov":
                self.assertEqual(float(scalar(nodes, "add_manpower")), 2000)
                self.assertEqual(float(scalar(nodes, "add_stability")), 0.02)
            elif candidate == "shabrat":
                amounts = {scalar(node.value, "var"): float(scalar(node.value, "value")) for node in nodes if node.key == "add_to_variable"}
                self.assertEqual(amounts["ADISCORD_economy_treasury"], 600)
                self.assertEqual(amounts["ADISCORD_economy_current_month_action_income"], 600)
                self.assertEqual(scalar(nodes, "ADISCORD_economy_mark_dirty"), "yes")
            else:
                equipment = {scalar(node.value, "type"): float(scalar(node.value, "amount")) for node in nodes if node.key == "add_equipment_to_stockpile"}
                self.assertEqual(equipment, {"support_equipment": 100, "train_equipment": 2})
            paid["STS", "STP_pc_focus_available", "yes"] = False
            blocked = [node for _, node in selected_effects(complete, paid, "STS")]
            self.assertEqual([node.key for node in blocked], ["add_political_power"])
            self.assertEqual(float(scalar(blocked, "add_political_power")), price)
            stale = self.facts()
            stale["STS", "has_completed_focus", focus_id] = True
            blocked = [node for _, node in selected_effects(complete, stale, "STS")]
            self.assertEqual([node.key for node in blocked], ["add_political_power"])
            self.assertEqual(float(scalar(blocked, "add_political_power")), price)

    def test_new_story_events_are_registered_guarded_and_localisation_is_loadable(self):
        ledger_ids = {entry["id"] for entry in json.loads(read(LEDGER))["events"]}
        keys = set()
        descriptions = set()
        for event_id in ("ADISCORD_STP_pc.5", *(f"ADISCORD_STP_pc.{number}" for number in range(65, 71))):
            event = self.events[event_id]
            self.assertIn(event_id, ledger_ids)
            keys.add(scalar(event, "title"))
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            if event_id != "ADISCORD_STP_pc.5":
                number = int(event_id.rsplit(".", 1)[1])
                candidate = tuple(self.CANDIDATES)[(number - 65) % 3]
                self.assertIn(f"STP_pc_charter_{candidate}_current", {node.key for node in walk(block(event, "trigger"))})
                self.assertEqual(scalar(event, "fire_only_once"), "yes")
            for node in event:
                if node.key == "desc":
                    key = scalar(node.value, "text") if isinstance(node.value, list) else node.value
                    descriptions.add(key)
                    keys.add(key)
            for node in walk(event):
                if node.key in {"name", "custom_effect_tooltip"} and isinstance(node.value, str):
                    keys.add(node.value)
        for focus_id in self.focuses:
            if focus_id.startswith("STP_pc_charter_"):
                keys.update((focus_id, focus_id + "_desc"))
                keys.update(node.value for node in walk(self.focuses[focus_id]) if node.key in {"tooltip", "custom_effect_tooltip"} and isinstance(node.value, str))
        for candidate, (suffix, _) in self.PROGRAMMES.items():
            decision_id = f"STP_pc_charter_{candidate}_{suffix}"
            keys.update((decision_id, decision_id + "_desc"))
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = read(path)
            values = {}
            for line in text.splitlines():
                match = re.fullmatch(r'\s*([^\s:]+):\d*\s*"((?:[^"\\]|\\.)*)"', line)
                if match:
                    values[match[1]] = match[2]

            def expand(key, stack=()):
                self.assertNotIn(key, stack)
                return re.sub(r"\$([^$]+)\$", lambda match: expand(match[1], stack + (key,)), values[key]).replace(r"\n", "\n")

            for key in keys:
                with self.subTest(language=language, key=key):
                    self.assertEqual(text.count(f"\n {key}:"), 1)
                    value = expand(key)
                    self.assertNotRegex(value, "[\u2013\u2014]")
                    if key in descriptions:
                        self.assertLessEqual(len(value), 3000)
                        self.assertLessEqual(len(value.encode("utf-8")), 5500)
                        self.assertNotIn("§Y", value)


if __name__ == "__main__":
    unittest.main()
