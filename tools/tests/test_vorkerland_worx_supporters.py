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


class VorkerlandWorxSupporterTests(unittest.TestCase):
    def test_wrk_remains_a_main_civil_war_claimant(self) -> None:
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt")
        claimants = named_block(triggers, "ADISCORD_vorkerland_is_main_claimant")
        self.assertEqual(
            set(re.findall(r"tag\s*=\s*([A-Z]{3})", claimants)),
            {"WRK", "VAD", "TVA"},
        )

        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        initial = named_block(effects, "ADISCORD_vorkerland_apply_initial_map")
        wrk = named_block(initial, "WRK")
        self.assertEqual(
            set(map(int, re.findall(r"transfer_state\s*=\s*(\d+)", wrk))),
            {32, 33, 34, 200, 201},
        )
        self.assertIn("set_capital = { state = 32 }", wrk)

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
        self.assertIn("puppet = WTD", alignment)
        self.assertIn("ADISCORD_vorkerland_worx_aligned_technocrats", alignment)

    def test_committee_joins_doctor_worx_after_the_showdown_starts(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        showdown = named_block(
            decisions, "ADISCORD_vorkerland_prepare_worker_doctor_showdown"
        )
        self.assertNotIn("declare_war_on", showdown)
        self.assertIn(
            "WRK = { country_event = { id = ADISCORD_vorkerland_collapse.48 hours = 1 } }",
            showdown,
        )

        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        launch = named_block(effects, "ADISCORD_vorkerland_launch_worker_doctor_war")
        self.assertIn("declare_war_on = { target = TVA type = annex_everything }", launch)
        self.assertIn(
            "WTD = { country_event = { id = ADISCORD_vorkerland_collapse.47 days = 1 } }",
            launch,
        )

        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        join = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.47\b"
            r"(.*?)(?=^country_event\s*=|\Z)",
            events,
        )
        self.assertIsNotNone(join)
        body = join.group(1)
        for token in (
            "tag = WTD",
            "is_subject_of = TVA",
            "TVA = { has_war_with = WRK }",
            "targeted_alliance = TVA",
            "enemy = WRK",
        ):
            self.assertIn(token, body)

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
