#!/usr/bin/env python3
"""Validate the WRK/WKR/VAD/TVA lifecycle focus tree."""

from __future__ import annotations

from collections import Counter
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

FOCUS_FILE = Path("common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt")
CONTINUOUS_FOCUS_FILE = Path("common/continuous_focus/generic.txt")
ENGLISH_LOCALISATION = Path(
    "localisation/english/ADISCORD_vorkerland_civil_war_focus_l_english.yml"
)
RUSSIAN_LOCALISATION = Path(
    "localisation/russian/ADISCORD_vorkerland_civil_war_focus_l_russian.yml"
)
ENGLISH_COLLAPSE_LOCALISATION = Path(
    "localisation/english/ADISCORD_vorkerland_collapse_l_english.yml"
)
RUSSIAN_COLLAPSE_LOCALISATION = Path(
    "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml"
)
ENGLISH_POSTWAR_IDEA_LOCALISATION = Path(
    "localisation/english/ADISCORD_vorkerland_postwar_ideas_l_english.yml"
)
RUSSIAN_POSTWAR_IDEA_LOCALISATION = Path(
    "localisation/russian/ADISCORD_vorkerland_postwar_ideas_l_russian.yml"
)
CHARACTER_FILE = Path("common/characters/ADISCORD_vorkerland_collapse_characters.txt")
SHINE_FILE = Path("interface/goals_shine.gfx")
FOCUS_DECISIONS_FILE = Path("common/decisions/ADISCORD_vorkerland_focus_decisions.txt")
DIPLOMACY_DECISIONS_FILE = Path(
    "common/decisions/ADISCORD_vorkerland_diplomacy_decisions.txt"
)
DIPLOMACY_EFFECTS_FILE = Path(
    "common/scripted_effects/ADISCORD_vorkerland_diplomacy_effects.txt"
)
PHASE_EFFECTS_FILE = Path(
    "common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt"
)
COLLAPSE_IDEAS_FILE = Path("common/ideas/ADISCORD_vorkerland_collapse_ideas.txt")
FOCUS_EXPANSION_IDEAS_FILE = Path(
    "common/ideas/ADISCORD_vorkerland_focus_expansion_ideas.txt"
)
CLAIMANT_EVENTS_FILE = Path("events/ADISCORD_vorkerland_claimant_events.txt")
WKR_AI_PLAN_FILE = Path(
    "common/ai_strategy_plans/ADISCORD_vorkerland_wkr_wartime_plan.txt"
)
VAD_AI_PLAN_FILE = Path(
    "common/ai_strategy_plans/ADISCORD_vorkerland_vad_wartime_plan.txt"
)
TVA_AI_PLAN_FILE = Path(
    "common/ai_strategy_plans/ADISCORD_vorkerland_tva_wartime_plan.txt"
)

PREWAR_WRK_BASE_FOCUSES = (
    "WRK_measure_confederation_fault_lines",
    "WRK_convene_council_of_republics",
    "WRK_inventory_emergency_stores",
    "WRK_bind_districts_to_charter",
    "WRK_disperse_railway_reserves",
    "WRK_issue_continuity_orders",
)

PREWAR_WRK_EXPANSION_FOCUSES = (
    "WRK_open_worker_vadl_backchannel",
    "WRK_offer_emergency_compact",
    "WRK_mobilize_loyal_republics",
    "WRK_place_reserves_under_worker",
)

PREWAR_WRK_FOCUSES = (*PREWAR_WRK_BASE_FOCUSES, *PREWAR_WRK_EXPANSION_FOCUSES)

PREWAR_VAD_BASE_FOCUSES = (
    "VAD_review_district_obligations",
    "VAD_open_continuity_registers",
    "VAD_drill_district_guard",
    "VAD_secure_administrative_archives",
    "VAD_disperse_eastern_depots",
    "VAD_form_emergency_chancery",
)

RETIRED_WARTIME_FOCUSES = (
    "ADISCORD_vorkerland_stabilize_claimant_regime",
    "ADISCORD_vorkerland_mobilize_field_forces",
    "ADISCORD_vorkerland_fortify_home_region",
)

PREWAR_VAD_EXPANSION_FOCUSES = (
    "VAD_prepare_vadl_worker_terms",
    "VAD_ratify_emergency_compact",
    "VAD_activate_eastern_mandate",
    "VAD_seal_district_arsenals",
)

PREWAR_VAD_FOCUSES = (*PREWAR_VAD_BASE_FOCUSES, *PREWAR_VAD_EXPANSION_FOCUSES)

WARTIME_ROUTE_FOCUSES = {
    "WKR": (
        "WKR_affirm_worker_mandate",
        "WKR_convene_front_soviets",
        "WKR_organize_factory_battalions",
        "WKR_put_railways_under_councils",
        "WKR_authorize_retreat_levies",
        "WKR_form_revolutionary_supply_commission",
        "WKR_train_shopfloor_officers",
        "WKR_open_free_republics_channel",
        "WKR_empower_front_executive",
        "WKR_reopen_collective_workshops",
        "WKR_publish_emergency_constitution",
        "WKR_authorize_normative_command",
        "WKR_bind_workshops_to_directive",
        "WKR_settle_front_authority",
        "WKR_coordinate_counterattack_cells",
        "WKR_stockpile_interchange_reserves",
        "WKR_republic_fights_as_one",
    ),
    "VAD": (
        "VAD_proclaim_joint_charter",
        "VAD_open_imperial_registers",
        "VAD_form_field_commandantures",
        "VAD_invite_sol_delegation",
        "VAD_establish_mobile_headquarters",
        "VAD_dispatch_solland_liaison_mission",
        "VAD_standardize_district_logistics",
        "VAD_reconstitute_district_guard",
        "VAD_inventory_eastern_works",
        "VAD_reopen_armament_depots",
        "VAD_restore_crown_commissions",
        "VAD_bind_officers_to_chancery",
        "VAD_guarantee_worker_committees",
        "VAD_ratify_joint_command",
        "VAD_settle_restoration_authority",
        "VAD_balance_council_and_command",
        "VAD_assemble_joint_general_staff",
    ),
    "TVA": (
        "TVA_codify_utilitarian_directorate",
        "TVA_reroute_city_grid",
        "TVA_deploy_field_laboratories",
        "TVA_raise_technical_battalions",
        "TVA_seal_the_approaches",
        "TVA_issue_emergency_output_norms",
        "TVA_build_mobile_repair_trains",
        "TVA_publish_operational_metrics",
        "TVA_optimize_for_throughput",
        "TVA_protect_irreplaceable_specialists",
        "TVA_standardize_emergency_administration",
        "TVA_delegate_to_algorithmic_board",
        "TVA_select_trial_protocol",
        "TVA_test_remote_fire_control",
        "TVA_test_adaptive_logistics",
        "TVA_integrate_field_results",
        "TVA_harden_switching_stations",
        "TVA_close_operational_loop",
    ),
}

WKR_OPTIONAL_WARTIME_FOCUSES = (
    "WKR_establish_workers_air_command",
    "WKR_keep_frontline_sorties_flying",
    "WKR_raise_mobile_fortification_crews",
    "WKR_secure_the_southern_corridor",
    "WKR_rehearse_operation_southbound",
    "WKR_intervene_in_solyarino",
)

VAD_OPTIONAL_WARTIME_FOCUSES = (
    "VAD_restore_prefectural_courts",
    "VAD_issue_crown_mobilization_warrants",
    "VAD_turn_the_chancery_into_a_war_cabinet",
    "VAD_elect_district_commissars",
    "VAD_merge_guard_and_worker_rolls",
    "VAD_sign_the_dual_authority_protocol",
    "VAD_map_the_solar_corridors",
    "VAD_preposition_restoration_columns",
    "VAD_define_the_solar_settlement",
)

VAD_LATE_WAR_BRIDGE_FOCUSES = (
    "VAD_reconcile_emergency_district_rolls",
    "VAD_restore_eastern_supply_corridors",
    "VAD_convert_emergency_workshops",
    "VAD_publish_interim_restoration_register",
)

TVA_OPTIONAL_WARTIME_FOCUSES = (
    "TVA_unattended_shifts",
    "TVA_delegate_fire_plans_to_board",
    "TVA_bunker_specialist_cadres",
    "TVA_standardize_assault_teams",
    "TVA_network_observation_posts",
    "TVA_mandate_modular_repair",
    "TVA_print_interchangeable_repair_modules",
    "TVA_preposition_switching_crews",
    "TVA_cross_validate_trial_logs",
    "TVA_authorize_iteration_two",
)

SHOWDOWN_FOCUSES = {
    "WKR": (
        "WKR_establish_front_operations_bureau",
        "WKR_authorize_republican_mission_commands",
        "WKR_issue_normative_campaign_tables",
        "WKR_form_rolling_factory_groups",
        "WKR_reopen_night_freight_corridors",
        "WKR_arm_the_mobile_reserve",
        "WKR_coordinate_the_rolling_front",
    ),
    "VAD": (
        "VAD_convene_campaign_directorate",
        "VAD_issue_prefectural_field_decrees",
        "VAD_seat_front_commissars",
        "VAD_standardize_restoration_columns",
        "VAD_advance_under_one_register",
    ),
    "TVA": (
        "TVA_merge_iteration_with_field_command",
        "TVA_mass_produce_assault_modules",
        "TVA_link_observers_to_fire_control",
        "TVA_turn_repair_trains_into_supply_web",
        "TVA_run_live_front_validation",
    ),
}

PREWAR_EXPANSION_POSITIONS = {
    "WRK_open_worker_vadl_backchannel": (0, 4),
    "WRK_offer_emergency_compact": (0, 5),
    "WRK_mobilize_loyal_republics": (4, 4),
    "WRK_place_reserves_under_worker": (4, 5),
    "VAD_prepare_vadl_worker_terms": (9, 4),
    "VAD_ratify_emergency_compact": (9, 5),
    "VAD_activate_eastern_mandate": (14, 4),
    "VAD_seal_district_arsenals": (14, 5),
}

PREWAR_EXPANSION_COSTS = {
    focus_id: 1 if focus_id in {
        "WRK_open_worker_vadl_backchannel",
        "WRK_mobilize_loyal_republics",
        "VAD_prepare_vadl_worker_terms",
        "VAD_activate_eastern_mandate",
    } else 2
    for focus_id in PREWAR_EXPANSION_POSITIONS
}

PREWAR_EXPANSION_PREREQUISITES = {
    "WRK_open_worker_vadl_backchannel": (frozenset({"WRK_issue_continuity_orders"}),),
    "WRK_offer_emergency_compact": (frozenset({"WRK_open_worker_vadl_backchannel"}),),
    "WRK_mobilize_loyal_republics": (frozenset({"WRK_issue_continuity_orders"}),),
    "WRK_place_reserves_under_worker": (frozenset({"WRK_mobilize_loyal_republics"}),),
    "VAD_prepare_vadl_worker_terms": (frozenset({"VAD_form_emergency_chancery"}),),
    "VAD_ratify_emergency_compact": (frozenset({"VAD_prepare_vadl_worker_terms"}),),
    "VAD_activate_eastern_mandate": (frozenset({"VAD_form_emergency_chancery"}),),
    "VAD_seal_district_arsenals": (frozenset({"VAD_activate_eastern_mandate"}),),
}

PREWAR_COURSE_SELECTIONS = {
    "WRK_open_worker_vadl_backchannel": (
        "ADISCORD_vorkerland_prewar_wrk_compact_course",
        "ADISCORD_vorkerland_prewar_wrk_hardline_course",
    ),
    "WRK_mobilize_loyal_republics": (
        "ADISCORD_vorkerland_prewar_wrk_hardline_course",
        "ADISCORD_vorkerland_prewar_wrk_compact_course",
    ),
    "VAD_prepare_vadl_worker_terms": (
        "ADISCORD_vorkerland_prewar_vad_compact_course",
        "ADISCORD_vorkerland_prewar_vad_hardline_course",
    ),
    "VAD_activate_eastern_mandate": (
        "ADISCORD_vorkerland_prewar_vad_hardline_course",
        "ADISCORD_vorkerland_prewar_vad_compact_course",
    ),
}

PREWAR_WRK_CARRYOVER_FOCUSES = (
    *PREWAR_WRK_BASE_FOCUSES,
    "WRK_place_reserves_under_worker",
)

SHOWDOWN_POSITIONS = {
    "WKR_establish_front_operations_bureau": (3, 11),
    "WKR_authorize_republican_mission_commands": (1, 12),
    "WKR_issue_normative_campaign_tables": (5, 12),
    "WKR_form_rolling_factory_groups": (2, 13),
    "WKR_reopen_night_freight_corridors": (4, 13),
    "WKR_arm_the_mobile_reserve": (1, 14),
    "WKR_coordinate_the_rolling_front": (4, 15),
    "VAD_convene_campaign_directorate": (14, 14),
    "VAD_issue_prefectural_field_decrees": (12, 15),
    "VAD_seat_front_commissars": (16, 15),
    "VAD_standardize_restoration_columns": (14, 16),
    "VAD_advance_under_one_register": (14, 17),
    "TVA_merge_iteration_with_field_command": (23, 16),
    "TVA_mass_produce_assault_modules": (21, 17),
    "TVA_link_observers_to_fire_control": (23, 17),
    "TVA_turn_repair_trains_into_supply_web": (25, 17),
    "TVA_run_live_front_validation": (23, 18),
}

SHOWDOWN_COSTS = {
    "WKR_establish_front_operations_bureau": 2,
    "WKR_authorize_republican_mission_commands": 2,
    "WKR_issue_normative_campaign_tables": 2,
    "WKR_form_rolling_factory_groups": 3,
    "WKR_reopen_night_freight_corridors": 3,
    "WKR_arm_the_mobile_reserve": 2,
    "WKR_coordinate_the_rolling_front": 4,
    "VAD_convene_campaign_directorate": 2,
    "VAD_issue_prefectural_field_decrees": 3,
    "VAD_seat_front_commissars": 3,
    "VAD_standardize_restoration_columns": 3,
    "VAD_advance_under_one_register": 4,
    "TVA_merge_iteration_with_field_command": 2,
    "TVA_mass_produce_assault_modules": 3,
    "TVA_link_observers_to_fire_control": 3,
    "TVA_turn_repair_trains_into_supply_web": 3,
    "TVA_run_live_front_validation": 4,
}

SHOWDOWN_PREREQUISITES = {
    "WKR_establish_front_operations_bureau": (frozenset({"WKR_republic_fights_as_one"}),),
    "WKR_authorize_republican_mission_commands": (frozenset({"WKR_establish_front_operations_bureau"}),),
    "WKR_issue_normative_campaign_tables": (frozenset({"WKR_establish_front_operations_bureau"}),),
    "WKR_form_rolling_factory_groups": (frozenset({"WKR_authorize_republican_mission_commands", "WKR_issue_normative_campaign_tables"}),),
    "WKR_reopen_night_freight_corridors": (frozenset({"WKR_authorize_republican_mission_commands", "WKR_issue_normative_campaign_tables"}),),
    "WKR_arm_the_mobile_reserve": (frozenset({"WKR_form_rolling_factory_groups"}),),
    "WKR_coordinate_the_rolling_front": (
        frozenset({"WKR_arm_the_mobile_reserve"}),
        frozenset({"WKR_reopen_night_freight_corridors"}),
    ),
    "VAD_convene_campaign_directorate": (frozenset({"VAD_publish_interim_restoration_register"}),),
    "VAD_issue_prefectural_field_decrees": (frozenset({"VAD_convene_campaign_directorate"}),),
    "VAD_seat_front_commissars": (frozenset({"VAD_convene_campaign_directorate"}),),
    "VAD_standardize_restoration_columns": (frozenset({"VAD_issue_prefectural_field_decrees", "VAD_seat_front_commissars"}),),
    "VAD_advance_under_one_register": (frozenset({"VAD_standardize_restoration_columns"}),),
    "TVA_merge_iteration_with_field_command": (
        frozenset({"TVA_close_operational_loop"}),
        frozenset({"TVA_authorize_iteration_two"}),
    ),
    "TVA_mass_produce_assault_modules": (frozenset({"TVA_merge_iteration_with_field_command"}),),
    "TVA_link_observers_to_fire_control": (frozenset({"TVA_merge_iteration_with_field_command"}),),
    "TVA_turn_repair_trains_into_supply_web": (frozenset({"TVA_merge_iteration_with_field_command"}),),
    "TVA_run_live_front_validation": (frozenset({"TVA_mass_produce_assault_modules", "TVA_link_observers_to_fire_control", "TVA_turn_repair_trains_into_supply_web"}),),
}

FOCUS_EXPANSION_IDEAS = (
    "ADISCORD_vorkerland_wrk_loyal_republics_mobilized",
    "ADISCORD_vorkerland_vad_eastern_mandate",
    "ADISCORD_vorkerland_wkr_front_operations_bureau",
    "ADISCORD_vorkerland_wkr_republican_mission_commands",
    "ADISCORD_vorkerland_wkr_normative_campaign_tables",
    "ADISCORD_vorkerland_wkr_rolling_factory_groups",
    "ADISCORD_vorkerland_wkr_night_freight_corridors",
    "ADISCORD_vorkerland_wkr_rolling_front",
    "ADISCORD_vorkerland_vad_campaign_directorate",
    "ADISCORD_vorkerland_vad_restoration_war_cabinet_2",
    "ADISCORD_vorkerland_vad_dual_authority_protocol_2",
    "ADISCORD_vorkerland_vad_standardized_restoration_columns",
    "ADISCORD_vorkerland_vad_joint_front_operation",
    "ADISCORD_vorkerland_vad_prefectural_offensive",
    "ADISCORD_vorkerland_tva_integrated_second_protocol",
    "ADISCORD_vorkerland_tva_assault_modules",
    "ADISCORD_vorkerland_tva_linked_fire_control",
    "ADISCORD_vorkerland_tva_supply_web",
    "ADISCORD_vorkerland_tva_live_front_validated",
)

SHOWDOWN_AI_PLANS = {
    "WKR": {
        "ADISCORD_vorkerland_wkr_pragmatist_showdown_plan": (
            "WKR_establish_front_operations_bureau",
            "WKR_authorize_republican_mission_commands",
            "WKR_form_rolling_factory_groups",
            "WKR_reopen_night_freight_corridors",
            "WKR_arm_the_mobile_reserve",
            "WKR_coordinate_the_rolling_front",
        ),
        "ADISCORD_vorkerland_wkr_utilitarian_showdown_plan": (
            "WKR_establish_front_operations_bureau",
            "WKR_issue_normative_campaign_tables",
            "WKR_form_rolling_factory_groups",
            "WKR_reopen_night_freight_corridors",
            "WKR_arm_the_mobile_reserve",
            "WKR_coordinate_the_rolling_front",
        ),
    },
    "VAD": {
        "ADISCORD_vorkerland_vad_vlad_showdown_plan": (
            "VAD_convene_campaign_directorate",
            "VAD_issue_prefectural_field_decrees",
            "VAD_standardize_restoration_columns",
            "VAD_advance_under_one_register",
        ),
        "ADISCORD_vorkerland_vad_joint_showdown_plan": (
            "VAD_convene_campaign_directorate",
            "VAD_seat_front_commissars",
            "VAD_standardize_restoration_columns",
            "VAD_advance_under_one_register",
        ),
    },
    "TVA": {
        "ADISCORD_vorkerland_tva_technical_validation_plan": (
            "TVA_merge_iteration_with_field_command",
            "TVA_mass_produce_assault_modules",
            "TVA_run_live_front_validation",
        ),
        "ADISCORD_vorkerland_tva_remote_validation_plan": (
            "TVA_merge_iteration_with_field_command",
            "TVA_link_observers_to_fire_control",
            "TVA_run_live_front_validation",
        ),
        "ADISCORD_vorkerland_tva_adaptive_validation_plan": (
            "TVA_merge_iteration_with_field_command",
            "TVA_turn_repair_trains_into_supply_web",
            "TVA_run_live_front_validation",
        ),
    },
}

POSTWAR_ROUTE_FOCUSES = {
    "ADISCORD_vorkerland_route_worker": (
        "WRK_worker_convene_reunification_congress",
        "WRK_worker_open_erased_nations_archives",
        "WRK_worker_recognize_free_republics",
        "WRK_worker_fund_cooperative_reconstruction",
        "WRK_worker_restore_displaced_councils",
        "WRK_worker_authorize_homecoming_commissions",
        "WRK_worker_prioritize_housing_guarantees",
        "WRK_worker_devolve_reconstruction_grants",
        "WRK_worker_ratify_republican_compact",
        "WRK_worker_write_constitutional_guarantees",
    ),
    "ADISCORD_vorkerland_route_joint": (
        "WRK_joint_convene_restoration_council",
        "WRK_joint_publish_amnesty_registers",
        "WRK_joint_establish_military_districts",
        "WRK_joint_reopen_district_rail_commands",
        "WRK_joint_issue_integration_warrants",
        "WRK_joint_restore_central_chancery",
        "WRK_joint_civilianize_district_police",
        "WRK_joint_retain_emergency_inspectorate",
        "WRK_joint_codify_single_chain_of_command",
        "WRK_joint_impose_reunification_settlement",
    ),
    "ADISCORD_vorkerland_route_utilitarian": (
        "WRK_utilitarian_form_reconstruction_directorate",
        "WRK_utilitarian_standardize_power_grid",
        "WRK_utilitarian_rebuild_machine_tool_pool",
        "WRK_utilitarian_expand_national_laboratories",
        "WRK_utilitarian_publish_integration_metrics",
        "WRK_utilitarian_rationalize_districts",
        "WRK_utilitarian_prioritize_public_utilities",
        "WRK_utilitarian_prioritize_industrial_recovery",
        "WRK_utilitarian_publish_reconstruction_ledger",
        "WRK_utilitarian_build_measurable_republic",
    ),
}

