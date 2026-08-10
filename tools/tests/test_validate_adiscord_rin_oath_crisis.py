from __future__ import annotations

import re
import unittest

from tools.validators.validate_adiscord_rin_oath_crisis import (
    DECISIONS,
    EFFECTS,
    EVENTS,
    ON_ACTIONS,
    RIN_COUNTRY,
    RIN_HISTORY,
    RIN_OOB,
    TRIGGERS,
    collect_issues,
    event_block,
    named_block,
    read,
)


class RinOathCrisisContractTests(unittest.TestCase):
    def test_integrated_validator_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_war_edge_producer_is_one_shot_and_releases_both_minors(self) -> None:
        on_actions = read(ON_ACTIONS)
        war = named_block(on_actions, "on_war")
        self.assertIn("ADISCORD_rin_is_vorkerland_war_actor = yes", war)
        self.assertIn("ADISCORD_rin_oath_crisis_can_schedule = yes", war)
        self.assertEqual(war.count("ADISCORD_rin_crisis.1 days = 7"), 1)
        self.assertEqual(war.count("ADISCORD_release_non_participating_minor_optimization = yes"), 2)
        event_position = war.find("ADISCORD_rin_crisis.1 days = 7")
        for match in re.finditer("ADISCORD_release_non_participating_minor_optimization = yes", war):
            self.assertLess(match.start(), event_position)
        self.assertLess(
            war.find("set_global_flag = ADISCORD_rin_oath_crisis_scheduled"),
            war.find("ADISCORD_rin_crisis.1 days = 7"),
        )

    def test_startup_is_bounded_legacy_repair_not_a_poll(self) -> None:
        on_actions = read(ON_ACTIONS)
        startup = named_block(on_actions, "on_startup")
        rin_scope = named_block(startup, "RIN")
        self.assertIn("ADISCORD_rin_oath_crisis_legacy_needs_schedule = yes", rin_scope)
        self.assertEqual(startup.count("ADISCORD_rin_crisis.1 days = 1"), 1)
        legacy = named_block(read(TRIGGERS), "ADISCORD_rin_oath_crisis_legacy_needs_schedule")
        self.assertIn("tag = RIN", legacy)
        self.assertNotIn("RIN = {", legacy)
        for recurring in ("on_daily", "on_weekly", "on_monthly", "on_yearly", "every_country"):
            self.assertNotIn(recurring, on_actions)

    def test_starting_oob_uses_line_artillery_not_support_in_regiments(self) -> None:
        oob = read(RIN_OOB)
        template = named_block(oob, "division_template")
        regiments = named_block(template, "regiments")
        self.assertIn("ADISCORD_line_artillery = {", regiments)
        self.assertNotRegex(regiments, r"(?m)^\s*artillery\s*=\s*\{")

    def test_visual_definition_fields_live_only_in_common_country(self) -> None:
        history = read(RIN_HISTORY)
        country = read(RIN_COUNTRY)
        for field, expected in (
            ("graphical_culture", "western_european_gfx"),
            ("graphical_culture_2d", "western_european_2d"),
            ("color", "rgb { 102 48 61 }"),
        ):
            self.assertNotRegex(history, rf"(?m)^\s*{field}\s*=")
            self.assertRegex(country, rf"(?m)^\s*{field}\s*=\s*{re.escape(expected)}\s*$")

    def test_only_central_claimants_can_produce_the_crisis(self) -> None:
        actor = named_block(read(TRIGGERS), "ADISCORD_rin_is_vorkerland_war_actor")
        self.assertEqual(set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", actor)), {"WKR", "VAD", "TVA"})

    def test_visible_event_defaults_ai_to_the_split(self) -> None:
        prompt = event_block(read(EVENTS), "ADISCORD_rin_crisis.1")
        self.assertIn("title = ADISCORD_rin_crisis.1.t", prompt)
        self.assertIn("desc = ADISCORD_rin_crisis.1.d", prompt)
        self.assertIn("picture = GFX_report_event_generic_diplomacy", prompt)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_collapse_started", prompt)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_collapse_wars_started", prompt)
        self.assertIn("ai_chance = { base = 100 }", prompt)
        self.assertIn("ai_chance = { base = 0 }", prompt)
        self.assertIn("ADISCORD_rin_begin_oath_crisis = yes", prompt)

    def test_subject_break_precedes_one_day_cache_barrier(self) -> None:
        begin = named_block(read(EFFECTS), "ADISCORD_rin_begin_oath_crisis")
        self.assertIn("autonomy_state = autonomy_free", begin)
        self.assertIn("ADISCORD_rin_crisis.2 days = 1", begin)
        self.assertLess(begin.find("autonomy_state = autonomy_free"), begin.find("ADISCORD_rin_crisis.2 days = 1"))

    def test_split_is_exact_and_does_not_merge_wars(self) -> None:
        effects = read(EFFECTS)
        split = named_block(effects, "ADISCORD_rin_start_oath_civil_war")
        for token in (
            "size = 0", "army_ratio = 0.40", "capital = 147",
            "states = { 134 147 }", "set_cosmetic_tag = RIN_northern_court",
            "save_global_event_target_as = ADISCORD_rin_southern_charter",
            "set_country_flag = ADISCORD_rin_southern_charter_side",
        ):
            self.assertIn(token, split)
        self.assertNotIn("\n\tRIN = {", split)
        combined = effects + read(EVENTS) + read(ON_ACTIONS)
        for forbidden in ("declare_war_on", "add_to_war", "create_faction", "add_to_faction"):
            self.assertNotIn(forbidden, combined)

    def test_mission_starts_only_after_split_and_lasts_180_days(self) -> None:
        mission = named_block(read(DECISIONS), "ADISCORD_rin_palatin_breakup_mission")
        self.assertIn("activation = { always = no }", mission)
        self.assertIn("available = { always = no }", mission)
        self.assertIn("selectable_mission = no", mission)
        self.assertIn("days_mission_timeout = 180", mission)
        self.assertNotIn("activate_mission", mission)
        split = named_block(read(EFFECTS), "ADISCORD_rin_start_oath_civil_war")
        self.assertEqual(split.count("activate_mission = ADISCORD_rin_palatin_breakup_mission"), 1)

    def test_capitulation_router_preempts_generic_fallback(self) -> None:
        capitulation = named_block(read(ON_ACTIONS), "on_capitulation")
        self.assertEqual(capitulation.count("set_global_flag = skip_default_capitulation"), 2)
        self.assertEqual(capitulation.count("annex_country = { target = ROOT transfer_troops = yes }"), 2)
        self.assertIn("ADISCORD_rin_complete_southern_victory = yes", capitulation)
        self.assertIn("ADISCORD_rin_complete_northern_victory = yes", capitulation)

    def test_timeout_is_local_partition_not_external_war(self) -> None:
        armistice = named_block(read(EFFECTS), "ADISCORD_rin_force_partition_armistice")
        self.assertIn("save_global_event_target_as = ADISCORD_rin_southern_charter", armistice)
        self.assertIn("has_war_with = ROOT", armistice)
        self.assertIn("white_peace = ROOT", armistice)
        self.assertIn("ADISCORD_rin_complete_partition_armistice = yes", armistice)

    def test_partition_repairs_exact_two_four_border_in_southern_root(self) -> None:
        effects = read(EFFECTS)
        apply = named_block(effects, "ADISCORD_rin_apply_partition_armistice")
        north = named_block(apply, "event_target:ADISCORD_rin_northern_court")
        all_transfers = [int(value) for value in re.findall(r"\btransfer_state\s*=\s*(\d+)", apply)]
        north_transfers = [int(value) for value in re.findall(r"\btransfer_state\s*=\s*(\d+)", north)]
        self.assertEqual(all_transfers, [146, 148, 149, 150, 134, 147])
        self.assertEqual(north_transfers, [134, 147])
        self.assertNotIn("\n\tRIN = {", apply)
        for state in (146, 148, 149, 150):
            self.assertIn(
                f"{state} = {{ set_state_controller_to = event_target:ADISCORD_rin_southern_charter }}",
                apply,
            )
        for state in (134, 147):
            self.assertIn(
                f"{state} = {{ set_state_controller_to = event_target:ADISCORD_rin_northern_court }}",
                apply,
            )

    def test_partition_outcomes_and_temporary_content_are_mutually_exclusive(self) -> None:
        apply = named_block(read(EFFECTS), "ADISCORD_rin_apply_partition_armistice")
        north = named_block(apply, "event_target:ADISCORD_rin_northern_court")
        for token in (
            "remove_mission = ADISCORD_rin_palatin_breakup_mission",
            "remove_ideas = RIN_two_oaths",
            "remove_ideas = RIN_southern_charter_mobilization",
            "remove_ideas = RIN_northern_crown_columns",
            "add_ideas = RIN_charter_compact",
            "set_country_flag = ADISCORD_rin_charter_compact_survived",
            "clr_country_flag = ADISCORD_rin_crown_palatin_survived",
        ):
            self.assertIn(token, apply)
        for token in (
            "remove_ideas = RIN_charter_compact",
            "add_ideas = RIN_crown_palatin",
            "set_country_flag = ADISCORD_rin_crown_palatin_survived",
            "clr_country_flag = ADISCORD_rin_charter_compact_survived",
        ):
            self.assertIn(token, north)
        self.assertIn("puppet = event_target:ADISCORD_rin_northern_court", apply)
        self.assertIn("autonomy_state = autonomy_puppet", apply)

    def test_partition_verification_is_one_day_and_has_only_one_retry(self) -> None:
        events = read(EVENTS)
        first = event_block(events, "ADISCORD_rin_crisis.3")
        terminal = event_block(events, "ADISCORD_rin_crisis.4")
        self.assertIn("ADISCORD_rin_partition_armistice_is_valid = yes", first)
        self.assertEqual(first.count("ADISCORD_rin_apply_partition_armistice = yes"), 1)
        self.assertEqual(first.count("ADISCORD_rin_crisis.4 days = 1"), 1)
        self.assertIn("ADISCORD_rin_oath_crisis_terminal_failure", terminal)
        self.assertNotIn("ADISCORD_rin_apply_partition_armistice = yes", terminal)
        self.assertEqual(terminal.count("country_event ="), 1)
        completion = named_block(read(EFFECTS), "ADISCORD_rin_complete_partition_armistice")
        self.assertEqual(completion.count("ADISCORD_rin_crisis.3 days = 1"), 1)

    def test_external_peace_uses_cached_southern_country_not_original_tag(self) -> None:
        peace = named_block(read(ON_ACTIONS), "on_peace")
        self.assertIn("event_target:ADISCORD_rin_southern_charter", peace)
        self.assertNotIn("RIN = { ADISCORD_rin_complete_partition_armistice = yes }", peace)


if __name__ == "__main__":
    unittest.main()
