from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    start = match.start()
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block: {name}")


def event_block(text: str, event_id: str) -> str:
    for match in re.finditer(r"(?m)^country_event\s*=\s*\{", text):
        start = match.start()
        depth = 0
        for index in range(match.end() - 1, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    block = text[start : index + 1]
                    definition = re.match(
                        r"(?s)^country_event\s*=\s*\{\s*id\s*=\s*([^\s{}]+)",
                        block,
                    )
                    if definition is not None and definition.group(1) == event_id:
                        return block
                    break
    raise AssertionError(f"missing event: {event_id}")


class VorkerlandWorxSupporterTests(unittest.TestCase):
    def test_wkr_is_the_temporary_main_civil_war_claimant(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        claimants = named_block(triggers, "ADISCORD_vorkerland_is_main_claimant")
        self.assertEqual(
            set(re.findall(r"tag\s*=\s*([A-Z]{3})", claimants)),
            {"WKR", "VAD", "TVA"},
        )

        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        initial = named_block(effects, "ADISCORD_vorkerland_apply_initial_map")
        wkr = named_block(initial, "WKR")
        self.assertEqual(
            set(map(int, re.findall(r"transfer_state\s*=\s*(\d+)", wkr))),
            {32, 33, 40, 200, 201},
        )
        self.assertIn("set_capital = { state = 32 }", wkr)

    def test_oitfort_committee_takes_only_state_34_and_never_annexes_wrk(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        setup = named_block(effects, "ADISCORD_vorkerland_setup_wtd")
        self.assertEqual(
            set(map(int, re.findall(r"transfer_state\s*=\s*(\d+)", setup))),
            {34},
        )
        self.assertIn("set_capital = { state = 34 }", setup)
        self.assertNotIn("annex_country = { target = WRK", effects)

        alignment = named_block(effects, "ADISCORD_vorkerland_align_wtd_with_worx")
        self.assertNotIn("puppet = WTD", alignment)
        self.assertIn("is_subject = yes", alignment)
        self.assertIn("autonomy_state = autonomy_free", alignment)
        self.assertIn("is_in_faction = yes", alignment)
        self.assertIn("leave_faction = yes", alignment)
        self.assertIn("ADISCORD_vorkerland_worx_aligned_technocrats", alignment)

    def test_retired_worker_doctor_events_are_absent_and_wtd_joins_live_war(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        for legacy_id in (48, 49):
            with self.subTest(legacy_id=legacy_id):
                self.assertNotRegex(
                    events,
                    rf"(?m)^\s*id\s*=\s*ADISCORD_vorkerland_collapse\.{legacy_id}\b",
                )

        phase_events = read("events/ADISCORD_vorkerland_phase_events.txt")
        self.assertIn(
            "ADISCORD_vorkerland_initialize_showdown_edge_queue = yes",
            event_block(phase_events, "ADISCORD_vorkerland_phase.4"),
        )
        self.assertIn(
            "ADISCORD_vorkerland_advance_showdown_launch = yes",
            event_block(phase_events, "ADISCORD_vorkerland_phase.5"),
        )

        phase_effects = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        queue = named_block(
            phase_effects, "ADISCORD_vorkerland_initialize_showdown_edge_queue"
        )
        self.assertIn(
            "set_global_flag = ADISCORD_vorkerland_showdown_edge_wkr_tva_required",
            queue,
        )
        verify = named_block(
            phase_effects, "ADISCORD_vorkerland_verify_showdown_edge_wkr_tva"
        )
        self.assertIn("WKR = { has_war_with = TVA }", verify)
        self.assertIn(
            "ADISCORD_vorkerland_schedule_wtd_tva_temporary_alliance_check = yes",
            verify,
        )
        schedule = named_block(
            phase_effects, "ADISCORD_vorkerland_schedule_wtd_tva_temporary_alliance_check"
        )
        for token in (
            "is_subject = no",
            "TVA = { exists = yes has_war_with = WKR }",
            "NOT = { has_war_with = WKR }",
            "WTD = { country_event = { id = ADISCORD_vorkerland_collapse.47 days = 1 } }",
        ):
            self.assertIn(token, schedule)

        join = event_block(events, "ADISCORD_vorkerland_collapse.47")
        for token in (
            "tag = WTD",
            "is_subject = no",
            "TVA = { exists = yes has_war_with = WKR }",
            "NOT = { has_war_with = WKR }",
            "targeted_alliance = TVA",
            "enemy = WKR",
            "country_event = { id = ADISCORD_vorkerland_collapse.67 days = 1 }",
        ):
            self.assertIn(token, join)

        retry = event_block(events, "ADISCORD_vorkerland_collapse.67")
        self.assertIn("limit = { has_war_with = WKR }", retry)
        self.assertIn(
            "set_country_flag = ADISCORD_vorkerland_wtd_fighting_for_worx", retry
        )
        self.assertIn("set_country_flag = ADISCORD_vorkerland_wtd_join_retry", retry)
        self.assertIn("set_country_flag = ADISCORD_vorkerland_wtd_join_failed", retry)
        self.assertEqual(
            retry.count(
                "country_event = { id = ADISCORD_vorkerland_collapse.67 days = 1 }"
            ),
            1,
        )

    def test_committee_has_a_leader_army_spirit_and_localisation(self) -> None:
        history = read("history/countries/WTD - Central Technical Committee.txt")
        characters = read("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        units = read("history/units/WTD_vorkerland_collapse.txt")
        localisation = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")

        self.assertIn("recruit_character = WTD_Central_Engineering_Council", history)
        self.assertIn("WTD_Central_Engineering_Council", characters)
        self.assertIn("ADISCORD_vorkerland_wtd_worx_protocols", ideas)
        self.assertEqual(units.count("division = {"), 4)
        self.assertEqual(set(re.findall(r"location\s*=\s*(\d+)", units)), {"16426"})
        for key in (
            "WTD: \"Ойтфортский технический комитет\"",
            "WTD_Central_Engineering_Council: \"Ойтфортский инженерный совет\"",
            "ADISCORD_vorkerland_wtd_worx_protocols_desc:",
        ):
            self.assertIn(key, localisation)


if __name__ == "__main__":
    unittest.main()
