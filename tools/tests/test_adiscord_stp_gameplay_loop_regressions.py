from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
EVENTS = ROOT / "events/ADISCORD_STP_events.txt"
AI = ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    marker = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if marker is None:
        raise AssertionError(f"missing block: {name}")
    opening = source.find("{", marker.start())
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(source)):
        ch = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[marker.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


def event_block(source: str, event_id: str) -> str:
    start = source.index(f"\tid = {event_id}\n")
    opening = source.rfind("country_event = {", 0, start)
    return named_block(source[opening:], "country_event")


class StelanderGameplayLoopRegressionTests(unittest.TestCase):
    def test_inspection_scheduler_reconciles_to_one_or_two(self) -> None:
        effects = read(EFFECTS)
        scheduler = named_block(effects, "STP_schedule_next_party_inspection")
        opener = named_block(effects, "STP_cw_open_one_party_inspection")

        self.assertIn("has_country_flag = STP_cw_inspection_chain_open", scheduler)
        self.assertIn("NOT = { STP_cw_two_inspections_active = yes }", scheduler)
        self.assertIn("NOT = { STP_cw_any_inspection_active = yes }", scheduler)
        self.assertIn("STP_cw_second_inspection_unlocked = yes", scheduler)
        self.assertEqual(scheduler.count("STP_cw_open_one_party_inspection = yes"), 2)
        self.assertNotIn("1 = { }", opener, "a valid chain must not randomly stop while districts remain eligible")

        triggers = read(TRIGGERS)
        any_active = named_block(triggers, "STP_cw_any_inspection_active")
        for state in (2, 3, 29, 45, 46, 53):
            self.assertIn(f"{state} = {{ has_state_flag = STP_party_inspection_active }}", any_active)

    def test_inspection_delay_targets_one_commission(self) -> None:
        decision = named_block(read(DECISIONS), "STP_cw_delay_inspection")
        self.assertIn("state_target = yes", decision)
        self.assertIn("targets = { 2 3 29 45 46 53 }", decision)
        self.assertIn("FROM = { has_state_flag = STP_party_inspection_active }", decision)
        self.assertIn("target_trigger = { FROM = { is_owned_by = ROOT } }", decision)
        for state in (2, 3, 29, 45, 46, 53):
            self.assertIn(f"FROM = {{ state = {state} }}", decision)
            self.assertEqual(
                decision.count(f"mission = STP_party_inspection_state_{state} days = 14"),
                1,
                state,
            )

    def test_last_banquet_is_a_single_fada_deadline(self) -> None:
        decisions = read(DECISIONS)
        launch = named_block(decisions, "STP_cw_launch_last_banquet")
        mission = named_block(decisions, "STP_cw_last_banquet_window")

        self.assertIn("controls_state = 3", launch, "Niansas remains the staging requirement")
        self.assertIn("NOT = { has_country_flag = STP_cw_last_banquet_launched }", launch)
        self.assertIn("fire_only_once = yes", launch)
        self.assertIn("set_country_flag = STP_cw_last_banquet_launched", launch)
        self.assertIn("activate_mission = STP_cw_last_banquet_window", launch)
        self.assertIn("idea = STP_cw_deliberate_offensive days = 21", launch)

        self.assertIn("available = { controls_state = 28 }", mission)
        self.assertIn("days_mission_timeout = 21", mission)
        self.assertIn("selectable_mission = no", mission)
        self.assertIn("fire_only_once = yes", mission)
        self.assertIn("set_country_flag = STP_cw_last_banquet_success", mission)
        self.assertIn("set_country_flag = STP_cw_last_banquet_failed", mission)
        self.assertIn("add_war_support = -0.10", mission)

    def test_nod_timing_controls_keep_authoritative_and_mirror_missions_in_sync(self) -> None:
        decisions = read(DECISIONS)
        challenge = named_block(decisions, "STP_cw_trigger_northern_incident")
        sabotage = named_block(decisions, "STP_cw_sabotage_nodrul")

        # The challenge disputes intervention grounds, so it delays both clocks.
        self.assertIn("mission = NOD_cw_intervention_preparation days = 10", challenge)
        self.assertIn("mission = STP_cw_nod_warning days = 10", challenge)
        # A successful rear-area sabotage adds the same seven-day delay to both mirrors.
        self.assertIn("mission = NOD_cw_intervention_preparation days = 7", sabotage)
        self.assertIn("mission = STP_cw_nod_warning days = 7", sabotage)

    def test_last_banquet_closes_stale_nod_intervention_card(self) -> None:
        triggers = read(TRIGGERS)
        possible = named_block(triggers, "NOD_cw_intervention_possible")
        self.assertIn("STS = { has_country_flag = STP_cw_last_banquet_success }", possible)
        self.assertIn("NOT = {", possible)

        event = event_block(read(EVENTS), "ADISCORD_STP_cw.42")
        self.assertEqual(event.count("option = {"), 3)
        self.assertGreaterEqual(event.count("trigger = { NOD_cw_intervention_possible = yes }"), 2)
        self.assertIn("trigger = { NOD_cw_intervention_possible = no }", event)
        self.assertIn("ADISCORD_STP_cw.42.c", event)

    def test_party_ai_commits_a_real_reserve_to_fada(self) -> None:
        defend = named_block(read(AI), "STP_cw_defend_fada")
        self.assertIn("states = { 28 }", defend)
        self.assertIn("ratio = 0.20", defend)


if __name__ == "__main__":
    unittest.main()
