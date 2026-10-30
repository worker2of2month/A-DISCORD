from __future__ import annotations
from tools.lib.on_actions import read_country_on_actions

import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source

from tools.validators.validate_adiscord_vorkerland_recovery import named_block, named_blocks


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return read_focus_source(ROOT / relative, encoding="utf-8-sig")


class VorkerlandCampaignStateTests(unittest.TestCase):
    def test_calendar_controller_is_retired(self) -> None:
        production_paths = (
            "common/scripted_effects/ADISCORD_vorkerland_effects.txt",
            "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt",
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            "events/ADISCORD_vorkerland_events.txt",
            "common/national_focus/ADISCORD_vorkerland_focus.txt",
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

        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            'vorkerland_collapse',
        )
        self.assertEqual(named_block(on_actions, "on_monthly"), "")

    def test_only_factory_scaling_remains_monthly(self) -> None:
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            'vorkerland_collapse',
        )
        self.assertEqual(named_block(on_actions, "on_monthly_TVA"), "")
        for tag in ("WKR", "VAD"):
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
        legacy = (
            ROOT
            / "common/scripted_effects/ADISCORD_vorkerland_focus_dynamic_effects.txt"
        )
        self.assertFalse(legacy.exists())

        economy = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'war_economy_effects',
        )
        doctrine = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'doctrine_effects',
        )
        self.assertTrue(
            named_block(
                economy, "ADISCORD_vorkerland_refresh_war_economy_dynamic_state"
            )
        )
        self.assertTrue(
            named_block(doctrine, "ADISCORD_vorkerland_refresh_doctrine_dynamic_state")
        )
        self.assertTrue(
            named_block(doctrine, "ADISCORD_vorkerland_apply_focus_doctrine")
        )

    def test_legitimacy_leader_preserves_a_live_incumbent_on_ties(self) -> None:
        campaign = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'campaign_state_effects',
        )
        leader = named_block(campaign, "ADISCORD_vorkerland_refresh_legitimacy_leader")
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

    def test_coalition_uses_the_configured_early_lead_threshold(self) -> None:
        campaign = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'campaign_state_effects',
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
        collapse = source_section(
            read("events/ADISCORD_vorkerland_events.txt"), 'collapse_events'
        )
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
        reconcile = event_text.find(
            "ADISCORD_vorkerland_reconcile_campaign_state = yes"
        )
        self.assertTrue(0 <= started < attrition < reconcile)
        for tag in ("WKR", "VAD", "TVA"):
            initialize = "ADISCORD_vorkerland_initialize_legitimacy = yes"
            scopes = [block for block in named_blocks(event_text, tag) if initialize in block]
            self.assertEqual(len(scopes), 1)
            self.assertEqual(scopes[0].count(initialize), 1)
            self.assertLess(event_text.find(scopes[0]) + scopes[0].find(initialize), reconcile)
            if tag in ("TVA", "VAD"):
                self.assertEqual(scopes[0].count(f"{tag}_initialize_administration = yes"), 1)

        phase = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        showdown = named_block(phase, "ADISCORD_vorkerland_set_phase_central_showdown")
        terminal = named_block(phase, "ADISCORD_vorkerland_finalize_reunified_wrk")
        self.assertIn("ADISCORD_vorkerland_reconcile_campaign_state = yes", showdown)
        self.assertIn("ADISCORD_vorkerland_reconcile_campaign_state = yes", terminal)

    def test_central_state_edges_recount_and_refresh_coalitions(self) -> None:
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            'vorkerland_collapse',
        )
        state_hook = named_block(on_actions, "on_state_control_changed")
        self.assertIn(
            "FROM.FROM = { has_state_flag = ADISCORD_vorkerland_central_theatre }",
            state_hook,
        )
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        marked = set(re.findall(
            r"(\d+)\s*=\s*\{\s*set_state_flag = ADISCORD_vorkerland_central_theatre",
            effects,
        ))
        expected_states = {
            "32", "33", "35", "36", "37", "38", "39", "75", "81",
            "102", "106", "121", "122", "123", "124",
        }
        self.assertTrue(expected_states <= marked)
        self.assertIn("ADISCORD_vorkerland_recount_central_control = yes", state_hook)
        self.assertIn("ADISCORD_vorkerland_refresh_legitimacy_leader = yes", state_hook)
        self.assertEqual(
            state_hook.count("ADISCORD_vorkerland_refresh_claimant_coalition = yes"), 3
        )

    def test_district_orders_follow_native_state_loss_and_country_handoffs(self) -> None:
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            "vorkerland_collapse",
        )
        state_hook = named_block(on_actions, "on_state_control_changed")
        self.assertIn("FROM.FROM = { VAD_lose_district_administration = yes }", state_hook)
        for flag in ("VAD_oath_in_progress", "ADISCORD_vorkerland_vad_district_oath"):
            self.assertIn(f"has_state_flag = {flag}", state_hook)
        for hook in ("on_capitulation_immediate", "on_capitulation", "on_puppet"):
            hooks = "\n".join(named_blocks(on_actions, hook))
            self.assertEqual(hooks.count("VAD_refund_oath = yes"), 1, hook)
        annex = "\n".join(named_blocks(on_actions, "on_annex"))
        self.assertIn("limit = { FROM = { tag = VAD } }", annex)
        self.assertIn("ROOT = { VAD_settle_oath_handoff = yes }", annex)
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        for claimant in ("wkr", "vad", "tva"):
            handoff = named_block(effects, f"ADISCORD_vorkerland_form_wrk_from_{claimant}")
            self.assertEqual(handoff.count("VAD_settle_oath_handoff = yes"), 1, claimant)
            self.assertLess(handoff.index("transfer_state = 32"), handoff.index("VAD_settle_oath_handoff = yes"))
            self.assertLess(handoff.index("VAD_settle_oath_handoff = yes"), handoff.index("load_focus_tree"))
            self.assertLess(handoff.index("VAD_settle_oath_handoff = yes"),
                            handoff.index("country_event = { id = ADISCORD_vorkerland_phase.7 hours = 1 }"))
            self.assertLess(handoff.index("VAD_settle_oath_handoff = yes"),
                            re.search(r"\bchange_tag_from\s*=", handoff).start())
            completion = named_block(effects, f"ADISCORD_vorkerland_complete_wrk_from_{claimant}")
            self.assertRegex(completion, r"annex_country\s*=\s*\{\s*target = VAD")

    def test_factory_orders_settle_before_native_peace_or_player_handoff(self) -> None:
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            "vorkerland_collapse",
        )
        for hook in ("on_capitulation_immediate", "on_capitulation", "on_puppet"):
            callbacks = "\n".join(named_blocks(on_actions, hook))
            self.assertEqual(callbacks.count("WKR_refund_council_order = yes"), 1, hook)
        annex = "\n".join(named_blocks(on_actions, "on_annex"))
        self.assertIn("limit = { FROM = { tag = WKR } }", annex)
        self.assertTrue(any("WKR_settle_council_order_handoff = yes" in block
                            for block in named_blocks(annex, "ROOT")))
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        for claimant in ("wkr", "vad", "tva"):
            handoff = named_block(effects, f"ADISCORD_vorkerland_form_wrk_from_{claimant}")
            self.assertEqual(handoff.count("WKR_settle_council_order_handoff = yes"), 1)
            self.assertLess(handoff.index("transfer_state = 32"), handoff.index("WKR_settle_council_order_handoff"))
            self.assertLess(handoff.index("WKR_settle_council_order_handoff"), handoff.index("WKR_close_administration"))
            self.assertLess(handoff.index("WKR_close_administration"), handoff.index("load_focus_tree"))
        cleanup = named_block(effects, "ADISCORD_vorkerland_clear_claimant_war_modifiers")
        self.assertLess(cleanup.index("WKR_close_administration"), cleanup.index("remove_dynamic_modifier"))
        close = named_block(effects, "WKR_close_council_orders")
        self.assertLess(close.index("WKR_refund_council_order"), close.index("set_division_template_lock"))

    def test_railway_orders_settle_before_native_peace_or_player_handoff(self) -> None:
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            "vorkerland_collapse",
        )
        for hook in ("on_capitulation_immediate", "on_capitulation", "on_puppet"):
            callbacks = "\n".join(named_blocks(on_actions, hook))
            self.assertEqual(callbacks.count("WKR_refund_railway_order = yes"), 1, hook)
        annex = "\n".join(named_blocks(on_actions, "on_annex"))
        self.assertTrue(any("WKR_settle_railway_handoff = yes" in block
                            for block in named_blocks(annex, "ROOT")))
        self.assertLess(annex.index("WKR_settle_railway_handoff"), annex.index("WKR_close_railway_councils"))
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        for claimant in ("wkr", "vad", "tva"):
            handoff = named_block(effects, f"ADISCORD_vorkerland_form_wrk_from_{claimant}")
            self.assertEqual(handoff.count("WKR_settle_railway_handoff = yes"), 1)
            self.assertLess(handoff.index("transfer_state = 32"), handoff.index("WKR_settle_railway_handoff"))
            self.assertLess(handoff.index("WKR_settle_railway_handoff"), handoff.index("WKR_close_administration"))
            self.assertLess(handoff.index("WKR_close_administration"), handoff.index("load_focus_tree"))
        control = named_block(on_actions, "on_state_control_changed")
        self.assertIn("FROM.FROM = { WKR_lose_railway_council = yes }", control)
        for callback in ("on_daily", "on_weekly", "on_monthly"):
            self.assertNotIn("WKR_railway", "\n".join(named_blocks(on_actions, callback)))

    def test_recognition_offers_close_on_terminal_hooks_and_honour_only_worker_settlement(self) -> None:
        on_actions = read_country_on_actions(
            "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt",
            "vorkerland_collapse",
        )
        for hook in ("on_capitulation_immediate", "on_capitulation", "on_puppet", "on_annex"):
            callbacks = "\n".join(named_blocks(on_actions, hook))
            self.assertEqual(callbacks.count("WKR_close_recognition_offers = yes"), 1, hook)
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        self.assertIn("WKR_close_recognition_offers = yes", named_block(effects, "WKR_close_administration"))
        callers = [block for block in named_blocks(effects, "if")
                   if "ADISCORD_vorkerland_resolve_unguaranteed_free_republics = yes" in block
                   and "has_country_flag = ADISCORD_vorkerland_route_worker" in named_block(block, "limit")]
        self.assertEqual(len(callers), 1)


if __name__ == "__main__":
    unittest.main()
