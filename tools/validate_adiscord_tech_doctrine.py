#!/usr/bin/env python3
"""Static checks for the A-DISCORD technology and doctrine framework."""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from build_adiscord_technology_system import (
        BRANCH_GRAPHS as GENERATED_BRANCH_GRAPHS,
        BRANCHES as GENERATED_BRANCHES,
        BUILDING_RESOURCE_UPGRADES as GENERATED_BUILDING_RESOURCE_UPGRADES,
        ENABLE_BUILDINGS as GENERATED_ENABLE_BUILDINGS,
        ENABLE_EQUIPMENT as GENERATED_ENABLE_EQUIPMENT,
        EXTRA_TECH_DEPENDENCIES as GENERATED_EXTRA_TECH_DEPENDENCIES,
        FOLDER_BACKGROUNDS as GENERATED_FOLDERS,
        FORBIDDEN_IDS as GENERATED_FORBIDDEN_IDS,
        LANE_SLOT_MULTIPLIER as GENERATED_LANE_SLOT_MULTIPLIER,
        XOR_INDEX_GROUPS_BY_BRANCH as GENERATED_XOR_INDEX_GROUPS_BY_BRANCH,
        YEARS as GENERATED_YEARS,
        YEAR_TO_Y as GENERATED_YEAR_TO_Y,
    )
except ModuleNotFoundError:
    from tools.build_adiscord_technology_system import (
        BRANCH_GRAPHS as GENERATED_BRANCH_GRAPHS,
        BRANCHES as GENERATED_BRANCHES,
        BUILDING_RESOURCE_UPGRADES as GENERATED_BUILDING_RESOURCE_UPGRADES,
        ENABLE_BUILDINGS as GENERATED_ENABLE_BUILDINGS,
        ENABLE_EQUIPMENT as GENERATED_ENABLE_EQUIPMENT,
        EXTRA_TECH_DEPENDENCIES as GENERATED_EXTRA_TECH_DEPENDENCIES,
        FOLDER_BACKGROUNDS as GENERATED_FOLDERS,
        FORBIDDEN_IDS as GENERATED_FORBIDDEN_IDS,
        LANE_SLOT_MULTIPLIER as GENERATED_LANE_SLOT_MULTIPLIER,
        XOR_INDEX_GROUPS_BY_BRANCH as GENERATED_XOR_INDEX_GROUPS_BY_BRANCH,
        YEARS as GENERATED_YEARS,
        YEAR_TO_Y as GENERATED_YEAR_TO_Y,
    )


ROOT = Path(__file__).resolve().parents[1]
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
TDA = Path(r"Z:\SteamLibrary\steamapps\workshop\content\394360\3607150697")

TEXT_EXTS = {".txt", ".gfx", ".gui", ".yml"}
BRACE_EXTS = {".txt", ".gfx", ".gui"}

EXPECTED_TECH_GRID_POSITIONS = {
    tech.id: (
        GENERATED_BRANCH_GRAPHS[branch.key].lanes[index] * GENERATED_LANE_SLOT_MULTIPLIER,
        GENERATED_YEAR_TO_Y[branch.years[index]],
    )
    for branch in GENERATED_BRANCHES
    for index, tech in enumerate(branch.techs)
}
SAFE_TECH_GRID_POSITIONS = {
    folder: {
        EXPECTED_TECH_GRID_POSITIONS[tech.id]
        for branch in GENERATED_BRANCHES
        if folder in branch.folders
        for tech in branch.techs
    }
    for folder in GENERATED_FOLDERS
}

EXPECTED_TECH_YEARS = set(GENERATED_YEARS)
EXPECTED_TECH_UI_YEARS = {str(year) for year in GENERATED_YEARS}
LEGACY_TECH_UI_YEAR_RE = re.compile(r'\btext\s*=\s*"(19[0-9]{2}|20[0-8][0-9])"')

MIN_COUNTRY_TAGS = 51
REQUIRED_DYNAMIC_TAGS = {f"D{index:02d}" for index in range(1, 51)}
REQUIRED_SCRIPT_ENUMS = {
    "script_enum_operative_mission_type",
    "script_enum_advisor_slot_type",
    "script_enum_equipment_stat",
    "script_enum_production_stat",
    "script_enum_equipment_category",
    "script_enum_equipment_bonus_type",
}
REQUIRED_DOCTRINE_FOLDERS = {"land", "naval", "air"}
REQUIRED_AIR_MAP_ICON_FRAMES = {
    "ADISCORD_fighter_archetype": 1,
    "ADISCORD_cas_archetype": 2,
    "ADISCORD_rocket_strike_archetype": 6,
}

VALID_DOCTRINE_MASTERY_EQUIPMENT = {
    "capital_ship",
    "carrier",
    "screen_ship",
    "submarine",
    "fighter",
    "interceptor",
    "cas",
    "naval_bomber",
    "suicide",
    "tactical_bomber",
    "heavy_fighter",
    "scout_plane",
    "strategic_bomber",
    "maritime_patrol_plane",
}

EXPECTED_TECHS = [
    "ADISCORD_tech_salvage_standards",
    "ADISCORD_tech_ruin_workshops",
    "ADISCORD_tech_reconstruction_bureaus",
    "ADISCORD_tech_modular_rebuilding",
    "ADISCORD_tech_basic_fiscal_records",
    "ADISCORD_tech_reconstruction_contracts",
    "ADISCORD_tech_tax_census_network",
    "ADISCORD_tech_state_debt_instruments",
    "ADISCORD_tech_reserve_management",
    "ADISCORD_tech_fiscal_administration_1",
    "ADISCORD_tech_fiscal_administration_2",
    "ADISCORD_tech_automated_bureaucracy",
    "ADISCORD_tech_predictive_budgeting",
    "ADISCORD_tech_local_grid_restoration",
    "ADISCORD_tech_substation_networks",
    "ADISCORD_tech_radiation_mapping",
    "ADISCORD_tech_shielded_engineering_corps",
    "ADISCORD_tech_reactor_safety_protocols",
    "ADISCORD_tech_microreactor_blocks",
    "ADISCORD_tech_dead_reactor_salvage",
    "ADISCORD_tech_emergency_core_suppression",
    "ADISCORD_tech_standardized_machine_tools",
    "ADISCORD_tech_industrial_cluster_planning",
    "ADISCORD_tech_logistics_hub_networks",
    "ADISCORD_tech_automated_assembly",
    "ADISCORD_tech_synthetic_resource_cycles",
    "ADISCORD_tech_predictive_maintenance",
    "ADISCORD_tech_autonomous_factory_cells",
    "ADISCORD_tech_distributed_manufacturing",
    "ADISCORD_tech_postwar_weapon_standardization",
    "ADISCORD_tech_composite_protection_kits",
    "ADISCORD_tech_smart_optics",
    "ADISCORD_tech_battlefield_medical_drones",
    "ADISCORD_tech_exoskeleton_load_frames",
    "ADISCORD_tech_field_ew_units",
    "ADISCORD_tech_networked_command_terminals",
    "ADISCORD_tech_assault_sapper_kits",
    "ADISCORD_tech_restored_field_artillery",
    "ADISCORD_tech_smart_fire_control",
    "ADISCORD_tech_drone_spotted_batteries",
    "ADISCORD_tech_scrap_at_launchers",
    "ADISCORD_tech_coil_at_systems",
    "ADISCORD_tech_point_defense_aa",
    "ADISCORD_tech_rail_assisted_aa",
    "ADISCORD_tech_restored_armored_chassis",
    "ADISCORD_tech_remote_weapon_stations",
    "ADISCORD_tech_drone_recon_swarms",
    "ADISCORD_tech_semi_autonomous_combat_modules",
    "ADISCORD_tech_remote_repair_sections",
    "ADISCORD_tech_heavy_platform_cores",
    "ADISCORD_tech_limited_battle_ai",
    "ADISCORD_tech_autonomous_breakthrough_platforms",
    "ADISCORD_tech_restored_rail_stock",
    "ADISCORD_tech_armored_rail_convoys",
    "ADISCORD_tech_autonomous_rail_dispatch",
    "ADISCORD_tech_hardened_logistics_nodes",
    "ADISCORD_tech_railway_gun_reactivation",
    "ADISCORD_tech_over_the_horizon_fire_control",
    "ADISCORD_tech_reclaimed_jet_platforms",
    "ADISCORD_tech_guided_munitions",
    "ADISCORD_tech_vtol_assault_frames",
    "ADISCORD_tech_drone_air_wings",
    "ADISCORD_tech_high_altitude_interceptors",
    "ADISCORD_tech_strategic_rocket_architecture",
    "ADISCORD_tech_orbital_tracking_relics",
    "ADISCORD_tech_deep_strike_targeting",
    "ADISCORD_tech_mesh_command_networks",
    "ADISCORD_tech_encryption_rebuild",
    "ADISCORD_tech_signal_intercept_arrays",
    "ADISCORD_tech_battlefield_analytics",
    "ADISCORD_tech_counterintelligence_filters",
    "ADISCORD_tech_predictive_logistics",
    "ADISCORD_tech_memetic_security_protocols",
    "ADISCORD_tech_operational_ai_assistants",
    "ADISCORD_tech_modular_shelters",
    "ADISCORD_tech_ration_distribution_systems",
    "ADISCORD_tech_urban_radiation_sanitation",
    "ADISCORD_tech_technical_institutes",
    "ADISCORD_tech_automated_civil_registry",
    "ADISCORD_tech_public_repair_corps",
    "ADISCORD_tech_population_resilience_planning",
    "ADISCORD_tech_civil_defense_networks",
    "ADISCORD_tech_old_generator_fragments",
    "ADISCORD_tech_legacy_reactor_compactification",
    "ADISCORD_tech_self_repairing_industrial_swarms",
    "ADISCORD_tech_neural_command_cores",
    "ADISCORD_tech_dirty_energy_munitions",
    "ADISCORD_tech_singularity_cooling_systems",
    "ADISCORD_tech_black_grid_protocols",
    "ADISCORD_tech_forbidden_automation_doctrine",
]

EXPECTED_TECHS = [
    tech.id
    for branch in GENERATED_BRANCHES
    for tech in branch.techs
]
FORBIDDEN_TECHS = sorted(GENERATED_FORBIDDEN_IDS)

