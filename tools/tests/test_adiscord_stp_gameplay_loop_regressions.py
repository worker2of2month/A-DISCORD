from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
AI = ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    marker = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if marker is None:
        raise AssertionError(f"missing block: {name}")
    opening = source.find("{", marker.start())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[marker.start() : index + 1]
    raise AssertionError(f"unterminated block: {name}")


class StelanderGameplayLoopRegressionTests(unittest.TestCase):
    def test_inspection_scheduler_reconciles_to_one_or_two(self) -> None:
        effects = read(EFFECTS)
        scheduler = named_block(effects, "STP_schedule_next_party_inspection")
        opener = named_block(effects, "STP_cw_open_one_party_inspection")

        self.assertIn("has_country_flag = STP_cw_inspection_chain_open", scheduler)
        self.assertIn("STP_cw_any_inspection_active = yes", scheduler)
        self.assertIn("STP_cw_second_inspection_unlocked = yes", scheduler)
        self.assertEqual(scheduler.count("STP_cw_open_one_party_inspection = yes"), 2)
        self.assertNotIn("1 = { }", opener, "a valid chain must not randomly stop while districts remain eligible")

    def test_inspection_delay_targets_one_commission(self) -> None:
        decision = named_block(read(DECISIONS), "STP_cw_delay_inspection")
        self.assertIn("state_target = yes", decision)
        self.assertIn("targets = { 2 3 29 45 46 53 }", decision)
        self.assertIn("FROM = { has_state_flag = STP_party_inspection_active }", decision)
        for state in (2, 3, 29, 45, 46, 53):
            self.assertIn(f"FROM = {{ state = {state} }}", decision)
            self.assertEqual(
                decision.count(f"mission = STP_party_inspection_state_{state} days = 14"),
                1,
                state,
            )

    def test_last_banquet_is_a_single_fada_deadline(self) -> None:
        decision = named_block(read(DECISIONS), "STP_cw_launch_last_banquet")
        self.assertIn("controls_state = 3", decision, "Niansas remains the staging requirement")
        self.assertIn("days_remove = 21", decision)
        self.assertIn("fire_only_once = yes", decision)
        self.assertIn("NOT = { controls_state = 28 }", decision)
        self.assertIn("add_war_support = -0.10", decision)
        self.assertIn("idea = STP_cw_deliberate_offensive days = 21", decision)

    def test_nod_timing_controls_adjust_authoritative_and_mirror_missions(self) -> None:
        decisions = read(DECISIONS)
        accelerate = named_block(decisions, "STP_cw_trigger_northern_incident")
        delay = named_block(decisions, "STP_cw_sabotage_nodrul")

        self.assertIn("mission = NOD_cw_intervention_preparation days = -21", accelerate)
        self.assertIn("mission = STP_cw_nod_warning days = -21", accelerate)
        self.assertIn("mission = NOD_cw_intervention_preparation days = 21", delay)
        self.assertIn("mission = STP_cw_nod_warning days = 21", delay)

    def test_party_ai_commits_a_real_reserve_to_fada(self) -> None:
        defend = named_block(read(AI), "STP_cw_defend_fada")
        self.assertIn("states = { 28 }", defend)
        self.assertIn("ratio = 0.20", defend)


if __name__ == "__main__":
    unittest.main()
