from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PHASE_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt"
PHASE_EVENTS = ROOT / "events/ADISCORD_vorkerland_phase_events.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def balanced_block(source: str, opening_brace: int) -> str:
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1:index]
    raise AssertionError("unterminated Clausewitz block")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    return balanced_block(source, source.find("{", match.start()))


def event_block(source: str, event_id: str) -> str:
    id_match = re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", source)
    if id_match is None:
        raise AssertionError(f"missing event: {event_id}")
    event_start = source.rfind("country_event", 0, id_match.start())
    opening_brace = source.find("{", event_start, id_match.start())
    return balanced_block(source, opening_brace)


class ReunifiedWrkDestinationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.effects = read(PHASE_EFFECTS)
        cls.events = read(PHASE_EVENTS)

    def test_each_winner_is_consumed_by_materialized_wrk(self) -> None:
        contracts = (
            ("wkr", "WKR", "WRK_Nikita_Worcker"),
            ("vad", "VAD", "WRK_VAD_Joint_Council"),
            ("tva", "TVA", "TVA_Dorian_Worx"),
        )
        for suffix, winner, route_character in contracts:
            with self.subTest(winner=winner):
                block = named_block(
                    self.effects,
                    f"ADISCORD_vorkerland_form_wrk_from_{suffix}",
                )
                normalized = " ".join(block.split())
                human_guard = (
                    f"if = {{ limit = {{ {winner} = {{ is_ai = no }} }} "
                    f"change_tag_from = {winner} }}"
                )
                winner_annex = (
                    f"annex_country = {{ target = {winner} transfer_troops = yes }}"
                )

                self.assertEqual(block.count("transfer_state = 32"), 1)
                self.assertIn("set_state_controller_to = WRK", block)
                self.assertIn(f"inherit_technology = {winner}", block)
                self.assertIn(f"copy_completed_from = {winner}", block)
                self.assertIn(route_character, block)
                self.assertIn(human_guard, normalized)
                self.assertEqual(block.count(f"change_tag_from = {winner}"), 1)
                self.assertEqual(normalized.count(winner_annex), 1)
                self.assertIn("focus_unlock = yes", block)
                self.assertIn("mark_focus_tree_layout_dirty = yes", block)

                self.assertLess(block.index("transfer_state = 32"), block.index(route_character))
                self.assertLess(block.index(route_character), block.index(f"change_tag_from = {winner}"))
                self.assertLess(block.index(f"change_tag_from = {winner}"), block.index(winner_annex))
                self.assertLess(block.index(winner_annex), block.index("ADISCORD_vorkerland_finalize_wrk_formation"))

    def test_worker_route_uses_authored_anton_fallback(self) -> None:
        block = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_wkr")
        self.assertIn("ADISCORD_vorkerland_worker_safe_with_loyalists", block)
        self.assertIn("WRK_Nikita_Worcker", block)
        self.assertIn("WRK_Anton_Bagley", block)
        self.assertNotIn("WKR_Worker_Emergency_Presidium", block)
        self.assertNotIn("Lucas", block)

    def test_rescued_worker_and_route_leaders_follow_their_winners(self) -> None:
        vad = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_vad")
        tva = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_tva")
        self.assertIn("ADISCORD_vorkerland_worker_rescued_by_vlad", vad)
        self.assertIn("character = WRK_Nikita_Worcker", vad)
        self.assertIn("character = WRK_VAD_Joint_Council", vad)
        self.assertIn("character = TVA_Dorian_Worx", tva)

    def test_phase_six_runs_formation_and_verification_from_wrk(self) -> None:
        phase_six = event_block(self.events, "ADISCORD_vorkerland_phase.6")
        self.assertEqual(phase_six.count("country_event = { id = ADISCORD_vorkerland_phase.7 days = 1 }"), 3)
        for suffix, old_scope in (("wkr", "WKR"), ("vad", "VAD"), ("tva", "TVA")):
            effect = f"ADISCORD_vorkerland_form_wrk_from_{suffix} = yes"
            with self.subTest(winner=old_scope):
                self.assertIn(f"WRK = {{\n\t\t\t\t{effect}", phase_six)
                self.assertNotIn(f"{old_scope} = {{\n\t\t\t\t{effect}", phase_six)

    def test_no_random_lucas_contract_leaks_into_formation(self) -> None:
        self.assertNotIn("Lucas", self.effects)
        self.assertNotIn("Lucas", self.events)


if __name__ == "__main__":
    unittest.main()
