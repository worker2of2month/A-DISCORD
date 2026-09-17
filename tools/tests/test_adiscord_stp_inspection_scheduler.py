from __future__ import annotations

import itertools
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
PLANS = ROOT / "common/ai_strategy_plans/ADISCORD_STP_plans.txt"
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
