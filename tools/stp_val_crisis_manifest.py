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
    "STP_crisis_operations",
    "VAL_contract_campaign",
    "NOD_crisis_posture",
    "VAL_northern_campaign",
    "STP_VAL_war_countdown_category",
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
WAR_COUNTDOWN_MISSIONS = (
    "STP_VAL_war_countdown_120",
    "STP_VAL_war_countdown_180",
    "STP_VAL_war_countdown_300",
    "STP_VAL_war_countdown_450",
    "STP_VAL_war_countdown_breached",
)
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
VAL_NEGOTIATION_POSTURES = {
    1: "cautious_broker",
    2: "predatory_concessionaire",
    3: "fear_nodrul_reaction",
    4: "double_game",
}
VAL_AUTHORITY_FOCUS_REWARDS = {
    "VAL_The_Contract_State": 5,
    "VAL_The_Weaponry_Baron": 10,
    "VAL_Export_Rifles_Not_Promises": 5,
    "VAL_Morns_Supply_Trains": 5,
    "VAL_Dead_Villages_Still_Count": 5,
    "VAL_Different_Views_On_Freedom": 5,
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
    "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt",
    "common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt",
    "common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt",
    "common/decisions/ADISCORD_STP_crisis_decisions.txt",
    "events/ADISCORD_STP_crisis_events.txt",
    "common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt",
    "common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt",
    "common/national_focus/ADISCORD_national_focus_STP_postwar.txt",
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