FOCUS_IDS = (
    *PREWAR_WRK_BASE_FOCUSES,
    *PREWAR_WRK_EXPANSION_FOCUSES,
    *PREWAR_VAD_BASE_FOCUSES,
    *PREWAR_VAD_EXPANSION_FOCUSES,
    RETIRED_WARTIME_FOCUSES[0],
    RETIRED_WARTIME_FOCUSES[1],
    RETIRED_WARTIME_FOCUSES[2],
    *WARTIME_ROUTE_FOCUSES["WKR"],
    *SHOWDOWN_FOCUSES["WKR"],
    *WKR_OPTIONAL_WARTIME_FOCUSES,
    *WARTIME_ROUTE_FOCUSES["VAD"],
    *VAD_OPTIONAL_WARTIME_FOCUSES,
    *VAD_LATE_WAR_BRIDGE_FOCUSES,
    *SHOWDOWN_FOCUSES["VAD"],
    *WARTIME_ROUTE_FOCUSES["TVA"],
    *TVA_OPTIONAL_WARTIME_FOCUSES,
    *SHOWDOWN_FOCUSES["TVA"],
    *POSTWAR_ROUTE_FOCUSES["ADISCORD_vorkerland_route_worker"],
    *POSTWAR_ROUTE_FOCUSES["ADISCORD_vorkerland_route_joint"],
    *POSTWAR_ROUTE_FOCUSES["ADISCORD_vorkerland_route_utilitarian"],
)

PREWAR_PHASE = "ADISCORD_vorkerland_phase_prewar"
SHOWDOWN_PHASE = "ADISCORD_vorkerland_phase_central_showdown"
ACTIVE_PHASE_FLAGS = {
    "ADISCORD_vorkerland_phase_collapse",
    "ADISCORD_vorkerland_phase_regional_consolidation",
    "ADISCORD_vorkerland_phase_central_preparation",
    "ADISCORD_vorkerland_phase_central_showdown",
}
LATE_WAR_PHASE_FLAGS = {
    "ADISCORD_vorkerland_phase_central_preparation",
    "ADISCORD_vorkerland_phase_central_showdown",
}
POSTWAR_PHASE = "ADISCORD_vorkerland_phase_postwar_integration"

CENTRAL_CAPSTONES = {
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

RETREAT_HOOKS = {
    "WKR": "ADISCORD_vorkerland_focus_wkr_retreat_levies_unlocked",
    "VAD": "ADISCORD_vorkerland_focus_vad_retreat_levies_unlocked",
    "TVA": "ADISCORD_vorkerland_focus_tva_retreat_levies_unlocked",
}

WARTIME_TERMINALS = {
    "WKR": (
        "WKR_republic_fights_as_one",
        (
            frozenset({"WKR_settle_front_authority"}),
            frozenset({"WKR_coordinate_counterattack_cells"}),
            frozenset({"WKR_stockpile_interchange_reserves"}),
        ),
    ),
    "VAD": (
        "VAD_balance_council_and_command",
        (
            frozenset({"VAD_settle_restoration_authority"}),
            frozenset({"VAD_dispatch_solland_liaison_mission"}),
            frozenset({"VAD_assemble_joint_general_staff"}),
            frozenset({"VAD_reopen_armament_depots"}),
        ),
    ),
    "TVA": (
        "TVA_close_operational_loop",
        (
            frozenset({"TVA_standardize_emergency_administration"}),
            frozenset({"TVA_seal_the_approaches"}),
            frozenset({"TVA_harden_switching_stations"}),
        ),
    ),
}

POSTWAR_ROUTE_TERMINALS = {
    "ADISCORD_vorkerland_route_worker": "WRK_worker_write_constitutional_guarantees",
    "ADISCORD_vorkerland_route_joint": "WRK_joint_impose_reunification_settlement",
    "ADISCORD_vorkerland_route_utilitarian": "WRK_utilitarian_build_measurable_republic",
}

POSTWAR_POLICY_CHOICE_PAIRS = (
    (
        "WRK_worker_prioritize_housing_guarantees",
        "WRK_worker_devolve_reconstruction_grants",
    ),
    (
        "WRK_joint_civilianize_district_police",
        "WRK_joint_retain_emergency_inspectorate",
    ),
    (
        "WRK_utilitarian_prioritize_public_utilities",
        "WRK_utilitarian_prioritize_industrial_recovery",
    ),
)

VAD_OPTIONAL_OUTCOME_FOCUSES = (
    frozenset(
        {
            "VAD_restore_prefectural_courts",
            "VAD_issue_crown_mobilization_warrants",
            "VAD_turn_the_chancery_into_a_war_cabinet",
            "VAD_map_the_solar_corridors",
            "VAD_preposition_restoration_columns",
            "VAD_define_the_solar_settlement",
        }
    ),
    frozenset(
        {
            "VAD_elect_district_commissars",
            "VAD_merge_guard_and_worker_rolls",
            "VAD_sign_the_dual_authority_protocol",
            "VAD_map_the_solar_corridors",
            "VAD_preposition_restoration_columns",
            "VAD_define_the_solar_settlement",
        }
    ),
)

VAD_OPTIONAL_POSITIONS = {
    "VAD_restore_prefectural_courts": (6, 9),
    "VAD_issue_crown_mobilization_warrants": (6, 10),
    "VAD_turn_the_chancery_into_a_war_cabinet": (7, 11),
    "VAD_elect_district_commissars": (10, 9),
    "VAD_merge_guard_and_worker_rolls": (10, 10),
    "VAD_sign_the_dual_authority_protocol": (9, 11),
    "VAD_map_the_solar_corridors": (12, 9),
    "VAD_preposition_restoration_columns": (13, 10),
    "VAD_define_the_solar_settlement": (11, 12),
}

VAD_OPTIONAL_COSTS = {
    "VAD_restore_prefectural_courts": 2,
    "VAD_issue_crown_mobilization_warrants": 3,
    "VAD_turn_the_chancery_into_a_war_cabinet": 5,
    "VAD_elect_district_commissars": 2,
    "VAD_merge_guard_and_worker_rolls": 3,
    "VAD_sign_the_dual_authority_protocol": 5,
    "VAD_map_the_solar_corridors": 2,
    "VAD_preposition_restoration_columns": 3,
    "VAD_define_the_solar_settlement": 5,
}

VAD_LATE_WAR_BRIDGE_POSITIONS = {
    "VAD_reconcile_emergency_district_rolls": (14, 11),
    "VAD_restore_eastern_supply_corridors": (13, 12),
    "VAD_convert_emergency_workshops": (15, 12),
    "VAD_publish_interim_restoration_register": (14, 13),
}

VAD_LATE_WAR_BRIDGE_COSTS = {
    "VAD_reconcile_emergency_district_rolls": 2,
    "VAD_restore_eastern_supply_corridors": 3,
    "VAD_convert_emergency_workshops": 3,
    "VAD_publish_interim_restoration_register": 4,
}

VAD_LATE_WAR_BRIDGE_PREREQUISITES = {
    "VAD_reconcile_emergency_district_rolls": (
        frozenset(
            {
                "VAD_preposition_restoration_columns",
                "VAD_balance_council_and_command",
            }
        ),
    ),
    "VAD_restore_eastern_supply_corridors": (
        frozenset({"VAD_reconcile_emergency_district_rolls"}),
    ),
    "VAD_convert_emergency_workshops": (
        frozenset({"VAD_reconcile_emergency_district_rolls"}),
    ),
    "VAD_publish_interim_restoration_register": (
        frozenset({"VAD_restore_eastern_supply_corridors"}),
        frozenset({"VAD_convert_emergency_workshops"}),
    ),
}

VAD_LATE_WAR_BRIDGE_REWARDS = {
    "VAD_reconcile_emergency_district_rolls": (
        "add_manpower = 400",
        "add_stability = 0.01",
        "add_political_power = 5",
        "set_country_flag = ADISCORD_vorkerland_focus_vad_emergency_rolls_reconciled",
    ),
    "VAD_restore_eastern_supply_corridors": (
        "limit = { owns_state = 107 controls_state = 107 }",
        "type = infrastructure level = 1 instant_build = yes",
        "add_timed_idea = { idea = ADISCORD_vorkerland_vad_restoration_columns days = 70 }",
        "add_command_power = 5",
        "set_country_flag = ADISCORD_vorkerland_focus_vad_eastern_supply_corridors_restored",
    ),
    "VAD_convert_emergency_workshops": (
        "limit = { owns_state = 121 controls_state = 121 }",
        "add_extra_state_shared_building_slots = 1",
        "type = arms_factory level = 1 instant_build = yes",
        "type = support_equipment amount = 50 producer = VAD",
        "add_war_support = 0.01",
        "set_country_flag = ADISCORD_vorkerland_focus_vad_emergency_workshops_converted",
    ),
    "VAD_publish_interim_restoration_register": (
        "add_command_power = 10",
        "army_experience = 5",
        "add_political_power = 15",
        "add_stability = 0.01",
        "set_country_flag = ADISCORD_vorkerland_focus_vad_interim_restoration_register",
    ),
}

VORKERLAND_CONTINUOUS_FOCUSES = (
    "ADISCORD_vorkerland_continuous_emergency_production",
    "ADISCORD_vorkerland_continuous_front_repair",
    "ADISCORD_vorkerland_continuous_field_training",
)

VORKERLAND_CONTINUOUS_FOCUS_CONTRACTS = {
    "ADISCORD_vorkerland_continuous_emergency_production": (
        "GFX_goal_generic_production",
        "ai_focus_military_advancements",
        (
            "industrial_capacity_factory = 0.05",
            "production_factory_efficiency_gain_factor = 0.05",
        ),
    ),
    "ADISCORD_vorkerland_continuous_front_repair": (
        "GFX_goal_continuous_repairments",
        "ai_focus_defense",
        (
            "industry_repair_factor = 0.25",
            "production_speed_infrastructure_factor = 0.10",
            "production_speed_rail_way_factor = 0.10",
            "production_speed_supply_node_factor = 0.10",
        ),
    ),
    "ADISCORD_vorkerland_continuous_field_training": (
        "GFX_goal_continuous_reduce_training_time",
        "ai_focus_defense",
        ("training_time_army_factor = -0.15",),
    ),
}

TVA_OPTIONAL_SHARED_SEQUENCE = (
    "TVA_print_interchangeable_repair_modules",
    "TVA_preposition_switching_crews",
    "TVA_cross_validate_trial_logs",
    "TVA_authorize_iteration_two",
)
TVA_OPTIONAL_SHARED_FOCUSES = frozenset(TVA_OPTIONAL_SHARED_SEQUENCE)

TVA_OPTIONAL_OUTCOME_FOCUSES = tuple(
    frozenset({metric_focus, trial_focus, *TVA_OPTIONAL_SHARED_FOCUSES})
    for metric_focus in (
        "TVA_unattended_shifts",
        "TVA_delegate_fire_plans_to_board",
        "TVA_bunker_specialist_cadres",
    )
    for trial_focus in (
        "TVA_standardize_assault_teams",
        "TVA_network_observation_posts",
        "TVA_mandate_modular_repair",
    )
)

TVA_OPTIONAL_POSITIONS = {
    "TVA_unattended_shifts": (16, 9),
    "TVA_delegate_fire_plans_to_board": (18, 9),
    "TVA_bunker_specialist_cadres": (20, 9),
    "TVA_standardize_assault_teams": (19, 10),
    "TVA_network_observation_posts": (22, 10),
    "TVA_mandate_modular_repair": (24, 10),
    "TVA_print_interchangeable_repair_modules": (21, 12),
    "TVA_preposition_switching_crews": (23, 13),
    "TVA_cross_validate_trial_logs": (24, 14),
    "TVA_authorize_iteration_two": (25, 15),
}

TVA_OPTIONAL_COSTS = {
    "TVA_unattended_shifts": 3,
    "TVA_delegate_fire_plans_to_board": 3,
    "TVA_bunker_specialist_cadres": 3,
    "TVA_standardize_assault_teams": 2,
    "TVA_network_observation_posts": 3,
    "TVA_mandate_modular_repair": 2,
    "TVA_print_interchangeable_repair_modules": 2,
    "TVA_preposition_switching_crews": 3,
    "TVA_cross_validate_trial_logs": 3,
    "TVA_authorize_iteration_two": 5,
}

TVA_OPTIONAL_TIMED_IDEAS = {
    "TVA_unattended_shifts": (
        "ADISCORD_vorkerland_tva_unattended_shifts",
        70,
    ),
    "TVA_delegate_fire_plans_to_board": (
        "ADISCORD_vorkerland_tva_algorithmic_fire_plans",
        70,
    ),
    "TVA_bunker_specialist_cadres": (
        "ADISCORD_vorkerland_tva_bunker_specialist_cadres",
        70,
    ),
    "TVA_standardize_assault_teams": (
        "ADISCORD_vorkerland_tva_standardized_assault_teams",
        56,
    ),
    "TVA_network_observation_posts": (
        "ADISCORD_vorkerland_tva_networked_observation_posts",
        70,
    ),
    "TVA_mandate_modular_repair": (
        "ADISCORD_vorkerland_tva_modular_repair_mandate",
        56,
    ),
    "TVA_print_interchangeable_repair_modules": (
        "ADISCORD_vorkerland_tva_interchangeable_repair_modules",
        70,
    ),
    "TVA_preposition_switching_crews": (
        "ADISCORD_vorkerland_tva_prepositioned_switching_crews",
        70,
    ),
}

TVA_OPTIONAL_IDEA_LOCALISATION_IDS = {
    idea_id for idea_id, _days in TVA_OPTIONAL_TIMED_IDEAS.values()
}

TVA_OPTIONAL_AI_PLANS = tuple(
    (
        f"ADISCORD_vorkerland_tva_{metric_slug}_{trial_slug}_depth_plan",
        metric_flag,
        trial_flag,
        (metric_focus, trial_focus, *TVA_OPTIONAL_SHARED_SEQUENCE),
    )
    for metric_slug, metric_flag, metric_focus in (
        (
            "throughput",
            "ADISCORD_vorkerland_focus_tva_throughput_priority",
            "TVA_unattended_shifts",
        ),
        (
            "algorithm",
            "ADISCORD_vorkerland_focus_tva_algorithmic_board",
            "TVA_delegate_fire_plans_to_board",
        ),
        (
            "specialist",
            "ADISCORD_vorkerland_focus_tva_specialist_priority",
            "TVA_bunker_specialist_cadres",
        ),
    )
    for trial_slug, trial_flag, trial_focus in (
        (
            "technical",
            "ADISCORD_vorkerland_focus_tva_technical_battalions",
            "TVA_standardize_assault_teams",
        ),
        (
            "remote",
            "ADISCORD_vorkerland_focus_tva_remote_fire_control",
            "TVA_network_observation_posts",
        ),
        (
            "adaptive",
            "ADISCORD_vorkerland_focus_tva_adaptive_logistics",
            "TVA_mandate_modular_repair",
        ),
    )
)

VAD_WARTIME_TIMED_IDEAS = {
    "VAD_open_imperial_registers": (
        "ADISCORD_vorkerland_vad_imperial_registers",
        70,
    ),
    "VAD_form_field_commandantures": (
        "ADISCORD_vorkerland_vad_field_commandantures",
        70,
    ),
    "VAD_standardize_district_logistics": (
        "ADISCORD_vorkerland_vad_standardized_logistics",
        70,
    ),
    "VAD_restore_prefectural_courts": (
        "ADISCORD_vorkerland_vad_prefectural_discipline",
        70,
    ),
    "VAD_map_the_solar_corridors": (
        "ADISCORD_vorkerland_vad_solar_corridor_intelligence",
        84,
    ),
    "VAD_preposition_restoration_columns": (
        "ADISCORD_vorkerland_vad_restoration_columns",
        84,
    ),
}

VAD_PERMANENT_PROTOCOL_IDEAS = {
    "VAD_turn_the_chancery_into_a_war_cabinet": (
        "ADISCORD_vorkerland_vad_restoration_war_cabinet",
        "ADISCORD_vorkerland_vad_dual_authority_protocol",
    ),
    "VAD_sign_the_dual_authority_protocol": (
        "ADISCORD_vorkerland_vad_dual_authority_protocol",
        "ADISCORD_vorkerland_vad_restoration_war_cabinet",
    ),
}

VAD_WARTIME_IDEA_LOCALISATION_IDS = {
    idea_id for idea_id, _days in VAD_WARTIME_TIMED_IDEAS.values()
} | {
    own for own, _other in VAD_PERMANENT_PROTOCOL_IDEAS.values()
}

WARTIME_OUTCOME_EXCLUSIONS = {
    "WKR": (
        frozenset({"WKR_empower_front_executive", "WKR_authorize_normative_command", "WKR_bind_workshops_to_directive"}),
        frozenset({"WKR_convene_front_soviets", "WKR_open_free_republics_channel", "WKR_publish_emergency_constitution"}),
    ),
    "VAD": (
        frozenset({"VAD_form_field_commandantures", "VAD_guarantee_worker_committees", "VAD_ratify_joint_command"}),
        frozenset({"VAD_open_imperial_registers", "VAD_restore_crown_commissions", "VAD_bind_officers_to_chancery"}),
    ),
    "TVA": tuple(
        frozenset(({*metric_choices} - {metric}) | ({*trial_choices} - {trial}))
        for metric_choices in (("TVA_optimize_for_throughput", "TVA_delegate_to_algorithmic_board", "TVA_protect_irreplaceable_specialists"),)
        for trial_choices in (("TVA_raise_technical_battalions", "TVA_test_remote_fire_control", "TVA_test_adaptive_logistics"),)
        for metric in metric_choices
        for trial in trial_choices
    ),
}

# Tokens which make a focus unavailable under each concrete claimant outcome.
# This complements the mutually-exclusive focus list: a common convergence node
# can otherwise look "completable" on paper while an accidental leader or
# government gate makes it unreachable in game.
WARTIME_OUTCOME_FALSE_GATE_TOKENS = {
    "WKR": (
        (
            "character = WRK_Anton_Bagley",
            "has_government = utilitarism",
            "character = WRK_Vlad_Petrichev",
            "character = WRK_VAD_Joint_Council",
            "character = TVA_Dorian_Worx",
            "has_government = technocracy",
        ),
        (
            "character = WRK_Nikita_Worcker",
            "has_government = pragmatism",
            "character = WRK_Vlad_Petrichev",
            "character = WRK_VAD_Joint_Council",
            "character = TVA_Dorian_Worx",
            "has_government = technocracy",
        ),
    ),
    "VAD": (
        (
            "character = WRK_VAD_Joint_Council",
            "character = WRK_Nikita_Worcker",
            "character = WRK_Anton_Bagley",
            "character = TVA_Dorian_Worx",
            "has_government = technocracy",
        ),
        (
            "character = WRK_Vlad_Petrichev",
            "character = WRK_Nikita_Worcker",
            "character = WRK_Anton_Bagley",
            "character = TVA_Dorian_Worx",
            "has_government = technocracy",
        ),
    ),
    "TVA": tuple(
        (
            "character = WRK_Nikita_Worcker",
            "character = WRK_Anton_Bagley",
            "character = WRK_Vlad_Petrichev",
            "character = WRK_VAD_Joint_Council",
            "has_government = pragmatism",
            "has_government = utilitarism",
        )
        for _excluded in WARTIME_OUTCOME_EXCLUSIONS["TVA"]
    ),
}

WARTIME_ROUTE_IDENTITIES = (
    (
        (
            "WKR_convene_front_soviets",
            "WKR_open_free_republics_channel",
            "WKR_publish_emergency_constitution",
        ),
        (
            "has_global_flag = ADISCORD_vorkerland_worker_safe_with_loyalists",
            "has_government = pragmatism",
            "has_country_leader_ideology = neo_vorkerism",
            "has_country_leader = { character = WRK_Nikita_Worcker ruling_only = yes }",
        ),
    ),
    (
        (
            "WKR_empower_front_executive",
            "WKR_authorize_normative_command",
            "WKR_bind_workshops_to_directive",
        ),
        (
            "NOT = { has_global_flag = ADISCORD_vorkerland_worker_safe_with_loyalists }",
            "has_government = utilitarism",
            "has_country_leader = { character = WRK_Anton_Bagley ruling_only = yes }",
        ),
    ),
    (
        (
            "VAD_open_imperial_registers",
            "VAD_restore_crown_commissions",
            "VAD_bind_officers_to_chancery",
        ),
        (
            "NOT = { has_global_flag = ADISCORD_vorkerland_joint_government_formed }",
            "has_country_leader = { character = WRK_Vlad_Petrichev ruling_only = yes }",
        ),
    ),
    (
        (
            "VAD_form_field_commandantures",
            "VAD_guarantee_worker_committees",
            "VAD_ratify_joint_command",
        ),
        (
            "has_global_flag = ADISCORD_vorkerland_joint_government_formed",
            "has_global_flag = ADISCORD_vorkerland_worker_rescued_by_vlad",
            "has_country_leader = { character = WRK_VAD_Joint_Council ruling_only = yes }",
        ),
    ),
)

NEW_WARTIME_FOCUSES = {
    "WKR": set(WARTIME_ROUTE_FOCUSES["WKR"][10:16]),
    "VAD": set(WARTIME_ROUTE_FOCUSES["VAD"][10:15]),
    "TVA": set(WARTIME_ROUTE_FOCUSES["TVA"][11:17]),
}

PREWAR_CARRYOVER_EFFECT = "ADISCORD_vorkerland_inherit_wrk_prewar_preparations"
PREWAR_CARRYOVER_FLAG = "ADISCORD_vorkerland_wrk_prewar_preparations_inherited_v1"
DORMANT_WRK_SCRUB_EFFECT = "ADISCORD_vorkerland_scrub_dormant_wrk_crisis"
WORKER_REFORM_INHERIT_EFFECT = "ADISCORD_vorkerland_inherit_worker_reform_spirits"
WORKER_REFORM_STAGE_IDEAS = (
    "WRK_birthplace_of_the_first_revolution_renewed_mandate",
    "WRK_birthplace_of_the_first_revolution_front_republic",
    "WRK_birthplace_of_the_first_revolution",
    "ADISCORD_vorkerland_erased_nations_relief_2",
    "ADISCORD_vorkerland_erased_nations_relief_1",
    "ADISCORD_vorkerland_erased_nations",
)
DORMANT_WRK_CRISIS_IDEAS = (
    "WRK_ashes_of_the_crown",
    "WRK_hourglass_of_discord",
    "WRK_constitution_of_the_republic",
    *WORKER_REFORM_STAGE_IDEAS,
)
WRK_FORMATION_EFFECTS = {
    "WKR": "ADISCORD_vorkerland_form_wrk_from_wkr",
    "VAD": "ADISCORD_vorkerland_form_wrk_from_vad",
    "TVA": "ADISCORD_vorkerland_form_wrk_from_tva",
}

POSTWAR_SETTLEMENT_IDEAS = {
    "WRK_worker_write_constitutional_guarantees": (
        "ADISCORD_vorkerland_worker_constitutional_settlement",
        {
            "ADISCORD_vorkerland_reunification_settlement",
            "ADISCORD_vorkerland_measurable_republic",
        },
    ),
    "WRK_joint_impose_reunification_settlement": (
        "ADISCORD_vorkerland_reunification_settlement",
        {
            "ADISCORD_vorkerland_worker_constitutional_settlement",
            "ADISCORD_vorkerland_measurable_republic",
        },
    ),
    "WRK_utilitarian_build_measurable_republic": (
        "ADISCORD_vorkerland_measurable_republic",
        {
            "ADISCORD_vorkerland_worker_constitutional_settlement",
            "ADISCORD_vorkerland_reunification_settlement",
        },
    ),
}

CENTRAL_PREPARED_FLAG = "ADISCORD_vorkerland_focus_central_front_prepared"
CLAIMANT_FOCUS_EVENT_IDS = (
    "ADISCORD_vorkerland_claimant.1",
    "ADISCORD_vorkerland_claimant.2",
    "ADISCORD_vorkerland_claimant.3",
    "ADISCORD_vorkerland_claimant.4",
    "ADISCORD_vorkerland_claimant.10",
    "ADISCORD_vorkerland_claimant.11",
    "ADISCORD_vorkerland_claimant.12",
    "ADISCORD_vorkerland_claimant.13",
    "ADISCORD_vorkerland_claimant.14",
    "ADISCORD_vorkerland_claimant.20",
    "ADISCORD_vorkerland_claimant.21",
    "ADISCORD_vorkerland_claimant.22",
    "ADISCORD_vorkerland_claimant.23",
    "ADISCORD_vorkerland_claimant.24",
    "ADISCORD_vorkerland_claimant.30",
    "ADISCORD_vorkerland_claimant.31",
    "ADISCORD_vorkerland_claimant.32",
)
CLAIMANT_NEWS_EVENT_IDS = (
    "ADISCORD_vorkerland_claimant.100",
    "ADISCORD_vorkerland_claimant.101",
    "ADISCORD_vorkerland_claimant.102",
)
CLAIMANT_TWO_OPTION_EVENT_IDS = (
    "ADISCORD_vorkerland_claimant.1",
    "ADISCORD_vorkerland_claimant.2",
    "ADISCORD_vorkerland_claimant.3",
    "ADISCORD_vorkerland_claimant.10",
    "ADISCORD_vorkerland_claimant.11",
    "ADISCORD_vorkerland_claimant.12",
    "ADISCORD_vorkerland_claimant.20",
    "ADISCORD_vorkerland_claimant.21",
    "ADISCORD_vorkerland_claimant.22",
)
CLAIMANT_ROUTE_LOCALISATION_KEYS = {
    *(f"ADISCORD_vorkerland_claimant.4.{suffix}" for suffix in ("t", "nikita.d", "anton.d", "nikita.a", "nikita.b", "anton.a", "anton.b")),
    *(f"ADISCORD_vorkerland_claimant.13.{suffix}" for suffix in ("t", "joint.d", "vlad.d", "joint.a", "joint.b", "vlad.a", "vlad.b")),
    *(f"ADISCORD_vorkerland_claimant.14.{suffix}" for suffix in ("t", "joint.d", "vlad.d", "joint.a", "vlad.a")),
    *(f"ADISCORD_vorkerland_claimant.23.{suffix}" for suffix in ("t", "d", "a", "b", "c")),
    *(f"ADISCORD_vorkerland_claimant.24.{suffix}" for suffix in ("t", "d", "a", "b", "c")),
}
MOBILE_REPAIR_IDEA = "ADISCORD_vorkerland_tva_mobile_repair_trains"
LAND_REPAIR_IDEAS = (
    "ADISCORD_vorkerland_wrk_rail_requisition",
    "ADISCORD_vorkerland_tva_grid_rerouting",
    MOBILE_REPAIR_IDEA,
)

WORX_WARTIME_TIMED_IDEAS = {
    "TVA_issue_emergency_output_norms": (
        "ADISCORD_vorkerland_tva_emergency_output_board",
        70,
    ),
    "TVA_publish_operational_metrics": (
        "ADISCORD_vorkerland_tva_operational_audit",
        70,
    ),
}
WORX_ADAPTIVE_LOGISTICS_IDEA = (
    "ADISCORD_vorkerland_worx_adaptive_logistics_trial"
)
RETIRED_WORX_SECOND_PROTOCOL_IDEA = "ADISCORD_vorkerland_worx_second_protocol"
WORX_FIELD_DIRECTORATE_IDEAS = (
    "ADISCORD_vorkerland_tva_field_directorate",
    "ADISCORD_vorkerland_tva_field_directorate_2",
    "ADISCORD_vorkerland_tva_field_directorate_3",
)

WORX_POSTWAR_PROVISIONAL_IDEAS = {
    "WRK_utilitarian_form_reconstruction_directorate": (
        "ADISCORD_vorkerland_technical_reconstruction_mandate"
    ),
    "WRK_utilitarian_standardize_power_grid": (
        "ADISCORD_vorkerland_national_power_standard"
    ),
    "WRK_utilitarian_expand_national_laboratories": (
        "ADISCORD_vorkerland_public_engineering_service"
    ),
    "WRK_utilitarian_rationalize_districts": (
        "ADISCORD_vorkerland_statistical_administration"
    ),
    "WRK_utilitarian_prioritize_public_utilities": (
        "ADISCORD_vorkerland_public_utility_priority"
    ),
    "WRK_utilitarian_prioritize_industrial_recovery": (
        "ADISCORD_vorkerland_industrial_recovery_priority"
    ),
    "WRK_utilitarian_publish_reconstruction_ledger": (
        "ADISCORD_vorkerland_technical_reconstruction_mandate_2"
    ),
}

POSTWAR_TRANSITIONAL_IDEAS = {
    "WRK_worker_write_constitutional_guarantees": {
        "WRK_worker_convene_reunification_congress": (
            "ADISCORD_vorkerland_worker_reconstruction_compact_1"
        ),
        "WRK_worker_prioritize_housing_guarantees": (
            "ADISCORD_vorkerland_worker_housing_guarantee"
        ),
        "WRK_worker_devolve_reconstruction_grants": (
            "ADISCORD_vorkerland_worker_local_reconstruction_grants"
        ),
        "WRK_worker_ratify_republican_compact": (
            "ADISCORD_vorkerland_worker_reconstruction_compact_2"
        ),
    },
    "WRK_joint_impose_reunification_settlement": {
        "WRK_joint_convene_restoration_council": (
            "ADISCORD_vorkerland_joint_restoration_authority_1"
        ),
        "WRK_joint_restore_central_chancery": (
            "ADISCORD_vorkerland_joint_restoration_authority_2"
        ),
        "WRK_joint_civilianize_district_police": (
            "ADISCORD_vorkerland_joint_civilian_transition"
        ),
        "WRK_joint_retain_emergency_inspectorate": (
            "ADISCORD_vorkerland_joint_emergency_inspectorate"
        ),
    },
}

IVANLAND_EXPEDITIONARY_IDEA = "ADISCORD_vorkerland_ivanland_expeditionary_command"

POSTWAR_IDEA_LOCALISATION_IDS = {
    "ADISCORD_vorkerland_worker_constitutional_settlement",
    "ADISCORD_vorkerland_reunification_settlement",
    "ADISCORD_vorkerland_measurable_republic",
    MOBILE_REPAIR_IDEA,
    *(idea_id for idea_id, _days in WORX_WARTIME_TIMED_IDEAS.values()),
    *WORX_POSTWAR_PROVISIONAL_IDEAS.values(),
    *(
        idea_id
        for route_ideas in POSTWAR_TRANSITIONAL_IDEAS.values()
        for idea_id in route_ideas.values()
    ),
    IVANLAND_EXPEDITIONARY_IDEA,
}

POSTWAR_CORE_UNLOCK_FOCUSES = {
    "WRK_worker_authorize_homecoming_commissions",
    "WRK_joint_issue_integration_warrants",
    "WRK_utilitarian_publish_integration_metrics",
}

CORE_DECISIONS = {
    "ADISCORD_vorkerland_restore_core_claimant_homes",
    "ADISCORD_vorkerland_restore_core_central_historical",
    "ADISCORD_vorkerland_restore_core_oitfort",
    "ADISCORD_vorkerland_restore_core_rimat",
    "ADISCORD_vorkerland_restore_core_techlar",
    "ADISCORD_vorkerland_restore_core_ebern",
    "ADISCORD_vorkerland_restore_core_solar",
}

POSTWAR_HOOKS = {
    "ADISCORD_vorkerland_focus_worker_postwar_congress",
    "ADISCORD_vorkerland_focus_worker_erased_archives",
    "ADISCORD_vorkerland_focus_worker_displaced_councils",
    "ADISCORD_vorkerland_focus_worker_constitutional_guarantees",
    "ADISCORD_vorkerland_focus_worker_free_republics",
    "ADISCORD_vorkerland_focus_worker_cooperative_reconstruction",
    "ADISCORD_vorkerland_focus_worker_homecoming_commissions",
    "ADISCORD_vorkerland_focus_worker_housing_guarantees",
    "ADISCORD_vorkerland_focus_worker_reconstruction_grants",
    "ADISCORD_vorkerland_focus_worker_republican_compact",
    "ADISCORD_vorkerland_focus_joint_postwar_council",
    "ADISCORD_vorkerland_focus_joint_amnesty_registers",
    "ADISCORD_vorkerland_focus_joint_military_districts",
    "ADISCORD_vorkerland_focus_joint_rail_commands",
    "ADISCORD_vorkerland_focus_joint_integration_warrants",
    "ADISCORD_vorkerland_focus_joint_restored_chancery",
    "ADISCORD_vorkerland_focus_joint_civilian_police",
    "ADISCORD_vorkerland_focus_joint_emergency_inspectorate",
    "ADISCORD_vorkerland_focus_joint_single_chain_of_command",
    "ADISCORD_vorkerland_focus_joint_order_settlement",
    "ADISCORD_vorkerland_focus_utilitarian_postwar_directorate",
    "ADISCORD_vorkerland_focus_utilitarian_power_standard",
    "ADISCORD_vorkerland_focus_utilitarian_machine_tools",
    "ADISCORD_vorkerland_focus_utilitarian_national_laboratories",
    "ADISCORD_vorkerland_focus_utilitarian_integration_metrics",
    "ADISCORD_vorkerland_focus_utilitarian_rationalized_districts",
    "ADISCORD_vorkerland_focus_utilitarian_public_utilities",
    "ADISCORD_vorkerland_focus_utilitarian_industrial_recovery",
    "ADISCORD_vorkerland_focus_utilitarian_reconstruction_ledger",
    "ADISCORD_vorkerland_focus_utilitarian_measurable_republic",
}

KNOWN_SHINED_ICONS = {
    "GFX_goal_generic_allies_build_infantry",
    "GFX_goal_generic_army_doctrines",
    "GFX_goal_generic_construct_civ_factory",
    "GFX_goal_generic_construct_infrastructure",
    "GFX_goal_generic_construct_mil_factory",
    "GFX_goal_generic_major_war",
    "GFX_goal_generic_military_sphere",
    "GFX_goal_generic_national_unity",
    "GFX_goal_generic_political_pressure",
    "GFX_goal_generic_positive_trade_relations",
    "GFX_goal_generic_production",
    "GFX_goal_generic_scientific_exchange",
}

SIGNATURE_ICONS = {
    "WKR_republic_fights_as_one": "GFX_goal_generic_allies_build_infantry",
    "VAD_proclaim_joint_charter": "GFX_goal_generic_military_sphere",
    "TVA_codify_utilitarian_directorate": "GFX_goal_generic_production",
    "TVA_close_operational_loop": "GFX_goal_generic_scientific_exchange",
    "VAD_balance_council_and_command": "GFX_goal_generic_national_unity",
    "WRK_joint_impose_reunification_settlement": "GFX_goal_generic_political_pressure",
    "WRK_utilitarian_build_measurable_republic": "GFX_goal_generic_production",
}


def read(relative: Path) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def _blocks(text: str, assignment: str) -> list[str]:
    results: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(assignment)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        start = text.find("{", match.start())
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    results.append(text[match.start() : index + 1])
                    break
        else:
            raise ValueError(f"unterminated {assignment} block")
    return results


def focus_blocks(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in _blocks(text, "focus"):
        match = re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_]+)\s*$", block)
        if not match:
            raise ValueError("focus block lacks an id")
        focus_id = match.group(1)
        if focus_id in result:
            raise ValueError(f"duplicate focus id {focus_id}")
        result[focus_id] = block
    return result