EXPECTED_TRIGGERS = [
    "ADISCORD_has_grid_economy_tech",
    "ADISCORD_has_radiation_mapping_tech",
    "ADISCORD_has_reactor_safety_tech",
    "ADISCORD_has_microreactor_tech",
    "ADISCORD_has_industrial_automation_tech",
    "ADISCORD_has_logistics_network_tech",
    "ADISCORD_has_military_standardization_tech",
    "ADISCORD_has_autonomous_platform_tech",
    "ADISCORD_has_cyber_command_tech",
    "ADISCORD_has_civil_resilience_tech",
    "ADISCORD_has_forbidden_legacy_access",
    "ADISCORD_has_black_grid_access",
]

EXPECTED_DOCTRINES = [
    "ADISCORD_doctrine_restoration_general_staff",
    "ADISCORD_doctrine_mass_recruitment_bureaus",
    "ADISCORD_doctrine_salvage_line_infantry",
    "ADISCORD_doctrine_distributed_militias",
    "ADISCORD_doctrine_emergency_replacement_system",
    "ADISCORD_doctrine_total_restoration_front",
    "ADISCORD_doctrine_people_and_scrap",
    "ADISCORD_doctrine_platform_battlegroups",
    "ADISCORD_doctrine_remote_weapon_coordination",
    "ADISCORD_doctrine_heavy_breakthrough_columns",
    "ADISCORD_doctrine_drone_screened_advance",
    "ADISCORD_doctrine_autonomous_repair_cycles",
    "ADISCORD_doctrine_armored_decision_warfare",
    "ADISCORD_doctrine_mesh_battlefield_command",
    "ADISCORD_doctrine_reconnaissance_saturation",
    "ADISCORD_doctrine_predictive_operational_planning",
    "ADISCORD_doctrine_integrated_fire_control",
    "ADISCORD_doctrine_distributed_command_cells",
    "ADISCORD_doctrine_algorithmic_campaigning",
    "ADISCORD_doctrine_fortress_state_command",
    "ADISCORD_doctrine_urban_defense_grids",
    "ADISCORD_doctrine_hardened_logistics",
    "ADISCORD_doctrine_radiation_zone_operations",
    "ADISCORD_doctrine_counteroffensive_reserves",
    "ADISCORD_doctrine_national_redoubt_protocols",
    "ADISCORD_air_doctrine_restored_air_command",
    "ADISCORD_air_doctrine_swarm_recon",
    "ADISCORD_air_doctrine_disposable_airframes",
    "ADISCORD_air_doctrine_layered_drone_screen",
    "ADISCORD_air_doctrine_autonomous_target_marking",
    "ADISCORD_air_doctrine_vtol_assault_groups",
    "ADISCORD_air_doctrine_precision_cas",
    "ADISCORD_air_doctrine_forward_air_liaisons",
    "ADISCORD_air_doctrine_deep_strike_windows",
    "ADISCORD_air_doctrine_interceptor_grids",
    "ADISCORD_air_doctrine_hardened_airfields",
    "ADISCORD_air_doctrine_strategic_denial_zones",
    "ADISCORD_air_doctrine_rocket_warning_network",
    "ADISCORD_naval_doctrine_littoral_command",
    "ADISCORD_naval_doctrine_littoral_security_network",
    "ADISCORD_naval_doctrine_convoy_shield_doctrine",
    "ADISCORD_naval_doctrine_drone_carrier_groups",
    "ADISCORD_naval_doctrine_subsurface_denial",
]

EXPECTED_TRACKS = [
    "ADISCORD_land_mass_restoration",
    "ADISCORD_land_platform_centric",
    "ADISCORD_land_networked_operations",
    "ADISCORD_land_fortress_state",
    "ADISCORD_air_drone_swarm",
    "ADISCORD_air_vtol_deep_strike",
    "ADISCORD_air_strategic_denial",
    "ADISCORD_naval_littoral_security",
]

TECHNOLOGY_FILES = [
    "common/technologies/ADISCORD_industry.txt",
    "common/technologies/ADISCORD_electronics.txt",
    "common/technologies/ADISCORD_infantry.txt",
    "common/technologies/ADISCORD_artillery.txt",
    "common/technologies/ADISCORD_armor.txt",
    "common/technologies/ADISCORD_logistics_trains.txt",
    "common/technologies/ADISCORD_air.txt",
    "common/technologies/ADISCORD_naval.txt",
    "common/technologies/ADISCORD_forbidden.txt",
]

EQUIPMENT_FILES = [
    "common/units/equipment/ADISCORD_infantry_equipment.txt",
    "common/units/equipment/ADISCORD_support_equipment.txt",
    "common/units/equipment/ADISCORD_artillery_equipment.txt",
    "common/units/equipment/ADISCORD_armor_equipment.txt",
    "common/units/equipment/ADISCORD_train_equipment.txt",
    "common/units/equipment/ADISCORD_railway_gun_equipment.txt",
    "common/units/equipment/ADISCORD_air_equipment.txt",
    "common/units/equipment/ADISCORD_convoy_equipment.txt",
]

EXPECTED_DESCRIPTOR_REPLACE_PATHS = [
    'replace_path="history/general"',
    'replace_path="common/bookmarks"',
    'replace_path="common/ai_templates"',
    'replace_path="common/country_tags"',
    'replace_path="common/country_tag_aliases"',
    'replace_path="common/country_leader"',
    'replace_path="common/focus_inlay_windows"',
    'replace_path="common/ideas"',
    'replace_path="common/unit_leader"',
    'replace_path="common/technologies"',
    'replace_path="common/units"',
    'replace_path="common/units/codenames_operatives"',
    'replace_path="common/units/critical_parts"',
    'replace_path="common/units/equipment"',
    'replace_path="common/units/equipment/modules"',
    'replace_path="common/units/equipment/upgrades"',
    'replace_path="common/raids"',
    'replace_path="common/raids/categories"',
    'replace_path="common/operations"',
    'replace_path="common/peace_conference/ai_peace"',
    'replace_path="common/peace_conference/categories"',
    'replace_path="common/peace_conference/cost_modifiers"',
    'replace_path="common/units/unit_modifiers"',
    'replace_path="common/units/names_railway_guns"',
    'replace_path="common/doctrines"',
    'replace_path="common/doctrines/folders"',
    'replace_path="common/doctrines/grand_doctrines"',
    'replace_path="common/doctrines/subdoctrines"',
    'replace_path="common/doctrines/subdoctrines/air"',
    'replace_path="common/doctrines/subdoctrines/land"',
    'replace_path="common/doctrines/subdoctrines/sea"',
    'replace_path="common/doctrines/subdoctrines/special_forces"',
    'replace_path="common/doctrines/tracks"',
    'replace_path="common/resistance_compliance_modifiers"',
    'replace_path="gfx/interface/equipmentdesigner/graphic_db"',
]

EXPECTED_EQUIPMENT = [
    "convoy",
    "convoy_1",
    "infantry_equipment",
    "infantry_equipment_0",
    "ADISCORD_infantry_equipment_2170",
    "ADISCORD_infantry_equipment_2183",
    "ADISCORD_infantry_equipment_2200",
    "ADISCORD_squad_weapons_equipment",
    "ADISCORD_squad_weapons_equipment_0",
    "ADISCORD_squad_weapons_equipment_2170",
    "ADISCORD_squad_weapons_equipment_2183",
    "ADISCORD_squad_weapons_equipment_2200",
    "support_equipment",
    "support_equipment_1",
    "ADISCORD_support_equipment_2170",
    "ADISCORD_support_equipment_2183",
    "ADISCORD_support_equipment_2200",
    "artillery_equipment",
    "artillery_equipment_1",
    "ADISCORD_artillery_equipment_2170",
    "ADISCORD_artillery_equipment_2183",
    "ADISCORD_anti_tank_equipment_2163",
    "ADISCORD_anti_tank_equipment_2183",
    "ADISCORD_anti_air_equipment_2163",
    "ADISCORD_anti_air_equipment_2183",
    "train_equipment",
    "train_equipment_1",
    "armored_train_equipment_1",
    "ADISCORD_autonomous_train_equipment_2183",
    "ADISCORD_hardened_train_equipment_2183",
    "railway_gun_equipment",
    "railway_gun_equipment_1",
    "ADISCORD_railway_gun_equipment_2200",
    "ADISCORD_light_combat_platform_2163",
    "ADISCORD_combat_platform_2170",
    "ADISCORD_recon_drone_carrier_2170",
    "ADISCORD_combat_platform_2183",
    "ADISCORD_repair_platform_2183",
    "ADISCORD_heavy_combat_platform_2183",
    "ADISCORD_combat_platform_2200",
    "ADISCORD_heavy_combat_platform_2200",
    "ADISCORD_fighter_airframe_2163",
    "ADISCORD_cas_airframe_2170",
    "ADISCORD_vtol_airframe_2170",
    "ADISCORD_drone_airframe_2183",
    "ADISCORD_interceptor_airframe_2183",
    "ADISCORD_rocket_strike_platform_2183",
    "ADISCORD_orbital_tracking_platform_2200",
    "ADISCORD_deep_strike_airframe_2200",
]

NEW_DATA_FILES = [
    "common/countries/ADISCORD_dynamic_country.txt",
    "common/country_tags/zz_dynamic_countries.txt",
    "common/technologies/ADISCORD_technologies.txt",
    *TECHNOLOGY_FILES,
    *EQUIPMENT_FILES,
    "common/units/ADISCORD_land_units.txt",
    "common/units/ADISCORD_air_units.txt",
    "common/ai_templates/ADISCORD_land_templates.txt",
    "common/script_enums.txt",
    "common/resistance_compliance_modifiers/ADISCORD_no_resistance_compliance_modifiers.txt",
    "common/scripted_triggers/ADISCORD_technology_triggers.txt",
    "common/doctrines/tracks/ADISCORD_doctrine_tracks.txt",
    "common/doctrines/folders/ADISCORD_doctrine_folders.txt",
    "common/doctrines/grand_doctrines/ADISCORD_grand_doctrines.txt",
    "common/doctrines/subdoctrines/land/ADISCORD_land_subdoctrines.txt",
    "common/doctrines/subdoctrines/air/ADISCORD_air_subdoctrines.txt",
    "common/doctrines/subdoctrines/sea/ADISCORD_naval_subdoctrines.txt",
    "common/doctrines/subdoctrines/special_forces/ADISCORD_no_special_forces_subdoctrines.txt",
    "common/operation_phases/lar_infiltration.txt",
    "common/operation_phases/lar_exfiltration.txt",
    "common/operation_phases/lar_historical_operations.txt",
    "common/operation_phases/lar_steal_blueprints.txt",
    "common/ai_strategy/ADISCORD_technology_doctrine_ai.txt",
    "interface/ADISCORD_technologies.gfx",
    "interface/countrytechtreeview.gui",
    "localisation/english/ADISCORD_technology_doctrine_l_english.yml",
    "localisation/russian/ADISCORD_technology_doctrine_l_russian.yml",
]

