"""Focused contracts for the Vorkerland civil-war story/news layer."""

from __future__ import annotations

import unittest

from tools.lib.paths import source_section
from tools.validators.validate_adiscord_vorkerland_story import (
    CAPITULATION_DISPATCH,
    CAMPAIGN_STATE_EFFECTS,
    COUNTRY_EVENT_NUMBERS,
    EVENT_PICTURES,
    NEWS_EVENTS,
    PHASE_EFFECTS,
    ROOT,
    RUSSIAN_LOC,
    STORY_EFFECTS,
    STORY_EVENTS,
    STORY_NUMBERS,
    UNDEFINED_ARRAY_TOKENS,
    VARIANT_DISPATCH,
    collect_issues,
    dispatch_issues,
    event_blocks,
    forbidden_story_mutations,
    localisation_quality_issues,
    named_block,
    named_blocks,
    pending_external_dispatch,
    upstream_contract_issues,
)


def read(relative) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class VorkerlandStoryValidationTests(unittest.TestCase):
    def test_live_story_contract(self) -> None:
        self.assertEqual(collect_issues(ROOT), [])

    def test_story_layer_contains_no_map_war_or_peace_ownership(self) -> None:
        source = "\n".join((source_section(read(STORY_EVENTS), "story_events"),
                            source_section(read(STORY_EFFECTS), "story_effects")))
        self.assertEqual(forbidden_story_mutations(source), [])
        self.assertNotIn("ADISCORD_superevent_news.2", source)

    def test_showdown_uses_neutral_civil_war_art_not_a_second_explosion(self) -> None:
        source = source_section(read(STORY_EVENTS), 'story_events')
        showdown = event_blocks(source)["ADISCORD_vorkerland_story.1"][1]
        self.assertIn("picture = GFX_news_event_adiscord_city_in_civil_war", showdown)
        self.assertNotIn("GFX_news_event_adiscord_vorkerland_explosion", source)
        pictures = read(EVENT_PICTURES)
        self.assertIn('name = "GFX_news_event_adiscord_city_in_civil_war"', pictures)

    def test_story_rewards_use_valid_army_experience_effect(self) -> None:
        source = source_section(read(STORY_EVENTS), 'story_events')
        self.assertNotIn("add_army_experience", source)
        self.assertEqual(source.count("army_experience = 5"), 3)

    def test_opening_superevent_presentation_is_immediate(self) -> None:
        source = read(NEWS_EVENTS)
        opening = event_blocks(source)["ADISCORD_superevent_news.1"][1]
        immediate = named_block(opening, "immediate")
        self.assertIn("superevent_vorkerland_civilwar", immediate)
        self.assertIn("ADISCORD_superevent_enqueue = yes", immediate)
        self.assertNotIn("every_country", immediate)
        for option in named_blocks(opening, "option"):
            self.assertNotIn("superevent_vorkerland_civilwar", option)
            self.assertNotIn("ADISCORD_vorkerland_play_superevent_sound", option)

    def test_russian_story_localisation_has_bom(self) -> None:
        self.assertTrue((ROOT / RUSSIAN_LOC).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_forbidden_mutation_helper_is_semantic(self) -> None:
        self.assertEqual(forbidden_story_mutations("effect = { transfer_state = 32 }"), ["transfer_state"])
        self.assertEqual(forbidden_story_mutations("# transfer_state = 32\nadd_stability = 0.02"), [])

    def test_each_world_news_event_is_broadcast_safe(self) -> None:
        definitions = event_blocks(source_section(read(STORY_EVENTS), 'story_events'))
        for number in STORY_NUMBERS:
            if number in COUNTRY_EVENT_NUMBERS:
                continue
            event_id = f"ADISCORD_vorkerland_story.{number}"
            kind, block = definitions[event_id]
            self.assertEqual(kind, "news_event", event_id)
            self.assertIn("fire_only_once = no", block)
            self.assertIn("major = yes", block)
            self.assertNotIn("check_variable", block, event_id)

    def test_city_capture_news_is_retired_but_objective_effects_remain(self) -> None:
        events = source_section(read(STORY_EVENTS), 'story_events')
        effects = source_section(read(STORY_EFFECTS), 'campaign_state_effects')
        self.assertNotIn("story_report_iconic_objective", effects)
        self.assertNotIn("ADISCORD_vorkerland_objective_last", effects)
        for number in range(50, 62):
            self.assertNotIn(f"ADISCORD_vorkerland_story.{number}", events)
        resolve = named_block(effects, "ADISCORD_vorkerland_resolve_iconic_objective")
        self.assertIn("ADISCORD_vorkerland_objective_value", resolve)
        self.assertIn("ADISCORD_vorkerland_objectives_taken", resolve)
        self.assertEqual(len(CAPITULATION_DISPATCH), 3)
        self.assertEqual(len(VARIANT_DISPATCH), 6)

    def test_worker_fate_dispatch_rejects_a_swapped_event_id(self) -> None:
        swapped = source_section(read(STORY_EFFECTS), 'story_effects').replace(
            "news_event = { id = ADISCORD_vorkerland_story.13 }",
            "news_event = { id = ADISCORD_vorkerland_story.12 }",
        )
        issues = dispatch_issues(swapped)
        self.assertTrue(
            any("expected ADISCORD_vorkerland_story.13" in issue for issue in issues), issues
        )

    def test_variant_dispatch_rejects_a_swapped_event_id(self) -> None:
        swapped = source_section(read(STORY_EFFECTS), 'story_effects').replace(
            "news_event = { id = ADISCORD_vorkerland_story.35 }",
            "news_event = { id = ADISCORD_vorkerland_story.36 }",
        )
        issues = dispatch_issues(swapped)
        self.assertTrue(
            any("expected ADISCORD_vorkerland_story.35" in issue for issue in issues),
            issues,
        )

    def test_capitulation_dispatch_rejects_a_swapped_event_id(self) -> None:
        swapped = source_section(read(STORY_EFFECTS), 'story_effects').replace(
            "news_event = { id = ADISCORD_vorkerland_story.42 }",
            "news_event = { id = ADISCORD_vorkerland_story.43 }",
        )
        issues = dispatch_issues(swapped)
        self.assertTrue(
            any("expected ADISCORD_vorkerland_story.42" in issue for issue in issues),
            issues,
        )

    def test_first_fall_requires_control_of_the_entire_claimant_home_region(self) -> None:
        effects = source_section(read(STORY_EFFECTS), 'story_effects')
        fall = named_block(
            effects, "ADISCORD_vorkerland_story_check_first_claimant_capital_fall"
        )
        for claimant, states in {
            "WKR": (32, 33, 40, 200, 201),
            "VAD": (75, 106, 107, 121),
            "TVA": (36, 37, 38, 39, 324),
        }.items():
            for state_id in states:
                self.assertIn(
                    f"{state_id} = {{ is_controlled_by = ROOT }}",
                    fall,
                    f"{claimant} region is missing state {state_id}",
                )
            self.assertNotIn(f"FROM = {{ tag = {claimant} }}", fall)

    def test_capitulation_news_is_scoped_to_the_claimant_that_fell(self) -> None:
        unscoped = source_section(read(STORY_EFFECTS), 'story_effects').replace(
            "ROOT = { ADISCORD_vorkerland_story_report_claimant_capitulation = yes }",
            "ADISCORD_vorkerland_story_report_claimant_capitulation = yes",
        )
        issues = dispatch_issues(unscoped)
        self.assertTrue(any("must be scoped to ROOT" in issue for issue in issues), issues)

    def test_story_layer_uses_the_documented_global_array_arguments(self) -> None:
        effects = source_section(read(CAMPAIGN_STATE_EFFECTS), 'campaign_state_effects')
        self.assertIn("array = global.ADISCORD_vorkerland_objectives_taken", effects)
        for token in UNDEFINED_ARRAY_TOKENS:
            self.assertNotIn(token, effects)

    def test_localisation_quality_catches_copied_and_untranslated_variants(self) -> None:
        keys = [f"ADISCORD_vorkerland_story.{number}.d" for number in (10, 11, 12, 13)]
        copied = {key: f"body {index}" for index, key in enumerate(keys)}
        copied[keys[2]] = copied[keys[1]]
        self.assertTrue(
            any("repeat the same text" in issue for issue in
                localisation_quality_issues("", "", copied, {}, set()))
        )
        untranslated = {keys[0]: "An English sentence."}
        self.assertTrue(
            any("no Cyrillic" in issue for issue in
                localisation_quality_issues("", "", {}, untranslated, {keys[0]}))
        )

    def test_localisation_quality_catches_a_duplicated_key(self) -> None:
        source = ' A.b: "one"\n A.b: "two"\n'
        self.assertTrue(
            any("duplicate keys" in issue for issue in
                localisation_quality_issues(source, "", {}, {}, set()))
        )

    def test_upstream_identifiers_are_pinned_to_their_owning_files(self) -> None:
        campaign_state_effects = source_section(read(CAMPAIGN_STATE_EFFECTS), 'campaign_state_effects')
        self.assertEqual(upstream_contract_issues(ROOT, campaign_state_effects), [])
        self.assertNotIn("ADISCORD_vorkerland_objective_last", campaign_state_effects)
        self.assertEqual(upstream_contract_issues(ROOT, campaign_state_effects), [])

    def test_pending_external_wiring_is_reported_verbatim(self) -> None:
        for entry in pending_external_dispatch(ROOT):
            self.assertRegex(entry, r"^ADISCORD_vorkerland_story_report_\w+ = yes -> ")


if __name__ == "__main__":
    unittest.main()
