from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import product
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from tools.lib.paths import source_section
from tools.lib.vorkerland_leader_branches import LEADER_BRANCH_FOCUS_IDS
from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    _can_share_view,
    lifecycle_tree,
    _plan_reward_contract,
    VAD_MANDATE_ENTRIES,
    ACTIVE_PHASE_FLAGS,
    CLAIMANT_EVENTS_FILE,
    CLAIMANT_FOCUS_EVENT_IDS,
    CLAIMANT_OWNED_EVENT_IDS,
    CLAIMANT_PROGRAMME_EVENT_IDS,
    CLAIMANT_NEWS_EVENT_IDS,
    CENTRAL_CAPSTONES,
    CENTRAL_PREPARED_FLAG,
    CHARACTER_FILE,
    DEPTH_AI_PLANS,
    DEPTH_ANCHORS,
    DEPTH_COSTS,
    DEPTH_EXCLUSIVE_PAIRS,
    DEPTH_FOCUSES,
    DEPTH_LATE_WAR_FOCUSES,
    DEPTH_LEGITIMACY_DELTAS,
    DEPTH_MODULE_FOCUSES,
    DEPTH_PERMANENT_IDEAS,
    DEPTH_POSITIONS,
    DEPTH_POSTWAR_CAPSTONES,
    DEPTH_TIMED_IDEAS,
    DEPTH_VARIANT_IDENTITY,
    COLLAPSE_IDEAS_FILE,
    COMMITTEE_STATE_ORDERS,
    COMMITTEE_TRIGGER_FILE,
    CONFEDERATION_BRANCHES,
    CONFEDERATION_COUNCIL_FOCUSES,
    CONFEDERATION_EXECUTIVE_CHOICES,
    CONFEDERATION_EXECUTIVE_FOCUSES,
    CONFEDERATION_FILE,
    CONFEDERATION_LATE_UNLOCKS,
    CONFEDERATION_ORDER_UPGRADES,
    CONFEDERATION_PROGRAMMES,
    CONFEDERATION_SHARED_FOCUSES,
    CONGRESS_AI_PLAN,
    CONTINUOUS_FOCUS_FILE,
    CORE_DECISIONS,
    DIPLOMACY_DECISIONS_FILE,
    DIPLOMACY_EFFECTS_FILE,
    ENGLISH_LOCALISATION,
    ENGLISH_POSTWAR_IDEA_LOCALISATION,
    FOCUS_DECISION_FILES,
    FOCUS_EXPANSION_IDEAS,
    FOCUS_EXPANSION_IDEAS_FILE,
    lifecycle_order,
    FOCUS_FILE,
    FOCUS_IDS,
    IVANLAND_EXPEDITIONARY_IDEA,
    LAND_REPAIR_IDEAS,
    LATE_WAR_PHASE_FLAGS,
    MOBILE_REPAIR_IDEA,
    PHASE_EFFECTS_FILE,
    POSTWAR_PHASE,
    POSTWAR_EXECUTIVE_CHOICE,
    POSTWAR_EXECUTIVE_FINAL,
    POSTWAR_EXECUTIVE_FOCUSES,
    POSTWAR_EXECUTIVE_GATE,
    POSTWAR_EXECUTIVE_POSITIONS,
    POSTWAR_EXECUTIVE_ROUTE,
    POSTWAR_IDEA_LOCALISATION_IDS,
    POSTWAR_POLICY_CHOICE_PAIRS,
    POSTWAR_ROUTE_FOCUSES,
    POSTWAR_ROUTE_TERMINALS,
    POSTWAR_SETTLEMENT_IDEAS,
    POSTWAR_TRANSITIONAL_IDEAS,
    NATION_TARGET,
    PRECOLLAPSE_CRISIS_IDEAS,
    PRECOLLAPSE_CRISIS_SCRUB_EFFECT,
    PRECOLLAPSE_SCRUBBED_IDEAS,
    PREWAR_CARRYOVER_EFFECT,
    PREWAR_CARRYOVER_FLAG,
    PREWAR_COURSE_SELECTIONS,
    PREWAR_EXPANSION_COSTS,
    LAYOUT_ANCHORS,
    LAYOUT_BANDS,
    LIFECYCLE_TREES,
    PREWAR_EXPANSION_POSITIONS,
    SUPPORTED_SEARCH_FILTERS,
    _layout_band,
    _relative_anchor,
    resolved_positions,
    PREWAR_EXPANSION_PREREQUISITES,
    PREWAR_PHASE,
    PREWAR_VAD_BASE_FOCUSES,
    PREWAR_VAD_EXPANSION_FOCUSES,
    PREWAR_VAD_FOCUSES,
    PREWAR_WRK_BASE_FOCUSES,
    PREWAR_WRK_CARRYOVER_FOCUSES,
    PREWAR_WRK_EXPANSION_FOCUSES,
    PREWAR_WRK_FOCUSES,
    PREWAR_WRK_BLOCK_GAP,
    PREWAR_WRK_CELLS,
    PREWAR_WRK_PATRON_GATES,
    PREWAR_WRK_ROOT_CELL,
    PREWAR_WRK_TREES,
    WRK_PREWAR_ROOT,
    prewar_tree_issues,
    prewar_wrk_patron_gate,
    prewar_wrk_tree_focuses,
    RETREAT_HOOKS,
    ROOT,
    RUSSIAN_LOCALISATION,
    RUSSIAN_POSTWAR_IDEA_LOCALISATION,
    SETTLEMENT_AGGREGATE_FILE,
    SETTLEMENT_AI_PLAN,
    SETTLEMENT_LOCALISATION_KEYS,
    SETTLEMENT_PROGRAMMES,
    SHINE_FILE,
    SHOWDOWN_PHASE,
    SHOWDOWN_AI_PLANS,
    SHOWDOWN_COSTS,
    SHOWDOWN_FOCUSES,
    SHOWDOWN_POSITIONS,
    SHOWDOWN_PREREQUISITES,
    REMAINING_FRONTS_FOCUSES,
    TVA_AI_PLAN_FILE,
    TVA_OPTIONAL_AI_PLANS,
    TVA_OPTIONAL_COSTS,
    TVA_OPTIONAL_OUTCOME_FOCUSES,
    TVA_OPTIONAL_POSITIONS,
    TVA_OPTIONAL_TIMED_IDEAS,
    TVA_OPTIONAL_WARTIME_FOCUSES,
    TVA_VARIANT_FOCUSES,
    RETIRED_HANDOFF_EFFECTS,
    RETIRED_WARTIME_FOCUSES,
    VAD_VARIANT_FOCUSES,
    VARIANT_BRANCHES,
    VARIANT_CLEANUP_FOCUSES,
    VARIANT_IDEAS,
    VARIANT_PERMANENT_IDEAS,
    TVA_AGGREGATE_PREVIEWS,
    WAR_ECONOMY_CAPSTONES,
    WAR_ECONOMY_DYNAMIC,
    WAR_ECONOMY_MODIFIER_FILE,
    WAR_ECONOMY_REFRESH_EFFECT,
    WAR_ECONOMY_REFRESH_FILE,
    WARTIME_ROUTE_FOCUSES,
    WKR_AI_PLAN_FILE,
    WKR_OPTIONAL_WARTIME_FOCUSES,
    VAD_AI_PLAN_FILE,
    VAD_LATE_WAR_BRIDGE_COSTS,
    VAD_LATE_WAR_BRIDGE_FOCUSES,
    VAD_LATE_WAR_BRIDGE_POSITIONS,
    VAD_LATE_WAR_BRIDGE_PREREQUISITES,
    VAD_LATE_WAR_BRIDGE_REWARDS,
    VAD_OPTIONAL_COSTS,
    VAD_OPTIONAL_OUTCOME_FOCUSES,
    VAD_OPTIONAL_POSITIONS,
    VAD_OPTIONAL_WARTIME_FOCUSES,
    VAD_PERMANENT_PROTOCOL_IDEAS,
    VAD_WARTIME_TIMED_IDEAS,
    WARTIME_OUTCOME_EXCLUSIONS,
    WARTIME_OUTCOME_FALSE_GATE_TOKENS,
    WARTIME_ROUTE_CONVERGENCE,
    WARTIME_ROUTE_IDENTITIES,
    WARTIME_TERMINALS,
    WKR_VARIANT_FOCUSES,
    WORX_ADAPTIVE_LOGISTICS_IDEA,
    WORX_FIELD_DIRECTORATE_IDEAS,
    WORX_POSTWAR_PROVISIONAL_IDEAS,
    WORX_WARTIME_TIMED_IDEAS,
    WORKER_REFORM_STAGE_IDEAS,
    UNIFICATION_EFFECTS,
    UNIFICATION_SETTLEMENT_EFFECTS,
    _blocks,
    _allow_branch,
    _check_focus_reference_order,
    _check_confederation_tree,
    _check_settlement_branch,
    committee_order_issues,
    confederation_can_share_view,
    confederation_path_units,
    confederation_reachable,
    confederation_reward_classes,
    confederation_view,
    planned_focuses,
    _focus_cost,
    _mutually_exclusive_focuses,
    _phase_flags,
    _postwar_completion_paths,
    _postwar_reward_categories,
    _prerequisite_groups,
    _prerequisites,
    _reachable_wartime_outcome,
    _reachable_vad_optional_outcome,
    _reachable_tva_optional_outcome,
    collect_issues,
    focus_blocks,
    localisation_entries,
    read,
    settlement_aggregate_delta,
    settlement_aggregate_fields,
    settlement_free_path_units,
    settlement_reward_classes,
    unification_spirit_issues,
)


class VorkerlandLifecycleFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = source_section(read(FOCUS_FILE), 'civil_war_focus')
        cls.blocks = focus_blocks(cls.source)
        # The tree positions almost every focus with relative_position_id, so
        # anything that asserts where a focus appears on screen has to compare
        # the resolved grid cell rather than the authored offset.
        cls.grid = resolved_positions(cls.blocks)
        cls.continuous_source = read(CONTINUOUS_FOCUS_FILE)
        cls.continuous_blocks = focus_blocks(cls.continuous_source)
        cls.phase_effects = source_section(read(PHASE_EFFECTS_FILE), 'phase_effects')
        cls.collapse_ideas = source_section(read(COLLAPSE_IDEAS_FILE), 'collapse_ideas')
        cls.focus_expansion_ideas = source_section(
            read(FOCUS_EXPANSION_IDEAS_FILE), 'focus_expansion_ideas'
        )
        cls.claimant_events = source_section(
            read(CLAIMANT_EVENTS_FILE), 'claimant_events'
        )
        cls.diplomacy_effects = source_section(
            read(DIPLOMACY_EFFECTS_FILE), 'diplomacy_effects'
        )
        cls.wkr_ai_plans = source_section(read(WKR_AI_PLAN_FILE), 'wkr_wartime_plan')
        cls.vad_ai_plans = source_section(read(VAD_AI_PLAN_FILE), 'vad_wartime_plan')
        cls.tva_ai_plans = source_section(read(TVA_AI_PLAN_FILE), 'tva_wartime_plan')

    def test_vad_and_tva_cards_have_native_horizontal_clearance(self):
        for tag in ("VAD_", "TVA_"):
            rows = {}
            for name, (x, y) in self.grid.items():
                if name.startswith(tag) and lifecycle_tree(name) == f"ADISCORD_vorkerland_{tag[:3].lower()}_focus":
                    rows.setdefault(y, []).append((x, name))
            for y, row in rows.items():
                ordered = sorted(row)
                # Course blocks drawn for different governments never meet on screen.
                for index, (left_x, left) in enumerate(ordered):
                    for right_x, right in ordered[index + 1:]:
                        if not _can_share_view(left, right):
                            continue
                        self.assertGreaterEqual((right_x - left_x) * 96, 165,
                                                f"{left} and {right} overlap on row {y}")

    def test_integrated_focus_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_capstone_report_validation_rejects_missing_and_duplicate_dispatch(self) -> None:
        original = read(CLAIMANT_EVENTS_FILE)
        call = "country_event = { id = ADISCORD_vorkerland_claimant.100 hours = 1 }"
        for replacement in ("", f"{call} {call}", call.replace("country_event", "news_event")):
            mutated = original.replace(call, replacement, 1)
            self.assertNotEqual(original, mutated)
            with self.subTest(replacement=replacement), patch(
                "tools.validators.validate_adiscord_vorkerland_civil_war_focus.read",
                side_effect=lambda path: mutated if path == CLAIMANT_EVENTS_FILE else read(path),
            ):
                self.assertIn(
                    "claimant capstone 30 must dispatch its country report once",
                    collect_issues(),
                )

    def test_postwar_trees_reject_a_literal_wrk_gate(self) -> None:
        original = read(FOCUS_FILE)
        claimant_selector = "OR = { tag = WKR tag = VAD tag = TVA }"
        focus_id = "WRK_worker_convene_reunification_congress"
        focus = self.blocks[focus_id]
        nation_gate = f"tag = {NATION_TARGET}"
        self.assertIn(nation_gate, focus)
        self.assertEqual(original.count(focus), 1)
        # One pass covers both gates: the settlement tree is the first tree
        # with a claimant selector, and the focus is its root.
        mutated = original.replace(claimant_selector, "tag = WRK", 1).replace(
            focus, focus.replace(nation_gate, "tag = WRK", 1), 1
        )
        with patch(
            "tools.validators.validate_adiscord_vorkerland_civil_war_focus.read",
            side_effect=lambda path: mutated if path == FOCUS_FILE else read(path),
        ):
            issues = collect_issues()
        self.assertIn(
            "ADISCORD_vorkerland_settlement_focus selector must cover "
            "['TVA', 'VAD', 'WKR'], found ['WRK']",
            issues,
        )
        self.assertIn(
            f"{focus_id} must expose only the block of the unified nation target",
            issues,
        )

    def test_each_lifecycle_tree_selects_only_its_own_tags(self) -> None:
        trees = _blocks(self.source, "focus_tree")
        self.assertEqual(len(trees), len(LIFECYCLE_TREES))
        for tree, (tree_id, (_, tags)) in zip(trees, LIFECYCLE_TREES.items()):
            self.assertIn(f"\tid = {tree_id}\n", tree)
            selector = tree.split("default = no", maxsplit=1)[0]
            self.assertEqual(set(re.findall(r"\btag = ([A-Z]{3})\b", selector)), tags, tree_id)
            self.assertNotIn("original_tag", selector)

    def test_manifest_has_all_bounded_lifecycle_definitions(self) -> None:
        self.assertEqual(tuple(self.blocks), lifecycle_order())
        # The worker and technocratic routes continue in their own trees after the Unity Tower.
        self.assertEqual(len(self.blocks), 364 + len(LEADER_BRANCH_FOCUS_IDS))
        self.assertEqual(len(POSTWAR_EXECUTIVE_FOCUSES), 7)
        self.assertEqual(len(DEPTH_FOCUSES), 45)
        self.assertEqual(len(WKR_VARIANT_FOCUSES), 6)
        self.assertEqual(len(VAD_VARIANT_FOCUSES), 6)
        self.assertEqual(len(TVA_VARIANT_FOCUSES), 6)
        # The shared root and the three trees of the apparatuses.
        self.assertEqual(len(PREWAR_WRK_FOCUSES), 98)
        self.assertEqual(
            {
                tree: [(name, len(cells)) for name, cells in blocks]
                for tree, blocks in PREWAR_WRK_TREES.items()
            },
            {
                "committees": [
                    ("budget", 5), ("tower", 3), ("capital", 6), ("core", 8), ("politics", 11),
                ],
                "staff": [
                    ("purse", 5), ("court", 6), ("core", 8), ("army", 5), ("tower", 8),
                ],
                "network": [
                    ("funds", 5), ("cells", 6), ("core", 8), ("plants", 5), ("tower", 8),
                ],
            },
        )
        self.assertEqual(len(PREWAR_VAD_FOCUSES), 15)
        self.assertEqual(len(PREWAR_WRK_EXPANSION_FOCUSES), 4)
        self.assertEqual(len(PREWAR_VAD_EXPANSION_FOCUSES), 4)
        self.assertEqual(len(RETIRED_WARTIME_FOCUSES), 3)
        self.assertEqual(
            {tag: len(route) for tag, route in WARTIME_ROUTE_FOCUSES.items()},
            {"WKR": 17, "VAD": 21, "TVA": 18},
        )
        self.assertEqual(len(WKR_OPTIONAL_WARTIME_FOCUSES), 7)
        self.assertEqual(len(VAD_OPTIONAL_WARTIME_FOCUSES), 12)
        self.assertEqual(len(VAD_LATE_WAR_BRIDGE_FOCUSES), 4)
        self.assertEqual(len(TVA_OPTIONAL_WARTIME_FOCUSES), 11)
        self.assertEqual(len(REMAINING_FRONTS_FOCUSES), 3)
        self.assertEqual(
            {tag: len(focuses) for tag, focuses in SHOWDOWN_FOCUSES.items()},
            {"WKR": 7, "VAD": 5, "TVA": 5},
        )
        self.assertTrue(
            all(len(route) == (12 if flag.endswith("_joint") else 11)
                for flag, route in POSTWAR_ROUTE_FOCUSES.items())
        )

    def test_patron_trees_are_gated_and_never_drawn_together(self) -> None:
        trees = {tree: prewar_wrk_tree_focuses(tree) for tree in PREWAR_WRK_TREES}
        self.assertEqual(PREWAR_WRK_FOCUSES[0], WRK_PREWAR_ROOT)
        self.assertEqual(
            set(PREWAR_WRK_FOCUSES), {WRK_PREWAR_ROOT, *(f for tree in trees.values() for f in tree)}
        )
        gates = {prewar_wrk_patron_gate(tree) for tree in trees}
        for tree, focus_ids in trees.items():
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    # Every focus but the root names exactly the gate of its own tree.
                    found = {gate for gate in gates if f"{gate} = yes" in self.blocks[focus_id]}
                    self.assertEqual(found, {prewar_wrk_patron_gate(tree)})
                    self.assertEqual(PREWAR_WRK_PATRON_GATES[focus_id], prewar_wrk_patron_gate(tree))
                    self.assertTrue(_can_share_view(focus_id, WRK_PREWAR_ROOT))
                    self.assertTrue(_can_share_view(focus_id, focus_ids[0]))
                    for other, other_ids in trees.items():
                        if other != tree:
                            self.assertFalse(_can_share_view(focus_id, other_ids[0]))
        self.assertNotIn(WRK_PREWAR_ROOT, PREWAR_WRK_PATRON_GATES)
        self.assertFalse([gate for gate in gates if f"{gate} = yes" in self.blocks[WRK_PREWAR_ROOT]])

    def test_prewar_trees_follow_their_manifest_and_the_block_layout(self) -> None:
        grid = resolved_positions(self.blocks)
        self.assertEqual(prewar_tree_issues(self.blocks, grid), [])
        self.assertEqual(grid[WRK_PREWAR_ROOT], PREWAR_WRK_ROOT_CELL)
        self.assertEqual(LAYOUT_ANCHORS[WRK_PREWAR_ROOT], PREWAR_WRK_ROOT_CELL)
        for focus_id, cell in PREWAR_WRK_CELLS.items():
            self.assertEqual(grid[focus_id], cell, focus_id)
        # The band holds the widest tree and nothing more.
        (left, right), (top, bottom) = LAYOUT_BANDS["prewar_WRK"]
        columns = [x for x, _y in PREWAR_WRK_CELLS.values()]
        rows = [y for _x, y in PREWAR_WRK_CELLS.values()]
        self.assertEqual((min(columns), min(rows), max(rows)), (left, top, bottom))
        self.assertLessEqual(max(columns), right)
        # Worker's blocks, left to right, two free columns apart.
        spans = [
            (name, min(x for x, _y in cells.values()), max(x for x, _y in cells.values()))
            for name, cells in PREWAR_WRK_TREES["committees"]
        ]
        self.assertEqual(
            spans,
            [("budget", 0, 2), ("tower", 5, 7), ("capital", 10, 12), ("core", 15, 17), ("politics", 20, 26)],
        )
        for (_name, _left, right), (_next, left, _right) in zip(spans, spans[1:]):
            self.assertEqual(left - right - 1, PREWAR_WRK_BLOCK_GAP)
        # The staff and the network stand in the same template columns around the core.
        for tree, names in (
            ("staff", ("purse", "court", "core", "army", "tower")),
            ("network", ("funds", "cells", "core", "plants", "tower")),
        ):
            self.assertEqual(
                [
                    (name, min(x for x, _y in cells.values()), max(x for x, _y in cells.values()))
                    for name, cells in PREWAR_WRK_TREES[tree]
                ],
                list(zip(names, (5, 10, 15, 20, 25), (7, 12, 17, 22, 27))),
            )
        # The two template trees fill the same cells.
        self.assertEqual(
            sorted(cell for _name, cells in PREWAR_WRK_TREES["staff"] for cell in cells.values()),
            sorted(cell for _name, cells in PREWAR_WRK_TREES["network"] for cell in cells.values()),
        )
        # A moved focus, a dropped exclusive pair and a crowded row are all reported.
        moved = dict(grid)
        moved["WRK_committee_store_keys"] = (11, 6)
        self.assertIn(
            "WRK_committee_store_keys must sit at (11, 5) of the prewar committees block capital, "
            "found (11, 6)",
            prewar_tree_issues(self.blocks, moved),
        )
        unpaired = dict(self.blocks)
        for focus_id in ("WRK_reinforce_the_tower_guard", "WRK_disperse_the_government"):
            unpaired[focus_id] = re.sub(r"\n\t\tmutually_exclusive = \{[^\n]*", "", unpaired[focus_id])
        self.assertIn(
            "prewar committees block tower must offer a mutually exclusive pair",
            prewar_tree_issues(unpaired, grid),
        )
        crowded = {
            "committees": (
                ("budget", {"WRK_emergency_central_budget": (0, 1), "WRK_district_emergency_powers": (1, 1)}),
                ("tower", {"WRK_inspect_the_unity_tower": (3, 1)}),
            ),
        }
        with patch(
            "tools.validators.validate_adiscord_vorkerland_civil_war_focus.PREWAR_WRK_TREES", crowded
        ):
            issues = prewar_tree_issues(self.blocks, grid)
        self.assertIn(
            "WRK_emergency_central_budget and WRK_district_emergency_powers of the prewar committees "
            "tree are neighbours in row 1 without a free cell between them",
            issues,
        )
        self.assertIn(
            "prewar committees block tower starts at column 3; 2 free columns must follow column 1",
            issues,
        )
        self.assertIn("prewar committees block tower must offer a mutually exclusive pair", issues)

    def test_each_claimant_has_a_compact_wartime_route(self) -> None:
        for tag, expected in {"WKR": 17, "VAD": 21, "TVA": 18}.items():
            with self.subTest(tag=tag):
                self.assertEqual(len(WARTIME_ROUTE_FOCUSES[tag]), expected)
                source = "\n".join(
                    self.blocks[focus_id] for focus_id in WARTIME_ROUTE_FOCUSES[tag]
                )
                for retired_id in RETIRED_WARTIME_FOCUSES:
                    self.assertNotIn(f"focus = {retired_id}", source)

    def test_wkr_southern_branch_is_live_optional_and_outcome_neutral(self) -> None:
        optional = set(WKR_OPTIONAL_WARTIME_FOCUSES)
        capstone = self.blocks["WKR_republic_fights_as_one"]
        self.assertEqual(optional & _prerequisites(capstone), set())
        for focus_id in WKR_OPTIONAL_WARTIME_FOCUSES:
            with self.subTest(focus_id=focus_id):
                block = self.blocks[focus_id]
                self.assertEqual(_phase_flags(block), ACTIVE_PHASE_FLAGS)
                self.assertIn("tag = WKR", block)
                self.assertNotIn("has_country_leader", block)
                self.assertNotIn("has_country_leader_ideology", block)
                cost = int(re.search(r"(?m)^\s*cost\s*=\s*(\d+)\s*$", block).group(1))
                self.assertIn(cost, {2, 3})
        terminal = self.blocks["WKR_intervene_in_solyarino"]
        self.assertEqual(
            terminal.count(
                "ADISCORD_vorkerland_attempt_wkr_solyarino_intervention = yes"
            ),
            1,
        )
        self.assertNotIn("declare_war_on", terminal)
        self.assertIn(
            "ADISCORD_vorkerland_wkr_has_solyarino_intervention_border = yes",
            terminal,
        )
        available = _blocks(terminal, "available")[0]
        for phase in (
            "ADISCORD_vorkerland_phase_central_preparation",
            "ADISCORD_vorkerland_phase_central_showdown",
        ):
            self.assertIn(f"has_global_flag = {phase}", available)
        for obsolete_blocker in (
            "ADISCORD_vorkerland_focus_central_showdown_requested",
            "ADISCORD_vorkerland_showdown_queue_initialized",
            "ADISCORD_vorkerland_central_showdown_started",
            "ADISCORD_vorkerland_vad_sol_alliance_accepted",
        ):
            self.assertNotIn(obsolete_blocker, available)

    def test_remaining_fronts_are_unstick_lanes_not_outcome_depth(self) -> None:
        self.assertEqual(
            REMAINING_FRONTS_FOCUSES,
            (
                "WKR_open_the_remaining_fronts",
                "VAD_open_the_remaining_fronts",
                "TVA_open_the_remaining_fronts",
            ),
        )
        expected_cells = {
            "WKR_open_the_remaining_fronts": (6, 8),
            "VAD_open_the_remaining_fronts": (62, 8),
            "TVA_open_the_remaining_fronts": (90, 8),
        }
        expected_parents = {
            "WKR_open_the_remaining_fronts": "WKR_affirm_worker_mandate",
            "VAD_open_the_remaining_fronts": "VAD_proclaim_joint_charter",
            "TVA_open_the_remaining_fronts": "TVA_codify_utilitarian_directorate",
        }
        occupied = set(self.grid.values())
        for focus_id, parent in expected_parents.items():
            with self.subTest(focus_id=focus_id):
                block = self.blocks[focus_id]
                self.assertEqual(self.grid[focus_id], expected_cells[focus_id])
                self.assertEqual(_prerequisites(block), {parent})
                self.assertEqual(_focus_cost(block), 3)
                self.assertIn(
                    "ADISCORD_vorkerland_attempt_remaining_central_fronts = yes",
                    block,
                )
                self.assertNotIn("declare_war_on", block)
                self.assertNotIn("any_neighbor_country", block)
                self.assertIn(
                    "ADISCORD_vorkerland_claimant_has_remaining_central_targets = yes",
                    block,
                )
                self.assertIn(
                    "ADISCORD_vorkerland_focus_central_minor_front_protracted",
                    block,
                )
        self.assertEqual(len(occupied), len(set(self.grid.values())))

    def test_vad_optional_depth_is_outcome_specific_and_capstone_neutral(self) -> None:
        optional = set(VAD_OPTIONAL_WARTIME_FOCUSES)
        self.assertEqual(
            optional & _prerequisites(self.blocks["VAD_balance_council_and_command"]),
            set(),
        )
        positions: set[tuple[int, int]] = set()
        for focus_id in VAD_OPTIONAL_WARTIME_FOCUSES:
            with self.subTest(focus_id=focus_id):
                block = self.blocks[focus_id]
                self.assertEqual(_phase_flags(block), ACTIVE_PHASE_FLAGS)
                self.assertIn("tag = VAD", block)
                self.assertNotIn("declare_war_on", block)
                self.assertNotIn("ADISCORD_vorkerland_tva_field_directorate_3", block)
                position = self.grid[focus_id]
                self.assertEqual(position, VAD_OPTIONAL_POSITIONS[focus_id])
                self.assertNotIn(position, positions)
                positions.add(position)
                self.assertEqual(_focus_cost(block), VAD_OPTIONAL_COSTS[focus_id])

        for outcome_index, expected in enumerate(VAD_OPTIONAL_OUTCOME_FOCUSES):
            with self.subTest(outcome=outcome_index + 1):
                eligible, reachable = _reachable_vad_optional_outcome(
                    self.blocks, outcome_index
                )
                self.assertEqual(eligible, set(expected))
                self.assertEqual(reachable, set(expected))
                self.assertEqual(len(reachable), (6, 8, 3, 3)[outcome_index])

    def test_wkr_southern_corridor_repairs_live_uncapped_states(self) -> None:
        corridor = self.blocks["WKR_secure_the_southern_corridor"]
        rewards = _blocks(corridor, "completion_reward")
        self.assertEqual(len(rewards), 1)
        reward = rewards[0]
        for state_id in (200, 201):
            with self.subTest(state_id=state_id):
                self.assertEqual(
                    reward.count(
                        f"limit = {{ owns_state = {state_id} controls_state = {state_id} }}"
                    ),
                    1,
                )
                self.assertEqual(
                    reward.count(
                        f"{state_id} = {{ add_building_construction = "
                        "{ type = infrastructure level = 1 instant_build = yes } }"
                    ),
                    1,
                )
        self.assertNotIn(
            "32 = { add_building_construction = { type = infrastructure",
            reward,
        )
        self.assertNotIn(
            "33 = { add_building_construction = { type = infrastructure",
            reward,
        )
        self.assertEqual(
            reward.count("type = infrastructure level = 1 instant_build = yes"),
            2,
        )

    def test_vad_late_war_bridge_is_compact_bounded_and_available_between_wars(
        self,
    ) -> None:
        self.assertEqual(len(VAD_LATE_WAR_BRIDGE_FOCUSES), 4)
        for focus_id in VAD_LATE_WAR_BRIDGE_FOCUSES:
            with self.subTest(focus_id=focus_id):
                block = self.blocks[focus_id]
                self.assertEqual(_phase_flags(block), LATE_WAR_PHASE_FLAGS)
                allow = _blocks(block, "allow_branch")
                available = _blocks(block, "available")
                self.assertEqual(len(allow), 1)
                self.assertEqual(len(available), 1)
                self.assertEqual(_phase_flags(allow[0]), LATE_WAR_PHASE_FLAGS)
                self.assertEqual(_phase_flags(available[0]), LATE_WAR_PHASE_FLAGS)
                self.assertEqual(
                    set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow[0])),
                    {"VAD"},
                )
                self.assertIn("is_subject = no", available[0])
                self.assertIn("NOT = { has_capitulated = yes }", available[0])
                self.assertNotIn("has_war", available[0])

                position = self.grid[focus_id]
                self.assertEqual(position, VAD_LATE_WAR_BRIDGE_POSITIONS[focus_id])
                colliding = [
                    other_id
                    for other_id, cell in self.grid.items()
                    if other_id != focus_id
                    and cell == position
                    and lifecycle_tree(other_id) == lifecycle_tree(focus_id)
                ]
                self.assertEqual(colliding, [])
                self.assertEqual(
                    _focus_cost(block), VAD_LATE_WAR_BRIDGE_COSTS[focus_id]
                )
                self.assertEqual(
                    _prerequisite_groups(block),
                    VAD_LATE_WAR_BRIDGE_PREREQUISITES[focus_id],
                )
                rewards = _blocks(block, "completion_reward")
                self.assertEqual(len(rewards), 1)
                for token in VAD_LATE_WAR_BRIDGE_REWARDS[focus_id]:
                    self.assertEqual(_plan_reward_contract(rewards[0]).count(token), 1)
                self.assertNotIn("ADISCORD_vorkerland_solar_terminal_", block)
                self.assertNotIn("declare_war_on", block)

        supply = self.blocks["VAD_restore_eastern_supply_corridors"]
        self.assertIn("limit = { owns_state = 107 controls_state = 107 }", supply)
        self.assertEqual(
            supply.count("type = infrastructure level = 1 instant_build = yes"),
            1,
        )
        workshops = self.blocks["VAD_convert_emergency_workshops"]
        self.assertIn("limit = { owns_state = 121 controls_state = 121 }", workshops)
        self.assertEqual(
            workshops.count("add_extra_state_shared_building_slots = 1"), 1
        )
        self.assertEqual(
            workshops.count("type = arms_factory level = 1 instant_build = yes"),
            1,
        )
        self.assertEqual(
            _prerequisite_groups(self.blocks["VAD_reconcile_emergency_district_rolls"]),
            (
                frozenset(
                    {
                        "VAD_preposition_restoration_columns",
                        "VAD_balance_council_and_command",
                    }
                ),
            ),
        )
        settlement_prerequisites = _prerequisite_groups(
            self.blocks["VAD_define_the_solar_settlement"]
        )
        self.assertIn(
            frozenset({"VAD_preposition_restoration_columns"}),
            settlement_prerequisites,
        )
        self.assertNotIn(
            "VAD_balance_council_and_command",
            set().union(*settlement_prerequisites),
        )

    def test_vad_depth_stages_timed_spirits_and_exclusive_protocols(self) -> None:
        for focus_id, (idea_id, days) in VAD_WARTIME_TIMED_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                self.assertEqual(
                    _plan_reward_contract(self.blocks[focus_id]).count(
                        f"add_timed_idea = {{ idea = {idea_id} days = {days} }}"
                    ),
                    1,
                )
                definition = _blocks(self.collapse_ideas, idea_id)
                self.assertEqual(len(definition), 1)
                self.assertIn("removal_cost = -1", definition[0])

        for focus_id, (own_idea, other_idea) in VAD_PERMANENT_PROTOCOL_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                block = self.blocks[focus_id]
                self.assertEqual(block.count(f"add_ideas = {own_idea}"), 1)
                for prior in (
                    "ADISCORD_vorkerland_vad_imperial_chancery",
                    "ADISCORD_vorkerland_vad_imperial_registers",
                    "ADISCORD_vorkerland_vad_field_commandantures",
                    other_idea,
                ):
                    self.assertEqual(block.count(f"remove_ideas = {prior}"), 1)

        strengthened = {
            "VAD_inventory_eastern_works": (
                "type = support_equipment amount = 200 producer = VAD",
                "bonus = 0.50 uses = 1 category = industry",
            ),
            "VAD_standardize_district_logistics": (
                "type = support_equipment amount = 60 producer = VAD",
                "ADISCORD_vorkerland_vad_standardized_logistics days = 70",
            ),
            "VAD_reconstitute_district_guard": (
                "type = infantry_equipment_0 amount = 5400 producer = VAD",
                "type = support_equipment amount = 100 producer = VAD",
            ),
        }
        for focus_id, tokens in strengthened.items():
            for token in tokens:
                self.assertIn(
                    token, re.sub(r"\s+", " ", _plan_reward_contract(self.blocks[focus_id]))
                )

    def test_tva_optional_depth_is_six_focus_outcome_specific_and_capstone_neutral(
        self,
    ) -> None:
        optional = set(TVA_OPTIONAL_WARTIME_FOCUSES)
        self.assertEqual(
            optional & _prerequisites(self.blocks["TVA_close_operational_loop"]),
            set(),
        )
        positions: set[tuple[int, int]] = set()
        for focus_id in TVA_OPTIONAL_WARTIME_FOCUSES:
            with self.subTest(focus_id=focus_id):
                block = self.blocks[focus_id]
                self.assertEqual(_phase_flags(block), ACTIVE_PHASE_FLAGS)
                self.assertIn("tag = TVA", block)
                if focus_id != "TVA_open_the_remaining_fronts":
                    self.assertIn("has_government = technocracy", block)
                    self.assertIn("character = TVA_Dorian_Worx", block)
                else:
                    allow = _allow_branch(block)
                    self.assertNotIn("has_government = technocracy", allow)
                    self.assertNotIn("character = TVA_Dorian_Worx", allow)
                self.assertNotIn("declare_war_on", block)
                self.assertNotIn("ADISCORD_vorkerland_tva_field_directorate_3", block)
                self.assertNotIn("phase_worx_client_administration", block)
                self.assertNotIn("phase_worx_fragmentation", block)
                position = self.grid[focus_id]
                self.assertEqual(position, TVA_OPTIONAL_POSITIONS[focus_id])
                self.assertNotIn(position, positions)
                positions.add(position)
                self.assertEqual(_focus_cost(block), TVA_OPTIONAL_COSTS[focus_id])

        for outcome_index, expected in enumerate(TVA_OPTIONAL_OUTCOME_FOCUSES):
            with self.subTest(outcome=outcome_index + 1):
                reachable = _reachable_tva_optional_outcome(self.blocks, outcome_index)
                self.assertEqual(reachable, set(expected))
                self.assertEqual(len(reachable), 6)
                self.assertIn(
                    sum(TVA_OPTIONAL_COSTS[focus_id] for focus_id in reachable),
                    {18, 19},
                )

    def test_tva_optional_depth_uses_bounded_spirits_event_and_level_two_ceiling(
        self,
    ) -> None:
        for focus_id, (idea_id, days) in TVA_OPTIONAL_TIMED_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                self.assertEqual(
                    _plan_reward_contract(self.blocks[focus_id]).count(
                        f"add_timed_idea = {{ idea = {idea_id} days = {days} }}"
                    ),
                    1,
                )
                definition = _blocks(self.collapse_ideas, idea_id)
                self.assertEqual(len(definition), 1)
                self.assertIn("allowed = { always = no }", definition[0])
                self.assertIn("removal_cost = -1", definition[0])

        cross_validate = self.blocks["TVA_cross_validate_trial_logs"]
        self.assertEqual(
            cross_validate.count(
                "country_event = { id = ADISCORD_vorkerland_claimant.24 hours = 1 }"
            ),
            1,
        )
        iteration = self.blocks["TVA_authorize_iteration_two"]
        self.assertEqual(
            _plan_reward_contract(iteration).count(
                "add_timed_idea = { idea = ADISCORD_vorkerland_worx_second_protocol days = 120 }"
            ),
            1,
        )
        self.assertNotIn("field_directorate_3", iteration)

    def test_vad_solar_settlement_uses_existing_bounded_retry_lane(self) -> None:
        terminal = self.blocks["VAD_define_the_solar_settlement"]
        self.assertIn(
            "country_event = { id = ADISCORD_vorkerland_claimant.14 hours = 1 }",
            terminal,
        )
        self.assertNotIn("declare_war_on", terminal)
        available = _blocks(terminal, "available")
        self.assertEqual(len(available), 1)
        fallback = _blocks(available[0], "OR")
        self.assertEqual(len(fallback), 1)
        for token in (
            "has_global_flag = ADISCORD_vorkerland_solar_terminal_verified",
            "ADISCORD_vorkerland_solar_terminal_sol = yes",
            "ADISCORD_vorkerland_solar_terminal_sra = yes",
            "ADISCORD_vorkerland_solar_terminal_csl = yes",
        ):
            self.assertEqual(fallback[0].count(token), 1)
        reward = _blocks(terminal, "completion_reward")
        self.assertEqual(len(reward), 1)
        recorder_call = "ADISCORD_vorkerland_record_regional_diplomacy_outcomes = yes"
        policy_event = (
            "country_event = { id = ADISCORD_vorkerland_claimant.14 hours = 1 }"
        )
        self.assertEqual(reward[0].count(recorder_call), 1)
        self.assertLess(reward[0].find(recorder_call), reward[0].find(policy_event))

        outcome_recorders = _blocks(
            self.diplomacy_effects,
            "ADISCORD_vorkerland_record_regional_diplomacy_outcomes",
        )
        self.assertEqual(len(outcome_recorders), 1)
        outcome_recorder = outcome_recorders[0]
        for suffix in ("sol", "sra", "csl"):
            self.assertEqual(
                outcome_recorder.count(
                    f"ADISCORD_vorkerland_solar_terminal_{suffix} = yes"
                ),
                1,
            )
            self.assertEqual(
                outcome_recorder.count(
                    f"set_global_flag = ADISCORD_vorkerland_solar_winner_{suffix}"
                ),
                1,
            )
        self.assertEqual(
            outcome_recorder.count(
                "NOT = { has_global_flag = ADISCORD_vorkerland_solar_terminal_verified }"
            ),
            3,
        )
        self.assertEqual(
            outcome_recorder.count(
                "set_global_flag = ADISCORD_vorkerland_solar_terminal_verified"
            ),
            3,
        )
        event = next(
            block
            for block in _blocks(self.claimant_events, "country_event")
            if "id = ADISCORD_vorkerland_claimant.14" in block
        )
        self.assertEqual(len(_blocks(event, "option")), 2)
        self.assertEqual(
            event.count("ADISCORD_vorkerland_offer_vad_sol_alliance = yes"), 2
        )
        self.assertEqual(
            event.count("ADISCORD_vorkerland_reserve_vad_solar_intervention = yes"),
            2,
        )
        self.assertEqual(
            event.count("ADISCORD_vorkerland_attempt_vad_solar_intervention = yes"),
            2,
        )
        self.assertNotIn("declare_war_on", event)
        verify = _blocks(
            self.diplomacy_effects,
            "ADISCORD_vorkerland_verify_vad_solar_intervention",
        )[0]
        self.assertEqual(
            verify.count(
                "set_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_retry"
            ),
            1,
        )
        self.assertEqual(
            verify.count(
                "country_event = { id = ADISCORD_vorkerland_diplomacy.9 days = 1 }"
            ),
            1,
        )

    def test_wkr_ai_plans_reach_capstone_before_solyarino(self) -> None:
        expected = {
            "ADISCORD_vorkerland_wkr_pragmatist_core_plan": (
                "WKR_presidential_course",
                (
                    "WKR_affirm_worker_mandate",
                    "WKR_convene_front_soviets",
                    "WKR_organize_factory_battalions",
                    "WKR_put_railways_under_councils",
                    "WKR_train_shopfloor_officers",
                    "WKR_form_revolutionary_supply_commission",
                    "WKR_open_free_republics_channel",
                    "WKR_authorize_retreat_levies",
                    "WKR_reopen_collective_workshops",
                    "WKR_publish_emergency_constitution",
                    "WKR_coordinate_counterattack_cells",
                    "WKR_stockpile_interchange_reserves",
                    "WKR_settle_front_authority",
                    "WKR_republic_fights_as_one",
                ),
            ),
            "ADISCORD_vorkerland_wkr_utilitarian_core_plan": (
                "WKR_executive_course",
                (
                    "WKR_affirm_worker_mandate",
                    "WKR_empower_front_executive",
                    "WKR_bind_workshops_to_directive",
                    "WKR_put_railways_under_councils",
                    "WKR_form_revolutionary_supply_commission",
                    "WKR_reopen_collective_workshops",
                    "WKR_organize_factory_battalions",
                    "WKR_train_shopfloor_officers",
                    "WKR_authorize_retreat_levies",
                    "WKR_coordinate_counterattack_cells",
                    "WKR_stockpile_interchange_reserves",
                    "WKR_settle_front_authority",
                    "WKR_republic_fights_as_one",
                ),
            ),
        }
        for plan_id, (leader, expected_focuses) in expected.items():
            with self.subTest(plan_id=plan_id):
                plan = _blocks(self.wkr_ai_plans, plan_id)[0]
                focus_list = _blocks(plan, "ai_national_focuses")[0]
                actual = tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list))
                self.assertEqual(actual, expected_focuses)
                self.assertEqual(actual[-1], "WKR_republic_fights_as_one")
                self.assertIn(f"{leader} = yes", _blocks(plan, "enable")[0])
                self.assertIn(f"{leader} = no", _blocks(plan, "abort")[0])
                self.assertIn(
                    "NOT = { has_country_flag = ADISCORD_vorkerland_focus_wkr_central_war_unlocked }",
                    plan,
                )
                self.assertIn("weight = { factor = 3 }", plan)

        solarino = _blocks(
            self.wkr_ai_plans, "ADISCORD_vorkerland_wkr_solyarino_operation_plan"
        )[0]
        focus_list = _blocks(solarino, "ai_national_focuses")[0]
        self.assertEqual(
            tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list)),
            ("WKR_intervene_in_solyarino",),
        )
        self.assertIn(
            "has_country_flag = ADISCORD_vorkerland_focus_wkr_central_war_unlocked",
            solarino,
        )
        self.assertIn("weight = { factor = 5 }", solarino)
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
            solarino,
        )
        for obsolete_blocker in (
            "ADISCORD_vorkerland_focus_central_showdown_requested",
            "ADISCORD_vorkerland_showdown_queue_initialized",
            "ADISCORD_vorkerland_central_showdown_started",
            "ADISCORD_vorkerland_vad_sol_alliance_accepted",
        ):
            self.assertNotIn(obsolete_blocker, solarino)

    def test_vad_ai_plans_traverse_core_then_outcome_depth(self) -> None:
        expected = {
            "ADISCORD_vorkerland_vad_vlad_depth_plan": (
                "VAD_restore_prefectural_courts",
                "VAD_issue_crown_mobilization_warrants",
                "VAD_turn_the_chancery_into_a_war_cabinet",
                "VAD_invite_sol_delegation",
                "VAD_dispatch_solland_liaison_mission",
                "VAD_map_the_solar_corridors",
                "VAD_preposition_restoration_columns",
                "VAD_define_the_solar_settlement",
                *VAD_LATE_WAR_BRIDGE_FOCUSES,
            ),
            "ADISCORD_vorkerland_vad_joint_depth_plan": (
                "VAD_elect_district_commissars",
                "VAD_merge_guard_and_worker_rolls",
                "VAD_sign_the_dual_authority_protocol",
                "VAD_invite_sol_delegation",
                "VAD_dispatch_solland_liaison_mission",
                "VAD_map_the_solar_corridors",
                "VAD_preposition_restoration_columns",
                "VAD_define_the_solar_settlement",
                *VAD_LATE_WAR_BRIDGE_FOCUSES,
            ),
        }
        for plan_id, expected_focuses in expected.items():
            with self.subTest(plan_id=plan_id):
                plan = _blocks(self.vad_ai_plans, plan_id)[0]
                focus_list = _blocks(plan, "ai_national_focuses")[0]
                actual = tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list))
                self.assertEqual(actual, expected_focuses)
                self.assertEqual(
                    actual[-len(VAD_LATE_WAR_BRIDGE_FOCUSES) :],
                    VAD_LATE_WAR_BRIDGE_FOCUSES,
                )
                self.assertIn(
                    "has_country_flag = ADISCORD_vorkerland_focus_vad_central_war_unlocked",
                    plan,
                )
                self.assertIn("weight = { factor = 4 }", plan)
                enable = _blocks(plan, "enable")
                self.assertEqual(len(enable), 1)
                self.assertNotIn(
                    "ADISCORD_vorkerland_wkr_solyarino_intervention_active",
                    enable[0],
                )

    def test_tva_ai_plans_select_each_metric_trial_depth_route(self) -> None:
        core = _blocks(
            self.tva_ai_plans, "ADISCORD_vorkerland_tva_experimental_core_plan"
        )
        self.assertEqual(len(core), 1)
        self.assertIn("weight = { factor = 3 }", core[0])
        for plan_id, metric_flag, trial_flag, expected_focuses in TVA_OPTIONAL_AI_PLANS:
            with self.subTest(plan_id=plan_id):
                definitions = _blocks(self.tva_ai_plans, plan_id)
                self.assertEqual(len(definitions), 1)
                plan = definitions[0]
                focus_list = _blocks(plan, "ai_national_focuses")[0]
                actual = tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list))
                self.assertEqual(actual, expected_focuses)
                self.assertEqual(len(actual), 6)
                self.assertIn(f"has_country_flag = {metric_flag}", plan)
                self.assertIn(f"has_country_flag = {trial_flag}", plan)
                self.assertIn("weight = { factor = 5 }", plan)

    def test_each_wartime_outcome_reaches_fourteen_completable_definitions(
        self,
    ) -> None:
        for tag, exclusions in WARTIME_OUTCOME_EXCLUSIONS.items():
            route = set(WARTIME_ROUTE_FOCUSES[tag])
            capstone = CENTRAL_CAPSTONES[tag][0]
            self.assertEqual(
                len(WARTIME_OUTCOME_FALSE_GATE_TOKENS[tag]), len(exclusions)
            )
            for outcome_index, excluded in enumerate(exclusions):
                with self.subTest(tag=tag, outcome=outcome_index + 1):
                    expected = route - set(excluded)
                    eligible, reachable = _reachable_wartime_outcome(
                        self.blocks, tag, outcome_index
                    )
                    self.assertEqual(eligible, expected)
                    self.assertEqual(reachable, expected)
                    self.assertEqual(len(reachable), 14)
                    self.assertIn(capstone, reachable)

    def test_outcome_reachability_rejects_the_previous_softlocks(self) -> None:
        regressions = (
            (
                "WKR",
                0,
                "WKR_reopen_collective_workshops",
                "has_country_leader = { character = WRK_Anton_Bagley ruling_only = yes }",
            ),
            (
                "VAD",
                0,
                "VAD_proclaim_joint_charter",
                "has_country_leader = { character = TVA_Dorian_Worx ruling_only = yes }",
            ),
            (
                "VAD",
                1,
                "VAD_reconstitute_district_guard",
                "has_country_leader = { character = WRK_Vlad_Petrichev ruling_only = yes }",
            ),
            (
                "VAD",
                0,
                "VAD_inventory_eastern_works",
                "has_country_leader = { character = WRK_VAD_Joint_Council ruling_only = yes }",
            ),
        )
        for tag, outcome_index, focus_id, bad_gate in regressions:
            with self.subTest(tag=tag, outcome=outcome_index + 1, focus_id=focus_id):
                mutated = dict(self.blocks)
                mutated[focus_id] = mutated[focus_id].replace(
                    "available = {", f"available = {{\n\t\t\t{bad_gate}", 1
                )
                eligible, reachable = _reachable_wartime_outcome(
                    mutated, tag, outcome_index
                )
                self.assertNotIn(focus_id, eligible)
                self.assertNotIn(CENTRAL_CAPSTONES[tag][0], reachable)

    def test_wartime_layouts_use_unique_compact_coordinates(self) -> None:
        for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
            positions = [self.grid[focus_id] for focus_id in focus_ids]
            with self.subTest(tag=tag):
                self.assertEqual(len(positions), len(set(positions)))
                # Seven spine steps at the two-row pitch the canvas is drawn on.
                self.assertLessEqual(
                    max(y for _x, y in positions) - min(y for _x, y in positions), 14
                )

    def test_no_two_visible_focuses_are_drawn_on_the_same_grid_cell(self) -> None:
        occupied: dict[tuple[int, int], list[str]] = {}
        for focus_id in sorted(self.blocks):
            cell = self.grid.get(focus_id)
            with self.subTest(focus_id=focus_id):
                self.assertIsNotNone(cell, "focus position must resolve")
                for other in occupied.get(cell, []):
                    self.assertFalse(_can_share_view(focus_id, other), f"{focus_id} collides with {other} at {cell}")
            occupied.setdefault(cell, []).append(focus_id)
        self.assertEqual(sum(map(len, occupied.values())), len(self.blocks))

    def test_layout_uses_one_absolute_anchor_per_lifecycle_block(self) -> None:
        absolute = sorted(
            focus_id
            for focus_id, block in self.blocks.items()
            if _relative_anchor(block) is None
        )
        self.assertEqual(absolute, sorted(LAYOUT_ANCHORS))
        for focus_id, expected in LAYOUT_ANCHORS.items():
            with self.subTest(focus_id=focus_id):
                self.assertEqual(self.grid[focus_id], expected)

    def test_every_branch_hangs_off_a_real_prerequisite_and_is_drawn_below_it(
        self,
    ) -> None:
        for focus_id in sorted(self.blocks):
            block = self.blocks[focus_id]
            anchor = _relative_anchor(block)
            if anchor is None:
                continue
            prerequisites = {
                token for group in _prerequisite_groups(block) for token in group
            }
            with self.subTest(focus_id=focus_id):
                self.assertIn(
                    anchor,
                    prerequisites,
                    "a branch may only be anchored to a focus that gates it",
                )
                self.assertGreater(self.grid[focus_id][1], self.grid[anchor][1])

    def test_every_relative_anchor_is_defined_before_its_consumer(self) -> None:
        offsets = {
            match.group(1): match.start()
            for match in re.finditer(
                r"(?ms)^\s*focus\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_]+)",
                self.source,
            )
        }
        for focus_id, block in self.blocks.items():
            anchor = _relative_anchor(block)
            if anchor is not None:
                self.assertIn(anchor, offsets)
                self.assertLess(offsets[anchor], offsets[focus_id], (focus_id, anchor))

    def test_reference_order_validator_reports_forward_and_missing_anchors(
        self,
    ) -> None:
        source = """
focus = {
    id = TEST_forward_consumer
    relative_position_id = TEST_late_anchor
}
focus = {
    id = TEST_missing_consumer
    relative_position_id = TEST_missing_anchor
}
focus = {
    id = TEST_late_anchor
}
"""
        self.assertEqual(
            _check_focus_reference_order(source, focus_blocks(source)),
            [
                "TEST_forward_consumer references TEST_late_anchor before its definition",
                "TEST_missing_consumer references missing relative anchor TEST_missing_anchor",
            ],
        )

    def test_every_focus_declares_supported_search_filters(self) -> None:
        for focus_id in sorted(self.blocks):
            filters = _blocks(self.blocks[focus_id], "search_filters")
            with self.subTest(focus_id=focus_id):
                self.assertEqual(len(filters), 1)
                tokens = re.findall(r"\b(FOCUS_FILTER_[A-Z_]+)\b", filters[0])
                self.assertTrue(tokens)
                self.assertLessEqual(len(tokens), 3)
                self.assertFalse(set(tokens) - SUPPORTED_SEARCH_FILTERS)

    def test_every_focus_stays_inside_its_documented_band(self) -> None:
        for focus_id in sorted(self.blocks):
            band = _layout_band(focus_id, self.blocks[focus_id])
            (x_low, x_high), (y_low, y_high) = LAYOUT_BANDS[band]
            x, y = self.grid[focus_id]
            with self.subTest(focus_id=focus_id, band=band):
                self.assertTrue(
                    x_low <= x <= x_high, f"{focus_id} x={x} outside {band}"
                )
                self.assertTrue(
                    y_low <= y <= y_high, f"{focus_id} y={y} outside {band}"
                )

    def test_mutually_exclusive_siblings_share_a_row(self) -> None:
        for focus_id in sorted(self.blocks):
            block = self.blocks[focus_id]
            for other in re.findall(
                r"mutually_exclusive = \{[^}]*focus = ([A-Za-z0-9_]+)", block
            ):
                if other not in self.grid:
                    continue
                with self.subTest(pair=(focus_id, other)):
                    self.assertEqual(
                        self.grid[focus_id][1],
                        self.grid[other][1],
                        "an exclusive fork must read as one row of alternatives",
                    )

    def test_showdown_expansion_has_exact_geometry_graph_and_live_war_gate(
        self,
    ) -> None:
        opponents = {
            "WKR": {
                "EYR",
                "EGC",
                "RIV",
                "REV",
                "YOR",
                "NDN",
                "SWB",
                "VHV",
                "OSV",
                "VAD",
                "TVA",
            },
            "VAD": {
                "EYR",
                "EGC",
                "RIV",
                "REV",
                "YOR",
                "NDN",
                "SWB",
                "VHV",
                "OSV",
                "WKR",
                "TVA",
            },
            "TVA": {
                "EYR",
                "EGC",
                "RIV",
                "REV",
                "YOR",
                "NDN",
                "SWB",
                "VHV",
                "OSV",
                "WKR",
                "VAD",
            },
        }
        for tag, focus_ids in SHOWDOWN_FOCUSES.items():
            positions = set()
            for focus_id in focus_ids:
                block = self.blocks[focus_id]
                position = self.grid[focus_id]
                available = _blocks(block, "available")[0]
                with self.subTest(tag=tag, focus_id=focus_id):
                    self.assertEqual(position, SHOWDOWN_POSITIONS[focus_id])
                    self.assertNotIn(position, positions)
                    positions.add(position)
                    self.assertEqual(_focus_cost(block), SHOWDOWN_COSTS[focus_id])
                    self.assertEqual(
                        _prerequisite_groups(block),
                        SHOWDOWN_PREREQUISITES[focus_id],
                    )
                    self.assertIn(
                        "tooltip = ADISCORD_vorkerland_showdown_focus_live_war_tt",
                        available,
                    )
                    self.assertEqual(
                        set(
                            re.findall(
                                r"\bhas_war_with\s*=\s*([A-Z0-9]{3})\b",
                                available,
                            )
                        ),
                        opponents[tag],
                    )

    def test_showdown_expansion_ideas_are_bounded_and_all_earned(self) -> None:
        expansion_focuses = "\n".join(
            self.blocks[focus_id]
            for focus_ids in SHOWDOWN_FOCUSES.values()
            for focus_id in focus_ids
        )
        expansion_focuses += "\n" + "\n".join(
            self.blocks[focus_id]
            for focus_id in (
                *PREWAR_WRK_EXPANSION_FOCUSES,
                *PREWAR_VAD_EXPANSION_FOCUSES,
                *WKR_VARIANT_FOCUSES,
                *VAD_VARIANT_FOCUSES,
                *TVA_VARIANT_FOCUSES,
                *DEPTH_FOCUSES,
            )
        )
        for idea_id in FOCUS_EXPANSION_IDEAS:
            definitions = _blocks(self.focus_expansion_ideas, idea_id)
            with self.subTest(idea_id=idea_id):
                self.assertEqual(len(definitions), 1)
                self.assertIn("allowed = { always = no }", definitions[0])
                self.assertIn("allowed_civil_war = { always = yes }", definitions[0])
                self.assertIn("removal_cost = -1", definitions[0])
                self.assertIn("ai_will_do = { factor = 0 }", definitions[0])
                self.assertIn(idea_id, _plan_reward_contract(expansion_focuses))
        for forbidden in (
            "activate_mission",
            "declare_war_on",
            "create_wargoal",
            "annex_country",
            "white_peace",
            "transfer_state",
            "every_country",
            "on_daily",
            "on_weekly",
            "on_monthly",
        ):
            self.assertNotIn(forbidden, expansion_focuses)

    def test_wkr_night_freight_upgrades_only_nonmaxed_southern_corridors(self) -> None:
        reward = _blocks(
            self.blocks["WKR_reopen_night_freight_corridors"],
            "completion_reward",
        )[0]
        for state_id in (200, 201):
            with self.subTest(state_id=state_id):
                self.assertIn(f"owns_state = {state_id}", reward)
                self.assertIn(f"controls_state = {state_id}", reward)
                self.assertIn(f"{state_id} = {{ infrastructure < 5 }}", reward)
                self.assertIn(
                    f"{state_id} = {{ add_building_construction = "
                    "{ type = infrastructure level = 1 instant_build = yes } }",
                    reward,
                )
        self.assertNotRegex(reward, r"\b(?:32|33)\b")
        self.assertEqual(
            reward.count("type = support_equipment amount = 50 producer = WKR"),
            1,
        )

    def test_showdown_ai_plans_follow_each_authored_outcome(self) -> None:
        sources = {
            "WKR": self.wkr_ai_plans,
            "VAD": self.vad_ai_plans,
            "TVA": self.tva_ai_plans,
        }
        for tag, plans in SHOWDOWN_AI_PLANS.items():
            for plan_id, expected_focuses in plans.items():
                definitions = _blocks(sources[tag], plan_id)
                with self.subTest(tag=tag, plan_id=plan_id):
                    self.assertEqual(len(definitions), 1)
                    plan = definitions[0]
                    focus_list = _blocks(plan, "ai_national_focuses")[0]
                    actual = tuple(
                        re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list)
                    )
                    self.assertEqual(actual, expected_focuses)
                    self.assertIn(
                        "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
                        plan,
                    )
                    self.assertIn(
                        "has_global_flag = ADISCORD_vorkerland_central_showdown_started",
                        plan,
                    )
                    self.assertIn(
                        "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
                        plan,
                    )
                    self.assertIn("has_war = yes", plan)
                    self.assertIn("weight = { factor = 5 }", plan)

    def test_real_claimant_identities_gate_each_asymmetric_political_route(
        self,
    ) -> None:
        """Structural gating lives in allow_branch, volatile identity in available.

        Entry focuses expose the choice before its government exists. Later
        descendants may use the fixed mandate for visibility, but cached leader
        identity belongs in availability so a transient mismatch cannot remove
        both branches and their convergence from the tree.
        """

        for focus_ids, branch_tokens, identity_tokens in WARTIME_ROUTE_IDENTITIES:
            for focus_id in focus_ids:
                block = self.blocks[focus_id]
                allow = _blocks(block, "allow_branch")[0]
                available = "\n".join(_blocks(block, "available"))
                expected_branch = () if focus_id in VAD_MANDATE_ENTRIES else branch_tokens
                expected_identity = VAD_MANDATE_ENTRIES.get(focus_id, identity_tokens)
                for token in expected_branch:
                    with self.subTest(focus_id=focus_id, token=token):
                        self.assertIn(token, allow)
                for token in expected_identity:
                    with self.subTest(focus_id=focus_id, token=token):
                        self.assertIn(token, available)
                        self.assertNotIn(token, allow)

    def test_each_claimant_convergence_accepts_either_mandate(self) -> None:
        for convergence_id, left_index, right_index in WARTIME_ROUTE_CONVERGENCE:
            with self.subTest(convergence_id=convergence_id):
                left = WARTIME_ROUTE_IDENTITIES[left_index]
                right = WARTIME_ROUTE_IDENTITIES[right_index]
                for entry, other in ((left[0][0], right[0][0]), (right[0][0], left[0][0])):
                    self.assertIn(f"focus = {other}", _blocks(self.blocks[entry], "mutually_exclusive")[0])
                if convergence_id == "WKR_settle_front_authority":
                    self.assertEqual((left[1], right[1]), ((), ()))
                else:
                    self.assertEqual(len(left[1]), 1)
                    self.assertEqual(len(right[1]), 1)
                    left_token, right_token = left[1][0], right[1][0]
                    self.assertTrue(
                        f"NOT = {{ {left_token} }}" == right_token
                        or f"NOT = {{ {right_token} }}" == left_token,
                        (left_token, right_token),
                    )
                groups = _prerequisite_groups(self.blocks[convergence_id])
                self.assertTrue(
                    any(
                        group & set(left[0]) and group & set(right[0])
                        for group in groups
                    )
                )

    def test_vad_mandate_exclusion_line_has_no_focus_in_its_corridor(self) -> None:
        grid = resolved_positions(self.blocks)
        left, right = (grid[name] for name in VAD_MANDATE_ENTRIES)
        self.assertEqual(left[1], right[1])
        low, high = sorted((left[0], right[0]))
        blockers = [name for name, (x, y) in grid.items()
                    if y == left[1] and low < x < high
                    and _can_share_view("VAD_form_field_commandantures", name)]
        self.assertEqual(blockers, [])

    def test_every_claimant_offers_two_variant_settlements(self) -> None:
        self.assertEqual(len(VARIANT_BRANCHES), 6)
        self.assertEqual(
            Counter(branch["tag"] for branch in VARIANT_BRANCHES),
            Counter({"WKR": 2, "VAD": 2, "TVA": 2}),
        )
        declared = [
            focus_id for branch in VARIANT_BRANCHES for focus_id in branch["focuses"]
        ]
        self.assertEqual(len(declared), len(set(declared)))
        self.assertEqual(
            set(declared),
            {*WKR_VARIANT_FOCUSES, *VAD_VARIANT_FOCUSES, *TVA_VARIANT_FOCUSES},
        )
        self.assertTrue(set(declared) <= set(self.blocks))
        positions = [
            position for branch in VARIANT_BRANCHES for position in branch["positions"]
        ]
        self.assertEqual(len(positions), len(set(positions)))

    def test_variant_chains_are_costed_and_chained_from_their_political_line(
        self,
    ) -> None:
        for branch in VARIANT_BRANCHES:
            root, program, settlement = branch["focuses"]
            with self.subTest(variant=f"{branch['tag']}_{branch['key']}"):
                expected = {branch["root_prerequisite"]}
                if root == "WKR_govern_by_delivered_results":
                    expected.add("WKR_authorize_normative_command")
                self.assertEqual(_prerequisites(self.blocks[root]), expected)
                self.assertEqual(_prerequisites(self.blocks[program]), {root})
                self.assertEqual(_prerequisites(self.blocks[settlement]), {program})
                self.assertEqual(
                    tuple(
                        _focus_cost(self.blocks[focus_id])
                        for focus_id in branch["focuses"]
                    ),
                    branch["costs"],
                )
                for focus_id, cell in zip(branch["focuses"], branch["positions"]):
                    self.assertEqual(self.grid[focus_id], cell)

    def test_variant_roots_are_mutually_exclusive_and_flag_their_choice(self) -> None:
        for branch in VARIANT_BRANCHES:
            root = branch["focuses"][0]
            sibling = branch["sibling"]
            with self.subTest(variant=f"{branch['tag']}_{branch['key']}"):
                self.assertIn(sibling, _mutually_exclusive_focuses(self.blocks[root]))
                self.assertIn(root, _mutually_exclusive_focuses(self.blocks[sibling]))
                self.assertIn(
                    f"set_country_flag = {branch['variant_flag']}", self.blocks[root]
                )
                for other in VARIANT_BRANCHES:
                    if other["variant_flag"] == branch["variant_flag"]:
                        continue
                    self.assertNotIn(
                        f"set_country_flag = {other['variant_flag']}", self.blocks[root]
                    )

    def test_variant_focuses_gate_identity_outside_allow_branch(self) -> None:
        for branch in VARIANT_BRANCHES:
            for focus_id in branch["focuses"]:
                block = self.blocks[focus_id]
                allow = _blocks(block, "allow_branch")[0]
                available = "\n".join(_blocks(block, "available"))
                with self.subTest(focus_id=focus_id):
                    self.assertIn(f"tag = {branch['tag']}", allow)
                    self.assertEqual(_phase_flags(block), ACTIVE_PHASE_FLAGS)
                    self.assertIn("cancel_if_invalid = yes", block)
                    self.assertIn("bypass", block)
                    self.assertIn("ai_will_do", block)
                    for token in branch["branch_tokens"]:
                        self.assertIn(token, allow)
                    for token in branch["identity_tokens"]:
                        self.assertIn(token, available)
                        self.assertNotIn(token, allow)

    def test_variant_branches_grant_distinct_national_spirits(self) -> None:
        self.assertEqual(len(VARIANT_IDEAS), 18)
        self.assertEqual(len(set(VARIANT_IDEAS)), 18)
        for branch in VARIANT_BRANCHES:
            root, program, settlement = branch["focuses"]
            first, last = branch["permanent_ideas"]
            with self.subTest(variant=f"{branch['tag']}_{branch['key']}"):
                self.assertIn(f"add_ideas = {first}", self.blocks[root])
                self.assertIn(f"idea = {branch['timed_idea']}", _plan_reward_contract(self.blocks[program]))
                self.assertIn("add_timed_idea", _plan_reward_contract(self.blocks[program]))
                self.assertIn(f"add_ideas = {last}", self.blocks[settlement])
        for idea_id in VARIANT_IDEAS:
            definitions = _blocks(self.focus_expansion_ideas, idea_id)
            with self.subTest(idea_id=idea_id):
                self.assertEqual(len(definitions), 1)
                self.assertIn("allowed = { always = no }", definitions[0])
                self.assertIn("allowed_civil_war = { always = yes }", definitions[0])
                self.assertIn("removal_cost = -1", definitions[0])
                self.assertIn("ai_will_do = { factor = 0 }", definitions[0])
                self.assertTrue(_blocks(definitions[0], "modifier"))

    def test_sibling_variants_differ_mechanically_not_cosmetically(self) -> None:
        """Two variants of one claimant must not be reskins of each other."""

        def modifiers(idea_id: str) -> dict[str, str]:
            definition = _blocks(self.focus_expansion_ideas, idea_id)[0]
            body = _blocks(definition, "modifier")[0]
            return dict(re.findall(r"(?m)^\s*([a-z_]+)\s*=\s*(-?[\d.]+)\s*$", body))

        by_tag: dict[str, list[dict]] = {}
        for branch in VARIANT_BRANCHES:
            by_tag.setdefault(branch["tag"], []).append(branch)
        for tag, branches in by_tag.items():
            left, right = branches
            left_modifiers = {
                key: value
                for idea_id in (*left["permanent_ideas"], left["timed_idea"])
                for key, value in modifiers(idea_id).items()
            }
            right_modifiers = {
                key: value
                for idea_id in (*right["permanent_ideas"], right["timed_idea"])
                for key, value in modifiers(idea_id).items()
            }
            with self.subTest(tag=tag):
                self.assertTrue(left_modifiers)
                self.assertTrue(right_modifiers)
                self.assertNotEqual(left_modifiers, right_modifiers)
                exclusive = set(left_modifiers) ^ set(right_modifiers)
                self.assertGreaterEqual(len(exclusive), 3)

    def test_variant_spirits_are_cleared_by_every_postwar_settlement(self) -> None:
        for focus_id in VARIANT_CLEANUP_FOCUSES:
            block = self.blocks[focus_id]
            for idea_id in VARIANT_PERMANENT_IDEAS:
                with self.subTest(focus_id=focus_id, idea_id=idea_id):
                    if idea_id in TVA_AGGREGATE_PREVIEWS:
                        self.assertNotIn(f"remove_ideas = {idea_id}", block)
                    else:
                        self.assertIn(f"remove_ideas = {idea_id}", block)

    def test_variant_ai_plans_follow_their_own_variant_only(self) -> None:
        sources = {
            "WKR": self.wkr_ai_plans,
            "VAD": self.vad_ai_plans,
            "TVA": self.tva_ai_plans,
        }
        for branch in VARIANT_BRANCHES:
            source = sources[branch["tag"]]
            plans = _blocks(source, branch["ai_plan"])
            with self.subTest(plan=branch["ai_plan"]):
                self.assertEqual(len(plans), 1)
                plan = plans[0]
                focus_list = _blocks(plan, "ai_national_focuses")[0]
                self.assertEqual(
                    re.findall(r"[A-Za-z0-9_]+", focus_list)[1:],
                    list(branch["focuses"]),
                )
                enable = _blocks(plan, "enable")[0]
                self.assertIn(f"tag = {branch['tag']}", enable)
                self.assertIn("is_ai = yes", enable)
                self.assertIn(
                    "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
                    enable,
                )
                for token in branch["branch_tokens"]:
                    self.assertIn(token, enable)
                abort = _blocks(plan, "abort")[0]
                self.assertIn(
                    "has_global_flag = ADISCORD_vorkerland_collapse_finished", abort
                )
                for token in branch["identity_tokens"]:
                    if token.startswith("WKR_"):
                        self.assertIn(token.replace(" = yes", " = no"), abort)
                    else:
                        self.assertIn(f"NOT = {{ {token} }}", abort)
                if branch["branch_tokens"]:
                    for token in branch["branch_tokens"]:
                        complement = (
                            token[len("NOT = { ") : -len(" }")]
                            if token.startswith("NOT = {")
                            else f"NOT = {{ {token} }}"
                        )
                        self.assertIn(complement, abort)
                elif branch["tag"] != "WKR":
                    sibling_flag = next(
                        other["variant_flag"]
                        for other in VARIANT_BRANCHES
                        if other["focuses"][0] == branch["sibling"]
                    )
                    self.assertIn(f"has_country_flag = {sibling_flag}", abort)

    def test_variant_focuses_and_spirits_are_localised_in_both_languages(self) -> None:
        expected = {
            *(
                focus_id
                for branch in VARIANT_BRANCHES
                for focus_id in branch["focuses"]
            ),
            *(
                f"{focus_id}_desc"
                for branch in VARIANT_BRANCHES
                for focus_id in branch["focuses"]
            ),
            *VARIANT_IDEAS,
            *(f"{idea_id}_desc" for idea_id in VARIANT_IDEAS),
        }
        for label, path in (
            ("english", ENGLISH_LOCALISATION),
            ("russian", RUSSIAN_LOCALISATION),
        ):
            entries = localisation_entries(read(path))
            for key in sorted(expected):
                with self.subTest(language=label, key=key):
                    self.assertIn(key, entries)
                    self.assertTrue(entries[key].strip())

    def test_russian_variant_localisation_is_cyrillic_prose(self) -> None:
        entries = localisation_entries(
            source_section(read(RUSSIAN_LOCALISATION), 'civil_war_focus_l_russian')
        )
        for branch in VARIANT_BRANCHES:
            for focus_id in branch["focuses"]:
                for key in (focus_id, f"{focus_id}_desc"):
                    with self.subTest(key=key):
                        self.assertRegex(entries[key], "[А-Яа-яЁё]")
        raw = (ROOT / RUSSIAN_LOCALISATION).read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_prewar_blocks_are_separate_and_phase_bounded(self) -> None:
        for tag, focus_ids in (
            ("WRK", PREWAR_WRK_FOCUSES),
            ("VAD", PREWAR_VAD_FOCUSES),
        ):
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), {PREWAR_PHASE})
                    allowed_tags = set(re.findall(r"\btag\s*=\s*([A-Z]{3})", _allow_branch(block)))
                    expected_tags = {"WRK"} if tag == "WRK" else {"EYR", "EGC", "RIV", "YOR"}
                    self.assertEqual(allowed_tags, expected_tags)

    def test_vad_prewar_continuity_paths_are_short_and_reward_dense(self) -> None:
        terminal = "VAD_form_emergency_chancery"
        paths = _postwar_completion_paths(
            self.blocks, PREWAR_VAD_BASE_FOCUSES, terminal
        )
        self.assertEqual(len(paths), 2)
        self.assertEqual({len(path) for path in paths}, {4})
        self.assertEqual(
            {
                sum(_focus_cost(self.blocks[focus_id]) for focus_id in path)
                for path in paths
            },
            {8},
        )
        self.assertEqual(set().union(*paths), set(PREWAR_VAD_BASE_FOCUSES))
        self.assertTrue(
            all(
                _focus_cost(self.blocks[focus_id]) in {2, 3}
                for focus_id in PREWAR_WRK_BASE_FOCUSES
            )
        )
        for focus_id in PREWAR_VAD_BASE_FOCUSES:
            block = self.blocks[focus_id]
            cost = _focus_cost(block)
            payload = _postwar_reward_categories(block)
            minimum = 2 if cost <= 2 else 4
            with self.subTest(focus_id=focus_id):
                self.assertIn(cost, {1, 2, 3, 4})
                self.assertGreaterEqual(len(payload), minimum)
        self.assertEqual(_focus_cost(self.blocks[terminal]), 3)

    def test_prewar_expansion_has_exact_routes_geometry_and_course_switching(
        self,
    ) -> None:
        for focus_id in (
            *PREWAR_WRK_EXPANSION_FOCUSES,
            *PREWAR_VAD_EXPANSION_FOCUSES,
        ):
            block = self.blocks[focus_id]
            position = self.grid[focus_id]
            with self.subTest(focus_id=focus_id):
                self.assertEqual(position, PREWAR_EXPANSION_POSITIONS[focus_id])
                self.assertEqual(_focus_cost(block), PREWAR_EXPANSION_COSTS[focus_id])
                self.assertEqual(
                    _prerequisite_groups(block),
                    PREWAR_EXPANSION_PREREQUISITES[focus_id],
                )

        for left, right in (
            ("WRK_open_worker_vadl_backchannel", "WRK_mobilize_loyal_republics"),
            ("VAD_prepare_vadl_worker_terms", "VAD_activate_eastern_mandate"),
        ):
            self.assertEqual(_mutually_exclusive_focuses(self.blocks[left]), {right})
            self.assertEqual(_mutually_exclusive_focuses(self.blocks[right]), {left})

        for focus_id, (set_flag, clear_flag) in PREWAR_COURSE_SELECTIONS.items():
            selection = _blocks(self.blocks[focus_id], "select_effect")
            with self.subTest(focus_id=focus_id):
                self.assertEqual(len(selection), 1)
                self.assertEqual(
                    selection[0].count(f"set_country_flag = {set_flag}"), 1
                )
                self.assertEqual(
                    selection[0].count(f"clr_country_flag = {clear_flag}"), 1
                )

        for focus_id, expected_base in {
            "WRK_open_worker_vadl_backchannel": 35,
            "WRK_mobilize_loyal_republics": 65,
        }.items():
            ai = _blocks(self.blocks[focus_id], "ai_will_do")[0]
            self.assertEqual(
                int(re.search(r"\bbase\s*=\s*(\d+)\b", ai).group(1)),
                expected_base,
            )

        for focus_id, final_flag in {
            "WRK_offer_emergency_compact": "ADISCORD_vorkerland_wrk_compact_committed",
            "VAD_ratify_emergency_compact": "ADISCORD_vorkerland_district_compact_committed",
        }.items():
            reward = _blocks(self.blocks[focus_id], "completion_reward")[0]
            self.assertEqual(
                reward.count("ADISCORD_vorkerland_resolve_prewar_compact = yes"),
                1,
            )
            self.assertEqual(reward.count(f"set_country_flag = {final_flag}"), 1)

    def test_prewar_wrk_rewards_cross_once_into_the_materialized_wkr(self) -> None:
        definitions = _blocks(self.phase_effects, PREWAR_CARRYOVER_EFFECT)
        self.assertEqual(len(definitions), 1)
        carryover = definitions[0]
        self.assertIn("tag = WKR", carryover)
        self.assertRegex(
            carryover,
            rf"NOT\s*=\s*\{{\s*has_country_flag\s*=\s*{PREWAR_CARRYOVER_FLAG}\s*\}}",
        )
        self.assertEqual(
            carryover.count(f"set_country_flag = {PREWAR_CARRYOVER_FLAG}"), 1
        )
        for focus_id in PREWAR_WRK_CARRYOVER_FOCUSES:
            with self.subTest(focus_id=focus_id):
                self.assertEqual(
                    carryover.count(f"has_completed_focus = {focus_id}"), 1
                )

        hardline = next(
            scope
            for scope in _blocks(carryover, "if")
            if "has_completed_focus = WRK_place_reserves_under_worker" in scope
            and scope.count("has_completed_focus = ") == 1
        )
        for token in (
            "add_manpower = 1000",
            "type = infantry_equipment_0 amount = 5400 producer = WKR",
            "idea = ADISCORD_vorkerland_wrk_loyal_republics_mobilized days = 70",
        ):
            with self.subTest(hardline_token=token):
                self.assertEqual(re.sub(r"\s+", " ", hardline).count(token), 1)

        verify = _blocks(
            self.phase_effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )[0]
        wkr_tree_scopes = [
            scope for scope in _blocks(verify, "WKR") if "load_focus_tree" in scope
        ]
        self.assertEqual(len(wkr_tree_scopes), 1)
        self.assertIn(f"{PREWAR_CARRYOVER_EFFECT} = yes", wkr_tree_scopes[0])

    def test_prewar_wrk_native_grants_match_successor_carryover(self) -> None:
        carryover = _blocks(self.phase_effects, PREWAR_CARRYOVER_EFFECT)[0]

        def native_grants(source: str) -> Counter:
            grants = Counter(
                re.findall(
                    r"\b(add_political_power|add_stability|add_command_power|"
                    r"army_experience|add_manpower)\s*=\s*(-?[0-9.]+)",
                    source,
                )
            )
            for equipment in _blocks(source, "add_equipment_to_stockpile"):
                equipment_type = re.search(r"\btype\s*=\s*(\w+)", equipment).group(1)
                amount = re.search(r"\bamount\s*=\s*([0-9.]+)", equipment).group(1)
                grants[(equipment_type, amount)] += 1
            for timed in _blocks(source, "add_timed_idea"):
                idea = re.search(r"\bidea\s*=\s*(\w+)", timed).group(1)
                days = re.search(r"\bdays\s*=\s*(\d+)", timed).group(1)
                grants[(idea, days)] += 1
            return grants

        for focus_id in PREWAR_WRK_CARRYOVER_FOCUSES:
            inherited = next(
                scope
                for scope in _blocks(carryover, "if")
                if f"has_completed_focus = {focus_id}" in scope
                and scope.count("has_completed_focus = ") == 1
            )
            reward = _blocks(self.blocks[focus_id], "completion_reward")[0]
            with self.subTest(focus_id=focus_id):
                self.assertEqual(native_grants(reward), native_grants(inherited))

    def test_every_winner_settlement_ends_the_precollapse_crisis_on_its_own_tag(
        self,
    ) -> None:
        scrub = _blocks(self.phase_effects, PRECOLLAPSE_CRISIS_SCRUB_EFFECT)[0]
        scrubbed_ideas = Counter(
            re.findall(r"\bremove_ideas\s*=\s*([A-Za-z0-9_]+)", scrub)
        )
        for idea_id in PRECOLLAPSE_SCRUBBED_IDEAS:
            with self.subTest(scrubbed_idea=idea_id):
                self.assertEqual(scrubbed_ideas[idea_id], 1)

        effects = read(PHASE_EFFECTS_FILE)
        for retired in RETIRED_HANDOFF_EFFECTS:
            with self.subTest(retired=retired):
                self.assertNotIn(retired, effects)

        scrub_call = f"{PRECOLLAPSE_CRISIS_SCRUB_EFFECT} = yes"
        for winner_tag, settlement_name in UNIFICATION_SETTLEMENT_EFFECTS.items():
            with self.subTest(winner_tag=winner_tag):
                unification = _blocks(
                    self.phase_effects, UNIFICATION_EFFECTS[winner_tag]
                )[0]
                settlement = _blocks(self.phase_effects, settlement_name)[0]
                # The winner is the country being settled; nothing consumes it
                # or moves its player to another tag.
                self.assertNotIn("change_tag_from", unification + settlement)
                self.assertNotRegex(
                    unification + settlement,
                    rf"annex_country\s*=\s*\{{\s*target\s*=\s*{winner_tag}\b",
                )
                self.assertEqual(
                    settlement.count(scrub_call), 0 if winner_tag == "WKR" else 1
                )
                self.assertNotIn(scrub_call, unification)

    def test_worker_unification_keeps_the_reform_stage_it_reached(self) -> None:
        unification = _blocks(self.phase_effects, UNIFICATION_EFFECTS["WKR"])[0]
        settlements = {
            tag: _blocks(self.phase_effects, name)[0]
            for tag, name in UNIFICATION_SETTLEMENT_EFFECTS.items()
        }
        worker = settlements["WKR"]
        ended = Counter(re.findall(r"\bremove_ideas\s*=\s*([A-Za-z0-9_]+)", worker))
        for idea_id in PRECOLLAPSE_CRISIS_IDEAS:
            with self.subTest(ended=idea_id):
                self.assertEqual(ended[idea_id], 1)
        for idea_id in WORKER_REFORM_STAGE_IDEAS:
            with self.subTest(kept=idea_id):
                self.assertNotRegex(unification + worker, rf"\b{idea_id}\b")

        effects = read(PHASE_EFFECTS_FILE)
        self.assertEqual(unification_spirit_issues(settlements, effects), [])
        worker_name = UNIFICATION_SETTLEMENT_EFFECTS["WKR"]
        joint_name = UNIFICATION_SETTLEMENT_EFFECTS["VAD"]
        scrub_call = f"{PRECOLLAPSE_CRISIS_SCRUB_EFFECT} = yes"
        hourglass = "remove_ideas = WRK_hourglass_of_discord"
        reform_stage = WORKER_REFORM_STAGE_IDEAS[0]
        cases = (
            (
                {"WKR": worker.replace(hourglass, scrub_call, 1)},
                effects,
                (
                    f"{worker_name} must keep the worker reform stage instead of "
                    f"running {PRECOLLAPSE_CRISIS_SCRUB_EFFECT}",
                    f"{worker_name} must end WRK_hourglass_of_discord exactly once",
                ),
            ),
            (
                {"WKR": worker.replace(hourglass, f"{hourglass}\n\tremove_ideas = {reform_stage}", 1)},
                effects,
                (f"{worker_name} must leave the worker reform stage {reform_stage} untouched",),
            ),
            (
                {
                    "WKR": worker.replace(
                        hourglass,
                        f"{hourglass}\n\tannex_country = {{ target = WKR transfer_troops = yes }}",
                        1,
                    )
                },
                effects,
                (f"{worker_name} must not annex its winner WKR",),
            ),
            (
                {"VAD": settlements["VAD"].replace(scrub_call, "", 1)},
                effects,
                (f"{joint_name} must invoke {PRECOLLAPSE_CRISIS_SCRUB_EFFECT} exactly once",),
            ),
            (
                {},
                f"{effects}\n{worker_name} = {{ {RETIRED_HANDOFF_EFFECTS[0]} = yes }}\n",
                (
                    f"retired handoff effect {RETIRED_HANDOFF_EFFECTS[0]} must not be "
                    "defined or called",
                ),
            ),
        )
        for mutated, script, expected in cases:
            with self.subTest(expected=expected[0]):
                for tag, block in mutated.items():
                    self.assertNotEqual(block, settlements[tag])
                issues = unification_spirit_issues({**settlements, **mutated}, script)
                for diagnostic in expected:
                    self.assertIn(diagnostic, issues)

    def test_wartime_routes_are_isolated_and_bounded(self) -> None:
        for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), ACTIVE_PHASE_FLAGS)
                    self.assertIn(f"tag = {tag}", block)
                    self.assertEqual(len(_blocks(block, "bypass")), 0 if focus_id in ("VAD_convene_collegial_staff", "VAD_require_collective_directives", "VAD_delegate_to_front_commands", "VAD_codify_staff_mandate") else 1)
                    for other in {"WKR", "VAD", "TVA"} - {tag}:
                        self.assertNotIn(f"tag = {other}", block)
            route = "\n".join(self.blocks[focus_id] for focus_id in focus_ids)
            self.assertGreaterEqual(route.count("modifier ="), 3)

    def test_military_terminal_unlocks_retreat_levies_once(self) -> None:
        for tag, hook in RETREAT_HOOKS.items():
            route = "\n".join(
                self.blocks[focus_id] for focus_id in WARTIME_ROUTE_FOCUSES[tag]
            )
            self.assertEqual(route.count(f"set_country_flag = {hook}"), 1)
            capstone, central_hook = CENTRAL_CAPSTONES[tag]
            self.assertIn(f"set_country_flag = {central_hook}", self.blocks[capstone])
            self.assertIn(
                f"set_country_flag = {CENTRAL_PREPARED_FLAG}", self.blocks[capstone]
            )

    def test_wartime_routes_and_converge_before_central_unlock(self) -> None:
        for tag, (capstone, expected_groups) in WARTIME_TERMINALS.items():
            with self.subTest(tag=tag):
                prerequisites = _blocks(self.blocks[capstone], "prerequisite")
                actual = Counter(
                    frozenset(re.findall(r"\bfocus\s*=\s*([A-Za-z0-9_]+)", block))
                    for block in prerequisites
                )
                expected = Counter(expected_groups)
                self.assertEqual(actual, expected)

    def test_only_meaningful_wartime_choices_are_mutually_exclusive(self) -> None:
        pairs = (
            ("TVA_optimize_for_throughput", "TVA_protect_irreplaceable_specialists"),
            ("TVA_optimize_for_throughput", "TVA_delegate_to_algorithmic_board"),
            (
                "TVA_delegate_to_algorithmic_board",
                "TVA_protect_irreplaceable_specialists",
            ),
            ("TVA_raise_technical_battalions", "TVA_test_remote_fire_control"),
            ("TVA_raise_technical_battalions", "TVA_test_adaptive_logistics"),
            ("TVA_test_remote_fire_control", "TVA_test_adaptive_logistics"),
        )
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertIn(f"focus = {right}", self.blocks[left])
                self.assertIn(f"focus = {left}", self.blocks[right])

    def test_worx_engineering_programmes_remain_jointly_completable(self) -> None:
        for focus_id in (
            "TVA_reroute_city_grid",
            "TVA_deploy_field_laboratories",
            "TVA_seal_the_approaches",
            "TVA_issue_emergency_output_norms",
            "TVA_build_mobile_repair_trains",
            "TVA_harden_switching_stations",
        ):
            with self.subTest(focus_id=focus_id):
                self.assertNotIn("mutually_exclusive", self.blocks[focus_id])

        for focus_id, (idea_id, days) in WORX_WARTIME_TIMED_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                self.assertIn(
                    f"add_timed_idea = {{ idea = {idea_id} days = {days} }}",
                    _plan_reward_contract(self.blocks[focus_id]),
                )
                self.assertEqual(len(_blocks(self.collapse_ideas, idea_id)), 1)

    def test_successful_worx_logistics_trial_grants_its_seventy_day_spirit(self) -> None:
        trial_effects = source_section(read(PHASE_EFFECTS_FILE), "war_economy_effects")
        success = _blocks(trial_effects, "ADISCORD_vorkerland_tva_field_trial_success")[0]
        reward = (
            f"add_timed_idea = {{ idea = {WORX_ADAPTIVE_LOGISTICS_IDEA} days = 70 }}"
        )
        self.assertEqual(success.count(reward), 1)
        self.assertEqual(
            len(_blocks(self.collapse_ideas, WORX_ADAPTIVE_LOGISTICS_IDEA)), 1
        )

    def test_operational_loop_does_not_repeat_level_two_and_formation_has_level_three(
        self,
    ) -> None:
        close_loop = self.blocks["TVA_close_operational_loop"]
        self.assertNotIn("ADISCORD_vorkerland_tva_field_directorate", close_loop)
        self.assertIn(
            "TVA_standardize_emergency_administration", _prerequisites(close_loop)
        )

        standardize = self.blocks["TVA_standardize_emergency_administration"]
        self.assertEqual(standardize.count("else = { add_war_support = 0.01 }"), 1)

        formation = _blocks(self.phase_effects, "ADISCORD_vorkerland_settle_unification_under_tva")
        self.assertEqual(len(formation), 1)
        self.assertEqual(
            formation[0].count(
                "add_ideas = ADISCORD_vorkerland_tva_field_directorate_3"
            ),
            1,
        )

        measurable_republic = self.blocks["WRK_utilitarian_build_measurable_republic"]
        for idea_id in WORX_FIELD_DIRECTORATE_IDEAS:
            with self.subTest(consolidated_idea=idea_id):
                self.assertRegex(
                    measurable_republic,
                    rf"(?m)^\s*remove_ideas\s*=\s*{re.escape(idea_id)}\s*$",
                )

    def test_public_utilities_adds_capacity_before_energy_infrastructure(self) -> None:
        focus = self.blocks["WRK_utilitarian_prioritize_public_utilities"]
        self.assertEqual(focus.count("limit = { controls_state = 37 }"), 1)
        self.assertEqual(focus.count("add_extra_state_shared_building_slots = 1"), 1)
        self.assertEqual(
            focus.count("type = energy_infrastructure level = 1 instant_build = yes"),
            1,
        )

    def test_vad_armament_depots_guarantee_factory_capacity(self) -> None:
        focus = self.blocks["VAD_reopen_armament_depots"]
        slot = "add_extra_state_shared_building_slots = 1"
        factory = "type = arms_factory level = 1 instant_build = yes"
        self.assertEqual(focus.count("limit = { controls_state = 75 }"), 1)
        self.assertEqual(focus.count(slot), 1)
        self.assertEqual(focus.count(factory), 1)
        self.assertLess(focus.index(slot), focus.index(factory))

    def test_each_wartime_route_has_political_military_and_economic_rewards(
        self,
    ) -> None:
        reward_classes = (
            ("add_political_power", "add_stability"),
            ("army_experience", "add_command_power", "add_manpower", "add_war_support"),
            (
                "add_equipment_to_stockpile",
                "add_building_construction",
                "add_timed_idea",
            ),
        )
        for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
            source = "\n".join(self.blocks[focus_id] for focus_id in focus_ids)
            for tokens in reward_classes:
                with self.subTest(tag=tag, tokens=tokens):
                    self.assertTrue(any(token in source for token in tokens))

    def test_mobile_repair_train_focus_grants_a_concrete_timed_spirit(self) -> None:
        focus = self.blocks["TVA_build_mobile_repair_trains"]
        reward = f"add_timed_idea = {{ idea = {MOBILE_REPAIR_IDEA} days = 35 }}"
        self.assertEqual(_plan_reward_contract(focus).count(reward), 1)
        self.assertEqual(len(_blocks(self.collapse_ideas, MOBILE_REPAIR_IDEA)), 1)

    def test_focus_land_repair_spirits_do_not_use_ship_repair_modifier(self) -> None:
        for idea_id in LAND_REPAIR_IDEAS:
            with self.subTest(idea_id=idea_id):
                definitions = _blocks(self.collapse_ideas, idea_id)
                self.assertEqual(len(definitions), 1)
                self.assertEqual(
                    definitions[0].count("industry_repair_factor = 0.20"), 1
                )
                self.assertNotRegex(definitions[0], r"\brepair_speed_factor\s*=")

    def test_vad_sol_policy_is_wartime_hook_only(self) -> None:
        hook = "ADISCORD_vorkerland_focus_vad_sol_invitation_intent"
        focus = self.blocks["VAD_invite_sol_delegation"]
        self.assertEqual(_phase_flags(focus), ACTIVE_PHASE_FLAGS)
        self.assertIn(f"set_country_flag = {hook}", focus)
        self.assertEqual(self.source.count(f"set_country_flag = {hook}"), 1)
        for forbidden in ("declare_war_on", "create_wargoal", "puppet", "set_autonomy"):
            self.assertNotIn(forbidden, focus)

    def test_focuses_feed_visible_diplomacy_and_support_decisions(self) -> None:
        diplomacy = source_section(
            read(DIPLOMACY_DECISIONS_FILE), 'diplomacy_decisions'
        )
        support = "\n".join(read(path) for path in FOCUS_DECISION_FILES)
        for hook in (
            "ADISCORD_vorkerland_focus_vad_sol_invitation_intent",
            "ADISCORD_vorkerland_focus_wkr_vla_invitation_intent",
        ):
            self.assertIn(hook, self.source)
            self.assertIn(hook, diplomacy)
        for flag in (
            "ADISCORD_vorkerland_wkr_vla_alliance_accepted",
            "ADISCORD_vorkerland_vad_sol_alliance_accepted",
        ):
            self.assertIn(flag, support)

    def test_claimant_focus_events_are_owned_one_shot_and_news_bounded(self) -> None:
        self.assertNotIn("has_command_power", self.claimant_events)
        self.assertIn("command_power < 20", self.claimant_events)
        definitions = [
            block
            for assignment in ("country_event", "news_event")
            for block in _blocks(self.claimant_events, assignment)
            if re.search(r"(?m)^\s*title\s*=", block)
        ]
        event_ids = [
            re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_.]+)\s*$", block).group(1)
            for block in definitions
        ]
        self.assertEqual(
            event_ids, list(CLAIMANT_OWNED_EVENT_IDS)
        )
        self.assertEqual(
            self.claimant_events.count("fire_only_once = yes"), len(event_ids) - len(CLAIMANT_PROGRAMME_EVENT_IDS) - 2
        )
        for event_id in CLAIMANT_NEWS_EVENT_IDS:
            self.assertEqual(self.claimant_events.count(f"id = {event_id}"), 2)

        by_id = {
            re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_.]+)\s*$", block).group(1): block
            for block in definitions
        }
        for event_id, option_count in {
            "ADISCORD_vorkerland_claimant.4": 4,
            "ADISCORD_vorkerland_claimant.13": 5,
            "ADISCORD_vorkerland_claimant.14": 2,
            "ADISCORD_vorkerland_claimant.23": 3,
            "ADISCORD_vorkerland_claimant.24": 3,
        }.items():
            with self.subTest(event_id=event_id):
                self.assertEqual(len(_blocks(by_id[event_id], "option")), option_count)

    def test_postwar_routes_need_phase_and_exact_route_flag(self) -> None:
        for route_flag, focus_ids in POSTWAR_ROUTE_FOCUSES.items():
            root = self.blocks[focus_ids[0]]
            self.assertEqual(_prerequisites(root), set())
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), {POSTWAR_PHASE})
                    # The postwar tree opens for whichever claimant unified
                    # the country, never for a literal tag.
                    self.assertEqual(
                        re.findall(r"\btag\s*=\s*(\S+)", _allow_branch(block)),
                        [NATION_TARGET],
                    )
                    self.assertNotIn("tag = WRK", block)
                    self.assertIn(f"has_country_flag = {route_flag}", block)

    def test_postwar_routes_have_two_reachable_policy_paths(self) -> None:
        expected_costs = {
            "ADISCORD_vorkerland_route_worker": 31,
            "ADISCORD_vorkerland_route_joint": 29,
            "ADISCORD_vorkerland_route_utilitarian": 31,
        }
        for route_flag, focus_ids in POSTWAR_ROUTE_FOCUSES.items():
            terminal_id = POSTWAR_ROUTE_TERMINALS[route_flag]
            paths = _postwar_completion_paths(self.blocks, focus_ids, terminal_id)
            with self.subTest(route_flag=route_flag):
                self.assertEqual(len(focus_ids), 12 if route_flag.endswith("_joint") else 11)
                self.assertEqual(_focus_cost(self.blocks[terminal_id]), 4)
                self.assertEqual(len(paths), 2)
                self.assertEqual({len(path) for path in paths}, {10})
                self.assertEqual(
                    {
                        sum(_focus_cost(self.blocks[focus_id]) for focus_id in path)
                        for path in paths
                    },
                    {expected_costs[route_flag]},
                )
                all_paths = paths
                if route_flag.endswith("_joint"):
                    staff_paths = _postwar_completion_paths(self.blocks, focus_ids, "WRK_joint_ratify_staff_constitution")
                    self.assertEqual(len(staff_paths), 2)
                    self.assertEqual({len(path) for path in staff_paths}, {11})
                    all_paths = (*paths, *staff_paths)
                self.assertEqual(set().union(*all_paths), set(focus_ids))

    def test_postwar_policy_choices_are_real_ai_weighted_forks(self) -> None:
        for left, right in POSTWAR_POLICY_CHOICE_PAIRS:
            with self.subTest(left=left, right=right):
                self.assertIn(right, _mutually_exclusive_focuses(self.blocks[left]))
                self.assertIn(left, _mutually_exclusive_focuses(self.blocks[right]))
                self.assertTrue(
                    _blocks(_blocks(self.blocks[left], "ai_will_do")[0], "modifier")
                )
                self.assertTrue(
                    _blocks(_blocks(self.blocks[right], "ai_will_do")[0], "modifier")
                )

    def test_postwar_focus_costs_match_substantive_reward_density(self) -> None:
        for focus_ids in POSTWAR_ROUTE_FOCUSES.values():
            for focus_id in focus_ids:
                block = self.blocks[focus_id]
                cost = _focus_cost(block)
                payload = _postwar_reward_categories(block)
                minimum = 2 if cost <= 2 else 3 if cost <= 4 else 4
                with self.subTest(focus_id=focus_id):
                    self.assertIn(cost, range(1, 8))
                    self.assertGreaterEqual(len(payload), minimum)
                    if cost >= 5:
                        self.assertIn(focus_id, POSTWAR_SETTLEMENT_IDEAS)

    def test_postwar_capstones_install_one_mutually_exclusive_lasting_settlement(
        self,
    ) -> None:
        for capstone_id, (
            settlement_idea,
            incompatible_ideas,
        ) in POSTWAR_SETTLEMENT_IDEAS.items():
            with self.subTest(capstone_id=capstone_id):
                capstone = self.blocks[capstone_id]
                self.assertEqual(capstone.count(f"add_ideas = {settlement_idea}"), 1)
                self.assertNotIn(f"remove_ideas = {settlement_idea}", capstone)
                for incompatible_idea in incompatible_ideas:
                    self.assertEqual(
                        capstone.count(f"remove_ideas = {incompatible_idea}"), 1
                    )

                definitions = _blocks(self.collapse_ideas, settlement_idea)
                self.assertEqual(len(definitions), 1)
                self.assertRegex(definitions[0], r"\bremoval_cost\s*=\s*-1\b")

    def test_worker_and_joint_routes_stage_then_consolidate_institutions(self) -> None:
        for capstone_id, installers in POSTWAR_TRANSITIONAL_IDEAS.items():
            capstone = self.blocks[capstone_id]
            for focus_id, idea_id in installers.items():
                with self.subTest(capstone_id=capstone_id, idea_id=idea_id):
                    self.assertEqual(
                        self.blocks[focus_id].count(f"add_ideas = {idea_id}"), 1
                    )
                    self.assertEqual(capstone.count(f"remove_ideas = {idea_id}"), 1)
                    definitions = _blocks(self.collapse_ideas, idea_id)
                    self.assertEqual(len(definitions), 1)
                    self.assertIn("removal_cost = -1", definitions[0])

    def test_worx_postwar_programmes_build_and_consolidate_real_institutions(
        self,
    ) -> None:
        capstone = self.blocks["WRK_utilitarian_build_measurable_republic"]
        for focus_id, idea_id in WORX_POSTWAR_PROVISIONAL_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                self.assertIn(f"add_ideas = {idea_id}", self.blocks[focus_id])
                self.assertIn(f"remove_ideas = {idea_id}", capstone)
                idea = _blocks(self.collapse_ideas, idea_id)
                self.assertEqual(len(idea), 1)
                self.assertIn("removal_cost = -1", idea[0])

        route = "\n".join(
            self.blocks[focus_id]
            for focus_id in POSTWAR_ROUTE_FOCUSES[
                "ADISCORD_vorkerland_route_utilitarian"
            ]
        )
        bonuses = _blocks(route, "add_tech_bonus")
        self.assertEqual(len(bonuses), 2)
        categories = {
            re.search(r"\bcategory\s*=\s*([A-Za-z0-9_]+)", bonus).group(1)
            for bonus in bonuses
        }
        self.assertEqual(categories, {"industry", "electronics"})

    def test_dorian_worx_is_the_existing_technocrat_with_authored_portrait(
        self,
    ) -> None:
        definitions = _blocks(read(CHARACTER_FILE), "TVA_Dorian_Worx")
        self.assertEqual(len(definitions), 1)
        worx = definitions[0]
        self.assertIn("ideology = dorian_technocracy", worx)
        self.assertIn("large = GFX_portrait_WRK_Dorian_Worx", worx)

        english = localisation_entries(
            source_section(read(ENGLISH_LOCALISATION), 'civil_war_focus_l_english')
        )
        russian = localisation_entries(
            source_section(read(RUSSIAN_LOCALISATION), 'civil_war_focus_l_russian')
        )
        self.assertIn("Worx", english["TVA_codify_utilitarian_directorate"])
        self.assertIn("Technocratic", english["TVA_codify_utilitarian_directorate"])
        self.assertIn(
            "Technocratic Republic",
            english["WRK_utilitarian_build_measurable_republic"],
        )
        self.assertIn("Воркс", russian["TVA_codify_utilitarian_directorate"])
        self.assertIn(
            "технократ", russian["TVA_codify_utilitarian_directorate"].lower()
        )
        self.assertIn(
            "технократическую республику",
            russian["WRK_utilitarian_build_measurable_republic"],
        )

    def test_focus_tooltip_references_have_exact_bilingual_keys(self) -> None:
        references = set(
            re.findall(
                r"\b(?:custom_effect_tooltip|tooltip)\s*=\s*([A-Za-z0-9_]+)",
                self.source,
            )
        )
        for localisation in (ENGLISH_LOCALISATION, RUSSIAN_LOCALISATION):
            with self.subTest(localisation=localisation):
                entries = localisation_entries(read(localisation))
                self.assertEqual(references - set(entries), set())

    def test_vorkerland_idea_localisation_and_ivanland_expedition_exist(self) -> None:
        expected_keys = {
            key
            for idea_id in POSTWAR_IDEA_LOCALISATION_IDS
            for key in (idea_id, f"{idea_id}_desc")
        }
        for localisation in (
            ENGLISH_POSTWAR_IDEA_LOCALISATION,
            RUSSIAN_POSTWAR_IDEA_LOCALISATION,
        ):
            with self.subTest(localisation=localisation):
                self.assertEqual(
                    set(
                        localisation_entries(
                            source_section(
                                read(localisation),
                                "postwar_ideas_l_"
                                + (
                                    "russian"
                                    if localisation == RUSSIAN_POSTWAR_IDEA_LOCALISATION
                                    else "english"
                                ),
                            )
                        )
                    ),
                    expected_keys,
                )

        definitions = _blocks(self.collapse_ideas, IVANLAND_EXPEDITIONARY_IDEA)
        self.assertEqual(len(definitions), 1)
        for token in (
            "army_attack_factor = 0.08",
            "army_org_regain = 0.08",
            "planning_speed = 0.10",
            "supply_consumption_factor = -0.08",
        ):
            self.assertIn(token, definitions[0])

    def test_each_postwar_route_unlocks_public_core_packages(self) -> None:
        hook = "ADISCORD_vorkerland_focus_postwar_core_decisions_unlocked"
        postwar = "\n".join(
            self.blocks[focus_id]
            for focus_ids in POSTWAR_ROUTE_FOCUSES.values()
            for focus_id in focus_ids
        )
        self.assertEqual(postwar.count(f"set_country_flag = {hook}"), 3)
        decisions = "\n".join(read(path) for path in FOCUS_DECISION_FILES)
        for decision_id in CORE_DECISIONS:
            with self.subTest(decision_id=decision_id):
                start = decisions.index(f"\t{decision_id} = {{")
                next_block = decisions.find("\n\tADISCORD_", start + 1)
                block = decisions[
                    start : next_block if next_block != -1 else len(decisions)
                ]
                self.assertIn(f"has_country_flag = {hook}", block)

    def test_retired_fillers_and_claimant_events_cannot_own_wars_or_phases(
        self,
    ) -> None:
        for focus_id in RETIRED_WARTIME_FOCUSES:
            with self.subTest(focus_id=focus_id):
                self.assertNotIn(focus_id, self.blocks)
                for path in (
                    "focus_trees/Vorkerland/prewar/focuses.txt",
                    "common/national_focus/ADISCORD_Vorkerland_prewar.txt",
                ):
                    self.assertNotIn(focus_id, (ROOT / path).read_text(encoding="utf-8-sig"))
        for token in (
            "declare_war_on",
            "start_civil_war",
            "create_wargoal",
            "annex_country",
            "set_global_flag",
            "ADISCORD_vorkerland_set_phase_",
        ):
            self.assertNotIn(token, self.source)
            self.assertNotIn(token, self.claimant_events)
        for token in (
            "every_country",
            "random_country",
            "on_monthly",
            "monthly_pulse",
            "Lucas",
            "lucas",
        ):
            self.assertNotIn(token, self.source)
            self.assertNotIn(token, self.claimant_events)

    def test_each_claimant_capstone_sets_decision_gate_and_reports_readiness(
        self,
    ) -> None:
        hooks = {
            "WKR": (
                "WKR_republic_fights_as_one",
                "ADISCORD_vorkerland_focus_wkr_central_war_unlocked",
            ),
            "VAD": (
                "VAD_balance_council_and_command",
                "ADISCORD_vorkerland_focus_vad_central_war_unlocked",
            ),
            "TVA": (
                "TVA_close_operational_loop",
                "ADISCORD_vorkerland_focus_tva_central_war_unlocked",
            ),
        }
        for tag, (capstone, hook) in hooks.items():
            with self.subTest(tag=tag):
                block = self.blocks[capstone]
                self.assertIn(f"set_country_flag = {hook}", block)
                self.assertEqual(
                    block.count(f"set_country_flag = {CENTRAL_PREPARED_FLAG}"), 1
                )
                for payload in (
                    "add_command_power = 10",
                    "add_war_support = 0.02",
                    "army_experience = 5",
                    "amount = 75",
                    "country_event = { id = ADISCORD_vorkerland_claimant.",
                ):
                    self.assertIn(payload, block)

    def test_fortification_is_one_minor_redoubt_per_claimant(self) -> None:
        focuses = {
            "WKR": ("WKR_authorize_retreat_levies", 32, 6713),
            "VAD": ("VAD_assemble_joint_general_staff", 75, 6192),
            "TVA": ("TVA_seal_the_approaches", 36, 12227),
        }
        for tag, (focus_id, state, province) in focuses.items():
            with self.subTest(tag=tag):
                block = self.blocks[focus_id]
                self.assertEqual(block.count("type = bunker level = 1"), 1)
                self.assertIn(f"limit = {{ controls_state = {state} }}", block)
                self.assertIn(f"province = {province}", block)

    def test_every_authored_tree_icon_has_an_explicit_additive_shine_sprite(
        self,
    ) -> None:
        shine = read(SHINE_FILE)
        for focus_id, block in self.blocks.items():
            icon_line = next(
                line.strip()
                for line in block.splitlines()
                if line.strip().startswith("icon = ")
            )
            icon = icon_line.split("=", maxsplit=1)[1].strip()
            with self.subTest(focus_id=focus_id, icon=icon):
                self.assertIn(f'name = "{icon}_shine"', shine)

    def test_route_signature_focuses_have_distinct_icons(self) -> None:
        expected = {
            "WKR_republic_fights_as_one": "GFX_focus_WKR_republic_fights_as_one",
            "VAD_proclaim_joint_charter": "GFX_focus_VAD_proclaim_joint_charter",
            "VAD_balance_council_and_command": "GFX_focus_VAD_balance_council_and_command",
            "TVA_codify_utilitarian_directorate": "GFX_focus_TVA_codify_utilitarian_directorate",
            "TVA_close_operational_loop": "GFX_focus_TVA_close_operational_loop",
            "WRK_joint_impose_reunification_settlement": "GFX_focus_WRK_joint_impose_reunification_settlement",
            "WRK_utilitarian_build_measurable_republic": "GFX_focus_WRK_utilitarian_build_measurable_republic",
        }
        for focus_id, expected_icon in expected.items():
            icon_line = next(
                line.strip()
                for line in self.blocks[focus_id].splitlines()
                if line.strip().startswith("icon = ")
            )
            with self.subTest(focus_id=focus_id):
                self.assertEqual(icon_line, f"icon = {expected_icon}")

    def test_continuous_focus_palette_is_deliberately_empty(self) -> None:
        self.assertEqual(self.continuous_blocks, {})
        palettes = _blocks(self.continuous_source, "continuous_focus_palette")
        self.assertEqual(len(palettes), 1)
        palette = palettes[0]
        self.assertIn("id = generic_focus", palette)
        self.assertIn("default = yes", palette)
        self.assertNotRegex(palette, r"(?m)^\s*focus\s*=")

    def test_focus_source_uses_valid_trigger_and_equipment_ids(self) -> None:
        self.assertNotRegex(
            self.source,
            r"(?<!has_)(?<!add_)\bstability\s*(?:=|<|>)",
        )
        self.assertNotRegex(
            self.source,
            r"(?<!has_)(?<!add_)\bpolitical_power\s*(?:=|<|>)",
        )
        self.assertNotRegex(self.source, r"\binfantry_equipment_1\b")

    def test_russian_localisation_keeps_utf8_bom(self) -> None:
        self.assertTrue(
            (ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf")
        )

    # ------------------------------------------------------------------
    # Claimant depth branches
    # ------------------------------------------------------------------

    def test_claimant_modules_match_their_authored_routes(self) -> None:
        modules = {}
        for (tag, branch), focus_ids in DEPTH_MODULE_FOCUSES.items():
            modules.setdefault(tag, {})[branch] = len(focus_ids)
        self.assertEqual(sorted(modules), ["TVA", "VAD", "WKR"])
        for tag, branches in modules.items():
            with self.subTest(tag=tag):
                expected = {
                    "war_economy": 3,
                    "doctrine": 4,
                    "late_war": 3,
                    "legitimacy": 3,
                    "diplomacy": 2,
                    "air": 2,
                }
                if tag == "TVA":
                    expected["air"] = 2
                    expected["doctrine"] = 2
                    expected["war_economy"] = 2
                    expected["late_war"] = 2
                    expected["legitimacy"] = 2
                else:
                    expected["foreign_policy"] = 3
                    if tag == "WKR":
                        expected["late_war"] = 2
                        expected["foreign_policy"] = 2
                    if tag == "VAD":
                        del expected["diplomacy"]
                        expected["foreign_policy"] = 2
                        expected["air"] = 2
                        expected["late_war"] = 2
                        expected["legitimacy"] = 2
                self.assertEqual(branches, expected)

    def test_depth_focuses_sit_on_their_documented_cells(self) -> None:
        for focus_id, expected in DEPTH_POSITIONS.items():
            with self.subTest(focus_id=focus_id):
                self.assertEqual(self.grid[focus_id], expected)

    def test_vad_final_icons_keep_art_masks_separate_from_the_shine_overlay(self) -> None:
        gfx = (ROOT / "interface/ADISCORD_national_focus.gfx").read_text(encoding="utf-8-sig")
        shines = (ROOT / "interface/ADISCORD_focus_shines.gfx").read_text(encoding="utf-8-sig")
        for focus_id in (
            "VAD_march_on_the_old_capital", "VAD_fortify_the_restoration_line",
            "VAD_issue_restoration_guarantees", "VAD_seat_the_observer_missions",
        ):
            name = "GFX_focus_" + focus_id
            base = next(block for block in _blocks(gfx, "spriteType") if f'name = "{name}"' in block)
            shine = next(block for block in _blocks(shines, "SpriteType") if f'name = "{name}_shine"' in block)
            texture = re.search(r'(?m)^\s*texturefile\s*=\s*"([^"]+)"', base).group(1)
            self.assertIn(f'texturefile = "{texture}"', shine)
            self.assertIn(f'animationmaskfile = "{texture}"', shine)
            self.assertIn('animationtexturefile = "gfx/interface/goals/shine_overlay.dds"', shine)

    def test_depth_focuses_anchor_to_a_real_prerequisite_inside_their_band(
        self,
    ) -> None:
        for focus_id, anchor in DEPTH_ANCHORS.items():
            with self.subTest(focus_id=focus_id):
                self.assertIn(anchor, self.blocks)
                self.assertIn(anchor, _prerequisites(self.blocks[focus_id]))
                tag = focus_id.split("_")[0]
                (low, high), (top, bottom) = LAYOUT_BANDS[f"war_{tag}"]
                x, y = self.grid[focus_id]
                self.assertTrue(low <= x <= high, (focus_id, x))
                self.assertTrue(top <= y <= bottom, (focus_id, y))
                self.assertGreater(y, self.grid[anchor][1])

    def test_depth_forks_are_symmetric_and_mutually_exclusive(self) -> None:
        for left, right in DEPTH_EXCLUSIVE_PAIRS:
            with self.subTest(pair=(left, right)):
                self.assertIn(right, _mutually_exclusive_focuses(self.blocks[left]))
                self.assertIn(left, _mutually_exclusive_focuses(self.blocks[right]))
                left_cell, right_cell = self.grid[left], self.grid[right]
                self.assertEqual(left_cell[1], right_cell[1])
                self.assertEqual(abs(left_cell[0] - right_cell[0]), 2)

    def test_timed_reward_count_distinguishes_preview_from_delivery(self) -> None:
        from tools.validators import validate_adiscord_vorkerland_civil_war_focus as validator

        self.assertTrue(hasattr(validator, "_count_timed_rewards"))
        grant = "add_timed_idea = { idea = operation days = 35 }"
        preview = f"effect_tooltip = {{ {grant} }}"
        self.assertEqual(validator._count_timed_rewards(preview, "operation", 35), 0)
        self.assertEqual(validator._count_timed_rewards(preview + grant, "operation", 35), 1)
        self.assertEqual(validator._count_timed_rewards(preview + grant + grant, "operation", 35), 2)

    def test_late_war_depth_branches_use_their_preparation_windows(self) -> None:
        self.assertNotIn("ADISCORD_vorkerland_war_month", self.source)
        for focus_id in DEPTH_LATE_WAR_FOCUSES:
            available = _blocks(self.blocks[focus_id], "available")[0]
            expected = {SHOWDOWN_PHASE}
            if focus_id.startswith(("TVA_", "WKR_", "VAD_")):
                expected.add("ADISCORD_vorkerland_phase_central_preparation")
            with self.subTest(focus=focus_id):
                self.assertEqual(_phase_flags(available), expected)

    def test_legitimacy_depth_branches_use_the_documented_interface(self) -> None:
        spends = [f for f, d in DEPTH_LEGITIMACY_DELTAS.items() if d < 0]
        builds = [f for f, d in DEPTH_LEGITIMACY_DELTAS.items() if d > 0]
        self.assertTrue(spends and builds)
        for focus_id, delta in DEPTH_LEGITIMACY_DELTAS.items():
            reward = _blocks(self.blocks[focus_id], "completion_reward")[0]
            with self.subTest(focus_id=focus_id):
                self.assertIn(
                    f"set_temp_variable = {{ ADISCORD_vorkerland_legitimacy_delta = {delta} }}",
                    reward,
                )
                self.assertEqual(
                    reward.count("ADISCORD_vorkerland_add_legitimacy = yes"), 1
                )
                self.assertNotIn("var = ADISCORD_vorkerland_legitimacy ", reward)

    def test_variant_doctrine_gates_identity_in_available_not_allow_branch(
        self,
    ) -> None:
        for focus_id, token in DEPTH_VARIANT_IDENTITY.items():
            block = self.blocks[focus_id]
            with self.subTest(focus_id=focus_id):
                self.assertIn(token, _blocks(block, "available")[0])
                self.assertNotIn(token, _blocks(block, "allow_branch")[0])

    def test_depth_focus_costs_and_ai_weights_are_bounded(self) -> None:
        for focus_id, expected in DEPTH_COSTS.items():
            block = self.blocks[focus_id]
            with self.subTest(focus_id=focus_id):
                self.assertEqual(_focus_cost(block), expected)
                self.assertIn(expected, {2, 3, 4})
                weight = _blocks(block, "ai_will_do")[0]
                base = re.search(r"\bbase\s*=\s*(\d+)", weight)
                self.assertIsNotNone(base)
                self.assertTrue(1 <= int(base.group(1)) <= 250)
                self.assertIn("modifier = {", weight)

    def test_permanent_depth_spirits_do_not_outlive_the_war(self) -> None:
        for idea_id in DEPTH_PERMANENT_IDEAS:
            with self.subTest(idea_id=idea_id):
                self.assertEqual(len(re.findall(rf"\badd_ideas\s*=\s*{re.escape(idea_id)}\b", self.source)), 1)
                for capstone_id in DEPTH_POSTWAR_CAPSTONES:
                    if idea_id in TVA_AGGREGATE_PREVIEWS:
                        self.assertNotIn(f"remove_ideas = {idea_id}", self.blocks[capstone_id])
                    else:
                        self.assertIn(f"remove_ideas = {idea_id}", self.blocks[capstone_id])
        for idea_id, (_focus_id, days) in DEPTH_TIMED_IDEAS.items():
            with self.subTest(idea_id=idea_id):
                self.assertLessEqual(days, 70)
                self.assertNotIn(f"remove_ideas = {idea_id}", self.source)

    def test_the_two_variants_of_a_claimant_take_different_ai_paths(self) -> None:
        pairs = (
            (
                "ADISCORD_vorkerland_wkr_neo_vorkerist_depth_plan",
                "ADISCORD_vorkerland_wkr_utilitarian_depth_plan",
            ),
            (
                "ADISCORD_vorkerland_vad_imperial_depth_plan",
                "ADISCORD_vorkerland_vad_joint_depth_war_plan",
            ),
            (
                "ADISCORD_vorkerland_tva_throughput_depth_plan",
                "ADISCORD_vorkerland_tva_preservation_depth_plan",
            ),
        )
        for left, right in pairs:
            with self.subTest(pair=(left, right)):
                left_order = set(DEPTH_AI_PLANS[left]["focuses"])
                right_order = set(DEPTH_AI_PLANS[right]["focuses"])
                self.assertLessEqual(len(left_order & right_order), 5)
                self.assertTrue(
                    left_order & DEPTH_LATE_WAR_FOCUSES,
                    "each variant plan must reach its late-war branch",
                )
                self.assertTrue(right_order & DEPTH_LATE_WAR_FOCUSES)


class WarEconomyDynamicModifiers(unittest.TestCase):
    """The war-economy branch has to stay driven by the monthly recompute.

    Converting a spirit to a dynamic modifier only buys anything if the
    variables keep moving. The failure this guards against is quiet: if the
    refresh stops writing a variable, or writes it only when a focus was taken,
    the modifier keeps loading and displaying and simply reads zero.
    """

    def setUp(self) -> None:
        self.blocks = focus_blocks(source_section(read(FOCUS_FILE), 'civil_war_focus'))
        self.modifiers = source_section(
            read(WAR_ECONOMY_MODIFIER_FILE), 'collapse_dynamic_modifiers'
        )
        self.refresh = source_section(
            read(WAR_ECONOMY_REFRESH_FILE), 'war_economy_effects'
        )

    def test_factory_scaled_claimants_have_one_war_economy_modifier(self) -> None:
        self.assertEqual({"WKR", "VAD"}, set(WAR_ECONOMY_DYNAMIC))
        modifiers = [modifier for _, modifier, _, _ in WAR_ECONOMY_DYNAMIC.values()]
        self.assertEqual(len(modifiers), len(set(modifiers)))
        for modifier in modifiers:
            with self.subTest(modifier=modifier):
                self.assertIn(f"{modifier} = {{", self.modifiers)

    def test_the_head_focus_applies_the_modifier(self) -> None:
        for tag, (head, modifier, _, _) in WAR_ECONOMY_DYNAMIC.items():
            with self.subTest(claimant=tag):
                self.assertIn(
                    f"add_dynamic_modifier = {{ modifier = {modifier} }}",
                    self.blocks[head],
                )

    def test_the_forks_no_longer_grant_static_spirits(self) -> None:
        # The pair used to add one spirit each. They now only set the flag the
        # refresh reads, so a stray add_ideas would mean two systems disagreeing
        # about the same trade-off.
        for tag, (_, _, strain_flag, relief_flag) in WAR_ECONOMY_DYNAMIC.items():
            for flag in (strain_flag, relief_flag):
                focus = next(
                    focus_id
                    for focus_id, block in self.blocks.items()
                    if f"set_country_flag = {flag}" in block
                )
                with self.subTest(claimant=tag, focus=focus):
                    reward = re.search(
                        r"completion_reward = \{(.*?)\n\t\t\}", self.blocks[focus], re.S
                    )
                    self.assertIsNotNone(reward)
                    self.assertNotIn("add_ideas", reward.group(1))

    def test_every_capstone_clears_every_war_economy(self) -> None:
        for capstone in WAR_ECONOMY_CAPSTONES:
            for _, modifier, _, _ in WAR_ECONOMY_DYNAMIC.values():
                with self.subTest(capstone=capstone, modifier=modifier):
                    self.assertIn(
                        f"remove_dynamic_modifier = {{ modifier = {modifier} }}",
                        self.blocks[capstone],
                    )

    def test_the_modifiers_read_variables_rather_than_constants(self) -> None:
        for _, modifier, _, _ in WAR_ECONOMY_DYNAMIC.values():
            body = re.search(
                rf"(?ms)^{re.escape(modifier)} = \{{(.*?)^\}}", self.modifiers
            ).group(1)
            fields = re.findall(r"(?m)^\t([a-z][a-z0-9_]*) = (\S+)$", body)
            values = [value for name, value in fields if name != "icon"]
            with self.subTest(modifier=modifier):
                self.assertGreaterEqual(len(values), 4)
                self.assertTrue(
                    all(value.startswith("ADISCORD_") for value in values),
                    f"{modifier} still carries a frozen constant: {values}",
                )

    def test_the_refresh_writes_every_variable_unconditionally(self) -> None:
        body = re.search(
            rf"(?ms)^{re.escape(WAR_ECONOMY_REFRESH_EFFECT)} = \{{(.*?)^\}}",
            self.refresh,
        ).group(1)

        top_level: set[str] = set()
        depth = 0
        for line in body.splitlines():
            if depth == 0:
                written = re.search(r"set_variable = \{ var = (ADISCORD_\w+)", line)
                if written:
                    top_level.add(written.group(1))
            depth += line.count("{") - line.count("}")

        for _, modifier, _, _ in WAR_ECONOMY_DYNAMIC.values():
            definition = re.search(
                rf"(?ms)^{re.escape(modifier)} = \{{(.*?)^\}}", self.modifiers
            ).group(1)
            for variable in re.findall(
                r"(?m)^\t[a-z][a-z0-9_]* = (ADISCORD_\w+)$", definition
            ):
                with self.subTest(modifier=modifier, variable=variable):
                    self.assertIn(variable, top_level)

    def test_the_refresh_reads_every_branch_flag(self) -> None:
        for tag, (_, _, strain_flag, relief_flag) in WAR_ECONOMY_DYNAMIC.items():
            for flag in (strain_flag, relief_flag):
                with self.subTest(claimant=tag, flag=flag):
                    self.assertIn(f"has_country_flag = {flag}", self.refresh)

    def test_the_refresh_performs_no_world_scan(self) -> None:
        # It runs every month for three countries for the whole war, and the
        # phase layer forbids scans for that reason.
        for scan in (
            "every_country",
            "any_country",
            "every_state",
            "any_state",
            "every_owned_state",
            "all_state",
            "random_country",
        ):
            with self.subTest(scan=scan):
                self.assertNotIn(scan, self.refresh)


class PrewarPreparationTests(unittest.TestCase):
    """Prewar reserve caches and the opening mandate they hand to claimants."""

    @classmethod
    def setUpClass(cls) -> None:
        from tools.validators import validate_adiscord_vorkerland_civil_war_focus as validator

        cls.validator = validator
        cls.blocks = focus_blocks(source_section(read(FOCUS_FILE), "civil_war_focus"))
        cls.effects = read(PHASE_EFFECTS_FILE)
        cls.triggers = read(Path("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"))
        cls.decisions = read(Path("common/decisions/ADISCORD_vorkerland_decisions.txt"))
        cls.events = read(CLAIMANT_EVENTS_FILE)

    def effect(self, name: str) -> str:
        definitions = _blocks(self.effects, name)
        self.assertEqual(len(definitions), 1, name)
        return definitions[0]

    def test_prewar_focuses_set_no_consumerless_markers(self) -> None:
        for focus_id in (*self.validator.PREWAR_WRK_FOCUSES, *self.validator.PREWAR_VAD_FOCUSES):
            with self.subTest(focus_id=focus_id):
                self.assertNotIn("ADISCORD_vorkerland_focus_", self.blocks[focus_id])
                self.assertNotIn("_hardline_committed", self.blocks[focus_id])

    def test_cache_recipients_follow_the_partition(self) -> None:
        tags = {
            "wkr": "WKR", "tva": "TVA", "vad": "VAD", "eyr": "EYR",
            "egc": "EGC", "riv": "RIV", "yor": "YOR",
        }
        initial_map = self.effect("ADISCORD_vorkerland_apply_initial_map")
        transfers: dict[str, set[str]] = {}
        for tag in tags.values():
            setup = _blocks(self.effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            source = setup[0] if setup else ""
            scopes = _blocks(initial_map, tag)
            source += "".join(scopes)
            transfers[tag] = set(re.findall(r"transfer_state = (\d+)", source)) - {"40"}
        recipients = self.effect("ADISCORD_vorkerland_reserve_cache_recipient_tt")
        listed: set[str] = set()
        for key, tag in tags.items():
            branch = next(
                scope for scope in re.split(r"\b(?:else_)?if = \{", recipients)
                if f"reserve_cache_to_{key}_tt" in scope
            )
            states = set(re.findall(r"state = (\d+)", branch))
            with self.subTest(recipient=tag):
                self.assertEqual(states, transfers[tag])
            listed |= states
        decision = _blocks(self.decisions, "ADISCORD_vorkerland_prewar_hide_reserves")[0]
        targets = re.search(r"targets = \{([^}]*)\}", decision)[1].split()
        self.assertEqual(set(targets), listed)
        self.assertEqual(len(targets), len(set(targets)))

    def test_cache_is_paid_once_and_settled_at_war_outbreak(self) -> None:
        decision = _blocks(self.decisions, "ADISCORD_vorkerland_prewar_hide_reserves")[0]
        self.assertIn("cost = 0", decision)
        self.assertIn("custom_cost_trigger = { ADISCORD_vorkerland_reserve_cache_affordable = yes }", decision)
        begin = self.effect("ADISCORD_vorkerland_begin_reserve_cache")
        self.assertEqual(begin.count("add_political_power = -25"), 1)
        self.assertEqual(begin.count("type = infantry_equipment amount = -1500"), 1)
        affordable = _blocks(self.triggers, "ADISCORD_vorkerland_reserve_cache_affordable")[0]
        self.assertIn("NOT = { has_political_power < 25 }", affordable)
        self.assertIn("NOT = { has_equipment = { infantry_equipment < 1500 } }", affordable)
        settle = self.effect("ADISCORD_vorkerland_settle_reserve_caches")
        self.assertIn("owner = {", settle)
        self.assertIn("clear_array = global.ADISCORD_vorkerland_reserve_caches", settle)
        outbreak = self.events[self.events.index("id = ADISCORD_vorkerland_collapse.2"):]
        self.assertEqual(self.events.count("ADISCORD_vorkerland_settle_reserve_caches = yes"), 1)
        self.assertLess(
            outbreak.index("ADISCORD_vorkerland_settle_reserve_caches = yes"),
            outbreak.index("ADISCORD_vorkerland_initialize_legitimacy = yes"),
        )

    def test_extra_cache_slots_belong_to_the_depot_focuses(self) -> None:
        slots = _blocks(self.triggers, "ADISCORD_vorkerland_reserve_cache_slot_free")[0]
        # The centre's caches are a capability of its tree; the districts name their own focus.
        self.assertIn("WRK_capability_extra_caches = yes", slots)
        self.assertIn("has_completed_focus = VAD_disperse_eastern_depots", slots)
        self.assertEqual(
            self.capability("WRK_capability_extra_caches"), ["WRK_disperse_railway_reserves"]
        )
        for focus_id in ("WRK_disperse_railway_reserves", "VAD_disperse_eastern_depots"):
            with self.subTest(focus_id=focus_id):
                self.assertIn("ADISCORD_vorkerland_reserve_cache_extra_slots_tt", self.blocks[focus_id])

    def capability(self, name: str) -> list[str]:
        """Focuses that grant one capability of the prewar preparation."""

        definition = _blocks(self.triggers, name)
        self.assertEqual(len(definition), 1, name)
        return re.findall(r"has_completed_focus = (\w+)", definition[0])

    def test_prewar_mandate_seeds_the_opening_legitimacy(self) -> None:
        initialize = self.effect("ADISCORD_vorkerland_initialize_legitimacy")
        # The heir holds the copied focus record, so legitimacy asks the capability.
        for capability, focus_id, value in (
            ("WRK_capability_council_mandate", "WRK_convene_council_of_republics", "0.10"),
            ("WRK_capability_charter_mandate", "WRK_bind_districts_to_charter", "0.05"),
        ):
            with self.subTest(focus_id=focus_id):
                self.assertIn(f"{capability} = yes", initialize)
                self.assertNotIn(f"has_completed_focus = {focus_id}", initialize)
                self.assertEqual(self.capability(capability), [focus_id])
                self.assertIn(f"value = {value} }}", initialize)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_prewar_compact_ratified", initialize)
        self.assertLess(
            initialize.index("ADISCORD_vorkerland_refresh_legitimacy_derived = yes"),
            initialize.index("add_dynamic_modifier"),
        )

    def test_archives_endorse_only_the_first_coalition(self) -> None:
        join = self.effect("ADISCORD_vorkerland_join_coalition_of_FROM")
        self.assertIn("has_completed_focus = VAD_secure_administrative_archives", join)
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_district_archives_endorsed }", join)
        self.assertEqual(join.count("set_country_flag = ADISCORD_vorkerland_district_archives_endorsed"), 1)

    def test_compact_payout_reaches_the_worker_claimant(self) -> None:
        carryover = self.effect(PREWAR_CARRYOVER_EFFECT)
        scope = next(
            block for block in _blocks(carryover, "if")
            if "WRK_capability_emergency_compact = yes" in block
        )
        self.assertEqual(
            self.capability("WRK_capability_emergency_compact"), ["WRK_offer_emergency_compact"]
        )
        self.assertIn("has_global_flag = ADISCORD_vorkerland_prewar_compact_ratified", scope)
        self.assertIn("amount = 5000 producer = WKR", scope)


class WorkerCouncilTests(unittest.TestCase):
    """WKR seats worker councils and trades their output for battalions."""

    SEATS = (
        "WKR_convene_front_soviets",
        "WKR_organize_factory_battalions",
        "WKR_put_railways_under_councils",
        "WKR_bind_workshops_to_directive",
        "WKR_seat_the_factory_councils",
        "WKR_convene_the_production_soviet",
    )

    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks = focus_blocks(source_section(read(FOCUS_FILE), "civil_war_focus"))
        cls.effects = read(PHASE_EFFECTS_FILE)
        cls.decisions = read(Path("common/decisions/ADISCORD_vorkerland_decisions.txt"))
        cls.modifiers = read(Path("common/dynamic_modifiers/ADISCORD_vorkerland_dynamic_modifiers.txt"))
        cls.ideas = read(Path("common/ideas/ADISCORD_vorkerland_ideas.txt"))

    def test_each_leader_route_seats_at_most_five_councils(self) -> None:
        for focus_id in self.SEATS:
            with self.subTest(focus_id=focus_id):
                reward = _blocks(self.blocks[focus_id], "completion_reward")[0]
                self.assertEqual(reward.count("ADISCORD_vorkerland_wkr_seat_council = yes"), 1)
        nikita = set(self.SEATS) - {"WKR_bind_workshops_to_directive"}
        anton = set(self.SEATS) - {"WKR_convene_front_soviets"}
        self.assertEqual(max(len(nikita), len(anton)), 5)
        self.assertNotIn("ADISCORD_vorkerland_wkr_mobilize_all_councils", self.effects)
        batch = self.blocks["WKR_requisition_in_the_republics_name"]
        self.assertIn("unlock_decision_tooltip = WKR_mobilize_factory_columns", batch)
        self.assertNotIn("ADISCORD_vorkerland_wkr_council_battalion = yes", batch)

    def test_dummy_previews_match_the_refreshed_aggregate(self) -> None:
        refresh = _blocks(self.effects, "ADISCORD_vorkerland_wkr_refresh_councils")[0]
        seated = _blocks(self.ideas, "ADISCORD_vorkerland_wkr_council_seated_dummy")[0]
        mobilized = _blocks(self.ideas, "ADISCORD_vorkerland_wkr_council_mobilized_dummy")[0]
        self.assertIn("var = ADISCORD_vorkerland_wkr_council_output value = 0.03", refresh)
        self.assertIn("var = ADISCORD_vorkerland_wkr_council_stability value = 0.01", refresh)
        self.assertIn("var = ADISCORD_vorkerland_wkr_council_conscription value = 0.004", refresh)
        self.assertIn("industrial_capacity_factory = 0.03", seated)
        self.assertIn("stability_factor = 0.01", seated)
        self.assertIn("industrial_capacity_factory = -0.03", mobilized)
        self.assertIn("conscription = 0.004", mobilized)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", refresh)
        aggregate = _blocks(self.modifiers, "ADISCORD_vorkerland_wkr_councils")[0]
        for field in ("industrial_capacity_factory", "stability_factor", "conscription"):
            self.assertIn(field, aggregate)

    def test_mobilisation_reserves_the_council_before_delivery(self) -> None:
        decision = _blocks(self.decisions, "ADISCORD_vorkerland_wkr_mobilize_council")[0]
        complete = _blocks(decision, "complete_effect")[0]
        self.assertIn("WKR_begin_council_order = yes", complete)
        begin = _blocks(self.effects, "WKR_begin_council_order")[0]
        self.assertIn("ADISCORD_vorkerland_wkr_withdraw_council = yes", begin)
        self.assertIn("ADISCORD_vorkerland_wkr_has_working_council = yes", _blocks(decision, "available")[0])
        self.assertIn("WKR_finish_council_order = yes", _blocks(decision, "remove_effect")[0])
        self.assertIn("has_completed_focus = WKR_organize_factory_battalions", decision)

    def test_council_aggregate_is_cleared_with_the_war(self) -> None:
        clear = _blocks(self.effects, "ADISCORD_vorkerland_clear_claimant_war_modifiers")[0]
        self.assertIn(
            "if = { limit = { has_dynamic_modifier = { modifier = ADISCORD_vorkerland_wkr_councils } } "
            "remove_dynamic_modifier = { modifier = ADISCORD_vorkerland_wkr_councils } }",
            clear,
        )


class DistrictOathTests(unittest.TestCase):
    """VAD trades legitimacy and men through one oath per central district."""

    DECISIONS = (
        "ADISCORD_vorkerland_vad_grant_district_charter",
        "ADISCORD_vorkerland_vad_impose_commandant_rule",
    )

    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks = focus_blocks(source_section(read(FOCUS_FILE), "civil_war_focus"))
        cls.effects = read(PHASE_EFFECTS_FILE)
        cls.decisions = read(Path("common/decisions/ADISCORD_vorkerland_decisions.txt"))

    def test_both_oaths_share_one_state_lock_and_target_list(self) -> None:
        targets = set()
        triggers = read(Path("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"))
        lock = _blocks(triggers, "VAD_oath_target_free")[0]
        self.assertIn("NOT = { has_state_flag = ADISCORD_vorkerland_vad_district_oath }", lock)
        self.assertIn("NOT = { has_state_flag = VAD_oath_in_progress }", lock)
        self.assertIn("NOT = { has_variable = VAD_oath_pp }", _blocks(triggers, "VAD_oath_slot_free")[0])
        for decision_id in self.DECISIONS:
            decision = _blocks(self.decisions, decision_id)[0]
            with self.subTest(decision=decision_id):
                self.assertIn("VAD_oath_target_free = yes", _blocks(decision, "available")[0])
                self.assertIn("VAD_oath_slot_free = yes", _blocks(decision, "available")[0])
                self.assertNotIn("has_state_flag", _blocks(decision, "target_trigger")[0])
                self.assertIn("VAD_refund_oath = yes", _blocks(decision, "cancel_effect")[0])
                targets.add(re.search(r"targets = \{([^}]*)\}", decision)[1].strip())
        self.assertEqual(len(targets), 1)

    def test_oaths_move_legitimacy_in_opposite_directions(self) -> None:
        charter = _blocks(self.effects, "ADISCORD_vorkerland_vad_seal_district_charter")[0]
        commandant = _blocks(self.effects, "ADISCORD_vorkerland_vad_seal_commandant_rule")[0]
        self.assertIn("ADISCORD_vorkerland_legitimacy_delta = 0.03", charter)
        self.assertIn("ADISCORD_vorkerland_legitimacy_delta = -0.02", commandant)
        self.assertIn("id = VAD_bop value = 0.15", charter)
        self.assertIn("id = VAD_bop value = -0.15", commandant)
        self.assertNotIn("add_manpower", commandant)
        self.assertNotIn("add_equipment_to_stockpile", commandant)

    def test_oath_modifiers_end_with_the_civil_war(self) -> None:
        retire = _blocks(self.effects, "ADISCORD_vorkerland_retire_civil_war_modifiers")[0]
        self.assertEqual(retire.count("ADISCORD_vorkerland_vad_retire_district_oaths = yes"), 1)
        oaths = _blocks(self.effects, "ADISCORD_vorkerland_vad_retire_district_oaths")[0]
        for modifier in ("ADISCORD_vorkerland_vad_chartered_district", "ADISCORD_vorkerland_vad_commandant_district"):
            self.assertIn(f"limit = {{ has_dynamic_modifier = {{ modifier = {modifier} }} }}", oaths)
        self.assertIn("clear_array = global.ADISCORD_vorkerland_vad_oath_states", oaths)

    def test_focuses_unlock_the_matching_oath(self) -> None:
        for focus_id, decision_id in (
            ("VAD_open_imperial_registers", "ADISCORD_vorkerland_vad_grant_district_charter"),
            ("VAD_form_field_commandantures", "ADISCORD_vorkerland_vad_impose_commandant_rule"),
        ):
            with self.subTest(focus_id=focus_id):
                self.assertIn(f"unlock_decision_tooltip = {decision_id}", self.blocks[focus_id])
                self.assertIn(f"has_completed_focus = {focus_id}", _blocks(self.decisions, decision_id)[0])


class CentralOutcomeRecheckTests(unittest.TestCase):
    """A capitulation must not leave the central victory waiting for a new war."""

    def test_capitulation_queues_one_deferred_outcome_check(self) -> None:
        peace = read(Path("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"))
        section = peace[peace.index("# BEGIN vorkerland_collapse:on_capitulation\n"):peace.index("# END vorkerland_collapse:on_capitulation\n")]
        self.assertLess(
            section.index("ADISCORD_vorkerland_check_central_outcome = yes"),
            section.index("ADISCORD_vorkerland_schedule_outcome_recheck = yes"),
        )
        schedule = _blocks(read(PHASE_EFFECTS_FILE), "ADISCORD_vorkerland_schedule_outcome_recheck")[0]
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_outcome_recheck_pending }", schedule)
        self.assertEqual(schedule.count("id = ADISCORD_vorkerland_collapse.102 days = 1"), 3)
        events = read(CLAIMANT_EVENTS_FILE)
        recheck = events[events.index("id = ADISCORD_vorkerland_collapse.102"):]
        recheck = recheck[:recheck.index("\n}\n")]
        self.assertIn("clr_global_flag = ADISCORD_vorkerland_outcome_recheck_pending", recheck)
        self.assertIn("ADISCORD_vorkerland_check_central_outcome = yes", recheck)