LOCAL_TECH_REFERENCE_ROOTS = [
    "common",
    "history/countries",
]

LOCAL_DOCTRINE_REFERENCE_ROOTS = [
    "common",
    "history/countries",
]

DOCTRINE_FOLDERS = {"land", "air", "naval"}

VANILLA_TAGS = {
    "AFG", "ALB", "ARG", "AST", "AUS", "BEL", "BOL", "BRA", "BUL", "CAN",
    "CHI", "CHL", "COL", "COS", "CRO", "CUB", "CZE", "DEN", "DOM", "ECU",
    "ELS", "ENG", "EST", "ETH", "FIN", "FRA", "GER", "GRE", "HOL", "HUN",
    "INS", "ITA", "JAP", "LAT", "LIT", "LUX", "MEX", "NOR", "NZL", "POL",
    "POR", "PRC", "RAJ", "SAF", "SIA", "SOV", "SPR", "SWE", "TUR", "USA",
    "YUG",
}


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def strip_comments(text: str) -> str:
    stripped = []
    for line in text.splitlines():
        in_quote = False
        escaped = False
        cut = len(line)
        for i, ch in enumerate(line):
            if ch == "\\" and in_quote and not escaped:
                escaped = True
                continue
            if ch == '"' and not escaped:
                in_quote = not in_quote
            if ch == "#" and not in_quote:
                cut = i
                break
            escaped = False
        stripped.append(line[:cut])
    return "\n".join(stripped)


def iter_text_files(*roots: str):
    for root in roots:
        base = ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTS:
                yield path


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def extract_block(text: str, start: int) -> str:
    open_at = text.find("{", start)
    if open_at < 0:
        return ""
    depth = 0
    in_quote = False
    escaped = False
    for i in range(open_at, len(text)):
        ch = text[i]
        if ch == "\\" and in_quote and not escaped:
            escaped = True
            continue
        if ch == '"' and not escaped:
            in_quote = not in_quote
        if not in_quote:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[open_at + 1:i]
        escaped = False
    return text[open_at + 1:]


def top_level_keys(block: str) -> set[str]:
    keys: set[str] = set()
    depth = 0
    for line in block.splitlines():
        start_depth = depth
        match = re.match(r"\s*([A-Za-z0-9_.:-]+)\s*=\s*\{", line)
        if start_depth == 0 and match:
            keys.add(match.group(1))
        depth += line.count("{") - line.count("}")
    return keys


def top_level_blocks(block: str, key: str) -> list[str]:
    """Return blocks whose declaration is a direct child of ``block``.

    Clausewitz GUI lookup is not recursive for technology grid boxes, so a
    regex over the entire folder container can produce a false positive when
    a grid is accidentally nested in a decorative child container.
    """

    result: list[str] = []
    depth = 0
    offset = 0
    pattern = re.compile(rf"\s*{re.escape(key)}\s*=\s*\{{")
    for line in block.splitlines(keepends=True):
        match = pattern.match(line)
        if depth == 0 and match:
            result.append(extract_block(block, offset + match.start()))
        depth += line.count("{") - line.count("}")
        offset += len(line)
    return result


def collect_technologies() -> tuple[set[str], dict[str, str]]:
    techs: set[str] = set()
    blocks: dict[str, str] = {}
    for path in (ROOT / "common" / "technologies").glob("*.txt"):
        text = strip_comments(read_text(path))
        match = re.search(r"\btechnologies\s*=\s*\{", text)
        if not match:
            continue
        block = extract_block(text, match.start())
        for key in top_level_keys(block):
            techs.add(key)
            tech_match = re.search(rf"\b{re.escape(key)}\s*=\s*\{{", block)
            if tech_match:
                blocks[key] = extract_block(block, tech_match.start())
    return techs, blocks


def collect_equipment_keys() -> set[str]:
    equipment: set[str] = set()
    base = ROOT / "common" / "units" / "equipment"
    for path in base.glob("*.txt") if base.exists() else []:
        text = strip_comments(read_text(path))
        match = re.search(r"\bequipments\s*=\s*\{", text)
        if match:
            equipment.update(top_level_keys(extract_block(text, match.start())))
    return equipment


