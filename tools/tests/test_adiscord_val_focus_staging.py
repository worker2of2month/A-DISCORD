from __future__ import annotations

import re
import unittest
from pathlib import Path


from tools.lib.focus_sources import read_focus_source
from tools.tests.test_adiscord_val_focus_layout import PERSONAL_FOCUSES

ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"
ON_ACTIONS_PATH = ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"
RU_LOC_PATH = ROOT / "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation/english/ADISCORD_VAL_decisions_l_english.yml"

CHAPTER_ROOTS = {
    "VAL_Contracts_Outlive_Kings",
    "VAL_frontier_conference",
    "VAL_Return_Southern_Tsaygen",
    "VAL_bjk_op_staff",
    "VAL_Bezhaysk_Operation",
    "VAL_Marine_Contract_Corps",
    "VAL_Shield_Special_Forces",
    "VAL_econ_development_fund",
    "VAL_Naval_Contract_Office",
    "VAL_Occidian_Claims_Commission",
    "VAL_Reopen_Trade_Routes",
    "VAL_Settle_Industrial_Debts",
    "VAL_Veterans_Of_The_Campaign",
    "VAL_Peace_Without_Orders",
}
REVEAL_MILESTONES = {
    "VAL_Inventory_The_Empty_Yards",
    "VAL_Resource_War_Contracts",
    "VAL_Brokered_Steel",
    "VAL_State_Contract",
    "VAL_council_charter",
    "VAL_council_permanent_government",
    "VAL_council_limited_mandate",
    "VAL_Industrial_Mobilization_Plan",
    "VAL_Army_Of_The_Ledger",
    "VAL_Contracts_Outlive_Kings",
    "VAL_The_Steel_Contract",
    "VAL_Campaign_Secured",
    "VAL_Returning_Buyers",
}


def read(path: Path) -> str:
    return read_focus_source(path)


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
                return source[start : index + 1]
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


def focus_ids(source: str) -> list[str]:
    from tools.tests.test_adiscord_stp_preparation import scalar, walk
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz

    return [
        scalar(entry.value, "id")
        for entry in walk(parse_clausewitz(source))
        if entry.key == "focus" and isinstance(entry.value, list)
    ]


class KefreytFocusStagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS_PATH)
        cls.on_actions = read(ON_ACTIONS_PATH)
        cls.ru_loc = read(RU_LOC_PATH)
        cls.en_loc = read(EN_LOC_PATH)

    def test_every_focus_gate_explains_what_it_reveals(self) -> None:
        ids = focus_ids(self.focuses)
        known = set(ids)
        expected = {}
        for focus_id in ids:
            block = focus_block(self.focuses, focus_id)
            if not re.search(r"(?m)^\s*allow_branch\s*=", block):
                continue
            gate = allow(self.focuses, focus_id)
            for dependency in set(
                re.findall(r"has_completed_focus\s*=\s*(VAL_[A-Za-z0-9_]+)", gate)
            ):
                if dependency in known:
                    expected.setdefault(dependency, set()).add(focus_id)

        self.assertEqual(
            set(expected),
            REVEAL_MILESTONES,
        )
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
                    text = re.search(
                        rf'(?m)^\s*{re.escape(key)}:\d*\s+"([^\"]+)"', localisation
                    ).group(1)
                    self.assertIn(f"${target}$", text)

    def test_world_event_root_descriptions_omit_reveal_instructions(self) -> None:
        for localisation in (self.en_loc, self.ru_loc):
            stelander = re.search(
                r'(?m)^\s*VAL_Stelander_Crisis_Opens_desc:\d*\s+"([^"]+)"', localisation
            )
            resource = re.search(
                r'(?m)^\s*VAL_Resource_War_Contracts_desc:\d*\s+"([^"]+)"', localisation
            )
            self.assertIsNotNone(stelander)
            self.assertIsNotNone(resource)
            self.assertNotIn("§Y", stelander.group(1))
            self.assertNotIn("§Y", resource.group(1))
            self.assertNotIn("$VAL_Operational_Directorate$", resource.group(1))

    def test_progression_tooltips_match_current_dependencies(self) -> None:
        from tools.tests.test_adiscord_stp_preparation import scalar, walk
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        next_focuses = {}
        for tree in parse_clausewitz(self.focuses):
            for focus in tree.value:
                if focus.key != "focus" or not isinstance(focus.value, list):
                    continue
                target = scalar(focus.value, "id")
                for gate in focus.value:
                    if gate.key not in ("prerequisite", "allow_branch", "available"):
                        continue
                    for condition in walk(gate.value):
                        if condition.key in ("focus", "has_completed_focus"):
                            next_focuses.setdefault(condition.value, set()).add(target)

        for source in (self.ru_loc, self.en_loc):
            rows = re.findall(
                r'(?m)^\s*VAL_focus_progression_(VAL_\w+)_tt:\d*\s+"([^\"]+)"',
                source,
            )
            self.assertGreaterEqual(len(rows), 50)
            for parent, text in rows:
                self.assertEqual(
                    set(re.findall(r"\$(VAL_\w+)\$", text)),
                    next_focuses[parent],
                    parent,
                )
                self.assertNotIn("После завершения откроются", text, parent)
                self.assertNotIn("Will reveal on completion", text, parent)

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
            if focus_id in PERSONAL_FOCUSES:
                self.assertRegex(allow(self.focuses, focus_id), r"VAL_council_governs\s*=\s*no")
                continue
            if focus_id == "VAL_One_Ledger_One_Banner":
                self.assertRegex(allow(self.focuses, focus_id), r"always\s*=\s*yes")
                continue
            self.assertNotIn(
                "allow_branch",
                focus_block(self.focuses, focus_id),
                f"{focus_id} must be visible as part of the opening roadmap",
            )

    def test_core_milestones_are_static_but_keep_their_gates(self) -> None:
        expected = {
            "VAL_Paid_Loyalty": "VAL_Price_Of_Loyalty",
            "VAL_Provincial_Brokers": "VAL_Count_The_Captains",
            "VAL_Contract_Accounting_Office": "VAL_Factories_Like_Cathedrals",
            "VAL_Company_Rosters": "VAL_The_Mercenary_State",
            "VAL_Field_Repair_Corps": "VAL_Morns_Supply_Trains",
            "VAL_Reserve_Battalions": "VAL_Morns_Supply_Trains",
            "VAL_Ministry_Auditors": "VAL_Operational_Directorate",
            "VAL_Wireless_Contract_Bureau": "VAL_Ministry_Of_Contract_Memory",
            "VAL_Occidian_Registries": "VAL_Occidian_Claims_Commission",
        }
        for focus_id, milestone in expected.items():
            body = focus_block(self.focuses, focus_id)
            if focus_id in PERSONAL_FOCUSES:
                self.assertRegex(allow(self.focuses, focus_id), r"VAL_council_governs\s*=\s*no")
            else:
                self.assertNotIn("dynamic = yes", body, focus_id)
                self.assertNotIn("allow_branch", body, focus_id)
            self.assertIn(f"has_completed_focus = {milestone}", body, focus_id)

    def test_contracts_outlive_kings_reveals_after_first_core_programme(self) -> None:
        body = focus_block(self.focuses, "VAL_Contracts_Outlive_Kings")
        gate = allow(self.focuses, "VAL_Contracts_Outlive_Kings")
        self.assertIn("dynamic = yes", body)
        self.assertNotIn("always = yes", gate)
        self.assertEqual(
            set(re.findall(r"has_completed_focus\s*=\s*(VAL_\w+)", named_block(gate, "OR"))),
            {
                "VAL_State_Contract", "VAL_council_charter",
                "VAL_council_permanent_government", "VAL_council_limited_mandate",
                "VAL_Industrial_Mobilization_Plan", "VAL_Army_Of_The_Ledger",
            },
        )
        for dependency in (
            "VAL_Industrial_Mobilization_Plan",
            "VAL_Army_Of_The_Ledger",
        ):
            self.assertIn(f"prerequisite = {{ focus = {dependency} }}", body)
        self.assertIn("focus = VAL_State_Contract", body)
        self.assertIn("focus = VAL_council_charter", body)
        self.assertRegex(body, r"ai_will_do\s*=\s*\{[^}]*base\s*=\s*1000")

    def test_foreign_clearing_house_waits_for_the_northern_choice(self) -> None:
        body = focus_block(self.focuses, "VAL_Foreign_Broker_Licences")
        self.assertNotIn("dynamic = yes", body)
        self.assertNotIn("allow_branch", body)
        self.assertIn(
            "prerequisite = { focus = VAL_Trading_Partners focus = VAL_October_Of_2160 }",
            body,
        )
        self.assertIn("OR = { has_completed_focus = VAL_Trading_Partners", body)

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
        gate = focus_block(self.focuses, root)
        self.assertIn("dynamic = yes", gate)
        self.assertIn("has_completed_focus = VAL_Contracts_Outlive_Kings", allow(self.focuses, root))
        # Prerequisites already show these requirements; available keeps only the postwar gate.
        self.assertIn("prerequisite = { focus = VAL_One_Ledger_One_Banner }", gate)
        self.assertIn("prerequisite = { focus = VAL_Trading_Partners focus = VAL_October_Of_2160 }", gate)
        self.assertNotIn("has_completed_focus = VAL_One_Ledger_One_Banner", gate)

        for focus_id in internals:
            block = focus_block(self.focuses, focus_id)
            self.assertNotIn(
                "allow_branch",
                block,
                f"{focus_id} is inside the revealed chapter and must not disappear behind branch-cache state",
            )
            self.assertIn("prerequisite", block, focus_id)

    def test_frontier_requirements_stay_out_of_story_description(self) -> None:
        body = focus_block(self.focuses, "VAL_frontier_conference")
        groups = re.findall(r"prerequisite\s*=\s*\{([^}]+)\}", body)
        self.assertEqual(groups[0].strip(), "focus = VAL_Contracts_Outlive_Kings")
        dependencies = set(re.findall(r"\bfocus\s*=\s*(\w+)", " ".join(groups)))
        for source in (self.ru_loc, self.en_loc):
            description = re.search(
                r'(?m)^\s*VAL_frontier_conference_desc:\d*\s+"([^\"]+)"', source
            ).group(1)
            for dependency in dependencies:
                self.assertNotIn(f"${dependency}$", description)
            progression = re.search(
                r'(?m)^\s*VAL_focus_progression_VAL_Contracts_Outlive_Kings_tt:\d*\s+"([^\"]+)"', source
            ).group(1)
            self.assertIn("$VAL_frontier_conference$", progression)
        self.assertIn(
            "VAL_focus_progression_VAL_Contracts_Outlive_Kings_tt",
            focus_block(self.focuses, "VAL_Contracts_Outlive_Kings"),
        )

    def test_unmasked_focus_condition_flags_have_localised_names(self) -> None:
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        def visible_flags(nodes):
            for node in nodes:
                if node.key in ("custom_trigger_tooltip", "hidden_trigger"):
                    continue
                if node.key == "has_country_flag" and isinstance(node.value, str):
                    yield node.value
                elif isinstance(node.value, list):
                    yield from visible_flags(node.value)

        flags = set()
        for path in (ROOT / "focus_trees/VAL").rglob("focuses.txt"):
            for tree in parse_clausewitz(read(path)):
                for node in tree.value:
                    if node.key != "focus" or not isinstance(node.value, list):
                        continue
                    for condition in node.value:
                        if condition.key in ("available", "bypass"):
                            flags.update(visible_flags(condition.value))
        for flag in flags:
            for source in (self.ru_loc, self.en_loc):
                self.assertIsNotNone(
                    re.search(rf'(?m)^\s*{re.escape(flag)}:\d*\s+"[^\"]+"', source),
                    flag,
                )

    def test_world_reactive_branches_still_use_world_state(self) -> None:
        stelander = allow(self.focuses, "VAL_Stelander_Crisis_Opens")
        self.assertIn("has_global_flag = STP_cw_started", stelander)
        self.assertNotIn("has_completed_focus =", stelander)

        resource = allow(self.focuses, "VAL_Resource_War_Contracts")
        self.assertIn("ADISCORD_nam_resource_war_active = yes", resource)
        self.assertNotIn("has_completed_focus =", resource)
        root = focus_block(self.focuses, "VAL_Resource_War_Contracts")
        self.assertIn("prerequisite = { focus = VAL_Operational_Directorate }", root)
        self.assertNotIn("prerequisite = { focus = VAL_Ministry_Auditors }", root)

        vorkerland = allow(self.focuses, "VAL_Vorkerland_Contracts_Burn")
        self.assertIn("ADISCORD_vorkerland_collapse_wars_started", vorkerland)
        self.assertNotIn("has_completed_focus =", vorkerland)
        root = focus_block(self.focuses, "VAL_Vorkerland_Contracts_Burn")
        self.assertRegex(
            root,
            r"prerequisite = \{\s*focus = VAL_Ballistics_Schools\s*focus = VAL_Brokered_Steel\s*\}",
        )
        self.assertNotIn("focus = VAL_Operational_Directorate", root)

    def test_late_chapters_keep_selection_gates_and_reveal_their_internal_roadmap(self) -> None:
        expected = {
            "VAL_Integrate_Occidia": "VAL_Occidian_Registries",
            "VAL_Balchansk_Charter": "VAL_Occidian_Registries",
            "VAL_Bezhaysk_Operation": "VAL_Contracts_Outlive_Kings",
            "VAL_Return_Southern_Tsaygen": "VAL_Contracts_Outlive_Kings",
            "VAL_frontier_return_irem": "VAL_Return_Southern_Tsaygen",
            "VAL_frontier_lease_irem": "VAL_Return_Southern_Tsaygen",
            "VAL_Stelander_Ultimatum": "VAL_frontier_treaty_offices",
            "VAL_Equal_Powers_Pact": "VAL_Stelander_Ultimatum",
            "VAL_Campaign_Secured": "VAL_Northern_Settlement",
            "VAL_Joint_General_Staff": "VAL_Equal_Powers_Pact",
            "VAL_Cross_Border_Contracts": "VAL_Equal_Powers_Pact",
            "VAL_Wasteland_Charter": "VAL_frontier_return_irem",
            "VAL_Two_States_One_Frontier": "VAL_Joint_General_Staff",
            "VAL_Reopen_Trade_Routes": "VAL_Campaign_Secured",
            "VAL_Settle_Industrial_Debts": "VAL_Industrial_Mobilization_Plan",
            "VAL_Veterans_Of_The_Campaign": "VAL_Campaign_Secured",
            "VAL_Southern_Expansion": "VAL_Wasteland_Charter",
            "VAL_Eastern_Expansion": "VAL_Wasteland_Charter",
        }
        for focus_id, milestone in expected.items():
            body = focus_block(self.focuses, focus_id)
            if focus_id in CHAPTER_ROOTS:
                self.assertIn("allow_branch", body, focus_id)
                self.assertIn("dynamic = yes", body, focus_id)
            else:
                self.assertNotIn("allow_branch", body, focus_id)
                self.assertNotIn("dynamic = yes", body, focus_id)
            self.assertIn(f"focus = {milestone}", body, focus_id)

        southern = focus_block(self.focuses, "VAL_Return_Southern_Tsaygen")
        self.assertIn(
            "prerequisite = { focus = VAL_Contracts_Outlive_Kings }", southern
        )
        self.assertIn(
            "prerequisite = { focus = VAL_Foreign_Broker_Licences }", southern
        )

    def test_branch_courses_are_exclusive_pairs_that_rejoin(self) -> None:
        pairs = {
            ("VAL_Army_Arsenal_Orders", "VAL_Strategic_Arms_Exports"): None,
            ("VAL_Serial_Armor_Production", "VAL_Tank_Crew_School"): "VAL_Armored_Contract_Companies",
            ("VAL_Assault_From_The_Sea", "VAL_Beachhead_Logistics"): "VAL_Contract_Landing_Craft",
            ("VAL_Expedition_Cruisers", "VAL_Expedition_Landing_Staff"): None,
            ("VAL_econ_export_finance", "VAL_econ_war_economy"): "VAL_econ_integrated_economy",
            ("VAL_frontier_return_irem", "VAL_frontier_lease_irem"): "VAL_Wasteland_Charter",
        }
        for (left, right), merge in pairs.items():
            self.assertIn(
                f"mutually_exclusive = {{ focus = {right} }}", focus_block(self.focuses, left)
            )
            self.assertIn(
                f"mutually_exclusive = {{ focus = {left} }}", focus_block(self.focuses, right)
            )
            if merge:
                self.assertRegex(
                    focus_block(self.focuses, merge),
                    rf"prerequisite = \{{\s*focus = {left}\s*focus = {right}\s*\}}",
                )

        arms = focus_block(self.focuses, "VAL_Strategic_Arms_Exports")
        self.assertIn("prerequisite = { focus = VAL_Bulk_Arms_Contracts }", arms)
        self.assertNotIn("prerequisite = { focus = VAL_Army_Arsenal_Orders }", arms)

    def test_only_world_roots_chapter_roots_and_government_branches_are_dynamic(self) -> None:
        ids = focus_ids(self.focuses)
        staged = []
        for focus_id in ids:
            block = focus_block(self.focuses, focus_id)
            if not re.search(r"(?m)^\s*allow_branch\s*=", block):
                continue
            if re.fullmatch(r"\s*allow_branch\s*=\s*\{\s*always\s*=\s*yes\s*\}", allow(self.focuses, focus_id)):
                self.assertNotIn("dynamic = yes", block)
                continue
            staged.append(focus_id)
            self.assertIn(
                "dynamic = yes",
                block,
                f"{focus_id} can hide dynamically, so it must also be able to reappear dynamically",
            )
        self.assertEqual(
            set(staged),
            {
                "VAL_Stelander_Crisis_Opens",
                "VAL_Vorkerland_Contracts_Burn",
                "VAL_Audit_Lost_Contracts",
                "VAL_Resource_War_Contracts",
                "VAL_Support_The_Viceroy",
                "VAL_Westerholm_Concessions",
            } | CHAPTER_ROOTS | PERSONAL_FOCUSES | {focus_id for focus_id in ids if focus_id.startswith("VAL_council_")},
        )

    def test_frontier_chapter_has_no_old_save_migration(self) -> None:
        self.assertNotIn("ADISCORD_val_frontier_postpeace_fix_v1", self.on_actions)
        self.assertNotIn("VAL_frontier_focus_tree_schema_v3", self.on_actions)
        self.assertNotIn(
            "load_focus_tree = { tree = VAL_focus keep_completed = yes }",
            self.on_actions,
        )

    def test_focus_completion_refreshes_dynamic_layout(self) -> None:
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )

        focuses = {
            scalar(entry.value, "id"): entry.value
            for entry in walk(parse_clausewitz(self.focuses))
            if entry.key == "focus" and isinstance(entry.value, list)
        }
        parents = {
            entry.value
            for focus in focuses.values()
            for gate in focus
            if gate.key == "allow_branch"
            for entry in walk(gate.value)
            if entry.key == "has_completed_focus" and entry.value in focuses
        }
        self.assertEqual(
            parents,
            REVEAL_MILESTONES,
        )
        callers = set()
        for focus_id, focus in focuses.items():
            reward = block(focus, "completion_reward")
            calls = [
                entry.value
                for entry in walk(reward)
                if entry.key == "country_event"
                and scalar(entry.value, "id") == "val_rework.123"
            ]
            if not calls:
                continue
            callers.add(focus_id)
            self.assertEqual(len(calls), 1, focus_id)
            self.assertEqual(scalar(calls[0], "hours"), "1", focus_id)
            hidden_calls = [
                entry.value
                for hidden in reward
                if hidden.key == "hidden_effect"
                for entry in walk(hidden.value)
                if entry.key == "country_event"
                and scalar(entry.value, "id") == "val_rework.123"
            ]
            self.assertEqual(hidden_calls, calls, focus_id)
        self.assertTrue(parents <= callers)
        self.assertNotIn("on_focus_completed", self.on_actions)
        self.assertNotIn("on_focus_complete =", self.on_actions)

        events = parse_clausewitz(
            read(ROOT / "events/ADISCORD_VAL_contract_events.txt")
        )
        refresh = [
            entry.value
            for entry in events
            if entry.key == "country_event"
            and scalar(entry.value, "id") == "val_rework.123"
        ]
        self.assertEqual(len(refresh), 1)
        self.assertEqual(scalar(refresh[0], "hidden"), "yes")
        self.assertEqual(scalar(refresh[0], "is_triggered_only"), "yes")
        self.assertEqual(scalar(block(refresh[0], "trigger"), "tag"), "VAL")
        self.assertEqual(
            scalar(block(refresh[0], "trigger"), "has_focus_tree"), "VAL_focus"
        )
        self.assertEqual(
            [(entry.key, entry.value) for entry in block(refresh[0], "immediate")],
            [("mark_focus_tree_layout_dirty", "yes")],
        )

        startup = named_block(self.on_actions, "on_startup")
        self.assertIn("mark_focus_tree_layout_dirty = yes", startup)

    def test_contract_state_has_the_correct_russian_title(self) -> None:
        self.assertIn('VAL_The_Contract_State: "Государство контрактов"', self.ru_loc)
        self.assertNotIn('VAL_The_Contract_State: "Проклятая земля"', self.ru_loc)

    def test_no_parallel_focus_phase_state_machine_was_added(self) -> None:
        self.assertNotIn("VAL_focus_reveal_phase", self.focuses)
        self.assertNotIn("VAL_focus_tree_phase", self.focuses)


