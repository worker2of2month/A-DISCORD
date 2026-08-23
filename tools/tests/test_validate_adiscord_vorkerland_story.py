"""Focused contracts for the Vorkerland civil-war story/news layer."""

from __future__ import annotations

import unittest

from tools.validators.validate_adiscord_vorkerland_story import (
    CAPITULATION_DISPATCH,
    CAMPAIGN_STATE_EFFECTS,
    EVENT_PICTURES,
    NEWS_EVENTS,
    OBJECTIVE_DISPATCH,
    PHASE_EFFECTS,
    ROOT,
    RUSSIAN_LOC,
    STORY_EFFECTS,
    STORY_EVENTS,
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
        source = "\n".join(read(relative) for relative in (STORY_EVENTS, STORY_EFFECTS))
        self.assertEqual(forbidden_story_mutations(source), [])
        self.assertNotIn("ADISCORD_superevent_news.2", source)

    def test_showdown_uses_neutral_civil_war_art_not_a_second_explosion(self) -> None:
        source = read(STORY_EVENTS)
        showdown = event_blocks(source)["ADISCORD_vorkerland_story.1"][1]
        self.assertIn("picture = GFX_event_china_civil_war_1", showdown)
        self.assertNotIn("GFX_event_vorkerland_explosion", source)
        pictures = read(EVENT_PICTURES)
        self.assertIn('name = "GFX_event_china_civil_war_1"', pictures)

    def test_story_rewards_use_valid_army_experience_effect(self) -> None:
        source = read(STORY_EVENTS)
        self.assertNotIn("add_army_experience", source)
        self.assertEqual(source.count("army_experience = 5"), 3)

    def test_opening_superevent_presentation_is_immediate(self) -> None:
        source = read(NEWS_EVENTS)
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

    def test_each_worker_fate_is_its_own_one_shot_news_event(self) -> None:
        definitions = event_blocks(read(STORY_EVENTS))
        for number in (10, 11, 12, 13, 31, 32, 33, 34, 35, 36, 41, 42, 43, *range(50, 62)):
            event_id = f"ADISCORD_vorkerland_story.{number}"
            kind, block = definitions[event_id]
            self.assertEqual(kind, "news_event", event_id)
            self.assertIn("fire_only_once = yes", block)
            self.assertIn("major = yes", block)
            self.assertNotIn("check_variable", block, event_id)

    def test_objective_table_covers_all_twelve_iconic_centres(self) -> None:
        self.assertEqual(len(OBJECTIVE_DISPATCH), 12)
        self.assertEqual(len(CAPITULATION_DISPATCH), 3)
        self.assertEqual(len(VARIANT_DISPATCH), 6)

    def test_worker_fate_dispatch_rejects_a_swapped_event_id(self) -> None:
        swapped = read(STORY_EFFECTS).replace(
            "news_event = { id = ADISCORD_vorkerland_story.13 }",
            "news_event = { id = ADISCORD_vorkerland_story.12 }",
        )
        issues = dispatch_issues(swapped)
        self.assertTrue(
            any("expected ADISCORD_vorkerland_story.13" in issue for issue in issues), issues
        )

    def test_variant_dispatch_rejects_a_swapped_event_id(self) -> None:
        swapped = read(STORY_EFFECTS).replace(
            "news_event = { id = ADISCORD_vorkerland_story.35 }",
            "news_event = { id = ADISCORD_vorkerland_story.36 }",
        )
        issues = dispatch_issues(swapped)
        self.assertTrue(
            any("expected ADISCORD_vorkerland_story.35" in issue for issue in issues),
            issues,
        )

    def test_objective_dispatch_rejects_a_swapped_event_id(self) -> None:
        swapped = read(STORY_EFFECTS).replace(
            "news_event = { id = ADISCORD_vorkerland_story.57 }",
            "news_event = { id = ADISCORD_vorkerland_story.56 }",
        )
        issues = dispatch_issues(swapped)
        self.assertTrue(
            any("expected ADISCORD_vorkerland_story.57" in issue for issue in issues),
            issues,
        )

    def test_capitulation_dispatch_rejects_a_swapped_event_id(self) -> None:
        swapped = read(STORY_EFFECTS).replace(
            "news_event = { id = ADISCORD_vorkerland_story.42 }",
            "news_event = { id = ADISCORD_vorkerland_story.43 }",
        )
        issues = dispatch_issues(swapped)
        self.assertTrue(
            any("expected ADISCORD_vorkerland_story.42" in issue for issue in issues),
            issues,
        )

    def test_objective_news_stays_reachable_from_the_state_control_entry_point(self) -> None:
        unhooked = read(STORY_EFFECTS).replace(
            "\tADISCORD_vorkerland_story_report_iconic_objective = yes\n}", "\n}", 1
        )
        issues = dispatch_issues(unhooked)
        self.assertTrue(any("unreachable" in issue for issue in issues), issues)

    def test_capital_first_fall_news_is_not_duplicated_by_the_objective_news(self) -> None:
        effects = read(STORY_EFFECTS)
        for flag in (
            "ADISCORD_vorkerland_story_wkr_capital_fell_first",
            "ADISCORD_vorkerland_story_vad_capital_fell_first",
            "ADISCORD_vorkerland_story_tva_capital_fell_first",
        ):
            self.assertIn(
                flag,
                named_block(effects, "ADISCORD_vorkerland_story_report_iconic_objective"),
            )
        without = effects.replace(
            "has_global_flag = ADISCORD_vorkerland_story_vad_capital_fell_first",
            "has_global_flag = ADISCORD_vorkerland_story_wkr_capital_fell_first",
        )
        self.assertTrue(any("suppress objective 2" in issue for issue in dispatch_issues(without)))

    def test_capitulation_news_is_scoped_to_the_claimant_that_fell(self) -> None:
        unscoped = read(STORY_EFFECTS).replace(
            "ROOT = { ADISCORD_vorkerland_story_report_claimant_capitulation = yes }",
            "ADISCORD_vorkerland_story_report_claimant_capitulation = yes",
        )
        issues = dispatch_issues(unscoped)
        self.assertTrue(any("must be scoped to ROOT" in issue for issue in issues), issues)

    def test_story_layer_uses_the_documented_global_array_arguments(self) -> None:
        effects = read(STORY_EFFECTS)
        self.assertIn(
            "array = global.ADISCORD_vorkerland_story_objectives_reported", effects
        )
        for token in UNDEFINED_ARRAY_TOKENS:
            self.assertNotIn(token, effects)

    def test_localisation_quality_catches_copied_and_untranslated_variants(self) -> None:
        keys = [f"ADISCORD_vorkerland_story.{number}.d" for number in range(50, 62)]
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
        campaign_state_effects = read(CAMPAIGN_STATE_EFFECTS)
        self.assertEqual(upstream_contract_issues(ROOT, campaign_state_effects), [])
        renamed = campaign_state_effects.replace(
            "var = global.ADISCORD_vorkerland_objective_last",
            "var = global.ADISCORD_vorkerland_objective_previous",
        )
        issues = upstream_contract_issues(ROOT, renamed)
        self.assertTrue(any("no longer writes" in issue for issue in issues), issues)

    def test_pending_external_wiring_is_reported_verbatim(self) -> None:
        for entry in pending_external_dispatch(ROOT):
            self.assertRegex(entry, r"^ADISCORD_vorkerland_story_report_\w+ = yes -> ")


if __name__ == "__main__":
    unittest.main()
