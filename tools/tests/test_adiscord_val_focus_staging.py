from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"
ON_ACTIONS_PATH = ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def brace_block(source: str, start: int) -> str:
    opening = source.find("{", start)
    if opening < 0:
        raise AssertionError("missing opening brace")
    depth = 0
    quoted = False
    escaped = False
    comment = False
    for index in range(opening, len(source)):
        char = source[index]
        if comment:
            if char == "\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == "#":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("unterminated block")


def focus_block(source: str, focus_id: str) -> str:
    marker = f"id = {focus_id}"
    pos = source.find(marker)
    if pos < 0:
        raise AssertionError(f"missing focus: {focus_id}")
    start = source.rfind("focus = {", 0, pos)
    if start < 0:
        raise AssertionError(f"missing focus block: {focus_id}")
    return brace_block(source, start)


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    return brace_block(source, match.start())


def allow(source: str, focus_id: str) -> str:
    return named_block(focus_block(source, focus_id), "allow_branch")


class KefreytFocusStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS_PATH)
        cls.on_actions = read(ON_ACTIONS_PATH)

    def test_opening_screen_is_small_then_reveals_five_pillars(self) -> None:
        self.assertNotIn("allow_branch", focus_block(self.focuses, "VAL_The_Contract_State"))
        for focus_id in (
            "VAL_The_Weaponry_Baron",
            "VAL_Factories_Like_Cathedrals",
            "VAL_The_Mercenary_State",
            "VAL_Operational_Directorate",
            "VAL_Ministry_Of_Contract_Memory",
        ):
            self.assertIn(
                "has_completed_focus = VAL_The_Contract_State",
                allow(self.focuses, focus_id),
                focus_id,
            )

    def test_pillars_expand_only_after_their_existing_milestones(self) -> None:
        expected = {
            "VAL_Price_Of_Loyalty": "VAL_The_Weaponry_Baron",
            "VAL_Ballistics_Schools": "VAL_Factories_Like_Cathedrals",
            "VAL_Contract_Accounting_Office": "VAL_Factories_Like_Cathedrals",
            "VAL_Hire_Out_War": "VAL_The_Mercenary_State",
            "VAL_Company_Rosters": "VAL_The_Mercenary_State",
            "VAL_Ministry_Auditors": "VAL_Operational_Directorate",
            "VAL_Wireless_Contract_Bureau": "VAL_Ministry_Of_Contract_Memory",
            "VAL_Market_Roads_North": "VAL_One_Ledger_One_Banner",
            "VAL_econ_development_fund": "VAL_Industrial_Mobilization_Plan",
            "VAL_Bezhaysk_Operation": "VAL_Contracts_Outlive_Kings",
        }
        for focus_id, prerequisite in expected.items():
            self.assertIn(
                f"has_completed_focus = {prerequisite}",
                allow(self.focuses, focus_id),
                focus_id,
            )

    def test_join_nodes_preserve_original_or_semantics(self) -> None:
        export = allow(self.focuses, "VAL_Export_Rifles_Not_Promises")
        self.assertRegex(
            export,
            r"OR\s*=\s*\{[^}]*VAL_Ballistics_Schools[^}]*VAL_Brokered_Steel",
        )

        reopen = allow(self.focuses, "VAL_Reopen_Trade_Routes")
        self.assertRegex(
            reopen,
            r"OR\s*=\s*\{[^}]*VAL_Campaign_Secured[^}]*VAL_Returning_Buyers",
        )
        self.assertRegex(
            reopen,
            r"OR\s*=\s*\{[^}]*VAL_New_Supply_Base[^}]*VAL_Contingency_Ledgers",
        )

        debts = allow(self.focuses, "VAL_Settle_Industrial_Debts")
        self.assertRegex(
            debts,
            r"OR\s*=\s*\{[^}]*VAL_Campaign_Secured[^}]*VAL_Returning_Buyers",
        )
        self.assertIn("VAL_Industrial_Mobilization_Plan", debts)

    def test_world_reactive_branches_still_use_world_state(self) -> None:
        stelander = allow(self.focuses, "VAL_Stelander_Crisis_Opens")
        self.assertIn("has_global_flag = STP_cw_started", stelander)
        self.assertNotIn("has_completed_focus =", stelander)

        resource = allow(self.focuses, "VAL_Resource_War_Contracts")
        self.assertIn("ADISCORD_nam_resource_war_active = yes", resource)
        self.assertIn("has_completed_focus = VAL_Ministry_Auditors", resource)

        vorkerland = allow(self.focuses, "VAL_Vorkerland_Contracts_Burn")
        self.assertIn("ADISCORD_vorkerland_collapse_wars_started", vorkerland)
        self.assertIn("has_completed_focus = VAL_Operational_Directorate", vorkerland)

    def test_regional_and_postwar_content_is_not_on_the_opening_screen(self) -> None:
        expected = {
            "VAL_Occidian_Registries": "VAL_The_Steel_Contract",
            "VAL_frontier_conference": "VAL_One_Ledger_One_Banner",
            "VAL_Return_Southern_Tsaygen": "VAL_Contracts_Outlive_Kings",
            "VAL_Wasteland_Charter": "VAL_frontier_return_irem",
            "VAL_Campaign_Secured": "VAL_Northern_Settlement",
            "VAL_Veterans_Of_The_Campaign": "VAL_Campaign_Secured",
            "VAL_Return_To_World_Market": "VAL_Reopen_Trade_Routes",
        }
        for focus_id, milestone in expected.items():
            self.assertIn(
                f"has_completed_focus = {milestone}",
                allow(self.focuses, focus_id),
                focus_id,
            )

    def test_focus_completion_refreshes_dynamic_layout(self) -> None:
        hook = named_block(self.on_actions, "on_focus_completed")
        self.assertIn("tag = VAL", hook)
        self.assertIn("has_focus_tree = VAL_focus", hook)
        self.assertIn("mark_focus_tree_layout_dirty = yes", hook)

        startup = named_block(self.on_actions, "on_startup")
        self.assertIn("mark_focus_tree_layout_dirty = yes", startup)

    def test_no_parallel_focus_phase_state_machine_was_added(self) -> None:
        self.assertNotIn("VAL_focus_reveal_phase", self.focuses)
        self.assertNotIn("VAL_focus_tree_phase", self.focuses)


if __name__ == "__main__":
    unittest.main()
