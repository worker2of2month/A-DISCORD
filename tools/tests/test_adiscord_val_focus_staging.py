from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"
ON_ACTIONS_PATH = ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"
RU_LOC_PATH = ROOT / "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation/english/ADISCORD_VAL_decisions_l_english.yml"


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
        cls.ru_loc = read(RU_LOC_PATH)
        cls.en_loc = read(EN_LOC_PATH)

    def test_every_focus_gate_explains_what_it_reveals(self) -> None:
        ids = re.findall(r"(?m)^\s*id\s*=\s*(VAL_[A-Za-z0-9_]+)\s*$", self.focuses)
        known = set(ids)
        expected = {}
        for focus_id in ids:
            block = focus_block(self.focuses, focus_id)
            if "allow_branch" not in block:
                continue
            gate = allow(self.focuses, focus_id)
            for dependency in set(re.findall(r"has_completed_focus\s*=\s*(VAL_[A-Za-z0-9_]+)", gate)):
                if dependency in known:
                    expected.setdefault(dependency, set()).add(focus_id)

        self.assertGreaterEqual(len(expected), 50)
        for dependency, targets in expected.items():
            key = f"VAL_focus_progression_{dependency}_tt"
            source = focus_block(self.focuses, dependency)
            self.assertIn(
                f"custom_effect_tooltip = {key}",
                source,
                f"{dependency} hides later focuses but does not explain that progression",
            )
            for localisation in (self.en_loc, self.ru_loc):
                self.assertRegex(localisation, rf"(?m)^\s*{re.escape(key)}:0?\s+\"")
                for target in targets:
                    self.assertIn(f"${target}$", localisation[localisation.index(key):])

    def test_world_event_reveals_are_explained_in_root_descriptions(self) -> None:
        for localisation in (self.en_loc, self.ru_loc):
            stelander = re.search(r'(?m)^\s*VAL_Stelander_Crisis_Opens_desc:\d*\s+"([^"]+)"', localisation)
            resource = re.search(r'(?m)^\s*VAL_Resource_War_Contracts_desc:\d*\s+"([^"]+)"', localisation)
            self.assertIsNotNone(stelander)
            self.assertIsNotNone(resource)
            self.assertIn("§Y", stelander.group(1))
            self.assertIn("§Y", resource.group(1))
            self.assertIn("$VAL_Ministry_Auditors$", resource.group(1))

    def test_first_act_is_a_visible_roadmap_not_a_single_button(self) -> None:
        first_act = (
            "VAL_The_Contract_State",
            "VAL_The_Weaponry_Baron",
            "VAL_Price_Of_Loyalty",
            "VAL_Count_The_Captains",
            "VAL_One_Ledger_One_Banner",
            "VAL_Factories_Like_Cathedrals",
            "VAL_Ballistics_Schools",
            "VAL_Brokered_Steel",
            "VAL_Export_Rifles_Not_Promises",
            "VAL_The_Mercenary_State",
            "VAL_Company_Mandates",
            "VAL_Contract_Arbitration",
            "VAL_Hire_Out_War",
            "VAL_Vorons_Companies",
            "VAL_Stahls_Schedules",
            "VAL_Gromovs_Assault_Tables",
            "VAL_Morns_Supply_Trains",
            "VAL_reclamation_survey",
            "VAL_The_Harvest_Of_Ash",
            "VAL_Field_Surgeons",
            "VAL_Bread_From_Barracks",
            "VAL_Dead_Villages_Still_Count",
            "VAL_reclamation_road_crews",
            "VAL_reclamation_clean_water",
            "VAL_reclamation_workshops",
            "VAL_reclamation_return_home",
            "VAL_reclamation_land_register",
            "VAL_reclamation_industrial_sites",
            "VAL_Market_Roads_North",
            "VAL_Trading_Partners",
            "VAL_October_Of_2160",
            "VAL_Different_Views_On_Freedom",
            "VAL_Operational_Directorate",
            "VAL_Ministry_Of_Contract_Memory",
        )
        for focus_id in first_act:
            self.assertNotIn(
                "allow_branch",
                focus_block(self.focuses, focus_id),
                f"{focus_id} must be visible as part of the opening roadmap",
            )

    def test_second_layer_roots_reveal_in_meaningful_chunks(self) -> None:
        expected = {
            "VAL_Paid_Loyalty": "VAL_Price_Of_Loyalty",
            "VAL_Provincial_Brokers": "VAL_Count_The_Captains",
            "VAL_Contract_Accounting_Office": "VAL_Factories_Like_Cathedrals",
            "VAL_Company_Rosters": "VAL_The_Mercenary_State",
            "VAL_Field_Repair_Corps": "VAL_Morns_Supply_Trains",
            "VAL_Reserve_Battalions": "VAL_Morns_Supply_Trains",
            "VAL_Ministry_Auditors": "VAL_Operational_Directorate",
            "VAL_Wireless_Contract_Bureau": "VAL_Ministry_Of_Contract_Memory",
            "VAL_Occidian_Claims_Commission": "VAL_The_Steel_Contract",
            "VAL_Occidian_Registries": "VAL_Occidian_Claims_Commission",
            "VAL_Audit_Lost_Contracts": "VAL_Inventory_The_Empty_Yards",
            "VAL_econ_development_fund": "VAL_Industrial_Mobilization_Plan",
            "VAL_Bezhaysk_Operation": "VAL_Contracts_Outlive_Kings",
        }
        for focus_id, milestone in expected.items():
            self.assertIn(
                f"has_completed_focus = {milestone}",
                allow(self.focuses, focus_id),
                focus_id,
            )

    def test_contracts_outlive_kings_is_a_visible_capstone(self) -> None:
        body = focus_block(self.focuses, "VAL_Contracts_Outlive_Kings")
        self.assertNotIn("allow_branch", body)
        self.assertNotIn("dynamic = yes", body)
        for dependency in (
            "VAL_State_Contract",
            "VAL_Industrial_Mobilization_Plan",
            "VAL_Army_Of_The_Ledger",
        ):
            self.assertIn(f"prerequisite = {{ focus = {dependency} }}", body)
        self.assertRegex(body, r"ai_will_do\s*=\s*\{[^}]*base\s*=\s*1000")

    def test_foreign_clearing_house_waits_for_the_northern_choice(self) -> None:
        gate = allow(self.focuses, "VAL_Foreign_Broker_Licences")
        self.assertIn("VAL_Trading_Partners", gate)
        self.assertIn("VAL_October_Of_2160", gate)
        self.assertIn("OR =", gate)

    def test_frontier_chapter_reveals_as_one_roadmap(self) -> None:
        root = "VAL_frontier_conference"
        internals = (
            "VAL_frontier_logistics",
            "VAL_frontier_commissioners",
            "VAL_frontier_provincial_offices",
            "VAL_frontier_security_plan",
            "VAL_frontier_treaty_offices",
            "VAL_New_Supply_Base",
            "VAL_Northern_Settlement",
        )
        gate = allow(self.focuses, root)
        self.assertIn("has_completed_focus = VAL_One_Ledger_One_Banner", gate)
        self.assertIn("has_completed_focus = VAL_Trading_Partners", gate)
        self.assertIn("has_completed_focus = VAL_October_Of_2160", gate)

        for focus_id in internals:
            block = focus_block(self.focuses, focus_id)
            self.assertNotIn(
                "allow_branch",
                block,
                f"{focus_id} is inside the revealed chapter and must not disappear behind branch-cache state",
            )
            self.assertIn("prerequisite", block, focus_id)

    def test_world_reactive_branches_still_use_world_state(self) -> None:
        stelander = allow(self.focuses, "VAL_Stelander_Crisis_Opens")
        self.assertIn("has_global_flag = STP_cw_started", stelander)
        self.assertNotIn("has_completed_focus =", stelander)

        resource = allow(self.focuses, "VAL_Resource_War_Contracts")
        self.assertIn("ADISCORD_nam_resource_war_active = yes", resource)
        self.assertNotIn("has_completed_focus =", resource)
        root = focus_block(self.focuses, "VAL_Resource_War_Contracts")
        self.assertIn("prerequisite = { focus = VAL_Ministry_Auditors }", root)

        vorkerland = allow(self.focuses, "VAL_Vorkerland_Contracts_Burn")
        self.assertIn("ADISCORD_vorkerland_collapse_wars_started", vorkerland)
        self.assertIn("has_completed_focus = VAL_Operational_Directorate", vorkerland)

    def test_late_campaign_roots_remain_hidden(self) -> None:
        expected = {
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

    def test_every_staged_allow_branch_focus_is_dynamic(self) -> None:
        ids = re.findall(r"(?m)^\s*id\s*=\s*(VAL_[A-Za-z0-9_]+)\s*$", self.focuses)
        staged = []
        for focus_id in ids:
            block = focus_block(self.focuses, focus_id)
            if "allow_branch" not in block:
                continue
            staged.append(focus_id)
            self.assertIn(
                "dynamic = yes",
                block,
                f"{focus_id} can hide dynamically, so it must also be able to reappear dynamically",
            )
        self.assertIn("VAL_frontier_conference", staged)
        for focus_id in (
            "VAL_frontier_logistics",
            "VAL_frontier_commissioners",
            "VAL_frontier_provincial_offices",
            "VAL_frontier_security_plan",
            "VAL_frontier_treaty_offices",
            "VAL_New_Supply_Base",
            "VAL_Northern_Settlement",
        ):
            self.assertNotIn(focus_id, staged)
        self.assertGreaterEqual(len(staged), 50)

    def test_frontier_chapter_has_no_old_save_migration(self) -> None:
        self.assertNotIn("ADISCORD_val_frontier_postpeace_fix_v1", self.on_actions)
        self.assertNotIn("VAL_frontier_focus_tree_schema_v3", self.on_actions)
        self.assertNotIn("load_focus_tree = { tree = VAL_focus keep_completed = yes }", self.on_actions)

    def test_focus_completion_refreshes_dynamic_layout(self) -> None:
        hook = named_block(self.on_actions, "on_focus_completed")
        self.assertIn("tag = VAL", hook)
        self.assertIn("has_focus_tree = VAL_focus", hook)
        self.assertIn("mark_focus_tree_layout_dirty = yes", hook)

        startup = named_block(self.on_actions, "on_startup")
        self.assertIn("mark_focus_tree_layout_dirty = yes", startup)

    def test_contract_state_has_the_correct_russian_title(self) -> None:
        self.assertIn('VAL_The_Contract_State: "Государство контрактов"', self.ru_loc)
        self.assertNotIn('VAL_The_Contract_State: "Проклятая земля"', self.ru_loc)

    def test_no_parallel_focus_phase_state_machine_was_added(self) -> None:
        self.assertNotIn("VAL_focus_reveal_phase", self.focuses)
        self.assertNotIn("VAL_focus_tree_phase", self.focuses)


if __name__ == "__main__":
    unittest.main()