class KefreytAIExpansionPriorityTests(unittest.TestCase):
    """Evaluate authored priorities; this does not simulate native AI scheduling."""

    def weight(self, items, key, facts):
        from tools.tests.test_adiscord_stp_preparation import (
            block, matches_conditions, scalar,
        )

        weights = block(items, key)
        result = float(scalar(weights, "base") or 1)
        for modifier in weights:
            if modifier.key != "modifier":
                continue
            conditions = [
                item for item in modifier.value if item.key not in {"factor", "add"}
            ]
            if matches_conditions(conditions, facts, "VAL"):
                adjustment = {item.key: item.value for item in modifier.value}
                result *= float(adjustment.get("factor", 1))
                result += float(adjustment.get("add", 0))
        return result

    def test_priority_plan_reaches_expansion_with_all_prerequisites(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar

        path = ROOT / "common/ai_strategy_plans/ADISCORD_VAL_plans.txt"
        self.assertTrue(path.exists(), "VAL needs an explicit expansion focus plan")
        plan = block(entries(path.relative_to(ROOT).as_posix()), "VAL_expansion_priority_plan")
        order = [entry.value for entry in block(plan, "ai_national_focuses")]
        focuses = {
            scalar(entry.value, "id"): entry.value
            for entry in block(entries("focus_trees/VAL/main/focuses.txt"), "focus_tree")
            if entry.key == "focus"
        }
        done = set()
        for focus_id in order:
            self.assertIn(focus_id, focuses)
            self.assertNotIn(focus_id, done)
            for prerequisite in (e for e in focuses[focus_id] if e.key == "prerequisite"):
                self.assertTrue(done.intersection(e.value for e in prerequisite.value), focus_id)
            exclusions = {
                e.value
                for gate in focuses[focus_id] if gate.key == "mutually_exclusive"
                for e in gate.value
            }
            self.assertFalse(done.intersection(exclusions), focus_id)
            done.add(focus_id)
        for focus_id in (
            "VAL_Integrate_Occidia", "VAL_Contracts_Outlive_Kings",
            "VAL_Foreign_Broker_Licences", "VAL_Return_Southern_Tsaygen",
            "VAL_frontier_security_plan",
        ):
            self.assertIn(focus_id, done)
        self.assertLess(order.index("VAL_Integrate_Occidia"), order.index("VAL_The_Weaponry_Baron"))
        self.assertLess(
            order.index("VAL_Return_Southern_Tsaygen"),
            order.index("VAL_frontier_conference"),
        )
        self.assertNotIn("VAL_Balchansk_Charter", done)
        self.assertNotIn("VAL_Returning_Buyers", done)

    def test_trade_route_does_not_permanently_defer_an_available_northern_target(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries

        category = block(entries("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_military_operations")
        decision = block(category, "VAL_defer_northern_expansion")
        self.assertTrue(decision)
        for trade in (False, True):
            for target in ("CIN", "OSF", "APH"):
                facts = {
                    ("VAL", "has_completed_focus", "VAL_Trading_Partners"): trade,
                    (target, "VAL_frontier_bloc_target_eligible", "yes"): True,
                }
                with self.subTest(trade=trade, target=target):
                    self.assertEqual(self.weight(decision, "ai_will_do", facts), 0)
        self.assertGreater(self.weight(decision, "ai_will_do", {}), 0)

    def test_northern_refusal_means_war_or_preparation_never_permanent_withdrawal(self):
        from tools.tests.test_adiscord_stp_preparation import entries, scalar

        event = next(
            e.value for e in entries("events/ADISCORD_VAL_contract_events.txt")
            if isinstance(e.value, list) and scalar(e.value, "id") == "val_rework.111"
        )
        options = {scalar(e.value, "name"): e.value for e in event if e.key == "option"}
        for target in (1, 2, 3):
            for ready in (False, True):
                facts = {
                    ("VAL", "variable", "VAL_frontier_target"): target,
                    ("VAL", "VAL_frontier_prewar_eligible", "yes"): True,
                    ("VAL", "VAL_ai_frontier_force_ready", "yes"): ready,
                    ("VAL", "VAL_ai_frontier_force_ready", "no"): not ready,
                    ("VAL", "numeric", "has_manpower"): 30000,
                }
                with self.subTest(target=target, ready=ready):
                    self.assertEqual(self.weight(options["val_rework.111.withdraw"], "ai_chance", facts), 0)
                    chosen = "war" if ready else "prepare"
                    self.assertGreater(self.weight(options[f"val_rework.111.{chosen}"], "ai_chance", facts), 0)
                    if not ready:
                        self.assertEqual(self.weight(options["val_rework.111.war"], "ai_chance", facts), 0)
                    else:
                        self.assertEqual(self.weight(options["val_rework.111.prepare"], "ai_chance", facts), 0)
        ert = {("VAL", "variable", "VAL_frontier_target"): 4}
        self.assertEqual(self.weight(options["val_rework.111.withdraw"], "ai_chance", ert), 30)

    def test_ai_does_not_choose_the_permanent_occidian_client(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar

        focuses = block(entries("focus_trees/VAL/main/focuses.txt"), "focus_tree")
        charter = next(
            e.value for e in focuses
            if e.key == "focus" and scalar(e.value, "id") == "VAL_Balchansk_Charter"
        )
        self.assertEqual(self.weight(charter, "ai_will_do", {}), 0)


class KefreytNorthernOperationTests(unittest.TestCase):
    AXES = (
        "VAL_nod_op_axis_breakthrough",
        "VAL_nod_op_axis_landing",
        "VAL_nod_op_axis_forest",
    )
    PREPARATION = {
        "VAL_nod_op_staff_games": 10,
        "VAL_nod_op_border_roads": 10,
        "VAL_nod_op_armour_reserve": 15,
        "VAL_nod_op_landing_drills": 15,
        "VAL_nod_op_forest_guides": 15,
        "VAL_nod_op_deception": 5,
        "VAL_final_reconnaissance": 15,
        "VAL_final_stockpile_supplies": 15,
        "VAL_final_register_reserves": 10,
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS_PATH)
        cls.decisions = read(ROOT / "common/decisions/ADISCORD_VAL_decisions.txt")
        cls.effects = read(ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt")
        cls.triggers = read(ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        cls.modifiers = read(ROOT / "common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        cls.events = read(ROOT / "events/ADISCORD_VAL_contract_events.txt")
        cls.ru_loc = read(RU_LOC_PATH)
        cls.en_loc = read(EN_LOC_PATH)

    def test_staff_opens_one_exclusive_plan_that_leads_to_the_strike(self) -> None:
        staff = focus_block(self.focuses, "VAL_nod_op_staff")
        self.assertIn("prerequisite = { focus = VAL_Northern_Settlement }", staff)
        for axis in self.AXES:
            body = focus_block(self.focuses, axis)
            self.assertIn("prerequisite = { focus = VAL_nod_op_staff }", body)
            exclusive = set(re.findall(r"focus = (\w+)", named_block(body, "mutually_exclusive")))
            self.assertEqual(exclusive, set(self.AXES) - {axis}, axis)
        final = focus_block(self.focuses, "VAL_nod_op_final_plan")
        self.assertRegex(
            final,
            r"prerequisite = \{\s*focus = VAL_nod_op_axis_breakthrough\s*"
            r"focus = VAL_nod_op_axis_landing\s*focus = VAL_nod_op_axis_forest\s*\}",
        )
        self.assertIn("var = VAL_nod_op_readiness value = 50", final)
        for focus_id in ("VAL_nod_op_staff", "VAL_nod_op_final_plan", *self.AXES):
            self.assertIn("bypass = { VAL_nod_op_moment_passed = yes }", focus_block(self.focuses, focus_id))
        for value, axis in enumerate(self.AXES, start=1):
            self.assertIn(f"set_variable = {{ var = VAL_nod_op_axis value = {value} }}", focus_block(self.focuses, axis))

    def test_every_preparation_step_adds_its_shown_readiness_once(self) -> None:
        for decision_id, gain in self.PREPARATION.items():
            body = named_block(self.decisions, decision_id)
            self.assertEqual(body.count("VAL_nod_op_add_readiness = yes"), 1, decision_id)
            self.assertIn(f"var = VAL_nod_op_gain value = {gain} }}", body, decision_id)
            self.assertIn(f"custom_effect_tooltip = VAL_nod_op_readiness_{gain}_tt", body, decision_id)
            if decision_id.startswith("VAL_nod_op_"):
                self.assertIn("cancel_effect", body, decision_id)
                self.assertIn("fire_only_once = yes", body, decision_id)

        helper = named_block(self.effects, "VAL_nod_op_add_readiness")
        self.assertIn("VAL_nod_op_can_prepare = yes", helper)
        self.assertIn("clamp_variable = { var = VAL_nod_op_readiness min = 0 max = 100 }", helper)
        self.assertIn("set_country_flag = VAL_nod_op_noticed", helper)
        self.assertIn("id = val_rework.205", helper)

    def test_roads_deposit_is_paid_once_and_refunded_on_every_exit(self) -> None:
        roads = named_block(self.decisions, "VAL_nod_op_border_roads")
        self.assertIn("NOT = { has_variable = VAL_nod_op_roads_deposit }", roads)
        self.assertEqual(roads.count("ADISCORD_economy_spend_300 = yes"), 1)
        self.assertIn("VAL_nod_op_refund_roads = yes", named_block(roads, "cancel_effect"))
        self.assertIn("clear_variable = VAL_nod_op_roads_deposit", named_block(roads, "remove_effect"))
        self.assertIn("VAL_nod_op_refund_roads = yes", named_block(self.effects, "VAL_nod_op_close"))

    def test_launch_pays_one_scaled_plan_bonus_from_every_war_entry(self) -> None:
        pay = named_block(self.effects, "VAL_op_pay_offensive")
        for threshold, scale, tier in (("100", "2", "3"), ("75", "1.5", "2"), ("50", "1", "1")):
            self.assertRegex(
                pay,
                rf"var = VAL_op_in_readiness value = {re.escape(threshold)} compare = greater_than_or_equals \}} \}}\s*"
                rf"set_temp_variable = \{{ var = VAL_op_scale value = {re.escape(scale)} \}}\s*"
                rf"set_variable = \{{ var = VAL_op_last_tier value = {tier} \}}",
            )
        self.assertIn("add_dynamic_modifier = { modifier = VAL_operation_offensive days = 180 }", pay)
        modifier = named_block(self.modifiers, "VAL_operation_offensive")
        self.assertIn("remove_trigger = { has_war = no }", modifier)
        variables = re.findall(r"=\s*(VAL_op_\w+)", modifier)
        self.assertGreaterEqual(len(variables), 9)
        clear = named_block(self.effects, "VAL_op_clear_offensive")
        for variable in variables:
            self.assertIn(f"multiply_variable = {{ var = {variable} value = VAL_op_scale }}", pay)
            self.assertIn(f"clear_variable = {variable}", clear)

        launch = named_block(self.effects, "VAL_nod_op_apply_launch")
        self.assertIn("NOT = { has_country_flag = VAL_nod_op_launched }", launch)
        self.assertIn("has_war_with = NOD", launch)
        self.assertIn("set_temp_variable = { var = VAL_op_in_readiness value = VAL_nod_op_readiness }", launch)
        self.assertIn("set_temp_variable = { var = VAL_op_in_profile value = VAL_nod_op_axis }", launch)
        self.assertIn("VAL_op_pay_offensive = yes", launch)
        self.assertIn("VAL_nod_op_apply_launch = yes", named_block(self.effects, "VAL_final_crisis_join_war"))
        joint = named_block(self.effects, "VAL_begin_joint_nod_shabrat_campaign")
        self.assertIn("VAL_confirm_joint_nod_entry = yes", joint)
        confirmed = named_block(self.effects, "VAL_confirm_joint_nod_entry")
        self.assertEqual(confirmed.count("VAL_nod_op_apply_launch = yes"), 1)

        close = named_block(self.effects, "VAL_nod_op_close")
        self.assertIn("VAL_op_clear_offensive = yes", close)
        self.assertIn("VAL_nod_op_close = yes", named_block(self.effects, "VAL_final_crisis_close"))

    def test_manual_campaign_needs_first_threshold_once_the_staff_exists(self) -> None:
        campaign = named_block(self.decisions, "VAL_campaign_against_nod")
        gate = named_block(campaign, "available")
        self.assertIn("NOT = { has_completed_focus = VAL_nod_op_staff }", gate)
        self.assertIn("var = VAL_nod_op_readiness value = 30", gate)

    def test_noticed_event_offers_time_or_power_and_texts_exist(self) -> None:
        source = self.events
        start = source.index("id = val_rework.205")
        block = brace_block(source, source.rfind("country_event = {", 0, start))
        options = block.split("option = {")[1:]
        self.assertEqual(len(options), 2)
        self.assertIn("var = VAL_final_escalation value = 15", options[0])
        self.assertIn("add_political_power = -35", options[1])
        self.assertIn("NOT = { has_political_power < 35 }", options[1])
        keys = set(re.findall(r"\b((?:VAL_nod_op|VAL_stl_op|VAL_op)_\w+_tt)\b", self.effects + self.decisions + self.focuses + self.events))
        keys |= {f"val_rework.{number}.{part}" for number in (205, 206, 207, 208) for part in ("t", "d", "a")}
        keys |= {f"{name}_desc" for name in ("VAL_nod_op_staff", "VAL_nod_op_final_plan", *self.AXES, *[d for d in self.PREPARATION if d.startswith("VAL_nod_op_")])}
        keys |= {f"VAL_OP_TIER_{tier}" for tier in ("FULL", "HIGH", "BASE", "NONE")}
        keys |= {"VAL_operation_offensive", "VAL_op_caught_off_guard", "VAL_op_target_unrest"}
        for loc in (self.ru_loc, self.en_loc):
            for key in sorted(keys):
                self.assertRegex(loc, rf'(?m)^ {re.escape(key)}:\d* "', key)


class KefreytStelanderOperationTests(unittest.TestCase):
    AXES = {
        "VAL_stl_op_axis_assault": 1,
        "VAL_stl_op_axis_landing": 2,
        "VAL_stl_op_axis_uprising": 4,
    }
    PREPARATION = {
        "VAL_stl_op_survey": 15,
        "VAL_stl_op_rifle_reserve": 15,
        "VAL_stl_op_mountain_batteries": 15,
        "VAL_stl_op_fada_transports": 15,
        "VAL_stl_op_fund_opposition": 15,
        "VAL_stl_op_false_talks": 5,
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS_PATH)
        cls.decisions = read(ROOT / "common/decisions/ADISCORD_VAL_decisions.txt")
        cls.effects = read(ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt")
        cls.triggers = read(ROOT / "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        cls.ru_loc = read(RU_LOC_PATH)
        cls.en_loc = read(EN_LOC_PATH)

    def test_staff_follows_the_ultimatum_and_opens_one_plan(self) -> None:
        staff = focus_block(self.focuses, "VAL_stl_op_staff")
        self.assertIn("prerequisite = { focus = VAL_Stelander_Ultimatum }", staff)
        for axis, profile in self.AXES.items():
            body = focus_block(self.focuses, axis)
            self.assertIn("prerequisite = { focus = VAL_stl_op_staff }", body)
            exclusive = set(re.findall(r"focus = (\w+)", named_block(body, "mutually_exclusive")))
            self.assertEqual(exclusive, set(self.AXES) - {axis}, axis)
            self.assertIn(f"set_variable = {{ var = VAL_stl_op_profile value = {profile} }}", body)
            self.assertIn("bypass = { VAL_stl_op_moment_passed = yes }", body)
        moment = named_block(self.triggers, "VAL_stl_op_moment_passed")
        self.assertIn("has_global_flag = STP_cw_union_wars_finished", moment)

    def test_preparation_adds_shown_readiness_once_and_refunds(self) -> None:
        for decision_id, gain in self.PREPARATION.items():
            body = named_block(self.decisions, decision_id)
            self.assertEqual(body.count("VAL_stl_op_add_readiness = yes"), 1, decision_id)
            self.assertIn(f"var = VAL_stl_op_gain value = {gain} }}", body, decision_id)
            self.assertIn(f"custom_effect_tooltip = VAL_stl_op_readiness_{gain}_tt", body, decision_id)
            self.assertIn("cancel_effect", body, decision_id)
            self.assertIn("fire_only_once = yes", body, decision_id)
        talks = named_block(self.decisions, "VAL_stl_op_false_talks")
        self.assertIn("var = VAL_stl_op_readiness value = 50", talks)

    def test_campaign_spends_the_operation_once_war_exists(self) -> None:
        campaign = named_block(self.decisions, "VAL_campaign_against_stelander")
        remove = named_block(campaign, "remove_effect")
        self.assertLess(
            remove.index("FROM = { save_event_target_as = VAL_stl_op_target }"),
            remove.index("VAL_stl_op_apply_launch = yes"),
        )
        gate = named_block(campaign, "available")
        self.assertIn("var = VAL_stl_op_readiness value = 30", gate)
        self.assertNotIn("has_war_with = ROOT", gate)
        # The order is hidden during the war instead of repeating every 90 days;
        # a mobilisation interrupted by the target's declaration still settles.
        self.assertIn("NOT = { has_war_with = ROOT }", named_block(campaign, "visible"))
        self.assertIn("cancel_if_not_visible = no", campaign)

        on_actions = read(ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        relation = named_block(on_actions, "on_war_relation_added")
        self.assertEqual(relation.count("VAL_stl_op_apply_launch = yes"), 2)
        self.assertIn("FROM = { save_event_target_as = VAL_stl_op_target }", relation)
        self.assertIn("ROOT = { save_event_target_as = VAL_stl_op_target }", relation)
        self.assertIn("set_country_flag = VAL_stl_op_counterstrike", relation)
        events = read(ROOT / "events/ADISCORD_VAL_contract_events.txt")
        report = events[events.index("id = val_rework.208\n"):]
        report = report[:report.index("\n}\n")]
        self.assertIn("text = val_rework.208.counter", report)
        self.assertIn("clr_country_flag = VAL_stl_op_counterstrike", report)

        launch = named_block(self.effects, "VAL_stl_op_apply_launch")
        self.assertIn("has_war_with = event_target:VAL_stl_op_target", launch)
        self.assertIn("set_country_flag = VAL_stl_op_launched", launch)
        self.assertIn("set_temp_variable = { var = VAL_op_in_profile value = VAL_stl_op_profile }", launch)
        self.assertIn("VAL_op_pay_offensive = yes", launch)
        self.assertIn("idea = VAL_op_target_unrest days = 90", launch)
        self.assertIn("var = VAL_op_last_tier value = 0 compare = greater_than", launch)
        self.assertIn("clear_variable = VAL_stl_op_readiness", launch)
        for loc in (self.ru_loc, self.en_loc):
            self.assertIn("$VAL_stl_op_staff$", re.search(
                r'(?m)^ VAL_focus_progression_VAL_Stelander_Ultimatum_tt:\d* "([^"]+)"', loc).group(1))


class KefreytNorthernCoalitionOperationTests(unittest.TestCase):
    PROFILE_DECISIONS = {
        "VAL_nc_op_assault_guns": 1,
        "VAL_nc_op_coastal_transports": 2,
        "VAL_nc_op_forest_rangers": 3,
    }
    PREPARATION = {
        "VAL_nc_op_survey": 15,
        "VAL_nc_op_depots": 15,
        "VAL_nc_op_winter_kit": 15,
        "VAL_nc_op_assault_guns": 15,
        "VAL_nc_op_coastal_transports": 15,
        "VAL_nc_op_forest_rangers": 15,
        "VAL_nc_op_feint": 10,
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS_PATH)
        cls.decisions = read(ROOT / "common/decisions/ADISCORD_VAL_decisions.txt")
        cls.effects = read(ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt")
        cls.events = read(ROOT / "events/ADISCORD_VAL_contract_events.txt")
        cls.ideas = read(ROOT / "common/ideas/ADISCORD_VAL_rework_ideas.txt")

    def test_war_focus_waits_for_the_staff_and_spends_the_operation(self) -> None:
        staff = focus_block(self.focuses, "VAL_nc_op_staff")
        self.assertIn("prerequisite = { focus = VAL_Northern_Settlement }", staff)
        self.assertIn("id = val_rework.209", staff)
        war = focus_block(self.focuses, "VAL_Break_The_Northern_Coalition")
        self.assertIn("prerequisite = { focus = VAL_nc_op_staff }", war)
        self.assertIn("var = VAL_nc_op_readiness value = 30", war)
        reward = named_block(war, "completion_reward")
        self.assertLess(
            reward.index("VAL_begin_northern_coalition_campaign = yes"),
            reward.index("VAL_nc_op_apply_launch = yes"),
        )
        launch = named_block(self.effects, "VAL_nc_op_apply_launch")
        self.assertIn("has_war_with = YPR", launch)
        self.assertIn("VAL_op_pay_offensive = yes", launch)
        self.assertIn("clear_variable = VAL_nc_op_profile", launch)

    def test_plan_event_sets_one_profile_and_opens_its_order(self) -> None:
        start = self.events.index("id = val_rework.209")
        block = brace_block(self.events, self.events.rfind("country_event = {", 0, start))
        options = block.split("option = {")[1:]
        self.assertEqual(len(options), 3)
        profiles = {}
        for option in options:
            profile = int(re.search(r"var = VAL_nc_op_profile value = (\d)", option).group(1))
            decision = re.search(r"unlock_decision_tooltip = (\w+)", option).group(1)
            profiles[decision] = profile
        self.assertEqual(profiles, self.PROFILE_DECISIONS)
        for decision_id, profile in self.PROFILE_DECISIONS.items():
            self.assertIn(
                f"var = VAL_nc_op_profile value = {profile} compare = equals",
                named_block(self.decisions, decision_id),
            )

    def test_preparation_adds_shown_readiness_once_and_refunds(self) -> None:
        for decision_id, gain in self.PREPARATION.items():
            body = named_block(self.decisions, decision_id)
            self.assertEqual(body.count("VAL_nc_op_add_readiness = yes"), 1, decision_id)
            self.assertIn(f"var = VAL_nc_op_gain value = {gain} }}", body, decision_id)
            self.assertIn(f"custom_effect_tooltip = VAL_nc_op_readiness_{gain}_tt", body, decision_id)
            self.assertIn("cancel_effect", body, decision_id)
            self.assertIn("fire_only_once = yes", body, decision_id)

    def test_coalition_is_reinforced_at_the_declaration(self) -> None:
        start = named_block(self.effects, "VAL_begin_northern_coalition_campaign")
        self.assertLess(start.index("VAL_join_northern_coalition_war = yes"), start.index("VAL_nc_reinforce_coalition = yes"))
        reinforce = named_block(self.effects, "VAL_nc_reinforce_coalition")
        for tag in ("YPR", "COF", "TFF"):
            self.assertIn(f"{tag} = {{", reinforce)
        self.assertEqual(reinforce.count("VAL_nc_reinforce_member = yes"), 3)
        self.assertNotIn("every_country", reinforce)
        member = named_block(self.effects, "VAL_nc_reinforce_member")
        self.assertIn("add_manpower = 8000", member)
        self.assertIn("idea = VAL_nc_coalition_resolve days = 180", member)
        idea = named_block(self.ideas, "VAL_nc_coalition_resolve")
        self.assertIn("army_defence_factor = 0.15", idea)


class KefreytBezhayskOperationTests(unittest.TestCase):
    PROFILE_DECISIONS = {
        "VAL_bjk_op_storm_groups": 1,
        "VAL_bjk_op_blockade": 3,
        "VAL_bjk_op_council_contacts": 4,
    }
    PREPARATION = {
        "VAL_bjk_op_survey": 15,
        "VAL_bjk_op_siege_train": 15,
        "VAL_bjk_op_depots": 15,
        "VAL_bjk_op_storm_groups": 15,
        "VAL_bjk_op_blockade": 15,
        "VAL_bjk_op_council_contacts": 15,
        "VAL_bjk_op_feint": 10,
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS_PATH)
        cls.decisions = read(ROOT / "common/decisions/ADISCORD_VAL_decisions.txt")
        cls.effects = read(ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt")
        cls.events = read(ROOT / "events/ADISCORD_VAL_contract_events.txt")
        cls.ideas = read(ROOT / "common/ideas/ADISCORD_VAL_rework_ideas.txt")

    def test_war_focus_waits_for_the_staff_and_spends_the_operation(self) -> None:
        staff = focus_block(self.focuses, "VAL_bjk_op_staff")
        self.assertIn("prerequisite = { focus = VAL_Contracts_Outlive_Kings }", staff)
        self.assertIn("id = val_rework.212", staff)
        war = focus_block(self.focuses, "VAL_Bezhaysk_Operation")
        self.assertIn("prerequisite = { focus = VAL_bjk_op_staff }", war)
        self.assertIn("var = VAL_bjk_op_readiness value = 30", war)
        reward = named_block(war, "completion_reward")
        declaration = reward.index("declare_war_on = { target = BJK")
        self.assertLess(declaration, reward.index("VAL_bjk_reinforce_city = yes"))
        self.assertLess(declaration, reward.index("VAL_bjk_op_apply_launch = yes"))
        launch = named_block(self.effects, "VAL_bjk_op_apply_launch")
        self.assertIn("has_war_with = BJK", launch)
        self.assertIn("VAL_op_pay_offensive = yes", launch)

    def test_plan_event_sets_one_profile_and_opens_its_order(self) -> None:
        start = self.events.index("id = val_rework.212")
        block = brace_block(self.events, self.events.rfind("country_event = {", 0, start))
        profiles = {}
        for option in block.split("option = {")[1:]:
            profile = int(re.search(r"var = VAL_bjk_op_profile value = (\d)", option).group(1))
            decision = re.search(r"unlock_decision_tooltip = (\w+)", option).group(1)
            profiles[decision] = profile
        self.assertEqual(profiles, self.PROFILE_DECISIONS)
        for decision_id, gain in self.PREPARATION.items():
            body = named_block(self.decisions, decision_id)
            self.assertEqual(body.count("VAL_bjk_op_add_readiness = yes"), 1, decision_id)
            self.assertIn(f"var = VAL_bjk_op_gain value = {gain} }}", body, decision_id)
            self.assertIn("cancel_effect", body, decision_id)

    def test_city_reinforcement_grows_with_difficulty(self) -> None:
        reinforce = named_block(self.effects, "VAL_bjk_reinforce_city")
        base, veteran = reinforce.split("difficulty > 2", 1)
        veteran, elite = veteran.split("difficulty > 3", 1)
        self.assertIn("idea = VAL_bjk_fortress_city days = 240", base)
        self.assertIn("level = 2", base)
        self.assertIn("idea = VAL_bjk_last_bastion days = 240", veteran)
        for tier in (base, veteran, elite):
            self.assertIn("add_manpower", tier)
            self.assertIn("type = infantry_equipment", tier)
        for tier in (veteran, elite):
            self.assertIn("type = bunker", tier)
        self.assertIn("allowed = { original_tag = BJK }", named_block(self.ideas, "VAL_bjk_fortress_city"))
        self.assertIn("allowed = { original_tag = BJK }", named_block(self.ideas, "VAL_bjk_last_bastion"))


class KefreytSouthernOperationTests(unittest.TestCase):
    # tag: (target, expansion focus, war order, plan event, report event,
    #       profile decisions, preparation gains)
    OPERATIONS = {
        "ert": (
            "ERT", "VAL_Southern_Expansion", "VAL_operation_expand_southern_bridgehead", 215, 217,
            {"VAL_ert_op_motor_columns": 1, "VAL_ert_op_hazard_kits": 3, "VAL_ert_op_garrison_bribes": 4},
            {
                "VAL_ert_op_route_survey": 15,
                "VAL_ert_op_bridgehead_depots": 15,
                "VAL_ert_op_administration_guides": 15,
                "VAL_ert_op_motor_columns": 15,
                "VAL_ert_op_hazard_kits": 15,
                "VAL_ert_op_garrison_bribes": 15,
                "VAL_ert_op_feint": 10,
            },
        ),
        "irt": (
            "IRT", "VAL_Eastern_Expansion", "VAL_operation_eastern_security_belt", 218, 220,
            {"VAL_irt_op_rail_raid": 1, "VAL_irt_op_outposts": 3, "VAL_irt_op_envoys": 4},
            {
                "VAL_irt_op_recon": 15,
                "VAL_irt_op_rail_depots": 15,
                "VAL_irt_op_staff_exercises": 15,
                "VAL_irt_op_rail_raid": 15,
                "VAL_irt_op_outposts": 15,
                "VAL_irt_op_envoys": 15,
                "VAL_irt_op_feint": 10,
            },
        ),
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.focuses = read(FOCUS_PATH)
        cls.decisions = read(ROOT / "common/decisions/ADISCORD_VAL_decisions.txt")
        cls.effects = read(ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt")
        cls.events = read(ROOT / "events/ADISCORD_VAL_contract_events.txt")
        cls.ideas = read(ROOT / "common/ideas/ADISCORD_VAL_rework_ideas.txt")

    def event_block(self, number: int) -> str:
        start = self.events.index(f"id = val_rework.{number}\n")
        return brace_block(self.events, self.events.rfind("country_event = {", 0, start))

    def test_war_orders_wait_for_a_started_staff_and_spend_the_operation(self) -> None:
        for tag, (target, parent, order, plan, report, _, _) in self.OPERATIONS.items():
            with self.subTest(tag=tag):
                staff = focus_block(self.focuses, f"VAL_{tag}_op_staff")
                self.assertIn(f"prerequisite = {{ focus = {parent} }}", staff)
                self.assertIn(f"id = val_rework.{plan}", staff)
                self.assertIn(f"bypass = {{ VAL_{tag}_op_moment_passed = yes }}", staff)
                decision = named_block(self.decisions, order)
                gate = named_block(decision, "available")
                self.assertIn(f"NOT = {{ has_completed_focus = VAL_{tag}_op_staff }}", gate)
                self.assertIn(f"var = VAL_{tag}_op_readiness value = 30", gate)
                effect = named_block(decision, "complete_effect")
                declaration = effect.index(f"declare_war_on = {{ target = {target}")
                self.assertLess(declaration, effect.index(f"{target} = {{ VAL_south_reinforce_defender = yes }}"))
                self.assertLess(declaration, effect.index(f"VAL_{tag}_op_apply_launch = yes"))
                launch = named_block(self.effects, f"VAL_{tag}_op_apply_launch")
                self.assertIn(f"has_war_with = {target}", launch)
                self.assertIn(f"NOT = {{ has_country_flag = VAL_{tag}_op_launched }}", launch)
                self.assertIn("VAL_op_pay_offensive = yes", launch)
                self.assertIn(f"id = val_rework.{report}", launch)

    def test_plan_events_set_one_profile_and_open_their_order(self) -> None:
        for tag, (_, _, _, plan, _, profile_decisions, preparation) in self.OPERATIONS.items():
            with self.subTest(tag=tag):
                profiles = {}
                for option in self.event_block(plan).split("option = {")[1:]:
                    profile = int(re.search(rf"var = VAL_{tag}_op_profile value = (\d)", option).group(1))
                    decision = re.search(r"unlock_decision_tooltip = (\w+)", option).group(1)
                    profiles[decision] = profile
                self.assertEqual(profiles, profile_decisions)
                for decision_id, gain in preparation.items():
                    body = named_block(self.decisions, decision_id)
                    self.assertEqual(body.count(f"VAL_{tag}_op_add_readiness = yes"), 1, decision_id)
                    self.assertIn(f"var = VAL_{tag}_op_gain value = {gain} }}", body, decision_id)
                    self.assertIn(f"cancel_trigger = {{ hidden_trigger = {{ VAL_{tag}_op_can_prepare = no }} }}", body, decision_id)
                    self.assertIn("cancel_effect", body, decision_id)

    def test_full_preparation_reaches_full_readiness(self) -> None:
        for tag, (_, _, _, _, _, profile_decisions, preparation) in self.OPERATIONS.items():
            with self.subTest(tag=tag):
                common = sum(gain for decision, gain in preparation.items() if decision not in profile_decisions)
                # Staff focus 15, plan 10, one profile order 15 and the noticed event 5.
                self.assertEqual(15 + 10 + common + 15 + 5, 100)

    def test_defenders_mobilise_once_and_grow_with_difficulty(self) -> None:
        reinforce = named_block(self.effects, "VAL_south_reinforce_defender")
        self.assertIn("NOT = { has_country_flag = VAL_south_defence_mobilised }", reinforce)
        self.assertIn("has_war_with = ROOT", reinforce)
        base, veteran = reinforce.split("difficulty > 2", 1)
        veteran, elite = veteran.split("difficulty > 3", 1)
        self.assertIn("idea = VAL_south_zone_defence days = 180", base)
        self.assertIn("idea = VAL_south_zone_militia days = 180", veteran)
        for tier in (base, veteran, elite):
            self.assertIn("add_manpower", tier)
            self.assertIn("type = infantry_equipment", tier)
            self.assertIn("VAL_south_raise_detachments = yes", tier)
        self.assertNotIn("type = bunker", base)
        for tier in (veteran, elite):
            self.assertIn("type = bunker", tier)
        raise_units = named_block(self.effects, "VAL_south_raise_detachments")
        self.assertIn('has_template = "CBRN Protection Detachment"', raise_units)
        for idea in ("VAL_south_zone_defence", "VAL_south_zone_militia"):
            self.assertIn(
                "allowed = { OR = { original_tag = ERT original_tag = IRT } }",
                named_block(self.ideas, idea),
            )
        for idea in ("VAL_op_caught_off_guard", "VAL_op_target_unrest"):
            allowed = named_block(named_block(self.ideas, idea), "allowed")
            self.assertIn("original_tag = ERT", allowed)
            self.assertIn("original_tag = IRT", allowed)


if __name__ == "__main__":
    unittest.main()
