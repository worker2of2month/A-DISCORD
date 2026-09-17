from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
EVENTS = ROOT / "events/ADISCORD_STP_events.txt"
LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


def closing_brace(text: str, opening: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        ch = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise AssertionError("unterminated block")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    opening = text.index("{", match.start(), match.end())
    return text[match.start() : closing_brace(text, opening)]


def event_block(text: str, event_id: str) -> str:
    marker = f"\tid = {event_id}\n"
    id_pos = text.index(marker)
    start = text.rfind("country_event = {", 0, id_pos)
    if start < 0:
        raise AssertionError(event_id)
    opening = text.index("{", start)
    return text[start : closing_brace(text, opening)]


class StelanderNodStaleInterventionTests(unittest.TestCase):
    def test_last_banquet_success_is_a_durable_intervention_blocker(self) -> None:
        effects = read(EFFECTS)
        success = named_block(effects, "STP_cw_resolve_last_banquet_success")
        cancel = named_block(effects, "STP_cw_cancel_pending_nod_intervention")

        self.assertIn("set_country_flag = STP_cw_last_banquet_success", success)
        self.assertIn("STP_cw_cancel_pending_nod_intervention = yes", success)
        self.assertIn("NOT = { has_country_flag = NOD_cw_entered }", cancel)
        self.assertIn("NOD_cw_intervention_preparation", cancel)
        self.assertIn("NOD_cw_northern_redeployment", cancel)
        self.assertIn("STP_cw_nod_warning", cancel)
        self.assertIn("STP_cw_nod_redeployment", cancel)

        possible = named_block(read(TRIGGERS), "NOD_cw_intervention_possible")
        self.assertIn(
            "NOT = { STS = { has_country_flag = STP_cw_last_banquet_success } }",
            possible,
        )

    def test_open_nod_card_revalidates_before_every_settlement(self) -> None:
        event = event_block(read(EVENTS), "ADISCORD_STP_cw.42")
        self.assertEqual(event.count("option = {"), 3)
        self.assertIn("name = ADISCORD_STP_cw.42.c", event)
        self.assertGreaterEqual(
            event.count("trigger = { NOD_cw_intervention_possible = yes }"),
            2,
        )
        self.assertIn("trigger = { NOD_cw_intervention_possible = no }", event)
        self.assertGreaterEqual(
            event.count("limit = { NOD_cw_intervention_possible = yes }"),
            2,
        )
        self.assertIn("ADISCORD_STP_cw.42.c:", read(LOC))


if __name__ == "__main__":
    unittest.main()
