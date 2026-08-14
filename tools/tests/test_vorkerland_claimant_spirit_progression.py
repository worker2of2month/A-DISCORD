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


class VorkerlandClaimantSpiritProgressionTests(unittest.TestCase):
    WRK_CHAIN = (
        "WRK_birthplace_of_the_first_revolution",
        "WRK_birthplace_of_the_first_revolution_front_republic",
        "WRK_birthplace_of_the_first_revolution_renewed_mandate",
    )
    TVA_CHAIN = (
        "ADISCORD_vorkerland_tva_field_directorate",
        "ADISCORD_vorkerland_tva_field_directorate_2",
        "ADISCORD_vorkerland_tva_field_directorate_3",
    )
    OBSOLETE_WRK_SPIRITS = (
        "WRK_ashes_of_the_crown",
        "WRK_hourglass_of_discord",
        "WRK_constitution_of_the_republic",
    )

    def test_wkr_keeps_only_the_revolutionary_starting_spirit(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
        repair = named_block(
            effects, "ADISCORD_vorkerland_repair_claimant_spirit_progression"
        )
        self.assertIn("limit = { OR = { tag = WRK tag = WKR } }", repair)
        for spirit in self.OBSOLETE_WRK_SPIRITS:
            self.assertIn(f"remove_ideas = {spirit}", repair)
        self.assertIn(f"add_ideas = {self.WRK_CHAIN[0]}", repair)
        for spirit in self.WRK_CHAIN:
            self.assertIn(f"has_idea = {spirit}", repair)

    def test_revolutionary_spirit_chain_accepts_neo_vorkerism(self) -> None:
        ideas = read("common/ideas/vorkerland.txt")
        for spirit in self.WRK_CHAIN:
            with self.subTest(spirit=spirit):
                block = named_block(ideas, spirit)
                self.assertIn("has_country_leader_ideology = vorkerism", block)
                self.assertIn("has_country_leader_ideology = neo_vorkerism", block)
                self.assertIn(f"picture = GFX_idea_{spirit}", block)

    def test_revolutionary_spirit_chain_has_registered_pictures(self) -> None:
        gfx = read("interface/ADISCORD_ideas.gfx")
        for spirit in self.WRK_CHAIN:
            with self.subTest(spirit=spirit):
                self.assertIn(f'name = "GFX_idea_{spirit}"', gfx)

    def test_wkr_decisions_upgrade_one_spirit_in_order(self) -> None:
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        chain = (
            ("ADISCORD_vorkerland_wrk_convene_front_soviets", self.WRK_CHAIN[0], self.WRK_CHAIN[1], "60"),
            ("ADISCORD_vorkerland_wrk_adopt_front_charter", self.WRK_CHAIN[1], self.WRK_CHAIN[2], "90"),
        )
        for decision, old, new, days in chain:
            with self.subTest(decision=decision):
                block = named_block(decisions, decision)
                self.assertIn("allowed = { tag = WKR }", block)
                self.assertIn("ADISCORD_vorkerland_collapse_wars_started", block)
                self.assertIn("ADISCORD_vorkerland_central_war_finished", block)
                self.assertIn("available = { has_war = yes }", block)
                self.assertIn(f"days_remove = {days}", block)
                self.assertIn(f"remove_ideas = {old}", block)
                self.assertIn(f"add_ideas = {new}", block)

    def test_tva_decisions_upgrade_field_directorate_in_order(self) -> None:
        ideas = read("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
        decisions = read("common/decisions/ADISCORD_vorkerland_collapse_decisions.txt")
        for spirit in self.TVA_CHAIN:
            block = named_block(ideas, spirit)
            self.assertIn("picture = generic_production_bonus", block)
            self.assertIn("original_tag = TVA", block)
        chain = (
            ("ADISCORD_vorkerland_tva_unify_front_bureaus", self.TVA_CHAIN[0], self.TVA_CHAIN[1], "60"),
            ("ADISCORD_vorkerland_tva_close_operational_loop", self.TVA_CHAIN[1], self.TVA_CHAIN[2], "90"),
        )
        for decision, old, new, days in chain:
            with self.subTest(decision=decision):
                block = named_block(decisions, decision)
                self.assertIn("allowed = { tag = TVA }", block)
                self.assertIn("available = { has_war = yes }", block)
                self.assertIn(f"days_remove = {days}", block)
                self.assertIn(f"remove_ideas = {old}", block)
                self.assertIn(f"add_ideas = {new}", block)

    def test_outbreak_runs_the_versioned_repair_without_startup_migration(self) -> None:
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        outbreak = re.search(
            r"(?ms)^country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.2\b"
            r"(.*?)(?=^country_event\s*=|\Z)",
            events,
        )
        self.assertIsNotNone(outbreak)
        self.assertIn("WKR = { ADISCORD_vorkerland_repair_claimant_spirit_progression = yes }", outbreak.group(1))
        self.assertIn("TVA = { ADISCORD_vorkerland_repair_claimant_spirit_progression = yes }", outbreak.group(1))
        self.assertIn("ADISCORD_vorkerland_claimant_spirit_progression_v3", outbreak.group(1))

        startup = named_block(
            read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"),
            "on_startup",
        )
        for token in (
            "ADISCORD_vorkerland_collapse_wars_started",
            "ADISCORD_vorkerland_claimant_spirit_progression_v3",
            "WKR = { ADISCORD_vorkerland_repair_claimant_spirit_progression = yes }",
            "TVA = { ADISCORD_vorkerland_repair_claimant_spirit_progression = yes }",
        ):
            self.assertNotIn(token, startup)

    def test_russian_localisation_is_complete_and_keeps_bom(self) -> None:
        paths = (
            ROOT / "localisation/russian/ADISCORD_ideas_l_russian.yml",
            ROOT / "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml",
        )
        localisation = ""
        for path in paths:
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path)
            localisation += path.read_text(encoding="utf-8-sig")
        keys = self.WRK_CHAIN[1:] + self.TVA_CHAIN[1:] + (
            "ADISCORD_vorkerland_wrk_convene_front_soviets",
            "ADISCORD_vorkerland_wrk_adopt_front_charter",
            "ADISCORD_vorkerland_tva_unify_front_bureaus",
            "ADISCORD_vorkerland_tva_close_operational_loop",
        )
        for key in keys:
            self.assertIn(f" {key}:", localisation)
            self.assertIn(f" {key}_desc:", localisation)


if __name__ == "__main__":
    unittest.main()
