from __future__ import annotations

import itertools
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
PLANS = ROOT / "common/ai_strategy_plans/ADISCORD_STP_plans.txt"
AI = ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt"
LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"
INSPECTION_STATES = (2, 3, 29, 45, 46, 53)


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


def focus_list(plan: str) -> tuple[str, ...]:
    block = named_block(plan, "ai_national_focuses")
    return tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", block))


class StelanderInspectionSchedulerRegressionTests(unittest.TestCase):
    def test_second_commission_gate_covers_every_active_pair(self) -> None:
        triggers = read(TRIGGERS)
        pair_guard = named_block(triggers, "STP_cw_two_inspections_active")
        second = named_block(triggers, "STP_cw_second_inspection_unlocked")

        self.assertIn(
            "var = STP_party_suspicion value = 50 compare = greater_than_or_equals",
            second,
        )
        self.assertIn("NOT = { STP_cw_two_inspections_active = yes }", second)

        for left, right in itertools.combinations(INSPECTION_STATES, 2):
            expected = (
                f"AND = {{ {left} = {{ has_state_flag = STP_party_inspection_active }} "
                f"{right} = {{ has_state_flag = STP_party_inspection_active }} }}"
            )
            self.assertIn(expected, pair_guard, (left, right))

    def test_scheduler_reconciles_one_or_two_commissions_and_has_no_random_dead_end(self) -> None:
        effects = read(EFFECTS)
        scheduler = named_block(effects, "STP_schedule_next_party_inspection")
        opener = named_block(effects, "STP_cw_open_one_party_inspection")

        self.assertIn("has_country_flag = STP_cw_inspection_chain_open", scheduler)
        self.assertIn("NOT = { STP_cw_two_inspections_active = yes }", scheduler)
        self.assertEqual(scheduler.count("STP_cw_open_one_party_inspection = yes"), 2)
        self.assertIn("STP_cw_second_inspection_unlocked = yes", scheduler)
        for state in INSPECTION_STATES:
            self.assertIn(f"{state} = {{ has_state_flag = STP_party_inspection_active }}", scheduler)
        self.assertIsNone(
            re.search(r"(?m)^\s*1\s*=\s*\{\s*\}\s*$", opener),
            "a valid inspection chain must never die on a random no-op",
        )

    def test_one_delay_purchase_extends_only_one_active_commission(self) -> None:
        decision = named_block(read(DECISIONS), "STP_cw_delay_inspection")
        complete = named_block(decision, "complete_effect")

        self.assertEqual(
            complete.count("add_days_mission_timeout = { mission = STP_party_inspection_state_"),
            6,
        )
        self.assertGreaterEqual(complete.count("else_if ="), 5)
        for state in INSPECTION_STATES:
            self.assertIn(f"mission = STP_party_inspection_state_{state} days = 14", complete)

    def test_last_banquet_is_a_bounded_fada_operation_with_real_failure_cost(self) -> None:
        decisions = read(DECISIONS)
        launch = named_block(decisions, "STP_cw_launch_last_banquet")
        fallback = named_block(decisions, "STP_cw_launch_last_banquet_fallback")
        mission = named_block(decisions, "STP_cw_last_banquet_window")

        for block in (launch, fallback):
            self.assertIn("set_country_flag = STP_cw_last_banquet_launched", block)
            self.assertIn("activate_mission = STP_cw_last_banquet_window", block)
            self.assertIn("add_timed_idea = { idea = STP_cw_deliberate_offensive days = 21 }", block)
        self.assertIn("controls_state = 3", launch)
        self.assertIn("NOT = { controls_state = 3 }", fallback)
        self.assertIn("has_completed_focus = STP_cw_last_banquet", fallback)

        self.assertIn("days_mission_timeout = 21", mission)
        self.assertIn("available = { controls_state = 28 }", mission)
        success = named_block(mission, "complete_effect")
        self.assertIn("set_country_flag = STP_cw_last_banquet_success", success)
        self.assertIn("set_country_flag = NOD_cw_offer_shown", success)
        self.assertIn("remove_mission = NOD_cw_intervention_preparation", success)
        self.assertIn("set_country_flag = STP_cw_nod_warning_cancelled", success)
        timeout = named_block(mission, "timeout_effect")
        self.assertIn("set_country_flag = STP_cw_last_banquet_failed", timeout)
        self.assertIn("add_war_support = -0.10", timeout)

    def test_border_evidence_can_shift_the_real_nod_countdown_once_in_either_direction(self) -> None:
        decisions = read(DECISIONS)
        delay = named_block(decisions, "STP_cw_trigger_northern_incident")
        accelerate = named_block(decisions, "STP_cw_accelerate_nodrul_preparation")

        for block in (delay, accelerate):
            self.assertIn("has_country_flag = STP_cw_northern_strategy_evidence", block)
            self.assertIn("has_active_mission = STP_cw_nod_warning", block)
            self.assertIn("NOD = { has_active_mission = NOD_cw_intervention_preparation }", block)
            self.assertIn("clr_country_flag = STP_cw_northern_strategy_evidence", block)
        self.assertIn("mission = STP_cw_nod_warning days = 10", delay)
        self.assertIn("mission = NOD_cw_intervention_preparation days = 10", delay)
        self.assertIn("mission = STP_cw_nod_warning days = -10", accelerate)
        self.assertIn("mission = NOD_cw_intervention_preparation days = -10", accelerate)

        loc = read(LOC)
        self.assertIn("STP_cw_delay_election_tt:", loc)
        self.assertIn("Нодрул", next(line for line in loc.splitlines() if line.startswith(" STP_cw_delay_election_tt:")))
        self.assertIn("STP_cw_accelerate_nodrul_preparation:", loc)

    def test_party_ai_hardens_fada_while_last_banquet_is_running(self) -> None:
        strategy = named_block(read(AI), "STP_cw_defend_bronze_congress")
        self.assertIn("STS = { has_active_mission = STP_cw_last_banquet_window }", strategy)
        self.assertIn("states = { 28 }", strategy)
        self.assertIn("ratio = 0.25", strategy)
        self.assertIn("priority = 1800", strategy)

    def test_postwar_bridge_focuses_belong_to_reconstruction_plan(self) -> None:
        plans = read(PLANS)
        war = named_block(plans, "STS_shabrat_civil_war_plan")
        reconstruction = named_block(plans, "STS_shabrat_reconstruction_plan")

        bridge = (
            "STP_cw_first_postwar_budget",
            "STP_cw_restore_civil_authority",
        )
        self.assertNotIn(bridge[0], focus_list(war))
        self.assertNotIn(bridge[1], focus_list(war))
        self.assertEqual(focus_list(reconstruction)[:2], bridge)
        self.assertIn("has_country_flag = STP_cw_postwar", named_block(reconstruction, "enable"))
        self.assertIn("has_country_flag = STP_cw_postwar", named_block(war, "abort"))


if __name__ == "__main__":
    unittest.main()
