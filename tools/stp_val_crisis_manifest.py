"""Canonical identifiers and file ownership for the Stelander Kefreyt crisis."""

HEALTH_STAGE_DAYS = (70, 70, 63, 63)
DEATH_CAMPAIGN_DAY = 267
RESOURCE_STATES = (45, 88)
VAL_STP_INTEL_STATES = (43, 44, 45, 88)
NORTHERN_STATES = {"CIN": 59, "OSF": 61}
NODE_LIMITS = {
    "palace": 2,
    "officers": 3,
    "mountains": 3,
    "market": 2,
    "street": 2,
    "val_channel": 2,
}
LEADERS = {
    "shabrat": ("STP_maksim_shabrat", "chauvinism_ideology", "chauvinism"),
    "sotnikov": ("STP_grigory_sotnikov", "etatism_ideology", "etatism"),
    "hedersett": ("STP_rufus_hedersett", "aristocratic_hedonism", "hedonism"),
}
DECISION_CATEGORIES = (
    "VAL_contract_campaign",
    "NOD_crisis_posture",
    "STP_VAL_war_countdown_category",
)
HEALTH_MISSIONS = {
    "STP_health_stage_1_to_2": (70, "stp_crisis.1"),
    "STP_health_stage_2_to_3": (70, "stp_crisis.2"),
    "STP_health_stage_3_to_4": (63, "stp_crisis.3"),
    "STP_health_stage_4_to_death": (63, "stp_crisis.4"),
}
STP_SPINE_FOCUS_STAGES = {
    1: ("STP_Nectar_of_the_Gods",),
    2: ("STP_The_Man_Who_Bought_The_Sky", "STP_When_The_Guarantee_Died"),
    3: ("STP_The_Dying_Feast", "STP_The_Doctors_Lie"),
    4: (
        "STP_The_Last_Signature",
        "STP_Cancel_The_Morning_Address",
        "STP_A_Glass_Raised_Too_High",
    ),
    5: ("STP_The_Father_Of_Peace_Is_Gone",),
}
STP_CRISIS_FOCUS_STAGES = {
    "STP_Foreign_Guests_At_The_Banquet": 1,
    "STP_Kefreite_Security_Offer": 1,
    "STP_The_Old_Man_On_The_Balcony": 1,
    "STP_The_City_Still_Dances": 1,
    "STP_Count_The_Loyalists": 1,
    "STP_Show_Him_The_Truth": 2,
    "STP_Govern_In_His_Name": 2,
    "STP_The_Valirian_Advisers": 2,
    "STP_Contractors_In_The_Passes": 2,
    "STP_Rumours_In_The_Highlands": 2,
    "STP_The_Lower_Market": 2,
    "STP_The_Party_Was_Not_Born_Here": 3,
    "STP_The_Desert_Watches_The_Snow": 3,
    "STP_The_Mountain_Printing_House": 3,
    "STP_Hunt_The_Mountain_Cells": 3,
    "STP_Steal_The_Black_Ledger": 3,
    "STP_Burn_The_Client_Archives": 3,
    "STP_The_Silent_Mountain_March": 3,
    "STP_One_Last_National_Festival": 3,
    "STP_Turn_The_Young_Officers": 3,
    "STP_Feed_The_Festival_Police": 3,
    "STP_The_Last_Confession": 3,
    "STP_The_Hand_That_Still_Signs": 3,
    "STP_Imported_Freedom": 4,
    "STP_Cut_The_Silk_Leash": 4,
    "STP_Renew_The_Cultural_Mandate": 4,
    "STP_No_Mercenaries_In_Our_Mountains": 4,
    "STP_Sell_The_Highland_Concessions": 4,
    "STP_A_Name_On_The_Walls": 4,
    "STP_Erase_His_Name": 4,
    "STP_The_First_Witness": 4,
    "STP_Silence_The_First_Witness": 4,
    "STP_Lower_Market_Dossiers": 4,
    "STP_The_Port_Must_Smile": 4,
    "STP_Call_For_Shabrat": 4,
    "STP_Seal_The_Western_Wing": 4,
    "STP_The_People_Stop_Singing": 4,
    "STP_Drown_The_Rumours_In_Music": 4,
    "STP_Garrisons_Hesitate": 4,
    "STP_Garrisons_Swear_Loyalty": 4,
}
STP_CRISIS_FOCUS_REWARDS = {
    "STP_Foreign_Guests_At_The_Banquet": "STP_focus_nodrul_observed",
    "STP_Kefreite_Security_Offer": "STP_focus_kefreyt_observed",
    "STP_The_Old_Man_On_The_Balcony": "STP_focus_palace_observed",
    "STP_The_City_Still_Dances": "STP_focus_street_observed",
    "STP_Count_The_Loyalists": "STP_focus_garrisons_observed",
    "STP_Show_Him_The_Truth": "STP_commit_to_shabrat",
    "STP_Govern_In_His_Name": "STP_commit_to_party",
    "STP_The_Valirian_Advisers": "STP_focus_nodrul_advisers_open",
    "STP_Contractors_In_The_Passes": "STP_focus_val_supply_open",
    "STP_Rumours_In_The_Highlands": "STP_focus_mountains_open",
    "STP_The_Lower_Market": "STP_focus_market_open",
    "STP_The_Party_Was_Not_Born_Here": "STP_focus_nodrul_disinformation_open",
    "STP_The_Desert_Watches_The_Snow": "STP_focus_val_red_line_known",
    "STP_The_Mountain_Printing_House": "STP_focus_mountain_caches_improved",
    "STP_Hunt_The_Mountain_Cells": "STP_focus_mountain_raids_improved",
    "STP_Steal_The_Black_Ledger": "STP_focus_black_ledger_open",
    "STP_Burn_The_Client_Archives": "STP_focus_archive_burning_open",
    "STP_The_Silent_Mountain_March": "STP_focus_silent_march_open",
    "STP_One_Last_National_Festival": "STP_focus_festival_police_open",
    "STP_Turn_The_Young_Officers": "STP_focus_young_officers_open",
    "STP_Feed_The_Festival_Police": "STP_focus_garrison_rotation_open",
    "STP_The_Last_Confession": "STP_focus_palace_channel_improved",
    "STP_The_Hand_That_Still_Signs": "STP_focus_seal_palace_improved",
    "STP_Imported_Freedom": "STP_focus_nodrul_mandate_exposed",
    "STP_Cut_The_Silk_Leash": "STP_focus_break_mandate_ready",
    "STP_Renew_The_Cultural_Mandate": "STP_focus_renew_mandate_ready",
    "STP_No_Mercenaries_In_Our_Mountains": "STP_focus_val_channel_countered",
    "STP_Sell_The_Highland_Concessions": "STP_focus_val_concession_ready",
    "STP_A_Name_On_The_Walls": "STP_focus_mountain_final_open",
    "STP_Erase_His_Name": "STP_focus_mountain_purge_open",
    "STP_The_First_Witness": "STP_focus_first_witness_open",
    "STP_Silence_The_First_Witness": "STP_focus_silence_witness_open",
    "STP_Lower_Market_Dossiers": "STP_focus_dossiers_protected",
    "STP_The_Port_Must_Smile": "STP_focus_market_censorship_ready",
    "STP_Call_For_Shabrat": "STP_focus_final_palace_move_open",
    "STP_Seal_The_Western_Wing": "STP_focus_final_palace_lock_open",
    "STP_The_People_Stop_Singing": "STP_focus_final_street_move_open",
    "STP_Drown_The_Rumours_In_Music": "STP_focus_final_street_lock_open",
    "STP_Garrisons_Hesitate": "STP_focus_final_garrison_move_open",
    "STP_Garrisons_Swear_Loyalty": "STP_focus_final_garrison_lock_open",
}
STP_SHABRAT_FOCUSES = (
    "STP_The_Party_Was_Not_Born_Here",
    "STP_The_Mountain_Printing_House",
    "STP_Steal_The_Black_Ledger",
    "STP_The_Silent_Mountain_March",
    "STP_Turn_The_Young_Officers",
    "STP_The_Last_Confession",
    "STP_Imported_Freedom",
    "STP_Cut_The_Silk_Leash",
    "STP_Sell_The_Highland_Concessions",
    "STP_A_Name_On_The_Walls",
    "STP_The_First_Witness",
    "STP_Lower_Market_Dossiers",
    "STP_Call_For_Shabrat",
    "STP_The_People_Stop_Singing",
    "STP_Garrisons_Hesitate",
)
STP_PARTY_FOCUSES = (
    "STP_Hunt_The_Mountain_Cells",
    "STP_Burn_The_Client_Archives",
    "STP_One_Last_National_Festival",
    "STP_Feed_The_Festival_Police",
    "STP_The_Hand_That_Still_Signs",
    "STP_Renew_The_Cultural_Mandate",
    "STP_No_Mercenaries_In_Our_Mountains",
    "STP_Erase_His_Name",
    "STP_Silence_The_First_Witness",
    "STP_The_Port_Must_Smile",
    "STP_Seal_The_Western_Wing",
    "STP_Drown_The_Rumours_In_Music",
    "STP_Garrisons_Swear_Loyalty",
)
NOD_POSTURES = (
    "NOD_crisis_posture_guardian",
    "NOD_crisis_posture_ypr",
    "NOD_crisis_posture_cof",
    "NOD_crisis_posture_beshay",
    "NOD_crisis_posture_wait",
)
NOD_BORDER_STATES = (10, 11)
NOD_LIMITED_TARGET_STATES = {
    "YPR": (15, 19),
    "COF": (14,),
    "BHG": (5,),
    "BBV": (7,),
}
NOD_LIMITED_TIMEOUT_DAYS = {"YPR": 240, "COF": 180, "BHG": 120, "BBV": 120}
NOD_ESCALATION_MISSIONS = {
    "NOD_escalation_ypr": ("NOD_crisis_posture_ypr", "YPR", 35),
    "NOD_escalation_cof": ("NOD_crisis_posture_cof", "COF", 35),
    "NOD_escalation_bhg": ("NOD_crisis_posture_beshay", "BHG", 35),
    "NOD_escalation_bbv": ("NOD_crisis_posture_beshay", "BBV", 35),
}
NOD_CONTROL_MISSIONS = {
    "NOD_control_ypr_generation_1": ("YPR", 30, 1),
    "NOD_control_ypr_generation_2": ("YPR", 30, 2),
    "NOD_control_cof_generation_1": ("COF", 30, 1),
    "NOD_control_cof_generation_2": ("COF", 30, 2),
}
NOD_SUPPORT_LEVELS = {
    "NOD_support_stp_material": (250, 25, "material"),
    "NOD_support_stp_limited": (500, 50, "limited"),
    "NOD_support_stp_full": (1000, 100, "full"),
}
WAR_COUNTDOWN_MISSIONS = (
    "STP_VAL_war_countdown_120",
    "STP_VAL_war_countdown_180",
    "STP_VAL_war_countdown_300",
    "STP_VAL_war_countdown_450",
    "STP_VAL_war_countdown_breached",
)
WAR_COUNTDOWN_MISSION_DAYS = {
    "STP_VAL_war_countdown_120": 120,
    "STP_VAL_war_countdown_180": 180,
    "STP_VAL_war_countdown_300": 300,
    "STP_VAL_war_countdown_450": 450,
    "STP_VAL_war_countdown_breached": 14,
}
WAR_COUNTDOWN_WARNING_EVENTS = {
    "STP_VAL_war_countdown_120": ("val_contract.60", 106, "val_contract.70", 119),
    "STP_VAL_war_countdown_180": ("val_contract.61", 166, "val_contract.71", 179),
    "STP_VAL_war_countdown_300": ("val_contract.62", 286, "val_contract.72", 299),
    "STP_VAL_war_countdown_450": ("val_contract.63", 436, "val_contract.73", 449),
    "STP_VAL_war_countdown_breached": ("val_contract.64", 0, "val_contract.74", 13),
}
WAR_COUNTDOWN_TRUCE_POLICY = "no_engine_truce"
NORTHERN_MODES = (
    "VAL_northern_campaign_full",
    "VAL_northern_campaign_partial_cin",
    "VAL_northern_campaign_partial_osf",
)
NORTHERN_TARGET_LOCKS = (
    "VAL_northern_target_59_resolved",
    "VAL_northern_target_61_resolved",
)
CIVIL_WAR_STATE_MAP = {
    "party_base": (1, 2, 3),
    "palace": (28,),
    "officers": (29,),
    "mountains": (43, 44, 53),
    "market": (45,),
    "street": (46,),
    "resource_garrison": (88,),
}
STP_CIVIL_WAR_STATES = (1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88)
STP_CIVIL_WAR_ARMY_RATIOS = {
    "resistance_revolter": (0, 0.2, 0.35, 0.5),
    "party_revolter": (1, 0.8, 0.65, 0.5),
}
STP_INTERNAL_OUTCOMES = {
    "shabrat_bloodless": ("shabrat", "no_war", None),
    "shabrat_main_war": ("shabrat", "resistance_main", "hedersett"),
    "sotnikov_main_war": ("sotnikov", "resistance_main", "hedersett"),
    "hedersett_fail_state": ("hedersett", "no_war", None),
    "hedersett_consolidation": ("hedersett", "no_war", None),
    "hedersett_vs_shabrat": ("hedersett", "party_main", "shabrat"),
    "hedersett_vs_sotnikov": ("hedersett", "party_main", "sotnikov"),
}
STP_CIVIL_WAR_FOCUS_IDS = (
    "STP_Crisis_Rally_The_Provinces",
    "STP_Crisis_Secure_The_Depots",
    "STP_Crisis_Hold_The_Capital_Road",
    "STP_Crisis_Request_External_Supplies",
)
STP_OFFICER_PACKAGES = {
    1: ("STP_Maurice_Dallon",),
    2: ("STP_Maurice_Dallon", "STP_Leonid_Barchel"),
    3: (
        "STP_Maurice_Dallon",
        "STP_Leonid_Barchel",
        "STP_Viktor_Marent",
        "STP_Severin_Drake",
    ),
}
STP_PARTY_CHARACTER_PACKAGE = (
    "STP_Roland_Keitel",
    "STP_Edmund_Ravel",
    "STP_August_Veil",
)
RESISTANCE_POSTURES = {
    1: "quiet_palace_conspiracy",
    2: "officer_network",
    3: "mountain_street_uprising",
    4: "external_val_contract",
}
SECURITY_POSTURES = {
    1: ("total_surveillance", "street", "palace"),
    2: ("targeted_arrests", "palace", "mountains"),
    3: ("garrison_rotation", "officers", "market"),
    4: ("mass_purge", "mountains", "street"),
    5: ("false_tolerance", "market", "officers"),
}
STP_ADAPTATION_FAMILIES = (
    "palace",
    "officers",
    "mountains",
    "market",
    "street",
    "foreign",
)
RESISTANCE_POSTURE_COUNTERS = {
    1: ("street", ("palace",)),
    2: ("palace", ("officers",)),
    3: ("officers", ("mountains", "street")),
    4: ("market", ("foreign",)),
}
STP_OPERATION_SPECS = {
    "STP_operation_palace_channel": (
        "shabrat", "aux", "palace", 28, 40, 10, {}, 0, "stp_crisis.20",
    ),
    "STP_operation_recruit_young_officers": (
        "shabrat",
        "major",
        "officers",
        35,
        35,
        20,
        {"infantry_equipment": 400, "support_equipment": 50},
        0,
        "stp_crisis.21",
    ),
    "STP_operation_mountain_caches": (
        "shabrat",
        "major",
        "mountains",
        35,
        25,
        0,
        {"infantry_equipment": 600, "support_equipment": 50},
        0,
        "stp_crisis.22",
    ),
    "STP_operation_steal_black_ledger": (
        "shabrat", "major", "market", 28, 45, 0, {}, 2, "stp_crisis.23",
    ),
    "STP_operation_silent_march": (
        "shabrat", "aux", "street", 21, 30, 0, {}, 1, "stp_crisis.24",
    ),
    "STP_operation_nodrul_disinformation": (
        "shabrat",
        "major",
        "foreign",
        35,
        50,
        0,
        {"infantry_equipment": 250},
        0,
        "stp_crisis.25",
    ),
    "STP_operation_val_secret_channel": (
        "shabrat", "aux", "foreign", 28, 35, 0, {}, 1, "stp_crisis.26",
    ),
    "STP_operation_seal_palace": (
        "party", "aux", "palace", 28, 35, 10, {}, 0, "stp_crisis.27",
    ),
    "STP_operation_rotate_garrisons": (
        "party", "major", "officers", 28, 30, 25, {}, 0, "stp_crisis.28",
    ),
    "STP_operation_targeted_raid": (
        "party", "major", "project", 28, 40, 15, {}, 0, "stp_crisis.29",
    ),
    "STP_operation_burn_client_archives": (
        "party", "major", "market", 28, 35, 0, {}, 2, "stp_crisis.30",
    ),
    "STP_operation_arm_festival_police": (
        "party",
        "aux",
        "street",
        21,
        30,
        0,
        {"infantry_equipment": 300},
        0,
        "stp_crisis.31",
    ),
    "STP_operation_request_nodrul_advisers": (
        "party", "major", "foreign", 35, 50, 0, {}, 0, "stp_crisis.32",
    ),
    "STP_operation_false_val_channel": (
        "party", "aux", "foreign", 28, 35, 0, {}, 1, "stp_crisis.33",
    ),
}
STP_OPERATION_VARIANTS = {
    "STP_operation_nodrul_disinformation_convoys": (
        "STP_operation_nodrul_disinformation",
        {"convoy": 25},
    ),
}
STP_RESISTANCE_PROJECTS = {
    "STP_resistance_project_palace": "palace",
    "STP_resistance_project_garrison_theft": "officers",
    "STP_resistance_project_mountain_smuggling": "mountains",
    "STP_resistance_project_street_agitation": "street",
    "STP_resistance_project_external_contract": "foreign",
}
VAL_NEGOTIATION_POSTURES = {
    1: "cautious_broker",
    2: "predatory_concessionaire",
    3: "fear_nodrul_reaction",
    4: "double_game",
}
VAL_AUTHORITY_FOCUS_REWARDS = {
    "VAL_The_Contract_State": 5,
    "VAL_The_Weaponry_Baron": 10,
    "VAL_Price_Of_Loyalty": 5,
    "VAL_Count_The_Captains": 5,
    "VAL_One_Ledger_One_Banner": 10,
    "VAL_Export_Rifles_Not_Promises": 5,
    "VAL_Morns_Supply_Trains": 5,
    "VAL_Dead_Villages_Still_Count": 5,
    "VAL_Different_Views_On_Freedom": 5,
    "VAL_Contracts_Outlive_Kings": 5,
}
VAL_BASE_FOCUS_IDS = (
    "VAL_The_Contract_State",
    "VAL_The_Weaponry_Baron",
    "VAL_Price_Of_Loyalty",
    "VAL_Count_The_Captains",
    "VAL_One_Ledger_One_Banner",
    "VAL_Factories_Like_Cathedrals",
    "VAL_Keep_The_Lines_Hot",
    "VAL_Ballistics_Schools",
    "VAL_Brokered_Steel",
    "VAL_Export_Rifles_Not_Promises",
    "VAL_The_Mercenary_State",
    "VAL_Hire_Out_War",
    "VAL_Vorons_Companies",
    "VAL_Stahls_Schedules",
    "VAL_Gromovs_Assault_Tables",
    "VAL_Morns_Supply_Trains",
    "VAL_The_Harvest_Of_Ash",
    "VAL_Field_Surgeons",
    "VAL_Bread_From_Barracks",
    "VAL_Dead_Villages_Still_Count",
    "VAL_Market_Roads_North",
    "VAL_Trading_Partners",
    "VAL_October_Of_2160",
    "VAL_Different_Views_On_Freedom",
    "VAL_Contracts_Outlive_Kings",
)
VAL_CRISIS_FOCUS_IDS = (
    "VAL_Offer_The_Mountain_Contract",
    "VAL_Secure_The_Resource_Corridor",
    "VAL_Negotiate_The_Deferred_Invoice",
    "VAL_Let_Nodrul_Bleed",
    "VAL_Present_The_Final_Invoice",
)
VAL_STP_OPERATION_SPECS = {
    "VAL_STP_map_mountain_passes": (25, 28, "intel"),
    "VAL_STP_build_contractor_depot": (35, 35, "supply"),
    "VAL_STP_offer_mountain_concession": (40, 35, "concession"),
    "VAL_STP_buy_border_officers": (45, 35, "garrison"),
    "VAL_STP_test_nodrul_red_line": (30, 28, "nodrul"),
}
VAL_NORTHERN_OPERATION_SPECS = {
    "study_market": (30, 28, 0),
    "arms_brokerage": (25, 35, 1),
    "prepare_separate_terms": (50, 35, 1),
}
VAL_NORTHERN_OPERATION_TARGETS = ("CIN", "OSF", "APH")
STP_TRANSITION_FOCUS_MAP = {
    "STP_outcome_shabrat_bloodless": "STP_The_Mountain_Window",
    "STP_outcome_shabrat_main_war": "STP_No_One_Controls_The_Transition",
    "STP_outcome_sotnikov_main_war": "STP_A_General_Takes_The_Passes",
    "STP_outcome_hedersett_fail_state": "STP_The_Underground_Was_Too_Late",
    "STP_outcome_hedersett_consolidation": "STP_The_Party_Closes_Ranks",
    "STP_outcome_hedersett_vs_shabrat": "STP_Two_Claims_To_The_Palace",
    "STP_outcome_hedersett_vs_sotnikov": "STP_The_Army_Rejects_The_Party",
}
VAL_STP_CONCESSION_FLAGS = (
    "VAL_STP_concession_resource_45",
    "VAL_STP_concession_resource_88",
    "VAL_STP_concession_arms_debt",
    "VAL_STP_concession_transit",
    "VAL_STP_concession_advisers",
    "VAL_STP_concession_postwar_contracts",
)
VAL_FOCUS_REWARD_TOKENS = {
    "VAL_The_Contract_State": ("VAL_contract_board_open", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
    "VAL_The_Weaponry_Baron": ("army_experience = 10", "ADISCORD_STP_VAL_effect_value value = 10", "VAL_change_contract_authority = yes"),
    "VAL_Price_Of_Loyalty": ("VAL_captain_retainers_unlocked", "add_political_power = 25", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
    "VAL_Count_The_Captains": ("VAL_negotiation_posture_visible", "army_experience = 10", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
    "VAL_One_Ledger_One_Banner": ("VAL_foreign_operations_unlocked", "add_war_support = 0.05", "ADISCORD_STP_VAL_effect_value value = 10", "VAL_change_contract_authority = yes"),
    "VAL_Factories_Like_Cathedrals": ("VAL_factory_cathedrals_drive", "days = 365"),
    "VAL_Keep_The_Lines_Hot": ("VAL_hot_production_lines",),
    "VAL_Ballistics_Schools": ("VAL_quality_arsenal", "category = infantry_weapons", "VAL_refresh_contract_modifier = yes"),
    "VAL_Brokered_Steel": ("VAL_broad_resource_network", "add_political_power = 25", "VAL_refresh_contract_modifier = yes"),
    "VAL_Export_Rifles_Not_Promises": ("VAL_supply_contracts", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
    "VAL_The_Mercenary_State": ("army_experience = 10", "VAL_doctrine_choice_unlocked"),
    "VAL_Hire_Out_War": ("VAL_foreign_contracts_unlocked", "add_political_power = 50"),
    "VAL_Vorons_Companies": ("VAL_doctrine_covert_intervention", "VAL_refresh_contract_modifier = yes"),
    "VAL_Stahls_Schedules": ("VAL_doctrine_sustained_supply", "VAL_refresh_contract_modifier = yes"),
    "VAL_Gromovs_Assault_Tables": ("VAL_doctrine_resource_raider", "VAL_refresh_contract_modifier = yes"),
    "VAL_Morns_Supply_Trains": ("VAL_supply_preparation", "VAL_change_final_war_preparation = yes", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
    "VAL_The_Harvest_Of_Ash": ("VAL_ash_model_unlocked", "add_war_support = 0.05"),
    "VAL_Field_Surgeons": ("VAL_ash_manpower_preservation", "VAL_refresh_contract_modifier = yes"),
    "VAL_Bread_From_Barracks": ("VAL_ash_rear_mobilization", "VAL_refresh_contract_modifier = yes"),
    "VAL_Dead_Villages_Still_Count": ("VAL_ash_model_selected", "add_war_support = 0.05", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
    "VAL_Market_Roads_North": ("VAL_northern_intelligence_unlocked", "VAL_northern_roads_drive"),
    "VAL_Trading_Partners": ("VAL_north_open_market", "VAL_refresh_contract_modifier = yes"),
    "VAL_October_Of_2160": ("VAL_north_coercive", "add_war_support = 0.05", "VAL_refresh_contract_modifier = yes"),
    "VAL_Different_Views_On_Freedom": ("VAL_northern_operations_unlocked", "add_political_power = 25", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
    "VAL_Contracts_Outlive_Kings": ("VAL_crisis_strategy_unlocked", "VAL_change_final_war_preparation = yes", "ADISCORD_STP_VAL_effect_value value = 5", "VAL_change_contract_authority = yes"),
}
VAL_CONTRACT_BANDS = (
    {"minimum": 0, "maximum": 24, "modifiers": {"org": 3, "org_regain": 2, "daily_pp": -0.10}},
    {
        "minimum": 25,
        "maximum": 49,
        "modifiers": {"attack": 3, "defence": 3, "org": 5, "org_regain": 3, "capture": 2, "planning": -5, "daily_pp": -0.10},
    },
    {
        "minimum": 50,
        "maximum": 74,
        "modifiers": {"attack": 6, "defence": 5, "org": 8, "org_regain": 5, "capture": 5, "supply": -3, "planning": -5, "state_overload": 3, "trade_income": 3, "military_industry_income": 3, "army_expense": -3},
    },
    {
        "minimum": 75,
        "maximum": 89,
        "modifiers": {"attack": 10, "defence": 8, "org": 10, "org_regain": 8, "capture": 8, "supply": -5, "planning": -10, "daily_pp": -0.20, "state_overload": 5, "trade_income": 5, "military_industry_income": 5, "army_expense": -5},
    },
    {
        "minimum": 90,
        "maximum": 100,
        "modifiers": {"attack": 12, "defence": 10, "org": 12, "org_regain": 10, "capture": 10, "supply": -7, "planning": -15, "daily_pp": -0.25, "stability": -5, "state_overload": 8, "trade_income": 7, "military_industry_income": 7, "army_expense": -7},
    },
)
VAL_CONTRACT_SPECIALISATIONS = {
    "VAL_captain_retainers_unlocked": (("VAL_contract_command_power_factor", 0.1),),
    "VAL_negotiation_posture_visible": (("VAL_contract_pp_gain", 0.1),),
    "VAL_quality_arsenal": (
        ("VAL_contract_factory_output_factor", 0.05),
        ("VAL_contract_capture_factor", 0.02),
    ),
    "VAL_broad_resource_network": (
        ("VAL_contract_supply_factor", -0.03),
        ("VAL_contract_trade_income_factor", 0.05),
    ),
    "VAL_supply_contracts": (
        ("VAL_contract_military_income_factor", 0.05),
        ("VAL_contract_army_expense_factor", -0.03),
    ),
    "VAL_doctrine_covert_intervention": (
        ("VAL_contract_planning_factor", 0.05),
        ("VAL_contract_capture_factor", 0.03),
    ),
    "VAL_doctrine_sustained_supply": (
        ("VAL_contract_org_regain", 0.03),
        ("VAL_contract_supply_factor", -0.05),
    ),
    "VAL_doctrine_resource_raider": (
        ("VAL_contract_attack_factor", 0.04),
        ("VAL_contract_capture_factor", 0.05),
        ("VAL_contract_defence_factor", -0.02),
    ),
    "VAL_ash_manpower_preservation": (
        ("VAL_contract_conscription_factor", 0.05),
        ("VAL_contract_org_regain", 0.02),
    ),
    "VAL_ash_rear_mobilization": (
        ("VAL_contract_factory_output_factor", 0.05),
        ("VAL_contract_consumer_goods_factor", -0.03),
    ),
    "VAL_north_open_market": (
        ("VAL_contract_trade_income_factor", 0.07),
        ("VAL_contract_pp_gain", 0.1),
    ),
    "VAL_north_coercive": (
        ("VAL_contract_military_income_factor", 0.07),
        ("VAL_contract_attack_factor", 0.02),
        ("VAL_contract_stability_factor", -0.02),
    ),
}
VAL_AI_FOCUS_COURSE_BIASES = {
    "VAL_Ballistics_Schools": ("VAL_ai_course_resource_raider",),
    "VAL_Brokered_Steel": ("VAL_ai_course_contract_broker", "VAL_ai_course_northern_broker"),
    "VAL_Vorons_Companies": ("VAL_ai_course_contract_broker", "VAL_ai_course_northern_broker"),
    "VAL_Stahls_Schedules": ("VAL_ai_course_patient_invader",),
    "VAL_Gromovs_Assault_Tables": ("VAL_ai_course_resource_raider",),
    "VAL_Field_Surgeons": ("VAL_ai_course_patient_invader",),
    "VAL_Bread_From_Barracks": ("VAL_ai_course_contract_broker", "VAL_ai_course_northern_broker"),
    "VAL_Trading_Partners": ("VAL_ai_course_contract_broker", "VAL_ai_course_northern_broker"),
    "VAL_October_Of_2160": ("VAL_ai_course_resource_raider",),
}
POSTWAR_FOCUS_IDS = (
    "STP_Shabrat_Count_The_Surviving_Regiments",
    "STP_Shabrat_Open_The_Archives",
    "STP_Shabrat_Break_The_Mandate",
    "STP_Shabrat_Buy_The_Desert_Season",
    "STP_Shabrat_Fortify_The_Resource_Road",
    "STP_Sotnikov_The_Military_Committee",
    "STP_Sotnikov_Rebuild_The_General_Staff",
    "STP_Sotnikov_Arm_The_Northern_Passes",
    "STP_Sotnikov_War_On_Two_Maps",
    "STP_Hedersett_The_Party_After_The_Father",
    "STP_Hedersett_End_The_Lists",
    "STP_Hedersett_One_Last_Purge",
    "STP_Hedersett_Renew_The_Nodrul_Mandate",
    "STP_Hedersett_Pay_The_Deferred_Invoice",
    "STP_Hedersett_Rebuild_The_Festival_Army",
)

OWNED_FEATURE_FILES = (
	"common/autonomous_states/ADISCORD_contract_clients.txt",
    "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt",
    "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt",
    "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt",
    "common/decisions/ADISCORD_STP_crisis_decisions.txt",
    "events/ADISCORD_STP_crisis_events.txt",
    "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt",
    "common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt",
    "common/national_focus/ADISCORD_national_focus_STP_postwar.txt",
    "common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt",
    "common/decisions/ADISCORD_VAL_contract_decisions.txt",
    "events/ADISCORD_VAL_contract_events.txt",
    "common/decisions/ADISCORD_NOD_crisis_decisions.txt",
    "events/ADISCORD_NOD_crisis_events.txt",
    "common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt",
    "common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt",
    "interface/ADISCORD_STP_VAL_crisis.gui",
    "common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt",
    "localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml",
)
