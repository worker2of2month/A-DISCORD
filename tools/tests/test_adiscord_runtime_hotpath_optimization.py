from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    opening = source.find("{", match.start())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


class RuntimeHotpathOptimizationTests(unittest.TestCase):
    def test_kefreyt_contract_monthly_hook_is_tag_scoped(self) -> None:
        source = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        self.assertIn("on_monthly_VAL = {", source)
        self.assertIsNone(re.search(r"(?m)^\s*on_monthly\s*=", source))
        monthly = named_block(source, "on_monthly_VAL")
        self.assertNotIn("tag = VAL", monthly)
        self.assertIn("VAL_quarterly_contract_active", monthly)

    def test_kefreyt_trade_refresh_is_bounded_to_route_nodes(self) -> None:
        source = read("common/on_actions/03_ADISCORD_VAL_logistics_market_on_actions.txt")
        state_hook = named_block(source, "on_state_control_changed")
        self.assertEqual(state_hook.count("VAL_refresh_trade_network = yes"), 1)
        for state_id in (29, 33, 43, 44, 46, 59, 60, 61, 88):
            self.assertIn(f"state = {state_id}", state_hook)
        for unrelated in (32, 38, 75, 90, 230):
            self.assertNotIn(f"state = {unrelated}", state_hook)

    def test_operations_map_cache_is_event_driven(self) -> None:
        owner = read("common/on_actions/04_ADISCORD_operations_map_on_actions.txt")
        state_hook = named_block(owner, "on_state_control_changed")
        startup = named_block(owner, "on_startup")
        self.assertGreaterEqual(startup.count("VAL_operations_map_refresh_cache = yes"), 2)
        self.assertGreaterEqual(state_hook.count("VAL_operations_map_refresh_cache = yes"), 2)
        self.assertIn("ROOT = {", state_hook)
        self.assertIn("FROM = {", state_hook)
        self.assertIn("has_country_flag = VAL_operations_map_unlocked", state_hook)
        self.assertIn("has_country_flag = STP_cw_postwar", state_hook)
        for path, hook in (
            ("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt", "on_weekly_VAL"),
            ("common/on_actions/02_ADISCORD_STP_on_actions.txt", "on_weekly_STS"),
        ):
            self.assertNotIn("VAL_operations_map_refresh_cache", named_block(read(path), hook))

    def test_kefreyt_resource_rights_checks_follow_their_states(self) -> None:
        source = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        state_hook = named_block(source, "on_state_control_changed")
        self.assertIn(
            "FROM.FROM = { state = 33 }\n\t\t\t\t\tVAL = {",
            state_hook,
        )
        self.assertIn(
            "FROM.FROM = { state = 38 }\n\t\t\t\t\tVAL = {",
            state_hook,
        )

    def test_economy_initialization_recomputes_model_once(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_economy_effects.txt")
        initialize = named_block(effects, "ADISCORD_economy_initialize_country")
        self.assertEqual(initialize.count("ADISCORD_economy_update_model_and_cycle = yes"), 1)

    def test_stelander_union_recovery_has_no_global_daily_poll(self) -> None:
        source = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        self.assertIsNone(re.search(r"(?m)^\s*on_daily\s*=", source))
        daily = named_block(source, "on_daily_STP")
        self.assertNotIn("STP_cw_check_union_wars_finished = yes", daily)
        self.assertIsNone(re.search(r"(?m)^\s*on_daily_STS\s*=", source))


    def test_new_campaign_phase_initializes_postwar_without_weekly_repair(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        finish = named_block(effects, "STP_cw_finish_mobilization")
        self.assertLess(finish.index("set_country_flag = STP_cw_postwar"), finish.index("STP_pw_reconcile_postwar_interactivity = yes"))
        weekly = named_block(read("common/on_actions/02_ADISCORD_STP_on_actions.txt"), "on_weekly_STS")
        self.assertNotIn("STP_pw_reconcile_postwar_interactivity", weekly)
        focus = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        for slot in (1, 2):
            self.assertIn(f"set_country_flag = STP_pw_propaganda_slot_{slot}", focus)
        self.assertNotIn("has_completed_focus", named_block(effects, "STP_pw_reconcile_postwar_interactivity"))

    def test_supply_outbreak_has_an_authored_producer_without_weekly_migration(self):
        weekly = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_weekly_VAL")
        self.assertNotIn("VAL_reconcile_supply_crisis", weekly)
        self.assertIn("VAL_handle_vorkerland_war_outbreak = yes", read("events/ADISCORD_vorkerland_events.txt"))
        repair = named_block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_reconcile_supply_crisis")
        self.assertNotIn("has_completed_focus", repair)
        self.assertNotIn("set_variable", repair)

    def test_nam_territorial_check_uses_its_state_and_annex_edge(self):
        hooks = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        state = named_block(hooks, "on_state_control_changed")
        self.assertIn("limit = { FROM.FROM = { state = 230 } }", state)
        self.assertEqual(state.count("VAL_check_nam_concession = yes"), 1)
        annex = named_block(read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"), "on_annex")
        self.assertIn("FROM = { tag = NAM }", annex)
        self.assertIn("VAL_check_nam_concession = yes", annex)
        self.assertIn("VAL_cancel_nam_concession = yes", read("common/scripted_effects/ADISCORD_nam_resource_war_effects.txt"))

    def test_frontier_victory_uses_one_shot_native_notifications(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        weekly = named_block(effects, "VAL_frontier_weekly")
        self.assertNotIn("VAL_frontier_settle_victory = yes", weekly)
        self.assertNotIn("VAL_frontier_reconcile = yes", weekly)
        self.assertIn("surrender_progress > 0.65", weekly)
        reconcile = named_block(effects, "VAL_frontier_reconcile")
        self.assertIn("VAL_frontier_settle_victory = yes", reconcile)
        self.assertLess(
            reconcile.index("VAL_frontier_settle_victory = yes"),
            reconcile.index("VAL_frontier_has_campaign_war = no"),
            "A post-peace callback must award victory before generic no-war cleanup",
        )
        shared = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        for hook in ("on_capitulation", "on_peace", "on_annex", "on_peaceconference_ended", "on_state_control_changed"):
            self.assertIn("VAL_queue_frontier_reconciliation = yes", named_block(shared, hook))
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, scalar, walk
        events = parse_clausewitz(read("events/ADISCORD_VAL_contract_events.txt"))
        found = [
            entry.value
            for entry in events
            if entry.key == "country_event" and scalar(entry.value, "id") == "val_rework.102"
        ]
        self.assertEqual(len(found), 1)
        event = found[0]
        self.assertIn("VAL_frontier_reconcile", {entry.key for entry in walk(event)})
        self.assertNotIn("country_event", {entry.key for entry in walk(event)})

    def test_trade_cache_detects_every_route_transition_before_payment(self):
        from itertools import product
        from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, matches_conditions
        triggers = parse_clausewitz(read("common/scripted_triggers/ADISCORD_VAL_logistics_market_triggers.txt"))
        gate = block(triggers, "VAL_trade_network_changed")
        routes = ("occidia", "north", "stelander", "vorkerland")
        for cached in product((0, 1), repeat=4):
            for current in product((0, 1), repeat=4):
                facts = {("VAL", "VAL_trade_corridors_unlocked", "yes"): True,
                         ("VAL", "VAL_trade_corridors_unlocked", "no"): False,
                         ("VAL", "has_idea", "VAL_corridor_network_partial"): True}
                for route, old, new in zip(routes, cached, current):
                    facts["VAL", "variable", f"VAL_route_{route}_active"] = old
                    facts["VAL", f"VAL_trade_route_{route}_open", "yes"] = bool(new)
                    facts["VAL", f"VAL_trade_route_{route}_open", "no"] = not new
                self.assertEqual(matches_conditions(gate, facts, "VAL"), cached != current, (cached, current))
        effects = named_block(read("common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt"), "VAL_logistics_market_weekly")
        self.assertLess(effects.index("VAL_trade_network_changed"), effects.index("VAL_pay_trade_corridors"))

    def test_nod_intervention_has_one_periodic_owner_and_annex_cleanup(self):
        hooks = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        self.assertIn("STP_cw_poll_nod_intervention = yes", named_block(hooks, "on_weekly_NOD"))
        self.assertNotIn("STP_cw_poll_nod_intervention", named_block(hooks, "on_weekly_STS"))
        shared = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        annex = named_block(shared, "on_annex")
        self.assertIn("if = { limit = { FROM = { tag = NOD } } STP_cw_poll_nod_intervention = yes }", annex)
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        for mission in ("NOD_cw_intervention_preparation", "NOD_cw_northern_redeployment"):
            self.assertIn("STP_cw_poll_nod_intervention = yes", named_block(decisions, mission))
        effect = named_block(read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_poll_nod_intervention")
        for marker in ("NOD_cw_intervention_approved", "NOD_cw_intervention_ready", "STP_cw_nod_warning_active"):
            self.assertIn("clr_country_flag = " + marker, effect)


if __name__ == "__main__":
    unittest.main()
