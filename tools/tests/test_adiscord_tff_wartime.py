from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_tff_wartime import (
    BORDER_PROVINCES,
    CHARACTERS,
    COUNTRY_TAGS,
    DECISIONS,
    EFFECTS,
    EVENTS,
    HISTORY,
    ON_ACTIONS,
    PORTRAIT,
    PORTRAITS_GFX,
    collect_issues,
    event_block,
    named_block,
    read,
)


ROOT = Path(__file__).resolve().parents[2]


class TFFWartimeContractTests(unittest.TestCase):
    def test_integrated_validator_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_war_hook_covers_both_directions_once(self) -> None:
        war = named_block(read(ON_ACTIONS), "on_war_relation_added")
        self.assertIn("ROOT = { tag = TFF }", war)
        self.assertIn("FROM = { tag = NOD }", war)
        self.assertIn("ROOT = { tag = NOD }", war)
        self.assertIn("FROM = { tag = TFF }", war)
        self.assertEqual(war.count("TFF_nodrul_war_crisis_started"), 2)
        self.assertLess(
            war.find("set_country_flag = TFF_nodrul_war_crisis_started"),
            war.find("country_event = { id = ADISCORD_TFF.1 }"),
        )
        self.assertNotIn("tag = VAL", war)
        self.assertNotIn("tag = YPR", war)

    def test_scripted_effect_sets_cosmetic_tag_and_promotes_colt(self) -> None:
        form = named_block(read(EFFECTS), "ADISCORD_TFF_form_wartime_confederation")
        self.assertIn("set_cosmetic_tag = TFF_frontier_defense_confederation", form)
        self.assertIn(
            "promote_character = { character = TFF_Colt_Ardent ideology = tff_emergency_war_coordinator }",
            form,
        )
        self.assertIn("set_country_flag = TFF_wartime_confederation_formed", form)
        self.assertIn("set_country_flag = TFF_wartime_command_active", form)
        self.assertNotIn("clr_country_flag = TFF_wartime_confederation_formed", form)

    def test_no_new_real_country_tag(self) -> None:
        tags = read(COUNTRY_TAGS)
        self.assertRegex(tags, r'(?m)^TFF\s*=\s*"countries/TheFreeFrontier.txt"\s*$')
        for path in (ROOT / "common/country_tags").glob("*.txt"):
            extras = re.findall(
                r'(?m)^(TFF_[A-Za-z0-9_]+)\s*=\s*"countries/',
                path.read_text(encoding="utf-8-sig"),
            )
            self.assertEqual(extras, [], path)

    def test_colt_portrait_gfx_points_at_renamed_asset(self) -> None:
        gfx = read(PORTRAITS_GFX)
        self.assertIn('name = "GFX_portrait_TFF_Colt_Ardent"', gfx)
        self.assertIn('texturefile = "gfx/leaders/TFF/portrait_TFF_Colt_Ardent.png"', gfx)
        self.assertTrue((ROOT / PORTRAIT).is_file())
        self.assertFalse((ROOT / "gfx/leaders/TFF/portrait.png").exists())
        self.assertIn("GFX_portrait_TFF_Colt_Ardent", named_block(read(CHARACTERS), "TFF_Colt_Ardent"))

    def test_start_keeps_absent_government_and_recruits_colt(self) -> None:
        history = read(HISTORY)
        self.assertIn("recruit_character = The_Absent_Government", history)
        self.assertIn("recruit_character = TFF_Colt_Ardent", history)
        self.assertIn(
            "promote_character = { character = The_Absent_Government ideology = anarchism_ideology }",
            history,
        )
        self.assertIn("The_Absent_Government = {", read(CHARACTERS))

    def test_empty_chair_transforms_in_immediate(self) -> None:
        event = event_block(read(EVENTS), "ADISCORD_TFF.1")
        immediate = named_block(event, "immediate")
        self.assertIn("hidden_effect = {", immediate)
        self.assertIn("ADISCORD_TFF_form_wartime_confederation = yes", immediate)
        option = named_block(event, "option")
        self.assertNotIn("ADISCORD_TFF_form_wartime_confederation = yes", option)

    def test_border_forts_stay_on_the_odar_esnos_line(self) -> None:
        forts = named_block(read(DECISIONS), "TFF_fortify_the_nodrul_border")
        self.assertEqual(tuple(re.findall(r"province\s*=\s*(\d+)", forts)), BORDER_PROVINCES)
        self.assertIn("83 = {", forts)
        self.assertNotIn("province = 30", forts)
        self.assertNotIn("province = 16533", forts)


if __name__ == "__main__":
    unittest.main()