class FieldTrialTests(unittest.TestCase):
    """TVA field trials: a paid risk whose odds improve with every iteration."""

    ITERATION_FOCUSES = (
        "TVA_integrate_field_results",
        "TVA_cross_validate_trial_logs",
        "TVA_delegate_to_algorithmic_board",
    )

    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks = focus_blocks(source_section(read(FOCUS_FILE), "civil_war_focus"))
        cls.effects = read(PHASE_EFFECTS_FILE)
        cls.decisions = read(Path("common/decisions/ADISCORD_vorkerland_decisions.txt"))
        cls.triggers = read(Path("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"))

    def test_trial_uses_the_probability_paid_for_at_start(self) -> None:
        resolve = _blocks(self.effects, "ADISCORD_vorkerland_tva_resolve_field_trial")[0]
        begin = _blocks(self.effects, "ADISCORD_vorkerland_tva_begin_field_trial")[0]
        self.assertIn("var = TVA_trial_chance value = TVA_trial_success_chance", begin)
        self.assertIn("TVA_trial_chance = { ADISCORD_vorkerland_tva_field_trial_success = yes }", resolve)
        self.assertIn("TVA_trial_failure_chance = { ADISCORD_vorkerland_tva_field_trial_failure = yes }", resolve)
        self.assertEqual(resolve.count("ADISCORD_vorkerland_tva_add_iteration = yes"), 1)

    def test_price_is_checked_and_debited_once(self) -> None:
        decision = _blocks(self.decisions, "ADISCORD_vorkerland_tva_run_field_trial")[0]
        self.assertIn("cost = 0", decision)
        self.assertIn("ADISCORD_vorkerland_tva_trial_affordable = yes", decision)
        begin = _blocks(self.effects, "ADISCORD_vorkerland_tva_begin_field_trial")[0]
        self.assertEqual(begin.count("add_political_power = TVA_trial_price_pp"), 1)
        self.assertEqual(begin.count("type = infantry_equipment amount = TVA_trial_price_rifles"), 1)
        affordable = _blocks(self.triggers, "ADISCORD_vorkerland_tva_trial_affordable")[0]
        self.assertIn("NOT = { has_political_power < 30 }", affordable)
        self.assertIn("NOT = { has_equipment = { infantry_equipment < 9000 } }", affordable)

    def test_bonus_follows_the_committed_protocol(self) -> None:
        success = _blocks(self.effects, "ADISCORD_vorkerland_tva_field_trial_success")[0]
        for protocol, category in (
            ("battalion", "infantry_weapons"),
            ("fire_control", "electronics"),
            ("logistics", "support_tech"),
        ):
            with self.subTest(protocol=protocol):
                branch = success[success.index(f"TVA_trial_is_{protocol} = yes"):]
                self.assertIn(f"category = {category}", branch[:branch.index("}\n\t}")])

    def test_focuses_contribute_iterations(self) -> None:
        for focus_id in self.ITERATION_FOCUSES:
            with self.subTest(focus_id=focus_id):
                reward = _blocks(self.blocks[focus_id], "completion_reward")[0]
                self.assertEqual(reward.count("ADISCORD_vorkerland_tva_add_iteration = yes"), 1)
        self.assertIn(
            "unlock_decision_tooltip = ADISCORD_vorkerland_tva_run_field_trial",
            self.blocks["TVA_select_trial_protocol"],
        )