def collect_equipment_blocks() -> dict[str, str]:
    blocks: dict[str, str] = {}
    base = ROOT / "common" / "units" / "equipment"
    for path in base.glob("*.txt") if base.exists() else []:
        text = strip_comments(read_text(path))
        match = re.search(r"\bequipments\s*=\s*\{", text)
        if not match:
            continue
        container = extract_block(text, match.start())
        for key in top_level_keys(container):
            key_match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*\{{", container)
            if key_match:
                blocks[key] = extract_block(container, key_match.start())
    return blocks


def collect_building_blocks() -> dict[str, str]:
    blocks: dict[str, str] = {}
    base = ROOT / "common" / "buildings"
    for path in base.glob("*.txt") if base.exists() else []:
        text = strip_comments(read_text(path))
        match = re.search(r"\bbuildings\s*=\s*\{", text)
        if not match:
            continue
        container = extract_block(text, match.start())
        for key in top_level_keys(container):
            key_match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*\{{", container)
            if key_match:
                blocks[key] = extract_block(container, key_match.start())
    return blocks


def collect_doctrine_keys() -> tuple[set[str], set[str], set[str], dict[str, str]]:
    grand: set[str] = set()
    tracks: set[str] = set()
    sub: set[str] = set()
    blocks: dict[str, str] = {}

    doctrine_dir = ROOT / "common" / "doctrines"
    for path in doctrine_dir.rglob("*.txt") if doctrine_dir.exists() else []:
        text = strip_comments(read_text(path))
        keys = top_level_keys(text)
        for key in keys:
            match = re.search(rf"\b{re.escape(key)}\s*=\s*\{{", text)
            if match:
                blocks[key] = extract_block(text, match.start())
            r = rel(path)
            if "/grand_doctrines/" in r:
                grand.add(key)
            elif "/tracks/" in r:
                tracks.add(key)
            elif "/subdoctrines/" in r:
                sub.add(key)
                reward_match = re.search(r"\brewards\s*=\s*\{", blocks[key])
                if reward_match:
                    sub.update(top_level_keys(extract_block(blocks[key], reward_match.start())))
    return grand, tracks, sub, blocks


def collect_scripted_triggers() -> set[str]:
    triggers: set[str] = set()
    base = ROOT / "common" / "scripted_triggers"
    for path in base.glob("*.txt") if base.exists() else []:
        text = strip_comments(read_text(path))
        triggers.update(top_level_keys(text))
    return triggers


def collect_localisation_keys() -> set[str]:
    keys: set[str] = set()
    for path in iter_text_files("localisation"):
        if path.suffix.lower() != ".yml":
            continue
        for line in read_text(path).splitlines():
            match = re.match(r"\s*([A-Za-z0-9_.:-]+)\s*:", line)
            if match and not match.group(1).startswith("l_"):
                keys.add(match.group(1))
    return keys


def collect_sprite_names() -> dict[str, str]:
    sprites: dict[str, str] = {}
    for path in iter_text_files("interface"):
        if path.suffix.lower() != ".gfx":
            continue
        text = strip_comments(read_text(path))
        for match in re.finditer(r"\bname\s*=\s*\"([A-Za-z0-9_.:-]+)\"", text):
            sprite = match.group(1)
            block_start = text.rfind("{", 0, match.start())
            block = extract_block(text, block_start) if block_start >= 0 else ""
            texture = re.search(r'\btexture[Ff]ile\s*=\s*"([^"]+)"', block)
            sprites[sprite] = texture.group(1).replace("\\", "/") if texture else ""
    return sprites


def resolve_texture(texture: str) -> Path | None:
    if not texture:
        return None
    candidates = [
        ROOT / texture,
        BASE_GAME / texture,
        TDA / texture,
    ]
    return next((path for path in candidates if path.exists()), None)


def texture_exists(texture: str) -> bool:
    return not texture or resolve_texture(texture) is not None


def texture_has_valid_dimensions(texture: str) -> bool:
    path = resolve_texture(texture)
    if path is None or path.suffix.lower() != ".dds":
        return path is not None
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"DDS ":
        return False
    height = int.from_bytes(data[12:16], "little")
    width = int.from_bytes(data[16:20], "little")
    return width > 0 and height > 0


def texture_dimensions(texture: str) -> tuple[int, int] | None:
    path = resolve_texture(texture)
    if path is None or path.suffix.lower() != ".dds":
        return None
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"DDS ":
        return None
    height = int.from_bytes(data[12:16], "little")
    width = int.from_bytes(data[16:20], "little")
    return (width, height) if width > 0 and height > 0 else None


def collect_reference_tech_categories() -> set[str]:
    categories: set[str] = set()
    roots = [
        BASE_GAME / "common" / "technologies",
        TDA / "common" / "technologies",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*.txt"):
            text = strip_comments(read_text(path))
            for match in re.finditer(r"\bcategories\s*=\s*\{([^{}]*)\}", text, re.S):
                categories.update(re.findall(r"[A-Za-z0-9_]+", match.group(1)))
    return categories


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def check_technology_parser_constraints(tech_blocks: dict[str, str]) -> list[str]:
    issues: list[str] = []
    valid_categories = collect_reference_tech_categories()

    for tech in EXPECTED_TECHS:
        block = tech_blocks.get(tech, "")
        if not block:
            continue

        invalid_equipment_scopes = {
            "artillery_equipment": "artillery",
            "anti_tank_equipment": "category_anti_tank",
            "anti_air_equipment": "anti_air",
        }
        for invalid, replacement in invalid_equipment_scopes.items():
            if re.search(rf"\b{invalid}\s*=\s*\{{", block):
                issues.append(f"{tech} uses invalid modifier scope {invalid}; use {replacement}")

        if re.search(r"\bfolder[^\S\r\n]*=[^\S\r\n]*\{[^\S\r\n]*name[^\S\r\n]*=", block):
            issues.append(f"{tech} uses inline folder block; use vanilla multiline folder format")

        year_match = re.search(r"\bstart_year\s*=\s*(\d+)", block)
        if not year_match:
            issues.append(f"{tech} has no start_year")
        elif int(year_match.group(1)) not in EXPECTED_TECH_YEARS:
            issues.append(f"{tech} uses legacy or unsupported year {year_match.group(1)}")

        folder_matches = list(re.finditer(r"\bfolder\s*=\s*\{", block))
        if not folder_matches:
            issues.append(f"{tech} has no folder block")
        for folder_match in folder_matches:
            folder_block = extract_block(block, folder_match.start())
            name_match = re.search(r"\bname\s*=\s*([A-Za-z0-9_]+)", folder_block)
            pos_match = re.search(
                r"\bposition\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*y\s*=\s*(-?\d+)\s*\}",
                folder_block,
            )
            if not name_match or not pos_match:
                issues.append(f"{tech} has malformed folder position")
            else:
                folder = name_match.group(1)
                position = (int(pos_match.group(1)), int(pos_match.group(2)))
                if folder not in SAFE_TECH_GRID_POSITIONS:
                    issues.append(f"{tech} uses unsupported folder {folder}")
                elif position not in SAFE_TECH_GRID_POSITIONS[folder]:
                    issues.append(f"{tech} uses unsafe {folder} grid position {position}")
                elif position != EXPECTED_TECH_GRID_POSITIONS[tech]:
                    issues.append(
                        f"{tech} uses {folder} grid position {position}; "
                        f"expected {EXPECTED_TECH_GRID_POSITIONS[tech]}"
                    )

        categories_match = re.search(r"\bcategories\s*=\s*\{([^{}]*)\}", block, re.S)
        if valid_categories and categories_match:
            for category in re.findall(r"[A-Za-z0-9_]+", categories_match.group(1)):
                if category not in valid_categories:
                    issues.append(f"{tech} uses invalid technology category {category}")

    return issues


def check_country_tag_database() -> list[str]:
    issues: list[str] = []
    tag_dir = ROOT / "common" / "country_tags"
    tags: dict[str, str] = {}
    dynamic_tags: set[str] = set()
    tag_pattern = re.compile(r'^\s*([A-Z][A-Z0-9]{2})\s*=\s*"([^"]+)"')

    for path in sorted(tag_dir.glob("*.txt")) if tag_dir.exists() else []:
        dynamic_mode = False
        for line in strip_comments(read_text(path)).splitlines():
            if re.match(r"^\s*dynamic_tags\s*=\s*yes\b", line):
                dynamic_mode = True
                continue
            match = tag_pattern.match(line)
            if not match:
                continue
            tag, country_file = match.groups()
            tags[tag] = country_file.replace("\\", "/")
            if dynamic_mode:
                dynamic_tags.add(tag)

    if len(tags) < MIN_COUNTRY_TAGS:
        issues.append(
            f"country tag database has {len(tags)} tags; at least {MIN_COUNTRY_TAGS} are required "
            "to avoid a zero-height flag atlas"
        )

    missing_dynamic = sorted(REQUIRED_DYNAMIC_TAGS - dynamic_tags)
    if missing_dynamic:
        issues.append(f"missing reserved dynamic country tags: {', '.join(missing_dynamic)}")

    for tag, country_file in sorted(tags.items()):
        if not (ROOT / "common" / country_file).exists():
            issues.append(f"country tag {tag} references missing common/{country_file}")

    return issues


def check_doctrine_folder_database() -> list[str]:
    folder_dir = ROOT / "common" / "doctrines" / "folders"
    defined: set[str] = set()
    for path in folder_dir.glob("*.txt") if folder_dir.exists() else []:
        defined.update(top_level_keys(strip_comments(read_text(path))))
    missing = sorted(REQUIRED_DOCTRINE_FOLDERS - defined)
    return [f"missing doctrine folder definition {folder}" for folder in missing]


def check_split_technology_layout() -> list[str]:
    issues: list[str] = []
    for rel_path in TECHNOLOGY_FILES + EQUIPMENT_FILES:
        if not (ROOT / rel_path).exists():
            issues.append(f"missing split framework file {rel_path}")

    legacy = ROOT / "common" / "technologies" / "ADISCORD_technologies.txt"
    if legacy.exists():
        text = re.sub(r"\s+", " ", strip_comments(read_text(legacy))).strip()
        if text not in {"", "technologies = { }"}:
            issues.append("common/technologies/ADISCORD_technologies.txt must be empty after split migration")
    return issues


def check_equipment_definitions(equipment: set[str]) -> list[str]:
    issues: list[str] = []
    for eq in EXPECTED_EQUIPMENT:
        if eq not in equipment:
            issues.append(f"missing equipment {eq}")
    return issues


def check_equipment_unlocks(tech_blocks: dict[str, str], equipment: set[str]) -> list[str]:
    issues: list[str] = []
    unlocked: set[str] = set()
    for block in tech_blocks.values():
        for match in re.finditer(r"\benable_equipments\s*=\s*\{([^{}]*)\}", block, re.S):
            unlocked.update(re.findall(r"[A-Za-z0-9_]+", match.group(1)))

    for eq in sorted(unlocked):
        if eq not in equipment:
            issues.append(f"technology unlocks undefined equipment {eq}")

    required_unlocks = {
        "infantry_equipment_0",
        "ADISCORD_squad_weapons_equipment_0",
        "support_equipment_1",
        "artillery_equipment_1",
        "train_equipment_1",
        "armored_train_equipment_1",
        "railway_gun_equipment_1",
        "ADISCORD_light_combat_platform_2163",
        "ADISCORD_fighter_airframe_2163",
    }
    for eq in sorted(required_unlocks - unlocked):
        issues.append(f"no technology unlocks required equipment {eq}")

    return issues


def check_equipment_parser_constraints() -> list[str]:
    issues: list[str] = []
    invalid_air_stats = {
        "agility": "air_agility",
        "range": "air_range",
        "ground_attack": "air_ground_attack",
    }

    for rel_path in EQUIPMENT_FILES:
        path = ROOT / rel_path
        if not path.exists():
            continue
        text = strip_comments(read_text(path))
        for invalid, replacement in invalid_air_stats.items():
            for match in re.finditer(rf"\b{invalid}\s*=", text):
                issues.append(
                    f"{rel_path}:{line_for_offset(text, match.start())}: "
                    f"use {replacement}, not {invalid}"
                )

    air_path = ROOT / "common" / "units" / "equipment" / "ADISCORD_air_equipment.txt"
    if air_path.exists():
        air_text = strip_comments(read_text(air_path))
        for equipment, frame in REQUIRED_AIR_MAP_ICON_FRAMES.items():
            match = re.search(rf"\b{re.escape(equipment)}\s*=\s*\{{", air_text)
            if not match:
                continue
            block = extract_block(air_text, match.start())
            if not re.search(rf"\bair_map_icon_frame\s*=\s*{frame}\b", block):
                issues.append(f"{equipment} must use air_map_icon_frame = {frame}")
    return issues


def check_platform_equipment_architecture() -> list[str]:
    issues: list[str] = []
    blocks = collect_equipment_blocks()
    expected_archetypes = {
        "ADISCORD_light_combat_platform_2163": "ADISCORD_recon_platform_archetype",
        "ADISCORD_recon_drone_carrier_2170": "ADISCORD_recon_platform_archetype",
        "ADISCORD_combat_platform_2170": "ADISCORD_combat_platform_archetype",
        "ADISCORD_combat_platform_2183": "ADISCORD_combat_platform_archetype",
        "ADISCORD_combat_platform_2200": "ADISCORD_combat_platform_archetype",
        "ADISCORD_heavy_combat_platform_2183": "ADISCORD_heavy_platform_archetype",
        "ADISCORD_heavy_combat_platform_2200": "ADISCORD_heavy_platform_archetype",
        "ADISCORD_repair_platform_2183": "ADISCORD_recovery_platform_archetype",
    }
    for archetype in sorted(set(expected_archetypes.values())):
        block = blocks.get(archetype, "")
        if not block or not re.search(r"\bis_archetype\s*=\s*yes\b", block):
            issues.append(f"missing platform archetype {archetype}")

    actual_archetype_by_variant: dict[str, str] = {}
    for equipment, block in blocks.items():
        match = re.search(r"\barchetype\s*=\s*([A-Za-z0-9_]+)", block)
        if match:
            actual_archetype_by_variant[equipment] = match.group(1)
    for variant, expected in expected_archetypes.items():
        actual = actual_archetype_by_variant.get(variant)
        if actual != expected:
            issues.append(f"{variant} uses archetype {actual}; expected {expected}")
        block = blocks.get(variant, "")
        parent_match = re.search(r"\bparent\s*=\s*([A-Za-z0-9_]+)", block)
        if parent_match:
            parent = parent_match.group(1)
            parent_archetype = actual_archetype_by_variant.get(parent)
            if parent_archetype != expected:
                issues.append(
                    f"{variant} has cross-archetype parent {parent} ({parent_archetype})"
                )

    for removed in (
        "ADISCORD_command_equipment_2183",
        "ADISCORD_combat_engineer_equipment_2170",
    ):
        if removed in blocks:
            issues.append(f"obsolete production-only variant still defined: {removed}")
    return issues


def check_resource_building_architecture(tech_blocks: dict[str, str]) -> list[str]:
    issues: list[str] = []
    buildings = collect_building_blocks()
    required = {
        "ADISCORD_metallurgical_complex": (28000, "steel"),
        "ADISCORD_electrolysis_complex": (30000, "aluminium"),
        "ADISCORD_strategic_mining_complex": (34000, "tungsten"),
        "ADISCORD_thermal_power_complex": (24000, "coal"),
    }
    for building, (minimum_cost, resource) in required.items():
        block = buildings.get(building, "")
        if not block:
            issues.append(f"missing strategic resource building {building}")
            continue
        cost_match = re.search(r"\bbase_cost\s*=\s*(\d+)", block)
        cost = int(cost_match.group(1)) if cost_match else 0
        if cost < minimum_cost:
            issues.append(f"{building} costs {cost}; expected at least {minimum_cost}")
        if not re.search(rf"\blocal_resources_{resource}\s*=\s*[1-9]\d*", block):
            issues.append(f"{building} does not produce {resource}")
        for pattern, label in (
            (r"\bhide_if_missing_tech\s*=\s*yes\b", "hide_if_missing_tech"),
            (r"\bstate_max\s*=\s*1\b", "state_max = 1"),
            (r"\bshares_slots\s*=\s*yes\b", "shares_slots = yes"),
            (r"\bgroup_by\s*=\s*ADISCORD_resource_complexes\b", "shared resource-complex cap"),
            (r"\bstate_production_speed_buildings_factor\s*=\s*-0\.0[5-9]", "regional construction penalty"),
        ):
            if not re.search(pattern, block):
                issues.append(f"{building} is missing {label}")
        icon_match = re.search(r"\bicon_frame\s*=\s*(\d+)", block)
        if icon_match and int(icon_match.group(1)) > 31:
            issues.append(f"{building} uses out-of-range building icon frame {icon_match.group(1)}")

    expected_unlocks = {
        tech: {(building, level) for building, level in entries}
        for tech, entries in GENERATED_ENABLE_BUILDINGS.items()
    }
    for tech, expected in expected_unlocks.items():
        block = tech_blocks.get(tech, "")
        actual: set[tuple[str, int]] = set()
        for match in re.finditer(r"\benable_building\s*=\s*\{", block):
            effect = extract_block(block, match.start())
            building_match = re.search(r"\bbuilding\s*=\s*([A-Za-z0-9_]+)", effect)
            level_match = re.search(r"\blevel\s*=\s*(\d+)", effect)
            if building_match and level_match:
                actual.add((building_match.group(1), int(level_match.group(1))))
        if actual != expected:
            issues.append(f"{tech} building unlocks are {sorted(actual)}; expected {sorted(expected)}")
        for building, _ in actual:
            if building not in buildings:
                issues.append(f"{tech} unlocks undefined building {building}")

    expected_upgrades = {
        tech: set(entries)
        for tech, entries in GENERATED_BUILDING_RESOURCE_UPGRADES.items()
    }
    for tech, expected in expected_upgrades.items():
        block = tech_blocks.get(tech, "")
        actual: set[tuple[str, str, int]] = set()
        for match in re.finditer(r"\bmodify_building_resources\s*=\s*\{", block):
            effect = extract_block(block, match.start())
            building_match = re.search(r"\bbuilding\s*=\s*([A-Za-z0-9_]+)", effect)
            resource_match = re.search(r"\bresource\s*=\s*([A-Za-z0-9_]+)", effect)
            amount_match = re.search(r"\bamount\s*=\s*(-?\d+)", effect)
            if building_match and resource_match and amount_match:
                actual.add((building_match.group(1), resource_match.group(1), int(amount_match.group(1))))
        if actual != expected:
            issues.append(f"{tech} resource upgrades are {sorted(actual)}; expected {sorted(expected)}")
    return issues


def check_infantry_visual_model_chain() -> list[str]:
    issues: list[str] = []
    equipment_path = (
        ROOT / "common" / "units" / "equipment" / "ADISCORD_infantry_equipment.txt"
    )
    if not equipment_path.exists():
        return ["ADISCORD infantry equipment file missing"]

    text = strip_comments(read_text(equipment_path))
    expected_levels = {
        "infantry_equipment_0": 0,
        "ADISCORD_infantry_equipment_2170": 1,
        "ADISCORD_infantry_equipment_2183": 2,
        "ADISCORD_infantry_equipment_2200": 3,
    }
    for equipment, expected_level in expected_levels.items():
        match = re.search(rf"(?m)^\s*{re.escape(equipment)}\s*=\s*\{{", text)
        if not match:
            issues.append(f"missing visual infantry equipment {equipment}")
            continue
        block = extract_block(text, match.start())
        level_match = re.search(r"\bvisual_level\s*=\s*(\d+)", block)
        actual_level = int(level_match.group(1)) if level_match else None
        if actual_level != expected_level:
            issues.append(
                f"{equipment} visual_level is {actual_level}; expected {expected_level}"
            )

    legacy_asset = ROOT / "gfx" / "units_infantry.asset"
    canonical_asset = ROOT / "gfx" / "entities" / "units_infantry.asset"
    if legacy_asset.exists():
        issues.append(
            "gfx/units_infantry.asset duplicates gfx/entities/units_infantry.asset"
        )
    if not canonical_asset.exists():
        issues.append("gfx/entities/units_infantry.asset missing")
    else:
        asset_text = read_text(canonical_asset)
        for entity in ("infantry_entity", "infantry_2_entity", "infantry_3_entity"):
            if not re.search(rf'\bname\s*=\s*"{entity}"', asset_text):
                issues.append(f"canonical infantry asset is missing {entity}")
    return issues


def collect_defined_subunits() -> set[str]:
    subunits: set[str] = set()
    units_dir = ROOT / "common" / "units"
    for path in units_dir.glob("*.txt") if units_dir.exists() else []:
        text = strip_comments(read_text(path))
        match = re.search(r"\bsub_units\s*=\s*\{", text)
        if match:
            subunits.update(top_level_keys(extract_block(text, match.start())))
    return subunits


def check_required_unit_definitions() -> list[str]:
    issues: list[str] = []
    used: dict[str, set[str]] = {}
    defined = collect_defined_subunits()

    for directory in ("history/units", "common/ai_templates"):
        for path in iter_text_files(directory):
            text = strip_comments(read_text(path))
            for block_match in re.finditer(r"\b(regiments|support)\s*=\s*\{", text):
                block = extract_block(text, block_match.start())
                for match in re.finditer(r"^\s*([A-Za-z0-9_-]+)\s*=", block, re.M):
                    subunit = match.group(1)
                    if subunit not in {"x", "y"}:
                        used.setdefault(subunit, set()).add(
                            f"{rel(path)}:{line_for_offset(text, block_match.start())}"
                        )

    required_units = {
        "fighter",
        "cas",
        "tac_bomber",
        "fake_intel_unit",
        "artillery",
        "anti_tank",
        "anti_air",
        "ADISCORD_militia",
        "ADISCORD_assault_infantry",
        "ADISCORD_recon_platform",
        "ADISCORD_combat_platform",
        "ADISCORD_heavy_platform",
        "ADISCORD_recovery_platform",
        "maintenance_company",
        "logistics_company",
        "signal_company",
        "field_hospital",
    }
    for subunit in sorted(set(used) | required_units):
        if subunit not in defined:
            locations = sorted(used.get(subunit, []))
            if locations:
                sample = ", ".join(locations[:3])
                suffix = "" if len(locations) <= 3 else f" (+{len(locations) - 3} more)"
                issues.append(f"missing subunit {subunit} used at {sample}{suffix}")
            else:
                issues.append(f"missing required engine/operation subunit {subunit}")

    return issues


def check_infantry_equipment_requirements() -> list[str]:
    path = ROOT / "common" / "units" / "ADISCORD_land_units.txt"
    if not path.exists():
        return ["common/units/ADISCORD_land_units.txt missing"]

    text = strip_comments(read_text(path))
    container_match = re.search(r"\bsub_units\s*=\s*\{", text)
    if not container_match:
        return ["ADISCORD_land_units.txt has no sub_units container"]
    container = extract_block(text, container_match.start())
    expected = {
        "ADISCORD_militia": {"infantry_equipment": 80},
        "infantry": {
            "infantry_equipment": 100,
            "ADISCORD_squad_weapons_equipment": 8,
        },
        "ADISCORD_assault_infantry": {
            "infantry_equipment": 100,
            "ADISCORD_squad_weapons_equipment": 14,
            "support_equipment": 5,
        },
        "mountaineers": {
            "infantry_equipment": 110,
            "ADISCORD_squad_weapons_equipment": 6,
        },
    }

    issues: list[str] = []
    for subunit, expected_need in expected.items():
        match = re.search(rf"(?m)^\s*{re.escape(subunit)}\s*=\s*\{{", container)
        if not match:
            issues.append(f"missing infantry subunit {subunit}")
            continue
        block = extract_block(container, match.start())
        need_match = re.search(r"\bneed\s*=\s*\{", block)
        if not need_match:
            issues.append(f"{subunit} has no equipment need")
            continue
        need_block = extract_block(block, need_match.start())
        actual_need = {
            key: float(value)
            for key, value in re.findall(
                r"(?m)^\s*([A-Za-z0-9_]+)\s*=\s*(-?\d+(?:\.\d+)?)",
                need_block,
            )
        }
        if actual_need != expected_need:
            issues.append(
                f"{subunit} needs {actual_need}; expected {expected_need}"
            )
    return issues


def check_new_support_and_platform_units() -> list[str]:
    path = ROOT / "common" / "units" / "ADISCORD_land_units.txt"
    if not path.exists():
        return ["common/units/ADISCORD_land_units.txt missing"]
    text = strip_comments(read_text(path))
    container_match = re.search(r"\bsub_units\s*=\s*\{", text)
    if not container_match:
        return ["ADISCORD_land_units.txt has no sub_units container"]
    container = extract_block(text, container_match.start())
    expected = {
        "ADISCORD_recon_platform": {
            "ADISCORD_recon_platform_archetype": 18,
            "support_equipment": 5,
        },
        "ADISCORD_combat_platform": {"ADISCORD_combat_platform_archetype": 40},
        "ADISCORD_heavy_platform": {"ADISCORD_heavy_platform_archetype": 32},
        "ADISCORD_recovery_platform": {
            "ADISCORD_recovery_platform_archetype": 12,
            "support_equipment": 15,
        },
        "maintenance_company": {"support_equipment": 25},
        "logistics_company": {"support_equipment": 25},
        "signal_company": {"support_equipment": 25},
        "field_hospital": {"support_equipment": 40},
    }
    issues: list[str] = []
    for subunit, expected_need in expected.items():
        match = re.search(rf"(?m)^\s*{re.escape(subunit)}\s*=\s*\{{", container)
        if not match:
            issues.append(f"missing new subunit {subunit}")
            continue
        block = extract_block(container, match.start())
        if not re.search(r"\bactive\s*=\s*no\b", block):
            issues.append(f"{subunit} must be technology-gated with active = no")
        need_match = re.search(r"\bneed\s*=\s*\{", block)
        actual_need: dict[str, float] = {}
        if need_match:
            need_block = extract_block(block, need_match.start())
            actual_need = {
                key: float(value)
                for key, value in re.findall(
                    r"(?m)^\s*([A-Za-z0-9_]+)\s*=\s*(-?\d+(?:\.\d+)?)",
                    need_block,
                )
            }
        if actual_need != expected_need:
            issues.append(f"{subunit} needs {actual_need}; expected {expected_need}")
    return issues


def check_script_enums(equipment: set[str]) -> list[str]:
    issues: list[str] = []
    path = ROOT / "common" / "script_enums.txt"
    if not path.exists():
        return ["common/script_enums.txt missing"]

    text = strip_comments(read_text(path))
    defined_enums = set(re.findall(r"^\s*(script_enum_[A-Za-z0-9_]+)\s*=\s*\{", text, re.M))
    for enum_name in sorted(REQUIRED_SCRIPT_ENUMS - defined_enums):
        issues.append(f"common/script_enums.txt missing {enum_name}")

    category_match = re.search(r"\bscript_enum_equipment_category\s*=\s*\{", text)
    bonus_match = re.search(r"\bscript_enum_equipment_bonus_type\s*=\s*\{", text)
    if not category_match:
        issues.append("common/script_enums.txt missing script_enum_equipment_category")
        categories: set[str] = set()
    else:
        categories = set(re.findall(r"\b[A-Za-z0-9_]+\b", extract_block(text, category_match.start())))

    if not bonus_match:
        return issues + ["common/script_enums.txt missing script_enum_equipment_bonus_type"]

    bonus_entries = set(re.findall(r"\b[A-Za-z0-9_]+\b", extract_block(text, bonus_match.start())))
    for eq in sorted(equipment - bonus_entries):
        issues.append(f"script_enum_equipment_bonus_type is missing equipment {eq}")

    allowed = equipment | categories
    for entry in sorted(bonus_entries - allowed):
        issues.append(f"script_enum_equipment_bonus_type references undefined equipment/category {entry}")

    return issues


def collect_script_enum_equipment_categories() -> set[str]:
    path = ROOT / "common" / "script_enums.txt"
    if not path.exists():
        return set()
    text = strip_comments(read_text(path))
    match = re.search(r"\bscript_enum_equipment_category\s*=\s*\{", text)
    if not match:
        return set()
    return set(re.findall(r"\b[A-Za-z0-9_]+\b", extract_block(text, match.start())))


def check_local_equipment_references(equipment: set[str]) -> list[str]:
    issues: list[str] = []
    valid = equipment | collect_script_enum_equipment_categories()

    for path in iter_text_files("common", "history/countries", "history/units"):
        text = strip_comments(read_text(path))
        location = rel(path)

        for match in re.finditer(r"\bhas_equipment\s*=\s*\{\s*([A-Za-z0-9_]+)\b", text):
            eq = match.group(1)
            if eq not in valid:
                issues.append(f"{location}:{line_for_offset(text, match.start())}: has_equipment references {eq}")

        if location.startswith("common/ai_strategy/"):
            for block_match in re.finditer(r"\bai_strategy\s*=\s*\{", text):
                block = extract_block(text, block_match.start())
                if "equipment_production" not in block and "equipment_variant_production" not in block:
                    continue
                id_match = re.search(r"\bid\s*=\s*([A-Za-z0-9_]+)", block)
                if id_match and id_match.group(1) not in valid:
                    issues.append(
                        f"{location}:{line_for_offset(text, block_match.start())}: "
                        f"equipment production strategy references {id_match.group(1)}"
                    )

        for match in re.finditer(r"\bequipment\s*=\s*\{[^{}]*\btype\s*=\s*([A-Za-z0-9_]+)", text, re.S):
            eq = match.group(1)
            if eq not in valid:
                issues.append(f"{location}:{line_for_offset(text, match.start())}: equipment type references {eq}")

        for match in re.finditer(r"\ballowed_ship_equipments\s*=\s*\{([^{}]*)\}", text, re.S):
            for eq in re.findall(r"\b[A-Za-z0-9_]+\b", match.group(1)):
                if eq not in valid:
                    issues.append(
                        f"{location}:{line_for_offset(text, match.start())}: "
                        f"allowed_ship_equipments references {eq}"
                    )

        if location.startswith(("common/country_leader/", "common/ideas/")):
            for bonus_match in re.finditer(r"\bequipment_bonus\s*=\s*\{", text):
                block = extract_block(text, bonus_match.start())
                for eq in top_level_keys(block):
                    if eq not in valid:
                        issues.append(
                            f"{location}:{line_for_offset(text, bonus_match.start())}: "
                            f"equipment_bonus references {eq}"
                        )

        if location.startswith("common/military_industrial_organization/"):
            for match in re.finditer(r"\b(?:equipment_type|limit_to_equipment_type)\s*=\s*\{([^{}]*)\}", text, re.S):
                for eq in re.findall(r"\b[A-Za-z0-9_]+\b", match.group(1)):
                    if eq not in valid:
                        issues.append(
                            f"{location}:{line_for_offset(text, match.start())}: "
                            f"MIO equipment reference {eq}"
                        )

    return issues


def check_total_conversion_technology_scope(defined_techs: set[str]) -> list[str]:
    vanilla_techs = sorted(tech for tech in defined_techs if not tech.startswith("ADISCORD_"))
    if not vanilla_techs:
        return []
    sample = ", ".join(vanilla_techs[:20])
    suffix = "" if len(vanilla_techs) <= 20 else f" (+{len(vanilla_techs) - 20} more)"
    return [f"common/technologies still defines vanilla technologies: {sample}{suffix}"]


def check_doctrine_parser_constraints() -> list[str]:
    issues: list[str] = []
    trigger_replacements = {
        "manpower": "has_manpower",
        "num_of_dockyards": "remove this condition or replace it with a valid scripted trigger",
        "num_of_convoys": "remove this condition or replace it with a valid scripted trigger",
    }

    for rel_path in NEW_DATA_FILES:
        path = ROOT / rel_path
        if not path.exists() or path.suffix.lower() != ".txt":
            continue
        text = strip_comments(read_text(path))

        for trigger, replacement in trigger_replacements.items():
            for match in re.finditer(rf"\b{trigger}\s*[<>]", text):
                issues.append(
                    f"{rel_path}:{line_for_offset(text, match.start())}: invalid trigger "
                    f"{trigger}; {replacement}"
                )

        for match in re.finditer(r"\bcategory_[A-Za-z0-9_]+\s*=\s*\{[^{}]*\battrition\s*=", text, re.S):
            issues.append(
                f"{rel_path}:{line_for_offset(text, match.start())}: attrition is not valid "
                "inside a unit category modifier block"
            )

        for match in re.finditer(r"\bcategory_tactical_bomber\s*=\s*\{", text):
            issues.append(
                f"{rel_path}:{line_for_offset(text, match.start())}: use category_tac_bomber, "
                "not category_tactical_bomber"
            )

        for match in re.finditer(r"\bsubmarine\s*=\s*\{[^{}]*\bvisibility\s*=", text, re.S):
            issues.append(
                f"{rel_path}:{line_for_offset(text, match.start())}: submarine visibility modifier "
                "is sub_visibility, not visibility"
            )

        if "/doctrines/tracks/" in rel_path:
            for mastery_match in re.finditer(r"\bmastery\s*=\s*\{", text):
                mastery_block = extract_block(text, mastery_match.start())
                equipment_match = re.search(r"\bequipment\s*=\s*\{([^{}]*)\}", mastery_block, re.S)
                if equipment_match:
                    for equipment in re.findall(r"[A-Za-z0-9_]+", equipment_match.group(1)):
                        if equipment not in VALID_DOCTRINE_MASTERY_EQUIPMENT:
                            issues.append(
                                f"{rel_path}:{line_for_offset(text, mastery_match.start())}: "
                                f"invalid doctrine mastery equipment category {equipment}"
                            )

        if "/doctrines/subdoctrines/" in rel_path:
            for key in top_level_keys(text):
                match = re.search(rf"\b{re.escape(key)}\s*=\s*\{{", text)
                if not match:
                    continue
                block = extract_block(text, match.start())
                if "rewards" not in block:
                    issues.append(f"{rel_path}:{line_for_offset(text, match.start())}: {key} has no rewards block")

    return issues


def check_technology_replace_path() -> list[str]:
    issues: list[str] = []
    descriptor_paths = [
        ROOT / "descriptor.mod",
        ROOT.parent / "A-Discord.mod",
    ]
    for path in descriptor_paths:
        if not path.exists():
            issues.append(f"missing descriptor {path}")
            continue
        text = read_text(path)
        for required in EXPECTED_DESCRIPTOR_REPLACE_PATHS:
            if required not in text:
                issues.append(
                    f"{rel(path) if path.is_relative_to(ROOT) else path.name} is missing {required}"
                )
    return issues


def check_technology_ui_years() -> list[str]:
    issues: list[str] = []
    gui_path = ROOT / "interface" / "countrytechtreeview.gui"
    if not gui_path.exists():
        return ["interface/countrytechtreeview.gui is missing"]

    text = strip_comments(read_text(gui_path))
    for match in LEGACY_TECH_UI_YEAR_RE.finditer(text):
        issues.append(
            f"interface/countrytechtreeview.gui:{line_for_offset(text, match.start())}: "
            f"legacy tech UI year {match.group(1)}"
        )

    for folder in SAFE_TECH_GRID_POSITIONS:
        folder_block = extract_named_container(text, folder)
        if not folder_block:
            issues.append(f"technology UI is missing folder container {folder}")
            continue
        for year in sorted(EXPECTED_TECH_UI_YEARS):
            count = len(re.findall(rf'\btext\s*=\s*"{year}"', folder_block))
            if count != 1:
                issues.append(f"{folder} has {count} labels for era {year}; expected exactly 1")

    return issues


def extract_named_container(text: str, name: str) -> str:
    for match in re.finditer(r"\bcontainerWindowType\s*=\s*\{", text):
        block = extract_block(text, match.start())
        name_match = re.search(r'\bname\s*=\s*"([^"]+)"', block)
        if name_match and name_match.group(1) == name:
            return block
    return ""


def check_technology_gridboxes(tech_blocks: dict[str, str]) -> list[str]:
    issues: list[str] = []
    gui_path = ROOT / "interface" / "countrytechtreeview.gui"
    if not gui_path.exists():
        return ["interface/countrytechtreeview.gui is missing ADISCORD technology branch gridboxes"]

    gui_text = strip_comments(read_text(gui_path))
    for template in (
        "techtree_industry_folder_item",
        "techtree_electronics_folder_item",
    ):
        block = extract_named_container(gui_text, template)
        if not block:
            issues.append(f"missing compact GUI template {template}")
        elif not re.search(
            r"\bsize\s*=\s*\{\s*width\s*=\s*72\s*height\s*=\s*72\s*\}",
            block,
        ):
            issues.append(f"{template} must use a compact 72x72 container")
    expected_gridboxes_by_folder: dict[str, set[str]] = {
        folder: {
            f"{branch.techs[0].id}_tree"
            for branch in GENERATED_BRANCHES
            if folder in branch.folders
        }
        for folder in SAFE_TECH_GRID_POSITIONS
    }

    incoming_count: dict[str, int] = {}
    expected_incoming_count: dict[str, int] = {}
    for branch in GENERATED_BRANCHES:
        graph = GENERATED_BRANCH_GRAPHS[branch.key]
        expected_folders = set(branch.folders)
        for targets in graph.successors:
            for target in targets:
                child = branch.techs[target].id
                expected_incoming_count[child] = expected_incoming_count.get(child, 0) + 1
        for index, tech_spec in enumerate(branch.techs):
            block = tech_blocks.get(tech_spec.id, "")
            if not block:
                continue
            actual_folders: set[str] = set()
            for folder_match in re.finditer(r"\bfolder\s*=\s*\{", block):
                folder_block = extract_block(block, folder_match.start())
                name_match = re.search(r"\bname\s*=\s*([A-Za-z0-9_]+)", folder_block)
                if name_match:
                    actual_folders.add(name_match.group(1))
            if actual_folders != expected_folders:
                issues.append(
                    f"{tech_spec.id} uses folders {sorted(actual_folders)}; "
                    f"expected {sorted(expected_folders)}"
                )

            lead_entries = re.findall(
                r"\bleads_to_tech\s*=\s*(ADISCORD_tech_[A-Za-z0-9_]+)", block
            )
            actual_leads = set(lead_entries)
            expected_leads = {
                branch.techs[target].id for target in graph.successors[index]
            }
            if actual_leads != expected_leads:
                issues.append(
                    f"{tech_spec.id} leads to {sorted(actual_leads)}; "
                    f"expected {sorted(expected_leads)}"
                )
            if len(lead_entries) != len(actual_leads):
                issues.append(f"{tech_spec.id} contains duplicate technology paths")
            for child in lead_entries:
                incoming_count[child] = incoming_count.get(child, 0) + 1

            actual_dependencies: set[str] = set()
            dependency_matches = list(re.finditer(r"\bdependencies\s*=\s*\{", block))
            if len(dependency_matches) > 1:
                issues.append(f"{tech_spec.id} has multiple dependencies blocks")
            for dependency_match in dependency_matches:
                dependency_block = extract_block(block, dependency_match.start())
                actual_dependencies.update(
                    re.findall(
                        r"(?m)^\s*(ADISCORD_tech_[A-Za-z0-9_]+)\s*=\s*1\b",
                        dependency_block,
                    )
                )
            extra_dependencies = GENERATED_EXTRA_TECH_DEPENDENCIES.get(
                tech_spec.id, ()
            )
            expected_parent_indices = graph.dependencies[index]
            if extra_dependencies:
                expected_parent_indices = tuple(
                    source
                    for source, targets in enumerate(graph.successors)
                    if index in targets
                )
            expected_dependencies = {
                branch.techs[parent].id for parent in expected_parent_indices
            }
            expected_dependencies.update(extra_dependencies)
            if actual_dependencies != expected_dependencies:
                issues.append(
                    f"{tech_spec.id} dependencies are {sorted(actual_dependencies)}; "
                    f"expected {sorted(expected_dependencies)}"
                )

            actual_xor: set[str] = set()
            xor_matches = list(re.finditer(r"\bXOR\s*=\s*\{", block))
            if len(xor_matches) > 1:
                issues.append(f"{tech_spec.id} has multiple XOR blocks")
            for xor_match in xor_matches:
                xor_block = extract_block(block, xor_match.start())
                actual_xor.update(
                    re.findall(r"\bADISCORD_tech_[A-Za-z0-9_]+\b", xor_block)
                )
            expected_xor: set[str] = set()
            for group in GENERATED_XOR_INDEX_GROUPS_BY_BRANCH.get(branch.key, ()):
                if index in group:
                    expected_xor.update(
                        branch.techs[sibling].id
                        for sibling in group
                        if sibling != index
                    )
            if actual_xor != expected_xor:
                issues.append(
                    f"{tech_spec.id} XOR is {sorted(actual_xor)}; "
                    f"expected {sorted(expected_xor)}"
                )

    for tech, expected_count in sorted(expected_incoming_count.items()):
        actual_count = incoming_count.get(tech, 0)
        if actual_count != expected_count:
            issues.append(
                f"{tech} has {actual_count} incoming paths; expected {expected_count}"
            )

    for folder, expected in expected_gridboxes_by_folder.items():
        folder_block = extract_named_container(gui_text, folder)
        direct_grid_blocks = top_level_blocks(folder_block, "gridboxtype")
        names = []
        for grid_block in direct_grid_blocks:
            name_match = re.search(r'\bname\s*=\s*"(ADISCORD_tech_[^"]+_tree)"', grid_block)
            if name_match:
                names.append(name_match.group(1))
        actual = set(names)
        duplicates = sorted(name for name in actual if names.count(name) > 1)
        for duplicate in duplicates:
            issues.append(f"{folder} contains duplicate gridbox {duplicate}")
        for missing in sorted(expected - actual):
            issues.append(f"missing {missing} gridbox in {folder}")
        for extra in sorted(actual - expected):
            issues.append(f"{extra} is in {folder} but no generated branch uses it")

        positions: dict[tuple[int, int], str] = {}
        for grid_block in direct_grid_blocks:
            name_match = re.search(r'\bname\s*=\s*"(ADISCORD_tech_[^"]+_tree)"', grid_block)
            pos_match = re.search(
                r"\bposition\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*y\s*=\s*(-?\d+)\s*\}",
                grid_block,
            )
            if not name_match or not pos_match:
                continue
            name = name_match.group(1)
            position = (int(pos_match.group(1)), int(pos_match.group(2)))
            if position in positions:
                issues.append(f"{folder} gridboxes {positions[position]} and {name} overlap at {position}")
            positions[position] = name
            if not re.search(r'\bformat\s*=\s*"LEFT"', grid_block):
                issues.append(f"{folder} gridbox {name} must use horizontal LEFT format")
            if not re.search(r"\bslotsize\s*=\s*\{\s*width\s*=\s*70\s*height\s*=\s*70\s*\}", grid_block):
                issues.append(f"{folder} gridbox {name} must use stable 70x70 slots")

    return issues


def check_local_technology_references(defined_techs: set[str]) -> list[str]:
    issues: list[str] = []
    references: dict[str, set[str]] = {}

    for root in LOCAL_TECH_REFERENCE_ROOTS:
        for path in iter_text_files(root):
            text = strip_comments(read_text(path))
            for match in re.finditer(r"\bhas_tech\s*=\s*([A-Za-z0-9_]+)", text):
                references.setdefault(match.group(1), set()).add(f"{rel(path)}:{line_for_offset(text, match.start())}")
            for set_match in re.finditer(r"\bset_technology\s*=\s*\{", text):
                block = extract_block(text, set_match.start())
                for tech in re.findall(r"^\s*([A-Za-z0-9_]+)\s*=", block, re.M):
                    if tech != "popup":
                        references.setdefault(tech, set()).add(f"{rel(path)}:{line_for_offset(text, set_match.start())}")
            for match in re.finditer(r"\bleads_to_tech\s*=\s*([A-Za-z0-9_]+)", text):
                references.setdefault(match.group(1), set()).add(f"{rel(path)}:{line_for_offset(text, match.start())}")

    for tech, locations in sorted(references.items()):
        if tech not in defined_techs:
            sample = ", ".join(sorted(locations)[:3])
            suffix = "" if len(locations) <= 3 else f" (+{len(locations) - 3} more)"
            issues.append(f"undefined technology reference {tech} at {sample}{suffix}")
    return issues


def check_campaign_technology_baseline(tech_blocks: dict[str, str]) -> list[str]:
    issues: list[str] = []
    path = ROOT / "common" / "scripted_effects" / "ADISCORD_technology_baseline_effects.txt"
    if not path.exists():
        return ["missing generated 2150 campaign technology baseline"]
    text = strip_comments(read_text(path))
    actual = set(re.findall(r"(?m)^\s*(ADISCORD_tech_[A-Za-z0-9_]+)\s*=\s*1\b", text))
    expected = {
        tech.id
        for branch in GENERATED_BRANCHES
        if not branch.profile.startswith("forbidden_")
        for tech, year in zip(branch.techs, branch.years)
        if year <= 2150
    }
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        issues.append(f"campaign baseline mismatch; missing={missing}, extra={extra}")
    on_action = ROOT / "common" / "on_actions" / "00_ADISCORD_on_actions.txt"
    if not on_action.exists() or "ADISCORD_grant_2150_technology_baseline = yes" not in read_text(on_action):
        issues.append("on_startup does not apply the generated 2150 technology baseline")
    for tech, block in tech_blocks.items():
        if re.search(r"\brepair_speed_factor\s*=", block):
            issues.append(
                f"{tech} uses ship repair_speed_factor; land reconstruction must use industry_repair_factor"
            )
    return issues


def check_campaign_dates_cover_technology_tree() -> list[str]:
    issues: list[str] = []
    defines = ROOT / "common" / "defines" / "ADISCORD_defines_changes.lua"
    bookmark = ROOT / "common" / "bookmarks" / "the_gathering_storm.txt"
    defines_text = read_text(defines) if defines.exists() else ""
    bookmark_text = read_text(bookmark) if bookmark.exists() else ""
    if not re.search(r'NDefines\.NGame\.START_DATE\s*=\s*"2160\.1\.1\.1"', defines_text):
        issues.append("campaign START_DATE must be 2160.1.1.1")
    end_match = re.search(r'NDefines\.NGame\.END_DATE\s*=\s*"(\d+)\.', defines_text)
    if not end_match or int(end_match.group(1)) < max(GENERATED_YEARS):
        issues.append("campaign END_DATE does not cover the 2200 technology generation")
    if not re.search(r"\bdate\s*=\s*2160\.1\.1\.12\b", bookmark_text):
        issues.append("default bookmark must start on 2160.1.1.12")
    return issues


def check_local_doctrine_references(
    grand: set[str],
    tracks: set[str],
    subdoctrines: set[str],
    top_level_doctrines: set[str],
) -> list[str]:
    issues: list[str] = []

    for root in LOCAL_DOCTRINE_REFERENCE_ROOTS:
        for path in iter_text_files(root):
            text = strip_comments(read_text(path))
            location = rel(path)

            for match in re.finditer(r"\bset_grand_doctrine\s*=\s*([A-Za-z0-9_]+)", text):
                doctrine = match.group(1)
                if doctrine not in grand:
                    issues.append(
                        f"{location}:{line_for_offset(text, match.start())}: "
                        f"set_grand_doctrine references undefined grand doctrine {doctrine}"
                    )

            for match in re.finditer(r"\bhas_doctrine\s*=\s*([A-Za-z0-9_]+)", text):
                doctrine = match.group(1)
                if doctrine not in top_level_doctrines:
                    issues.append(
                        f"{location}:{line_for_offset(text, match.start())}: "
                        f"has_doctrine references undefined or non-top-level doctrine {doctrine}"
                    )

            for match in re.finditer(r"\bhas_completed_subdoctrine\s*=\s*([A-Za-z0-9_]+)", text):
                doctrine = match.group(1)
                if doctrine not in subdoctrines:
                    issues.append(
                        f"{location}:{line_for_offset(text, match.start())}: "
                        f"has_completed_subdoctrine references undefined subdoctrine {doctrine}"
                    )

            for match in re.finditer(r"\bhas_completed_track\s*=\s*([A-Za-z0-9_]+)", text):
                track = match.group(1)
                if track not in tracks:
                    issues.append(
                        f"{location}:{line_for_offset(text, match.start())}: "
                        f"has_completed_track references undefined doctrine track {track}"
                    )

            for match in re.finditer(r"\b([A-Za-z0-9_]+)_mastery_gain_factor\s*=", text):
                modifier = match.group(1)
                if modifier in DOCTRINE_FOLDERS:
                    continue
                if modifier.endswith("_track"):
                    track = modifier[:-6]
                    if track in tracks or track in DOCTRINE_FOLDERS:
                        continue
                elif modifier in top_level_doctrines or modifier in subdoctrines:
                    continue
                issues.append(
                    f"{location}:{line_for_offset(text, match.start())}: "
                    f"mastery gain modifier references undefined doctrine or track {modifier}"
                )

    return issues


def check_braces() -> list[str]:
    issues: list[str] = []
    for rel_path in NEW_DATA_FILES:
        path = ROOT / rel_path
        if not path.exists() or path.suffix.lower() not in BRACE_EXTS:
            continue
        text = strip_comments(read_text(path))
        depth = 0
        for lineno, line in enumerate(text.splitlines(), 1):
            for ch in line:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth < 0:
                        issues.append(f"{rel_path}:{lineno}: extra closing brace")
                        depth = 0
        if depth:
            issues.append(f"{rel_path}: unbalanced braces, net +{depth}")
    return issues


def check_economy_spending() -> list[str]:
    issues: list[str] = []
    effects = ROOT / "common" / "scripted_effects" / "ADISCORD_economy_effects.txt"
    if not effects.exists():
        return ["common/scripted_effects/ADISCORD_economy_effects.txt missing"]
    text = strip_comments(read_text(effects))
    expected_spenders = {
        "ADISCORD_economy_repay_debt": -50,
        "ADISCORD_economy_stabilization_package": -100,
        "ADISCORD_economy_invest_reserves": -50,
        "ADISCORD_economy_civilian_investment_action": -50,
        "ADISCORD_economy_military_investment_action": -50,
    }
    for effect, value in expected_spenders.items():
        match = re.search(rf"\b{re.escape(effect)}\s*=\s*\{{", text)
        if not match:
            issues.append(f"{effect} is missing")
            continue
        block = extract_block(text, match.start())
        pattern = rf"add_to_variable\s*=\s*\{{[^{{}}]*var\s*=\s*ADISCORD_economy_treasury[^{{}}]*value\s*=\s*{value}\b"
        if not re.search(pattern, block, re.S):
            issues.append(f"{effect} does not subtract {abs(value)} treasury")
    return issues


def main() -> int:
    issues: list[str] = []

    missing_files = [path for path in NEW_DATA_FILES if not (ROOT / path).exists()]
    issues.extend(f"missing framework file {path}" for path in missing_files)

    techs, tech_blocks = collect_technologies()
    equipment = collect_equipment_keys()
    grand, tracks, subdoctrines, doctrine_blocks = collect_doctrine_keys()
    top_level_doctrines = grand | (subdoctrines & set(doctrine_blocks))
    triggers = collect_scripted_triggers()
    loc_keys = collect_localisation_keys()
    sprites = collect_sprite_names()

    for tech in EXPECTED_TECHS:
        if tech not in techs:
            issues.append(f"missing technology {tech}")
        for key in (tech, f"{tech}_desc"):
            if key not in loc_keys:
                issues.append(f"missing localisation {key}")
        sprite = f"GFX_{tech}_medium"
        if sprite not in sprites:
            issues.append(f"missing sprite {sprite}")
        elif not texture_exists(sprites[sprite]):
            issues.append(f"{sprite} points to missing texture {sprites[sprite]}")
        elif sprites[sprite] and not texture_has_valid_dimensions(sprites[sprite]):
            issues.append(f"{sprite} points to invalid or zero-sized DDS {sprites[sprite]}")

    # Effect-only technologies use 72x72 item templates.  Wide equipment and
    # ship silhouettes are valid only when the technology actually unlocks
    # equipment and therefore receives the corresponding large GUI item.
    for branch in GENERATED_BRANCHES:
        for tech_spec in branch.techs:
            if tech_spec.id in GENERATED_ENABLE_EQUIPMENT:
                continue
            sprite = f"GFX_{tech_spec.id}_medium"
            texture = sprites.get(sprite, "")
            dimensions = texture_dimensions(texture)
            if dimensions and (dimensions[0] > 72 or dimensions[1] > 72):
                issues.append(
                    f"{sprite} uses oversized effect-only texture {dimensions[0]}x{dimensions[1]}"
                )

    for trigger in EXPECTED_TRIGGERS:
        if trigger not in triggers:
            issues.append(f"missing scripted trigger {trigger}")

    all_doctrines = grand | subdoctrines
    for doctrine in EXPECTED_DOCTRINES:
        if doctrine not in all_doctrines:
            issues.append(f"missing doctrine {doctrine}")
        for key in (doctrine, f"{doctrine}_desc"):
            if key not in loc_keys:
                issues.append(f"missing localisation {key}")

    for track in EXPECTED_TRACKS:
        if track not in tracks:
            issues.append(f"missing doctrine track {track}")
        if track not in loc_keys:
            issues.append(f"missing localisation {track}")

    for tech in FORBIDDEN_TECHS:
        block = tech_blocks.get(tech, "")
        if "allow" not in block:
            issues.append(f"forbidden technology {tech} has no allow gate")
        if "ADISCORD_has_forbidden_legacy_access" not in block and "ADISCORD_has_black_grid_access" not in block:
            issues.append(f"forbidden technology {tech} lacks forbidden/black-grid access gate")
        if re.search(r"allow\s*=\s*\{\s*always\s*=\s*yes\s*\}", block):
            issues.append(f"forbidden technology {tech} is freely available")

    new_text = "\n".join(
        strip_comments(read_text(ROOT / path))
        for path in NEW_DATA_FILES
        if (ROOT / path).exists() and (ROOT / path).suffix.lower() in TEXT_EXTS
    )
    for tech in re.findall(r"\bhas_tech\s*=\s*(ADISCORD_tech_[A-Za-z0-9_]+)", new_text):
        if tech not in techs:
            issues.append(f"has_tech references undefined {tech}")

    for trigger in re.findall(r"\b(ADISCORD_has_[A-Za-z0-9_]+)\s*=\s*yes\b", new_text):
        if trigger not in triggers:
            issues.append(f"script references undefined trigger {trigger}")

    for track, block in doctrine_blocks.items():
        if track in subdoctrines:
            match = re.search(r"\btrack\s*=\s*([A-Za-z0-9_]+)", block)
            if match and match.group(1) not in tracks:
                issues.append(f"subdoctrine {track} references missing track {match.group(1)}")

    for tag in VANILLA_TAGS:
        if re.search(rf"\b(original_tag|tag|has_country_flag)\s*=\s*{tag}\b", new_text):
            issues.append(f"new framework hardcodes vanilla tag {tag}")

    issues.extend(check_split_technology_layout())
    issues.extend(check_country_tag_database())
    issues.extend(check_equipment_definitions(equipment))
    issues.extend(check_equipment_unlocks(tech_blocks, equipment))
    issues.extend(check_equipment_parser_constraints())
    issues.extend(check_platform_equipment_architecture())
    issues.extend(check_infantry_visual_model_chain())
    issues.extend(check_required_unit_definitions())
    issues.extend(check_infantry_equipment_requirements())
    issues.extend(check_new_support_and_platform_units())
    issues.extend(check_script_enums(equipment))
    issues.extend(check_local_equipment_references(equipment))
    issues.extend(check_technology_parser_constraints(tech_blocks))
    issues.extend(check_total_conversion_technology_scope(techs))
    issues.extend(check_technology_gridboxes(tech_blocks))
    issues.extend(check_resource_building_architecture(tech_blocks))
    issues.extend(check_doctrine_parser_constraints())
    issues.extend(check_doctrine_folder_database())
    issues.extend(check_technology_replace_path())
    issues.extend(check_technology_ui_years())
    issues.extend(check_local_technology_references(techs))
    issues.extend(check_campaign_technology_baseline(tech_blocks))
    issues.extend(check_campaign_dates_cover_technology_tree())
    issues.extend(check_local_doctrine_references(grand, tracks, subdoctrines, top_level_doctrines))
    issues.extend(check_braces())
    issues.extend(check_economy_spending())

    if issues:
        print("A-DISCORD technology/doctrine validation: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("A-DISCORD technology/doctrine validation: OK")
    print(f"Technologies: {len(EXPECTED_TECHS)}")
    print(f"Doctrines/subdoctrines: {len(EXPECTED_DOCTRINES)}")
    print(f"Tracks: {len(EXPECTED_TRACKS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
