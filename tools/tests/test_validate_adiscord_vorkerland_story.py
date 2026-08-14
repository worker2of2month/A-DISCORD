"""Focused contracts for the Vorkerland civil-war story/news layer."""

from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_vorkerland_story import (
    EVENT_PICTURES,
    NEWS_EVENTS,
    ROOT,
    RUSSIAN_LOC,
    STORY_EFFECTS,
    STORY_EVENTS,
    collect_issues,
    event_blocks,
    forbidden_story_mutations,
    named_block,
    named_blocks,
)


class VorkerlandStoryValidationTests(unittest.TestCase):
    def test_live_story_contract(self) -> None:
        self.assertEqual(collect_issues(ROOT), [])

    def test_story_layer_contains_no_map_war_or_peace_ownership(self) -> None:
        source = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8-sig")
            for relative in (STORY_EVENTS, STORY_EFFECTS)
        )
        self.assertEqual(forbidden_story_mutations(source), [])
        self.assertNotIn("ADISCORD_superevent_news.2", source)

    def test_showdown_uses_neutral_civil_war_art_not_a_second_explosion(self) -> None:
        source = (ROOT / STORY_EVENTS).read_text(encoding="utf-8-sig")
        showdown = event_blocks(source)["ADISCORD_vorkerland_story.1"][1]
        self.assertIn("picture = GFX_event_china_civil_war_1", showdown)
        self.assertNotIn("GFX_event_vorkerland_explosion", source)
        pictures = (ROOT / EVENT_PICTURES).read_text(encoding="utf-8-sig")
        self.assertIn('name = "GFX_event_china_civil_war_1"', pictures)

    def test_story_rewards_use_valid_army_experience_effect(self) -> None:
        source = (ROOT / STORY_EVENTS).read_text(encoding="utf-8-sig")
        self.assertNotIn("add_army_experience", source)
        self.assertEqual(source.count("army_experience = 5"), 3)

    def test_opening_superevent_presentation_is_immediate(self) -> None:
        source = (ROOT / NEWS_EVENTS).read_text(encoding="utf-8-sig")
        opening = event_blocks(source)["ADISCORD_superevent_news.1"][1]
        immediate = named_block(opening, "immediate")
        self.assertIn("superevent_vorkerland_civilwar", immediate)
        self.assertIn("ADISCORD_superevent_audio.1", immediate)
        for option in named_blocks(opening, "option"):
            self.assertNotIn("superevent_vorkerland_civilwar", option)
            self.assertNotIn("ADISCORD_superevent_audio.1", option)

    def test_russian_story_localisation_has_bom(self) -> None:
        self.assertTrue((ROOT / RUSSIAN_LOC).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_forbidden_mutation_helper_is_semantic(self) -> None:
        self.assertEqual(forbidden_story_mutations("effect = { transfer_state = 32 }"), ["transfer_state"])
        self.assertEqual(forbidden_story_mutations("# transfer_state = 32\nadd_stability = 0.02"), [])


if __name__ == "__main__":
    unittest.main()