class WarLegacyTests(unittest.TestCase):
    """The winning claimant's war systems carry into the reunified settlement."""

    ROUTES = {
        "ADISCORD_vorkerland_settle_unification_under_wkr": ("WKR", "ADISCORD_vorkerland_pw_record_worker_councils"),
        "ADISCORD_vorkerland_settle_unification_under_vad": ("VAD", "ADISCORD_vorkerland_pw_record_district_oaths"),
        "ADISCORD_vorkerland_settle_unification_under_tva": ("TVA", "ADISCORD_vorkerland_pw_record_trial_iterations"),
    }
    CONSUMERS = {
        "WRK_worker_convene_reunification_congress": "ADISCORD_vorkerland_pw_council_output",
        "WRK_worker_authorize_homecoming_commissions": "ADISCORD_vorkerland_pw_council_veterans",
        "WRK_joint_pw_local_charters": "ADISCORD_vorkerland_pw_charter_construction",
        "WRK_joint_publish_amnesty_registers": "ADISCORD_vorkerland_pw_amnesty_manpower",
        "WRK_utilitarian_expand_national_laboratories": "ADISCORD_vorkerland_pw_iteration_efficiency",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.blocks = focus_blocks(source_section(read(FOCUS_FILE), "civil_war_focus"))
        cls.effects = read(PHASE_EFFECTS_FILE)

    def test_legacy_is_recorded_once_on_the_surviving_winner(self) -> None:
        for settlement, (tag, record) in self.ROUTES.items():
            with self.subTest(settlement=settlement):
                body = _blocks(self.effects, settlement)[0]
                # The settlement runs on the winner, whose own war systems the
                # record reads; the winner is never annexed, so they stay readable.
                self.assertEqual(body.count(f"{record} = yes"), 1)
                guards = [
                    block for block in _blocks(body, "if") if f"{record} = yes" in block
                ]
                self.assertEqual(len(guards), 1)
                self.assertIn(f"country_exists = {tag}", guards[0])
                self.assertNotRegex(
                    body, rf"annex_country\s*=\s*\{{\s*target\s*=\s*{tag}\b"
                )
                sources = set(
                    re.findall(
                        r"\bvalue\s*=\s*([A-Z]{3})\.", _blocks(self.effects, record)[0]
                    )
                )
                self.assertEqual(sources, {tag})

    def test_each_recorded_delta_has_one_settlement_consumer(self) -> None:
        recorded = "".join(
            _blocks(self.effects, record)[0] for _, record in self.ROUTES.values()
        )
        for focus_id, variable in self.CONSUMERS.items():
            with self.subTest(focus_id=focus_id):
                self.assertIn(f"var = {variable} value =", recorded)
                reward = _blocks(self.blocks[focus_id], "completion_reward")[0]
                applied = reward.count(f"value = {variable} }}") + reward.count(f"var:{variable} ")
                self.assertEqual(applied, 1)
                self.assertIn(f"custom_effect_tooltip = {variable}_tt", reward)

    def test_commandant_rule_is_counted_for_the_amnesty(self) -> None:
        seal = _blocks(self.effects, "ADISCORD_vorkerland_vad_seal_commandant_rule")[0]
        self.assertIn("add_to_variable = { var = ADISCORD_vorkerland_vad_commandants value = 1 }", seal)
        iterations = _blocks(self.effects, "ADISCORD_vorkerland_pw_record_trial_iterations")[0]
        self.assertIn("max = 8", iterations)


def settlement_script_class():
    """Simulator of the preparation suite, extended for the postwar worker route.

    This slice runs from source; other subsystems and native calls are
    recorded at their boundary.
    """

    from tools.tests.test_vorkerland_preparation import EFFECTS, Script, V, fields

    class SettlementScript(Script):
        EXPANDED = ("WRK_executive_", V + "worker_", V + "pw_ensure_institutions")
        RECORDED = (
            "ADISCORD_reform_",
            "ADISCORD_increase_",
            "ADISCORD_west_push_lean",
            V + "restore_unity_tower",
            V + "schedule_route_tree",
        )

        def run(self, block, current=None, previous=None):
            current = current or self.root
            translated = []
            for key, operator, value in block:
                if key in EFFECTS and key.startswith(self.EXPANDED):
                    translated.append(("hidden_effect", "=", EFFECTS[key]))
                elif key.startswith(self.RECORDED):
                    self.calls.append((key, current, value))
                elif key == "add_extra_state_shared_building_slots":
                    # A shared slot serves either kind of factory. Earlier
                    # effects of the block run first, as in the engine.
                    super().run(translated, current, previous)
                    translated = []
                    state = self.scopes[current]
                    state.variables["shared_building_slots"] = (
                        state.variables.get("shared_building_slots", 0) + float(value)
                    )
                    for building in ("industrial_complex", "arms_factory"):
                        state.resources[building + "_slots"] += float(value)
                elif key == "add_ideas":
                    translated.append(("set_country_flag", "=", value))
                elif key == "random_owned_controlled_state":
                    # The engine picks any matching region; the fixture takes
                    # the first so that the result is repeatable.
                    limit = fields(value).get("limit", [])
                    body = [item for item in value if item[0] != "limit"]
                    held = sorted(
                        name
                        for name, scope in self.scopes.items()
                        if name.isdigit() and scope.owner == scope.controller == current
                    )
                    for name in held:
                        if self.conditions(limit, name, current):
                            translated.append((name, "=", body))
                            break
                else:
                    translated.append((key, operator, value))
            super().run(translated, current, previous)

    return SettlementScript


def start_programme(script, nation: str, decision: dict, target: str | None = None) -> bool:
    """Place a paid programme the way the engine does: gates, one native debit, effect."""

    country = script.scopes[nation]
    gates = [decision["visible"], decision["available"]]
    if "state_target" in decision:
        assert target in [value for _key, _op, value in decision["targets"]], target
        script.source = target
        gates += [decision["target_root_trigger"], decision["target_trigger"]]
    if not all(script.conditions(gate) for gate in gates):
        return False
    price = float(decision["cost"])
    if country.resources["pp"] < price:
        return False
    country.resources["pp"] -= price
    script.run(decision["complete_effect"])
    return True


class WorkerSettlementTests(unittest.TestCase):
    """Execute the worker settlement rewards and paid programmes from source.

    The native decision cost is an engine boundary: the fixture debits it once
    when a programme starts and the scripts only keep its receipt.
    """

    NATION = "WKR"
    SITE = "201"
    OTHER_SITE = "32"
    WORKS = "ADISCORD_vorkerland_worker_cooperative_works"
    WORKS_RECEIPT = "ADISCORD_vorkerland_worker_works_deposit"
    ORDER_RECEIPT = "WRK_executive_order_deposit"
    ORDERS = (
        "WRK_executive_norm_order",
        "WRK_executive_republic_contract",
        "WRK_executive_district_audit",
    )

    @classmethod
    def setUpClass(cls) -> None:
        from tools.tests.test_vorkerland_preparation import V, fields, parse, walk

        cls.Script = settlement_script_class()
        cls.V = V
        cls.fields = staticmethod(fields)
        cls.blocks = focus_blocks(source_section(read(FOCUS_FILE), "civil_war_focus"))
        cls.grid = resolved_positions(cls.blocks)
        cls.worker_route = POSTWAR_ROUTE_FOCUSES[POSTWAR_EXECUTIVE_ROUTE]
        cls.settlement = (*cls.worker_route, *POSTWAR_EXECUTIVE_FOCUSES)
        source = read(Path("focus_trees/Vorkerland/settlement/focuses.txt"))
        cls.focuses = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(source))
            if key == "focus" and isinstance(value, list)
        }
        cls.decision_source = read(DIPLOMACY_DECISIONS_FILE)
        operations = fields(parse(cls.decision_source))[V + "focus_operations_category"]
        operations = fields(operations)
        cls.programmes = {
            decision: fields(operations[decision])
            for decision, _flag, _receipt in SETTLEMENT_PROGRAMMES.values()
        }
        cls.ideas = read(COLLAPSE_IDEAS_FILE)
        cls.dynamic = read(SETTLEMENT_AGGREGATE_FILE)
        cls.aggregate = settlement_aggregate_fields(cls.dynamic)
        cls.plans = read(WKR_AI_PLAN_FILE)

    def campaign(self, executive: bool = True):
        V = self.V
        script = self.Script()
        script.root = self.NATION
        script.globals = {
            V + "phase_postwar_integration",
            V + "reunification_verified",
            V + "collapse_finished",
        }
        script.event_targets["ADISCORD_vorkerland_nation"] = self.NATION
        country = script.scopes[self.NATION]
        country.resources.clear()
        country.resources["pp"] = 200
        country.flags.update({POSTWAR_EXECUTIVE_ROUTE, V + "central_unifier"})
        if executive:
            country.flags.add(POSTWAR_EXECUTIVE_GATE)
        for _focus, (_decision, flag, _receipt) in SETTLEMENT_PROGRAMMES.items():
            country.flags.add(flag)
        for state in (self.SITE, self.OTHER_SITE, "40", "200"):
            scope = script.scopes[state]
            scope.owner = scope.controller = self.NATION
            scope.resources.update(industrial_complex_slots=1, infrastructure_slots=1)
        return script

    def start(self, script, name: str, target: str | None = None) -> bool:
        return start_programme(script, self.NATION, self.programmes[name], target)

    def target(self, name: str) -> str | None:
        return self.SITE if "state_target" in self.programmes[name] else None

    def assert_order_closed(self, script) -> None:
        country = script.scopes[self.NATION]
        self.assertNotIn(self.ORDER_RECEIPT, country.variables)
        self.assertFalse({flag for flag in country.flags if flag.endswith("_pending")})
        for state in (self.SITE, self.OTHER_SITE):
            self.assertNotIn("WRK_executive_order_site", script.scopes[state].flags)

    def test_committee_branch_is_drawn_only_for_the_executive_government(self) -> None:
        for executive in (True, False):
            script = self.campaign(executive)
            visible = {
                name
                for name, focus in self.focuses.items()
                if script.conditions(focus["allow_branch"])
            }
            expected = set(self.worker_route)
            if executive:
                expected |= set(POSTWAR_EXECUTIVE_FOCUSES)
            self.assertEqual(visible, expected, executive)
        # The congress government completes its route without the committee.
        committee = set(POSTWAR_EXECUTIVE_FOCUSES)
        for focus_id in self.worker_route:
            self.assertFalse(_prerequisites(self.blocks[focus_id]) & committee, focus_id)
        paths = _postwar_completion_paths(
            self.blocks, self.worker_route, POSTWAR_ROUTE_TERMINALS[POSTWAR_EXECUTIVE_ROUTE]
        )
        self.assertEqual({len(path) for path in paths}, {10})

    def test_committee_branch_is_a_choice_that_rejoins_and_fits_before_the_tower(self) -> None:
        left, right = POSTWAR_EXECUTIVE_CHOICE
        self.assertEqual(_mutually_exclusive_focuses(self.blocks[left]), {right})
        self.assertEqual(_mutually_exclusive_focuses(self.blocks[right]), {left})
        rejoin = [
            focus_id
            for focus_id in POSTWAR_EXECUTIVE_FOCUSES
            if frozenset({left, right}) in _prerequisite_groups(self.blocks[focus_id])
        ]
        self.assertEqual(rejoin, ["WRK_executive_audit_the_districts"])
        # Each alternative opens its own programme and neither repeats the other.
        self.assertIn(left, SETTLEMENT_PROGRAMMES)
        self.assertIn(right, SETTLEMENT_PROGRAMMES)
        self.assertNotEqual(
            settlement_reward_classes(self.blocks[left]),
            settlement_reward_classes(self.blocks[right]),
        )
        self.assertEqual(settlement_free_path_units(self.blocks), 16)
        cells = [self.grid[focus_id] for focus_id in self.settlement]
        self.assertEqual(len(cells), len(set(cells)))
        self.assertEqual(
            {focus_id: self.grid[focus_id] for focus_id in POSTWAR_EXECUTIVE_FOCUSES},
            POSTWAR_EXECUTIVE_POSITIONS,
        )
        tower = self.focuses[POSTWAR_ROUTE_TERMINALS[POSTWAR_EXECUTIVE_ROUTE]]
        script = self.campaign()
        weight = self.fields(tower["ai_will_do"])["modifier"]
        conditions = [item for item in weight if item[0] != "factor"]
        self.assertEqual(self.fields(weight)["factor"], "0")
        self.assertTrue(script.conditions(conditions))
        script.scopes[self.NATION].focuses.add(POSTWAR_EXECUTIVE_FINAL)
        self.assertFalse(script.conditions(conditions))
        self.assertFalse(self.campaign(executive=False).conditions(conditions))

    def test_every_settlement_focus_pays_two_substantive_rewards(self) -> None:
        for focus_id in self.settlement:
            with self.subTest(focus_id=focus_id):
                self.assertGreaterEqual(
                    len(settlement_reward_classes(self.blocks[focus_id])), 2
                )
        token = (
            "focus = {\n\tcompletion_reward = {\n\t\tadd_political_power = 5\n"
            "\t\tadd_stability = 0.01\n\t}\n}"
        )
        self.assertEqual(settlement_reward_classes(token), set())

    def test_aggregate_previews_equal_the_executed_change(self) -> None:
        V = self.V
        council_output = V + "pw_council_output"
        changed = 0
        for focus_id in self.settlement:
            with self.subTest(focus_id=focus_id):
                script = self.campaign()
                country = script.scopes[self.NATION]
                country.variables[council_output] = 0.06
                country.flags.update({V + "erased_nations", V + "erased_nations_relief_1"})
                before = dict(country.variables)
                script.run(self.focuses[focus_id]["completion_reward"])
                executed = {
                    modifier: round(
                        country.variables.get(variable, 0) - before.get(variable, 0), 6
                    )
                    for variable, modifier in self.aggregate.items()
                    if country.variables.get(variable, 0) != before.get(variable, 0)
                }
                applied, shown, defects = settlement_aggregate_delta(
                    self.blocks[focus_id], self.aggregate, self.ideas
                )
                self.assertEqual(defects, [])
                self.assertEqual(applied, shown)
                expected = dict(shown)
                if focus_id == "WRK_worker_convene_reunification_congress":
                    # The councils' own share is shown by its dedicated tooltip.
                    expected["industrial_capacity_factory"] = 0.06
                self.assertEqual(executed, expected)
                if executed:
                    changed += 1
                    self.assertIn(V + "postwar_institutions", country.flags)
                # A preview idea is shown, never installed.
                self.assertFalse(
                    {flag for flag in country.flags if flag.startswith(V + "pw_delta_")}
                )
        self.assertEqual(changed, 9)

    def test_treasury_tooltips_state_the_executed_amount(self) -> None:
        treasury = "ADISCORD_economy_treasury"
        ledger = "ADISCORD_economy_current_month_action_income"
        for focus_id, tooltip in (
            ("WRK_worker_ratify_republican_compact", "WRK_worker_compact_fund_tt"),
            ("WRK_executive_audit_the_districts", "WRK_executive_audit_recovery_tt"),
        ):
            script = self.campaign()
            country = script.scopes[self.NATION]
            script.run(self.focuses[focus_id]["completion_reward"])
            amount = country.variables[treasury]
            self.assertGreater(amount, 0)
            # The monthly ledger records the same receipt.
            self.assertEqual(country.variables[ledger], amount)
            self.assertIn(f"custom_effect_tooltip = {tooltip}", self.blocks[focus_id])
            for path in (ENGLISH_LOCALISATION, RUSSIAN_LOCALISATION):
                value = localisation_entries(read(path))[tooltip]
                self.assertIn(
                    f"§G+{amount:g}§! £ADISCORD_economy_treasury_texticon", value, (path, tooltip)
                )

    def test_orders_charge_the_native_price_once_and_share_one_receipt(self) -> None:
        for name in self.ORDERS:
            with self.subTest(name=name):
                script = self.campaign()
                country = script.scopes[self.NATION]
                price = float(self.programmes[name]["cost"])
                self.assertTrue(self.start(script, name, self.target(name)))
                self.assertEqual(country.resources["pp"], 200 - price)
                self.assertEqual(country.variables[self.ORDER_RECEIPT], price)
                paid = deepcopy(script.scopes)
                for other in self.ORDERS:
                    other_target = (
                        self.OTHER_SITE if "state_target" in self.programmes[other] else None
                    )
                    self.assertFalse(self.start(script, other, other_target), other)
                    self.assertEqual(script.scopes, paid)
                # The congress government and a locked programme get no order.
                self.assertFalse(
                    self.start(self.campaign(executive=False), name, self.target(name))
                )
                locked = self.campaign()
                flag = next(
                    flag
                    for decision, flag, _receipt in SETTLEMENT_PROGRAMMES.values()
                    if decision == name
                )
                locked.scopes[self.NATION].flags.discard(flag)
                self.assertFalse(self.start(locked, name, self.target(name)))

    def test_delivery_equals_the_preview_and_closes_the_receipt(self) -> None:
        delivered = {
            # The order brings its own slot and fills it; the old one stays free.
            "WRK_executive_norm_order": ({}, {"industrial_complex": 1, "industrial_complex_slots": 1}, 1),
            "WRK_executive_republic_contract": (
                {"infantry_equipment": 5000, "support_equipment": 150}, {}, 0,
            ),
            "WRK_executive_district_audit": ({"infantry_equipment": 600}, {}, 1),
        }
        for name in self.ORDERS:
            with self.subTest(name=name):
                decision = self.programmes[name]
                script = self.campaign()
                country = script.scopes[self.NATION]
                site = script.scopes[self.SITE]
                self.assertTrue(self.start(script, name, self.target(name)))
                paid = country.resources["pp"]
                preview = deepcopy(script)
                preview.run(self.fields(decision["complete_effect"])["effect_tooltip"])
                script.run(decision["remove_effect"])
                for scope in (self.NATION, self.SITE):
                    self.assertEqual(
                        dict(script.scopes[scope].resources),
                        dict(preview.scopes[scope].resources),
                    )
                self.assertEqual(
                    site.variables.get("shared_building_slots", 0),
                    preview.scopes[self.SITE].variables.get("shared_building_slots", 0),
                )
                gained, built, slots = delivered[name]
                for resource, amount in gained.items():
                    self.assertEqual(country.resources[resource], amount)
                for resource, amount in built.items():
                    self.assertEqual(site.resources[resource], amount)
                self.assertEqual(site.variables.get("shared_building_slots", 0), slots)
                self.assertEqual(country.resources["pp"], paid)
                self.assert_order_closed(script)
                settled = deepcopy(script.scopes)
                script.run(decision["remove_effect"])
                script.run(decision["cancel_effect"])
                self.assertEqual(script.scopes, settled)
        script = self.campaign()
        self.assertTrue(self.start(script, "WRK_executive_republic_contract"))
        script.scopes["TRU"].enemies.add(self.NATION)
        script.run(self.programmes["WRK_executive_republic_contract"]["remove_effect"])
        leans = [scope for key, scope, _ in script.calls if key == "ADISCORD_west_push_lean"]
        self.assertEqual(leans, ["ROM"])
        self.assertEqual(script.scopes[self.NATION].variables["ADISCORD_west_push"], 5)

    def test_each_region_is_audited_once(self) -> None:
        audit = "WRK_executive_district_audit"
        script = self.campaign()
        self.assertTrue(self.start(script, audit, self.SITE))
        script.run(self.programmes[audit]["remove_effect"])
        self.assertIn("WRK_executive_district_audited", script.scopes[self.SITE].flags)
        self.assertFalse(self.start(script, audit, self.SITE))
        self.assertTrue(self.start(script, audit, self.OTHER_SITE))

    def test_cancellation_and_a_failed_delivery_refund_the_price_exactly_once(self) -> None:
        causes = ("subject", "capitulation", "site_lost", "no_room")
        for name, cause, callback in product(
            self.ORDERS, causes, ("cancel_effect", "remove_effect")
        ):
            decision = self.programmes[name]
            targeted = "state_target" in decision
            if cause == "site_lost" and not targeted:
                continue
            if cause == "no_room" and (name != "WRK_executive_norm_order" or callback != "remove_effect"):
                continue
            with self.subTest(name=name, cause=cause, callback=callback):
                script = self.campaign()
                country = script.scopes[self.NATION]
                site = script.scopes[self.SITE]
                self.assertTrue(self.start(script, name, self.target(name)))
                self.assertLess(country.resources["pp"], 200)
                if cause == "subject":
                    country.subject = "IVN"
                elif cause == "capitulation":
                    country.capitulated = True
                elif cause == "site_lost":
                    site.controller = "IVN"
                else:
                    site.resources["industrial_complex_slots"] = 0
                if cause != "no_room":
                    self.assertTrue(script.conditions(decision["cancel_trigger"]))
                script.run(decision[callback])
                script.run(decision[callback])
                script.run(decision["cancel_effect"])
                self.assertEqual(country.resources["pp"], 200)
                self.assert_order_closed(script)
                self.assertEqual(country.resources["infantry_equipment"], 0)
                self.assertEqual(site.resources["industrial_complex"], 0)
                self.assertEqual(site.variables.get("shared_building_slots", 0), 0)
                self.assertNotIn("WRK_executive_district_audited", site.flags)
                self.assertNotIn("WRK_executive_norm_built", site.flags)

    def test_norm_orders_build_one_plant_per_region(self) -> None:
        norm = "WRK_executive_norm_order"
        decision = self.programmes[norm]
        script = self.campaign()
        country = script.scopes[self.NATION]
        site = script.scopes[self.SITE]
        country.resources["pp"] = 1000
        self.assertTrue(self.start(script, norm, self.SITE))
        script.run(decision["remove_effect"])
        self.assertIn("WRK_executive_norm_built", site.flags)
        self.assertEqual(site.resources["industrial_complex"], 1)
        # The order brought its own slot, yet the region is closed for good.
        site.resources["industrial_complex_slots"] = 5
        self.assertFalse(self.start(script, norm, self.SITE))
        self.assertEqual(country.resources["pp"], 950)
        self.assertTrue(self.start(script, norm, self.OTHER_SITE))
        script.run(decision["remove_effect"])
        self.assertEqual(script.scopes[self.OTHER_SITE].resources["industrial_complex"], 1)
        self.assertFalse(self.start(script, norm, self.OTHER_SITE))
        # A refunded order leaves the region open.
        retry = self.campaign()
        self.assertTrue(self.start(retry, norm, self.SITE))
        retry.scopes[self.SITE].controller = "IVN"
        retry.run(decision["cancel_effect"])
        retry.scopes[self.SITE].controller = self.NATION
        self.assertTrue(self.start(retry, norm, self.SITE))

    def test_state_orders_keep_slot_tests_out_of_the_cached_target_list(self) -> None:
        from tools.tests.test_vorkerland_preparation import TRIGGERS, walk

        effects = read(PHASE_EFFECTS_FILE)
        triggers = read(COMMITTEE_TRIGGER_FILE)
        self.assertEqual(committee_order_issues(self.decision_source, effects, triggers), [])
        for decision_id, (site, _finish, done_flag) in COMMITTEE_STATE_ORDERS.items():
            with self.subTest(decision_id=decision_id):
                cached = [key for key, _op, _value in walk(TRIGGERS[site])]
                self.assertNotIn("free_building_slots", cached)
                self.assertIn("is_owned_and_controlled_by", cached)
                self.assertIn(done_flag, [value for _key, _op, value in walk(TRIGGERS[site])])
        # A norm order with no room is refused when it is placed, with a reason.
        norm = self.programmes["WRK_executive_norm_order"]
        self.assertIn("WRK_executive_norm_room_tt", [value for _k, _o, value in walk(norm["available"])])
        script = self.campaign()
        script.scopes[self.SITE].resources["industrial_complex_slots"] = 0
        script.source = self.SITE
        self.assertTrue(script.conditions(norm["target_trigger"]))
        self.assertFalse(script.conditions(norm["available"]))
        self.assertFalse(self.start(script, "WRK_executive_norm_order", self.SITE))
        broken = triggers.replace(
            "WRK_executive_norm_site = {\n\tis_owned_and_controlled_by = ROOT\n",
            "WRK_executive_norm_site = {\n\tis_owned_and_controlled_by = ROOT\n"
            "\tfree_building_slots = { building = industrial_complex size > 0 }\n",
            1,
        )
        self.assertNotEqual(broken, triggers)
        self.assertIn(
            "WRK_executive_norm_site must keep building-slot tests out of the cached target list",
            committee_order_issues(self.decision_source, effects, broken),
        )
        farmed = triggers.replace(
            "\tNOT = { has_state_flag = WRK_executive_norm_built }\n", "", 1
        )
        self.assertNotEqual(farmed, triggers)
        self.assertIn(
            "WRK_executive_norm_site must stop at one WRK_executive_norm_order per region",
            committee_order_issues(self.decision_source, effects, farmed),
        )

    def test_contract_lean_stops_after_five_counted_deliveries(self) -> None:
        contract = "WRK_executive_republic_contract"
        decision = self.programmes[contract]
        script = self.campaign()
        country = script.scopes[self.NATION]
        country.resources["pp"] = 1000
        for delivery in range(1, 8):
            self.assertTrue(self.start(script, contract))
            script.run(decision["remove_effect"])
            leans = [scope for key, scope, _ in script.calls if key == "ADISCORD_west_push_lean"]
            self.assertEqual(len(leans), 2 * min(delivery, 5), delivery)
        self.assertEqual(country.variables["WRK_executive_contract_leans"], 5)
        # The goods keep coming; only the political effect is spent.
        self.assertEqual(country.resources["infantry_equipment"], 7 * 5000)
        effects = read(PHASE_EFFECTS_FILE)
        triggers = read(COMMITTEE_TRIGGER_FILE)
        gate = "var = WRK_executive_contract_leans value = 5 compare = less_than"
        self.assertEqual(triggers.count(gate), 1)
        uncapped = triggers.replace(gate, gate.replace("value = 5 ", "value = 500 "))
        self.assertIn(
            "the republic contract's lean must stop after five counted deliveries",
            committee_order_issues(self.decision_source, effects, uncapped),
        )

    def test_order_tooltips_name_every_refund_path_and_the_limit(self) -> None:
        for path, words in (
            (RUSSIAN_LOCALISATION, ("капитуляция", "утрата самостоятельности", "Потеря региона")),
            (ENGLISH_LOCALISATION, ("capitulation", "loss of independence", "Loss of the region")),
        ):
            entries = localisation_entries(read(path))
            for key in ("WRK_executive_norm_order_tt", "WRK_executive_district_audit_tt"):
                with self.subTest(path=path, key=key):
                    for word in words:
                        self.assertIn(word, entries[key])
                    # One per region, shown as a number.
                    self.assertIn("§Y1§!", entries[key])
            self.assertIn("§Y5§!", entries["WRK_executive_contract_lean_tt"])
            self.assertNotRegex(entries["WRK_executive_norm_order_desc"], r"\d|§|£")

    def test_callback_of_another_order_or_region_settles_nothing(self) -> None:
        for name in self.ORDERS:
            script = self.campaign()
            self.assertTrue(self.start(script, name, self.target(name)))
            paid = deepcopy(script.scopes)
            for other in self.ORDERS:
                if other == name:
                    continue
                for callback in ("remove_effect", "cancel_effect"):
                    script.run(self.programmes[other][callback])
                    self.assertEqual(script.scopes, paid, (name, other, callback))
            if "state_target" in self.programmes[name]:
                script.source = self.OTHER_SITE
                for callback in ("remove_effect", "cancel_effect"):
                    script.run(self.programmes[name][callback])
                    self.assertEqual(script.scopes, paid, (name, callback))

    def test_cooperative_works_are_paid_once_and_delivered_as_previewed(self) -> None:
        decision = self.programmes[self.WORKS]
        brigades = self.V + "worker_cooperative_brigades"
        for executive in (True, False):
            script = self.campaign(executive)
            country = script.scopes[self.NATION]
            self.assertTrue(self.start(script, self.WORKS))
            self.assertEqual(country.resources["pp"], 170)
            self.assertEqual(country.variables[self.WORKS_RECEIPT], float(decision["cost"]))
            paid = deepcopy(script.scopes)
            self.assertFalse(self.start(script, self.WORKS))
            self.assertEqual(script.scopes, paid)
            preview = deepcopy(script)
            preview.run(self.fields(decision["complete_effect"])["effect_tooltip"])
            script.run(decision["remove_effect"])
            self.assertEqual(dict(country.resources), dict(preview.scopes[self.NATION].resources))
            self.assertEqual(country.resources["train_equipment"], 10)
            self.assertEqual(country.resources["pp"], 170)
            self.assertIn(brigades, country.flags)
            terms = [
                self.fields(value)
                for key, _scope, value in script.calls
                if key == "add_timed_idea"
            ]
            self.assertEqual(terms, [{"idea": brigades, "days": "60"}])
            self.assertNotIn(self.WORKS_RECEIPT, country.variables)
            settled = deepcopy((script.scopes, script.calls))
            script.run(decision["remove_effect"])
            script.run(decision["cancel_effect"])
            self.assertEqual((script.scopes, script.calls), settled)
            # A new contract waits until the brigades have left.
            self.assertFalse(self.start(script, self.WORKS))
            country.flags.discard(brigades)
            self.assertTrue(self.start(script, self.WORKS))
        locked = self.campaign()
        locked.scopes[self.NATION].flags.discard(
            SETTLEMENT_PROGRAMMES["WRK_worker_fund_cooperative_reconstruction"][1]
        )
        self.assertFalse(self.start(locked, self.WORKS))

    def test_cooperative_works_refund_when_the_country_loses_its_independence(self) -> None:
        decision = self.programmes[self.WORKS]
        for cause, callback in product(
            ("subject", "capitulation"), ("cancel_effect", "remove_effect")
        ):
            with self.subTest(cause=cause, callback=callback):
                script = self.campaign()
                country = script.scopes[self.NATION]
                self.assertTrue(self.start(script, self.WORKS))
                if cause == "subject":
                    country.subject = "IVN"
                else:
                    country.capitulated = True
                self.assertTrue(script.conditions(decision["cancel_trigger"]))
                script.run(decision[callback])
                script.run(decision[callback])
                script.run(decision["cancel_effect"])
                self.assertEqual(country.resources["pp"], 200)
                self.assertNotIn(self.WORKS_RECEIPT, country.variables)
                self.assertEqual(country.resources["train_equipment"], 0)
                self.assertFalse([call for call in script.calls if call[0] == "add_timed_idea"])

    def test_programme_unlocks_outlive_the_settlement_tree(self) -> None:
        for focus_id, (decision, flag, _receipt) in SETTLEMENT_PROGRAMMES.items():
            with self.subTest(focus_id=focus_id):
                script = self.campaign()
                country = script.scopes[self.NATION]
                country.flags.discard(flag)
                script.run(self.focuses[focus_id]["completion_reward"])
                self.assertIn(flag, country.flags)
                # The next tree is loaded without the completed settlement focuses.
                country.focuses.clear()
                country.resources["pp"] = 200
                self.assertTrue(self.start(script, decision, self.target(decision)))
                self.assertNotIn("has_completed_focus", _blocks(self.decision_source, decision)[0])

    def contract_issues(self, blocks=None, decisions=None, plans=None, ideas=None) -> list[str]:
        return _check_settlement_branch(
            blocks or self.blocks,
            resolved_positions(blocks) if blocks else self.grid,
            decisions or self.decision_source,
            ideas or self.ideas,
            self.dynamic,
            plans or self.plans,
        )

    def test_contract_rejects_a_broken_branch(self) -> None:
        self.assertEqual(self.contract_issues(), [])
        tower_id = POSTWAR_ROUTE_TERMINALS[POSTWAR_EXECUTIVE_ROUTE]
        norms, contracts = POSTWAR_EXECUTIVE_CHOICE

        def mutated(focus_id: str, old: str, new: str) -> dict[str, str]:
            self.assertEqual(self.blocks[focus_id].count(old), 1, (focus_id, old))
            return {**self.blocks, focus_id: self.blocks[focus_id].replace(old, new)}

        required = mutated(
            tower_id,
            "prerequisite = { focus = WRK_worker_write_constitutional_guarantees }",
            "prerequisite = { focus = WRK_worker_write_constitutional_guarantees }\n"
            f"\t\tprerequisite = {{ focus = {POSTWAR_EXECUTIVE_FINAL} }}",
        )
        self.assertIn(
            f"{tower_id} must not require an Executive Committee focus",
            self.contract_issues(blocks=required),
        )
        preview = mutated(
            norms,
            "var = ADISCORD_vorkerland_pw_construction value = 0.10",
            "var = ADISCORD_vorkerland_pw_construction value = 0.15",
        )
        self.assertTrue(
            [issue for issue in self.contract_issues(blocks=preview) if issue.startswith(f"{norms} previews")]
        )
        unread = mutated(
            norms,
            "var = ADISCORD_vorkerland_pw_construction value = 0.10",
            "var = ADISCORD_vorkerland_pw_unread value = 0.10",
        )
        self.assertIn(
            f"{norms}: ADISCORD_vorkerland_pw_unread is not read by ADISCORD_vorkerland_postwar_institutions",
            self.contract_issues(blocks=unread),
        )
        merged = mutated(
            norms, f"mutually_exclusive = {{ focus = {contracts} }}", ""
        )
        self.assertIn(
            f"{norms} must be mutually exclusive with {contracts}",
            self.contract_issues(blocks=merged),
        )
        ungated = mutated(
            tower_id, f"has_country_flag = {POSTWAR_EXECUTIVE_GATE}\n\t\t\t\tNOT", "NOT"
        )
        self.assertIn(
            "the executive AI must finish the committee branch before the Tower",
            self.contract_issues(blocks=ungated),
        )
        receipt = "set_variable = { var = WRK_executive_order_deposit value = 50 }"
        self.assertEqual(self.decision_source.count(receipt), 1)
        underpaid = self.decision_source.replace(receipt, receipt.replace("50", "40"))
        self.assertIn(
            "programme WRK_executive_norm_order must record a receipt equal to its price",
            self.contract_issues(decisions=underpaid),
        )
        both = self.plans.replace(f"\t\t{norms}\n", f"\t\t{norms}\n\t\t{contracts}\n", 1)
        self.assertNotEqual(both, self.plans)
        self.assertIn(
            f"AI plan must take exactly one committee alternative, found {[norms, contracts]}",
            self.contract_issues(plans=both),
        )
        plan = _blocks(self.plans, SETTLEMENT_AI_PLAN)[0]
        late = self.plans.replace(
            plan,
            plan.replace(f"\t\t{POSTWAR_EXECUTIVE_FINAL}\n", "", 1).replace(
                f"\t\t{tower_id}\n", f"\t\t{tower_id}\n\t\t{POSTWAR_EXECUTIVE_FINAL}\n", 1
            ),
            1,
        )
        self.assertNotEqual(late, self.plans)
        self.assertIn(
            "AI plan must finish the committee branch before the Unity Tower",
            self.contract_issues(plans=late),
        )
        # Each government has its own plan, and each plan takes one of the
        # housing and grants alternatives.
        congress = _blocks(self.plans, CONGRESS_AI_PLAN)[0]
        housing, grants = next(
            pair for pair in POSTWAR_POLICY_CHOICE_PAIRS if pair[0] in self.worker_route
        )
        self.assertEqual(
            [name for name in (housing, grants) if f"\t\t{name}\n" in congress], [housing]
        )
        self.assertEqual(
            [name for name in (housing, grants) if f"\t\t{name}\n" in plan], [grants]
        )
        undecided = self.plans.replace(congress, congress.replace(f"\t\t{housing}\n", "", 1), 1)
        self.assertIn(
            f"AI plan {CONGRESS_AI_PLAN} must take exactly one of the housing and grants "
            "alternatives, found []",
            self.contract_issues(plans=undecided),
        )
        leaked = self.plans.replace(
            congress,
            congress.replace(f"\t\t{tower_id}\n", f"\t\t{norms}\n\t\t{tower_id}\n", 1),
            1,
        )
        self.assertIn(
            f"AI plan {CONGRESS_AI_PLAN} names focuses hidden from its government ['{norms}']",
            self.contract_issues(plans=leaked),
        )

    def test_settlement_text_is_bilingual_narrative_and_plain_ascii(self) -> None:
        focus_keys = [
            key
            for focus_id in POSTWAR_EXECUTIVE_FOCUSES
            for key in (focus_id, f"{focus_id}_desc")
        ]
        narrative = [key for key in (*focus_keys, *SETTLEMENT_LOCALISATION_KEYS) if key.endswith("_desc")]
        self.assertEqual(len(narrative), 12)
        for path in (ENGLISH_LOCALISATION, RUSSIAN_LOCALISATION):
            raw = (ROOT / path).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), path)
            text = raw.decode("utf-8-sig")
            for key in (*focus_keys, *SETTLEMENT_LOCALISATION_KEYS):
                with self.subTest(path=path, key=key):
                    lines = re.findall(
                        rf'(?m)^ {re.escape(key)}:(?:\d+)? "((?:[^"\\\r\n]|\\.)*)"\r?$', text
                    )
                    self.assertEqual(len(lines), 1)
                    value = lines[0]
                    self.assertTrue(value.strip())
                    for character in ("\u2013", "\u2014", "\u00ab", "\u00bb"):
                        self.assertNotIn(character, value)
                    if key in narrative:
                        # Prices, durations and results stay in the effect block.
                        self.assertNotRegex(value, r"[§£%]|\d")
        russian = (ROOT / RUSSIAN_LOCALISATION).read_text(encoding="utf-8-sig")
        english = (ROOT / ENGLISH_LOCALISATION).read_text(encoding="utf-8-sig")
        committee = "\n".join(
            line for line in russian.splitlines() if line.startswith(" WRK_executive_")
        )
        self.assertIn("Багли", committee)
        self.assertNotIn("Бэгли", committee)
        self.assertIn(
            "Bagley",
            "\n".join(line for line in english.splitlines() if line.startswith(" WRK_executive_")),
        )


