from __future__ import annotations

from collections import Counter
import re
import unittest

from tools.validators.validate_adiscord_vorkerland_civil_war_focus import (
    ACTIVE_PHASE_FLAGS,
    CLAIMANT_EVENTS_FILE,
    CLAIMANT_FOCUS_EVENT_IDS,
    CLAIMANT_NEWS_EVENT_IDS,
    CENTRAL_CAPSTONES,
    CENTRAL_PREPARED_FLAG,
    CHARACTER_FILE,
    COLLAPSE_IDEAS_FILE,
    CONTINUOUS_FOCUS_FILE,
    CORE_DECISIONS,
    DIPLOMACY_DECISIONS_FILE,
    DIPLOMACY_EFFECTS_FILE,
    DORMANT_WRK_CRISIS_IDEAS,
    DORMANT_WRK_SCRUB_EFFECT,
    ENGLISH_LOCALISATION,
    ENGLISH_POSTWAR_IDEA_LOCALISATION,
    FOCUS_DECISIONS_FILE,
    FOCUS_EXPANSION_IDEAS,
    FOCUS_EXPANSION_IDEAS_FILE,
    FOCUS_FILE,
    FOCUS_IDS,
    IVANLAND_EXPEDITIONARY_IDEA,
    LAND_REPAIR_IDEAS,
    LATE_WAR_PHASE_FLAGS,
    MOBILE_REPAIR_IDEA,
    PHASE_EFFECTS_FILE,
    POSTWAR_PHASE,
    POSTWAR_IDEA_LOCALISATION_IDS,
    POSTWAR_POLICY_CHOICE_PAIRS,
    POSTWAR_ROUTE_FOCUSES,
    POSTWAR_ROUTE_TERMINALS,
    POSTWAR_SETTLEMENT_IDEAS,
    POSTWAR_TRANSITIONAL_IDEAS,
    PREWAR_CARRYOVER_EFFECT,
    PREWAR_CARRYOVER_FLAG,
    PREWAR_COURSE_SELECTIONS,
    PREWAR_EXPANSION_COSTS,
    PREWAR_EXPANSION_POSITIONS,
    PREWAR_EXPANSION_PREREQUISITES,
    PREWAR_PHASE,
    PREWAR_VAD_BASE_FOCUSES,
    PREWAR_VAD_EXPANSION_FOCUSES,
    PREWAR_VAD_FOCUSES,
    PREWAR_WRK_BASE_FOCUSES,
    PREWAR_WRK_CARRYOVER_FOCUSES,
    PREWAR_WRK_EXPANSION_FOCUSES,
    PREWAR_WRK_FOCUSES,
    RETREAT_HOOKS,
    ROOT,
    RUSSIAN_LOCALISATION,
    RUSSIAN_POSTWAR_IDEA_LOCALISATION,
    SHINE_FILE,
    SHOWDOWN_AI_PLANS,
    SHOWDOWN_COSTS,
    SHOWDOWN_FOCUSES,
    SHOWDOWN_POSITIONS,
    SHOWDOWN_PREREQUISITES,
    TVA_AI_PLAN_FILE,
    TVA_OPTIONAL_AI_PLANS,
    TVA_OPTIONAL_COSTS,
    TVA_OPTIONAL_OUTCOME_FOCUSES,
    TVA_OPTIONAL_POSITIONS,
    TVA_OPTIONAL_TIMED_IDEAS,
    TVA_OPTIONAL_WARTIME_FOCUSES,
    RETIRED_WARTIME_FOCUSES,
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
    VORKERLAND_CONTINUOUS_FOCUS_CONTRACTS,
    VORKERLAND_CONTINUOUS_FOCUSES,
    WARTIME_OUTCOME_EXCLUSIONS,
    WARTIME_OUTCOME_FALSE_GATE_TOKENS,
    WARTIME_ROUTE_IDENTITIES,
    WARTIME_TERMINALS,
    WORX_ADAPTIVE_LOGISTICS_IDEA,
    WORX_FIELD_DIRECTORATE_IDEAS,
    WORX_POSTWAR_PROVISIONAL_IDEAS,
    WORX_WARTIME_TIMED_IDEAS,
    WORKER_REFORM_INHERIT_EFFECT,
    WORKER_REFORM_STAGE_IDEAS,
    WRK_FORMATION_EFFECTS,
    _blocks,
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
)


class VorkerlandLifecycleFocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = read(FOCUS_FILE)
        cls.blocks = focus_blocks(cls.source)
        cls.continuous_source = read(CONTINUOUS_FOCUS_FILE)
        cls.continuous_blocks = focus_blocks(cls.continuous_source)
        cls.phase_effects = read(PHASE_EFFECTS_FILE)
        cls.collapse_ideas = read(COLLAPSE_IDEAS_FILE)
        cls.focus_expansion_ideas = read(FOCUS_EXPANSION_IDEAS_FILE)
        cls.claimant_events = read(CLAIMANT_EVENTS_FILE)
        cls.diplomacy_effects = read(DIPLOMACY_EFFECTS_FILE)
        cls.wkr_ai_plans = read(WKR_AI_PLAN_FILE)
        cls.vad_ai_plans = read(VAD_AI_PLAN_FILE)
        cls.tva_ai_plans = read(TVA_AI_PLAN_FILE)

    def test_integrated_focus_contract(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_one_tree_follows_all_four_lifecycle_tags(self) -> None:
        selector = self.source.split("default = no", maxsplit=1)[0]
        for tag in ("WRK", "WKR", "VAD", "TVA"):
            self.assertEqual(selector.count(f"tag = {tag}"), 1)
        self.assertNotIn("original_tag", selector)

    def test_manifest_has_one_hundred_fifty_one_bounded_definitions(self) -> None:
        self.assertEqual(tuple(self.blocks), FOCUS_IDS)
        self.assertEqual(len(self.blocks), 151)
        self.assertEqual(len(PREWAR_WRK_FOCUSES), 10)
        self.assertEqual(len(PREWAR_VAD_FOCUSES), 10)
        self.assertEqual(len(PREWAR_WRK_EXPANSION_FOCUSES), 4)
        self.assertEqual(len(PREWAR_VAD_EXPANSION_FOCUSES), 4)
        self.assertEqual(len(RETIRED_WARTIME_FOCUSES), 3)
        self.assertEqual(
            {tag: len(route) for tag, route in WARTIME_ROUTE_FOCUSES.items()},
            {"WKR": 17, "VAD": 17, "TVA": 18},
        )
        self.assertEqual(len(WKR_OPTIONAL_WARTIME_FOCUSES), 6)
        self.assertEqual(len(VAD_OPTIONAL_WARTIME_FOCUSES), 9)
        self.assertEqual(len(VAD_LATE_WAR_BRIDGE_FOCUSES), 4)
        self.assertEqual(len(TVA_OPTIONAL_WARTIME_FOCUSES), 10)
        self.assertEqual(
            {tag: len(focuses) for tag, focuses in SHOWDOWN_FOCUSES.items()},
            {"WKR": 7, "VAD": 5, "TVA": 5},
        )
        self.assertTrue(all(len(route) == 10 for route in POSTWAR_ROUTE_FOCUSES.values()))

    def test_each_claimant_has_a_compact_wartime_route(self) -> None:
        for tag, expected in {"WKR": 17, "VAD": 17, "TVA": 18}.items():
            with self.subTest(tag=tag):
                self.assertEqual(len(WARTIME_ROUTE_FOCUSES[tag]), expected)
                source = "\n".join(self.blocks[focus_id] for focus_id in WARTIME_ROUTE_FOCUSES[tag])
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
            terminal.count("ADISCORD_vorkerland_attempt_wkr_solyarino_intervention = yes"),
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
                position = (
                    int(re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block).group(1)),
                    int(re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block).group(1)),
                )
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
                self.assertEqual(len(reachable), 6)

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

                position = (
                    int(re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block).group(1)),
                    int(re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block).group(1)),
                )
                self.assertEqual(position, VAD_LATE_WAR_BRIDGE_POSITIONS[focus_id])
                colliding = []
                for other_id, other_block in self.blocks.items():
                    if other_id == focus_id:
                        continue
                    x_match = re.search(
                        r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", other_block
                    )
                    y_match = re.search(
                        r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", other_block
                    )
                    if x_match and y_match and (
                        int(x_match.group(1)),
                        int(y_match.group(1)),
                    ) == position:
                        colliding.append(other_id)
                self.assertEqual(colliding, [])
                self.assertEqual(_focus_cost(block), VAD_LATE_WAR_BRIDGE_COSTS[focus_id])
                self.assertEqual(
                    _prerequisite_groups(block),
                    VAD_LATE_WAR_BRIDGE_PREREQUISITES[focus_id],
                )
                rewards = _blocks(block, "completion_reward")
                self.assertEqual(len(rewards), 1)
                for token in VAD_LATE_WAR_BRIDGE_REWARDS[focus_id]:
                    self.assertEqual(rewards[0].count(token), 1)
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
            _prerequisite_groups(
                self.blocks["VAD_reconcile_emergency_district_rolls"]
            ),
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
                    self.blocks[focus_id].count(
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
                "type = support_equipment amount = 50 producer = VAD",
                "bonus = 0.50 uses = 1 category = industry",
            ),
            "VAD_standardize_district_logistics": (
                "type = support_equipment amount = 60 producer = VAD",
                "ADISCORD_vorkerland_vad_standardized_logistics days = 70",
            ),
            "VAD_reconstitute_district_guard": (
                "type = infantry_equipment_0 amount = 100 producer = VAD",
                "type = support_equipment amount = 40 producer = VAD",
            ),
        }
        for focus_id, tokens in strengthened.items():
            for token in tokens:
                self.assertIn(token, self.blocks[focus_id])

    def test_tva_optional_depth_is_six_focus_outcome_specific_and_capstone_neutral(self) -> None:
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
                self.assertIn("has_government = technocracy", block)
                self.assertIn("character = TVA_Dorian_Worx", block)
                self.assertNotIn("declare_war_on", block)
                self.assertNotIn("ADISCORD_vorkerland_tva_field_directorate_3", block)
                self.assertNotIn("phase_worx_client_administration", block)
                self.assertNotIn("phase_worx_fragmentation", block)
                position = (
                    int(re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block).group(1)),
                    int(re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block).group(1)),
                )
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

    def test_tva_optional_depth_uses_bounded_spirits_event_and_level_two_ceiling(self) -> None:
        for focus_id, (idea_id, days) in TVA_OPTIONAL_TIMED_IDEAS.items():
            with self.subTest(focus_id=focus_id):
                self.assertEqual(
                    self.blocks[focus_id].count(
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
            iteration.count(
                "add_timed_idea = { idea = ADISCORD_vorkerland_worx_second_protocol days = 120 }"
            ),
            1,
        )
        self.assertNotIn("field_directorate_3", iteration)

    def test_vad_solar_settlement_uses_existing_bounded_retry_lane(self) -> None:
        terminal = self.blocks["VAD_define_the_solar_settlement"]
        self.assertIn("country_event = { id = ADISCORD_vorkerland_claimant.14 hours = 1 }", terminal)
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
        policy_event = "country_event = { id = ADISCORD_vorkerland_claimant.14 hours = 1 }"
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
            verify.count("country_event = { id = ADISCORD_vorkerland_diplomacy.9 days = 1 }"),
            1,
        )

    def test_wkr_ai_plans_reach_capstone_before_solyarino(self) -> None:
        expected = {
            "ADISCORD_vorkerland_wkr_pragmatist_core_plan": (
                "WRK_Nikita_Worcker",
                (
                    "WKR_affirm_worker_mandate",
                    "WKR_establish_workers_air_command",
                    "WKR_raise_mobile_fortification_crews",
                    "WKR_organize_factory_battalions",
                    "WKR_put_railways_under_councils",
                    "WKR_keep_frontline_sorties_flying",
                    "WKR_convene_front_soviets",
                    "WKR_train_shopfloor_officers",
                    "WKR_form_revolutionary_supply_commission",
                    "WKR_secure_the_southern_corridor",
                    "WKR_open_free_republics_channel",
                    "WKR_authorize_retreat_levies",
                    "WKR_reopen_collective_workshops",
                    "WKR_rehearse_operation_southbound",
                    "WKR_publish_emergency_constitution",
                    "WKR_coordinate_counterattack_cells",
                    "WKR_stockpile_interchange_reserves",
                    "WKR_settle_front_authority",
                    "WKR_republic_fights_as_one",
                ),
            ),
            "ADISCORD_vorkerland_wkr_utilitarian_core_plan": (
                "WRK_Anton_Bagley",
                (
                    "WKR_affirm_worker_mandate",
                    "WKR_establish_workers_air_command",
                    "WKR_raise_mobile_fortification_crews",
                    "WKR_organize_factory_battalions",
                    "WKR_put_railways_under_councils",
                    "WKR_keep_frontline_sorties_flying",
                    "WKR_empower_front_executive",
                    "WKR_train_shopfloor_officers",
                    "WKR_form_revolutionary_supply_commission",
                    "WKR_secure_the_southern_corridor",
                    "WKR_authorize_normative_command",
                    "WKR_authorize_retreat_levies",
                    "WKR_reopen_collective_workshops",
                    "WKR_rehearse_operation_southbound",
                    "WKR_bind_workshops_to_directive",
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
                actual = tuple(
                    re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list)
                )
                self.assertEqual(actual, expected_focuses)
                self.assertEqual(actual[-1], "WKR_republic_fights_as_one")
                self.assertLess(
                    actual.index("WKR_raise_mobile_fortification_crews"),
                    actual.index("WKR_organize_factory_battalions"),
                )
                self.assertIn(f"character = {leader}", plan)
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
                "VAD_map_the_solar_corridors",
                "VAD_preposition_restoration_columns",
                "VAD_define_the_solar_settlement",
                *VAD_LATE_WAR_BRIDGE_FOCUSES,
            ),
            "ADISCORD_vorkerland_vad_joint_depth_plan": (
                "VAD_elect_district_commissars",
                "VAD_merge_guard_and_worker_rolls",
                "VAD_sign_the_dual_authority_protocol",
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
                actual = tuple(
                    re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list)
                )
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
                actual = tuple(
                    re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_list)
                )
                self.assertEqual(actual, expected_focuses)
                self.assertEqual(len(actual), 6)
                self.assertIn(f"has_country_flag = {metric_flag}", plan)
                self.assertIn(f"has_country_flag = {trial_flag}", plan)
                self.assertIn("weight = { factor = 5 }", plan)

    def test_each_wartime_outcome_reaches_fourteen_completable_definitions(self) -> None:
        for tag, exclusions in WARTIME_OUTCOME_EXCLUSIONS.items():
            route = set(WARTIME_ROUTE_FOCUSES[tag])
            capstone = CENTRAL_CAPSTONES[tag][0]
            self.assertEqual(len(WARTIME_OUTCOME_FALSE_GATE_TOKENS[tag]), len(exclusions))
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
            positions = []
            for focus_id in focus_ids:
                block = self.blocks[focus_id]
                x = int(re.search(r"(?m)^\s*x\s*=\s*(\d+)$", block).group(1))
                y = int(re.search(r"(?m)^\s*y\s*=\s*(\d+)$", block).group(1))
                positions.append((x, y))
            with self.subTest(tag=tag):
                self.assertEqual(len(positions), len(set(positions)))
                self.assertLessEqual(max(y for _x, y in positions) - min(y for _x, y in positions), 6)

    def test_showdown_expansion_has_exact_geometry_graph_and_live_war_gate(self) -> None:
        opponents = {
            "WKR": {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "VAD", "TVA"},
            "VAD": {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "WKR", "TVA"},
            "TVA": {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "WKR", "VAD"},
        }
        for tag, focus_ids in SHOWDOWN_FOCUSES.items():
            positions = set()
            for focus_id in focus_ids:
                block = self.blocks[focus_id]
                position = tuple(
                    int(
                        re.search(
                            rf"(?m)^\s*{axis}\s*=\s*(-?\d+)\s*$", block
                        ).group(1)
                    )
                    for axis in ("x", "y")
                )
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
                self.assertIn(idea_id, expansion_focuses)
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

    def test_real_claimant_identities_gate_each_asymmetric_political_route(self) -> None:
        for focus_ids, identity_tokens in WARTIME_ROUTE_IDENTITIES:
            for focus_id in focus_ids:
                allow = _blocks(self.blocks[focus_id], "allow_branch")[0]
                for token in identity_tokens:
                    with self.subTest(focus_id=focus_id, token=token):
                        self.assertIn(token, allow)

    def test_prewar_blocks_are_separate_and_phase_bounded(self) -> None:
        for tag, focus_ids in (("WRK", PREWAR_WRK_FOCUSES), ("VAD", PREWAR_VAD_FOCUSES)):
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), {PREWAR_PHASE})
                    self.assertIn(f"allow_branch = {{ tag = {tag}", block)

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
                _focus_cost(self.blocks[focus_id]) == 5
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

    def test_prewar_expansion_has_exact_routes_geometry_and_course_switching(self) -> None:
        for focus_id in (
            *PREWAR_WRK_EXPANSION_FOCUSES,
            *PREWAR_VAD_EXPANSION_FOCUSES,
        ):
            block = self.blocks[focus_id]
            position = tuple(
                int(
                    re.search(
                        rf"(?m)^\s*{axis}\s*=\s*(-?\d+)\s*$", block
                    ).group(1)
                )
                for axis in ("x", "y")
            )
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
            "VAD_ratify_emergency_compact": "ADISCORD_vorkerland_vad_compact_committed",
        }.items():
            reward = _blocks(self.blocks[focus_id], "completion_reward")[0]
            self.assertEqual(
                reward.count("ADISCORD_vorkerland_resolve_prewar_compact = yes"),
                1,
            )
            self.assertEqual(
                reward.count(f"set_country_flag = {final_flag}"), 1
            )

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
            "add_manpower = 250",
            "type = infantry_equipment_0 amount = 150 producer = WKR",
            "idea = ADISCORD_vorkerland_wrk_loyal_republics_mobilized days = 70",
            "set_country_flag = ADISCORD_vorkerland_wrk_hardline_committed",
            "set_country_flag = ADISCORD_vorkerland_focus_wrk_reserves_under_worker",
        ):
            with self.subTest(hardline_token=token):
                self.assertEqual(hardline.count(token), 1)

        verify = _blocks(
            self.phase_effects, "ADISCORD_vorkerland_verify_collapse_materialized"
        )[0]
        wkr_tree_scopes = [
            scope for scope in _blocks(verify, "WKR") if "load_focus_tree" in scope
        ]
        self.assertEqual(len(wkr_tree_scopes), 1)
        self.assertIn(f"{PREWAR_CARRYOVER_EFFECT} = yes", wkr_tree_scopes[0])

    def test_all_winner_formations_normalize_the_dormant_wrk_before_annex(self) -> None:
        scrub = _blocks(self.phase_effects, DORMANT_WRK_SCRUB_EFFECT)[0]
        scrubbed_ideas = Counter(
            re.findall(r"\bremove_ideas\s*=\s*([A-Za-z0-9_]+)", scrub)
        )
        for idea_id in DORMANT_WRK_CRISIS_IDEAS:
            with self.subTest(scrubbed_idea=idea_id):
                self.assertEqual(scrubbed_ideas[idea_id], 1)

        worker_inheritance = _blocks(
            self.phase_effects, WORKER_REFORM_INHERIT_EFFECT
        )[0]
        self.assertEqual(
            worker_inheritance.count(f"{DORMANT_WRK_SCRUB_EFFECT} = yes"), 1
        )

        for winner_tag, formation_name in WRK_FORMATION_EFFECTS.items():
            with self.subTest(winner_tag=winner_tag):
                formation = _blocks(self.phase_effects, formation_name)[0]
                route_bridge = (
                    WORKER_REFORM_INHERIT_EFFECT
                    if winner_tag == "WKR"
                    else DORMANT_WRK_SCRUB_EFFECT
                )
                bridge_token = f"{route_bridge} = yes"
                annex_token = (
                    f"annex_country = {{ target = {winner_tag} transfer_troops = yes }}"
                )
                self.assertEqual(formation.count(bridge_token), 1)
                self.assertEqual(formation.count(annex_token), 1)
                self.assertLess(formation.index(bridge_token), formation.index(annex_token))

    def test_worker_formation_inherits_one_exact_stage_from_each_reform_chain(self) -> None:
        inheritance = _blocks(self.phase_effects, WORKER_REFORM_INHERIT_EFFECT)[0]
        self.assertEqual(len(_blocks(inheritance, "if")), 2)
        self.assertEqual(len(_blocks(inheritance, "else_if")), 4)
        inherited_ideas = Counter(
            re.findall(r"\badd_ideas\s*=\s*([A-Za-z0-9_]+)", inheritance)
        )
        self.assertEqual(inherited_ideas, Counter(WORKER_REFORM_STAGE_IDEAS))
        for idea_id in WORKER_REFORM_STAGE_IDEAS:
            with self.subTest(idea_id=idea_id):
                self.assertEqual(
                    inheritance.count(f"WKR = {{ has_idea = {idea_id} }}"), 1
                )

        formation = _blocks(
            self.phase_effects, WRK_FORMATION_EFFECTS["WKR"]
        )[0]
        self.assertLess(
            formation.index(f"{WORKER_REFORM_INHERIT_EFFECT} = yes"),
            formation.index("annex_country = { target = WKR transfer_troops = yes }"),
        )

    def test_wartime_routes_are_isolated_and_bounded(self) -> None:
        for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
            for focus_id in focus_ids:
                with self.subTest(focus_id=focus_id):
                    block = self.blocks[focus_id]
                    self.assertEqual(_phase_flags(block), ACTIVE_PHASE_FLAGS)
                    self.assertIn(f"tag = {tag}", block)
                    self.assertEqual(len(_blocks(block, "bypass")), 1)
                    for other in {"WKR", "VAD", "TVA"} - {tag}:
                        self.assertNotIn(f"tag = {other}", block)
            route = "\n".join(self.blocks[focus_id] for focus_id in focus_ids)
            self.assertGreaterEqual(route.count("modifier ="), 3)

    def test_military_terminal_unlocks_retreat_levies_once(self) -> None:
        for tag, hook in RETREAT_HOOKS.items():
            route = "\n".join(self.blocks[focus_id] for focus_id in WARTIME_ROUTE_FOCUSES[tag])
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
            ("TVA_delegate_to_algorithmic_board", "TVA_protect_irreplaceable_specialists"),
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
                    self.blocks[focus_id],
                )
                self.assertEqual(len(_blocks(self.collapse_ideas, idea_id)), 1)

    def test_worx_adaptive_trial_grants_its_ninety_day_spirit(self) -> None:
        focus = self.blocks["TVA_test_adaptive_logistics"]
        reward = (
            f"add_timed_idea = {{ idea = {WORX_ADAPTIVE_LOGISTICS_IDEA} days = 90 }}"
        )
        self.assertEqual(focus.count(reward), 1)
        self.assertEqual(
            len(_blocks(self.collapse_ideas, WORX_ADAPTIVE_LOGISTICS_IDEA)), 1
        )

    def test_operational_loop_does_not_repeat_level_two_and_formation_has_level_three(self) -> None:
        close_loop = self.blocks["TVA_close_operational_loop"]
        self.assertNotIn(
            "ADISCORD_vorkerland_tva_field_directorate", close_loop
        )
        self.assertIn(
            "TVA_standardize_emergency_administration", _prerequisites(close_loop)
        )

        standardize = self.blocks["TVA_standardize_emergency_administration"]
        self.assertEqual(standardize.count("else = { add_war_support = 0.01 }"), 1)

        formation = _blocks(
            self.phase_effects, "ADISCORD_vorkerland_form_wrk_from_tva"
        )
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
            focus.count(
                "type = energy_infrastructure level = 1 instant_build = yes"
            ),
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

    def test_each_wartime_route_has_political_military_and_economic_rewards(self) -> None:
        reward_classes = (
            ("add_political_power", "add_stability"),
            ("army_experience", "add_command_power", "add_manpower", "add_war_support"),
            ("add_equipment_to_stockpile", "add_building_construction", "add_timed_idea"),
        )
        for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
            source = "\n".join(self.blocks[focus_id] for focus_id in focus_ids)
            for tokens in reward_classes:
                with self.subTest(tag=tag, tokens=tokens):
                    self.assertTrue(any(token in source for token in tokens))

    def test_mobile_repair_train_focus_grants_a_concrete_timed_spirit(self) -> None:
        focus = self.blocks["TVA_build_mobile_repair_trains"]
        reward = f"add_timed_idea = {{ idea = {MOBILE_REPAIR_IDEA} days = 35 }}"
        self.assertEqual(focus.count(reward), 1)
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
        diplomacy = read(DIPLOMACY_DECISIONS_FILE)
        support = read(FOCUS_DECISIONS_FILE)
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
            event_ids, [*CLAIMANT_FOCUS_EVENT_IDS, *CLAIMANT_NEWS_EVENT_IDS]
        )
        self.assertEqual(
            self.claimant_events.count("fire_only_once = yes"), len(event_ids)
        )
        for event_id in CLAIMANT_NEWS_EVENT_IDS:
            self.assertEqual(self.claimant_events.count(f"id = {event_id}"), 2)

        by_id = {
            re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_.]+)\s*$", block).group(1): block
            for block in definitions
        }
        for event_id, option_count in {
            "ADISCORD_vorkerland_claimant.4": 4,
            "ADISCORD_vorkerland_claimant.13": 4,
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
                    self.assertIn("tag = WRK", block)
                    self.assertIn(f"has_country_flag = {route_flag}", block)
    def test_postwar_routes_have_two_reachable_189_day_policy_paths(self) -> None:
        for route_flag, focus_ids in POSTWAR_ROUTE_FOCUSES.items():
            terminal_id = POSTWAR_ROUTE_TERMINALS[route_flag]
            paths = _postwar_completion_paths(self.blocks, focus_ids, terminal_id)
            with self.subTest(route_flag=route_flag):
                self.assertEqual(len(focus_ids), 10)
                self.assertEqual(_focus_cost(self.blocks[terminal_id]), 5)
                self.assertEqual(len(paths), 2)
                self.assertEqual({len(path) for path in paths}, {9})
                self.assertEqual(
                    {
                        sum(_focus_cost(self.blocks[focus_id]) for focus_id in path)
                        for path in paths
                    },
                    {27},
                )
                self.assertEqual(set().union(*paths), set(focus_ids))

    def test_postwar_policy_choices_are_real_ai_weighted_forks(self) -> None:
        for left, right in POSTWAR_POLICY_CHOICE_PAIRS:
            with self.subTest(left=left, right=right):
                self.assertIn(right, _mutually_exclusive_focuses(self.blocks[left]))
                self.assertIn(left, _mutually_exclusive_focuses(self.blocks[right]))
                self.assertTrue(_blocks(_blocks(self.blocks[left], "ai_will_do")[0], "modifier"))
                self.assertTrue(_blocks(_blocks(self.blocks[right], "ai_will_do")[0], "modifier"))

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

    def test_postwar_capstones_install_one_mutually_exclusive_lasting_settlement(self) -> None:
        for capstone_id, (settlement_idea, incompatible_ideas) in POSTWAR_SETTLEMENT_IDEAS.items():
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

    def test_worx_postwar_programmes_build_and_consolidate_real_institutions(self) -> None:
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

    def test_dorian_worx_is_the_existing_technocrat_with_authored_portrait(self) -> None:
        definitions = _blocks(read(CHARACTER_FILE), "TVA_Dorian_Worx")
        self.assertEqual(len(definitions), 1)
        worx = definitions[0]
        self.assertIn("ideology = technocracy_ideology", worx)
        self.assertIn("large = GFX_portrait_WRK_Dorian_Worx", worx)

        english = localisation_entries(read(ENGLISH_LOCALISATION))
        russian = localisation_entries(read(RUSSIAN_LOCALISATION))
        self.assertIn("Worx", english["TVA_codify_utilitarian_directorate"])
        self.assertIn("Technocratic", english["TVA_codify_utilitarian_directorate"])
        self.assertIn(
            "Technocratic Republic",
            english["WRK_utilitarian_build_measurable_republic"],
        )
        self.assertIn("Воркс", russian["TVA_codify_utilitarian_directorate"])
        self.assertIn("технократ", russian["TVA_codify_utilitarian_directorate"].lower())
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
                    set(localisation_entries(read(localisation))), expected_keys
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
        decisions = read(FOCUS_DECISIONS_FILE)
        for decision_id in CORE_DECISIONS:
            with self.subTest(decision_id=decision_id):
                start = decisions.index(f"\t{decision_id} = {{")
                next_block = decisions.find("\n\tADISCORD_", start + 1)
                block = decisions[start : next_block if next_block != -1 else len(decisions)]
                self.assertIn(f"has_country_flag = {hook}", block)

    def test_retired_fillers_and_claimant_events_cannot_own_wars_or_phases(self) -> None:
        for focus_id in RETIRED_WARTIME_FOCUSES:
            with self.subTest(focus_id=focus_id):
                block = self.blocks[focus_id]
                self.assertIn("allow_branch = { always = no }", block)
                self.assertIn("available = { always = no }", block)
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
        for token in ("every_country", "random_country", "on_monthly", "monthly_pulse", "Lucas", "lucas"):
            self.assertNotIn(token, self.source)
            self.assertNotIn(token, self.claimant_events)

    def test_each_claimant_capstone_sets_decision_gate_and_reports_readiness(self) -> None:
        hooks = {
            "WKR": ("WKR_republic_fights_as_one", "ADISCORD_vorkerland_focus_wkr_central_war_unlocked"),
            "VAD": ("VAD_balance_council_and_command", "ADISCORD_vorkerland_focus_vad_central_war_unlocked"),
            "TVA": ("TVA_close_operational_loop", "ADISCORD_vorkerland_focus_tva_central_war_unlocked"),
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

    def test_every_focus_icon_has_an_explicit_shine_sprite(self) -> None:
        shine = read(SHINE_FILE)
        for focus_id, block in self.blocks.items():
            icon_line = next(line.strip() for line in block.splitlines() if line.strip().startswith("icon = "))
            icon = icon_line.split("=", maxsplit=1)[1].strip()
            with self.subTest(focus_id=focus_id, icon=icon):
                self.assertIn(f'name = "{icon}_shine"', shine)

    def test_route_signature_focuses_have_distinct_icons(self) -> None:
        expected = {
            "WKR_republic_fights_as_one": "GFX_goal_generic_allies_build_infantry",
            "VAD_proclaim_joint_charter": "GFX_goal_generic_military_sphere",
            "VAD_balance_council_and_command": "GFX_goal_generic_national_unity",
            "TVA_codify_utilitarian_directorate": "GFX_goal_generic_production",
            "TVA_close_operational_loop": "GFX_goal_generic_scientific_exchange",
            "WRK_joint_impose_reunification_settlement": "GFX_goal_generic_political_pressure",
            "WRK_utilitarian_build_measurable_republic": "GFX_goal_generic_production",
        }
        for focus_id, expected_icon in expected.items():
            icon_line = next(
                line.strip()
                for line in self.blocks[focus_id].splitlines()
                if line.strip().startswith("icon = ")
            )
            with self.subTest(focus_id=focus_id):
                self.assertEqual(icon_line, f"icon = {expected_icon}")

    def test_three_continuous_focuses_are_vorkerland_only_and_modifier_bounded(
        self,
    ) -> None:
        self.assertEqual(tuple(self.continuous_blocks), VORKERLAND_CONTINUOUS_FOCUSES)
        palettes = _blocks(self.continuous_source, "continuous_focus_palette")
        self.assertEqual(len(palettes), 1)
        header = palettes[0].split("focus =", maxsplit=1)[0]
        for token in (
            "id = generic_focus",
            "country = { factor = 1 }",
            "default = yes",
            "reset_on_civilwar = no",
        ):
            self.assertIn(token, header)

        gate_tokens = (
            "AND = { tag = WKR has_country_flag = ADISCORD_vorkerland_focus_wkr_central_war_unlocked }",
            "AND = { tag = VAD has_country_flag = ADISCORD_vorkerland_focus_vad_central_war_unlocked }",
            "AND = { tag = TVA has_country_flag = ADISCORD_vorkerland_focus_tva_central_war_unlocked }",
            "AND = { tag = WRK has_global_flag = ADISCORD_vorkerland_phase_postwar_integration }",
        )
        for focus_id in VORKERLAND_CONTINUOUS_FOCUSES:
            with self.subTest(focus_id=focus_id):
                block = self.continuous_blocks[focus_id]
                for assignment in ("available", "enable"):
                    gates = _blocks(block, assignment)
                    self.assertEqual(len(gates), 1)
                    self.assertEqual(
                        set(
                            re.findall(
                                r"\btag\s*=\s*([A-Z0-9]{3})\b", gates[0]
                            )
                        ),
                        {"WRK", "WKR", "VAD", "TVA"},
                    )
                    for token in gate_tokens:
                        self.assertEqual(gates[0].count(token), 1)

                icon, strategy, modifier_tokens = (
                    VORKERLAND_CONTINUOUS_FOCUS_CONTRACTS[focus_id]
                )
                self.assertEqual(block.count(f"icon = {icon}"), 1)
                self.assertEqual(
                    block.count(f"supports_ai_strategy = {strategy}"), 1
                )
                self.assertEqual(block.count("daily_cost = 1"), 1)
                self.assertEqual(block.count("available_if_capitulated = no"), 1)
                self.assertEqual(len(_blocks(block, "ai_will_do")), 1)
                for token in modifier_tokens:
                    self.assertEqual(block.count(token), 1)
                for forbidden in (
                    "completion_reward",
                    "add_manpower",
                    "add_equipment_to_stockpile",
                    "add_political_power",
                    "add_stability",
                    "set_country_flag",
                    "set_global_flag",
                ):
                    self.assertNotIn(forbidden, block)

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
        self.assertTrue((ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
