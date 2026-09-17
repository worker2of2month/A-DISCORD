from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEWS = ROOT / "events/ADISCORD_news.txt"
SUPEREVENTS = ROOT / "interface/superevents.gfx"
IMPERIAL_DECISIONS = ROOT / "common/decisions/ADISCORD_STP_imperial_union_decisions.txt"
IMPERIAL_TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_imperial_union_triggers.txt"
IMPERIAL_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_imperial_union_effects.txt"
WORKER_ART = ROOT / "gfx/interface/superevents/WRK/superevent_vorkerland_worker_victory.png"

REQUIRED_IMPERIAL_STATES = (
    4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 24, 30, 31, 41, 42, 48, 54, 55, 56, 57,
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def event_block(text: str, event_id: str) -> str:
    marker = re.search(rf"(?:country|news)_event\s*=\s*\{{(?:(?!\n\}}).)*?\bid\s*=\s*{re.escape(event_id)}\b", text, re.S)
    if marker is None:
        raise AssertionError(f"missing event {event_id}")
    start = marker.start()
    brace = text.find("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unterminated event {event_id}")


class SupereventAndImperialUnionTests(unittest.TestCase):
    def test_worker_victory_has_dedicated_art(self) -> None:
        gfx = read(SUPEREVENTS)
        self.assertIn(
            'name = "GFX_superevent_vorkerland_worker_victory"',
            gfx,
        )
        self.assertIn(
            'textureFile = "gfx/interface/superevents/WRK/superevent_vorkerland_worker_victory.png"',
            gfx,
        )
        self.assertTrue(WORKER_ART.is_file())

    def test_civilwar_console_gateway_runs_the_real_outbreak(self) -> None:
        gateway = event_block(read(NEWS), "ADISCORD_superevent.1")
        self.assertIn("ADISCORD_vorkerland_collapse.1", gateway)
        self.assertIn("superevent_vorkerland_civilwar", gateway)

    def test_stelander_empire_news_is_presentation_only(self) -> None:
        empire = event_block(read(NEWS), "ADISCORD_superevent_news.2")
        for forbidden in (
            "transfer_state",
            "set_politics",
            "add_country_leader_role",
            "set_country_leader_portrait",
        ):
            self.assertNotIn(forbidden, empire)
        self.assertIn("superevent_stelander_empire", empire)
        self.assertIn("ADISCORD_superevent_audio.2", empire)

    def test_shabrat_imperial_union_requires_the_full_map(self) -> None:
        decisions = read(IMPERIAL_DECISIONS)
        triggers = read(IMPERIAL_TRIGGERS)
        self.assertIn("STP_proclaim_imperial_union", decisions)
        self.assertIn("tag = STS", decisions)
        self.assertIn("STP_maksim_shabrat", decisions)
        self.assertIn("STP_imperial_union_requirements_met = yes", decisions)
        self.assertIn("VAL", triggers)
        self.assertIn("NOD", triggers)
        for state in REQUIRED_IMPERIAL_STATES:
            self.assertIn(f"owns_state = {state}", triggers)
            self.assertIn(f"controls_state = {state}", triggers)
            self.assertIn(f"highlight_state_targets = {{ state = {state} }}", decisions)

    def test_imperial_union_effect_owns_state_change_not_news(self) -> None:
        effects = read(IMPERIAL_EFFECTS)
        self.assertIn("STP_proclaim_imperial_union = {", effects)
        self.assertIn("set_cosmetic_tag = STP_empire", effects)
        self.assertIn("ruling_party = chauvinism", effects)
        self.assertIn("character = STP_maksim_shabrat", effects)
        self.assertIn("news_event = { id = ADISCORD_superevent_news.2 }", effects)
        self.assertNotIn("transfer_state", effects)


if __name__ == "__main__":
    unittest.main()
