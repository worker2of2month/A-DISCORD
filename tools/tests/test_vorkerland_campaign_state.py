from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_vorkerland_recovery import named_block


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class VorkerlandCampaignStateTests(unittest.TestCase):
    def test_calendar_controller_is_retired(self) -> None:
        production_paths = (
            "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt",
            "common/scripted_triggers/ADISCORD_vorkerland_phase_triggers.txt",
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            "events/ADISCORD_vorkerland_collapse_events.txt",
            "common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt",
        )
        retired_tokens = (
            "global.ADISCORD_vorkerland_war_month",
            "global.ADISCORD_vorkerland_live_claimants",
            "ADISCORD_vorkerland_is_war_clock_owner",
            "ADISCORD_vorkerland_advance_war_clock",
            "ADISCORD_vorkerland_tick_claimant_state",
        )
        for relative in production_paths:
            source = read(relative)
            for token in retired_tokens:
                self.assertNotIn(token, source, f"{relative} still uses {token}")

        on_actions = read(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
        )
        self.assertEqual(named_block(on_actions, "on_monthly"), "")

    def test_only_factory_scaling_remains_monthly(self) -> None:
        on_actions = read(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
        )
        for tag in ("WKR", "VAD", "TVA"):
            hook = named_block(on_actions, f"on_monthly_{tag}")
            self.assertTrue(hook, f"missing on_monthly_{tag}")
            self.assertEqual(
                hook.count(
                    "ADISCORD_vorkerland_refresh_war_economy_dynamic_state = yes"
                ),
                1,
            )
            self.assertIn("ADISCORD_vorkerland_is_live_claimant = yes", hook)
            self.assertNotIn("ADISCORD_vorkerland_refresh_doctrine_dynamic_state", hook)
            self.assertNotIn("every_country", hook)
            self.assertNotIn("every_state", hook)

    def test_dynamic_effect_owners_are_split(self) -> None:
        legacy = ROOT / "common/scripted_effects/ADISCORD_vorkerland_focus_dynamic_effects.txt"
        self.assertFalse(legacy.exists())

        economy = read(
            "common/scripted_effects/ADISCORD_vorkerland_war_economy_effects.txt"
        )
        doctrine = read(
            "common/scripted_effects/ADISCORD_vorkerland_doctrine_effects.txt"
        )
        self.assertTrue(
            named_block(economy, "ADISCORD_vorkerland_refresh_war_economy_dynamic_state")
        )
        self.assertTrue(
            named_block(doctrine, "ADISCORD_vorkerland_refresh_doctrine_dynamic_state")
        )
        self.assertTrue(
            named_block(doctrine, "ADISCORD_vorkerland_apply_focus_doctrine")
        )

    def test_legitimacy_leader_preserves_a_live_incumbent_on_ties(self) -> None:
        campaign = read(
            "common/scripted_effects/ADISCORD_vorkerland_campaign_state_effects.txt"
        )
        leader = named_block(
            campaign, "ADISCORD_vorkerland_refresh_legitimacy_leader"
        )
        first_clear = leader.find(
            "clr_country_flag = ADISCORD_vorkerland_legitimacy_leader"
        )
        self.assertGreater(first_clear, 0)
        for tag in ("WKR", "VAD", "TVA"):
            incumbent = leader.find(
                f"{tag} = {{ has_country_flag = ADISCORD_vorkerland_legitimacy_leader"
            )
            self.assertGreaterEqual(incumbent, 0, f"missing incumbent guard for {tag}")
            self.assertLess(incumbent, first_clear)
        self.assertGreaterEqual(leader.count("compare = greater_than"), 6)

    def test_coalition_requires_a_territorial_majority(self) -> None:
        campaign = read(
            "common/scripted_effects/ADISCORD_vorkerland_campaign_state_effects.txt"
        )
        coalition = named_block(
            campaign, "ADISCORD_vorkerland_refresh_claimant_coalition"
        )
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
            coalition,
        )
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
            coalition,
        )
        self.assertIn("compare = greater_than", coalition)
        self.assertRegex(
            coalition,
            r"ADISCORD_vorkerland_central_control_score\s+value\s*=\s*8\b",
        )
        for tag in ("wkr", "vad", "tva"):
            idea = f"ADISCORD_vorkerland_coalition_against_{tag}"
            self.assertIn(f"remove_ideas = {idea}", coalition)
            self.assertIn(f"add_ideas = {idea}", coalition)
        self.assertNotIn("war_month", coalition)

    def test_collapse_and_phase_transitions_reconcile_immediately(self) -> None:
        collapse = read("events/ADISCORD_vorkerland_collapse_events.txt")
        event = re.search(
            r"(?s)country_event\s*=\s*\{\s*id\s*=\s*ADISCORD_vorkerland_collapse\.2\b(.*?)\n\}",
            collapse,
        )
        self.assertIsNotNone(event)
        event_text = event.group(1)
        started = event_text.find(
            "set_global_flag = ADISCORD_vorkerland_collapse_wars_started"
        )
        attrition = event_text.find("ADISCORD_vorkerland_apply_central_attrition = yes")
        reconcile = event_text.find("ADISCORD_vorkerland_reconcile_campaign_state = yes")
        self.assertTrue(0 <= started < attrition < reconcile)
        for tag in ("WKR", "VAD", "TVA"):
            initialize = (
                f"{tag} = {{ ADISCORD_vorkerland_initialize_legitimacy = yes }}"
            )
            self.assertEqual(event_text.count(initialize), 1)
            self.assertLess(event_text.find(initialize), reconcile)

        phase = read("common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt")
        showdown = named_block(phase, "ADISCORD_vorkerland_set_phase_central_showdown")
        terminal = named_block(phase, "ADISCORD_vorkerland_finalize_reunified_wrk")
        self.assertIn("ADISCORD_vorkerland_reconcile_campaign_state = yes", showdown)
        self.assertIn("ADISCORD_vorkerland_reconcile_campaign_state = yes", terminal)

    def test_central_state_edges_recount_and_refresh_coalitions(self) -> None:
        on_actions = read(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
        )
        state_hook = named_block(on_actions, "on_state_control_changed")
        for state in (32, 33, 35, 36, 37, 38, 39, 40, 75, 81, 102, 104, 106, 121, 122, 123, 124):
            self.assertIn(f"state = {state}", state_hook)
        self.assertIn("ADISCORD_vorkerland_recount_central_control = yes", state_hook)
        self.assertIn("ADISCORD_vorkerland_refresh_legitimacy_leader = yes", state_hook)
        self.assertEqual(
            state_hook.count("ADISCORD_vorkerland_refresh_claimant_coalition = yes"),
            3,
        )


if __name__ == "__main__":
    unittest.main()
