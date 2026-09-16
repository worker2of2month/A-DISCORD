from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "events/ADISCORD_STP_events.txt"
FOCUSES = ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
LOCALISATION = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
LEDGER = ROOT / "tools/data/adiscord_event_ids.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


def focus_block(text: str, focus_id: str) -> str:
    marker = f"\t\tid = {focus_id}\n"
    start = text.index(marker)
    next_focus = text.find("\n\tfocus = {", start + len(marker))
    return text[start:] if next_focus == -1 else text[start:next_focus]


class ShabratPostwarStoryTests(unittest.TestCase):
    def test_story_events_are_registered_and_hooked_to_postwar_focuses(self) -> None:
        events = read(EVENTS)
        focuses = read(FOCUSES)
        ledger = json.loads(read(LEDGER))

        expected = {
            "ADISCORD_STP_pw.1": "STP_pw_republic_new_republic",
            "ADISCORD_STP_pw.2": "STP_pw_republic_civil_records",
            "ADISCORD_STP_pw.3": "STP_pw_republic_civil_charter",
        }

        self.assertIn("add_namespace = ADISCORD_STP_pw", events)
        ledger_ids = {entry["id"] for entry in ledger["ids"]}
        for event_id, focus_id in expected.items():
            self.assertEqual(events.count(f"id = {event_id}"), 1)
            self.assertIn(event_id, focus_block(focuses, focus_id))
            self.assertIn(event_id, ledger_ids)

    def test_story_events_have_complete_russian_localisation(self) -> None:
        loc = read(LOCALISATION)
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
        )
        for key in expected_keys:
            self.assertEqual(loc.count(f"\n {key}:"), 1, key)


if __name__ == "__main__":
    unittest.main()
