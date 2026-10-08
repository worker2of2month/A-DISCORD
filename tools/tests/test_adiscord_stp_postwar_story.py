from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source

from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.tests.test_adiscord_stp_preparation import block, scalar, walk, matches_conditions


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
            ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
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
        for option in (node.value for node in self.events["ADISCORD_STP_pc.7"] if node.key == "option"):
            hidden = block(option, "hidden_effect")
            self.assertEqual([scalar(node.value, "id") for node in walk(hidden) if node.key == "country_event"], ["ADISCORD_STP_pc.62"])
            condition = block(block(hidden, "if"), "limit")
            self.assertTrue(matches_conditions(condition, {("STS", "variable", "STP_pc_course"): 4}, "STS"))
            self.assertFalse(matches_conditions(condition, {("STS", "variable", "STP_pc_course"): 2}, "STS"))

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


if __name__ == "__main__":
    unittest.main()
