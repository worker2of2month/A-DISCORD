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

    def test_stelander_union_recovery_has_no_global_daily_poll(self) -> None:
        source = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        self.assertIsNone(re.search(r"(?m)^\s*on_daily\s*=", source))
        for hook in ("on_daily_STP", "on_daily_STS"):
            block = named_block(source, hook)
            self.assertIn("STP_cw_check_union_wars_finished = yes", block)


if __name__ == "__main__":
    unittest.main()