def localisation_entries(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for match in re.finditer(r'(?m)^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"(.*)"\s*$', text):
        entries[match.group(1)] = match.group(2)
    return entries


def localisation_keys(text: str) -> list[str]:
    return re.findall(r'(?m)^\s+([A-Za-z0-9_.]+):(?:\d+)?\s+"', text)


def expected_localisation_keys() -> set[str]:
    return {
        *FOCUS_IDS,
        *(f"{focus_id}_desc" for focus_id in FOCUS_IDS),
        *VORKERLAND_CONTINUOUS_FOCUSES,
        *(f"{focus_id}_desc" for focus_id in VORKERLAND_CONTINUOUS_FOCUSES),
        "ADISCORD_vorkerland_claimant_focus_phase_tt",
        "ADISCORD_vorkerland_central_showdown_phase_tt",
        "ADISCORD_vorkerland_wrk_preparations_carry_over_tt",
        "ADISCORD_vorkerland_unlock_core_restoration_decisions_tt",
        "WRK_worker_recognize_free_republics_tt",
        "WRK_worker_write_constitutional_guarantees_tt",
        "TVA_technocratic_directorate_tt",
        "WRK_technocratic_reconstruction_mandate_tt",
        "WRK_technocratic_republic_settlement_tt",
        "WKR_intervene_in_solyarino_available_tt",
        "WKR_intervene_in_solyarino_effect_tt",
        "ADISCORD_vorkerland_prewar_compact_requires_both_tt",
        "ADISCORD_vorkerland_showdown_focus_live_war_tt",
        *FOCUS_EXPANSION_IDEAS,
        *(f"{idea_id}_desc" for idea_id in FOCUS_EXPANSION_IDEAS),
        *(
            f"{event_id}.{suffix}"
            for event_id in (*CLAIMANT_FOCUS_EVENT_IDS, *CLAIMANT_NEWS_EVENT_IDS)
            if event_id not in {
                "ADISCORD_vorkerland_claimant.4",
                "ADISCORD_vorkerland_claimant.13",
                "ADISCORD_vorkerland_claimant.14",
                "ADISCORD_vorkerland_claimant.23",
                "ADISCORD_vorkerland_claimant.24",
            }
            for suffix in ("t", "d", "a")
        ),
        *(f"{event_id}.b" for event_id in CLAIMANT_TWO_OPTION_EVENT_IDS),
        *CLAIMANT_ROUTE_LOCALISATION_KEYS,
    }


def _phase_flags(block: str) -> set[str]:
    return set(
        re.findall(
            r"\bhas_global_flag\s*=\s*(ADISCORD_vorkerland_phase_[A-Za-z0-9_]+)",
            block,
        )
    )


def _allow_branch(block: str) -> str:
    blocks = _blocks(block, "allow_branch")
    return blocks[0] if len(blocks) == 1 else ""


def _prerequisites(block: str) -> set[str]:
    result: set[str] = set()
    for prerequisite in _blocks(block, "prerequisite"):
        result.update(re.findall(r"\bfocus\s*=\s*([A-Za-z0-9_]+)", prerequisite))
    return result


def _prerequisite_groups(block: str) -> tuple[frozenset[str], ...]:
    """Return Clausewitz prerequisite groups (AND blocks containing OR focuses)."""

    return tuple(
        frozenset(
            re.findall(r"\bfocus\s*=\s*([A-Za-z0-9_]+)", prerequisite)
        )
        for prerequisite in _blocks(block, "prerequisite")
    )


def _focus_cost(block: str) -> int:
    match = re.search(r"(?m)^\s*cost\s*=\s*(\d+)\s*$", block)
    return int(match.group(1)) if match else -1


def _mutually_exclusive_focuses(block: str) -> set[str]:
    return {
        focus_id
        for mutually_exclusive in _blocks(block, "mutually_exclusive")
        for focus_id in re.findall(
            r"\bfocus\s*=\s*([A-Za-z0-9_]+)", mutually_exclusive
        )
    }


def _postwar_completion_paths(
    blocks: dict[str, str], route_ids: tuple[str, ...], terminal_id: str
) -> tuple[frozenset[str], ...]:
    """Enumerate inclusion-minimal, graph-valid ways to reach a route terminal."""

    route = tuple(route_ids)
    valid: set[frozenset[str]] = set()
    for mask in range(1 << len(route)):
        selected = frozenset(
            focus_id for index, focus_id in enumerate(route) if mask & (1 << index)
        )
        if terminal_id not in selected:
            continue
        if any(
            _mutually_exclusive_focuses(blocks.get(focus_id, "")) & selected
            for focus_id in selected
        ):
            continue

        reachable: set[str] = set()
        pending = set(selected)
        while pending:
            newly_reachable = {
                focus_id
                for focus_id in pending
                if all(
                    group & reachable
                    for group in _prerequisite_groups(blocks.get(focus_id, ""))
                )
            }
            if not newly_reachable:
                break
            reachable.update(newly_reachable)
            pending.difference_update(newly_reachable)
        if reachable == set(selected):
            valid.add(selected)

    minimal = {
        path
        for path in valid
        if not any(other < path for other in valid)
    }
    return tuple(sorted(minimal, key=lambda path: tuple(sorted(path))))


def _postwar_reward_categories(block: str) -> set[str]:
    rewards = _blocks(block, "completion_reward")
    reward = rewards[0] if len(rewards) == 1 else ""
    token_groups = {
        "political": ("add_political_power",),
        "legitimacy": ("add_stability", "add_war_support"),
        "institution": ("add_ideas", "add_timed_idea"),
        "cleanup": ("remove_ideas", "swap_ideas"),
        "command": ("add_command_power",),
        "experience": ("army_experience", "air_experience", "navy_experience"),
        "manpower": ("add_manpower",),
        "material": ("add_equipment_to_stockpile", "add_building_construction"),
        "research": ("add_tech_bonus",),
        "public_unlock": (
            "ADISCORD_vorkerland_focus_postwar_core_decisions_unlocked",
            "WRK_worker_recognize_free_republics_tt",
        ),
    }
    return {
        category
        for category, tokens in token_groups.items()
        if any(token in reward for token in tokens)
    }


def _wartime_gate_source(block: str) -> str:
    return "\n".join((_allow_branch(block), *_blocks(block, "available")))


def _reachable_wartime_outcome(
    blocks: dict[str, str], tag: str, outcome_index: int
) -> tuple[set[str], set[str]]:
    """Return eligible and graph-reachable focuses for one real claimant outcome."""

    route = set(WARTIME_ROUTE_FOCUSES[tag])
    excluded = WARTIME_OUTCOME_EXCLUSIONS[tag][outcome_index]
    false_gate_tokens = WARTIME_OUTCOME_FALSE_GATE_TOKENS[tag][outcome_index]
    eligible = {
        focus_id
        for focus_id in route - set(excluded)
        if not any(
            token in _wartime_gate_source(blocks.get(focus_id, ""))
            for token in false_gate_tokens
        )
    }

    reachable: set[str] = set()
    pending = set(eligible)
    while pending:
        newly_reachable = {
            focus_id
            for focus_id in pending
            if all(
                prerequisite_group & reachable
                for prerequisite_group in _prerequisite_groups(
                    blocks.get(focus_id, "")
                )
            )
        }
        if not newly_reachable:
            break
        reachable.update(newly_reachable)
        pending.difference_update(newly_reachable)
    return eligible, reachable


def _reachable_vad_optional_outcome(
    blocks: dict[str, str], outcome_index: int
) -> tuple[set[str], set[str]]:
    """Return eligible and graph-reachable VAD depth focuses for one outcome."""

    false_gate_tokens = WARTIME_OUTCOME_FALSE_GATE_TOKENS["VAD"][outcome_index]
    optional = set(VAD_OPTIONAL_WARTIME_FOCUSES)
    eligible = {
        focus_id
        for focus_id in optional
        if not any(
            token in _wartime_gate_source(blocks.get(focus_id, ""))
            for token in false_gate_tokens
        )
    }
    _core_eligible, core_reachable = _reachable_wartime_outcome(
        blocks, "VAD", outcome_index
    )
    all_reachable = set(core_reachable)
    pending = set(eligible)
    while pending:
        newly_reachable = {
            focus_id
            for focus_id in pending
            if all(
                prerequisite_group & all_reachable
                for prerequisite_group in _prerequisite_groups(
                    blocks.get(focus_id, "")
                )
            )
        }
        if not newly_reachable:
            break
        all_reachable.update(newly_reachable)
        pending.difference_update(newly_reachable)
    return eligible, all_reachable & optional


def _reachable_tva_optional_outcome(
    blocks: dict[str, str], outcome_index: int
) -> set[str]:
    """Return graph-reachable TVA depth focuses for one metric/trial outcome."""

    optional = set(TVA_OPTIONAL_WARTIME_FOCUSES)
    _core_eligible, core_reachable = _reachable_wartime_outcome(
        blocks, "TVA", outcome_index
    )
    all_reachable = set(core_reachable)
    pending = set(optional)
    while pending:
        newly_reachable = {
            focus_id
            for focus_id in pending
            if all(
                prerequisite_group & all_reachable
                for prerequisite_group in _prerequisite_groups(
                    blocks.get(focus_id, "")
                )
            )
        }
        if not newly_reachable:
            break
        all_reachable.update(newly_reachable)
        pending.difference_update(newly_reachable)
    return all_reachable & optional


def _check_graph(blocks: dict[str, str]) -> list[str]:
    issues: list[str] = []
    edges = {focus_id: _prerequisites(block) for focus_id, block in blocks.items()}
    for focus_id, prerequisites in edges.items():
        unknown = sorted(prerequisites - set(blocks))
        if unknown:
            issues.append(f"{focus_id} has unknown prerequisites {unknown}")
        if focus_id in prerequisites:
            issues.append(f"{focus_id} depends on itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(focus_id: str) -> None:
        if focus_id in visited:
            return
        if focus_id in visiting:
            issues.append(f"focus graph contains a cycle through {focus_id}")
            return
        visiting.add(focus_id)
        for prerequisite in edges.get(focus_id, set()):
            if prerequisite in blocks:
                visit(prerequisite)
        visiting.remove(focus_id)
        visited.add(focus_id)

    for focus_id in blocks:
        visit(focus_id)
    return issues


def collect_issues() -> list[str]:
    issues: list[str] = []
    required_paths = (
        FOCUS_FILE,
        CONTINUOUS_FOCUS_FILE,
        ENGLISH_LOCALISATION,
        RUSSIAN_LOCALISATION,
        ENGLISH_COLLAPSE_LOCALISATION,
        RUSSIAN_COLLAPSE_LOCALISATION,
        ENGLISH_POSTWAR_IDEA_LOCALISATION,
        RUSSIAN_POSTWAR_IDEA_LOCALISATION,
        CHARACTER_FILE,
        SHINE_FILE,
        FOCUS_DECISIONS_FILE,
        DIPLOMACY_DECISIONS_FILE,
        DIPLOMACY_EFFECTS_FILE,
        PHASE_EFFECTS_FILE,
        COLLAPSE_IDEAS_FILE,
        FOCUS_EXPANSION_IDEAS_FILE,
        CLAIMANT_EVENTS_FILE,
        WKR_AI_PLAN_FILE,
        VAD_AI_PLAN_FILE,
        TVA_AI_PLAN_FILE,
    )
    for relative in required_paths:
        if not (ROOT / relative).is_file():
            issues.append(f"missing {relative.as_posix()}")
    if issues:
        return issues

    source = read(FOCUS_FILE)
    continuous_source = read(CONTINUOUS_FOCUS_FILE)
    shine_source = read(SHINE_FILE)
    focus_decisions = read(FOCUS_DECISIONS_FILE)
    diplomacy_decisions = read(DIPLOMACY_DECISIONS_FILE)
    diplomacy_effects = read(DIPLOMACY_EFFECTS_FILE)
    phase_effects = read(PHASE_EFFECTS_FILE)
    collapse_ideas = read(COLLAPSE_IDEAS_FILE)
    focus_expansion_ideas = read(FOCUS_EXPANSION_IDEAS_FILE)
    claimant_events = read(CLAIMANT_EVENTS_FILE)
    wkr_ai_plans = read(WKR_AI_PLAN_FILE)
    vad_ai_plans = read(VAD_AI_PLAN_FILE)
    tva_ai_plans = read(TVA_AI_PLAN_FILE)
    characters = read(CHARACTER_FILE)
    try:
        trees = _blocks(source, "focus_tree")
        blocks = focus_blocks(source)
    except ValueError as exc:
        return [str(exc)]
    try:
        continuous_palettes = _blocks(continuous_source, "continuous_focus_palette")
        continuous_blocks = focus_blocks(continuous_source)
    except ValueError as exc:
        return [f"continuous focus palette could not be parsed: {exc}"]

    if len(trees) != 1:
        issues.append(f"lifecycle focus source must define one tree, found {len(trees)}")
        tree = source
    else:
        tree = trees[0]
    if "id = ADISCORD_vorkerland_civil_war_focus" not in tree:
        issues.append("lifecycle focus tree id is missing")
    if not re.search(r"(?m)^\s*default\s*=\s*no\s*$", tree):
        issues.append("lifecycle focus tree must be non-default")

    country_blocks = _blocks(tree, "country")
    if len(country_blocks) != 1:
        issues.append(f"lifecycle focus tree must have one country selector, found {len(country_blocks)}")
    else:
        country = country_blocks[0]
        tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", country))
        if tags != {"WRK", "WKR", "VAD", "TVA"}:
            issues.append(f"country selector must cover WRK/WKR/VAD/TVA, found {sorted(tags)}")
        if "original_tag" in country:
            issues.append("country selector must use current lifecycle tags, not original_tag")
        if not re.search(r"\bfactor\s*=\s*0\b", country):
            issues.append("country selector must start from factor 0")
        if not re.search(r"\badd\s*=\s*100\b", country):
            issues.append("country selector must add weight 100 for lifecycle tags")

    if tuple(blocks) != FOCUS_IDS:
        issues.append(f"focus IDs/order differ from the 151-focus lifecycle manifest: {tuple(blocks)}")
    if len(FOCUS_IDS) != 151:
        issues.append(f"validator manifest must contain 151 definitions, found {len(FOCUS_IDS)}")
    issues.extend(_check_graph(blocks))

    if len(continuous_palettes) != 1:
        issues.append(
            "Vorkerland continuous focus source must define exactly one palette, "
            f"found {len(continuous_palettes)}"
        )
    else:
        palette_header = continuous_palettes[0].split("focus =", maxsplit=1)[0]
        for token in (
            "id = generic_focus",
            "country = { factor = 1 }",
            "default = yes",
            "reset_on_civilwar = no",
        ):
            if token not in palette_header:
                issues.append(f"Vorkerland continuous focus palette lacks {token}")
    if tuple(continuous_blocks) != VORKERLAND_CONTINUOUS_FOCUSES:
        issues.append(
            "continuous focus IDs/order differ from the three-focus Vorkerland manifest: "
            f"{tuple(continuous_blocks)}"
        )
    continuous_gate_tokens = (
        "AND = { tag = WKR has_country_flag = ADISCORD_vorkerland_focus_wkr_central_war_unlocked }",
        "AND = { tag = VAD has_country_flag = ADISCORD_vorkerland_focus_vad_central_war_unlocked }",
        "AND = { tag = TVA has_country_flag = ADISCORD_vorkerland_focus_tva_central_war_unlocked }",
        "AND = { tag = WRK has_global_flag = ADISCORD_vorkerland_phase_postwar_integration }",
    )
    for focus_id in VORKERLAND_CONTINUOUS_FOCUSES:
        block = continuous_blocks.get(focus_id, "")
        available = _blocks(block, "available")
        enable = _blocks(block, "enable")
        for gate_name, gate_blocks in (("available", available), ("enable", enable)):
            if len(gate_blocks) != 1:
                issues.append(
                    f"continuous focus {focus_id} must define one {gate_name} gate"
                )
                continue
            gate = gate_blocks[0]
            tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", gate))
            if tags != {"WRK", "WKR", "VAD", "TVA"}:
                issues.append(
                    f"continuous focus {focus_id} {gate_name} tags {sorted(tags)} "
                    "must be WRK/WKR/VAD/TVA only"
                )
            for token in continuous_gate_tokens:
                if gate.count(token) != 1:
                    issues.append(
                        f"continuous focus {focus_id} {gate_name} gate must contain "
                        f"{token} exactly once"
                    )

        icon, strategy, modifier_tokens = VORKERLAND_CONTINUOUS_FOCUS_CONTRACTS[
            focus_id
        ]
        for token in (
            f"icon = {icon}",
            f"supports_ai_strategy = {strategy}",
            "daily_cost = 1",
            "available_if_capitulated = no",
        ):
            if block.count(token) != 1:
                issues.append(
                    f"continuous focus {focus_id} must contain {token} exactly once"
                )
        for token in modifier_tokens:
            if block.count(token) != 1:
                issues.append(
                    f"continuous focus {focus_id} must contain bounded modifier {token} exactly once"
                )
        if len(_blocks(block, "ai_will_do")) != 1:
            issues.append(f"continuous focus {focus_id} must define one AI weight")
        for forbidden in (
            "completion_reward",
            "add_manpower",
            "add_equipment_to_stockpile",
            "add_political_power",
            "add_stability",
            "set_country_flag",
            "set_global_flag",
        ):
            if forbidden in block:
                issues.append(
                    f"continuous focus {focus_id} contains repeatable lump effect {forbidden}"
                )

    invalid_focus_triggers = {
        "stability": r"(?<!has_)(?<!add_)\bstability\s*(?:=|<|>)",
        "political_power": r"(?<!has_)(?<!add_)\bpolitical_power\s*(?:=|<|>)",
    }
    for trigger, pattern in invalid_focus_triggers.items():
        if re.search(pattern, source):
            issues.append(
                f"lifecycle focus tree uses invalid bare {trigger} trigger syntax"
            )
    if re.search(r"\binfantry_equipment_1\b", source):
        issues.append(
            "lifecycle focus tree references unavailable equipment infantry_equipment_1"
        )

    lifecycle_effect_names = (
        PREWAR_CARRYOVER_EFFECT,
        DORMANT_WRK_SCRUB_EFFECT,
        WORKER_REFORM_INHERIT_EFFECT,
        "ADISCORD_vorkerland_verify_collapse_materialized",
        *WRK_FORMATION_EFFECTS.values(),
    )
    lifecycle_effects: dict[str, str] = {}
    try:
        for effect_name in lifecycle_effect_names:
            definitions = _blocks(phase_effects, effect_name)
            if len(definitions) != 1:
                issues.append(
                    f"phase lifecycle effect {effect_name} must have one definition, "
                    f"found {len(definitions)}"
                )
            else:
                lifecycle_effects[effect_name] = definitions[0]
    except ValueError as exc:
        issues.append(f"phase lifecycle effects could not be parsed: {exc}")

    carryover = lifecycle_effects.get(PREWAR_CARRYOVER_EFFECT, "")
    if carryover:
        carryover_guard = re.search(
            rf"NOT\s*=\s*\{{\s*has_country_flag\s*=\s*{PREWAR_CARRYOVER_FLAG}\s*\}}",
            carryover,
        )
        if "tag = WKR" not in carryover or carryover_guard is None:
            issues.append("WRK prewar carryover must be WKR-only and guarded by its idempotence flag")
        if carryover.count(f"set_country_flag = {PREWAR_CARRYOVER_FLAG}") != 1:
            issues.append("WRK prewar carryover must set its idempotence flag exactly once")
        for focus_id in PREWAR_WRK_CARRYOVER_FOCUSES:
            if carryover.count(f"has_completed_focus = {focus_id}") != 1:
                issues.append(f"WRK prewar carryover must derive {focus_id} from completed-focus truth")

    verify_collapse = lifecycle_effects.get(
        "ADISCORD_vorkerland_verify_collapse_materialized", ""
    )
    if verify_collapse:
        wkr_tree_scopes = [
            scope
            for scope in _blocks(verify_collapse, "WKR")
            if "load_focus_tree" in scope
        ]
        if len(wkr_tree_scopes) != 1 or (
            f"{PREWAR_CARRYOVER_EFFECT} = yes" not in wkr_tree_scopes[0]
        ):
            issues.append("verified WKR tree installation must invoke the idempotent prewar carryover")

    dormant_scrub = lifecycle_effects.get(DORMANT_WRK_SCRUB_EFFECT, "")
    if dormant_scrub:
        scrubbed_ideas = Counter(
            re.findall(r"\bremove_ideas\s*=\s*([A-Za-z0-9_]+)", dormant_scrub)
        )
        for idea_id in DORMANT_WRK_CRISIS_IDEAS:
            if scrubbed_ideas[idea_id] != 1:
                issues.append(f"dormant WRK crisis scrub must remove {idea_id} exactly once")

    worker_inheritance = lifecycle_effects.get(WORKER_REFORM_INHERIT_EFFECT, "")
    if worker_inheritance:
        if worker_inheritance.count(f"{DORMANT_WRK_SCRUB_EFFECT} = yes") != 1:
            issues.append("worker reform inheritance must begin from the common dormant-WRK scrub")
        if len(_blocks(worker_inheritance, "if")) != 2 or len(
            _blocks(worker_inheritance, "else_if")
        ) != 4:
            issues.append("worker reform inheritance must keep two exact three-stage fallback chains")
        inherited_ideas = re.findall(
            r"\badd_ideas\s*=\s*([A-Za-z0-9_]+)", worker_inheritance
        )
        if Counter(inherited_ideas) != Counter(WORKER_REFORM_STAGE_IDEAS):
            issues.append("worker reform inheritance must add only the six exact reform stages")
        for idea_id in WORKER_REFORM_STAGE_IDEAS:
            if worker_inheritance.count(f"WKR = {{ has_idea = {idea_id} }}") != 1:
                issues.append(f"worker reform inheritance must read {idea_id} from WKR exactly once")

    for winner_tag, formation_name in WRK_FORMATION_EFFECTS.items():
        formation = lifecycle_effects.get(formation_name, "")
        if not formation:
            continue
        route_bridge = (
            WORKER_REFORM_INHERIT_EFFECT
            if winner_tag == "WKR"
            else DORMANT_WRK_SCRUB_EFFECT
        )
        bridge_token = f"{route_bridge} = yes"
        annex_token = f"annex_country = {{ target = {winner_tag} transfer_troops = yes }}"
        if formation.count(bridge_token) != 1:
            issues.append(f"{formation_name} must invoke {route_bridge} exactly once")
        if formation.count(annex_token) != 1:
            issues.append(f"{formation_name} must annex its winner {winner_tag} exactly once")
        elif formation.find(bridge_token) > formation.find(annex_token):
            issues.append(f"{formation_name} must preserve/scrub dormant WRK before annexing {winner_tag}")

    category_by_focus: dict[str, tuple[str, str | None]] = {}
    for focus_id in PREWAR_WRK_FOCUSES:
        category_by_focus[focus_id] = ("prewar", "WRK")
    for focus_id in PREWAR_VAD_FOCUSES:
        category_by_focus[focus_id] = ("prewar", "VAD")
    for focus_id in RETIRED_WARTIME_FOCUSES:
        category_by_focus[focus_id] = ("retired", None)
    for tag, focus_ids in WARTIME_ROUTE_FOCUSES.items():
        for focus_id in focus_ids:
            category_by_focus[focus_id] = ("wartime", tag)
    for focus_id in WKR_OPTIONAL_WARTIME_FOCUSES:
        category_by_focus[focus_id] = ("optional_wartime", "WKR")
    for focus_id in VAD_OPTIONAL_WARTIME_FOCUSES:
        category_by_focus[focus_id] = ("optional_wartime", "VAD")
    for focus_id in VAD_LATE_WAR_BRIDGE_FOCUSES:
        category_by_focus[focus_id] = ("late_war_bridge", "VAD")
    for focus_id in TVA_OPTIONAL_WARTIME_FOCUSES:
        category_by_focus[focus_id] = ("optional_wartime", "TVA")
    for tag, focus_ids in SHOWDOWN_FOCUSES.items():
        for focus_id in focus_ids:
            category_by_focus[focus_id] = ("showdown", tag)
    for route_flag, focus_ids in POSTWAR_ROUTE_FOCUSES.items():
        for focus_id in focus_ids:
            category_by_focus[focus_id] = ("postwar", route_flag)

    for focus_id, block in blocks.items():
        if "cancel_if_invalid = yes" not in block:
            issues.append(f"{focus_id} must cancel when its lifecycle phase becomes invalid")
        allow = _allow_branch(block)
        if not allow:
            issues.append(f"{focus_id} must define exactly one allow_branch gate")
        category, gate = category_by_focus.get(focus_id, ("unknown", None))
        flags = _phase_flags(block)
        if category == "prewar":
            if flags != {PREWAR_PHASE}:
                issues.append(f"{focus_id} must be prewar-only, found phases {sorted(flags)}")
            if _phase_flags(allow) != {PREWAR_PHASE}:
                issues.append(f"{focus_id} allow_branch must hide outside the prewar phase")
            if set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow)) != {gate}:
                issues.append(f"{focus_id} must expose only the prewar {gate} block")
            cost_expected = {1, 2, 3, 4, 5}
        elif category == "retired":
            if flags:
                issues.append(f"retired focus {focus_id} must not keep lifecycle phase gates")
            if not re.search(r"\balways\s*=\s*no\b", allow):
                issues.append(f"retired focus {focus_id} must be hidden by allow_branch")
            available = _blocks(block, "available")
            if len(available) != 1 or not re.search(r"\balways\s*=\s*no\b", available[0]):
                issues.append(f"retired focus {focus_id} must remain unavailable")
            cost_expected = {3, 4}
        elif category == "wartime":
            expected_flags = ACTIVE_PHASE_FLAGS
            if flags != expected_flags:
                issues.append(f"{focus_id} has wrong wartime phases {sorted(flags)}")
            if _phase_flags(allow) != expected_flags:
                issues.append(f"{focus_id} allow_branch has wrong wartime phases {sorted(_phase_flags(allow))}")
            branch_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow))
            expected_tags = {gate}
            if branch_tags != expected_tags:
                issues.append(f"{focus_id} branch tags {sorted(branch_tags)} != {sorted(expected_tags)}")
            cost_expected = {1, 2, 3, 4}
            if len(_blocks(block, "bypass")) != 1:
                issues.append(f"{focus_id} must define one old-save/progression bypass")
        elif category == "optional_wartime":
            expected_flags = ACTIVE_PHASE_FLAGS
            if flags != expected_flags:
                issues.append(f"{focus_id} has wrong optional wartime phases {sorted(flags)}")
            if _phase_flags(allow) != expected_flags:
                issues.append(
                    f"{focus_id} allow_branch has wrong optional wartime phases "
                    f"{sorted(_phase_flags(allow))}"
                )
            branch_tags = set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow))
            if branch_tags != {gate}:
                issues.append(
                    f"{focus_id} optional branch tags {sorted(branch_tags)} != {[gate]}"
                )
            cost_expected = {2, 3} if gate == "WKR" else {2, 3, 5}
            if len(_blocks(block, "bypass")) != 1:
                issues.append(f"{focus_id} must define one idempotent optional-branch bypass")
        elif category == "late_war_bridge":
            expected_flags = LATE_WAR_PHASE_FLAGS
            if flags != expected_flags:
                issues.append(
                    f"{focus_id} has wrong late-war bridge phases {sorted(flags)}"
                )
            if _phase_flags(allow) != expected_flags:
                issues.append(
                    f"{focus_id} allow_branch has wrong late-war bridge phases "
                    f"{sorted(_phase_flags(allow))}"
                )
            branch_tags = set(
                re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow)
            )
            if branch_tags != {"VAD"}:
                issues.append(
                    f"{focus_id} late-war bridge tags {sorted(branch_tags)} != ['VAD']"
                )
            cost_expected = {2, 3, 4}
            if len(_blocks(block, "bypass")) != 1:
                issues.append(
                    f"{focus_id} must define one idempotent late-war bridge bypass"
                )
        elif category == "showdown":
            if flags != {SHOWDOWN_PHASE}:
                issues.append(
                    f"{focus_id} must be showdown-only, found phases {sorted(flags)}"
                )
            if _phase_flags(allow) != {SHOWDOWN_PHASE}:
                issues.append(
                    f"{focus_id} allow_branch must hide outside the central showdown"
                )
            branch_tags = set(
                re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow)
            )
            if branch_tags != {gate}:
                issues.append(
                    f"{focus_id} showdown branch tags {sorted(branch_tags)} != {[gate]}"
                )
            cost_expected = {2, 3, 4}
            if len(_blocks(block, "bypass")) != 1:
                issues.append(
                    f"{focus_id} must define one idempotent showdown bypass"
                )
        elif category == "postwar":
            if flags != {POSTWAR_PHASE}:
                issues.append(f"{focus_id} must be postwar-only, found phases {sorted(flags)}")
            if _phase_flags(allow) != {POSTWAR_PHASE}:
                issues.append(f"{focus_id} allow_branch must hide outside postwar integration")
            if set(re.findall(r"\btag\s*=\s*([A-Z0-9]{3})\b", allow)) != {"WRK"}:
                issues.append(f"{focus_id} must expose only the reunified WRK block")
            if f"has_country_flag = {gate}" not in allow:
                issues.append(f"{focus_id} is not isolated behind {gate}")
            cost_expected = {1, 2, 3, 4, 5, 6, 7}
        else:
            issues.append(f"{focus_id} is not classified in the lifecycle manifest")
            continue

        cost_match = re.search(r"(?m)^\s*cost\s*=\s*(\d+)\s*$", block)
        cost = int(cost_match.group(1)) if cost_match else -1
        if cost not in cost_expected:
            issues.append(f"{focus_id} cost {cost} is outside {sorted(cost_expected)}")

        position = {
            axis: re.search(rf"(?m)^\s*{axis}\s*=\s*(-?\d+)\s*$", block)
            for axis in ("x", "y")
        }
        if any(match is None or int(match.group(1)) < 0 for match in position.values()):
            issues.append(f"{focus_id} must have non-negative absolute x/y coordinates")

        icon_matches = re.findall(r"(?m)^\s*icon\s*=\s*([A-Za-z0-9_]+)\s*$", block)
        if len(icon_matches) != 1 or icon_matches[0] not in KNOWN_SHINED_ICONS:
            issues.append(f"{focus_id} must use one known generic shined icon, found {icon_matches}")
        elif f'name = "{icon_matches[0]}_shine"' not in shine_source:
            issues.append(f"{focus_id} icon {icon_matches[0]} lacks an explicit local shine sprite")
        expected_icon = SIGNATURE_ICONS.get(focus_id)
        if expected_icon and icon_matches != [expected_icon]:
            issues.append(f"{focus_id} signature icon {icon_matches} != {expected_icon}")
        ai = _blocks(block, "ai_will_do")
        ai_base = re.search(r"\bbase\s*=\s*(\d+)\b", ai[0]) if len(ai) == 1 else None
        if ai_base is None or not 1 <= int(ai_base.group(1)) <= 250:
            issues.append(f"{focus_id} must define a bounded positive AI weight")

    if len(PREWAR_WRK_EXPANSION_FOCUSES) != 4 or len(PREWAR_VAD_EXPANSION_FOCUSES) != 4:
        issues.append("prewar Worker-Vadl expansion must contain exactly eight definitions")
    for focus_id in (*PREWAR_WRK_EXPANSION_FOCUSES, *PREWAR_VAD_EXPANSION_FOCUSES):
        block = blocks.get(focus_id, "")
        position = tuple(
            int(re.search(rf"(?m)^\s*{axis}\s*=\s*(-?\d+)\s*$", block).group(1))
            for axis in ("x", "y")
        )
        if position != PREWAR_EXPANSION_POSITIONS[focus_id]:
            issues.append(
                f"{focus_id} position {position} != {PREWAR_EXPANSION_POSITIONS[focus_id]}"
            )
        if _focus_cost(block) != PREWAR_EXPANSION_COSTS[focus_id]:
            issues.append(
                f"{focus_id} cost {_focus_cost(block)} != {PREWAR_EXPANSION_COSTS[focus_id]}"
            )
        if _prerequisite_groups(block) != PREWAR_EXPANSION_PREREQUISITES[focus_id]:
            issues.append(
                f"{focus_id} prerequisites {_prerequisite_groups(block)} != "
                f"{PREWAR_EXPANSION_PREREQUISITES[focus_id]}"
            )

    prewar_choice_pairs = (
        ("WRK_open_worker_vadl_backchannel", "WRK_mobilize_loyal_republics"),
        ("VAD_prepare_vadl_worker_terms", "VAD_activate_eastern_mandate"),
    )
    for left, right in prewar_choice_pairs:
        if _mutually_exclusive_focuses(blocks.get(left, "")) != {right}:
            issues.append(f"{left} must be mutually exclusive with {right}")
        if _mutually_exclusive_focuses(blocks.get(right, "")) != {left}:
            issues.append(f"{right} must be mutually exclusive with {left}")

    for focus_id, (set_flag, clear_flag) in PREWAR_COURSE_SELECTIONS.items():
        selections = _blocks(blocks.get(focus_id, ""), "select_effect")
        if len(selections) != 1:
            issues.append(f"{focus_id} must define one course select_effect")
            continue
        selection = selections[0]
        if selection.count(f"set_country_flag = {set_flag}") != 1:
            issues.append(f"{focus_id} must set course flag {set_flag} exactly once")
        if selection.count(f"clr_country_flag = {clear_flag}") != 1:
            issues.append(f"{focus_id} must clear opposite course flag {clear_flag} exactly once")

    for focus_id, expected_base in {
        "WRK_open_worker_vadl_backchannel": 35,
        "WRK_mobilize_loyal_republics": 65,
    }.items():
        ai_blocks = _blocks(blocks.get(focus_id, ""), "ai_will_do")
        ai_base = (
            re.search(r"\bbase\s*=\s*(\d+)\b", ai_blocks[0])
            if len(ai_blocks) == 1
            else None
        )
        if ai_base is None or int(ai_base.group(1)) != expected_base:
            issues.append(
                f"{focus_id} AI base must be {expected_base} to keep compact optional"
            )

    compact_finals = {
        "WRK_offer_emergency_compact": "ADISCORD_vorkerland_wrk_compact_committed",
        "VAD_ratify_emergency_compact": "ADISCORD_vorkerland_vad_compact_committed",
    }
    for focus_id, final_flag in compact_finals.items():
        reward_blocks = _blocks(blocks.get(focus_id, ""), "completion_reward")
        reward = reward_blocks[0] if len(reward_blocks) == 1 else ""
        if reward.count("ADISCORD_vorkerland_resolve_prewar_compact = yes") != 1:
            issues.append(f"{focus_id} must invoke the compact resolver exactly once")
        if reward.count(f"set_country_flag = {final_flag}") != 1:
            issues.append(f"{focus_id} must set final compact flag {final_flag}")

    hardline_rewards = {
        "WRK_place_reserves_under_worker": (
            "add_manpower = 250",
            "type = infantry_equipment_0 amount = 150 producer = WRK",
            "idea = ADISCORD_vorkerland_wrk_loyal_republics_mobilized days = 70",
            "set_country_flag = ADISCORD_vorkerland_wrk_hardline_committed",
        ),
        "VAD_seal_district_arsenals": (
            "add_manpower = 250",
            "type = infantry_equipment_0 amount = 150 producer = VAD",
            "idea = ADISCORD_vorkerland_vad_eastern_mandate days = 70",
            "set_country_flag = ADISCORD_vorkerland_vad_hardline_committed",
        ),
    }
    for focus_id, tokens in hardline_rewards.items():
        reward_blocks = _blocks(blocks.get(focus_id, ""), "completion_reward")
        reward = reward_blocks[0] if len(reward_blocks) == 1 else ""
        for token in tokens:
            if reward.count(token) != 1:
                issues.append(f"{focus_id} must contain hardline reward {token} exactly once")

    if carryover:
        hardline_scopes = [
            scope
            for scope in _blocks(carryover, "if")
            if "has_completed_focus = WRK_place_reserves_under_worker" in scope
            and scope.count("has_completed_focus = ") == 1
        ]
        if len(hardline_scopes) != 1:
            issues.append("WRK hardline preparation must have one completed-focus carryover scope")
        else:
            for token in (
                "add_manpower = 250",
                "type = infantry_equipment_0 amount = 150 producer = WKR",
                "idea = ADISCORD_vorkerland_wrk_loyal_republics_mobilized days = 70",
                "set_country_flag = ADISCORD_vorkerland_wrk_hardline_committed",
                "set_country_flag = ADISCORD_vorkerland_focus_wrk_reserves_under_worker",
            ):
                if hardline_scopes[0].count(token) != 1:
                    issues.append(f"WRK hardline carryover must contain {token} exactly once")

    if {tag: len(focuses) for tag, focuses in SHOWDOWN_FOCUSES.items()} != {
        "WKR": 7,
        "VAD": 5,
        "TVA": 5,
    }:
        issues.append("live-showdown expansion must contain exactly 7 WKR, 5 VAD, and 5 TVA focuses")

    showdown_opponents = {
        "WKR": {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "VAD", "TVA"},
        "VAD": {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "WKR", "TVA"},
        "TVA": {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV", "WKR", "VAD"},
    }
    for tag, focus_ids in SHOWDOWN_FOCUSES.items():
        positions: set[tuple[int, int]] = set()
        for focus_id in focus_ids:
            block = blocks.get(focus_id, "")
            position = tuple(
                int(re.search(rf"(?m)^\s*{axis}\s*=\s*(-?\d+)\s*$", block).group(1))
                for axis in ("x", "y")
            )
            if position != SHOWDOWN_POSITIONS[focus_id]:
                issues.append(f"{focus_id} position {position} != {SHOWDOWN_POSITIONS[focus_id]}")
            if position in positions:
                issues.append(f"{tag} showdown focus position {position} is duplicated")
            positions.add(position)
            if _focus_cost(block) != SHOWDOWN_COSTS[focus_id]:
                issues.append(f"{focus_id} cost {_focus_cost(block)} != {SHOWDOWN_COSTS[focus_id]}")
            if _prerequisite_groups(block) != SHOWDOWN_PREREQUISITES[focus_id]:
                issues.append(
                    f"{focus_id} prerequisites {_prerequisite_groups(block)} != "
                    f"{SHOWDOWN_PREREQUISITES[focus_id]}"
                )
            allow = _allow_branch(block)
            for token in (
                "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
                "has_global_flag = ADISCORD_vorkerland_central_showdown_started",
                "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
            ):
                if token not in allow:
                    issues.append(f"{focus_id} showdown allow_branch lacks {token}")
            available_blocks = _blocks(block, "available")
            available = available_blocks[0] if len(available_blocks) == 1 else ""
            if "tooltip = ADISCORD_vorkerland_showdown_focus_live_war_tt" not in available:
                issues.append(f"{focus_id} must expose the live-war tooltip")
            opponents = set(re.findall(r"\bhas_war_with\s*=\s*([A-Z0-9]{3})\b", available))
            if opponents != showdown_opponents[tag]:
                issues.append(
                    f"{focus_id} live-war opponents {sorted(opponents)} != "
                    f"{sorted(showdown_opponents[tag])}"
                )

    night_freight = blocks.get("WKR_reopen_night_freight_corridors", "")
    night_rewards = _blocks(night_freight, "completion_reward")
    night_reward = night_rewards[0] if len(night_rewards) == 1 else ""
    for state_id in (200, 201):
        for token in (
            f"owns_state = {state_id}",
            f"controls_state = {state_id}",
            f"{state_id} = {{ infrastructure < 5 }}",
            f"{state_id} = {{ add_building_construction = {{ type = infrastructure level = 1 instant_build = yes }} }}",
        ):
            if token not in night_reward:
                issues.append(f"WKR night freight reward lacks bounded state {state_id} token {token}")
    for dead_state_id in (32, 33):
        if re.search(rf"\b{dead_state_id}\b", night_reward):
            issues.append(f"WKR night freight must not target maxed state {dead_state_id}")
    if night_reward.count(
        "type = support_equipment amount = 50 producer = WKR"
    ) != 1:
        issues.append("WKR night freight must grant one support-equipment fallback")

    expansion_source = "\n".join(
        blocks.get(focus_id, "")
        for focus_id in (
            *PREWAR_WRK_EXPANSION_FOCUSES,
            *PREWAR_VAD_EXPANSION_FOCUSES,
            *(focus_id for focus_ids in SHOWDOWN_FOCUSES.values() for focus_id in focus_ids),
        )
    )
    for forbidden in (
        "activate_mission",
        "declare_war_on",
        "create_wargoal",
        "annex_country",
        "white_peace",
        "transfer_state",
        "every_country",
        "random_country",
        "on_daily",
        "on_weekly",
        "on_monthly",
        "set_global_flag",
    ):
        if forbidden in expansion_source:
            issues.append(f"focus expansion must not contain {forbidden}")

    for idea_id in FOCUS_EXPANSION_IDEAS:
        definitions = _blocks(focus_expansion_ideas, idea_id)
        if len(definitions) != 1:
            issues.append(f"focus expansion idea {idea_id} must have one definition")
            continue
        idea = definitions[0]
        for token in (
            "allowed = { always = no }",
            "allowed_civil_war = { always = yes }",
            "removal_cost = -1",
            "ai_will_do = { factor = 0 }",
        ):
            if idea.count(token) != 1:
                issues.append(f"focus expansion idea {idea_id} must contain {token} exactly once")
        if expansion_source.count(idea_id) < 1:
            issues.append(f"focus expansion idea {idea_id} is not earned by an expansion focus")

    ai_sources = {"WKR": wkr_ai_plans, "VAD": vad_ai_plans, "TVA": tva_ai_plans}
    for tag, plans in SHOWDOWN_AI_PLANS.items():
        for plan_id, expected_focuses in plans.items():
            definitions = _blocks(ai_sources[tag], plan_id)
            if len(definitions) != 1:
                issues.append(f"showdown AI plan {plan_id} must have one definition")
                continue
            plan = definitions[0]
            focus_lists = _blocks(plan, "ai_national_focuses")
            actual_focuses = (
                tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", focus_lists[0]))
                if len(focus_lists) == 1
                else ()
            )
            if actual_focuses != expected_focuses:
                issues.append(
                    f"showdown AI plan {plan_id} focus order {actual_focuses} != {expected_focuses}"
                )
            for token in (
                f"tag = {tag}",
                "is_ai = yes",
                "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
                "has_global_flag = ADISCORD_vorkerland_central_showdown_started",
                "NOT = { has_global_flag = ADISCORD_vorkerland_central_war_finished }",
                "has_war = yes",
                "weight = { factor = 5 }",
            ):
                if token not in plan:
                    issues.append(f"showdown AI plan {plan_id} lacks {token}")

    vad_prewar_terminal = "VAD_form_emergency_chancery"
    vad_prewar_paths = _postwar_completion_paths(
        blocks, PREWAR_VAD_BASE_FOCUSES, vad_prewar_terminal
    )
    if len(vad_prewar_paths) != 2:
        issues.append(
            "VAD prewar continuity programme must expose two terminal paths, "
            f"found {len(vad_prewar_paths)}"
        )
    if vad_prewar_paths and set().union(*vad_prewar_paths) != set(PREWAR_VAD_BASE_FOCUSES):
        issues.append("VAD prewar programme has focuses outside every terminal path")
    for path in vad_prewar_paths:
        if len(path) != 4:
            issues.append(
                f"VAD prewar terminal path must complete four focuses, found {len(path)}"
            )
        cost_units = sum(_focus_cost(blocks.get(focus_id, "")) for focus_id in path)
        if cost_units != 8:
            issues.append(
                f"VAD prewar terminal path costs {cost_units} units ({cost_units * 7} days), "
                "expected 56 days"
            )
    for focus_id in PREWAR_VAD_BASE_FOCUSES:
        block = blocks.get(focus_id, "")
        cost = _focus_cost(block)
        payload = _postwar_reward_categories(block)
        minimum_payload = 2 if cost <= 2 else 4
        if len(payload) < minimum_payload:
            issues.append(
                f"VAD prewar focus {focus_id} cost {cost} has only "
                f"{len(payload)} substantive reward classes {sorted(payload)}; "
                f"needs {minimum_payload}"
            )
    if _focus_cost(blocks.get(vad_prewar_terminal, "")) != 3:
        issues.append("VAD emergency chancery must be a bundled 21-day convergence focus")

    expected_wartime_sizes = {"WKR": 17, "VAD": 17, "TVA": 18}
    for tag, expected_size in expected_wartime_sizes.items():
        authored = len(WARTIME_ROUTE_FOCUSES[tag])
        if authored != expected_size:
            issues.append(f"{tag} asymmetric wartime route must contain {expected_size} definitions, found {authored}")
        route_source = "\n".join(blocks.get(focus_id, "") for focus_id in WARTIME_ROUTE_FOCUSES[tag])
        for retired_id in RETIRED_WARTIME_FOCUSES:
            if f"focus = {retired_id}" in route_source:
                issues.append(f"{tag} compact route still depends on retired filler {retired_id}")
        if route_source.count("modifier =") < 3:
            issues.append(f"{tag} compact route lacks contextual AI modifiers")

        positions: dict[tuple[int, int], str] = {}
        ys: list[int] = []
        route_set = set(WARTIME_ROUTE_FOCUSES[tag])
        for focus_id in WARTIME_ROUTE_FOCUSES[tag]:
            block = blocks.get(focus_id, "")
            x_match = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block)
            y_match = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block)
            if x_match is None or y_match is None:
                continue
            position = (int(x_match.group(1)), int(y_match.group(1)))
            if position in positions:
                issues.append(
                    f"{tag} wartime focuses {positions[position]} and {focus_id} overlap at {position}"
                )
            positions[position] = focus_id
            ys.append(position[1])
            for prerequisite in _prerequisites(block) & route_set:
                parent = blocks.get(prerequisite, "")
                parent_x = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", parent)
                parent_y = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", parent)
                if parent_x and parent_y:
                    dx = abs(position[0] - int(parent_x.group(1)))
                    dy = position[1] - int(parent_y.group(1))
                    if not 1 <= dy <= 3 or dx > 5:
                        issues.append(
                            f"{tag} edge {prerequisite}->{focus_id} is not compact/readable (dx={dx}, dy={dy})"
                        )
        if ys and max(ys) - min(ys) > 6:
            issues.append(f"{tag} wartime layout exceeds seven compact rows")

        outcome_count = len(WARTIME_OUTCOME_EXCLUSIONS[tag])
        if len(WARTIME_OUTCOME_FALSE_GATE_TOKENS[tag]) != outcome_count:
            issues.append(f"{tag} outcome gate profiles do not match its exclusions")
        for outcome_index, excluded in enumerate(WARTIME_OUTCOME_EXCLUSIONS[tag]):
            expected = route_set - set(excluded)
            eligible, reachable = _reachable_wartime_outcome(
                blocks, tag, outcome_index
            )
            accidentally_gated = sorted(expected - eligible)
            if accidentally_gated:
                issues.append(
                    f"{tag} outcome {outcome_index + 1} has impossible identity gates on "
                    f"{accidentally_gated}"
                )
            unreachable = sorted(expected - reachable)
            if unreachable:
                issues.append(
                    f"{tag} outcome {outcome_index + 1} cannot reach {unreachable} through "
                    "its prerequisite graph"
                )
            if len(reachable) != 14:
                issues.append(
                    f"{tag} outcome {outcome_index + 1} must reach 14 completable focuses, "
                    f"found {len(reachable)}"
                )
            capstone = CENTRAL_CAPSTONES[tag][0]
            if capstone not in reachable:
                issues.append(
                    f"{tag} outcome {outcome_index + 1} cannot reach its capstone {capstone}"
                )

        capstone_flag = CENTRAL_CAPSTONES[tag][1]
        for focus_id in NEW_WARTIME_FOCUSES[tag]:
            bypasses = _blocks(blocks.get(focus_id, ""), "bypass")
            if len(bypasses) != 1 or f"has_country_flag = {capstone_flag}" not in bypasses[0]:
                issues.append(f"new focus {focus_id} lacks old-save capstone bypass {capstone_flag}")

    if len(WKR_OPTIONAL_WARTIME_FOCUSES) != 6:
        issues.append(
            "WKR optional southern branch must contain exactly six definitions, "
            f"found {len(WKR_OPTIONAL_WARTIME_FOCUSES)}"
        )
    optional_prerequisites = {
        "WKR_establish_workers_air_command": {"WKR_affirm_worker_mandate"},
        "WKR_keep_frontline_sorties_flying": {"WKR_establish_workers_air_command"},
        "WKR_raise_mobile_fortification_crews": {"WKR_establish_workers_air_command"},
        "WKR_secure_the_southern_corridor": {"WKR_establish_workers_air_command"},
        "WKR_rehearse_operation_southbound": {
            "WKR_keep_frontline_sorties_flying",
            "WKR_raise_mobile_fortification_crews",
            "WKR_secure_the_southern_corridor",
        },
        "WKR_intervene_in_solyarino": {"WKR_rehearse_operation_southbound"},
    }
    for focus_id, expected in optional_prerequisites.items():
        actual = _prerequisites(blocks.get(focus_id, ""))
        if actual != expected:
            issues.append(f"{focus_id} optional prerequisites {sorted(actual)} != {sorted(expected)}")
    optional_source = "\n".join(
        blocks.get(focus_id, "") for focus_id in WKR_OPTIONAL_WARTIME_FOCUSES
    )
    for token in (
        "ADISCORD_vorkerland_bootstrap_wkr_air_sustainment = yes",
        "ADISCORD_vorkerland_build_wkr_live_frontline_fortifications = yes",
        "type = infrastructure level = 1 instant_build = yes",
        "ADISCORD_vorkerland_solar_counter_preparation days = 42",
        "ADISCORD_vorkerland_attempt_wkr_solyarino_intervention = yes",
    ):
        if token not in optional_source:
            issues.append(f"WKR optional southern branch lacks payload {token}")
    terminal = blocks.get("WKR_intervene_in_solyarino", "")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
        "ADISCORD_vorkerland_wkr_has_solyarino_intervention_border = yes",
        "ADISCORD_vorkerland_wkr_has_valid_solyarino_target = yes",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_reserved }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active }",
    ):
        if token not in terminal:
            issues.append(f"WKR Solarino terminal lacks gate {token}")
    terminal_available_blocks = _blocks(terminal, "available")
    terminal_available = terminal_available_blocks[0] if len(terminal_available_blocks) == 1 else ""
    for obsolete_blocker in (
        "ADISCORD_vorkerland_focus_central_showdown_requested",
        "ADISCORD_vorkerland_showdown_queue_initialized",
        "ADISCORD_vorkerland_central_showdown_started",
        "ADISCORD_vorkerland_vad_sol_alliance_accepted",
    ):
        if obsolete_blocker in terminal_available:
            issues.append(
                f"WKR Solarino terminal must not retain obsolete blocker {obsolete_blocker}"
            )
    if set(WKR_OPTIONAL_WARTIME_FOCUSES) & set(_prerequisites(blocks.get("WKR_republic_fights_as_one", ""))):
        issues.append("WKR central capstone must not depend on the optional southern branch")

    expected_wkr_core_plans = {
        "ADISCORD_vorkerland_wkr_pragmatist_core_plan": (
            (
                "has_global_flag = ADISCORD_vorkerland_worker_safe_with_loyalists",
                "has_government = pragmatism",
                "has_country_leader_ideology = neo_vorkerism",
                "character = WRK_Nikita_Worcker",
            ),
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
            (
                "NOT = { has_global_flag = ADISCORD_vorkerland_worker_safe_with_loyalists }",
                "has_government = utilitarism",
                "character = WRK_Anton_Bagley",
            ),
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
    for plan_id, (identity_tokens, expected_focuses) in expected_wkr_core_plans.items():
        definitions = _blocks(wkr_ai_plans, plan_id)
        if len(definitions) != 1:
            issues.append(f"WKR AI plan {plan_id} must have one definition")
            continue
        plan = definitions[0]
        plan_focus_blocks = _blocks(plan, "ai_national_focuses")
        actual_focuses = (
            tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", plan_focus_blocks[0]))
            if len(plan_focus_blocks) == 1
            else ()
        )
        if actual_focuses != expected_focuses:
            issues.append(
                f"WKR AI plan {plan_id} focus order {actual_focuses} != {expected_focuses}"
            )
        for token in (
            "original_tag = WRK",
            "original_tag = WKR",
            "tag = WKR",
            "is_ai = yes",
            "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
            "NOT = { has_country_flag = ADISCORD_vorkerland_focus_wkr_central_war_unlocked }",
            "weight = { factor = 3 }",
            *identity_tokens,
        ):
            if token not in plan:
                issues.append(f"WKR AI plan {plan_id} lacks {token}")

    solarino_plan_id = "ADISCORD_vorkerland_wkr_solyarino_operation_plan"
    solarino_definitions = _blocks(wkr_ai_plans, solarino_plan_id)
    if len(solarino_definitions) != 1:
        issues.append("WKR Solarino AI plan must have one definition")
    else:
        solarino_plan = solarino_definitions[0]
        solarino_focus_blocks = _blocks(solarino_plan, "ai_national_focuses")
        solarino_focuses = (
            tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", solarino_focus_blocks[0]))
            if len(solarino_focus_blocks) == 1
            else ()
        )
        if solarino_focuses != ("WKR_intervene_in_solyarino",):
            issues.append(
                "WKR Solarino AI plan must select only its post-capstone intervention focus"
            )
        for token in (
            "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
            "has_global_flag = ADISCORD_vorkerland_phase_central_showdown",
            "has_country_flag = ADISCORD_vorkerland_focus_wkr_central_war_unlocked",
            "weight = { factor = 5 }",
        ):
            if token not in solarino_plan:
                issues.append(f"WKR Solarino AI plan lacks {token}")
        for obsolete_blocker in (
            "ADISCORD_vorkerland_focus_central_showdown_requested",
            "ADISCORD_vorkerland_showdown_queue_initialized",
            "ADISCORD_vorkerland_central_showdown_started",
            "ADISCORD_vorkerland_vad_sol_alliance_accepted",
        ):
            if obsolete_blocker in solarino_plan:
                issues.append(
                    f"WKR Solarino AI plan must not retain obsolete blocker {obsolete_blocker}"
                )

    southern_corridor = blocks.get("WKR_secure_the_southern_corridor", "")
    corridor_reward_blocks = _blocks(southern_corridor, "completion_reward")
    if len(corridor_reward_blocks) != 1:
        issues.append("WKR southern corridor must define one completion reward")
    else:
        corridor_reward = corridor_reward_blocks[0]
        for state_id in (200, 201):
            gate = f"limit = {{ owns_state = {state_id} controls_state = {state_id} }}"
            construction = (
                f"{state_id} = {{ add_building_construction = "
                "{ type = infrastructure level = 1 instant_build = yes } }"
            )
            if corridor_reward.count(gate) != 1:
                issues.append(
                    f"WKR southern corridor must gate state {state_id} exactly once"
                )
            if corridor_reward.count(construction) != 1:
                issues.append(
                    f"WKR southern corridor must improve state {state_id} exactly once"
                )
        for capped_state_id in (32, 33):
            if re.search(
                rf"\b{capped_state_id}\s*=\s*\{{[^{{}}]*"
                r"add_building_construction\s*=\s*\{\s*type\s*=\s*infrastructure\b",
                corridor_reward,
            ):
                issues.append(
                    "WKR southern corridor must not target already capped "
                    f"state {capped_state_id} infrastructure"
                )
        if corridor_reward.count(
            "type = infrastructure level = 1 instant_build = yes"
        ) != 2:
            issues.append(
                "WKR southern corridor must add exactly two live infrastructure levels"
            )

    if len(VAD_LATE_WAR_BRIDGE_FOCUSES) != 4:
        issues.append(
            "VAD late-war bridge must contain exactly four definitions, "
            f"found {len(VAD_LATE_WAR_BRIDGE_FOCUSES)}"
        )
    for focus_id in VAD_LATE_WAR_BRIDGE_FOCUSES:
        block = blocks.get(focus_id, "")
        prerequisite_groups = _prerequisite_groups(block)
        if prerequisite_groups != VAD_LATE_WAR_BRIDGE_PREREQUISITES[focus_id]:
            issues.append(
                f"{focus_id} bridge prerequisites {prerequisite_groups} != "
                f"{VAD_LATE_WAR_BRIDGE_PREREQUISITES[focus_id]}"
            )
        x_match = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block)
        y_match = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block)
        position = (
            int(x_match.group(1)) if x_match else None,
            int(y_match.group(1)) if y_match else None,
        )
        if position != VAD_LATE_WAR_BRIDGE_POSITIONS[focus_id]:
            issues.append(
                f"{focus_id} bridge position {position} != "
                f"{VAD_LATE_WAR_BRIDGE_POSITIONS[focus_id]}"
            )
        colliding_focuses = []
        for other_id, other_block in blocks.items():
            if other_id == focus_id:
                continue
            other_x = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", other_block)
            other_y = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", other_block)
            if other_x and other_y and (
                int(other_x.group(1)),
                int(other_y.group(1)),
            ) == position:
                colliding_focuses.append(other_id)
        if colliding_focuses:
            issues.append(
                f"{focus_id} bridge position {position} overlaps {sorted(colliding_focuses)}"
            )
        cost = _focus_cost(block)
        if cost != VAD_LATE_WAR_BRIDGE_COSTS[focus_id]:
            issues.append(
                f"{focus_id} bridge cost {cost} != "
                f"{VAD_LATE_WAR_BRIDGE_COSTS[focus_id]}"
            )

        available = _blocks(block, "available")
        if len(available) != 1:
            issues.append(f"{focus_id} bridge must define one availability gate")
        else:
            gate = available[0]
            if _phase_flags(gate) != LATE_WAR_PHASE_FLAGS:
                issues.append(
                    f"{focus_id} bridge availability phases "
                    f"{sorted(_phase_flags(gate))} != {sorted(LATE_WAR_PHASE_FLAGS)}"
                )
            for token in (
                "is_subject = no",
                "NOT = { has_capitulated = yes }",
            ):
                if token not in gate:
                    issues.append(f"{focus_id} bridge availability lacks {token}")
            if "has_war" in gate:
                issues.append(
                    f"{focus_id} bridge must remain available between claimant wars"
                )

        completion_rewards = _blocks(block, "completion_reward")
        if len(completion_rewards) != 1:
            issues.append(f"{focus_id} bridge must define one completion reward")
        else:
            reward = completion_rewards[0]
            for token in VAD_LATE_WAR_BRIDGE_REWARDS[focus_id]:
                if reward.count(token) != 1:
                    issues.append(
                        f"{focus_id} bridge reward must contain {token} exactly once"
                    )
        if focus_id == "VAD_restore_eastern_supply_corridors" and block.count(
            "type = infrastructure level = 1 instant_build = yes"
        ) != 1:
            issues.append(
                "VAD eastern supply bridge must add exactly one infrastructure level"
            )
        if focus_id == "VAD_convert_emergency_workshops":
            if block.count("add_extra_state_shared_building_slots = 1") != 1:
                issues.append(
                    "VAD emergency workshops must add exactly one shared building slot"
                )
            if block.count(
                "type = arms_factory level = 1 instant_build = yes"
            ) != 1:
                issues.append(
                    "VAD emergency workshops must add exactly one arms factory"
                )
        for forbidden in (
            "declare_war_on",
            "create_wargoal",
            "ADISCORD_vorkerland_solar_terminal_",
            "ADISCORD_vorkerland_attempt_vad_solar_intervention",
        ):
            if forbidden in block:
                issues.append(
                    f"{focus_id} bridge contains forbidden diplomacy payload {forbidden}"
                )

    if len(VAD_OPTIONAL_WARTIME_FOCUSES) != 9:
        issues.append(
            "VAD optional depth must contain exactly nine definitions, "
            f"found {len(VAD_OPTIONAL_WARTIME_FOCUSES)}"
        )
    vad_optional_prerequisites = {
        "VAD_restore_prefectural_courts": {"VAD_bind_officers_to_chancery"},
        "VAD_issue_crown_mobilization_warrants": {"VAD_restore_prefectural_courts"},
        "VAD_turn_the_chancery_into_a_war_cabinet": {
            "VAD_issue_crown_mobilization_warrants",
            "VAD_settle_restoration_authority",
        },
        "VAD_elect_district_commissars": {"VAD_ratify_joint_command"},
        "VAD_merge_guard_and_worker_rolls": {"VAD_elect_district_commissars"},
        "VAD_sign_the_dual_authority_protocol": {
            "VAD_merge_guard_and_worker_rolls",
            "VAD_settle_restoration_authority",
        },
        "VAD_map_the_solar_corridors": {"VAD_dispatch_solland_liaison_mission"},
        "VAD_preposition_restoration_columns": {"VAD_map_the_solar_corridors"},
        "VAD_define_the_solar_settlement": {
            "VAD_preposition_restoration_columns",
            "VAD_settle_restoration_authority",
        },
    }
    vad_optional_source = "\n".join(
        blocks.get(focus_id, "") for focus_id in VAD_OPTIONAL_WARTIME_FOCUSES
    )
    for focus_id in VAD_OPTIONAL_WARTIME_FOCUSES:
        block = blocks.get(focus_id, "")
        actual_prerequisites = _prerequisites(block)
        if actual_prerequisites != vad_optional_prerequisites[focus_id]:
            issues.append(
                f"{focus_id} optional prerequisites {sorted(actual_prerequisites)} != "
                f"{sorted(vad_optional_prerequisites[focus_id])}"
            )
        x_match = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block)
        y_match = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block)
        position = (
            int(x_match.group(1)) if x_match else None,
            int(y_match.group(1)) if y_match else None,
        )
        if position != VAD_OPTIONAL_POSITIONS[focus_id]:
            issues.append(
                f"{focus_id} position {position} != {VAD_OPTIONAL_POSITIONS[focus_id]}"
            )
        cost = _focus_cost(block)
        if cost != VAD_OPTIONAL_COSTS[focus_id]:
            issues.append(
                f"{focus_id} cost {cost} != {VAD_OPTIONAL_COSTS[focus_id]}"
            )
        payload = _postwar_reward_categories(block)
        if "country_event" in block:
            payload.add("event")
        minimum_payload = 3 if cost <= 3 else 4
        if focus_id == "VAD_define_the_solar_settlement":
            minimum_payload = 1
        if len(payload) < minimum_payload:
            issues.append(
                f"VAD optional focus {focus_id} cost {cost} has only "
                f"{len(payload)} substantive reward classes {sorted(payload)}; "
                f"needs {minimum_payload}"
            )
    if len(set(VAD_OPTIONAL_POSITIONS.values())) != len(VAD_OPTIONAL_POSITIONS):
        issues.append("VAD optional depth contains overlapping authored coordinates")
    if set(VAD_OPTIONAL_WARTIME_FOCUSES) & set(
        _prerequisites(blocks.get("VAD_balance_council_and_command", ""))
    ):
        issues.append("VAD central capstone must not depend on optional depth")
    for outcome_index, expected_optional in enumerate(VAD_OPTIONAL_OUTCOME_FOCUSES):
        eligible, reachable = _reachable_vad_optional_outcome(blocks, outcome_index)
        if eligible != set(expected_optional):
            issues.append(
                f"VAD optional outcome {outcome_index + 1} eligibility "
                f"{sorted(eligible)} != {sorted(expected_optional)}"
            )
        if reachable != set(expected_optional):
            issues.append(
                f"VAD optional outcome {outcome_index + 1} reaches "
                f"{sorted(reachable)} != {sorted(expected_optional)}"
            )
    for token in (
        "declare_war_on",
        "create_wargoal",
        "annex_country",
        "ADISCORD_vorkerland_worx_client",
        "ADISCORD_vorkerland_tva_field_directorate_3",
        "tower_of_unity",
        "Tower of Unity",
    ):
        if token in vad_optional_source:
            issues.append(f"VAD optional depth contains forbidden payload {token}")
    for solar_focus in (
        "VAD_map_the_solar_corridors",
        "VAD_preposition_restoration_columns",
        "VAD_define_the_solar_settlement",
    ):
        if (
            "NOT = { has_global_flag = "
            "ADISCORD_vorkerland_wkr_solyarino_intervention_active }"
            not in blocks.get(solar_focus, "")
        ):
            issues.append(f"{solar_focus} lacks the WKR Solarino lane guard")
    solar_terminal = blocks.get("VAD_define_the_solar_settlement", "")
    for token in (
        "has_global_flag = ADISCORD_vorkerland_phase_central_preparation",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_reserved }",
        "NOT = { has_global_flag = ADISCORD_vorkerland_vad_solar_intervention_active }",
        "country_event = { id = ADISCORD_vorkerland_claimant.14 hours = 1 }",
    ):
        if token not in solar_terminal:
            issues.append(f"VAD Solar settlement focus lacks bounded integration {token}")
    solar_available = _blocks(solar_terminal, "available")
    solar_fallback_tokens = (
        "has_global_flag = ADISCORD_vorkerland_solar_terminal_verified",
        "ADISCORD_vorkerland_solar_terminal_sol = yes",
        "ADISCORD_vorkerland_solar_terminal_sra = yes",
        "ADISCORD_vorkerland_solar_terminal_csl = yes",
    )
    if len(solar_available) != 1:
        issues.append("VAD Solar settlement must define one availability gate")
    else:
        fallback_blocks = _blocks(solar_available[0], "OR")
        if len(fallback_blocks) != 1:
            issues.append(
                "VAD Solar settlement availability must define one direct terminal fallback"
            )
        else:
            fallback = fallback_blocks[0]
            for token in solar_fallback_tokens:
                if fallback.count(token) != 1:
                    issues.append(
                        f"VAD Solar settlement fallback must contain {token} exactly once"
                    )
    solar_rewards = _blocks(solar_terminal, "completion_reward")
    if len(solar_rewards) != 1:
        issues.append("VAD Solar settlement must define one completion reward")
    else:
        solar_reward = solar_rewards[0]
        recorder = "ADISCORD_vorkerland_record_regional_diplomacy_outcomes = yes"
        event = "country_event = { id = ADISCORD_vorkerland_claimant.14 hours = 1 }"
        if solar_reward.count(recorder) != 1:
            issues.append(
                "VAD Solar settlement must record direct terminal truth exactly once"
            )
        elif solar_reward.find(recorder) > solar_reward.find(event):
            issues.append(
                "VAD Solar settlement must record direct terminal truth before its policy event"
            )

    regional_recorders = _blocks(
        diplomacy_effects, "ADISCORD_vorkerland_record_regional_diplomacy_outcomes"
    )
    if len(regional_recorders) != 1:
        issues.append(
            "regional diplomacy outcome recorder must have exactly one definition"
        )
    else:
        recorder = regional_recorders[0]
        solar_record_contract = {
            "sol": "ADISCORD_vorkerland_solar_winner_sol",
            "sra": "ADISCORD_vorkerland_solar_winner_sra",
            "csl": "ADISCORD_vorkerland_solar_winner_csl",
        }
        for suffix, winner_flag in solar_record_contract.items():
            terminal_trigger = f"ADISCORD_vorkerland_solar_terminal_{suffix} = yes"
            if recorder.count(terminal_trigger) != 1:
                issues.append(
                    f"regional outcome recorder must read {terminal_trigger} exactly once"
                )
            if recorder.count(f"set_global_flag = {winner_flag}") != 1:
                issues.append(
                    f"regional outcome recorder must set {winner_flag} exactly once"
                )
        if recorder.count(
            "NOT = { has_global_flag = ADISCORD_vorkerland_solar_terminal_verified }"
        ) != 3:
            issues.append(
                "regional outcome recorder must guard all three Solar terminal branches"
            )
        if recorder.count(
            "set_global_flag = ADISCORD_vorkerland_solar_terminal_verified"
        ) != 3:
            issues.append(
                "regional outcome recorder must verify each direct Solar terminal branch"
            )

    for focus_id, (idea_id, days) in VAD_WARTIME_TIMED_IDEAS.items():
        reward = f"add_timed_idea = {{ idea = {idea_id} days = {days} }}"
        if blocks.get(focus_id, "").count(reward) != 1:
            issues.append(f"{focus_id} must grant the bounded {days}-day spirit {idea_id}")
        definitions = _blocks(collapse_ideas, idea_id)
        if len(definitions) != 1:
            issues.append(f"VAD wartime spirit {idea_id} must have one definition")
        elif "removal_cost = -1" not in definitions[0]:
            issues.append(f"VAD wartime spirit {idea_id} must be non-removable")
    for focus_id, (own_idea, other_idea) in VAD_PERMANENT_PROTOCOL_IDEAS.items():
        block = blocks.get(focus_id, "")
        if block.count(f"add_ideas = {own_idea}") != 1:
            issues.append(f"{focus_id} must install permanent protocol {own_idea}")
        for idea_id in (
            "ADISCORD_vorkerland_vad_imperial_chancery",
            "ADISCORD_vorkerland_vad_imperial_registers",
            "ADISCORD_vorkerland_vad_field_commandantures",
            other_idea,
        ):
            if block.count(f"remove_ideas = {idea_id}") != 1:
                issues.append(f"{focus_id} must consolidate prior VAD idea {idea_id}")
        definitions = _blocks(collapse_ideas, own_idea)
        if len(definitions) != 1 or "removal_cost = -1" not in definitions[0]:
            issues.append(f"permanent VAD protocol {own_idea} is not uniquely defined")

    for focus_id, tokens in {
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
    }.items():
        for token in tokens:
            if token not in blocks.get(focus_id, ""):
                issues.append(f"{focus_id} lacks strengthened VAD payload {token}")

    armament_depots = blocks.get("VAD_reopen_armament_depots", "")
    depot_slot = "add_extra_state_shared_building_slots = 1"
    depot_factory = "type = arms_factory level = 1 instant_build = yes"
    if armament_depots.count("limit = { controls_state = 75 }") != 1:
        issues.append("VAD armament depots must retain their state 75 control gate")
    if armament_depots.count(depot_slot) != 1:
        issues.append("VAD armament depots must add one guaranteed shared slot")
    if armament_depots.count(depot_factory) != 1:
        issues.append("VAD armament depots must build exactly one arms factory")
    if 0 <= armament_depots.find(depot_factory) < armament_depots.find(depot_slot):
        issues.append("VAD armament depots must add capacity before the arms factory")

    expected_vad_ai_plans = {
        "ADISCORD_vorkerland_vad_vlad_core_plan": (
            "WRK_Vlad_Petrichev",
            WARTIME_ROUTE_FOCUSES["VAD"][0:2]
            + (
                "VAD_establish_mobile_headquarters",
                "VAD_inventory_eastern_works",
                "VAD_restore_crown_commissions",
                "VAD_invite_sol_delegation",
                "VAD_reconstitute_district_guard",
                "VAD_standardize_district_logistics",
                "VAD_bind_officers_to_chancery",
                "VAD_dispatch_solland_liaison_mission",
                "VAD_assemble_joint_general_staff",
                "VAD_reopen_armament_depots",
                "VAD_settle_restoration_authority",
                "VAD_balance_council_and_command",
            ),
            False,
        ),
        "ADISCORD_vorkerland_vad_joint_core_plan": (
            "WRK_VAD_Joint_Council",
            (
                "VAD_proclaim_joint_charter",
                "VAD_form_field_commandantures",
                "VAD_establish_mobile_headquarters",
                "VAD_inventory_eastern_works",
                "VAD_guarantee_worker_committees",
                "VAD_invite_sol_delegation",
                "VAD_reconstitute_district_guard",
                "VAD_standardize_district_logistics",
                "VAD_ratify_joint_command",
                "VAD_dispatch_solland_liaison_mission",
                "VAD_assemble_joint_general_staff",
                "VAD_reopen_armament_depots",
                "VAD_settle_restoration_authority",
                "VAD_balance_council_and_command",
            ),
            False,
        ),
        "ADISCORD_vorkerland_vad_vlad_depth_plan": (
            "WRK_Vlad_Petrichev",
            tuple(VAD_OPTIONAL_WARTIME_FOCUSES[index] for index in (0, 1, 2, 6, 7, 8))
            + VAD_LATE_WAR_BRIDGE_FOCUSES,
            True,
        ),
        "ADISCORD_vorkerland_vad_joint_depth_plan": (
            "WRK_VAD_Joint_Council",
            tuple(VAD_OPTIONAL_WARTIME_FOCUSES[index] for index in (3, 4, 5, 6, 7, 8))
            + VAD_LATE_WAR_BRIDGE_FOCUSES,
            True,
        ),
    }
    for plan_id, (leader, expected_focuses, is_depth) in expected_vad_ai_plans.items():
        definitions = _blocks(vad_ai_plans, plan_id)
        if len(definitions) != 1:
            issues.append(f"VAD AI plan {plan_id} must have one definition")
            continue
        plan = definitions[0]
        ai_focus_blocks = _blocks(plan, "ai_national_focuses")
        actual_focuses = (
            tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", ai_focus_blocks[0]))
            if len(ai_focus_blocks) == 1
            else ()
        )
        if actual_focuses != expected_focuses:
            issues.append(
                f"VAD AI plan {plan_id} focus order {actual_focuses} != {expected_focuses}"
            )
        for token in (
            "allowed = { original_tag = VAD }",
            "tag = VAD",
            "is_ai = yes",
            f"character = {leader}",
        ):
            if token not in plan:
                issues.append(f"VAD AI plan {plan_id} lacks {token}")
        capstone_gate = (
            "has_country_flag = ADISCORD_vorkerland_focus_vad_central_war_unlocked"
        )
        if is_depth:
            if capstone_gate not in plan or "factor = 4" not in plan:
                issues.append(f"VAD depth AI plan {plan_id} lacks post-capstone priority")
            enable_blocks = _blocks(plan, "enable")
            if len(enable_blocks) != 1:
                issues.append(f"VAD depth AI plan {plan_id} must define one enable block")
            elif (
                "ADISCORD_vorkerland_wkr_solyarino_intervention_active"
                in enable_blocks[0]
            ):
                issues.append(
                    f"VAD depth AI plan {plan_id} must remain enabled while the WKR "
                    "Solarino lane is active"
                )
        elif f"NOT = {{ {capstone_gate} }}" not in plan or "factor = 3" not in plan:
            issues.append(f"VAD core AI plan {plan_id} lacks pre-capstone priority")

    if len(TVA_OPTIONAL_WARTIME_FOCUSES) != 10:
        issues.append(
            "TVA optional depth must contain exactly ten definitions, "
            f"found {len(TVA_OPTIONAL_WARTIME_FOCUSES)}"
        )
    tva_optional_prerequisites = {
        "TVA_unattended_shifts": {"TVA_optimize_for_throughput"},
        "TVA_delegate_fire_plans_to_board": {"TVA_delegate_to_algorithmic_board"},
        "TVA_bunker_specialist_cadres": {"TVA_protect_irreplaceable_specialists"},
        "TVA_standardize_assault_teams": {"TVA_raise_technical_battalions"},
        "TVA_network_observation_posts": {"TVA_test_remote_fire_control"},
        "TVA_mandate_modular_repair": {"TVA_test_adaptive_logistics"},
        "TVA_print_interchangeable_repair_modules": {
            "TVA_unattended_shifts",
            "TVA_delegate_fire_plans_to_board",
            "TVA_bunker_specialist_cadres",
            "TVA_standardize_assault_teams",
            "TVA_network_observation_posts",
            "TVA_mandate_modular_repair",
        },
        "TVA_preposition_switching_crews": {
            "TVA_print_interchangeable_repair_modules"
        },
        "TVA_cross_validate_trial_logs": {"TVA_preposition_switching_crews"},
        "TVA_authorize_iteration_two": {"TVA_cross_validate_trial_logs"},
    }
    tva_optional_source = "\n".join(
        blocks.get(focus_id, "") for focus_id in TVA_OPTIONAL_WARTIME_FOCUSES
    )
    for focus_id in TVA_OPTIONAL_WARTIME_FOCUSES:
        block = blocks.get(focus_id, "")
        actual_prerequisites = _prerequisites(block)
        if actual_prerequisites != tva_optional_prerequisites[focus_id]:
            issues.append(
                f"{focus_id} optional prerequisites {sorted(actual_prerequisites)} != "
                f"{sorted(tva_optional_prerequisites[focus_id])}"
            )
        x_match = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block)
        y_match = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block)
        position = (
            int(x_match.group(1)) if x_match else None,
            int(y_match.group(1)) if y_match else None,
        )
        if position != TVA_OPTIONAL_POSITIONS[focus_id]:
            issues.append(
                f"{focus_id} position {position} != {TVA_OPTIONAL_POSITIONS[focus_id]}"
            )
        cost = _focus_cost(block)
        if cost != TVA_OPTIONAL_COSTS[focus_id]:
            issues.append(
                f"{focus_id} cost {cost} != {TVA_OPTIONAL_COSTS[focus_id]}"
            )
        payload = _postwar_reward_categories(block)
        if "country_event" in block:
            payload.add("event")
        minimum_payload = 3 if cost <= 3 else 5
        if len(payload) < minimum_payload:
            issues.append(
                f"TVA optional focus {focus_id} cost {cost} has only "
                f"{len(payload)} substantive reward classes {sorted(payload)}; "
                f"needs {minimum_payload}"
            )
        allow = _allow_branch(block)
        for identity_token in (
            "has_government = technocracy",
            "has_country_leader = { character = TVA_Dorian_Worx ruling_only = yes }",
        ):
            if identity_token not in allow:
                issues.append(f"{focus_id} lacks Worx identity gate {identity_token}")
        bypasses = _blocks(block, "bypass")
        if len(bypasses) == 1:
            bypass_flags = re.findall(
                r"\bhas_country_flag\s*=\s*([A-Za-z0-9_]+)", bypasses[0]
            )
            if len(bypass_flags) != 1 or "central_war_unlocked" in bypasses[0]:
                issues.append(
                    f"{focus_id} bypass must contain only its fresh-campaign idempotency flag"
                )
    if len(set(TVA_OPTIONAL_POSITIONS.values())) != len(TVA_OPTIONAL_POSITIONS):
        issues.append("TVA optional depth contains overlapping authored coordinates")
    if set(TVA_OPTIONAL_WARTIME_FOCUSES) & set(
        _prerequisites(blocks.get("TVA_close_operational_loop", ""))
    ):
        issues.append("TVA central capstone must not depend on optional depth")
    convergence_groups = Counter(
        frozenset(re.findall(r"\bfocus\s*=\s*([A-Za-z0-9_]+)", prerequisite))
        for prerequisite in _blocks(
            blocks.get("TVA_print_interchangeable_repair_modules", ""), "prerequisite"
        )
    )
    expected_convergence_groups = Counter(
        (
            frozenset(TVA_OPTIONAL_WARTIME_FOCUSES[0:3]),
            frozenset(TVA_OPTIONAL_WARTIME_FOCUSES[3:6]),
        )
    )
    if convergence_groups != expected_convergence_groups:
        issues.append("TVA repair-module convergence must require one metric and one field trial")
    for outcome_index, expected_optional in enumerate(TVA_OPTIONAL_OUTCOME_FOCUSES):
        reachable = _reachable_tva_optional_outcome(blocks, outcome_index)
        if reachable != set(expected_optional):
            issues.append(
                f"TVA optional outcome {outcome_index + 1} reaches "
                f"{sorted(reachable)} != {sorted(expected_optional)}"
            )
        route_cost = sum(TVA_OPTIONAL_COSTS[focus_id] for focus_id in reachable)
        if len(reachable) != 6 or route_cost not in {18, 19}:
            issues.append(
                f"TVA optional outcome {outcome_index + 1} must have six focuses "
                f"and 18/19 cost units, found {len(reachable)} and {route_cost}"
            )
    for token in (
        "declare_war_on",
        "create_wargoal",
        "annex_country",
        "transfer_state",
        "ADISCORD_vorkerland_phase_worx_client_administration",
        "ADISCORD_vorkerland_phase_worx_fragmentation",
        "ADISCORD_vorkerland_tva_field_directorate_3",
        "Tower of Unity",
        "tower_of_unity",
    ):
        if token in tva_optional_source:
            issues.append(f"TVA optional depth contains forbidden payload {token}")
    for focus_id, (idea_id, days) in TVA_OPTIONAL_TIMED_IDEAS.items():
        reward = f"add_timed_idea = {{ idea = {idea_id} days = {days} }}"
        if blocks.get(focus_id, "").count(reward) != 1:
            issues.append(f"{focus_id} must grant the bounded {days}-day spirit {idea_id}")
        definitions = _blocks(collapse_ideas, idea_id)
        if len(definitions) != 1:
            issues.append(f"TVA optional spirit {idea_id} must have one definition")
        elif any(
            token not in definitions[0]
            for token in (
                "allowed = { always = no }",
                "allowed_civil_war = { always = yes }",
                "removal_cost = -1",
                "ai_will_do = { factor = 0 }",
            )
        ):
            issues.append(f"TVA optional spirit {idea_id} lacks bounded idea guards")
    iteration = blocks.get("TVA_authorize_iteration_two", "")
    second_protocol_reward = (
        "add_timed_idea = { idea = "
        f"{RETIRED_WORX_SECOND_PROTOCOL_IDEA} days = 120 }}"
    )
    if iteration.count(second_protocol_reward) != 1:
        issues.append("TVA iteration two must grant exactly one 120-day second protocol")
    if "field_directorate_3" in iteration:
        issues.append("TVA iteration two must not grant field directorate level 3")
    trial_log_focus = blocks.get("TVA_cross_validate_trial_logs", "")
    if trial_log_focus.count(
        "country_event = { id = ADISCORD_vorkerland_claimant.24 hours = 1 }"
    ) != 1:
        issues.append("TVA trial-log cross-validation must call claimant.24 exactly once")

    core_plan_definitions = _blocks(
        tva_ai_plans, "ADISCORD_vorkerland_tva_experimental_core_plan"
    )
    if len(core_plan_definitions) != 1:
        issues.append("TVA experimental core AI plan must have one definition")
    else:
        core_plan = core_plan_definitions[0]
        core_focus_blocks = _blocks(core_plan, "ai_national_focuses")
        actual_core_focuses = (
            tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", core_focus_blocks[0]))
            if len(core_focus_blocks) == 1
            else ()
        )
        expected_core_focuses = (
            "TVA_codify_utilitarian_directorate",
            "TVA_publish_operational_metrics",
            "TVA_deploy_field_laboratories",
            "TVA_select_trial_protocol",
        )
        if actual_core_focuses != expected_core_focuses:
            issues.append(
                f"TVA experimental core AI focus order {actual_core_focuses} != "
                f"{expected_core_focuses}"
            )
        for token in (
            "allowed = { original_tag = TVA }",
            "tag = TVA",
            "is_ai = yes",
            "factor = 3",
        ):
            if token not in core_plan:
                issues.append(f"TVA experimental core AI plan lacks {token}")
    for plan_id, metric_flag, trial_flag, expected_focuses in TVA_OPTIONAL_AI_PLANS:
        definitions = _blocks(tva_ai_plans, plan_id)
        if len(definitions) != 1:
            issues.append(f"TVA depth AI plan {plan_id} must have one definition")
            continue
        plan = definitions[0]
        ai_focus_blocks = _blocks(plan, "ai_national_focuses")
        actual_focuses = (
            tuple(re.findall(r"(?m)^\s*([A-Za-z0-9_]+)\s*$", ai_focus_blocks[0]))
            if len(ai_focus_blocks) == 1
            else ()
        )
        if actual_focuses != expected_focuses:
            issues.append(
                f"TVA depth AI plan {plan_id} focus order {actual_focuses} != "
                f"{expected_focuses}"
            )
        for token in (
            "allowed = { original_tag = TVA }",
            "tag = TVA",
            "is_ai = yes",
            f"has_country_flag = {metric_flag}",
            f"has_country_flag = {trial_flag}",
            "NOT = { has_country_flag = ADISCORD_vorkerland_focus_tva_iteration_two_authorized }",
            "factor = 5",
        ):
            if token not in plan:
                issues.append(f"TVA depth AI plan {plan_id} lacks {token}")

    for focus_ids, identity_tokens in WARTIME_ROUTE_IDENTITIES:
        for focus_id in focus_ids:
            allow = _allow_branch(blocks.get(focus_id, ""))
            for token in identity_tokens:
                if token not in allow:
                    issues.append(f"{focus_id} route gate lacks exact identity token {token}")

    tva_root = _allow_branch(blocks.get("TVA_codify_utilitarian_directorate", ""))
    for token in (
        "has_government = technocracy",
        "has_country_leader = { character = TVA_Dorian_Worx ruling_only = yes }",
    ):
        if token not in tva_root:
            issues.append(f"TVA wartime programme root lacks exact Worx identity token {token}")

    mex_pairs = (
        ("WRK_convene_council_of_republics", "WRK_inventory_emergency_stores"),
        ("VAD_open_continuity_registers", "VAD_drill_district_guard"),
        ("TVA_optimize_for_throughput", "TVA_protect_irreplaceable_specialists"),
        ("TVA_optimize_for_throughput", "TVA_delegate_to_algorithmic_board"),
        ("TVA_delegate_to_algorithmic_board", "TVA_protect_irreplaceable_specialists"),
        ("TVA_raise_technical_battalions", "TVA_test_remote_fire_control"),
        ("TVA_raise_technical_battalions", "TVA_test_adaptive_logistics"),
        ("TVA_test_remote_fire_control", "TVA_test_adaptive_logistics"),
    )
    for left, right in mex_pairs:
        if f"focus = {right}" not in "\n".join(_blocks(blocks.get(left, ""), "mutually_exclusive")):
            issues.append(f"{left} must be mutually exclusive with {right}")
        if f"focus = {left}" not in "\n".join(_blocks(blocks.get(right, ""), "mutually_exclusive")):
            issues.append(f"{right} must be mutually exclusive with {left}")

    for focus_id in (
        "TVA_reroute_city_grid",
        "TVA_deploy_field_laboratories",
        "TVA_seal_the_approaches",
        "TVA_issue_emergency_output_norms",
        "TVA_build_mobile_repair_trains",
        "TVA_harden_switching_stations",
    ):
        if "mutually_exclusive" in blocks.get(focus_id, ""):
            issues.append(f"Worx military/industrial programme {focus_id} must remain jointly completable")

    for tag, (capstone, flag) in CENTRAL_CAPSTONES.items():
        capstone_block = blocks.get(capstone, "")
        if f"set_country_flag = {flag}" not in capstone_block:
            issues.append(f"{capstone} must set gameplay hook {flag}")
        if capstone_block.count(f"set_country_flag = {CENTRAL_PREPARED_FLAG}") != 1:
            issues.append(f"{capstone} must set the shared central preparation gate exactly once")
        for token in (
            "add_command_power = 10",
            "add_war_support = 0.02",
            "army_experience = 5",
            "amount = 75",
            "country_event = { id = ADISCORD_vorkerland_claimant.",
        ):
            if token not in capstone_block:
                issues.append(f"{capstone} is missing compact capstone payload {token}")

    for tag, (capstone, expected_groups) in WARTIME_TERMINALS.items():
        prerequisite_blocks = _blocks(blocks.get(capstone, ""), "prerequisite")
        actual = Counter(
            frozenset(re.findall(r"\bfocus\s*=\s*([A-Za-z0-9_]+)", prerequisite))
            for prerequisite in prerequisite_blocks
        )
        expected = Counter(expected_groups)
        if actual != expected:
            issues.append(f"{tag} capstone {capstone} must AND-converge political/military/industrial terminals")

    for tag, hook in RETREAT_HOOKS.items():
        route_source = "\n".join(blocks.get(focus_id, "") for focus_id in WARTIME_ROUTE_FOCUSES[tag])
        if route_source.count(f"set_country_flag = {hook}") != 1:
            issues.append(f"{tag} military terminal must set retreat hook {hook} exactly once")
        if hook not in focus_decisions:
            issues.append(f"{tag} retreat hook {hook} is not consumed by visible decisions")

    reward_classes = {
        "political": ("add_political_power", "add_stability"),
        "military": ("army_experience", "add_command_power", "add_manpower", "add_war_support"),
        "economic": ("add_equipment_to_stockpile", "add_building_construction", "add_timed_idea"),
    }
    for tag, route_ids in WARTIME_ROUTE_FOCUSES.items():
        route_source = "\n".join(blocks.get(focus_id, "") for focus_id in route_ids)
        for reward_class, tokens in reward_classes.items():
            if not any(token in route_source for token in tokens):
                issues.append(f"{tag} wartime route lacks a {reward_class} reward")

    mobile_repair = blocks.get("TVA_build_mobile_repair_trains", "")
    mobile_repair_reward = (
        f"add_timed_idea = {{ idea = {MOBILE_REPAIR_IDEA} days = 35 }}"
    )
    if mobile_repair.count(mobile_repair_reward) != 1:
        issues.append("TVA mobile repair trains must grant its concrete 35-day repair spirit")

    for focus_id, (idea_id, days) in WORX_WARTIME_TIMED_IDEAS.items():
        reward = f"add_timed_idea = {{ idea = {idea_id} days = {days} }}"
        if blocks.get(focus_id, "").count(reward) != 1:
            issues.append(f"{focus_id} must grant the bounded {days}-day spirit {idea_id}")
        definitions = _blocks(collapse_ideas, idea_id)
        if len(definitions) != 1:
            issues.append(f"Worx wartime spirit {idea_id} must have one definition")

    adaptive_reward = (
        f"add_timed_idea = {{ idea = {WORX_ADAPTIVE_LOGISTICS_IDEA} days = 90 }}"
    )
    if blocks.get("TVA_test_adaptive_logistics", "").count(adaptive_reward) != 1:
        issues.append("TVA adaptive-logistics trial must grant its bounded 90-day spirit")
    if len(_blocks(collapse_ideas, WORX_ADAPTIVE_LOGISTICS_IDEA)) != 1:
        issues.append("Worx adaptive-logistics trial spirit must have one definition")

    close_loop = blocks.get("TVA_close_operational_loop", "")
    if "ADISCORD_vorkerland_tva_field_directorate" in close_loop:
        issues.append(
            "TVA operational loop must not repeat the mandatory administration upgrade"
        )
    if "TVA_standardize_emergency_administration" not in _prerequisites(close_loop):
        issues.append(
            "TVA operational loop must inherit level two from emergency administration"
        )
    standardize = blocks.get("TVA_standardize_emergency_administration", "")
    if standardize.count("else = { add_war_support = 0.01 }") != 1:
        issues.append(
            "TVA emergency administration must reward an already upgraded directorate"
        )
    tva_formation = _blocks(phase_effects, "ADISCORD_vorkerland_form_wrk_from_tva")
    if len(tva_formation) != 1 or tva_formation[0].count(
        "add_ideas = ADISCORD_vorkerland_tva_field_directorate_3"
    ) != 1:
        issues.append("terminal TVA formation effect must uniquely award field directorate level 3")
    measurable_republic = blocks.get("WRK_utilitarian_build_measurable_republic", "")
    for idea_id in WORX_FIELD_DIRECTORATE_IDEAS:
        removals = re.findall(
            rf"(?m)^\s*remove_ideas\s*=\s*{re.escape(idea_id)}\s*$",
            measurable_republic,
        )
        if len(removals) != 1:
            issues.append(
                f"technocratic settlement must consolidate inherited field idea {idea_id}"
            )

    public_utilities = blocks.get(
        "WRK_utilitarian_prioritize_public_utilities", ""
    )
    if public_utilities.count("limit = { controls_state = 37 }") != 1:
        issues.append("WRK public utilities must target controlled state 37 exactly once")
    if public_utilities.count("add_extra_state_shared_building_slots = 1") != 1:
        issues.append("WRK public utilities must create one live energy building slot")
    if public_utilities.count(
        "type = energy_infrastructure level = 1 instant_build = yes"
    ) != 1:
        issues.append("WRK public utilities must build exactly one energy infrastructure")

    sol_hook = "ADISCORD_vorkerland_focus_vad_sol_invitation_intent"
    sol_focus = blocks.get("VAD_invite_sol_delegation", "")
    if f"set_country_flag = {sol_hook}" not in sol_focus:
        issues.append("wartime VAD SOL policy focus must set its outcome-dependent intent hook")
    if source.count(f"set_country_flag = {sol_hook}") != 1:
        issues.append("VAD SOL invitation intent hook must have one focus owner")

    vla_hook = "ADISCORD_vorkerland_focus_wkr_vla_invitation_intent"
    vla_focus = blocks.get("WKR_open_free_republics_channel", "")
    if f"set_country_flag = {vla_hook}" not in vla_focus:
        issues.append("expanded WKR diplomacy focus must expose the VLA invitation intent")
    for hook in (sol_hook, vla_hook):
        if hook not in diplomacy_decisions:
            issues.append(f"diplomacy intent {hook} is not consumed by a visible decision")
    for accepted_flag in (
        "ADISCORD_vorkerland_wkr_vla_alliance_accepted",
        "ADISCORD_vorkerland_vad_sol_alliance_accepted",
    ):
        if accepted_flag not in focus_decisions:
            issues.append(f"allied support decisions lack accepted-policy gate {accepted_flag}")

    postwar_source = "\n".join(
        blocks.get(focus_id, "")
        for focus_ids in POSTWAR_ROUTE_FOCUSES.values()
        for focus_id in focus_ids
    )

    for route_flag, focus_ids in POSTWAR_ROUTE_FOCUSES.items():
        if len(focus_ids) != 10:
            issues.append(
                f"postwar route {route_flag} must contain ten authored definitions, "
                f"found {len(focus_ids)}"
            )
        terminal_id = POSTWAR_ROUTE_TERMINALS[route_flag]
        if _focus_cost(blocks.get(terminal_id, "")) != 5:
            issues.append(
                f"postwar settlement {terminal_id} must remain a bundled cost-5 capstone"
            )
        paths = _postwar_completion_paths(blocks, focus_ids, terminal_id)
        if len(paths) != 2:
            issues.append(
                f"postwar route {route_flag} must expose two terminal policy paths, "
                f"found {len(paths)}"
            )
        if paths and set().union(*paths) != set(focus_ids):
            missing = sorted(set(focus_ids) - set().union(*paths))
            issues.append(
                f"postwar route {route_flag} has nodes outside every terminal path {missing}"
            )
        for path in paths:
            if len(path) != 9:
                issues.append(
                    f"postwar route {route_flag} terminal path must complete nine focuses, "
                    f"found {len(path)}"
                )
            cost_units = sum(_focus_cost(blocks.get(focus_id, "")) for focus_id in path)
            if not 27 <= cost_units <= 32:
                issues.append(
                    f"postwar route {route_flag} path costs {cost_units} units "
                    f"({cost_units * 7} days), expected 189-224 days"
                )

        positions: dict[tuple[int, int], str] = {}
        route_set = set(focus_ids)
        for focus_id in focus_ids:
            block = blocks.get(focus_id, "")
            x_match = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", block)
            y_match = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", block)
            if x_match and y_match:
                position = (int(x_match.group(1)), int(y_match.group(1)))
                if position in positions:
                    issues.append(
                        f"postwar focuses {positions[position]} and {focus_id} overlap "
                        f"at {position}"
                    )
                positions[position] = focus_id
                for prerequisite in _prerequisites(block) & route_set:
                    parent = blocks.get(prerequisite, "")
                    parent_x = re.search(r"(?m)^\s*x\s*=\s*(-?\d+)\s*$", parent)
                    parent_y = re.search(r"(?m)^\s*y\s*=\s*(-?\d+)\s*$", parent)
                    if parent_x and parent_y:
                        dx = abs(position[0] - int(parent_x.group(1)))
                        dy = position[1] - int(parent_y.group(1))
                        if not 1 <= dy <= 2 or dx > 2:
                            issues.append(
                                f"postwar edge {prerequisite}->{focus_id} is not compact "
                                f"(dx={dx}, dy={dy})"
                            )

            cost = _focus_cost(block)
            payload = _postwar_reward_categories(block)
            minimum_payload = 2 if cost <= 2 else 3 if cost <= 4 else 4
            if len(payload) < minimum_payload:
                issues.append(
                    f"postwar focus {focus_id} cost {cost} has only "
                    f"{len(payload)} substantive reward classes {sorted(payload)}; "
                    f"needs {minimum_payload}"
                )
            if cost >= 5 and focus_id not in POSTWAR_SETTLEMENT_IDEAS:
                issues.append(
                    f"long postwar focus {focus_id} cost {cost} is not a major settlement"
                )

    for left, right in POSTWAR_POLICY_CHOICE_PAIRS:
        left_block = blocks.get(left, "")
        right_block = blocks.get(right, "")
        if right not in _mutually_exclusive_focuses(left_block):
            issues.append(f"postwar policy focus {left} must exclude {right}")
        if left not in _mutually_exclusive_focuses(right_block):
            issues.append(f"postwar policy focus {right} must exclude {left}")
        for focus_id, block in ((left, left_block), (right, right_block)):
            ai = _blocks(block, "ai_will_do")
            if len(ai) != 1 or not _blocks(ai[0], "modifier"):
                issues.append(
                    f"postwar policy choice {focus_id} needs contextual AI weighting"
                )

    for hook in POSTWAR_HOOKS:
        if postwar_source.count(f"set_country_flag = {hook}") != 1:
            issues.append(f"postwar hook {hook} must have exactly one route focus owner")

    for capstone_id, (settlement_idea, incompatible_ideas) in POSTWAR_SETTLEMENT_IDEAS.items():
        capstone = blocks.get(capstone_id, "")
        if capstone.count(f"add_ideas = {settlement_idea}") != 1:
            issues.append(f"postwar capstone {capstone_id} must add lasting idea {settlement_idea}")
        if f"remove_ideas = {settlement_idea}" in capstone:
            issues.append(f"postwar capstone {capstone_id} must not remove its own settlement idea")
        for incompatible_idea in incompatible_ideas:
            if capstone.count(f"remove_ideas = {incompatible_idea}") != 1:
                issues.append(
                    f"postwar capstone {capstone_id} must replace incompatible idea "
                    f"{incompatible_idea}"
                )

        idea_definitions = _blocks(collapse_ideas, settlement_idea)
        if len(idea_definitions) != 1:
            issues.append(
                f"lasting postwar idea {settlement_idea} must have one definition, "
                f"found {len(idea_definitions)}"
            )
        elif not re.search(r"\bremoval_cost\s*=\s*-1\b", idea_definitions[0]):
            issues.append(f"lasting postwar idea {settlement_idea} must be non-removable")

    worx_capstone = blocks.get("WRK_utilitarian_build_measurable_republic", "")
    for focus_id, idea_id in WORX_POSTWAR_PROVISIONAL_IDEAS.items():
        if blocks.get(focus_id, "").count(f"add_ideas = {idea_id}") != 1:
            issues.append(f"{focus_id} must install concrete provisional institution {idea_id}")
        exact_removals = re.findall(
            rf"(?m)^\s*remove_ideas\s*=\s*{re.escape(idea_id)}\s*$",
            worx_capstone,
        )
        if len(exact_removals) != 1:
            issues.append(f"Worx capstone must consolidate provisional institution {idea_id}")
        definitions = _blocks(collapse_ideas, idea_id)
        if len(definitions) != 1:
            issues.append(f"Worx provisional institution {idea_id} must have one definition")
        elif not re.search(r"\bremoval_cost\s*=\s*-1\b", definitions[0]):
            issues.append(f"Worx provisional institution {idea_id} must be focus-controlled")

    for capstone_id, installers in POSTWAR_TRANSITIONAL_IDEAS.items():
        capstone = blocks.get(capstone_id, "")
        for focus_id, idea_id in installers.items():
            if blocks.get(focus_id, "").count(f"add_ideas = {idea_id}") != 1:
                issues.append(
                    f"postwar stage {focus_id} must install transitional idea {idea_id}"
                )
            if capstone.count(f"remove_ideas = {idea_id}") != 1:
                issues.append(
                    f"postwar capstone {capstone_id} must consolidate transitional idea {idea_id}"
                )
            definitions = _blocks(collapse_ideas, idea_id)
            if len(definitions) != 1:
                issues.append(f"postwar transitional idea {idea_id} must have one definition")
            elif not re.search(r"\bremoval_cost\s*=\s*-1\b", definitions[0]):
                issues.append(f"postwar transitional idea {idea_id} must be focus-controlled")

    expedition_definitions = _blocks(collapse_ideas, IVANLAND_EXPEDITIONARY_IDEA)
    if len(expedition_definitions) != 1:
        issues.append(f"Ivanland expedition spirit {IVANLAND_EXPEDITIONARY_IDEA} must have one definition")
    else:
        expedition = expedition_definitions[0]
        for token in (
            "army_attack_factor = 0.08",
            "army_org_regain = 0.08",
            "planning_speed = 0.10",
            "supply_consumption_factor = -0.08",
        ):
            if token not in expedition:
                issues.append(f"Ivanland expedition spirit is missing bounded modifier {token}")

    mobile_idea_definitions = _blocks(collapse_ideas, MOBILE_REPAIR_IDEA)
    if len(mobile_idea_definitions) != 1:
        issues.append(
            f"mobile repair spirit {MOBILE_REPAIR_IDEA} must have one definition, "
            f"found {len(mobile_idea_definitions)}"
        )

    for idea_id in LAND_REPAIR_IDEAS:
        definitions = _blocks(collapse_ideas, idea_id)
        if len(definitions) != 1:
            issues.append(f"land repair spirit {idea_id} must have one definition")
            continue
        if definitions[0].count("industry_repair_factor = 0.20") != 1:
            issues.append(f"land repair spirit {idea_id} must repair industry at +20 percent")
        if re.search(r"\brepair_speed_factor\s*=", definitions[0]):
            issues.append(f"land repair spirit {idea_id} must not use the ship repair modifier")

    core_unlock = "ADISCORD_vorkerland_focus_postwar_core_decisions_unlocked"
    if postwar_source.count(f"set_country_flag = {core_unlock}") != 3:
        issues.append("each postwar route must set the common core-decision unlock exactly once")
    for focus_id in POSTWAR_CORE_UNLOCK_FOCUSES:
        if f"set_country_flag = {core_unlock}" not in blocks.get(focus_id, ""):
            issues.append(f"{focus_id} must unlock visible postwar core decisions")
    for decision_id in CORE_DECISIONS:
        decision_blocks = _blocks(focus_decisions, decision_id)
        if len(decision_blocks) != 1:
            issues.append(f"core decision {decision_id} must have one public definition")
        elif f"has_country_flag = {core_unlock}" not in decision_blocks[0]:
            issues.append(f"core decision {decision_id} is not gated by its focus unlock")

    # Military victory is controller-owned. Postwar branches must be reachable
    # even if the showdown focus was canceled by a fast phase transition.
    for focus_ids in POSTWAR_ROUTE_FOCUSES.values():
        root = blocks.get(focus_ids[0], "")
        if _prerequisites(root):
            issues.append(f"postwar root {focus_ids[0]} must not require a wartime focus")
    fortification_foci = {
        "WKR": ("WKR_authorize_retreat_levies", 32, 6713),
        "VAD": ("VAD_assemble_joint_general_staff", 75, 6192),
        "TVA": ("TVA_seal_the_approaches", 36, 12227),
    }
    for tag, (focus_id, state, province) in fortification_foci.items():
        fortify = blocks.get(focus_id, "")
        pattern = (
            rf"limit\s*=\s*\{{\s*controls_state\s*=\s*{state}\s*\}}"
            rf"\s*{state}\s*=\s*\{{\s*add_building_construction\s*=\s*\{{"
            rf"\s*type\s*=\s*bunker\s+level\s*=\s*1\s+instant_build\s*=\s*yes"
            rf"\s+province\s*=\s*{province}\s*\}}\s*\}}"
        )
        if not re.search(pattern, fortify):
            issues.append(f"{focus_id} lacks bounded {tag} redoubt {state}/{province}")
        if fortify.count("type = bunker level = 1") != 1:
            issues.append(f"{focus_id} must contain exactly one level-one redoubt")

    forbidden_effects = (
        "declare_war_on",
        "start_civil_war",
        "create_wargoal",
        "annex_country",
        "puppet",
        "set_autonomy",
        "transfer_state",
        "add_core_of",
        "remove_core_of",
        "create_unit",
        "release =",
        "add_offsite_building",
        "set_global_flag",
        "ADISCORD_vorkerland_set_phase_",
        "every_country",
        "random_country",
        "on_monthly",
        "monthly_pulse",
    )
    for token in forbidden_effects:
        if token in source:
            issues.append(f"lifecycle focus tree contains forbidden controller/diplomacy effect {token}")
    if re.search(r"lucas", source, re.IGNORECASE):
        issues.append("lifecycle focus content must not depend on Lucas-specific state")

    focus_event_references = re.findall(
        r"\bcountry_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)", source
    )
    unexpected_focus_events = sorted(set(focus_event_references) - set(CLAIMANT_FOCUS_EVENT_IDS))
    if unexpected_focus_events:
        issues.append(f"wartime focuses reference unowned events {unexpected_focus_events}")
    missing_focus_events = sorted(set(CLAIMANT_FOCUS_EVENT_IDS) - set(focus_event_references))
    if missing_focus_events:
        issues.append(f"claimant focus event hooks are missing {missing_focus_events}")
    if "news_event" in source:
        issues.append("focus tree must route news through bounded claimant capstone events")

    event_definitions = tuple(
        block
        for assignment in ("country_event", "news_event")
        for block in _blocks(claimant_events, assignment)
        if re.search(r"(?m)^\s*title\s*=", block)
    )
    defined_event_ids = [
        match.group(1)
        for block in event_definitions
        if (match := re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_.]+)\s*$", block))
    ]
    expected_event_ids = [*CLAIMANT_FOCUS_EVENT_IDS, *CLAIMANT_NEWS_EVENT_IDS]
    if defined_event_ids != expected_event_ids:
        issues.append(f"claimant event definitions differ from the owned manifest: {defined_event_ids}")
    if claimant_events.count("add_namespace = ADISCORD_vorkerland_claimant") != 1:
        issues.append("claimant events must declare their owned namespace exactly once")
    if "has_command_power" in claimant_events:
        issues.append("claimant events use invalid trigger has_command_power; use command_power")
    if len(event_definitions) != len(expected_event_ids):
        issues.append("claimant event file has missing or extra event definitions")
    if claimant_events.count("fire_only_once = yes") != len(expected_event_ids):
        issues.append("every claimant focus/news event must be one-shot")
    event_blocks_by_id = {
        match.group(1): block
        for block in event_definitions
        if (match := re.search(r"(?m)^\s*id\s*=\s*([A-Za-z0-9_.]+)\s*$", block))
    }
    for event_id, expected_options in {
        "ADISCORD_vorkerland_claimant.4": 4,
        "ADISCORD_vorkerland_claimant.13": 4,
        "ADISCORD_vorkerland_claimant.14": 2,
        "ADISCORD_vorkerland_claimant.23": 3,
        "ADISCORD_vorkerland_claimant.24": 3,
    }.items():
        options = _blocks(event_blocks_by_id.get(event_id, ""), "option")
        if len(options) != expected_options:
            issues.append(f"{event_id} must expose {expected_options} outcome-specific options")
    trial_event = event_blocks_by_id.get("ADISCORD_vorkerland_claimant.23", "")
    for trial_flag in (
        "ADISCORD_vorkerland_tva_trial_technical_battalions",
        "ADISCORD_vorkerland_tva_trial_remote_fire_control",
        "ADISCORD_vorkerland_tva_trial_adaptive_logistics",
    ):
        if trial_event.count(f"set_country_flag = {trial_flag}") != 1:
            issues.append(f"TVA field-trial event must set {trial_flag} exactly once")
    iteration_event = event_blocks_by_id.get("ADISCORD_vorkerland_claimant.24", "")
    for iteration_flag in (
        "ADISCORD_vorkerland_tva_iteration_audit_precision",
        "ADISCORD_vorkerland_tva_iteration_field_variance",
        "ADISCORD_vorkerland_tva_iteration_production_variance",
    ):
        if iteration_event.count(f"set_country_flag = {iteration_flag}") != 1:
            issues.append(
                f"TVA cross-validation event must set {iteration_flag} exactly once"
            )
    for token in (
        "tag = TVA",
        "has_government = technocracy",
        "has_country_leader = { character = TVA_Dorian_Worx ruling_only = yes }",
    ):
        if token not in iteration_event:
            issues.append(f"TVA cross-validation event lacks trigger {token}")
    solar_settlement_event = event_blocks_by_id.get(
        "ADISCORD_vorkerland_claimant.14", ""
    )
    for token, expected_count in (
        ("ADISCORD_vorkerland_offer_vad_sol_alliance = yes", 2),
        ("ADISCORD_vorkerland_reserve_vad_solar_intervention = yes", 2),
        ("ADISCORD_vorkerland_attempt_vad_solar_intervention = yes", 2),
        ("set_country_flag = ADISCORD_vorkerland_vad_solar_restoration_mandate", 1),
        ("set_country_flag = ADISCORD_vorkerland_vad_solar_compact_mandate", 1),
    ):
        if solar_settlement_event.count(token) != expected_count:
            issues.append(
                f"claimant.14 Solar settlement must contain {token} "
                f"exactly {expected_count} time(s)"
            )
    if solar_settlement_event.count(
        "has_global_flag = ADISCORD_vorkerland_wkr_solyarino_intervention_active"
    ) < 4:
        issues.append("claimant.14 must guard every Solar diplomacy lane against WKR")
    vad_attempt = _blocks(
        diplomacy_effects, "ADISCORD_vorkerland_attempt_vad_solar_intervention"
    )
    vad_verify = _blocks(
        diplomacy_effects, "ADISCORD_vorkerland_verify_vad_solar_intervention"
    )
    if len(vad_attempt) != 1 or vad_attempt[0].count(
        "country_event = { id = ADISCORD_vorkerland_diplomacy.6 days = 1 }"
    ) != 2:
        issues.append("claimant.14 intervention caller lacks the existing one-day verification stage")
    if len(vad_verify) != 1 or any(
        token not in vad_verify[0]
        for token in (
            "set_country_flag = ADISCORD_vorkerland_vad_solar_intervention_verify_retry",
            "country_event = { id = ADISCORD_vorkerland_diplomacy.9 days = 1 }",
            "ADISCORD_vorkerland_clear_failed_vad_solar_intervention = yes",
        )
    ):
        issues.append("claimant.14 intervention caller is not backed by one bounded retry")
    news_references = re.findall(
        r"\bnews_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)", claimant_events
    )
    expected_news_references = Counter(
        event_id for event_id in CLAIMANT_NEWS_EVENT_IDS for _ in range(2)
    )
    if Counter(news_references) != expected_news_references:
        issues.append("claimant capstones must fire each owned news event exactly once")

    event_forbidden_effects = (
        "declare_war_on",
        "start_civil_war",
        "create_wargoal",
        "annex_country",
        "puppet",
        "set_autonomy",
        "transfer_state",
        "add_core_of",
        "remove_core_of",
        "create_unit",
        "release =",
        "set_global_flag",
        "ADISCORD_vorkerland_set_phase_",
        "every_country",
        "random_country",
        "on_monthly",
        "monthly_pulse",
    )
    for token in event_forbidden_effects:
        if token in claimant_events:
            issues.append(f"claimant focus events contain forbidden lifecycle/controller effect {token}")

    bounded_values = {
        "add_political_power": 25.0,
        "add_stability": 0.03,
        "add_manpower": 600.0,
        "army_experience": 10.0,
        "add_command_power": 10.0,
        "add_war_support": 0.03,
    }
    for reward_source_name, reward_source in (
        ("focus", source),
        ("claimant event", claimant_events),
    ):
        for effect, maximum in bounded_values.items():
            for raw in re.findall(rf"\b{effect}\s*=\s*(-?\d+(?:\.\d+)?)", reward_source):
                if float(raw) > maximum:
                    issues.append(
                        f"{reward_source_name} {effect} reward {raw} exceeds maximum {maximum:g}"
                    )
        for raw in re.findall(r"\bamount\s*=\s*(-?\d+(?:\.\d+)?)", reward_source):
            if float(raw) > 150:
                issues.append(f"{reward_source_name} equipment reward {raw} exceeds maximum 150")
    timed_idea_limits = {
        WORX_ADAPTIVE_LOGISTICS_IDEA: 90,
        RETIRED_WORX_SECOND_PROTOCOL_IDEA: 180,
        "ADISCORD_vorkerland_vad_solar_corridor_intelligence": 84,
        "ADISCORD_vorkerland_vad_restoration_columns": 84,
    }
    for idea_id, raw in re.findall(
        r"\badd_timed_idea\s*=\s*\{\s*idea\s*=\s*([A-Za-z0-9_]+)\s+days\s*=\s*(\d+)\s*\}",
        source,
    ):
        maximum = timed_idea_limits.get(idea_id, 70)
        if int(raw) > maximum:
            issues.append(
                f"timed idea {idea_id} duration {raw} exceeds maximum {maximum} days"
            )
    for construction in _blocks(source, "add_building_construction"):
        level = re.search(r"\blevel\s*=\s*(\d+)", construction)
        if not level or int(level.group(1)) != 1:
            issues.append(f"focus construction must add exactly one level: {construction}")

    for bonus in _blocks(source, "add_tech_bonus"):
        amount = re.search(r"\bbonus\s*=\s*(\d+(?:\.\d+)?)", bonus)
        uses = re.search(r"\buses\s*=\s*(\d+)", bonus)
        category = re.search(r"\bcategory\s*=\s*([A-Za-z0-9_]+)", bonus)
        if amount is None or float(amount.group(1)) > 0.50:
            issues.append(f"focus technology bonus exceeds the bounded 50 percent reward: {bonus}")
        if uses is None or int(uses.group(1)) != 1:
            issues.append(f"focus technology bonus must have exactly one use: {bonus}")
        if category is None or category.group(1) not in {
            "industry",
            "electronics",
            "infantry_weapons",
        }:
            issues.append(f"focus technology bonus uses an unsupported category: {bonus}")

    english = read(ENGLISH_LOCALISATION)
    russian = read(RUSSIAN_LOCALISATION)
    english_collapse_loc = read(ENGLISH_COLLAPSE_LOCALISATION)
    russian_collapse_loc = read(RUSSIAN_COLLAPSE_LOCALISATION)
    english_ideas = read(ENGLISH_POSTWAR_IDEA_LOCALISATION)
    russian_ideas = read(RUSSIAN_POSTWAR_IDEA_LOCALISATION)
    if not english.startswith("l_english:\n"):
        issues.append("English lifecycle focus localisation has the wrong header")
    if not russian.startswith("l_russian:\n"):
        issues.append("Russian lifecycle focus localisation has the wrong header")
    if not (ROOT / RUSSIAN_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian lifecycle focus localisation must use UTF-8 BOM")
    if not (ROOT / RUSSIAN_COLLAPSE_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian collapse idea localisation must use UTF-8 BOM")
    if not (ROOT / RUSSIAN_POSTWAR_IDEA_LOCALISATION).read_bytes().startswith(b"\xef\xbb\xbf"):
        issues.append("Russian Vorkerland idea localisation must use UTF-8 BOM")

    expected_keys = expected_localisation_keys()
    for language, text in (("English", english), ("Russian", russian)):
        keys = localisation_keys(text)
        duplicates = sorted(key for key, count in Counter(keys).items() if count != 1)
        if duplicates:
            issues.append(f"{language} localisation has duplicate keys: {duplicates}")
        entries = localisation_entries(text)
        if set(entries) != expected_keys:
            missing = sorted(expected_keys - set(entries))
            extra = sorted(set(entries) - expected_keys)
            issues.append(f"{language} localisation key mismatch: missing={missing}, extra={extra}")
        empty = sorted(key for key, value in entries.items() if not value.strip())
        if empty:
            issues.append(f"{language} localisation has empty values: {empty}")

    referenced_tooltips = set(
        re.findall(
            r"\b(?:custom_effect_tooltip|tooltip)\s*=\s*([A-Za-z0-9_]+)", source
        )
    )
    for language, text in (("English", english), ("Russian", russian)):
        entries = localisation_entries(text)
        missing = sorted(referenced_tooltips - set(entries))
        if missing:
            issues.append(f"{language} localisation lacks exact focus tooltip keys: {missing}")

    expected_idea_keys = {
        key
        for idea_id in POSTWAR_IDEA_LOCALISATION_IDS
        for key in (idea_id, f"{idea_id}_desc")
    }
    for language, text in (("English", english_ideas), ("Russian", russian_ideas)):
        entries = localisation_entries(text)
        if set(entries) != expected_idea_keys:
            missing = sorted(expected_idea_keys - set(entries))
            extra = sorted(set(entries) - expected_idea_keys)
            issues.append(
                f"{language} Vorkerland idea localisation mismatch: missing={missing}, extra={extra}"
            )

    expected_wartime_idea_keys = {
        key
        for idea_id in (
            VAD_WARTIME_IDEA_LOCALISATION_IDS
            | TVA_OPTIONAL_IDEA_LOCALISATION_IDS
        )
        for key in (idea_id, f"{idea_id}_desc")
    }
    for language, text in (
        ("English", english_collapse_loc),
        ("Russian", russian_collapse_loc),
    ):
        entries = localisation_entries(text)
        missing = sorted(expected_wartime_idea_keys - set(entries))
        if missing:
            issues.append(f"{language} claimant wartime idea localisation lacks {missing}")

    character_definitions = _blocks(characters, "TVA_Dorian_Worx")
    if len(character_definitions) != 1:
        issues.append("Dorian Worx must have exactly one character definition")
    else:
        worx = character_definitions[0]
        for token in (
            "ideology = technocracy_ideology",
            "large = GFX_portrait_WRK_Dorian_Worx",
        ):
            if token not in worx:
                issues.append(f"Dorian Worx identity is missing {token}")

    english_focus_entries = localisation_entries(english)
    russian_focus_entries = localisation_entries(russian)
    tva_english = english_focus_entries.get("TVA_codify_utilitarian_directorate", "")
    tva_russian = russian_focus_entries.get("TVA_codify_utilitarian_directorate", "")
    if "Worx" not in tva_english or "Technocratic" not in tva_english:
        issues.append("TVA wartime root must visibly name Worx's technocratic programme in English")
    if "Воркс" not in tva_russian or "технократ" not in tva_russian.lower():
        issues.append("TVA wartime root must visibly name Worx's technocratic programme in Russian")
    if "utilitarian" in tva_english.lower() or "утилитар" in tva_russian.lower():
        issues.append("TVA wartime root must not expose the legacy utilitarian route label")

    return issues


def main() -> int:
    issues = collect_issues()
    if issues:
        print("A-Discord Vorkerland lifecycle focus validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("A-Discord Vorkerland lifecycle focus validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
