from __future__ import annotations

import re
import unittest
from pathlib import Path


from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"
ON_ACTIONS_PATH = ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"
RU_LOC_PATH = ROOT / "localisation/russian/ADISCORD_VAL_decisions_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation/english/ADISCORD_VAL_decisions_l_english.yml"


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
            {
                "VAL_Operational_Directorate",
                "VAL_Inventory_The_Empty_Yards",
                "VAL_Resource_War_Contracts",
                "VAL_Brokered_Steel",
            },
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
                    self.assertIn(
                        f"${target}$", localisation[localisation.index(key) :]
                    )

    def test_world_event_reveals_are_explained_in_root_descriptions(self) -> None:
        for localisation in (self.en_loc, self.ru_loc):
            stelander = re.search(
                r'(?m)^\s*VAL_Stelander_Crisis_Opens_desc:\d*\s+"([^"]+)"', localisation
            )
            resource = re.search(
                r'(?m)^\s*VAL_Resource_War_Contracts_desc:\d*\s+"([^"]+)"', localisation
            )
            self.assertIsNotNone(stelander)
            self.assertIsNotNone(resource)
            self.assertIn("§Y", stelander.group(1))
            self.assertIn("§Y", resource.group(1))
            self.assertIn("$VAL_Operational_Directorate$", resource.group(1))

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
            "VAL_Occidian_Claims_Commission": "VAL_The_Steel_Contract",
            "VAL_Occidian_Registries": "VAL_Occidian_Claims_Commission",
            "VAL_econ_development_fund": "VAL_Industrial_Mobilization_Plan",
        }
        for focus_id, milestone in expected.items():
            body = focus_block(self.focuses, focus_id)
            self.assertNotIn("dynamic = yes", body, focus_id)
            self.assertNotIn("allow_branch", body, focus_id)
            self.assertIn(f"has_completed_focus = {milestone}", body, focus_id)

    def test_contracts_outlive_kings_is_a_visible_capstone(self) -> None:
        body = focus_block(self.focuses, "VAL_Contracts_Outlive_Kings")
        self.assertNotRegex(body, r"(?m)^\s*allow_branch\s*=")
        self.assertNotIn("dynamic = yes", body)
        for dependency in (
            "VAL_State_Contract",
            "VAL_Industrial_Mobilization_Plan",
            "VAL_Army_Of_The_Ledger",
        ):
            self.assertIn(f"prerequisite = {{ focus = {dependency} }}", body)
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
        self.assertNotIn("dynamic = yes", gate)
        self.assertNotIn("allow_branch", gate)
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

    def test_frontier_reveal_does_not_claim_the_focus_is_ready(self) -> None:
        body = focus_block(self.focuses, "VAL_frontier_conference")
        groups = re.findall(r"prerequisite\s*=\s*\{([^}]+)\}", body)
        self.assertEqual(groups[0].strip(), "focus = VAL_Contracts_Outlive_Kings")
        dependencies = set(re.findall(r"\bfocus\s*=\s*(\w+)", " ".join(groups)))
        for source in (self.ru_loc, self.en_loc):
            description = re.search(
                r'(?m)^\s*VAL_frontier_conference_desc:\d*\s+"([^\"]+)"', source
            ).group(1)
            for dependency in dependencies:
                self.assertIn(f"${dependency}$", description)
            guide = re.search(
                r'(?m)^\s*VAL_startup_guide:\d*\s+"([^\"]+)"', source
            ).group(1)
            self.assertIn("$VAL_Contracts_Outlive_Kings$", guide)

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
        stelander = focus_block(self.focuses, "VAL_Stelander_Crisis_Opens")
        self.assertNotIn("dynamic = yes", stelander)
        self.assertNotIn("allow_branch", stelander)
        self.assertIn("has_global_flag = STP_cw_started", stelander)

        resource = allow(self.focuses, "VAL_Resource_War_Contracts")
        self.assertIn("ADISCORD_nam_resource_war_active = yes", resource)
        self.assertNotIn("has_completed_focus =", resource)
        root = focus_block(self.focuses, "VAL_Resource_War_Contracts")
        self.assertIn("prerequisite = { focus = VAL_Operational_Directorate }", root)
        self.assertNotIn("prerequisite = { focus = VAL_Ministry_Auditors }", root)

        vorkerland = allow(self.focuses, "VAL_Vorkerland_Contracts_Burn")
        self.assertIn("ADISCORD_vorkerland_collapse_wars_started", vorkerland)
        self.assertIn("has_completed_focus = VAL_Operational_Directorate", vorkerland)

    def test_late_campaign_roadmap_is_static_and_prerequisite_gated(self) -> None:
        expected = {
            "VAL_Integrate_Occidia": "VAL_Occidian_Registries",
            "VAL_Balchansk_Charter": "VAL_Occidian_Registries",
            "VAL_Bezhaysk_Operation": "VAL_Contracts_Outlive_Kings",
            "VAL_Return_Southern_Tsaygen": "VAL_Contracts_Outlive_Kings",
            "VAL_frontier_return_irem": "VAL_Return_Southern_Tsaygen",
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
            "VAL_Return_To_World_Market": "VAL_Reopen_Trade_Routes",
            "VAL_Eastern_Expansion": "VAL_Southern_Expansion",
        }
        for focus_id, milestone in expected.items():
            body = focus_block(self.focuses, focus_id)
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

    def test_only_world_reactive_roots_remain_dynamic(self) -> None:
        ids = focus_ids(self.focuses)
        staged = []
        for focus_id in ids:
            block = focus_block(self.focuses, focus_id)
            if not re.search(r"(?m)^\s*allow_branch\s*=", block):
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
                "VAL_Vorkerland_Contracts_Burn",
                "VAL_Audit_Lost_Contracts",
                "VAL_Resource_War_Contracts",
                "VAL_Support_The_Viceroy",
                "VAL_Westerholm_Concessions",
            },
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
            {
                "VAL_Operational_Directorate",
                "VAL_Inventory_The_Empty_Yards",
                "VAL_Resource_War_Contracts",
                "VAL_Brokered_Steel",
            },
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
            "VAL_frontier_security_plan",
        ):
            self.assertIn(focus_id, done)
        self.assertLess(order.index("VAL_Integrate_Occidia"), order.index("VAL_The_Weaponry_Baron"))
        self.assertNotIn("VAL_Balchansk_Charter", done)
        self.assertNotIn("VAL_Returning_Buyers", done)

    def test_trade_route_does_not_permanently_defer_an_available_northern_target(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries

        category = block(entries("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_frontier")
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


if __name__ == "__main__":
    unittest.main()