class ExecutiveConfederationTests(unittest.TestCase):
    """Two governments share the confederation tree after the Unity Tower.

    The congress keeps its council branches; the Executive Committee draws its
    own in the same cells. Its rewards and orders are executed from source.
    """

    NATION = "WKR"
    SITE = "201"
    OTHER_SITE = "32"
    CIVIL_RECEIPT = "WRK_executive_order_deposit"
    CADRE_RECEIPT = "WRK_executive_cadre_deposit"
    CADRE_ORDERS = ("WRK_executive_cadre_course", "WRK_executive_depot_issue")
    STATE_ORDERS = tuple(COMMITTEE_STATE_ORDERS)
    CONTRACT = "WRK_executive_republic_contract"

    @classmethod
    def setUpClass(cls) -> None:
        from tools.tests.test_vorkerland_preparation import V, fields, parse, walk

        cls.Script = settlement_script_class()
        cls.V = V
        cls.fields = staticmethod(fields)
        cls.source = read(CONFEDERATION_FILE)
        cls.blocks = focus_blocks(cls.source)
        cls.grid = resolved_positions(cls.blocks)
        cls.focuses = {
            fields(value)["id"]: fields(value)
            for key, _, value in walk(parse(cls.source))
            if key == "focus" and isinstance(value, list)
        }
        cls.decision_source = read(DIPLOMACY_DECISIONS_FILE)
        operations = fields(fields(parse(cls.decision_source))[V + "focus_operations_category"])
        cls.orders = {
            name: fields(operations[name])
            for name in (*cls.STATE_ORDERS, cls.CONTRACT, *cls.CADRE_ORDERS)
        }
        cls.effects = read(PHASE_EFFECTS_FILE)
        cls.ideas = read(COLLAPSE_IDEAS_FILE)
        cls.dynamic = read(SETTLEMENT_AGGREGATE_FILE)
        cls.aggregate = settlement_aggregate_fields(cls.dynamic)
        cls.plans = read(WKR_AI_PLAN_FILE)
        cls.parsed_plans = fields(parse(cls.plans))
        cls.localisations = {
            "English": localisation_entries(read(ENGLISH_LOCALISATION)),
            "Russian": localisation_entries(read(RUSSIAN_LOCALISATION)),
        }
        cls.unlocks = {
            decision: flag
            for programmes in (SETTLEMENT_PROGRAMMES, CONFEDERATION_PROGRAMMES)
            for decision, flag, _receipt in programmes.values()
        }

    def campaign(self, executive: bool = True, unlocked: bool = True):
        V = self.V
        script = self.Script()
        script.root = self.NATION
        script.globals = {
            V + "phase_postwar_integration",
            V + "reunification_verified",
            V + "collapse_finished",
            V + "unity_tower_restored",
        }
        script.event_targets["ADISCORD_vorkerland_nation"] = self.NATION
        country = script.scopes[self.NATION]
        country.resources.clear()
        country.resources["pp"] = 1000
        country.flags.update({POSTWAR_EXECUTIVE_ROUTE, V + "central_unifier"})
        if executive:
            country.flags.add(POSTWAR_EXECUTIVE_GATE)
        if unlocked:
            country.flags.update(self.unlocks.values())
        for state, arsenal_slots in ((self.SITE, 0), (self.OTHER_SITE, 1)):
            scope = script.scopes[state]
            scope.owner = scope.controller = self.NATION
            scope.cores.add(self.NATION)
            scope.resources.update(
                industrial_complex_slots=1, arms_factory_slots=arsenal_slots, infrastructure_slots=1
            )
        script.scopes["capital_" + self.NATION].resources["infrastructure_slots"] = 1
        return script

    def start(self, script, name: str, target: str | None = None) -> bool:
        return start_programme(script, self.NATION, self.orders[name], target)

    def issues(self, source=None, plans=None, decisions=None) -> list[str]:
        return _check_confederation_tree(
            source or self.source,
            decisions or self.decision_source,
            self.effects,
            self.ideas,
            self.dynamic,
            plans or self.plans,
            self.localisations,
        )

    def test_each_government_sees_only_its_own_domestic_branches(self) -> None:
        for executive, government in ((True, "executive"), (False, "congress")):
            script = self.campaign(executive)
            visible = {
                name
                for name, focus in self.focuses.items()
                if script.conditions(focus.get("allow_branch", []))
            }
            view = confederation_view(government)
            self.assertEqual(visible, set(view), government)
            cells = [self.grid[name] for name in view]
            self.assertEqual(len(cells), len(set(cells)), government)
        self.assertEqual(
            (
                len(CONFEDERATION_SHARED_FOCUSES),
                len(CONFEDERATION_COUNCIL_FOCUSES),
                len(CONFEDERATION_EXECUTIVE_FOCUSES),
            ),
            (8, 14, 15),
        )
        self.assertEqual(len(self.blocks), 37)
        # The two governments' branches occupy the same part of the canvas,
        # which is legal only because they are never drawn together.
        council = {self.grid[name] for name in CONFEDERATION_COUNCIL_FOCUSES}
        executive = {self.grid[name] for name in CONFEDERATION_EXECUTIVE_FOCUSES}
        self.assertEqual(len(council & executive), 13)
        self.assertFalse(
            confederation_can_share_view(
                CONFEDERATION_COUNCIL_FOCUSES[0], CONFEDERATION_EXECUTIVE_FOCUSES[0]
            )
        )
        self.assertTrue(
            confederation_can_share_view(
                CONFEDERATION_SHARED_FOCUSES[0], CONFEDERATION_EXECUTIVE_FOCUSES[0]
            )
        )
        self.assertTrue(
            confederation_can_share_view(
                CONFEDERATION_EXECUTIVE_FOCUSES[0], CONFEDERATION_EXECUTIVE_FOCUSES[1]
            )
        )

    def test_both_governments_reach_every_shared_focus(self) -> None:
        for government in ("congress", "executive"):
            view = set(confederation_view(government))
            self.assertEqual(confederation_reachable(self.blocks, government), view)
        mandate = _prerequisite_groups(self.blocks["WRK_worker_west_mandate_for_itora"])
        self.assertIn(
            frozenset({"WRK_conf_army_of_the_republics", "WRK_exec_cadre_army"}), mandate
        )
        # Without its own army final in that block the Executive Committee
        # could never open the western mandate.
        severed = self.source.replace("\t\t\tfocus = WRK_exec_cadre_army\n", "", 1)
        self.assertNotEqual(severed, self.source)
        issues = self.issues(source=severed)
        self.assertIn(
            "the executive government cannot reach ['WRK_worker_west_mandate_for_itora']", issues
        )
        self.assertIn(
            "shared focus WRK_worker_west_mandate_for_itora needs "
            "['WRK_conf_army_of_the_republics'] of one government only",
            issues,
        )

    def test_branches_take_the_same_time_for_both_governments(self) -> None:
        days = {}
        for branch, (council, executive) in CONFEDERATION_BRANCHES.items():
            council_days = confederation_path_units(self.blocks, council) * 7
            executive_days = confederation_path_units(self.blocks, executive) * 7
            self.assertEqual(council_days, executive_days, branch)
            days[branch] = executive_days
        self.assertEqual(days, {"reconstruction": 77, "industry": 91, "army": 91})
        for left, right in CONFEDERATION_EXECUTIVE_CHOICES:
            self.assertEqual(_mutually_exclusive_focuses(self.blocks[left]), {right})
            self.assertEqual(_mutually_exclusive_focuses(self.blocks[right]), {left})
            rejoin = [
                name
                for name in CONFEDERATION_EXECUTIVE_FOCUSES
                if frozenset({left, right}) in _prerequisite_groups(self.blocks[name])
            ]
            self.assertEqual(len(rejoin), 1, (left, right))

    def test_every_committee_focus_pays_two_substantive_rewards(self) -> None:
        for name in CONFEDERATION_EXECUTIVE_FOCUSES:
            with self.subTest(name=name):
                self.assertGreaterEqual(len(confederation_reward_classes(self.blocks[name])), 2)
                # The congress branches own the development reforms of this tree.
                self.assertNotIn("ADISCORD_reform_", self.blocks[name])
        reforms = re.findall(r"ADISCORD_reform_(\w+)_development = yes", self.source)
        self.assertCountEqual(reforms, ("society", "social_system", "army", "state", "economic"))

    def test_aggregate_previews_equal_the_executed_change(self) -> None:
        V = self.V
        changed = 0
        for name in CONFEDERATION_EXECUTIVE_FOCUSES:
            with self.subTest(name=name):
                script = self.campaign()
                country = script.scopes[self.NATION]
                before = dict(country.variables)
                script.run(self.focuses[name]["completion_reward"])
                executed = {
                    modifier: round(
                        country.variables.get(variable, 0) - before.get(variable, 0), 6
                    )
                    for variable, modifier in self.aggregate.items()
                    if country.variables.get(variable, 0) != before.get(variable, 0)
                }
                applied, shown, defects = settlement_aggregate_delta(
                    self.blocks[name], self.aggregate, self.ideas
                )
                self.assertEqual(defects, [])
                self.assertEqual(applied, shown)
                self.assertEqual(executed, shown)
                if executed:
                    changed += 1
                    self.assertIn(V + "postwar_institutions", country.flags)
                self.assertFalse(
                    {flag for flag in country.flags if flag.startswith(V + "pw_delta_")}
                )
        self.assertEqual(changed, 11)

    def test_money_and_growth_tooltips_state_the_executed_amount(self) -> None:
        treasury = "ADISCORD_economy_treasury"
        for name, tooltip in (
            ("WRK_exec_district_inventory", "WRK_exec_inventory_treasury_tt"),
            ("WRK_exec_rolling_district_audit", "WRK_exec_rolling_audit_treasury_tt"),
            ("WRK_exec_central_order_bureau", "WRK_exec_order_bureau_treasury_tt"),
        ):
            script = self.campaign()
            script.run(self.focuses[name]["completion_reward"])
            amount = script.scopes[self.NATION].variables[treasury]
            self.assertEqual(
                script.scopes[self.NATION].variables["ADISCORD_economy_current_month_action_income"],
                amount,
            )
            for entries in self.localisations.values():
                self.assertIn(
                    f"§G+{amount:g}§! £ADISCORD_economy_treasury_texticon", entries[tooltip]
                )
        for name, axis in (
            ("WRK_exec_district_inventory", "society"),
            ("WRK_exec_ration_by_ledger", "social_system"),
            ("WRK_exec_central_order_bureau", "economic"),
            ("WRK_exec_staff_by_examination", "army"),
        ):
            script = self.campaign()
            script.run(self.focuses[name]["completion_reward"])
            calls = [key for key, _scope, _value in script.calls if key.startswith("ADISCORD_increase_")]
            self.assertEqual(calls, [f"ADISCORD_increase_{axis}_development_monthly_growth"] * 2)
            for entries in self.localisations.values():
                self.assertIn(
                    f"§G+{len(calls)}§! £ADISCORD_country_development_texticon",
                    entries[f"WRK_exec_{axis}_growth_tt"],
                )

    def test_late_unlocks_open_only_what_the_settlement_skipped(self) -> None:
        for name, (decision, flag) in CONFEDERATION_LATE_UNLOCKS.items():
            with self.subTest(name=name):
                skipped = self.campaign(unlocked=False)
                country = skipped.scopes[self.NATION]
                skipped.run(self.focuses[name]["completion_reward"])
                self.assertIn(flag, country.flags)
                gained_by_skipper = country.resources["pp"]
                finished = self.campaign(unlocked=False)
                country = finished.scopes[self.NATION]
                country.flags.add(flag)
                finished.run(self.focuses[name]["completion_reward"])
                self.assertIn(flag, country.flags)
                if name == "WRK_exec_district_inventory":
                    # The government that already runs audits is paid for two.
                    self.assertEqual(country.resources["pp"] - gained_by_skipper, 50)
                    self.assertEqual(float(self.orders[decision]["cost"]) * 2, 50)
                else:
                    self.assertEqual(country.resources["pp"], gained_by_skipper)
        # A government that skipped the whole settlement branch can still
        # place an order of each civil kind after these focuses.
        script = self.campaign(unlocked=False)
        country = script.scopes[self.NATION]
        self.assertFalse(self.start(script, "WRK_executive_district_audit", self.SITE))
        script.run(self.focuses["WRK_exec_district_inventory"]["completion_reward"])
        self.assertTrue(self.start(script, "WRK_executive_district_audit", self.SITE))
        script.run(self.orders["WRK_executive_district_audit"]["remove_effect"])
        self.assertFalse(self.start(script, "WRK_executive_norm_order", self.SITE))
        script.run(self.focuses["WRK_exec_norm_series"]["completion_reward"])
        self.assertTrue(self.start(script, "WRK_executive_norm_order", self.SITE))

    def test_committee_opens_district_reconstruction_for_its_own_government(self) -> None:
        from tools.tests.test_vorkerland_preparation import TRIGGERS

        V = self.V
        script = self.campaign()
        country = script.scopes[self.NATION]
        opened = TRIGGERS[V + "pw_reconstruction_open"]
        slot = TRIGGERS[V + "pw_rebuild_slot_free"]
        self.assertFalse(script.conditions(opened))
        country.focuses.add("WRK_exec_reconstruction_work_orders")
        self.assertTrue(script.conditions(opened))
        for extra, capacity in (
            ((), 1),
            (("WRK_exec_second_construction_trust",), 2),
            (("WRK_exec_ration_by_ledger",), 3),
            (("WRK_exec_second_construction_trust", "WRK_exec_ration_by_ledger"), 3),
        ):
            country.focuses = {"WRK_exec_reconstruction_work_orders", *extra}
            for active in range(4):
                country.variables[V + "pw_rebuild_active"] = active
                self.assertEqual(script.conditions(slot), active < capacity, (extra, active))
        for name in ("WRK_exec_second_construction_trust", "WRK_exec_ration_by_ledger"):
            self.assertIn("custom_effect_tooltip = WRK_route_rebuild_slot_tt", self.blocks[name])
        self.assertIn(
            "unlock_decision_tooltip = ADISCORD_vorkerland_pw_rebuild_district",
            self.blocks["WRK_exec_reconstruction_work_orders"],
        )

    def test_cadre_orders_run_beside_the_civil_orders_on_their_own_receipt(self) -> None:
        results = {
            "WRK_executive_cadre_course": {"army_experience": 40, "command": 15},
            "WRK_executive_depot_issue": {
                "artillery_equipment": 250, "support_equipment": 250, "motorized_equipment": 150,
            },
        }
        for name in self.CADRE_ORDERS:
            with self.subTest(name=name):
                decision = self.orders[name]
                price = float(decision["cost"])
                script = self.campaign()
                country = script.scopes[self.NATION]
                # A civil order in progress does not hold the cadre order back.
                self.assertTrue(self.start(script, "WRK_executive_norm_order", self.SITE))
                civil = country.resources["pp"]
                self.assertTrue(self.start(script, name))
                self.assertEqual(country.resources["pp"], civil - price)
                self.assertEqual(country.variables[self.CADRE_RECEIPT], price)
                self.assertEqual(country.variables[self.CIVIL_RECEIPT], 50)
                paid = deepcopy(script.scopes)
                for other in self.CADRE_ORDERS:
                    self.assertFalse(self.start(script, other), other)
                    self.assertEqual(script.scopes, paid)
                preview = deepcopy(script)
                preview.run(self.fields(decision["complete_effect"])["effect_tooltip"])
                script.run(decision["remove_effect"])
                self.assertEqual(
                    dict(country.resources), dict(preview.scopes[self.NATION].resources)
                )
                for resource, amount in results[name].items():
                    self.assertEqual(country.resources[resource], amount)
                self.assertEqual(country.resources["pp"], civil - price)
                self.assertNotIn(self.CADRE_RECEIPT, country.variables)
                # The civil receipt is untouched by the cadre delivery.
                self.assertEqual(country.variables[self.CIVIL_RECEIPT], 50)
                self.assertIn("WRK_executive_norm_order_pending", country.flags)
                settled = deepcopy(script.scopes)
                script.run(decision["remove_effect"])
                script.run(decision["cancel_effect"])
                for other in self.CADRE_ORDERS:
                    script.run(self.orders[other]["cancel_effect"])
                self.assertEqual(script.scopes, settled)
                self.assertFalse(self.start(self.campaign(executive=False), name))
                locked = self.campaign()
                locked.scopes[self.NATION].flags.discard(self.unlocks[name])
                self.assertFalse(self.start(locked, name))

    def test_cadre_orders_refund_once_when_the_country_loses_its_independence(self) -> None:
        for name, cause, callback in product(
            self.CADRE_ORDERS, ("subject", "capitulation"), ("cancel_effect", "remove_effect")
        ):
            with self.subTest(name=name, cause=cause, callback=callback):
                decision = self.orders[name]
                script = self.campaign()
                country = script.scopes[self.NATION]
                self.assertTrue(self.start(script, name))
                if cause == "subject":
                    country.subject = "IVN"
                else:
                    country.capitulated = True
                self.assertTrue(script.conditions(decision["cancel_trigger"]))
                script.run(decision[callback])
                script.run(decision[callback])
                script.run(decision["cancel_effect"])
                self.assertEqual(country.resources["pp"], 1000)
                self.assertNotIn(self.CADRE_RECEIPT, country.variables)
                self.assertFalse({flag for flag in country.flags if flag.endswith("_pending")})
                self.assertEqual(country.resources["army_experience"], 0)
                self.assertEqual(country.resources["artillery_equipment"], 0)

    def test_arsenal_order_builds_once_in_the_slot_an_audit_opened(self) -> None:
        arsenal = "WRK_executive_arsenal_order"
        audit = "WRK_executive_district_audit"
        decision = self.orders[arsenal]
        script = self.campaign()
        country = script.scopes[self.NATION]
        site = script.scopes[self.SITE]
        # An unaudited region is not on the books, whatever slots it has.
        self.assertFalse(self.start(script, arsenal, self.OTHER_SITE))
        self.assertFalse(self.start(script, arsenal, self.SITE))
        self.assertTrue(self.start(script, audit, self.SITE))
        script.run(self.orders[audit]["remove_effect"])
        self.assertEqual(site.resources["arms_factory_slots"], 1)
        before = country.resources["pp"]
        self.assertTrue(self.start(script, arsenal, self.SITE))
        self.assertEqual(country.resources["pp"], before - 60)
        self.assertEqual(country.variables[self.CIVIL_RECEIPT], 60)
        preview = deepcopy(script)
        preview.run(self.fields(decision["complete_effect"])["effect_tooltip"])
        script.run(decision["remove_effect"])
        self.assertEqual(dict(site.resources), dict(preview.scopes[self.SITE].resources))
        self.assertEqual(site.resources["arms_factory"], 1)
        self.assertEqual(site.resources["arms_factory_slots"], 0)
        self.assertIn("WRK_executive_arsenal_built", site.flags)
        self.assertNotIn(self.CIVIL_RECEIPT, country.variables)
        settled = deepcopy(script.scopes)
        script.run(decision["remove_effect"])
        script.run(decision["cancel_effect"])
        self.assertEqual(script.scopes, settled)
        site.resources["arms_factory_slots"] = 3
        self.assertFalse(self.start(script, arsenal, self.SITE))
        # A slot the player used meanwhile, or a lost region, returns the price.
        for cause in ("no_slot", "site_lost", "subject"):
            with self.subTest(cause=cause):
                retry = self.campaign()
                country = retry.scopes[self.NATION]
                site = retry.scopes[self.SITE]
                site.flags.add("WRK_executive_district_audited")
                site.resources["arms_factory_slots"] = 1
                self.assertTrue(self.start(retry, arsenal, self.SITE))
                if cause == "no_slot":
                    site.resources["arms_factory_slots"] = 0
                elif cause == "site_lost":
                    site.controller = "IVN"
                else:
                    country.subject = "IVN"
                if cause != "no_slot":
                    self.assertTrue(retry.conditions(decision["cancel_trigger"]))
                retry.run(decision["remove_effect"])
                retry.run(decision["cancel_effect"])
                self.assertEqual(country.resources["pp"], 1000)
                self.assertNotIn(self.CIVIL_RECEIPT, country.variables)
                self.assertEqual(site.resources["arms_factory"], 0)
                self.assertNotIn("WRK_executive_arsenal_built", site.flags)
        # No slot at all is refused when the order is placed.
        full = self.campaign()
        full.scopes[self.SITE].flags.add("WRK_executive_district_audited")
        self.assertFalse(self.start(full, arsenal, self.SITE))
        self.assertEqual(full.scopes[self.NATION].resources["pp"], 1000)

    def test_standing_upgrades_change_the_delivery_and_its_preview(self) -> None:
        cases = {
            "WRK_exec_norm_series": ("WRK_executive_norm_order", self.SITE),
            "WRK_exec_rolling_district_audit": ("WRK_executive_district_audit", self.SITE),
            "WRK_exec_republic_supply_chain": (self.CONTRACT, None),
        }
        outcomes = {}
        for upgraded in (False, True):
            for name, (order, target) in cases.items():
                decision = self.orders[order]
                script = self.campaign()
                country = script.scopes[self.NATION]
                site = script.scopes[self.SITE]
                if upgraded:
                    country.flags.add(CONFEDERATION_ORDER_UPGRADES[name][0])
                self.assertTrue(self.start(script, order, target))
                preview = deepcopy(script)
                preview.run(self.fields(decision["complete_effect"])["effect_tooltip"])
                script.run(decision["remove_effect"])
                for scope in (self.NATION, self.SITE):
                    self.assertEqual(
                        dict(script.scopes[scope].resources),
                        dict(preview.scopes[scope].resources),
                        (name, upgraded),
                    )
                self.assertEqual(
                    site.variables.get("shared_building_slots", 0),
                    preview.scopes[self.SITE].variables.get("shared_building_slots", 0),
                )
                outcomes[name, upgraded] = (
                    site.variables.get("shared_building_slots", 0),
                    site.resources["infrastructure"],
                    country.resources["infantry_equipment"],
                    country.resources["artillery_equipment"],
                )
        self.assertEqual(outcomes["WRK_exec_norm_series", False], (1, 0, 0, 0))
        self.assertEqual(outcomes["WRK_exec_norm_series", True], (2, 0, 0, 0))
        self.assertEqual(outcomes["WRK_exec_rolling_district_audit", False], (1, 0, 600, 0))
        self.assertEqual(outcomes["WRK_exec_rolling_district_audit", True], (1, 1, 900, 0))
        self.assertEqual(outcomes["WRK_exec_republic_supply_chain", False], (0, 0, 5000, 0))
        self.assertEqual(outcomes["WRK_exec_republic_supply_chain", True], (0, 0, 5000, 100))
        # The numbers in the focus tooltips are the delivered differences.
        for entries in self.localisations.values():
            self.assertIn("§G1§!", entries["WRK_exec_norm_series_tt"])
            self.assertIn("§G300§! £infantry_equipment_texticon", entries["WRK_exec_rolling_audit_tt"])
            self.assertIn("§G100§! £ADISCORD_artillery_texticon", entries["WRK_exec_supply_chain_tt"])
            self.assertIn("§G10§! £political_power_texticon", entries["WRK_exec_order_bureau_tt"])

    def test_order_bureau_returns_its_overhead_on_every_accepted_civil_order(self) -> None:
        bureau = CONFEDERATION_ORDER_UPGRADES["WRK_exec_central_order_bureau"][0]
        for order in (*self.STATE_ORDERS, self.CONTRACT):
            with self.subTest(order=order):
                decision = self.orders[order]
                target = self.SITE if "state_target" in decision else None
                for rebate in (0, 10):
                    script = self.campaign()
                    country = script.scopes[self.NATION]
                    site = script.scopes[self.SITE]
                    site.flags.add("WRK_executive_district_audited")
                    site.resources["arms_factory_slots"] = 1
                    if order == "WRK_executive_district_audit":
                        site.flags.discard("WRK_executive_district_audited")
                    if rebate:
                        country.flags.add(bureau)
                    self.assertTrue(self.start(script, order, target))
                    paid = country.resources["pp"]
                    preview = deepcopy(script)
                    preview.run(self.fields(decision["complete_effect"])["effect_tooltip"])
                    script.run(decision["remove_effect"])
                    self.assertEqual(country.resources["pp"], paid + rebate)
                    self.assertEqual(preview.scopes[self.NATION].resources["pp"], paid + rebate)
                    # A refunded order earns no rebate.
                    refund = self.campaign()
                    country = refund.scopes[self.NATION]
                    site = refund.scopes[self.SITE]
                    site.flags.add("WRK_executive_district_audited")
                    site.resources["arms_factory_slots"] = 1
                    if order == "WRK_executive_district_audit":
                        site.flags.discard("WRK_executive_district_audited")
                    country.flags.add(bureau)
                    self.assertTrue(self.start(refund, order, target))
                    country.subject = "IVN"
                    refund.run(decision["remove_effect"])
                    self.assertEqual(country.resources["pp"], 1000)
        # The cadre receipt is not a civil order.
        script = self.campaign()
        country = script.scopes[self.NATION]
        country.flags.add(bureau)
        self.assertTrue(self.start(script, "WRK_executive_cadre_course"))
        paid = country.resources["pp"]
        script.run(self.orders["WRK_executive_cadre_course"]["remove_effect"])
        self.assertEqual(country.resources["pp"], paid)

    def test_ai_plans_name_only_focuses_their_government_can_see(self) -> None:
        for plan_id, government in (
            (SETTLEMENT_AI_PLAN, "executive"), (CONGRESS_AI_PLAN, "congress"),
        ):
            with self.subTest(plan_id=plan_id):
                planned = planned_focuses(self.plans, plan_id)
                view = set(confederation_view(government))
                confederation = [name for name in planned if name in self.blocks]
                self.assertEqual(set(confederation) - view, set())
                self.assertEqual(len(confederation), len(set(confederation)))
                self.assertLessEqual(set(CONFEDERATION_SHARED_FOCUSES), set(confederation))
                self.assertIn("WRK_worker_west_mandate_for_itora", confederation)
                done: set[str] = set()
                for name in confederation:
                    self.assertTrue(
                        all(group & done for group in _prerequisite_groups(self.blocks[name])),
                        name,
                    )
                    self.assertFalse(_mutually_exclusive_focuses(self.blocks[name]) & done, name)
                    done.add(name)
                script = self.campaign(executive=government == "executive")
                script.scopes[self.NATION].ai = True
                enable = self.fields(self.parsed_plans[plan_id])["enable"]
                self.assertTrue(script.conditions(enable))
                other = self.campaign(executive=government != "executive")
                other.scopes[self.NATION].ai = True
                self.assertFalse(other.conditions(enable))
        executive = planned_focuses(self.plans, SETTLEMENT_AI_PLAN)
        for pair in CONFEDERATION_EXECUTIVE_CHOICES:
            self.assertEqual(len([name for name in pair if name in executive]), 1, pair)
        taken = [name for name in executive if name in CONFEDERATION_EXECUTIVE_FOCUSES]
        self.assertEqual(len(taken), 12)

    def test_contract_rejects_a_broken_tree(self) -> None:
        self.assertEqual(self.issues(), [])
        gate = f"has_country_flag = {POSTWAR_EXECUTIVE_GATE}"
        council_id = "WRK_conf_veteran_resettlement"
        council = self.blocks[council_id]
        ungated = self.source.replace(
            council, council.replace(f"\t\tallow_branch = {{ NOT = {{ {gate} }} }}\n", "", 1), 1
        )
        self.assertNotEqual(ungated, self.source)
        issues = self.issues(source=ungated)
        self.assertTrue(
            [issue for issue in issues if issue.startswith(f"{council_id} belongs to the congress view")]
        )
        self.assertNotEqual(issues, [])
        executive_id = "WRK_exec_cadre_army"
        moved = self.source.replace(
            self.blocks[executive_id],
            self.blocks[executive_id].replace("\t\tx = 8\n\t\ty = 4\n", "\t\tx = 12\n\t\ty = 5\n", 1),
            1,
        )
        self.assertNotEqual(moved, self.source)
        self.assertIn(
            "executive view draws WRK_worker_west_mandate_for_itora and WRK_exec_cadre_army "
            "in cell (12, 5)",
            self.issues(source=moved),
        )
        crowded = self.source.replace(
            self.blocks["WRK_exec_republic_supply_chain"],
            self.blocks["WRK_exec_republic_supply_chain"].replace("\t\tx = 6\n", "\t\tx = 7\n", 1),
            1,
        )
        self.assertIn(
            "executive view: WRK_exec_republic_supply_chain and WRK_exec_staff_by_examination "
            "need a free cell between them",
            self.issues(source=crowded),
        )
        cloned = self.source.replace(
            "\t\t\tadd_command_power = 25\n\t\t\tadd_manpower = 8000\n",
            "\t\t\tadd_command_power = 25\n\t\t\tADISCORD_reform_army_development = yes\n",
            1,
        )
        self.assertNotEqual(cloned, self.source)
        self.assertIn(
            f"{executive_id} must not repeat a development reform of the congress branches",
            self.issues(source=cloned),
        )
        slow = self.source.replace(
            self.blocks[executive_id], self.blocks[executive_id].replace("\t\tcost = 3\n", "\t\tcost = 6\n", 1), 1
        )
        self.assertIn(
            "army takes 91 days for the congress and 112 days for the Executive Committee",
            self.issues(source=slow),
        )
        plan = _blocks(self.plans, SETTLEMENT_AI_PLAN)[0]
        leaked = self.plans.replace(
            plan, plan.replace("\t\tWRK_exec_paid_cadre\n", "\t\tWRK_conf_republican_militias\n", 1), 1
        )
        self.assertNotEqual(leaked, self.plans)
        self.assertIn(
            f"AI plan {SETTLEMENT_AI_PLAN} names focuses hidden from its government "
            "['WRK_conf_republican_militias']",
            self.issues(plans=leaked),
        )
        both = self.plans.replace(
            plan,
            plan.replace(
                "\t\tWRK_exec_fortress_schedules\n",
                "\t\tWRK_exec_fortress_schedules\n\t\tWRK_exec_motor_columns\n",
                1,
            ),
            1,
        )
        self.assertIn(
            f"AI plan {SETTLEMENT_AI_PLAN} takes both alternatives at WRK_exec_motor_columns",
            self.issues(plans=both),
        )
        receipt = "set_variable = { var = WRK_executive_cadre_deposit value = 40 }"
        self.assertEqual(self.decision_source.count(receipt), 1)
        self.assertIn(
            "programme WRK_executive_cadre_course must record a receipt equal to its price",
            self.issues(decisions=self.decision_source.replace(receipt, receipt.replace("40", "30"))),
        )

    def test_committee_text_is_bilingual_narrative_and_plain_ascii(self) -> None:
        keys = {
            key for name in CONFEDERATION_EXECUTIVE_FOCUSES for key in (name, f"{name}_desc")
        }
        keys |= set(re.findall(r"custom_effect_tooltip = (\w+)", self.source))
        keys |= set(re.findall(r"add_ideas = (ADISCORD_vorkerland_pw_delta_\w+)", self.source))
        for decision, _flag, _receipt in CONFEDERATION_PROGRAMMES.values():
            keys |= {decision, f"{decision}_desc", f"{decision}_tt"}
        keys |= {"WRK_executive_arsenal_room_tt", "WRK_executive_cadre_slot_tt"}
        for path in (ENGLISH_LOCALISATION, RUSSIAN_LOCALISATION):
            raw = (ROOT / path).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), path)
            text = raw.decode("utf-8-sig")
            for key in sorted(keys):
                with self.subTest(path=path, key=key):
                    lines = re.findall(
                        rf'(?m)^ {re.escape(key)}:(?:\d+)? "((?:[^"\\\r\n]|\\.)*)"\r?$', text
                    )
                    self.assertEqual(len(lines), 1)
                    value = lines[0]
                    self.assertTrue(value.strip())
                    for character in ("\u2013", "\u2014", "\u00ab", "\u00bb"):
                        self.assertNotIn(character, value)
                    if key.endswith("_desc"):
                        self.assertNotRegex(value, r"[§£%]|\d")
            committee = "\n".join(
                line for line in text.splitlines() if line.startswith((" WRK_exec_", " WRK_executive_"))
            )
            self.assertNotIn("Бэгли", committee)
        self.assertIn("Багли", self.localisations["Russian"]["WRK_exec_paid_cadre_desc"])
        self.assertIn("Bagley", self.localisations["English"]["WRK_exec_paid_cadre_desc"])


if __name__ == "__main__":
    unittest.main()
