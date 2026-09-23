from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


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
        for filename in ("ADISCORD_STP_story_l_russian.yml", "ADISCORD_STP_postwar_story_l_russian.yml"):
            self.assertFalse((ROOT / "localisation/replace" / filename).exists(), filename)
        self.assertTrue(POSTWAR_LOCALISATION.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_story_events_are_registered_and_trigger_from_postwar_focus_completion(self) -> None:
        events = read(EVENTS)
        ledger = json.loads(read(LEDGER))
        focus_source = read(ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt")
        focuses = {
            next(field.value for field in node.value if field.key == "id"): node.value
            for tree in parse_clausewitz(focus_source) if tree.key == "focus_tree"
            for node in tree.value if node.key == "focus"
        }

        def dispatches(entries, hidden=False):
            for node in entries:
                if node.key == "effect_tooltip":
                    continue
                if node.key == "country_event":
                    yield {field.key: field.value for field in node.value}, hidden
                elif isinstance(node.value, list):
                    yield from dispatches(node.value, hidden or node.key == "hidden_effect")

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
            reward = next(node.value for node in focuses[focus_id] if node.key == "completion_reward")
            calls = [(payload, hidden) for payload, hidden in dispatches(reward)
                     if payload.get("id") == event_id]
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


if __name__ == "__main__":
    unittest.main()
