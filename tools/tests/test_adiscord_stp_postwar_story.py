from __future__ import annotations

import json
import re
import unittest
from dataclasses import replace
from pathlib import Path
from tools.builders.build_adiscord_focus_trees import render_source
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
            self.assertEqual(events.count(f"\tid = {event_id}\n"), 1)
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
    REVIEW_JOINS = {"sotnikov": 2, "shabrat": 3, "tikhoreva": 2}
    TRAITS = {
        "sotnikov": ("STP_charter_sotnikov_oath", "STP_charter_sotnikov_guarantor"),
        "shabrat": ("STP_charter_shabrat_founder", "STP_charter_shabrat_first_citizen"),
        "tikhoreva": ("STP_charter_tikhoreva_auditor", "STP_charter_tikhoreva_steward"),
    }
    STORY_EVENTS = {
        "sotnikov": (65, 68, 80, 81),
        "shabrat": (66, 69, 82, 83),
        "tikhoreva": (67, 70, 84, 85),
    }
    CAPSTONE_EVENTS = {"sotnikov": 68, "shabrat": 69, "tikhoreva": 70}

    @classmethod
    def setUpClass(cls):
        focus_sources = (
            "focus_trees/STP/postwar/shabrat/focuses.txt",
            "focus_trees/STP/postwar/charter/sotnikov.txt",
            "focus_trees/STP/postwar/charter/shabrat.txt",
            "focus_trees/STP/postwar/charter/tikhoreva.txt",
        )
        cls.focuses = {
            scalar(node.value, "id"): node.value
            for relative in focus_sources
            for node in parse_clausewitz(read(ROOT / relative))
            if node.key == "focus"
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

    def programme_nodes(self, entries, candidate, stack=()):
        """Follow native boolean calls without treating preview output as execution."""
        prefix = f"STP_pc_charter_{candidate}_"
        definitions = {
            node.key: node.value for node in (*self.effects, *self.triggers)
            if node.key.startswith(prefix) and isinstance(node.value, list)
        }
        for node in entries:
            yield node
            if isinstance(node.value, list):
                yield from self.programme_nodes(node.value, candidate, stack)
            elif node.key in definitions and node.value in {"yes", "no"}:
                self.assertNotIn(node.key, stack, f"Recursive cabinet call: {node.key}")
                yield from self.programme_nodes(definitions[node.key], candidate, (*stack, node.key))

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

    def test_each_programme_has_twenty_five_exclusive_connected_acyclic_focuses(self):
        all_ids = []
        for candidate in self.CANDIDATES:
            prefix = f"STP_pc_charter_{candidate}_"
            route = {key: value for key, value in self.focuses.items() if key.startswith(prefix)}
            self.assertEqual(len(route), 25, candidate)
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
            self.assertEqual(len(prerequisites), self.REVIEW_JOINS[candidate])
            self.assertTrue(all(len(group) == 1 for group in prerequisites))
        native = block(parse_clausewitz(read(ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt")), "focus_tree")
        native_ids = [scalar(node.value, "id") for node in native if node.key == "focus"]
        for focus_id in all_ids:
            self.assertEqual(native_ids.count(focus_id), 1, focus_id)

    def test_exclusive_forks_share_parents_and_rejoin_through_either_branch(self):
        for candidate in self.CANDIDATES:
            prefix = f"STP_pc_charter_{candidate}_"
            route = {key: value for key, value in self.focuses.items() if key.startswith(prefix)}

            def parents(focus):
                return [
                    sorted(node.value for node in entry.value if node.key == "focus")
                    for entry in focus if entry.key == "prerequisite"
                ]

            pairs = set()
            for focus_id, focus in route.items():
                rivals = [node.value for entry in focus if entry.key == "mutually_exclusive" for node in entry.value]
                for rival in rivals:
                    self.assertIn(focus_id, [node.value for entry in route[rival] if entry.key == "mutually_exclusive" for node in entry.value])
                    self.assertEqual(parents(focus), parents(route[rival]), (focus_id, rival))
                    pairs.add(frozenset((focus_id, rival)))
            self.assertEqual(len(pairs), 3, candidate)
            for pair in pairs:
                children = [focus for focus in route.values() if any(set(group) & pair for group in parents(focus))]
                self.assertTrue(children, pair)
                for child in children:
                    groups = [set(group) for group in parents(child) if set(group) & pair]
                    self.assertTrue(all(pair <= group for group in groups), (pair, scalar(child, "id")))

    def test_mandate_trait_is_upgraded_only_with_an_earned_legacy(self):
        traits = block(parse_clausewitz(read(ROOT / "common/country_leader/ADISCORD_traits_STP.txt")), "leader_traits")
        defined = {node.key for node in traits}
        for candidate, (first, final) in self.TRAITS.items():
            self.assertTrue({first, final} <= defined)
            mandate = block(self.focuses[f"STP_pc_charter_{candidate}_mandate"], "completion_reward")
            self.assertEqual(scalar(mandate, "add_country_leader_trait"), first)
            capstone = block(self.focuses[f"STP_pc_charter_{candidate}_charter_fulfilled"], "completion_reward")
            self.assertFalse(any(node.key in {"remove_country_leader_trait", "add_country_leader_trait"}
                                 for node in self.programme_nodes(capstone, candidate)))
            event = self.events[f"ADISCORD_STP_pc.{self.CAPSTONE_EVENTS[candidate]}"]
            awards = list(self.programme_nodes(event, candidate))
            self.assertEqual({node.value for node in awards if node.key == "remove_country_leader_trait"}, {first})
            self.assertEqual({node.value for node in awards if node.key == "add_country_leader_trait"}, {final})

    def test_capstone_legacy_options_require_earned_outcomes_and_allow_a_provisional_report(self):
        requirements = {
            "sotnikov": ("law_earned", "defenders_earned"),
            "shabrat": ("districts_ready", "nation_ready"),
            "tikhoreva": ("ledger_ready", "utility_ready"),
        }
        for candidate, number in self.CAPSTONE_EVENTS.items():
            event = self.events[f"ADISCORD_STP_pc.{number}"]
            options = {scalar(node.value, "name"): node.value for node in event if node.key == "option"}
            legacies = {node.value for node in self.programme_nodes(event, candidate)
                        if node.key == "add_ideas" and isinstance(node.value, str)
                        and node.value.startswith(f"STP_pc_charter_{candidate}_legacy_")}
            self.assertEqual(len(legacies), 2, candidate)
            for idea in legacies:
                self.assertIn("modifier", {node.key for node in block(self.ideas, idea)})
            for suffix, requirement in zip(("a", "b"), requirements[candidate]):
                option = options[f"ADISCORD_STP_pc.{number}.{suffix}"]
                self.assertIn(f"STP_pc_charter_{candidate}_{requirement}",
                              {node.key for node in walk(block(option, "trigger"))})
            provisional = [option for name, option in options.items()
                           if name.endswith((".provisional", ".c"))]
            self.assertEqual(len(provisional), 1, candidate)
            self.assertFalse(any(node.key in {"add_ideas", "add_country_leader_trait", "ADISCORD_superevent_enqueue"}
                                 for node in self.programme_nodes(provisional[0], candidate)))

    def test_law_rewards_keep_a_real_delta_when_the_law_is_already_active(self):
        laws = 0
        for focus_id, focus in self.focuses.items():
            if not focus_id.startswith("STP_pc_charter_"):
                continue
            reward = block(focus, "completion_reward")
            for index, node in enumerate(reward):
                if node.key != "if" or "add_ideas" not in {child.key for child in node.value}:
                    continue
                law = scalar(node.value, "add_ideas")
                self.assertTrue(law.startswith("ADISCORD_"), focus_id)
                self.assertEqual(scalar(block(block(node.value, "limit"), "NOT"), "has_idea"), law)
                fallback = reward[index + 1]
                self.assertEqual(fallback.key, "else", focus_id)
                self.assertGreater(float(scalar(fallback.value, "add_political_power")), 0)
                laws += 1
        self.assertGreaterEqual(laws, 15)

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
        self.assertGreaterEqual(constructions, 2)
        delayed = {
            "sotnikov": ("STP_pc_charter_sotnikov_settle_reintegration", {"industrial_complex"}),
            "shabrat": ("STP_pc_charter_shabrat_finish_compact", {"industrial_complex"}),
            "tikhoreva": ("STP_pc_charter_tikhoreva_finish_project", {"industrial_complex", "arms_factory"}),
        }
        for candidate, (effect, buildings) in delayed.items():
            payload = list(self.programme_nodes(block(self.effects, effect), candidate))
            delivered = {scalar(node.value, "type") for node in payload if node.key == "add_building_construction"}
            self.assertEqual(delivered, buildings, effect)
            capacities = {scalar(node.value, "building") for node in payload if node.key == "free_building_slots"}
            self.assertTrue(buildings <= capacities, effect)
            for node in payload:
                if node.key == "add_building_construction":
                    self.assertEqual(scalar(node.value, "level"), "1")
                    self.assertEqual(scalar(node.value, "instant_build"), "yes")
            self.assertIn("ADISCORD_economy_mark_dirty", {node.key for node in payload})

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
            if candidate != "tikhoreva":
                self.assertEqual(scalar(decision, "cost"), "0")
                self.assertEqual(scalar(decision, "days_remove"), "35")
                self.assertEqual(scalar(block(decision, "allowed"), "tag"), "STS")
                self.assertEqual(scalar(decision, "fire_only_once"), "no")
                self.assertTrue(scalar(decision, "custom_cost_text"))
                currencies = block(decision, "custom_cost_trigger")
                self.assertIn("has_political_power", {node.value for node in walk(currencies) if isinstance(node.value, str)})
                self.assertIn(str(price), {node.value for node in walk(currencies) if isinstance(node.value, str)})
                treasury = [node.value for node in walk(currencies) if node.key == "check_variable"
                            and scalar(node.value, "var") == "ADISCORD_economy_treasury"]
                self.assertEqual(len(treasury), 1)
                self.assertEqual(scalar(treasury[0], "value"), "600")
                self.assertEqual(scalar(treasury[0], "compare"), "greater_than_or_equals")
                payment = list(self.programme_nodes(block(decision, "complete_effect"), candidate))
                self.assertIn(str(-price), {node.value for node in payment if node.key == "add_political_power"})
                self.assertFalse(any(node.key in {"add_manpower", "add_building_construction"} for node in payment))
                settlement = list(self.programme_nodes(block(decision, "remove_effect"), candidate))
                self.assertIn("add_building_construction", {node.key for node in settlement})
                self.assertIn("ADISCORD_economy_mark_dirty", {node.key for node in settlement})
                cancellation = list(self.programme_nodes(block(decision, "cancel_effect"), candidate))
                self.assertIn("add_political_power", {node.key for node in cancellation})
                self.assertTrue(any(node.key == "add_to_variable" and scalar(node.value, "var") == "ADISCORD_economy_treasury"
                                    for node in cancellation))
                self.assertFalse(any(node.key == "add_building_construction" for node in cancellation))
                continue
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
                selectable = block(decision, "visible") + block(decision, "available")
                self.assertEqual(matches_conditions(selectable, facts, "STS"), current == candidate)
                facts["STS", "STP_pc_focus_available", "yes"] = False
                self.assertFalse(matches_conditions(selectable, facts, "STS"))
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

    def test_tikhoreva_decision_availability_names_public_conditions(self):
        def exposed_nodes(entries):
            for node in entries:
                if node.key == "custom_trigger_tooltip":
                    continue
                yield node
                if isinstance(node.value, list):
                    yield from exposed_nodes(node.value)

        prefix = "STP_pc_charter_tikhoreva_"
        for category in self.decisions:
            for decision in category.value:
                if not decision.key.startswith(prefix):
                    continue
                available = next((node.value for node in decision.value if node.key == "available"), [])
                raw = {node.key for node in exposed_nodes(available)}
                self.assertFalse(raw & {prefix + "work_current", prefix + "current", "has_country_flag", "check_variable"}, decision.key)
                if available:
                    self.assertIn("STP_pw_reconstruction_available_tt", {node.value for node in walk(available) if node.key == "tooltip"}, decision.key)

    def test_tikhoreva_independent_inspectors_unlock_faster_costlier_acceptance(self):
        prefix = "STP_pc_charter_tikhoreva_"
        reward = block(self.focuses[prefix + "limits_of_measurement"], "completion_reward")
        self.assertEqual(scalar(reward, "unlock_decision_tooltip"), prefix + "complete_acceptance")
        CharterTransactions.setUpClass()
        fixture = CharterTransactions()
        fixture.setUp()
        fixture.cabinet("tikhoreva")
        fixture.set_var(prefix + "project_kind", 10)
        fixture.mark("has_state_flag", prefix + "pilot_site", "2")
        fixture.mark("has_country_flag", prefix + "acceptance_open")
        options = {scalar(node.value, "name"): node.value for node in fixture.events["ADISCORD_STP_pc.67"] if node.key == "option"}
        self.assertFalse(fixture.conditions(block(options["ADISCORD_STP_pc.67.a"], "trigger")))
        self.assertTrue(fixture.conditions(block(options["ADISCORD_STP_pc.67.b"], "trigger")))
        fixture.mark("has_completed_focus", prefix + "limits_of_measurement")
        self.assertTrue(fixture.conditions(block(options["ADISCORD_STP_pc.67.a"], "trigger")))
        self.assertTrue(fixture.conditions(block(options["ADISCORD_STP_pc.67.b"], "trigger")))
        for name, price, days in (("complete_acceptance", 180, "28"), ("staged_acceptance", 120, "42")):
            decision = fixture.decisions[prefix + name]
            self.assertEqual(scalar(decision, "days_remove"), days)
            fixture.set_var("ADISCORD_economy_treasury", price)
            self.assertTrue(fixture.conditions(block(decision, "custom_cost_trigger")))
            fixture.set_var("ADISCORD_economy_treasury", price - 0.01)
            self.assertFalse(fixture.conditions(block(decision, "custom_cost_trigger")))

    def test_tikhoreva_norm_review_handles_either_focus_order_and_reopens_after_asset_loss(self):
        prefix = "STP_pc_charter_tikhoreva_"
        CharterTransactions.setUpClass()
        for focus_first in (True, False):
            with self.subTest(focus_first=focus_first):
                fixture = CharterTransactions()
                fixture.setUp()
                fixture.cabinet("tikhoreva")
                if focus_first:
                    fixture.mark("has_completed_focus", prefix + "public_results")
                fixture.set_var(prefix + "project_kind", 5)
                fixture.mark("has_state_flag", prefix + "pilot_site", "2")
                fixture.execute(fixture.effects[prefix + "finish_project"])
                if not focus_first:
                    self.assertFalse(any(key == "country_event" for _, key, _ in fixture.calls))
                    fixture.mark("has_completed_focus", prefix + "public_results")
                    decision = fixture.decisions[prefix + "reopen_norm_review"]
                    self.assertTrue(fixture.conditions(block(decision, "visible")))
                    self.assertTrue(fixture.conditions(block(decision, "available")))
                    fixture.decision(prefix + "reopen_norm_review")
                dispatches = [scalar(value, "id") for _, key, value in fixture.calls if key == "country_event"]
                self.assertEqual(dispatches, ["ADISCORD_STP_pc.85"])
                fixture.facts[("2", "controller")] = "VAL"
                close = next(node.value for node in fixture.events["ADISCORD_STP_pc.85"]
                             if node.key == "option" and scalar(node.value, "name") == "ADISCORD_STP_pc.5.closed")
                self.assertTrue(fixture.conditions(block(close, "trigger")))
                fixture.execute(close)
                self.assertNotIn(("STS", "has_country_flag", prefix + "norm_review_open"), fixture.facts)
                fixture.facts[("2", "controller")] = "STS"
                decision = fixture.decisions[prefix + "reopen_norm_review"]
                self.assertTrue(fixture.conditions(block(decision, "visible")))
                self.assertTrue(fixture.conditions(block(decision, "available")))
                fixture.decision(prefix + "reopen_norm_review")
                fixture.decision(prefix + "reopen_norm_review")
                dispatches = [scalar(value, "id") for _, key, value in fixture.calls if key == "country_event"]
                self.assertEqual(dispatches, ["ADISCORD_STP_pc.85", "ADISCORD_STP_pc.85"])

    def test_tikhoreva_abandon_returns_pending_pilot_after_cabinet_loss_without_touching_other_stages(self):
        prefix = "STP_pc_charter_tikhoreva_"
        CharterTransactions.setUpClass()
        fixture = CharterTransactions()
        fixture.setUp()
        fixture.cabinet("sotnikov")
        fixture.set_var(prefix + "deposit_treasury", 900)
        fixture.mark("has_country_flag", prefix + "acceptance_open")
        fixture.mark("has_state_flag", prefix + "pilot_site", "2")
        for kind in (1, 5, 9):
            fixture.set_var(prefix + "project_kind", kind)
            fixture.decision(prefix + "abandon_pilot")
            self.assertEqual(fixture.number(prefix + "deposit_treasury", "STS"), 900)
            self.assertEqual(fixture.number(prefix + "project_kind", "STS"), kind)
            self.assertEqual(fixture.number("ADISCORD_economy_treasury", "STS"), 5000)
        fixture.set_var(prefix + "project_kind", 10)
        self.assertTrue(fixture.conditions(block(fixture.decisions[prefix + "abandon_pilot"], "visible")))
        fixture.decision(prefix + "abandon_pilot")
        fixture.decision(prefix + "abandon_pilot")
        self.assertEqual(fixture.number("ADISCORD_economy_treasury", "STS"), 5900)
        self.assertEqual(fixture.number("ADISCORD_economy_current_month_action_income", "STS"), 900)
        self.assertNotIn(("STS", "variable", prefix + "project_kind"), fixture.facts)
        self.assertNotIn(("2", "has_state_flag", prefix + "pilot_site"), fixture.facts)
        self.assertIn(("STS", "has_country_flag", prefix + "acceptance_open"), fixture.facts)

    def test_new_story_events_are_registered_guarded_and_localisation_is_loadable(self):
        ledger_ids = {entry["id"] for entry in json.loads(read(LEDGER))["events"]}
        keys = set()
        descriptions = set()
        owners = {f"ADISCORD_STP_pc.{number}": candidate for candidate, numbers in self.STORY_EVENTS.items() for number in numbers}
        for event_id in ("ADISCORD_STP_pc.5", *owners):
            event = self.events[event_id]
            self.assertIn(event_id, ledger_ids)
            keys.add(scalar(event, "title"))
            self.assertEqual(scalar(event, "is_triggered_only"), "yes")
            self.assertEqual(scalar(event, "timeout_days"), "14")
            if event_id != "ADISCORD_STP_pc.5":
                candidate = owners[event_id]
                prefix = f"STP_pc_charter_{candidate}_"
                expanded = list(self.programme_nodes(event, candidate))
                self.assertIn(prefix + "current", {node.key for node in expanded})
                once = [node.value for node in event if node.key == "fire_only_once"]
                if once != ["yes"]:
                    guard = block(event, "trigger")
                    self.assertTrue(any(node.key in {"has_country_flag", "has_variable"} for node in walk(guard)), event_id)
                dispatchers = [
                    focus_id for focus_id, focus in self.focuses.items()
                    if focus_id.startswith(prefix)
                    and event_id in {scalar(node.value, "id") for node in walk(focus) if node.key == "country_event"}
                ]
                dispatchers.extend(
                    effect.key for effect in self.effects if effect.key.startswith(prefix)
                    and event_id in {scalar(node.value, "id") for node in walk(effect.value) if node.key == "country_event"}
                )
                self.assertEqual(len(dispatchers), 1, event_id)
                for node in expanded:
                    if node.key in {"add_ideas", "add_timed_idea"}:
                        idea = node.value if isinstance(node.value, str) else scalar(node.value, "idea")
                        keys.update((idea, idea + "_desc"))
            for node in event:
                if node.key == "desc":
                    key = scalar(node.value, "text") if isinstance(node.value, list) else node.value
                    descriptions.add(key)
                    keys.add(key)
            for node in walk(event):
                if node.key in {"name", "custom_effect_tooltip"} and isinstance(node.value, str):
                    keys.add(node.value)
        for first, final in self.TRAITS.values():
            keys.update((first, final))
        for focus_id in self.focuses:
            if focus_id.startswith("STP_pc_charter_"):
                keys.update((focus_id, focus_id + "_desc"))
                keys.update(node.value for node in walk(self.focuses[focus_id])
                            if node.key in {"tooltip", "custom_effect_tooltip"} and isinstance(node.value, str))
        for category in self.decisions:
            if not isinstance(category.value, list):
                continue
            for decision in category.value:
                if not decision.key.startswith("STP_pc_charter_") or not isinstance(decision.value, list):
                    continue
                keys.update((decision.key, decision.key + "_desc"))
                for node in walk(decision.value):
                    if node.key in {"tooltip", "custom_effect_tooltip"}:
                        keys.add(node.value)
                    elif node.key == "custom_cost_text":
                        keys.update((node.value, node.value + "_blocked", node.value + "_tooltip"))
        pilot_dispatch = block(self.effects, "STP_pc_charter_tikhoreva_finish_project")
        self.assertIn("ADISCORD_STP_pc.67", {scalar(node.value, "id") for node in walk(pilot_dispatch) if node.key == "country_event"})
        norm_dispatch = block(self.effects, "STP_pc_charter_tikhoreva_open_norm_review")
        self.assertIn("STP_pc_charter_tikhoreva_public_results", {node.value for node in walk(norm_dispatch) if node.key == "has_completed_focus"})
        self.assertIn("STP_pc_charter_tikhoreva_pilot_operational", {node.key for node in walk(norm_dispatch)})
        public_results = block(self.focuses["STP_pc_charter_tikhoreva_public_results"], "completion_reward")
        self.assertIn("STP_pc_charter_tikhoreva_reopen_norm_review",
                      {node.value for node in walk(public_results) if node.key == "unlock_decision_tooltip"})
        self.assertNotIn("STP_pc_charter_tikhoreva_open_norm_review", {node.key for node in walk(public_results)})
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = read(path) + "\n" + read(ROOT / f"localisation/{language}/ADISCORD_laws_l_{language}.yml")
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


class PostIvanovNarrativeTests(unittest.TestCase):
    """Story delivery and current-campaign guards, without native popup simulation."""

    STORIES = {
        "ADISCORD_STP_cw.100": ("STP_hw_leaflets_over_fada", "STS", "war"),
        "ADISCORD_STP_cw.101": ("STP_hw_council_of_passes", "STS", "war"),
        "ADISCORD_STP_cw.102": ("STP_hw_open_black_book", "STS", "war"),
        "ADISCORD_STP_cw.103": ("STP_hw_kefreyt_contract", "STS", "war"),
        "ADISCORD_STP_cw.104": ("STP_hw_mountains_pay", "STS", "war"),
        "ADISCORD_STP_cw.105": ("STP_hw_coalition_congress", "STS", "war"),
        "ADISCORD_STP_cw.110": ("STP_party_presidium_broadcast", "STP", "war"),
        "ADISCORD_STP_cw.111": ("STP_party_front_correspondents", "STP", "war"),
        "ADISCORD_STP_cw.112": ("STP_party_family_commissions", "STP", "war"),
        "ADISCORD_STP_cw.113": ("STP_party_regimental_organizers", "STP", "war"),
        "ADISCORD_STP_cw.114": ("STP_party_district_supply", "STP", "war"),
        "ADISCORD_STP_cw.115": ("STP_party_war_directorate", "STP", "war"),
        "ADISCORD_STP_pw.10": ("STP_pw_republic_district_authority", "STS", "postwar"),
        "ADISCORD_STP_pw.11": ("STP_pw_party_district_authority", "STP", "postwar"),
    }
    FOUNDER_SCENES = {"ADISCORD_STP_cw.101", "ADISCORD_STP_cw.105"}

    @classmethod
    def setUpClass(cls):
        cls.event_nodes = parse_clausewitz(read(EVENTS))
        cls.events = {
            scalar(node.value, "id"): node.value
            for node in cls.event_nodes if node.key == "country_event"
        }
        cls.triggers = {
            node.key: node.value
            for node in parse_clausewitz(read(
                ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
            )) if isinstance(node.value, list)
        }
        authored_tree = block(
            parse_clausewitz(render_source("STP/civil_war/focuses.txt")),
            "focus_tree",
        )
        cls.authored_focuses = [
            node.value for node in authored_tree
            if node.key == "focus" and isinstance(node.value, list)
        ]
        cls.native_focuses = [
            node.value for node in walk(parse_clausewitz(read(
                ROOT / "common/national_focus/ADISCORD_STP_civil_war.txt"
            ))) if node.key == "focus" and isinstance(node.value, list)
        ]

    def expanded_conditions(self, entries, stack=()):
        expanded = []
        for node in entries:
            if node.key in self.triggers:
                self.assertIn(node.value, ("yes", "no"))
                self.assertNotIn(node.key, stack)
                expanded.append(replace(
                    node,
                    key="AND" if node.value == "yes" else "NOT",
                    value=self.expanded_conditions(
                        self.triggers[node.key], stack + (node.key,)
                    ),
                ))
            elif isinstance(node.value, list):
                expanded.append(replace(
                    node, value=self.expanded_conditions(node.value, stack)
                ))
            else:
                expanded.append(node)
        return expanded

    def current_facts(self, event_id):
        focus_id, tag, phase = self.STORIES[event_id]
        facts = {
            (tag, "is_ai", "no"): True,
            (tag, "is_subject", "no"): True,
            (tag, "has_completed_focus", focus_id): True,
            ("STP", "exists", "yes"): True,
            ("STS", "exists", "yes"): True,
            ("STP", "has_capitulated", "no"): True,
            ("STS", "has_capitulated", "no"): True,
        }
        if phase == "war":
            facts["STP", "has_war_with", "STS"] = True
        else:
            facts[tag, "has_country_flag", "STP_cw_postwar"] = True
            facts[tag, "has_country_flag", "STP_cw_won_union_battle"] = True
            facts[tag, "has_global_flag", "STP_cw_union_wars_finished"] = True
        return facts

    def test_stories_are_registered_once_and_have_no_gameplay_payload(self):
        ledger = json.loads(read(LEDGER))["events"]
        event_fields = {
            "id", "title", "desc", "picture", "is_triggered_only",
            "fire_only_once", "trigger", "option",
        }
        for event_id in self.STORIES:
            with self.subTest(event=event_id):
                definitions = [
                    node.value for node in self.event_nodes
                    if node.key == "country_event"
                    and scalar(node.value, "id") == event_id
                ]
                self.assertEqual(len(definitions), 1)
                event = definitions[0]
                self.assertEqual(scalar(event, "is_triggered_only"), "yes")
                self.assertEqual(scalar(event, "fire_only_once"), "yes")
                self.assertEqual({node.key for node in event}, event_fields)
                options = [node.value for node in event if node.key == "option"]
                self.assertEqual(len(options), 1)
                self.assertEqual({node.key for node in options[0]}, {"name"})
                self.assertEqual(scalar(options[0], "name"), f"{event_id}.a")
                entries = [entry for entry in ledger if entry["id"] == event_id]
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["owner"], "events/ADISCORD_STP_events.txt")
                self.assertEqual(entries[0]["status"], "active")

    def test_each_story_has_one_hidden_deferred_focus_call_in_source_and_output(self):
        def dispatches(entries, hidden=False):
            for node in entries:
                if node.key == "effect_tooltip":
                    continue
                if node.key == "country_event":
                    yield node.value, hidden
                elif isinstance(node.value, list):
                    yield from dispatches(
                        node.value, hidden or node.key == "hidden_effect"
                    )

        for source, focuses in (
            ("authored", self.authored_focuses), ("native", self.native_focuses)
        ):
            calls = {event_id: [] for event_id in self.STORIES}
            for focus in focuses:
                for payload, hidden in dispatches(block(focus, "completion_reward")):
                    event_id = scalar(payload, "id")
                    if event_id in calls:
                        calls[event_id].append((
                            scalar(focus, "id"),
                            {node.key: node.value for node in payload},
                            hidden,
                        ))
            for event_id, (focus_id, _, _) in self.STORIES.items():
                with self.subTest(source=source, event=event_id):
                    self.assertEqual(calls[event_id], [(
                        focus_id, {"id": event_id, "days": "1"}, True,
                    )])

    def test_story_guards_follow_the_current_side_phase_and_human_country(self):
        for event_id, (focus_id, tag, phase) in self.STORIES.items():
            trigger = self.expanded_conditions(block(self.events[event_id], "trigger"))
            facts = self.current_facts(event_id)
            with self.subTest(event=event_id):
                self.assertTrue(matches_conditions(trigger, facts, tag))
                self.assertFalse(matches_conditions(trigger, facts, "VAL"))
                self.assertFalse(matches_conditions(trigger, facts | {
                    (tag, "has_completed_focus", focus_id): False,
                }, tag))
                self.assertFalse(matches_conditions(trigger, facts | {
                    (tag, "is_ai", "no"): False,
                    (tag, "is_ai", "yes"): True,
                }, tag))
                self.assertFalse(matches_conditions(trigger, facts | {
                    (tag, "has_capitulated", "no"): False,
                    (tag, "has_capitulated", "yes"): True,
                }, tag))
                if phase == "war":
                    self.assertFalse(matches_conditions(trigger, facts | {
                        ("STP", "has_war_with", "STS"): False,
                        (tag, "has_war_with", "VAL"): True,
                    }, tag))
                    self.assertFalse(matches_conditions(trigger, facts | {
                        (tag, "has_country_flag", "STP_cw_postwar"): True,
                    }, tag))
                    if tag == "STS":
                        self.assertFalse(matches_conditions(trigger, facts | {
                            ("STP", "has_capitulated", "no"): False,
                            ("STP", "has_capitulated", "yes"): True,
                        }, tag))
                    else:
                        self.assertFalse(matches_conditions(trigger, facts | {
                            (tag, "has_global_flag", "STP_cw_union_wars_finished"): True,
                        }, tag))
                else:
                    for flag, kind in (
                        ("STP_cw_postwar", "has_country_flag"),
                        ("STP_cw_union_wars_finished", "has_global_flag"),
                    ):
                        self.assertFalse(matches_conditions(trigger, facts | {
                            (tag, kind, flag): False,
                        }, tag))
                    self.assertTrue(matches_conditions(trigger, facts | {
                        (tag, "has_war_with", "VAL"): True,
                    }, tag))

    def test_reconstruction_story_allows_the_restored_dependent_party(self):
        event_id = "ADISCORD_STP_pw.11"
        trigger = self.expanded_conditions(block(self.events[event_id], "trigger"))
        facts = self.current_facts(event_id) | {
            ("STP", "has_country_flag", "STP_cw_won_union_battle"): False,
            ("STP", "has_country_flag", "STP_ps_restored_dependency"): True,
            ("STP", "is_subject", "no"): False,
            ("STP", "is_subject", "yes"): True,
            ("STP", "is_subject_of", "NOD"): True,
        }
        self.assertTrue(matches_conditions(trigger, facts, "STP"))
        self.assertFalse(matches_conditions(trigger, facts | {
            ("STP", "has_country_flag", "STP_ps_restored_dependency"): False,
        }, "STP"))

    def test_founder_scenes_do_not_speak_for_an_absent_shabrat(self):
        for event_id in self.FOUNDER_SCENES:
            descriptions = [
                node.value for node in self.events[event_id] if node.key == "desc"
            ]
            self.assertEqual(len(descriptions), 2)
            for leader, suffix in (
                ("STP_maksim_shabrat", "d"),
                ("STP_grigory_sotnikov", "absent"),
                (None, "absent"),
            ):
                with self.subTest(event=event_id, leader=leader):
                    facts = {("STS", "ruling_leader"): leader}
                    selected = [
                        scalar(desc, "text") for desc in descriptions
                        if matches_conditions(
                            self.expanded_conditions(block(desc, "trigger")),
                            facts,
                            "STS",
                        )
                    ]
                    self.assertEqual(selected, [f"{event_id}.{suffix}"])

    def test_story_localisation_loads_in_both_languages_within_page_limits(self):
        keys = set()
        descriptions = set()
        for event_id in self.STORIES:
            event = self.events[event_id]
            keys.add(scalar(event, "title"))
            keys.add(scalar(block(event, "option"), "name"))
            if event_id not in self.FOUNDER_SCENES:
                self.assertEqual(scalar(event, "desc"), f"{event_id}.d")
            for node in event:
                if node.key == "desc":
                    key = scalar(node.value, "text") if isinstance(node.value, list) else node.value
                    keys.add(key)
                    descriptions.add(key)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            source = read(path)
            values = {}
            for line in source.splitlines():
                match = re.fullmatch(r'\s*([^\s:]+):\d*\s*"((?:[^"\\]|\\.)*)"', line)
                if match:
                    values[match[1]] = match[2]

            def expand(key, stack=()):
                self.assertNotIn(key, stack)
                self.assertIn(key, values, "Missing or malformed quoted localisation")
                return re.sub(
                    r"\$([^$]+)\$",
                    lambda match: expand(match[1], stack + (key,)),
                    values[key],
                ).replace(r"\n", "\n")

            for key in keys:
                with self.subTest(language=language, key=key):
                    self.assertEqual(source.count(f"\n {key}:"), 1)
                    value = expand(key)
                    self.assertTrue(value.strip())
                    self.assertNotRegex(value, "[\u2013\u2014]")
                    if key in descriptions:
                        self.assertLessEqual(len(value), 3000)
                        self.assertLessEqual(len(value.encode("utf-8")), 5500)
                        self.assertNotIn("§Y", value)


class CharterTransactions(unittest.TestCase):
    """Execute the bounded charter payment paths; this is not a native engine test."""

    @classmethod
    def setUpClass(cls):
        cls.effects = {n.key: n.value for n in parse_clausewitz(read(
            ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
        ))}
        cls.triggers = {n.key: n.value for n in parse_clausewitz(read(
            ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
        ))}
        categories = parse_clausewitz(read(ROOT / "common/decisions/ADISCORD_STP_decisions.txt"))
        cls.decisions = {n.key: n.value for c in categories for n in c.value}
        cls.events = {scalar(n.value, "id"): n.value for n in parse_clausewitz(read(EVENTS))
                      if n.key == "country_event"}

    def setUp(self):
        self.facts = {}
        self.calls = []
        self.target = "2"
        self.states = ("2", "3")
        self.set_value("has_political_power", 500)
        self.set_var("ADISCORD_economy_treasury", 5000)
        for state in self.states:
            self.facts[(state, "owner")] = "STS"
            self.facts[(state, "controller")] = "STS"
            self.facts[(state, "slots", "industrial_complex")] = 3
            self.facts[(state, "slots", "arms_factory")] = 3
        self.facts[("STS", "external", "STP_pc_focus_available")] = True

    def set_var(self, name, value, scope="STS"):
        self.facts[(scope, "variable", name)] = value

    def set_value(self, name, value, scope="STS"):
        self.facts[(scope, "numeric", name)] = value

    def mark(self, kind, name, scope="STS"):
        self.facts[(scope, kind, name)] = True

    def number(self, value, scope):
        try:
            return float(value)
        except ValueError:
            return self.facts.get((scope, "variable", value.removeprefix("var:")), 0)

    def groups(self, nodes):
        index = 0
        while index < len(nodes):
            length = 1 if nodes[index].key else 3
            yield nodes[index:index + length]
            index += length

    def compare(self, left, op, right):
        return {"=": left == right, "<": left < right, ">": left > right,
                "<=": left <= right, ">=": left >= right}[op]

    def scope(self, name, current):
        return {"ROOT": "STS", "FROM": self.target, "PREV": "STS"}.get(name, name)

    def conditions(self, nodes, scope="STS"):
        for group in self.groups(nodes):
            node = group[0]
            key, value = node.key, node.value
            if not key:
                name, op, threshold = (n.value for n in group)
                result = self.compare(self.facts.get((scope, "numeric", name), 0),
                                      op, self.number(threshold, scope))
            elif (scope, "external", key) in self.facts:
                result = self.facts[(scope, "external", key)] == (value == "yes")
            elif key in self.triggers:
                result = self.conditions(self.triggers[key], scope) == (value == "yes")
            elif key in ("AND", "hidden_trigger", "custom_trigger_tooltip"):
                result = self.conditions(value, scope)
            elif key in ("OR", "NOT"):
                result = any(self.conditions(g, scope) for g in self.groups(value))
                if key == "NOT":
                    result = not result
            elif key == "any_owned_state":
                result = any(self.facts[(s, "owner")] == scope and self.conditions(value, s)
                             for s in self.states)
            elif key in ("ROOT", "FROM", "PREV", "STS", "VAL", "NOD"):
                result = self.conditions(value, self.scope(key, scope))
            elif key == "check_variable":
                op = {"equals": "=", "greater_than": ">", "less_than": "<",
                      "greater_than_or_equals": ">=", "less_than_or_equals": "<="}[scalar(value, "compare")]
                result = self.compare(self.number(scalar(value, "var"), scope), op,
                                      self.number(scalar(value, "value"), scope))
            elif key == "has_variable":
                result = (scope, "variable", value) in self.facts
            elif key == "has_country_leader":
                result = self.facts.get((scope, "leader")) == scalar(value, "character")
            elif key == "tag":
                result = scope == value
            elif key in ("is_owned_by", "is_controlled_by"):
                field = "owner" if key == "is_owned_by" else "controller"
                result = self.facts.get((scope, field)) == self.scope(value, scope)
            elif key == "free_building_slots":
                building = scalar(value, "building")
                result = self.facts.get((scope, "slots", building), 0) > 0
            elif key == "has_equipment":
                equipment, op, amount = (n.value for n in value)
                result = self.compare(self.facts.get((scope, "equipment", equipment), 0),
                                      op, self.number(amount, scope))
            elif key == "always":
                result = value == "yes"
            elif key in ("tooltip",):
                result = True
            elif isinstance(value, str):
                result = self.facts.get((scope, key, value), False)
            else:
                raise AssertionError(f"Unsupported charter condition: {key}")
            if not result:
                return False
        return True

    def execute(self, nodes, scope="STS"):
        taken = False
        for node in nodes:
            key, value = node.key, node.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                if not taken and (key == "else" or self.conditions(block(value, "limit"), scope)):
                    taken = True
                    self.execute([n for n in value if n.key != "limit"], scope)
            elif key == "hidden_effect":
                self.execute(value, scope)
            elif key in ("effect_tooltip", "custom_effect_tooltip", "unlock_decision_tooltip",
                         "name", "trigger", "ai_chance"):
                continue
            elif key in ("ROOT", "FROM", "STS", "VAL", "NOD"):
                self.execute(value, self.scope(key, scope))
            elif key in ("random_owned_controlled_state", "every_owned_state", "every_state"):
                for state in self.states:
                    owned = self.facts[(state, "owner")] == scope
                    controlled = self.facts[(state, "controller")] == scope
                    if key != "every_state" and not (owned and controlled):
                        continue
                    if self.conditions(block(value, "limit"), state):
                        self.execute([n for n in value if n.key != "limit"], state)
                        if key.startswith("random"):
                            break
            elif key in ("set_variable", "set_temp_variable", "add_to_variable", "subtract_from_variable",
                         "multiply_temp_variable"):
                explicit = any(n.key == "var" for n in value)
                variable = scalar(value, "var") if explicit else value[0].key
                amount = self.number(scalar(value, "value") if explicit else value[0].value, scope)
                old = self.number(variable, scope)
                if key == "add_to_variable":
                    amount += old
                elif key == "subtract_from_variable":
                    amount = old - amount
                elif key == "multiply_temp_variable":
                    amount *= old
                self.set_var(variable, amount, scope)
            elif key == "clear_variable":
                self.facts.pop((scope, "variable", value), None)
            elif key in ("set_country_flag", "clr_country_flag", "set_state_flag", "clr_state_flag"):
                kind = "has_state_flag" if "state" in key else "has_country_flag"
                if key.startswith("set"):
                    self.mark(kind, value, scope)
                else:
                    self.facts.pop((scope, kind, value), None)
            elif key in ("add_ideas", "remove_ideas", "add_timed_idea"):
                idea = scalar(value, "idea") if isinstance(value, list) else value
                if key == "remove_ideas":
                    self.facts.pop((scope, "has_idea", idea), None)
                else:
                    self.mark("has_idea", idea, scope)
            elif key == "add_equipment_to_stockpile":
                equipment = scalar(value, "type")
                old = self.facts.get((scope, "equipment", equipment), 0)
                self.facts[(scope, "equipment", equipment)] = old + self.number(scalar(value, "amount"), scope)
            elif key == "add_building_construction":
                building = scalar(value, "type")
                amount = self.number(scalar(value, "level"), scope)
                self.facts[(scope, "slots", building)] -= amount
                self.set_value(building, self.facts.get((scope, "numeric", building), 0) + amount, scope)
            elif key in ("add_political_power", "add_stability", "army_experience", "add_command_power"):
                field = "has_political_power" if key == "add_political_power" else key
                self.set_value(field, self.facts.get((scope, "numeric", field), 0) + self.number(value, scope), scope)
            elif key.startswith("STP_pc_") and key in self.effects:
                self.execute(self.effects[key], scope)
            elif key in ("ADISCORD_economy_mark_dirty", "ADISCORD_superevent_enqueue", "country_event",
                         "remove_country_leader_trait", "add_country_leader_trait", "set_cosmetic_tag",
                         "add_tech_bonus", "ADISCORD_reform_social_system_development"):
                self.calls.append((scope, key, value))
            else:
                raise AssertionError(f"Unsupported charter effect: {key}")

    def cabinet(self, name):
        value, leader = {"sotnikov": (1, "STP_grigory_sotnikov"),
                         "shabrat": (2, "STP_maksim_shabrat"),
                         "tikhoreva": (3, "STP_vera_tikh")}[name]
        self.set_var("STP_pc_charter_cabinet", value)
        self.facts[("STS", "leader")] = leader

    def decision(self, name, stage="complete_effect"):
        self.execute(block(self.decisions[name], stage))

    def test_shabrat_exact_cost_shared_slot_wrong_target_and_single_delivery(self):
        self.cabinet("shabrat")
        name = "STP_pc_charter_shabrat_civic_grants"
        self.mark("has_completed_focus", "STP_pc_charter_shabrat_district_grants")
        self.set_value("has_political_power", 75)
        self.set_var("ADISCORD_economy_treasury", 600)
        self.assertTrue(self.conditions(block(self.decisions[name], "custom_cost_trigger")))
        self.set_var("ADISCORD_economy_treasury", 599.99)
        self.decision(name)
        self.assertFalse(("STS", "variable", "STP_pc_charter_shabrat_project_kind") in self.facts)
        self.set_var("ADISCORD_economy_treasury", 600)
        self.decision(name)
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 0)
        self.target = "3"
        self.assertFalse(self.conditions(block(self.decisions[name], "available")))
        self.decision(name, "remove_effect")
        self.assertEqual(self.number("STP_pc_charter_shabrat_deposit", "STS"), 600)
        self.target = "2"
        self.decision(name, "remove_effect")
        self.decision(name, "cancel_effect")
        self.decision(name, "remove_effect")
        self.assertEqual(self.facts[("2", "numeric", "industrial_complex")], 1)
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 0)

    def test_shabrat_territory_loss_returns_both_currencies_once(self):
        self.cabinet("shabrat")
        self.mark("has_completed_focus", "STP_pc_charter_shabrat_district_grants")
        name = "STP_pc_charter_shabrat_civic_grants"
        self.decision(name)
        self.facts[("2", "controller")] = "VAL"
        self.assertTrue(self.conditions(block(self.decisions[name], "cancel_trigger")))
        self.decision(name, "cancel_effect")
        self.decision(name, "remove_effect")
        self.decision(name, "cancel_effect")
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 5000)
        self.assertEqual(self.facts[("STS", "numeric", "has_political_power")], 500)
        self.assertEqual(self.number("ADISCORD_economy_current_month_action_income", "STS"), 600)

    def test_sotnikov_factory_loss_refund_and_supply_cabinet_change(self):
        self.cabinet("sotnikov")
        self.mark("has_completed_focus", "STP_pc_charter_sotnikov_civil_return")
        name = "STP_pc_charter_sotnikov_reintegration"
        self.decision(name)
        for state in self.states:
            self.facts[(state, "slots", "industrial_complex")] = 0
        self.decision(name, "remove_effect")
        self.decision(name, "cancel_effect")
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 5000)
        self.assertEqual(self.facts[("STS", "numeric", "has_political_power")], 500)
        self.mark("has_completed_focus", "STP_pc_charter_sotnikov_rescue_stores")
        self.mark("has_idea", "ADISCORD_logistics_civilian_contracts")
        name = "STP_pc_charter_sotnikov_supply_contract"
        self.decision(name)
        self.cabinet("shabrat")
        self.decision(name, "remove_effect")
        self.decision(name, "cancel_effect")
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 5000)
        self.assertFalse(("STS", "equipment", "support_equipment") in self.facts)

    def test_tikhoreva_receipt_covers_construction_and_acceptance(self):
        self.cabinet("tikhoreva")
        prefix = "STP_pc_charter_tikhoreva_"
        self.mark("has_state_flag", prefix + "pilot_site", "2")
        for kind, cash in ((3, 900), (5, 180)):
            for field, amount in (("kind", kind), ("treasury", cash), ("pp", 0), ("equipment", 0)):
                self.set_var(prefix + "input_" + field, amount)
            self.execute(self.effects[prefix + "pay_project"])
            if kind == 3:
                self.execute(self.effects[prefix + "finish_project"])
                self.assertEqual(self.number(prefix + "project_kind", "STS"), 10)
                self.assertEqual(self.number(prefix + "deposit_treasury", "STS"), 900)
                self.assertFalse(self.conditions(self.triggers[prefix + "project_idle"]))
        self.assertEqual(self.number(prefix + "deposit_treasury", "STS"), 1080)
        self.facts[("2", "owner")] = "VAL"
        self.execute(self.effects[prefix + "finish_project"])
        self.execute(self.effects[prefix + "cancel_project"])
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 5000)
        self.assertFalse(("2", "has_state_flag", prefix + "pilot_site") in self.facts)

    def test_tikhoreva_actual_factory_only_after_acceptance_and_no_replay(self):
        self.cabinet("tikhoreva")
        prefix = "STP_pc_charter_tikhoreva_"
        self.set_var(prefix + "project_kind", 6)
        self.set_var(prefix + "deposit_treasury", 840)
        self.mark("has_state_flag", prefix + "pilot_site", "2")
        self.execute(self.effects[prefix + "finish_project"])
        self.execute(self.effects[prefix + "finish_project"])
        self.execute(self.effects[prefix + "cancel_project"])
        self.assertEqual(self.facts[("2", "numeric", "industrial_complex")], 1)
        self.assertTrue(self.conditions(self.triggers[prefix + "pilot_operational"]))
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 5000)

    def test_shabrat_late_final_requires_all_obligations_and_only_one_award(self):
        self.cabinet("shabrat")
        prefix = "STP_pc_charter_shabrat_"
        self.mark("has_completed_focus", prefix + "charter_fulfilled")
        self.set_var(prefix + "registers", 1)
        self.set_var(prefix + "oath", 1)
        self.set_var(prefix + "voice", 2)
        self.mark("has_state_flag", prefix + "compact", "2")
        self.execute(self.effects[prefix + "award_districts"])
        self.assertFalse(any(c[1] == "ADISCORD_superevent_enqueue" for c in self.calls))
        self.set_value("industrial_complex", 1, "2")
        self.execute(self.effects[prefix + "award_districts"])
        self.execute(self.effects[prefix + "award_districts"])
        self.mark("has_country_flag", prefix + "defence_delivered")
        self.execute(self.effects[prefix + "award_nation"])
        self.assertEqual(sum(c[1] == "ADISCORD_superevent_enqueue" for c in self.calls), 1)
        self.assertTrue(self.facts[("STS", "has_idea", prefix + "legacy_districts")])

    def test_paid_programmes_reject_fractional_shortages(self):
        cases = {
            "sotnikov_reintegration": (60, 600, 0),
            "sotnikov_complete_social": (50, 300, 0),
            "sotnikov_settle_labour": (40, 300, 0),
            "sotnikov_supply_contract": (0, 300, 0),
            "shabrat_civic_grants": (75, 600, 0),
            "shabrat_complete_registers": (40, 0, 0),
            "shabrat_review_citizenship": (50, 0, 0),
            "shabrat_defence_contract": (35, 300, 0),
            "tikhoreva_public_audit": (40, 0, 0),
            "tikhoreva_professional_audit": (0, 300, 0),
            "tikhoreva_contract_pilot": (0, 900, 0),
            "tikhoreva_standard_pilot": (0, 720, 0),
            "tikhoreva_complete_acceptance": (0, 180, 0),
            "tikhoreva_staged_acceptance": (0, 120, 0),
            "tikhoreva_revise_norm": (30, 0, 0),
            "tikhoreva_verify_norm": (0, 300, 0),
            "tikhoreva_replicate_pilot": (0, 450, 100),
        }
        fields = (("STS", "numeric", "has_political_power"),
                  ("STS", "variable", "ADISCORD_economy_treasury"),
                  ("STS", "equipment", "support_equipment"))
        for suffix, prices in cases.items():
            condition = block(self.decisions["STP_pc_charter_" + suffix], "custom_cost_trigger")
            for field, price in zip(fields, prices):
                self.facts[field] = price
            with self.subTest(programme=suffix, boundary="exact"):
                self.assertTrue(self.conditions(condition))
            for field, price in zip(fields, prices):
                if not price:
                    continue
                with self.subTest(programme=suffix, resource=field):
                    self.facts[field] = price - 0.01
                    self.assertFalse(self.conditions(condition))
                    self.facts[field] = price

    def test_tikhoreva_replication_returns_equipment_and_cash_once(self):
        self.cabinet("tikhoreva")
        prefix = "STP_pc_charter_tikhoreva_"
        self.facts[("STS", "equipment", "support_equipment")] = 100
        self.mark("has_state_flag", prefix + "replication_site", "3")
        for field, amount in (("kind", 9), ("treasury", 450), ("pp", 0), ("equipment", 100)):
            self.set_var(prefix + "input_" + field, amount)
        self.execute(self.effects[prefix + "pay_project"])
        self.assertEqual(self.facts[("STS", "equipment", "support_equipment")], 0)
        self.cabinet("shabrat")
        self.execute(self.effects[prefix + "finish_project"])
        self.execute(self.effects[prefix + "cancel_project"])
        self.assertEqual(self.facts[("STS", "equipment", "support_equipment")], 100)
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 5000)
        self.assertEqual(self.number("ADISCORD_economy_current_month_action_income", "STS"), 450)

    def test_sotnikov_each_unfulfilled_promise_blocks_final(self):
        self.cabinet("sotnikov")
        prefix = "STP_pc_charter_sotnikov_"
        for suffix in ("command_ruling", "prison_ruling", "labour_agreement"):
            self.set_var(prefix + suffix, 1)
        for suffix in ("reintegration_done", "second_social_done", "supply_delivered"):
            self.mark("has_country_flag", prefix + suffix)
        for idea in ("ADISCORD_internal_security_civilian_oversight", "ADISCORD_labor_policy_collective_bargaining",
                     "ADISCORD_logistics_civilian_contracts", "ADISCORD_military_organization_cadre_army"):
            self.mark("has_idea", idea)
        for suffix in ("professional_service", "charter_fulfilled"):
            self.mark("has_completed_focus", prefix + suffix)
        required = [("STS", "variable", prefix + n) for n in ("command_ruling", "prison_ruling", "labour_agreement")]
        required += [("STS", "has_country_flag", prefix + n) for n in ("reintegration_done", "second_social_done", "supply_delivered")]
        required += [("STS", "has_idea", "ADISCORD_military_organization_cadre_army")]
        for key in required:
            with self.subTest(missing=key):
                original = self.facts.pop(key)
                self.execute(self.effects[prefix + "confirm_legacy"])
                self.assertFalse(any(c[1] == "ADISCORD_superevent_enqueue" for c in self.calls))
                self.facts[key] = original
        self.execute(self.effects[prefix + "confirm_legacy"])
        self.execute(self.effects[prefix + "confirm_legacy"])
        self.assertEqual(sum(c[1] == "ADISCORD_superevent_enqueue" for c in self.calls), 1)

    def test_tikhoreva_final_stale_answer_cannot_award_second_legacy(self):
        self.cabinet("tikhoreva")
        prefix = "STP_pc_charter_tikhoreva_"
        for flag in ("audit_completed", "norms_corrected", "replication_completed", "final_review_open"):
            self.mark("has_country_flag", prefix + flag)
        self.mark("has_state_flag", prefix + "pilot_operational", "2")
        self.set_value("industrial_complex", 1, "2")
        options = {scalar(n.value, "name"): n.value for n in self.events["ADISCORD_STP_pc.70"] if n.key == "option"}
        self.execute(options["ADISCORD_STP_pc.70.b"])
        self.execute(options["ADISCORD_STP_pc.70.a"])
        self.execute(options["ADISCORD_STP_pc.70.b"])
        self.assertEqual(sum(c[1] == "ADISCORD_superevent_enqueue" for c in self.calls), 1)
        self.assertTrue(self.facts[("STS", "has_idea", prefix + "legacy_utility")])
        self.assertFalse(("STS", "has_idea", prefix + "legacy_ledger") in self.facts)

    def test_partner_acceptance_pays_once_and_delivers_only_to_recipient(self):
        self.cabinet("shabrat")
        self.mark("has_country_flag", "STP_pc_lib_package_pending")
        self.set_var("STP_pc_lib_package_tag", 1)
        self.set_var("STP_pc_lib_package_cabinet", 2)
        self.mark("exists", "yes")
        self.facts[("VAL", "external", "STP_pc_liberation_recipient_available")] = True
        self.set_var("ADISCORD_economy_treasury", 300)
        option = next(n.value for n in self.events["ADISCORD_STP_pc.11"]
                      if n.key == "option" and scalar(n.value, "name") == "ADISCORD_STP_pc.11.a")
        self.execute(block(option, "hidden_effect"), "VAL")
        self.execute(block(option, "hidden_effect"), "VAL")
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 0)
        self.assertEqual(self.facts[("VAL", "equipment", "infantry_equipment")], 900)
        self.assertEqual(self.facts[("VAL", "equipment", "support_equipment")], 150)
        self.assertFalse(("STS", "equipment", "infantry_equipment") in self.facts)
        self.assertEqual(self.number("ADISCORD_economy_current_month_action_costs", "STS"), 300)

    def test_partner_acceptance_spent_budget_releases_receipt_without_delivery(self):
        self.cabinet("shabrat")
        self.mark("has_country_flag", "STP_pc_lib_package_pending")
        self.set_var("STP_pc_lib_package_tag", 1)
        self.set_var("STP_pc_lib_package_cabinet", 2)
        self.mark("exists", "yes")
        self.facts[("VAL", "external", "STP_pc_liberation_recipient_available")] = True
        self.set_var("ADISCORD_economy_treasury", 299)
        option = next(n.value for n in self.events["ADISCORD_STP_pc.11"]
                      if n.key == "option" and scalar(n.value, "name") == "ADISCORD_STP_pc.11.a")
        self.execute(block(option, "hidden_effect"), "VAL")
        self.assertFalse(("STS", "has_country_flag", "STP_pc_lib_package_pending") in self.facts)
        self.assertEqual(self.number("ADISCORD_economy_treasury", "STS"), 299)
        self.assertFalse(("VAL", "equipment", "infantry_equipment") in self.facts)


if __name__ == "__main__":
    unittest.main()
