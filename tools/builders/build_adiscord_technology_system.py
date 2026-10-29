from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
import json
import re
from PIL import Image

from tools.lib.paths import repository_root
from tools.lib.adiscord_remainder_countries import COUNTRIES as REMAINDER_COUNTRIES
from tools.builders.build_adiscord_technology_ui_assets import (
    SPECIAL_TECHNOLOGY_FOLDER,
    STATE_GFX_OUTPUT as TECHNOLOGY_STATE_GFX,
    apply_tree_skin,
    expected_technology_state_gfx_bytes as _ui_expected_technology_state_gfx_bytes,
    technology_tree_gfx_entries,
)

ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")


def expected_technology_state_gfx_bytes() -> bytes:
    """Share the UI builder's canonical state declaration without owning it."""
    return _ui_expected_technology_state_gfx_bytes()


def ensure_technology_state_gfx_current() -> None:
    """Reject state declaration drift without writing the UI-owned output."""
    expected = expected_technology_state_gfx_bytes()
    if (
        not TECHNOLOGY_STATE_GFX.is_file()
        or TECHNOLOGY_STATE_GFX.read_bytes() != expected
    ):
        raise RuntimeError(
            "technology state GFX is stale; run "
            "python -B -m tools.builders.build_adiscord_technology_ui_assets --apply"
        )


# The campaign starts in 2160. Keep only a short recovered baseline before
# that date, place the overwhelming majority of research in the playable
# 2160-2175 window, and leave one small 2180 endgame generation. Dense playable
# eras avoid decades of empty waiting between otherwise interesting nodes.
LEGACY_YEARS = (
    2100,
    2120,
    2140,
    2150,
    2160,
    2162,
    2164,
    2166,
    2168,
    2170,
    2173,
    2176,
    2179,
    2182,
    2185,
    2188,
    2191,
    2194,
    2197,
    2200,
)
YEARS = (
    2150,
    2155,
    2158,
    2160,
    2161,
    2162,
    2163,
    2164,
    2165,
    2166,
    2167,
    2168,
    2169,
    2170,
    2171,
    2172,
    2173,
    2174,
    2175,
    2180,
)
LEGACY_TO_CAMPAIGN_YEAR = dict(zip(LEGACY_YEARS, YEARS, strict=True))
MILESTONE_YEARS = tuple(
    LEGACY_TO_CAMPAIGN_YEAR[year] for year in (2100, 2120, 2140, 2160, 2170, 2182, 2200)
)
# Every branch displays its own chronological labels. Vertical lanes keep
# compact generations adjacent even when their research dates are years apart.
YEAR_TO_Y = {year: index for index, year in enumerate(YEARS)}
GRID_X = 150
GRID_Y = 130
GRID_SLOT = 70
YEAR_LABEL_WIDTH = 56
YEAR_LABEL_HEIGHT = 22
# Line segments tile on a 70px square. Wider row spacing uses whole cells so
# connector ends still meet; two cells also leave room for 84px equipment cards.
HORIZONTAL_LANE_SLOT_MULTIPLIER = 2
LANE_SLOT_MULTIPLIER = 3
CIVIL_LANE_SLOT_MULTIPLIER = 2
VERTICAL_PROGRAMME_GAP_SLOTS = 2
CIVIL_TECHNOLOGY_FILES = frozenset({"ADISCORD_industry.txt", "ADISCORD_electronics.txt"})
BRANCH_GAP = 90
INFANTRY_BRANCH_GAP = 30
HORIZONTAL_YEAR_SLOT_MULTIPLIER = 3
# A one-slot step puts a 72px icon 70px from its neighbour and leaves no room for
# the connector, so vertical tabs spend two slots per rung exactly as vanilla
# does. Left-to-right tabs already spend three because their cards are 183px wide.
VERTICAL_YEAR_SLOT_MULTIPLIER = 2
HORIZONTAL_FOLDERS = frozenset(
    {
        "infantry_folder",
        "armour_folder",
        "nsb_armour_folder",
        "naval_folder",
        "mtgnavalfolder",
    }
)


@dataclass(frozen=True)
class Tech:
    key: str
    ru: str
    en: str
    icon: str
    effects: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return f"ADISCORD_tech_{self.key}"


@dataclass(frozen=True)
class Branch:
    key: str
    file: str
    folders: tuple[str, ...]
    ru: str
    en: str
    profile: str
    techs: tuple[Tech, ...]
    years: tuple[int, ...] = MILESTONE_YEARS

    def __post_init__(self) -> None:
        if len(self.techs) != len(self.years):
            raise ValueError(
                f"{self.key}: {len(self.techs)} techs for {len(self.years)} years"
            )


@dataclass(frozen=True)
class BranchGraph:
    """Visual and prerequisite graph for one connected technology component."""

    lanes: tuple[int, ...]
    successors: tuple[tuple[int, ...], ...]
    dependencies: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        count = len(self.lanes)
        if len(self.successors) != count or len(self.dependencies) != count:
            raise ValueError("Technology graph arrays have different lengths")
        if any(lane < 0 for lane in self.lanes):
            raise ValueError("Technology graph lanes must be non-negative")


def techs(rows: str) -> tuple[Tech, ...]:
    result: list[Tech] = []
    for raw in rows.strip().splitlines():
        key, ru, en, icon = (part.strip() for part in raw.split("|"))
        result.append(Tech(key, ru, en, icon))
    return tuple(result)


BRANCHES = (
    Branch(
        "reconstruction",
        "ADISCORD_industry.txt",
        ("industry_folder",),
        "Реконструкция",
        "Reconstruction",
        "construction",
        techs(
            """
salvage_standards|Стандарты утилизации|Salvage Standards|basic_machine_tools
ruin_workshops|Мастерские среди руин|Ruin Workshops|improved_machine_tools
reconstruction_bureaus|Бюро реконструкции|Reconstruction Bureaus|basic_construction
modular_rebuilding|Модульная застройка|Modular Rebuilding|improved_construction
prefabricated_districts|Сборные кварталы|Prefabricated Districts|advanced_construction
automated_civil_works|Автоматизированные стройки|Automated Civil Works|construction4
arcology_repair_networks|Ремонтные сети аркологий|Arcology Repair Networks|construction5
"""
        ),
    ),
    Branch(
        "production",
        "ADISCORD_industry.txt",
        ("industry_folder",),
        "Производство",
        "Production",
        "production",
        techs(
            """
standardized_machine_tools|Стандартные станки|Standardized Machine Tools|basic_machine_tools
interchangeable_components|Взаимозаменяемые узлы|Interchangeable Components|improved_machine_tools
industrial_cluster_planning|Промышленные кластеры|Industrial Cluster Planning|concentrated_industry1
automated_assembly|Автоматизированная сборка|Automated Assembly|assembly_line_production
predictive_maintenance|Предиктивное обслуживание|Predictive Maintenance|advanced_machine_tools
autonomous_factory_cells|Автономные заводские ячейки|Autonomous Factory Cells|flexible_line
distributed_manufacturing|Распределённое производство|Distributed Manufacturing|streamlined_line
"""
        ),
    ),
    Branch(
        "resources",
        "ADISCORD_industry.txt",
        ("industry_folder",),
        "Ресурсы и энергия",
        "Resources and Energy",
        "resources",
        techs(
            """
salvage_metallurgy|Утилизационная металлургия|Salvage Metallurgy|excavation1
grid_rationing|Нормирование энергосети|Grid Rationing|oil_processing
refinery_reclamation|Восстановление НПЗ|Refinery Reclamation|improved_oil_processing
logistics_hub_networks|Сети логистических узлов|Logistics Hub Networks|excavation2
synthetic_resource_cycles|Синтетические циклы|Synthetic Resource Cycles|rubber_processing
closed_loop_smelting|Замкнутая выплавка|Closed-loop Smelting|excavation4
strategic_material_recovery|Извлечение редких материалов|Strategic Material Recovery|excavation5
"""
        ),
    ),
    Branch(
        "finance",
        "ADISCORD_industry.txt",
        ("industry_folder",),
        "Финансы",
        "Public Finance",
        "finance",
        techs(
            """
basic_fiscal_records|Базовый фискальный учёт|Basic Fiscal Records|mechanical_computing
reconstruction_contracts|Контракты реконструкции|Reconstruction Contracts|basic_small_computer
state_debt_instruments|Государственные облигации|State Debt Instruments|improved_small_computer
reserve_management|Управление резервами|Reserve Management|basic_mainframe
fiscal_administration_1|Фискальная администрация I|Fiscal Administration I|improved_mainframe
fiscal_administration_2|Фискальная администрация II|Fiscal Administration II|advanced_mainframe
predictive_budgeting|Предиктивный бюджет|Predictive Budgeting|computing_machine
"""
        ),
    ),
    Branch(
        "administration",
        "ADISCORD_industry.txt",
        ("industry_folder",),
        "Государственное управление",
        "State Administration",
        "administration",
        techs(
            """
municipal_ledgers|Муниципальные реестры|Municipal Ledgers|mechanical_computing
tax_census_network|Сеть налоговой переписи|Tax Census Network|basic_small_computer
standard_civil_codes|Единые гражданские нормы|Standard Civil Codes|improved_small_computer
technical_institutes|Технические институты|Technical Institutes|computing_machine
automated_bureaucracy|Автоматизированная бюрократия|Automated Bureaucracy|basic_mainframe
automated_civil_registry|Автоматический реестр|Automated Civil Registry|improved_mainframe
predictive_administration|Предиктивное управление|Predictive Administration|advanced_mainframe
"""
        ),
    ),
    Branch(
        "civil_resilience",
        "ADISCORD_industry.txt",
        ("industry_folder",),
        "Гражданская устойчивость",
        "Civil Resilience",
        "civil",
        techs(
            """
modular_shelters|Модульные убежища|Modular Shelters|basic_construction
ration_distribution_systems|Распределение пайков|Ration Distribution Systems|basic_machine_tools
urban_radiation_sanitation|Дезактивация городов|Urban Radiation Sanitation|improved_construction
municipal_repair_depots|Муниципальные рембазы|Municipal Repair Depots|advanced_machine_tools
public_repair_corps|Общественные ремонтные корпуса|Public Repair Corps|construction4
population_resilience_planning|Устойчивость населения|Population Resilience Planning|construction5
civil_defense_networks|Комплексная гражданская оборона|Civil Defense Networks|concentrated_industry5
"""
        ),
    ),
    Branch(
        "power",
        "ADISCORD_electronics.txt",
        ("electronics_folder",),
        "Энергетика и реакторы",
        "Power and Reactors",
        "power",
        techs(
            """
local_grid_restoration|Локальные энергосети|Local Grid Restoration|electrical_mechanical_engineering
substation_networks|Восстановление подстанций|Substation Networks|radio
radiation_mapping|Радиационное картирование|Radiation Mapping|atomic_research
shielded_engineering_corps|Экранированная инженерия|Shielded Engineering Corps|nuclear_reactor
reactor_safety_protocols|Безопасность реакторов|Reactor Safety Protocols|improved_nuclear_reactor
microreactor_blocks|Массивы микрореакторов|Microreactor Blocks|advanced_nuclear_reactor
emergency_core_suppression|Аварийное глушение ядра|Emergency Core Suppression|special_project_nuclear_reactor
"""
        ),
    ),
    Branch(
        "signals",
        "ADISCORD_electronics.txt",
        ("electronics_folder",),
        "Связь и кибервойна",
        "Signals and Cyberwarfare",
        "signals",
        techs(
            """
mesh_command_networks|Ячеистые сети управления|Mesh Command Networks|radio
field_radio_networks|Полевые радиосети|Field Radio Networks|radio_detection
encryption_rebuild|Восстановление шифрования|Encryption Rebuild|encryption1
signal_intercept_arrays|Массивы радиоперехвата|Signal Intercept Arrays|decryption1
battlefield_analytics|Аналитика поля боя|Battlefield Analytics|encryption2
counterintelligence_filters|Автоматизация контрразведки|Counterintelligence Filters|decryption2
memetic_security_protocols|Протоколы меметической защиты|Memetic Security Protocols|encryption3
"""
        ),
    ),
    Branch(
        "computing",
        "ADISCORD_electronics.txt",
        ("electronics_folder",),
        "Вычисления и ИИ",
        "Computing and AI",
        "computing",
        techs(
            """
electromechanical_relays|Электромеханические реле|Electromechanical Relays|mechanical_computing
recovered_data_archives|Восстановленные архивы|Recovered Data Archives|computing_machine
recovered_semiconductors|Восстановленные полупроводники|Recovered Semiconductors|basic_small_computer
hardened_computers|Защищённые вычислители|Hardened Computers|improved_small_computer
predictive_logistics|Предиктивная логистика|Predictive Logistics|basic_mainframe
operational_ai_assistants|Операционные ИИ-ассистенты|Operational AI Assistants|improved_mainframe
strategic_ai_coordination|Стратегическая ИИ-координация|Strategic AI Coordination|advanced_mainframe
"""
        ),
    ),
    Branch(
        "forbidden_energy",
        "ADISCORD_forbidden.txt",
        ("electronics_folder",),
        "Запретная энергетика",
        "Forbidden Energy",
        "forbidden_energy",
        techs(
            """
old_generator_fragments|Фрагменты старого генератора|Old Generator Fragments|atomic_research
dead_reactor_salvage|Разбор мёртвых реакторов|Dead Reactor Salvage|nuclear_reactor
legacy_reactor_compactification|Компактификация реакторов|Legacy Reactor Compactification|improved_nuclear_reactor
dirty_energy_munitions|Боеприпасы грязной энергии|Dirty Energy Munitions|nuclear_bomb
singularity_cooling_systems|Сингулярное охлаждение|Singularity Cooling Systems|advanced_nuclear_reactor
black_grid_protocols|Протоколы чёрной энергосети|Black Grid Protocols|special_project_nuclear_reactor
"""
        ),
        (2164, 2166, 2168, 2170, 2173, 2180),
    ),
    Branch(
        "forbidden_automation",
        "ADISCORD_forbidden.txt",
        ("electronics_folder",),
        "Запретная автоматизация",
        "Forbidden Automation",
        "forbidden_automation",
        techs(
            """
self_repairing_industrial_swarms|Самовосстанавливающиеся рои|Self-repairing Industrial Swarms|flexible_line
neural_command_cores|Нейронные командные ядра|Neural Command Cores|improved_mainframe
forbidden_automation_doctrine|Доктрина запретной автоматизации|Forbidden Automation Doctrine|advanced_mainframe
"""
        ),
        (2168, 2172, 2180),
    ),
    Branch(
        "small_arms",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Личное оружие и боеприпасы",
        "Personal Weapons and Ammunition",
        "infantry",
        techs(
            """
postwar_weapon_standardization|Стандартизация оружия|Weapon Standardization|infantry_equipment_0
refurbished_receivers|Восстановленные ствольные коробки|Refurbished Receivers|infantry_weapons
standardized_cartridges|Стандартные боеприпасы|Standardized Cartridges|infantry_weapons2
smart_optics|Умная оптика|Smart Optics|night_vision1
modular_rifle_kits|Модульные оружейные комплекты|Modular Rifle Kits|infantry_weapons3
programmable_ammunition|Программируемые боеприпасы|Programmable Ammunition|infantry_at2
networked_service_rifles|Сетевые штурмовые комплексы|Networked Service Rifles|night_vision2
"""
        ),
    ),
    Branch(
        "squad_weapons",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Групповое оружие и огневая поддержка",
        "Crew-served Weapons and Fire Support",
        "squad",
        techs(
            """
belt_fed_recovery|Пулемёты с ленточным питанием|Belt-fed Machine Guns|support_weapons
squad_grenade_launchers|Стандартизация ленточных пулемётов|Standardized Belt-fed Machine Guns|support_weapons2
portable_at_cells|Противотанковое оружие расчёта|Crew-served Anti-tank Weapons|infantry_at
field_ew_units|Прицелы группового оружия|Crew-served Weapon Sights|support_weapons3
networked_command_terminals|Терминалы управления огнём|Fire-control Terminals|signal_company
autonomous_support_weapons|Автоматизированные огневые установки|Automated Fire-support Mounts|support_weapons4
swarm_fireteams|Единая сеть огневой поддержки|Integrated Fire-support Network|special_forces
"""
        ),
    ),
    Branch(
        "protection",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Защита и медицина",
        "Protection and Medicine",
        "protection",
        techs(
            """
composite_protection_kits|Композитные бронежилеты|Composite Body Armour|tech_engineers
trauma_plates|Амортизирующие вкладыши брони|Armour Trauma Pads|tech_field_hospital
sealed_combat_suits|Герметичные боевые костюмы|Sealed Combat Suits|tech_engineers2
battlefield_medical_drones|Медицинские дроны|Battlefield Medical Drones|tech_field_hospital2
exoskeleton_load_frames|Экзоскелетные рамы|Exoskeleton Load Frames|tech_engineers3
adaptive_camouflage|Адаптивная маскировка|Adaptive Camouflage|tech_recon3
assault_sapper_kits|Комплекты штурмовых сапёров|Assault Sapper Kits|tech_engineers4
"""
        ),
    ),
    Branch(
        "special_forces",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Разведка и спецназ",
        "Reconnaissance and Special Forces",
        "special_forces",
        techs(
            """
fieldcraft_manuals|Полевая подготовка разведчиков|Scout Fieldcraft Training|tech_recon
urban_breaching|Инструменты штурмового вскрытия|Assault Breaching Tools|special_forces
radiation_patrols|Разведка заражённой местности|Contaminated-area Reconnaissance|tech_recon2
combat_recon_drones|Разведывательные дроны|Combat Recon Drones|paratroopers
vertical_assault_training|Высотная штурмовая подготовка|Vertical Assault Training|paratroopers2
deep_recon_cells|Группы дальней разведки|Long-range Reconnaissance Teams|tech_recon4
augmented_special_forces|Экзоскелеты спецназа|Special Forces Exoskeletons|paratroopers3
"""
        ),
    ),
    Branch(
        "field_support",
        "ADISCORD_logistics_trains.txt",
        ("support_folder",),
        "Комплекты и ремонт",
        "Equipment Kits and Maintenance",
        "support",
        techs(
            """
field_workshop_tools|Инструменты полевых мастерских|Field Workshop Tools|tech_maintenance_company
modular_support_kits|Модульные комплекты обеспечения|Modular Support Kits|tech_engineers
combat_engineering_sections|Инженерно-штурмовые отделения|Combat Engineering Sections|tech_engineers2
casualty_evacuation|Эвакуация раненых|Casualty Evacuation|tech_field_hospital2
remote_repair_teams|Дистанционные ремонтные группы|Remote Repair Teams|tech_maintenance_company3
autonomous_recovery|Автономная эвакуация техники|Autonomous Recovery|tech_maintenance_company4
self_sustaining_support|Самодостаточное обеспечение|Self-sustaining Support|tech_logistics_company4
"""
        ),
    ),
    Branch(
        "logistics",
        "ADISCORD_logistics_trains.txt",
        ("support_folder",),
        "Моторизация и логистика",
        "Motorization and Logistics",
        "logistics",
        techs(
            """
pack_transport|Вьючный транспорт|Pack Transport|tech_logistics_company
restored_truck_fleets|Восстановленные автоколонны|Restored Truck Fleets|motorized_infantry
standardized_transport_columns|Стандартные транспортные колонны|Standardized Transport Columns|tech_logistics_company2
forward_supply_hubs|Передовые узлы снабжения|Forward Supply Hubs|tech_signal_company2
hardened_logistics_nodes|Защищённые логистические узлы|Hardened Logistics Nodes|tech_logistics_company3
route_optimization_ai|ИИ маршрутизации|Route Optimization AI|tech_signal_company3
zero_loss_logistics|Безотходная логистика|Zero-loss Logistics|tech_signal_company4
"""
        ),
    ),
    Branch(
        "rail",
        "ADISCORD_logistics_trains.txt",
        ("support_folder",),
        "Железные дороги",
        "Railway Systems",
        "rail",
        techs(
            """
restored_rail_stock|Восстановленная тяга|Restored Rail Stock|train_tech
standard_gauge_recovery|Восстановление единой колеи|Standard Gauge Recovery|train_tech2
armored_rail_convoys|Бронированные эшелоны|Armored Rail Convoys|armored_train
railway_gun_reactivation|Реактивация железнодорожных орудий|Railway Gun Reactivation|railway_gun
rail_repair_corps|Корпуса ремонта путей|Rail Repair Corps|tech_engineers3
autonomous_rail_dispatch|Автономная диспетчеризация|Autonomous Rail Dispatch|train_tech3
over_the_horizon_fire_control|Загоризонтный огонь|Over-the-horizon Fire Control|railway_gun2
"""
        ),
    ),
    Branch(
        "artillery",
        "ADISCORD_artillery.txt",
        ("artillery_folder",),
        "Полевая артиллерия",
        "Field Artillery",
        "artillery",
        techs(
            """
restored_field_artillery|Восстановленная артиллерия|Restored Field Artillery|artillery1
recoil_recovery|Восстановление противооткатных систем|Recoil Recovery|artillery2
modular_gun_carriages|Модульные лафеты|Modular Gun Carriages|artillery3
smart_fire_control|Умное управление огнём|Smart Fire Control|artillery4
assisted_projectiles|Корректируемые снаряды|Assisted Projectiles|artillery5
drone_spotted_batteries|Дроновая корректировка|Drone-spotted Batteries|rocket_artillery2
autonomous_battery_network|Автономная батарейная сеть|Autonomous Battery Network|rocket_artillery4
"""
        ),
    ),
    Branch(
        "anti_tank",
        "ADISCORD_artillery.txt",
        ("artillery_folder",),
        "Противотанковые системы",
        "Anti-tank Systems",
        "anti_tank",
        techs(
            """
salvaged_at_guns|Трофейные противотанковые орудия|Salvaged Anti-tank Guns|antitank1
shaped_charges|Кумулятивные заряды|Shaped Charges|antitank2
tandem_warheads|Тандемные боевые части|Tandem Warheads|antitank3
scrap_at_launchers|Кустарные противотанковые орудия|Scrap Anti-tank Launchers|antitank4
top_attack_munitions|Боеприпасы верхней атаки|Top-attack Munitions|antitank5
coil_at_systems|Катушечные ускорители ПТО|Coil Anti-tank Systems|railgun
hypervelocity_at_networks|Сеть гиперскоростной ПТО|Hypervelocity Anti-tank Networks|special_project_land_railgun
"""
        ),
    ),
    Branch(
        "anti_air",
        "ADISCORD_artillery.txt",
        ("artillery_folder",),
        "Противовоздушная оборона",
        "Air Defense",
        "anti_air",
        techs(
            """
improvised_air_defense|Импровизированная ПВО|Improvised Air Defense|antiair1
radar_laying|Радиолокационное наведение|Radar Laying|antiair2
proximity_fuzes|Радиовзрыватели|Proximity Fuzes|antiair3
point_defense_aa|Автопушки точечной обороны|Point-defense Air Defense|antiair4
networked_air_defense|Сетевая противовоздушная оборона|Networked Air Defense|antiair5
rail_assisted_aa|Рельсовые системы ПВО|Rail-assisted Air Defense|special_project_land_railgun
directed_energy_air_defense|Энергетическая противовоздушная оборона|Directed-energy Air Defense|special_project_thermonuclear_bomb
"""
        ),
    ),
    Branch(
        "recon_armor",
        "ADISCORD_armor.txt",
        ("armour_folder", "nsb_armour_folder"),
        "Разведывательная бронетехника",
        "Reconnaissance Armor",
        "recon_armor",
        techs(
            """
restored_armored_chassis|Восстановленное лёгкое шасси|Restored Armored Chassis|gwtank
light_suspension|Облегчённая подвеска|Light Suspension|basic_light_tank
modular_recon_chassis|Модульное разведывательное шасси|Modular Recon Chassis|improved_light_tank
drone_recon_swarms|Беспилотные разведмашины|Drone Recon Swarms|advanced_light_tank
active_scouting_suites|Комплексы активной разведки|Active Scouting Suites|recon
unmanned_recon_vehicles|Необитаемые разведмашины|Unmanned Recon Vehicles|armored_car1
autonomous_recon_screen|Автономное разведывательное охранение|Autonomous Recon Screen|armored_car3
"""
        ),
    ),
    Branch(
        "combat_armor",
        "ADISCORD_armor.txt",
        ("armour_folder", "nsb_armour_folder"),
        "Основные боевые танки",
        "Main Battle Tanks",
        "combat_armor",
        techs(
            """
recovered_medium_chassis|Восстановленный основной боевой танк|Restored Main Battle Tank|basic_medium_tank
remote_weapon_stations|Дистанционно управляемые башенные установки|Remote-controlled Turret Mounts|improved_medium_tank
composite_armor_arrays|Массивы композитной брони|Composite Armor Arrays|advanced_medium_tank
semi_autonomous_combat_modules|Полуавтономное управление танком|Semi-autonomous Tank Control|basic_modern_tank
adaptive_fire_control|Адаптивное управление огнём|Adaptive Fire Control|improved_modern_tank
limited_battle_ai|Ограниченный боевой ИИ|Limited Battle AI|advanced_modern_tank
distributed_battlegroup|Распределённая бронегруппа|Distributed Battlegroup|generic_modern_tank
"""
        ),
    ),
    Branch(
        "heavy_armor",
        "ADISCORD_armor.txt",
        ("armour_folder", "nsb_armour_folder"),
        "Тяжёлые и автономные танки",
        "Heavy and Autonomous Tanks",
        "heavy_armor",
        techs(
            """
heavy_recovery_frames|Тяжёлые ремонтные рамы|Heavy Recovery Frames|basic_heavy_tank
reinforced_powertrains|Усиленные силовые установки|Reinforced Powertrains|improved_heavy_tank
heavy_composite_cores|Тяжёлые композитные ядра|Heavy Composite Cores|advanced_heavy_tank
remote_repair_sections|Дистанционные ремонтные машины|Remote Repair Sections|maintenance_company
heavy_platform_cores|Усиленный корпус тяжёлого танка|Reinforced Heavy Tank Hull|super_heavy_tank
autonomous_breakthrough_platforms|Автономные танки прорыва|Autonomous Breakthrough Tanks|main_battle_tank
siege_platform_networks|Сеть осадных танков|Networked Siege Tanks|land_cruiser
"""
        ),
    ),
    Branch(
        "fighter",
        "ADISCORD_air.txt",
        ("air_techs_folder", "bba_air_techs_folder"),
        "Истребительная авиация",
        "Fighter Aviation",
        "fighter",
        techs(
            """
reclaimed_jet_platforms|Восстановленные реактивные планеры|Reclaimed Jet Platforms|early_fighter
standardized_airframes|Стандартные планеры|Standardized Airframes|fighter1
pulse_doppler_radar|Импульсно-доплеровская РЛС|Pulse-Doppler Radar|fighter2
high_altitude_interceptors|Высотные перехватчики|High-altitude Interceptors|fighter3
thrust_vectoring|Управляемый вектор тяги|Thrust Vectoring|jet_fighter1
loyal_wingmen|Ведомые беспилотники|Loyal Wingmen|jet_fighter2
aerospace_interceptors|Воздушно-космические перехватчики|Aerospace Interceptors|special_project_air_icbm
"""
        ),
    ),
    Branch(
        "air_support",
        "ADISCORD_air.txt",
        ("air_techs_folder", "bba_air_techs_folder"),
        "Штурмовая авиация",
        "Air Support",
        "air_support",
        techs(
            """
battlefield_attack_aircraft|Самолёты поля боя|Battlefield Attack Aircraft|CAS1
guided_munitions|Управляемые боеприпасы|Guided Munitions|CAS2
armored_cockpits|Бронированные кабины|Armored Cockpits|CAS3
vtol_assault_frames|Ударные СВВП|VTOL Assault Frames|jet_CAS1
drone_air_wings|Беспилотная авиаподдержка|Drone Air Wings|jet_CAS2
autonomous_strike_wings|Автономные ударные крылья|Autonomous Strike Wings|special_project_air_guided_missile
persistent_air_support|Непрерывная воздушная поддержка|Persistent Air Support|special_project_air_nuclear_missile
"""
        ),
    ),
    Branch(
        "strategic_air",
        "ADISCORD_air.txt",
        ("air_techs_folder", "bba_air_techs_folder"),
        "Дальняя ударная авиация",
        "Long-range Strike Aviation",
        "strategic_air",
        techs(
            """
rocket_test_stands|Ракетные испытательные стенды|Rocket Test Stands|rocket_engines
inertial_guidance|Инерциальное наведение|Inertial Guidance|rocket_engines2
cruise_missiles|Крылатые ракеты|Cruise Missiles|guided_missile
strategic_rocket_architecture|Стратегическая ракетная артиллерия|Strategic Rocket Architecture|guided_missile2
orbital_tracking_relics|Орбитальные комплексы слежения|Orbital Tracking Relics|radio_detection
deep_strike_targeting|Координация глубоких ударов|Deep Strike Targeting|guided_missile3
suborbital_strike_systems|Суборбитальные ударные системы|Suborbital Strike Systems|special_project_air_icbm
"""
        ),
    ),
    Branch(
        "naval_support",
        "ADISCORD_naval.txt",
        ("naval_folder", "mtgnavalsupportfolder"),
        "Прибрежные силы и эскорт",
        "Littoral Forces and Escort",
        "naval_support",
        techs(
            """
restored_dockyards|Восстановленные верфи|Restored Dockyards|basic_destroyer
coastal_patrols|Прибрежные патрули|Coastal Patrols|improved_destroyer
convoy_routing|Маршрутизация конвоев|Convoy Routing|sonar1
escort_datalinks|Каналы связи эскорта|Escort Datalinks|sonar2
drone_pickets|Беспилотные дозоры|Drone Pickets|advanced_destroyer
autonomous_escorts|Автономные корабли эскорта|Autonomous Escorts|modern_destroyer
distributed_sea_control|Распределённый контроль моря|Distributed Sea Control|naval_radar4
"""
        ),
    ),
    Branch(
        "surface_fleet",
        "ADISCORD_naval.txt",
        ("naval_folder", "mtgnavalfolder"),
        "Надводный флот",
        "Surface Fleet",
        "surface_fleet",
        techs(
            """
recovered_fire_control|Восстановленное управление огнём|Recovered Fire Control|basic_light_cruiser
modular_hull_standards|Модульные стандарты корпусов|Modular Hull Standards|improved_light_cruiser
radar_gunnery|Радиолокационная стрельба|Radar Gunnery|basic_heavy_cruiser
missile_batteries|Корабельные ракетные батареи|Missile Batteries|advanced_heavy_cruiser
networked_task_groups|Сетевые оперативные группы|Networked Task Groups|basic_battleship
railgun_batteries|Корабельные рельсовые батареи|Railgun Batteries|advanced_battleship
horizon_fleet_command|Загоризонтное управление флотом|Horizon Fleet Command|modern_battleship
"""
        ),
    ),
    Branch(
        "subsurface",
        "ADISCORD_naval.txt",
        ("naval_folder", "mtgnavalfolder"),
        "Подводные силы",
        "Subsurface Forces",
        "subsurface",
        techs(
            """
sonar_archives|Архивы гидроакустики|Sonar Archives|basic_submarine
quiet_propulsion|Малошумные движители|Quiet Propulsion|improved_submarine
homing_torpedoes|Самонаводящиеся торпеды|Homing Torpedoes|torpedo1
air_independent_cells|Воздухонезависимые ячейки|Air-independent Cells|advanced_submarine
seabed_sensor_webs|Донные сенсорные сети|Seabed Sensor Webs|naval_mines1
autonomous_submarines|Автономные подлодки|Autonomous Submarines|modern_submarine
deep_ocean_denial|Глубоководное сдерживание|Deep-ocean Denial|naval_mines3
"""
        ),
    ),
)


from tools.lib.adiscord_technology_expansions_civil import (
    EXPANSIONS as CIVIL_EXPANSIONS,
)
from tools.lib.adiscord_technology_expansions_combat import (
    EXPANSIONS as COMBAT_EXPANSIONS,
)
from tools.lib.adiscord_technology_applied_programmes import (
    APPLIED_EFFECTS,
    APPLIED_PROGRAMMES,
    APPLIED_YEARS,
    LEADER_TRAINING,
)


LEGACY_MILESTONE_YEARS = (2100, 2120, 2140, 2160, 2170, 2182, 2200)
LEGACY_EXPANSION_YEARS = set(LEGACY_YEARS) - set(LEGACY_MILESTONE_YEARS)
DENSE_TECH_EXPANSIONS = {**CIVIL_EXPANSIONS, **COMBAT_EXPANSIONS}


def expand_dense_branch(branch: Branch) -> Branch:
    """Insert setting-specific technologies between the seven milestones."""

    if branch.profile.startswith("forbidden_"):
        return branch
    if branch.years != MILESTONE_YEARS:
        raise ValueError(f"{branch.key}: unexpected milestone years {branch.years}")
    additions = DENSE_TECH_EXPANSIONS.get(branch.key)
    if additions is None:
        raise ValueError(f"{branch.key}: missing dense technology expansion")
    if set(additions) != LEGACY_EXPANSION_YEARS:
        missing = sorted(LEGACY_EXPANSION_YEARS - set(additions))
        extra = sorted(set(additions) - LEGACY_EXPANSION_YEARS)
        raise ValueError(
            f"{branch.key}: bad expansion years; missing={missing}, extra={extra}"
        )

    by_year = dict(zip(MILESTONE_YEARS, branch.techs, strict=True))
    by_year.update(
        {
            LEGACY_TO_CAMPAIGN_YEAR[year]: Tech(*additions[year])
            for year in LEGACY_EXPANSION_YEARS
        }
    )
    return replace(branch, techs=tuple(by_year[year] for year in YEARS), years=YEARS)


regular_branch_keys = {
    branch.key for branch in BRANCHES if not branch.profile.startswith("forbidden_")
}
if set(DENSE_TECH_EXPANSIONS) != regular_branch_keys:
    missing = sorted(regular_branch_keys - set(DENSE_TECH_EXPANSIONS))
    extra = sorted(set(DENSE_TECH_EXPANSIONS) - regular_branch_keys)
    raise ValueError(f"Bad expansion branch set; missing={missing}, extra={extra}")

BRANCHES = tuple(expand_dense_branch(branch) for branch in BRANCHES)


# The resource branch is laid out as three coherent post-2160 programmes.
# IDs remain stable for saves and scripted references; only player-facing text
# is corrected, which is safe because equipment models are keyed by equipment
# visual_level rather than technology localisation.
TECH_TEXT_OVERRIDES = {
    "drone_recon_swarms": (
        "Программа Р-63 \"След\"",
        "R-63 “Trace” Programme",
    ),
    "active_scouting_suites": (
        "Контур Р-66 \"Эхо\"",
        "R-66 “Echo” Reconnaissance Loop",
    ),
    "semi_autonomous_combat_modules": (
        "Контур БТ-62 \"Вожак\"",
        "BT-62 “Lead” Control Loop",
    ),
    "autonomous_breakthrough_platforms": (
        "Программа Т-71 \"Таран\"",
        "T-71 “Ram” Programme",
    ),
    "siege_platform_networks": (
        "Контур Т-80 \"Жернов\"",
        "T-80 “Millstone” Siege Loop",
    ),
    "reclaimed_jet_platforms": (
        "Программа А-50 \"Искра\"",
        "A-50 “Spark” Programme",
    ),
    "battlefield_attack_aircraft": (
        "Программа АШ-50 \"Коршун\"",
        "AS-50 “Kite” Programme",
    ),
    "drone_air_wings": (
        "Контур А-65 \"Стая\"",
        "A-65 “Flock” Air-control Loop",
    ),
    "directed_energy_defensive_suites": (
        "Контур А-73 \"Призма\"",
        "A-73 “Prism” Defensive Loop",
    ),
    "suborbital_strike_systems": (
        "Программа Р-80 \"Стрела\"",
        "R-80 “Arrow” Programme",
    ),
    "refinery_catalyst_recovery": (
        "Сейсмическая томография залежей",
        "Seismic Deposit Tomography",
    ),
    "plasma_scrap_separation": (
        "Промышленный электролиз",
        "Industrial Electrolysis",
    ),
    "microbial_tailings_leaching": (
        "Микробиологическое извлечение металлов",
        "Microbial Metal Recovery",
    ),
    "high_pressure_polymer_synthesis": (
        "Высокобарическое восстановление руды",
        "High-Pressure Ore Reduction",
    ),
    # This remains a risky energy-storage programme, not an early bomb.
    # Preserve the internal key for saves while correcting the visible concept.
    "dirty_energy_munitions": (
        "Нестабильные изотопные накопители",
        "Unstable Isotope Storage",
    ),
}


def apply_tech_text_overrides(branch: Branch) -> Branch:
    changed = []
    for tech in branch.techs:
        override = TECH_TEXT_OVERRIDES.get(tech.key)
        changed.append(
            replace(tech, ru=override[0], en=override[1]) if override else tech
        )
    return replace(branch, techs=tuple(changed))


BRANCHES = tuple(apply_tech_text_overrides(branch) for branch in BRANCHES)


APPLIED_DESCRIPTION_RU_BY_BRANCH = {
    programme["key"]: programme["description_ru"] for programme in APPLIED_PROGRAMMES
}
APPLIED_DESCRIPTION_EN_BY_BRANCH = {
    programme["key"]: programme["description_en"] for programme in APPLIED_PROGRAMMES
}
APPLIED_DESCRIPTION_RU_BY_BRANCH["mechanized_mobility"] = (
    "развивает защищённую перевозку пехоты, боевые машины сопровождения и "
    "сетевое управление механизированными группами"
)
APPLIED_DESCRIPTION_EN_BY_BRANCH["mechanized_mobility"] = (
    "develops protected infantry transport, infantry fighting vehicles, and "
    "networked control of mechanized groups"
)
APPLIED_DESCRIPTION_RU_BY_BRANCH["amphibious_operations"] = (
    "увеличивает число десантных планов и дивизий в одной высадке, "
    "сокращает подготовку и улучшает высадку на вражеский берег"
)
APPLIED_DESCRIPTION_EN_BY_BRANCH["amphibious_operations"] = (
    "expands simultaneous invasion plans and divisions per landing, "
    "shortens preparation and improves landings on hostile shores"
)
APPLIED_PROGRAMME_KEYS = {programme["key"] for programme in APPLIED_PROGRAMMES}


def build_applied_branches() -> tuple[Branch, ...]:
    """Create optional side programmes without lengthening the main trunks."""

    return tuple(
        Branch(
            programme["key"],
            programme["file"],
            programme["folders"],
            programme["ru"],
            programme["en"],
            programme["profile"],
            tuple(Tech(*row) for row in programme["techs"]),
            tuple(programme.get("years", APPLIED_YEARS)),
        )
        for programme in APPLIED_PROGRAMMES
    )


BRANCHES += build_applied_branches()

# The historical ID catalogue supports offline checks of authored script
# references. It does not generate save-recovery effects or recurring hooks.
LEGACY_BRANCHES = BRANCHES
LEGACY_BRANCH_BY_KEY = {branch.key: branch for branch in LEGACY_BRANCHES}
LEGACY_TECH_BY_KEY = {
    tech.key: tech for branch in LEGACY_BRANCHES for tech in branch.techs
}


# Research rows bind dates, art and effects to stable IDs. Changing the visual
# layout must never change the reward attached to a technology.
def research_branch(
    key: str,
    file: str,
    folders: tuple[str, ...],
    ru: str,
    en: str,
    profile: str,
    rows: tuple[tuple[str, str, str, str, int, tuple[str, ...]], ...],
) -> Branch:
    return Branch(
        key,
        file,
        folders,
        ru,
        en,
        profile,
        tuple(Tech(row[0], row[1], row[2], row[3], tuple(row[5])) for row in rows),
        tuple(row[4] for row in rows),
    )


BRANCHES = (
    research_branch(
        "production",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Станки и автоматизация",
        "Machine Tools and Automation",
        "production",
        (
            (
                "standardized_machine_tools",
                "Стандартные станки",
                "Standardized Machine Tools",
                "basic_machine_tools",
                2150,
                (
                    "production_factory_max_efficiency_factor = 0.03",
                    "production_factory_efficiency_gain_factor = 0.02",
                ),
            ),
            (
                "interchangeable_components",
                "Взаимозаменяемые узлы",
                "Interchangeable Components",
                "improved_machine_tools",
                2155,
                (
                    "production_factory_start_efficiency_factor = 0.03",
                    "line_change_production_efficiency_factor = 0.04",
                ),
            ),
            (
                "industrial_cluster_planning",
                "Промышленные кластеры",
                "Industrial Cluster Planning",
                "concentrated_industry",
                2158,
                (
                    "production_speed_industrial_complex_factor = 0.03",
                    "production_speed_arms_factory_factor = 0.03",
                ),
            ),
            (
                "precision_metrology_recovery",
                "Восстановление точной метрологии",
                "Precision Metrology Recovery",
                "improved_machine_tools",
                2160,
                (
                    "production_factory_max_efficiency_factor = 0.04",
                    "production_factory_efficiency_gain_factor = 0.03",
                ),
            ),
            (
                "automated_assembly",
                "Автоматизированная сборка",
                "Automated Assembly",
                "assembly_line_production",
                2161,
                (
                    "industrial_capacity_factory = 0.015",
                    "production_factory_efficiency_gain_factor = 0.03",
                    "ADISCORD_economy_civilian_factory_income_factor = 0.02",
                ),
            ),
            (
                "numerical_machine_controls",
                "Станки с числовым управлением",
                "Numerical Machine Controls",
                "advanced_machine_tools",
                2162,
                (
                    "production_factory_max_efficiency_factor = 0.03",
                ),
            ),
            (
                "digital_tooling_libraries",
                "Цифровые библиотеки оснастки",
                "Digital Tooling Libraries",
                "advanced_machine_tools",
                2163,
                (
                    "production_factory_start_efficiency_factor = 0.05",
                    "line_change_production_efficiency_factor = 0.08",
                ),
            ),
            (
                "sensor_calibrated_machining",
                "Сенсорная калибровка станков",
                "Sensor-Calibrated Machining",
                "advanced_machine_tools",
                2163,
                (
                    "production_factory_max_efficiency_factor = 0.06",
                    "production_factory_efficiency_gain_factor = 0.04",
                ),
            ),
            (
                "modular_fixture_systems",
                "Модульные системы крепления",
                "Modular Fixture Systems",
                "flexible_line",
                2165,
                (
                    "line_change_production_efficiency_factor = 0.06",
                    "production_factory_start_efficiency_factor = 0.03",
                ),
            ),
            (
                "closed_loop_quality_control",
                "Замкнутый контроль качества",
                "Closed-loop Quality Control",
                "streamlined_line",
                2165,
                (
                    "production_factory_max_efficiency_factor = 0.04",
                    "production_factory_efficiency_gain_factor = 0.02",
                ),
            ),
            (
                "predictive_maintenance",
                "Предиктивное обслуживание",
                "Predictive Maintenance",
                "advanced_machine_tools",
                2167,
                (
                    "production_factory_efficiency_gain_factor = 0.05",
                    "industry_repair_factor = 0.04",
                    "ADISCORD_economy_military_factory_expense_factor = -0.02",
                ),
            ),
            (
                "flexible_robotic_tooling",
                "Гибкая роботизированная оснастка",
                "Flexible Robotic Tooling",
                "assembly_line_production",
                2169,
                (
                    "production_factory_efficiency_gain_factor = 0.03",
                    "line_change_production_efficiency_factor = 0.03",
                ),
            ),
            (
                "autonomous_factory_cells",
                "Автономные заводские ячейки",
                "Autonomous Factory Cells",
                "flexible_line",
                2172,
                (
                    "industrial_capacity_factory = 0.04",
                    "factory_energy_consumption = 0.06",
                    "production_factory_max_efficiency_factor = 0.06",
                    "ADISCORD_economy_civilian_factory_income_factor = 0.03",
                ),
            ),
            (
                "machine_vision_inspection",
                "Контроль машинным зрением",
                "Machine-vision Inspection",
                "advanced_machine_tools",
                2169,
                (
                    "industrial_capacity_factory = 0.03",
                    "production_factory_max_efficiency_factor = 0.03",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "industrial_digital_twin_control",
                "Цифровые модели производственных линий",
                "Production-line Digital Twins",
                "computing_machine",
                2177,
                (
                    "production_factory_efficiency_gain_factor = 0.03",
                    "ADISCORD_economy_military_factory_expense_factor = -0.02",
                ),
            ),
            (
                "distributed_manufacturing",
                "Распределённое производство",
                "Distributed Manufacturing",
                "streamlined_line",
                2180,
                (
                    "industrial_capacity_factory = 0.10",
                    "industrial_capacity_dockyard = 0.07",
                    "factory_energy_consumption = 0.12",
                    "production_factory_max_efficiency_factor = 0.09",
                ),
            ),
        ),
    ),
    research_branch(
        "industry_organization",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Организация промышленности",
        "Industrial Organization",
        "production",
        (
            (
                "industrial_organization_baseline",
                "Организация производственных сетей",
                "Production Network Organization",
                "basic_machine_tools",
                2160,
                (
                    "production_factory_start_efficiency_factor = 0.02",
                    "production_factory_efficiency_gain_factor = 0.02",
                ),
            ),
            (
                "concentrated_industrial_zones",
                "Концентрированные промышленные зоны",
                "Concentrated Industrial Zones",
                "basic_machine_tools",
                2162,
                (
                    "industrial_capacity_factory = 0.05",
                    "industrial_capacity_dockyard = 0.04",
                    "factory_energy_consumption = 0.10",
                    "industry_air_damage_factor = 0.07",
                ),
            ),
            (
                "distributed_workshop_networks",
                "Распределённые сети мастерских",
                "Distributed Workshop Networks",
                "basic_machine_tools",
                2162,
                (
                    "industrial_capacity_factory = 0.03",
                    "factory_energy_consumption = 0.02",
                    "production_factory_start_efficiency_factor = 0.07",
                    "industry_air_damage_factor = -0.08",
                ),
            ),
            (
                "integrated_factory_campuses",
                "Единые заводские площадки",
                "Integrated Factory Campuses",
                "concentrated_industry",
                2164,
                (
                    "industrial_capacity_factory = 0.03",
                    "production_speed_arms_factory_factor = 0.04",
                    "factory_energy_consumption = 0.04",
                ),
            ),
            (
                "regional_workshop_standards",
                "Стандарты региональных мастерских",
                "Regional Workshop Standards",
                "dispersed_industry",
                2164,
                (
                    "production_factory_start_efficiency_factor = 0.04",
                    "line_change_production_efficiency_factor = 0.04",
                ),
            ),
            (
                "megafactory_power_buses",
                "Энергоконтуры мегафабрик",
                "Megafactory Power Buses",
                "basic_machine_tools",
                2167,
                (
                    "industrial_capacity_factory = 0.07",
                    "industrial_capacity_dockyard = 0.05",
                    "factory_energy_consumption = 0.15",
                    "line_change_production_efficiency_factor = -0.12",
                ),
            ),
            (
                "regional_spare_capacity",
                "Региональный резерв мощностей",
                "Regional Spare Capacity",
                "basic_machine_tools",
                2167,
                (
                    "industrial_capacity_factory = 0.03",
                    "factory_energy_consumption = 0.02",
                    "line_change_production_efficiency_factor = 0.14",
                    "industry_repair_factor = 0.12",
                ),
            ),
            (
                "centralized_process_dispatch",
                "Центральная диспетчеризация производства",
                "Centralized Process Dispatch",
                "concentrated_industry3",
                2170,
                (
                    "industrial_capacity_factory = 0.04",
                    "industrial_capacity_dockyard = 0.03",
                    "factory_energy_consumption = 0.05",
                ),
            ),
            (
                "interregional_backup_contracts",
                "Межрегиональное резервирование заказов",
                "Interregional Backup Contracts",
                "dispersed_industry3",
                2170,
                (
                    "line_change_production_efficiency_factor = 0.05",
                    "industry_air_damage_factor = -0.05",
                    "industry_repair_factor = 0.04",
                ),
            ),
            (
                "continuous_casting_lines",
                "Линии непрерывного литья",
                "Continuous Casting Lines",
                "basic_machine_tools",
                2173,
                (
                    "industrial_capacity_factory = 0.09",
                    "production_factory_max_efficiency_factor = 0.07",
                    "factory_energy_consumption = 0.19",
                    "industry_air_damage_factor = 0.12",
                ),
            ),
            (
                "mobile_fabrication_convoys",
                "Мобильные производственные колонны",
                "Mobile Fabrication Convoys",
                "basic_machine_tools",
                2173,
                (
                    "industrial_capacity_factory = 0.04",
                    "factory_energy_consumption = 0.03",
                    "industry_air_damage_factor = -0.15",
                    "industry_repair_factor = 0.15",
                ),
            ),
            (
                "strategic_production_complexes",
                "Стратегические производственные комплексы",
                "Strategic Production Complexes",
                "basic_machine_tools",
                2180,
                (
                    "industrial_capacity_factory = 0.12",
                    "industrial_capacity_dockyard = 0.10",
                    "factory_energy_consumption = 0.24",
                    "industry_air_damage_factor = 0.20",
                    "line_change_production_efficiency_factor = -0.15",
                ),
            ),
            (
                "resilient_production_meshes",
                "Устойчивые производственные сети",
                "Resilient Production Meshes",
                "basic_machine_tools",
                2180,
                (
                    "industrial_capacity_factory = 0.06",
                    "factory_energy_consumption = 0.04",
                    "production_factory_start_efficiency_factor = 0.10",
                    "line_change_production_efficiency_factor = 0.22",
                    "industry_air_damage_factor = -0.20",
                    "industry_repair_factor = 0.22",
                ),
            ),
        ),
    ),
    research_branch(
        "reconstruction",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Строительство и восстановление",
        "Construction and Recovery",
        "construction",
        (
            (
                "salvage_standards",
                "Стандарты утилизации",
                "Salvage Standards",
                "basic_machine_tools",
                2150,
                (
                    "production_speed_buildings_factor = 0.02",
                    "industry_repair_factor = 0.02",
                ),
            ),
            (
                "ruin_workshops",
                "Мастерские среди руин",
                "Ruin Workshops",
                "improved_machine_tools",
                2155,
                (
                    "production_speed_buildings_factor = 0.02",
                    "industry_repair_factor = 0.03",
                ),
            ),
            (
                "reconstruction_bureaus",
                "Бюро реконструкции",
                "Reconstruction Bureaus",
                "basic_construction",
                2158,
                (
                    "production_speed_buildings_factor = 0.03",
                    "industry_repair_factor = 0.03",
                ),
            ),
            (
                "drone_construction_cartography",
                "Картография строительных дронов",
                "Construction Drone Cartography",
                "basic_construction",
                2160,
                (
                    "production_speed_buildings_factor = 0.03",
                    "production_speed_infrastructure_factor = 0.04",
                    "global_building_slots_factor = 0.10",
                ),
            ),
            (
                "standardized_utility_corridors",
                "Стандартные инженерные коридоры",
                "Standardized Utility Corridors",
                "improved_construction",
                2162,
                (
                    "global_building_slots_factor = 0.10",
                    "production_speed_infrastructure_factor = 0.03",
                ),
            ),
            (
                "modular_rebuilding",
                "Модульная застройка",
                "Modular Rebuilding",
                "improved_construction",
                2164,
                (
                    "production_speed_buildings_factor = 0.04",
                    "production_speed_industrial_complex_factor = 0.03",
                    "global_building_slots_factor = 0.10",
                ),
            ),
            (
                "serviced_industrial_sites",
                "Подготовленные промышленные площадки",
                "Serviced Industrial Sites",
                "construction3",
                2166,
                (
                    "global_building_slots_factor = 0.10",
                    "production_speed_arms_factory_factor = 0.03",
                ),
            ),
            (
                "compact_industrial_zoning",
                "Плотная промышленная застройка",
                "Compact Industrial Zoning",
                "concentrated_industry",
                2166,
                (
                    "global_building_slots_factor = 0.10",
                ),
            ),
            (
                "rapid_reconstruction_standards",
                "Стандарты скоростного восстановления",
                "Rapid Reconstruction Standards",
                "dispersed_industry",
                2166,
                (
                    "production_speed_buildings_factor = 0.05",
                    "industry_repair_factor = 0.10",
                ),
            ),
            (
                "prefabricated_districts",
                "Сборные кварталы",
                "Prefabricated Districts",
                "advanced_construction",
                2169,
                (
                    "production_speed_buildings_factor = 0.04",
                    "consumer_goods_factor = -0.02",
                    "global_building_slots_factor = 0.10",
                ),
            ),
            (
                "public_repair_corps",
                "Общественные ремонтные корпуса",
                "Public Repair Corps",
                "advanced_construction",
                2163,
                (
                    "industry_repair_factor = 0.08",
                    "industry_air_damage_factor = -0.05",
                ),
            ),
            (
                "multilevel_industrial_districts",
                "Многоуровневые промышленные районы",
                "Multilevel Industrial Districts",
                "construction4",
                2172,
                (
                    "global_building_slots_factor = 0.10",
                    "production_speed_industrial_complex_factor = 0.03",
                ),
            ),
            (
                "vertical_factory_districts",
                "Вертикальные заводские кварталы",
                "Vertical Factory Districts",
                "concentrated_industry5",
                2174,
                (
                    "global_building_slots_factor = 0.10",
                    "production_speed_infrastructure_factor = 0.03",
                ),
            ),
            (
                "resilient_utility_construction",
                "Восстанавливаемые инженерные сети",
                "Resilient Utility Construction",
                "dispersed_industry5",
                2174,
                (
                    "production_speed_buildings_factor = 0.05",
                    "industry_repair_factor = 0.10",
                    "industry_air_damage_factor = -0.05",
                ),
            ),
            (
                "automated_civil_works",
                "Автоматизированные стройки",
                "Automated Civil Works",
                "advanced_construction",
                2175,
                (
                    "production_speed_buildings_factor = 0.06",
                    "production_speed_industrial_complex_factor = 0.05",
                ),
            ),
            (
                "integrated_land_development",
                "Комплексное освоение территорий",
                "Integrated Land Development",
                "construction5",
                2176,
                (
                    "global_building_slots_factor = 0.10",
                    "production_speed_infrastructure_factor = 0.04",
                ),
            ),
            (
                "civil_defense_networks",
                "Комплексная гражданская оборона",
                "Civil Defense Networks",
                "concentrated_industry5",
                2178,
                (
                    "production_speed_buildings_factor = 0.06",
                    "production_speed_infrastructure_factor = 0.05",
                    "industry_repair_factor = 0.10",
                    "industry_air_damage_factor = -0.10",
                ),
            ),
            (
                "integrated_city_complexes",
                "Интегрированные городские комплексы",
                "Integrated City Complexes",
                "construction5",
                2180,
                (
                    "global_building_slots_factor = 0.10",
                    "production_speed_buildings_factor = 0.03",
                ),
            ),
        ),
    ),
    research_branch(
        "resources",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Ресурсы и энергия",
        "Resources and Energy",
        "resources",
        (
            (
                "salvage_metallurgy",
                "Утилизационная металлургия",
                "Salvage Metallurgy",
                "excavation1",
                2150,
                (
                    "local_resources_factor = 0.02",
                    "fuel_gain_factor = 0.012",
                ),
            ),
            (
                "grid_rationing",
                "Нормирование энергосети",
                "Grid Rationing",
                "oil_processing",
                2155,
                (
                    "local_resources_factor = 0.021",
                    "fuel_gain_factor = 0.012",
                ),
            ),
            (
                "refinery_reclamation",
                "Восстановление НПЗ",
                "Refinery Reclamation",
                "improved_oil_processing",
                2158,
                (
                    "local_resources_factor = 0.021",
                    "fuel_gain_factor = 0.013",
                ),
            ),
            (
                "spectral_ore_sorting",
                "Спектральная сортировка руды",
                "Spectral Ore Sorting",
                "excavation2",
                2160,
                (
                    "local_resources_factor = 0.022",
                    "fuel_gain_factor = 0.013",
                ),
            ),
            (
                "logistics_hub_networks",
                "Сети логистических узлов",
                "Logistics Hub Networks",
                "excavation2",
                2161,
                (
                    "local_resources_factor = 0.023",
                    "fuel_gain_factor = 0.013",
                ),
            ),
            (
                "borehole_sensor_grids",
                "Сети скважинных датчиков",
                "Borehole Sensor Grids",
                "excavation1",
                2162,
                (
                    "local_resources_factor = 0.023",
                    "fuel_gain_factor = 0.014",
                ),
            ),
            (
                "plasma_scrap_separation",
                "Промышленный электролиз",
                "Industrial Electrolysis",
                "excavation2",
                2163,
                (
                    "production_lack_of_resource_penalty_factor = -0.024",
                    "industry_repair_factor = 0.014",
                ),
            ),
            (
                "microbial_tailings_leaching",
                "Микробиологическое извлечение металлов",
                "Microbial Metal Recovery",
                "excavation4",
                2164,
                (
                    "local_resources_factor = 0.031",
                    "production_lack_of_resource_penalty_factor = -0.007",
                ),
            ),
            (
                "synthetic_resource_cycles",
                "Синтетические циклы",
                "Synthetic Resource Cycles",
                "rubber_processing",
                2166,
                (
                    "local_resources_factor = 0.026",
                    "fuel_gain_factor = 0.015",
                ),
            ),
            (
                "geothermal_brine_extraction",
                "Извлечение минералов из рассолов",
                "Geothermal Brine Extraction",
                "excavation3",
                2167,
                (
                    "local_resources_factor = 0.04",
                ),
            ),
            (
                "rare_earth_solvent_loops",
                "Замкнутые циклы редкоземельной экстракции",
                "Rare-Earth Solvent Loops",
                "excavation4",
                2169,
                (
                    "local_resources_factor = 0.028",
                    "fuel_gain_factor = 0.016",
                ),
            ),
            (
                "automated_deep_mining",
                "Автоматизированная глубокая добыча",
                "Automated Deep Mining",
                "excavation5",
                2171,
                (
                    "local_resources_factor = 0.036",
                    "production_lack_of_resource_penalty_factor = -0.008",
                ),
            ),
            (
                "carbon_feedstock_cracking",
                "Крекинг углеродного сырья",
                "Carbon Feedstock Cracking",
                "oil_processing",
                2172,
                (
                    "local_resources_factor = 0.017",
                    "fuel_gain_factor = 0.029",
                ),
            ),
            (
                "isotope_selective_refining",
                "Избирательное рафинирование сырья",
                "Selective Feedstock Refining",
                "excavation5",
                2174,
                (
                    "production_lack_of_resource_penalty_factor = -0.03",
                    "fuel_gain_factor = 0.03",
                ),
            ),
            (
                "strategic_element_reclamation",
                "Регенерация стратегических элементов",
                "Strategic Element Reclamation",
                "excavation5",
                2175,
                (
                    "local_resources_factor = 0.031",
                    "fuel_gain_factor = 0.018",
                ),
            ),
            (
                "strategic_material_recovery",
                "Извлечение редких материалов",
                "Strategic Material Recovery",
                "excavation5",
                2180,
                (
                    "local_resources_factor = 0.046",
                    "fuel_gain_factor = 0.026",
                    "production_lack_of_resource_penalty_factor = -0.026",
                ),
            ),
        ),
    ),
    research_branch(
        "synthetic_rubber",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Синт. резина",
        "Synthetic Rubber",
        "resources",
        (
            (
                "synthetic_rubber_plants",
                "Заводы синтетической резины",
                "Synthetic Rubber Plants",
                "synth_oil_experiments",
                2160,
                (
                ),
            ),
            (
                "emulsion_polymerization",
                "Эмульсионная полимеризация",
                "Emulsion Polymerization",
                "rubber_processing",
                2163,
                (
                ),
            ),
            (
                "rubber_production_lines",
                "Расширение резинового производства",
                "Rubber Production Expansion",
                "improved_oil_plant",
                2166,
                (
                ),
            ),
            (
                "selective_polymer_catalysts",
                "Селективные катализаторы полимеризации",
                "Selective Polymerization Catalysts",
                "improved_rubber_processing",
                2169,
                (
                ),
            ),
            (
                "integrated_rubber_complexes",
                "Нефтехимические комплексы",
                "Integrated Petrochemical Complexes",
                "advanced_oil_plant",
                2172,
                (
                ),
            ),
            (
                "closed_cycle_polymerization",
                "Замкнутый цикл полимеризации",
                "Closed-Cycle Polymerization",
                "advanced_rubber_processing",
                2175,
                (
                ),
            ),
            (
                "solvent_recovery_columns",
                "Колонны регенерации растворителей",
                "Solvent Recovery Columns",
                "rubber_processing",
                2177,
                (
                    "factory_energy_consumption = -0.02",
                    "ADISCORD_economy_construction_expense_factor = -0.02",
                ),
            ),
            (
                "precision_polymer_blending",
                "Точное смешение полимеров",
                "Precision Polymer Blending",
                "rubber_processing",
                2180,
                (
                    "production_lack_of_resource_penalty_factor = -0.02",
                ),
            ),
        ),
    ),
    research_branch(
        "synthetic_oil",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Синт. нефть",
        "Synthetic Oil",
        "resources",
        (
            (
                "synthetic_oil_synthesis",
                "Синтез жидких углеводородов",
                "Liquid Hydrocarbon Synthesis",
                "oil_processing",
                2161,
                (
                ),
            ),
            (
                "synthetic_feedstock_purification",
                "Очистка синтетического сырья",
                "Synthetic Feedstock Purification",
                "improved_oil_processing",
                2163,
                (
                    "fuel_gain_factor_from_states = 0.10",
                ),
            ),
            (
                "catalytic_oil_synthesis",
                "Каталитический синтез нефти",
                "Catalytic Oil Synthesis",
                "oil_plant",
                2166,
                (
                ),
            ),
            (
                "synthetic_fuel_hydrocracking",
                "Гидрокрекинг синтетического топлива",
                "Synthetic Fuel Hydrocracking",
                "advanced_oil_processing",
                2169,
                (
                    "fuel_gain_factor_from_states = 0.10",
                ),
            ),
            (
                "closed_cycle_oil_synthesis",
                "Замкнутый цикл синтеза нефти",
                "Closed-Cycle Oil Synthesis",
                "advanced_oil_plant",
                2172,
                (
                ),
            ),
            (
                "synthetic_fuel_process_control",
                "Автоматическое управление переработкой",
                "Automated Refining Control",
                "modern_oil_processing",
                2175,
                (
                    "fuel_gain_factor_from_states = 0.10",
                ),
            ),
            (
                "synthetic_heat_recovery",
                "Утилизация тепла нефтесинтеза",
                "Synthetic Fuel Heat Recovery",
                "improved_oil_processing",
                2177,
                (
                    "factory_energy_consumption = -0.02",
                    "fuel_gain_factor_from_states = 0.10",
                ),
            ),
            (
                "precision_fuel_fractionation",
                "Точное фракционирование топлива",
                "Precision Fuel Fractionation",
                "advanced_oil_processing",
                2180,
                (
                ),
            ),
        ),
    ),
    research_branch(
        "public_finance",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Экономика и управление",
        "Economy and Administration",
        "finance",
        (
            (
                "treasury_accounting",
                "Казначейский учёт",
                "Treasury Accounting",
                "mechanical_computing",
                2155,
                (
                    "ADISCORD_economy_tax_collection_factor = 0.02",
                    "ADISCORD_economy_admin_expense_factor = -0.02",
                ),
            ),
            (
                "public_procurement_standards",
                "Стандарты государственных закупок",
                "Public Procurement Standards",
                "computing_machine",
                2160,
                (
                    "ADISCORD_economy_construction_expense_factor = -0.03",
                    "ADISCORD_economy_military_factory_expense_factor = -0.02",
                ),
            ),
            (
                "civilian_industrial_accounting",
                "Промышленный учёт",
                "Industrial Accounting",
                "improved_machine_tools",
                2162,
                (
                    "ADISCORD_economy_civilian_factory_income_factor = 0.04",
                    "ADISCORD_economy_tax_collection_factor = 0.02",
                ),
            ),
            (
                "industrial_investment_planning",
                "Планирование промышленных вложений",
                "Industrial Investment Planning",
                "mechanical_computing",
                2163,
                (
                    "ADISCORD_economy_civilian_factory_income_factor = 0.04",
                    "production_speed_industrial_complex_factor = 0.03",
                ),
            ),
            (
                "industrial_service_budgeting",
                "Сметы промышленного обслуживания",
                "Industrial Service Budgeting",
                "mechanical_computing",
                2163,
                (
                    "ADISCORD_economy_military_factory_expense_factor = -0.04",
                    "ADISCORD_economy_admin_expense_factor = -0.02",
                ),
            ),
            (
                "administrative_digitization",
                "Цифровое делопроизводство",
                "Digital Administration",
                "improved_computing_machine",
                2166,
                (
                    "ADISCORD_economy_admin_expense_factor = -0.04",
                    "ADISCORD_economy_research_expense_factor = -0.03",
                ),
            ),
            (
                "regional_development_contracts",
                "Договоры регионального развития",
                "Regional Development Contracts",
                "computing_machine",
                2167,
                (
                    "ADISCORD_economy_civilian_factory_income_factor = 0.03",
                    "production_speed_buildings_factor = 0.02",
                ),
            ),
            (
                "lifecycle_cost_audits",
                "Аудит жизненного цикла оборудования",
                "Equipment Lifecycle Audits",
                "computing_machine",
                2167,
                (
                    "ADISCORD_economy_construction_expense_factor = -0.04",
                    "ADISCORD_economy_research_expense_factor = -0.02",
                ),
            ),
            (
                "production_cost_accounting",
                "Учёт производственных затрат",
                "Production Cost Accounting",
                "advanced_machine_tools",
                2169,
                (
                    "ADISCORD_economy_military_industry_income_factor = 0.04",
                    "ADISCORD_economy_military_factory_expense_factor = -0.03",
                ),
            ),
            (
                "automated_treasury_audit",
                "Автоматизированный финансовый контроль",
                "Automated Treasury Audit",
                "advanced_computing_machine",
                2175,
                (
                    "ADISCORD_economy_tax_collection_factor = 0.03",
                    "ADISCORD_economy_civilian_factory_income_factor = 0.04",
                ),
            ),
        ),
    ),
    research_branch(
        "advanced_materials",
        "ADISCORD_industry.txt",
        ('industry_folder',),
        "Редкие материалы",
        "Advanced Materials",
        "resources",
        (
            (
                "precision_material_standards",
                "Стандарты чистоты материалов",
                "Material Purity Standards",
                "improved_machine_tools",
                2155,
                (
                    "production_lack_of_resource_penalty_factor = -0.01",
                    "production_factory_efficiency_gain_factor = 0.01",
                ),
            ),
            (
                "rare_components_industry",
                "Производство редких компонентов",
                "Rare Components Industry",
                "computing_machine",
                2158,
                (
                    "production_factory_efficiency_gain_factor = 0.02",
                    "production_factory_max_efficiency_factor = 0.01",
                ),
            ),
            (
                "rare_alloy_metallurgy",
                "Металлургия редких сплавов",
                "Rare Alloy Metallurgy",
                "excavation2",
                2158,
                (
                    "production_lack_of_resource_penalty_factor = -0.02",
                    "production_factory_max_efficiency_factor = 0.01",
                ),
            ),
            (
                "precision_component_fabrication",
                "Прецизионная сборка компонентов",
                "Precision Component Fabrication",
                "advanced_computing_machine",
                2166,
                (
                    "production_factory_efficiency_gain_factor = 0.02",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "vacuum_alloy_refining",
                "Вакуумная очистка сплавов",
                "Vacuum Alloy Refining",
                "excavation4",
                2166,
                (
                    "production_factory_max_efficiency_factor = 0.02",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "precision_ceramic_substrates",
                "Прецизионные керамические подложки",
                "Precision Ceramic Substrates",
                "advanced_machine_tools",
                2170,
                (
                    "production_factory_efficiency_gain_factor = 0.02",
                    "production_lack_of_resource_penalty_factor = -0.01",
                ),
            ),
            (
                "powder_alloy_sintering",
                "Спекание порошковых сплавов",
                "Powder Alloy Sintering",
                "advanced_machine_tools",
                2170,
                (
                    "production_factory_max_efficiency_factor = 0.02",
                    "industry_repair_factor = 0.03",
                ),
            ),
            (
                "advanced_material_recycling",
                "Переработка редких материалов",
                "Advanced Material Recycling",
                "excavation5",
                2173,
                (
                    "production_lack_of_resource_penalty_factor = -0.02",
                    "factory_energy_consumption = -0.02",
                ),
            ),
        ),
    ),
    research_branch(
        "signals",
        "ADISCORD_electronics.txt",
        ('electronics_folder',),
        "Связь и кибервойна",
        "Signals and Cyberwarfare",
        "signals",
        (
            (
                "mesh_command_networks",
                "Ячеистые сети управления",
                "Mesh Command Networks",
                "radio",
                2150,
                (
                    "coordination_bonus = 0.01",
                    "encryption_factor = 0.01",
                ),
            ),
            (
                "field_radio_networks",
                "Полевые радиосети",
                "Field Radio Networks",
                "radio_detection",
                2155,
                (
                    "land_reinforce_rate = 0.01",
                    "encryption_factor = 0.02",
                ),
            ),
            (
                "encryption_rebuild",
                "Восстановление шифрования",
                "Encryption Rebuild",
                "basic_encryption",
                2158,
                (
                    "encryption_factor = 0.03",
                    "coordination_bonus = 0.01",
                ),
            ),
            (
                "frequency_hopping_field_sets",
                "Полевые станции со скачками частоты",
                "Frequency-Hopping Field Sets",
                "radio",
                2160,
                (
                    "encryption_factor = 0.04",
                    "land_reinforce_rate = 0.01",
                ),
            ),
            (
                "signal_intercept_arrays",
                "Массивы радиоперехвата",
                "Signal Intercept Arrays",
                "basic_decryption",
                2161,
                (
                    "decryption_factor = 0.04",
                    "air_interception_detect_factor = 0.02",
                ),
            ),
            (
                "digital_radio_relays",
                "Цифровые радиорелейные сети",
                "Digital Radio Relays",
                "radio",
                2163,
                (
                    "land_reinforce_rate = 0.01",
                    "coordination_bonus = 0.01",
                ),
            ),
            (
                "phased_array_signal_processing",
                "Обработка сигналов фазированных решёток",
                "Phased-array Signal Processing",
                "radio_detection",
                2164,
                (
                    "air_interception_detect_factor = 0.03",
                    "decryption_factor = 0.02",
                ),
            ),
            (
                "battlefield_analytics",
                "Аналитика поля боя",
                "Battlefield Analytics",
                "improved_encryption",
                2166,
                (
                    "coordination_bonus = 0.02",
                    "decryption_factor = 0.03",
                ),
            ),
            (
                "adaptive_frequency_management",
                "Адаптивное распределение частот",
                "Adaptive Frequency Management",
                "improved_encryption",
                2169,
                (
                    "encryption_factor = 0.03",
                    "coordination_bonus = 0.01",
                ),
            ),
            (
                "counterintelligence_filters",
                "Автоматизация контрразведки",
                "Counterintelligence Filters",
                "improved_decryption",
                2170,
                (
                    "encryption_factor = 0.05",
                    "decryption_factor = 0.02",
                ),
            ),
            (
                "battlefield_sensor_fusion",
                "Сведение датчиков поля боя",
                "Battlefield Sensor Fusion",
                "radio_detection",
                2172,
                (
                    "coordination_bonus = 0.03",
                    "air_interception_detect_factor = 0.04",
                ),
            ),
            (
                "multistatic_radar_networks",
                "Многопозиционные радиолокационные сети",
                "Multistatic Radar Networks",
                "advanced_radar",
                2174,
                (
                    "air_interception_detect_factor = 0.03",
                    "air_mission_efficiency = 0.02",
                ),
            ),
            (
                "self_healing_tactical_networks",
                "Самовосстанавливающиеся тактические сети",
                "Self-Healing Tactical Networks",
                "advanced_encryption",
                2175,
                (
                    "encryption_factor = 0.06",
                    "land_reinforce_rate = 0.02",
                ),
            ),
            (
                "memetic_security_protocols",
                "Протоколы меметической защиты",
                "Memetic Security Protocols",
                "advanced_encryption",
                2180,
                (
                    "encryption_factor = 0.07",
                    "decryption_factor = 0.04",
                    "coordination_bonus = 0.03",
                ),
            ),
        ),
    ),
    research_branch(
        "computing",
        "ADISCORD_electronics.txt",
        ('electronics_folder',),
        "Вычисления и управление",
        "Computing and Control",
        "computing",
        (
            (
                "electromechanical_relays",
                "Электромеханические реле",
                "Electromechanical Relays",
                "mechanical_computing",
                2150,
                (
                    "research_speed_factor = 0.01",
                    "production_factory_efficiency_gain_factor = 0.01",
                ),
            ),
            (
                "recovered_data_archives",
                "Восстановленные архивы",
                "Recovered Data Archives",
                "electronic_mechanical_engineering",
                2155,
                (
                    "research_speed_factor = 0.015",
                    "planning_speed = 0.01",
                ),
            ),
            (
                "recovered_semiconductors",
                "Восстановленные полупроводники",
                "Recovered Semiconductors",
                "computing_machine",
                2158,
                (
                    "research_speed_factor = 0.02",
                    "production_factory_efficiency_gain_factor = 0.02",
                ),
            ),
            (
                "hardened_computers",
                "Защищённые вычислители",
                "Hardened Computers",
                "basic_encryption",
                2160,
                (
                    "research_speed_factor = 0.025",
                    "encryption_factor = 0.02",
                ),
            ),
            (
                "error_correcting_field_computers",
                "Полевые вычислители с коррекцией ошибок",
                "Error-Correcting Field Computers",
                "radio_detection",
                2162,
                (
                    "research_speed_factor = 0.03",
                    "encryption_factor = 0.035",
                    "supply_consumption_factor = -0.015",
                ),
            ),
            (
                "scientific_computing_centres",
                "Центры научных вычислений",
                "Scientific Computing Centres",
                "computing_machine",
                2164,
                (
                    "research_speed_factor = 0.035",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "industrial_computing_centres",
                "Центры прикладных вычислений",
                "Applied Computing Centres",
                "computing_machine",
                2164,
                (
                    "industrial_capacity_factory = 0.02",
                    "production_factory_efficiency_gain_factor = 0.02",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "predictive_logistics",
                "Предиктивная логистика",
                "Predictive Logistics",
                "mechanical_computing",
                2166,
                (
                    "research_speed_factor = 0.025",
                    "supply_consumption_factor = -0.03",
                    "encryption_factor = 0.03",
                ),
            ),
            (
                "parallel_numerical_solvers",
                "Параллельное численное моделирование",
                "Parallel Numerical Solvers",
                "improved_computing_machine",
                2167,
                (
                    "research_speed_factor = 0.035",
                ),
            ),
            (
                "industrial_process_optimizers",
                "Оптимизаторы производственных процессов",
                "Industrial Process Optimizers",
                "computing_machine",
                2167,
                (
                    "industrial_capacity_factory = 0.03",
                    "production_factory_efficiency_gain_factor = 0.03",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "operational_ai_assistants",
                "Операционные ИИ-ассистенты",
                "Operational AI Assistants",
                "radio_detection",
                2170,
                (
                    "research_speed_factor = 0.025",
                    "coordination_bonus = 0.035",
                    "factory_energy_consumption = 0.06",
                ),
            ),
            (
                "photonic_research_processors",
                "Фотонные исследовательские процессоры",
                "Photonic Research Processors",
                "advanced_computing_machine",
                2170,
                (
                    "research_speed_factor = 0.04",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "strategic_digital_twins",
                "Стратегические цифровые двойники",
                "Strategic Digital Twins",
                "advanced_computing_machine",
                2174,
                (
                    "research_speed_factor = 0.03",
                    "planning_speed = 0.03",
                    "production_factory_efficiency_gain_factor = 0.03",
                ),
            ),
            (
                "adaptive_factory_scheduling",
                "Адаптивные производственные графики",
                "Adaptive Factory Scheduling",
                "improved_computing_machine",
                2174,
                (
                    "industrial_capacity_factory = 0.03",
                    "line_change_production_efficiency_factor = 0.04",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "quantum_material_simulation",
                "Квантовое моделирование материалов",
                "Quantum Material Simulation",
                "advanced_computing_machine",
                2177,
                (
                    "research_speed_factor = 0.04",
                    "production_lack_of_resource_penalty_factor = -0.02",
                ),
            ),
            (
                "autonomous_supply_planning",
                "Автономное планирование снабжения",
                "Autonomous Supply Planning",
                "advanced_computing_machine",
                2177,
                (
                    "supply_consumption_factor = -0.03",
                    "production_factory_start_efficiency_factor = 0.04",
                ),
            ),
            (
                "strategic_ai_coordination",
                "Стратегическая ИИ-координация",
                "Strategic AI Coordination",
                "computing_machine",
                2180,
                (
                    "research_speed_factor = 0.04",
                    "coordination_bonus = 0.05",
                    "production_factory_efficiency_gain_factor = 0.04",
                    "factory_energy_consumption = 0.04",
                ),
            ),
        ),
    ),
    research_branch(
        "power",
        "ADISCORD_electronics.txt",
        ('electronics_folder',),
        "Энергетика и реакторы",
        "Power and Reactors",
        "power",
        (
            (
                "local_grid_restoration",
                "Локальные энергосети",
                "Local Grid Restoration",
                "electronic_mechanical_engineering",
                2150,
                (
                    "factory_energy_consumption = -0.03",
                    "industry_repair_factor = 0.02",
                ),
            ),
            (
                "substation_networks",
                "Восстановление подстанций",
                "Substation Networks",
                "oil_plant",
                2155,
                (
                    "factory_energy_consumption = -0.035",
                    "production_speed_infrastructure_factor = 0.025",
                ),
            ),
            (
                "radiation_mapping",
                "Радиационное картирование",
                "Radiation Mapping",
                "atomic_research",
                2158,
                (
                    "factory_energy_consumption = -0.025",
                    "nuclear_production_factor = 0.03",
                ),
            ),
            (
                "phase_synchronized_substations",
                "Фазосинхронизированные подстанции",
                "Phase-Synchronized Substations",
                "nuclear_reactor",
                2160,
                (
                    "factory_energy_consumption = -0.04",
                    "industry_repair_factor = 0.03",
                    "ADISCORD_economy_military_factory_expense_factor = -0.01",
                ),
            ),
            (
                "superconducting_power_busbars",
                "Сверхпроводящие силовые шины",
                "Superconducting Power Busbars",
                "advanced_oil_plant",
                2163,
                (
                    "factory_energy_consumption = -0.05",
                    "industrial_capacity_factory = 0.01",
                ),
            ),
            (
                "reactor_safety_protocols",
                "Безопасность реакторов",
                "Reactor Safety Protocols",
                "oil_plant",
                2166,
                (
                    "factory_energy_consumption = -0.04",
                    "nuclear_production_factor = 0.05",
                ),
            ),
            (
                "load_following_microreactors",
                "Маневренные микрореакторы",
                "Load-Following Microreactors",
                "nuclear_reactor",
                2168,
                (
                    "factory_energy_consumption = -0.05",
                    "nuclear_production_factor = 0.06",
                    "ADISCORD_economy_military_factory_expense_factor = -0.02",
                ),
            ),
            (
                "microreactor_blocks",
                "Массивы микрореакторов",
                "Microreactor Blocks",
                "sp_nuclear_isotope_separation",
                2170,
                (
                    "factory_energy_consumption = -0.055",
                    "nuclear_production_factor = 0.07",
                ),
            ),
            (
                "baseload_reactor_dispatch",
                "Централизованная диспетчеризация энергосистемы",
                "Centralised Grid Dispatch",
                "nuclear_reactor",
                2172,
                (
                    "production_factory_max_efficiency_factor = 0.03",
                    "factory_energy_consumption = -0.04",
                    "industrial_capacity_factory = 0.02",
                ),
            ),
            (
                "islandable_microgrids",
                "Автономные энергетические микрорайоны",
                "Islandable Microgrids",
                "radio",
                2172,
                (
                    "factory_energy_consumption = -0.04",
                    "industry_repair_factor = 0.06",
                    "industry_air_damage_factor = -0.03",
                ),
            ),
            (
                "high_capacity_transmission",
                "Магистрали высокой пропускной способности",
                "High-capacity Transmission",
                "nuclear_reactor",
                2174,
                (
                    "factory_energy_consumption = -0.04",
                    "industrial_capacity_factory = 0.02",
                ),
            ),
            (
                "regional_energy_reserves",
                "Региональные энергетические резервы",
                "Regional Energy Reserves",
                "radio",
                2174,
                (
                    "factory_energy_consumption = -0.04",
                    "industry_repair_factor = 0.06",
                    "production_speed_infrastructure_factor = 0.03",
                ),
            ),
            (
                "continental_load_balancing",
                "Континентальная балансировка нагрузки",
                "Continental Load Balancing",
                "atomic_research",
                2175,
                (
                    "factory_energy_consumption = -0.06",
                    "production_speed_buildings_factor = 0.04",
                    "ADISCORD_economy_military_factory_expense_factor = -0.02",
                ),
            ),
            (
                "emergency_core_suppression",
                "Аварийное глушение ядра",
                "Emergency Core Suppression",
                "nuclear_reactor",
                2180,
                (
                    "factory_energy_consumption = -0.07",
                    "nuclear_production_factor = 0.08",
                    "industry_repair_factor = 0.06",
                ),
            ),
        ),
    ),
    research_branch(
        "forbidden_energy",
        "ADISCORD_forbidden.txt",
        ('electronics_folder',),
        "Запретная энергетика",
        "Forbidden Energy",
        "forbidden_energy",
        (
            (
                "old_generator_fragments",
                "Фрагменты старого генератора",
                "Old Generator Fragments",
                "atomic_research",
                2164,
                (
                    "nuclear_production_factor = 0.04",
                    "industry_repair_factor = 0.02",
                    "stability_factor = -0.005",
                ),
            ),
            (
                "legacy_reactor_compactification",
                "Компактификация реакторов",
                "Legacy Reactor Compactification",
                "sp_nuclear_isotope_separation",
                2168,
                (
                    "nuclear_production_factor = 0.08",
                    "production_speed_buildings_factor = 0.025",
                    "stability_factor = -0.011",
                ),
            ),
            (
                "singularity_cooling_systems",
                "Сингулярное охлаждение",
                "Singularity Cooling Systems",
                "advanced_rocket_engines",
                2173,
                (
                    "nuclear_production_factor = 0.12",
                    "research_speed_factor = 0.025",
                    "stability_factor = -0.017",
                ),
            ),
            (
                "black_grid_protocols",
                "Протоколы чёрной энергосети",
                "Black Grid Protocols",
                "sp_physics_advanced_radio",
                2180,
                (
                    "nuclear_production_factor = 0.16",
                    "industrial_capacity_factory = 0.04",
                    "stability_factor = -0.025",
                ),
            ),
        ),
    ),
    research_branch(
        "forbidden_automation",
        "ADISCORD_forbidden.txt",
        ('electronics_folder',),
        "Запретная автоматизация",
        "Forbidden Automation",
        "forbidden_automation",
        (
            (
                "self_repairing_industrial_swarms",
                "Самовосстанавливающиеся рои",
                "Self-repairing Industrial Swarms",
                "flexible_line",
                2168,
                (
                    "production_factory_max_efficiency_factor = 0.04",
                    "industry_repair_factor = 0.03",
                    "stability_factor = -0.01",
                ),
            ),
            (
                "neural_command_cores",
                "Нейронные командные ядра",
                "Neural Command Cores",
                "improved_computing_machine",
                2172,
                (
                    "coordination_bonus = 0.05",
                    "land_reinforce_rate = 0.03",
                    "stability_factor = -0.02",
                ),
            ),
            (
                "forbidden_automation_doctrine",
                "Доктрина запретной автоматизации",
                "Forbidden Automation Doctrine",
                "advanced_computing_machine",
                2180,
                (
                    "production_factory_max_efficiency_factor = 0.08",
                    "research_speed_factor = 0.04",
                    "stability_factor = -0.035",
                ),
            ),
        ),
    ),
    research_branch(
        "small_arms",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Личное оружие и боеприпасы",
        "Personal Weapons and Ammunition",
        "infantry",
        (
            (
                "postwar_weapon_standardization",
                "Высокоточная нарезка стволов",
                "Precision Rifling of Barrel Bores",
                "infantry_weapons",
                2150,
                (
                    "category_all_infantry = { soft_attack = 0.006 }",
                ),
            ),
            (
                "rifling_alignment",
                "Соосность нарезов",
                "Rifling Alignment",
                "infantry_weapons",
                2150,
                (
                    "category_all_infantry = { soft_attack = 0.006 }",
                ),
            ),
            (
                "bolt_head_fitting",
                "Подгонка боевых упоров",
                "Locking Lug Fitting",
                "infantry_weapons",
                2150,
                (
                    "category_all_infantry = { soft_attack = 0.006 }",
                ),
            ),
            (
                "chamber_polishing",
                "Чистовая обработка патронника",
                "Chamber Finishing",
                "infantry_weapons",
                2150,
                (
                    "category_all_infantry = { soft_attack = 0.006 }",
                ),
            ),
            (
                "refurbished_receivers",
                "Герметизация казённой части",
                "Breech Obturation",
                "infantry_weapons",
                2155,
                (
                    "category_all_infantry = { defense = 0.012 }",
                ),
            ),
            (
                "standardized_cartridges",
                "Унитарный металлический патрон",
                "Metallic Self-contained Cartridge",
                "ADISCORD_equipment_ammunition",
                2158,
                (
                    "category_all_infantry = { soft_attack = 0.028 }",
                ),
            ),
            (
                "caseless_ammunition_trials",
                "Нитроцеллюлозные метательные составы",
                "Nitrocellulose Propellant Formulations",
                "ADISCORD_equipment_ammunition",
                2160,
                (
                    "category_all_infantry = { soft_attack = 0.028 breakthrough = 0.008 }",
                ),
            ),
            (
                "primer_consistency",
                "Стабильное воспламенение капсюля",
                "Consistent Primer Ignition",
                "ADISCORD_equipment_ammunition",
                2161,
                (
                    "category_all_infantry = { defense = 0.012 }",
                ),
            ),
        ),
    ),
    research_branch(
        "assault_rifles",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Штурмовые винтовки",
        "Assault Rifles",
        "infantry",
        (
            (
                "sealed_receiver_assemblies",
                "Промежуточные патроны",
                "Intermediate Cartridges",
                "infantry_weapons",
                2162,
                (
                    "category_all_infantry = { breakthrough = 0.008 soft_attack = 0.004 }",
                ),
            ),
            (
                "electrothermal_ignition",
                "Высокопрочные ствольные стали",
                "High-strength Barrel Steels",
                "ADISCORD_weapon_03_standardized_battle_rifle",
                2163,
                (
                    "category_all_infantry = { defense = 0.028 breakthrough = 0.008 }",
                ),
            ),
            (
                "magazine_feed_geometry",
                "Геометрия подачи магазина",
                "Magazine Feed Geometry",
                "infantry_weapons",
                2163,
                (
                    "category_all_infantry = { breakthrough = 0.008 soft_attack = 0.004 }",
                ),
            ),
            (
                "extractor_heat_treatment",
                "Закалка выбрасывателя",
                "Extractor Heat Treatment",
                "infantry_weapons",
                2163,
                (
                    "category_all_infantry = { breakthrough = 0.008 soft_attack = 0.004 }",
                ),
            ),
            (
                "smart_recoil_compensators",
                "Самозарядная автоматика",
                "Self-loading Action",
                "infantry_weapons3",
                2164,
                (
                    "category_all_infantry = { soft_attack = 0.008 breakthrough = 0.004 }",
                ),
            ),
            (
                "recoil_spring_tuning",
                "Настройка возвратной пружины",
                "Recoil Spring Tuning",
                "infantry_weapons",
                2164,
                (
                    "category_all_infantry = { soft_attack = 0.008 breakthrough = 0.004 }",
                ),
            ),
            (
                "bolt_carrier_guides",
                "Направляющие затворной рамы",
                "Bolt Carrier Guides",
                "infantry_weapons",
                2164,
                (
                    "category_all_infantry = { soft_attack = 0.008 breakthrough = 0.004 }",
                ),
            ),
            (
                "trigger_reset_geometry",
                "Короткий сброс спуска",
                "Short Trigger Reset",
                "infantry_weapons",
                2164,
                (
                    "category_all_infantry = { soft_attack = 0.008 breakthrough = 0.004 }",
                ),
            ),
            (
                "smart_optics",
                "Лазерное измерение дальности",
                "Laser Rangefinding",
                "night_vision",
                2165,
                (
                    "coordination_bonus = 0.004",
                    "category_all_infantry = { soft_attack = 0.004 }",
                ),
            ),
            (
                "networked_weapon_sights",
                "Баллистические вычислители",
                "Computerized Ballistic Correction",
                "ADISCORD_equipment_ballistic_sight",
                2166,
                (
                    "coordination_bonus = 0.016",
                    "category_all_infantry = { soft_attack = 0.016 }",
                ),
            ),
            (
                "rangefinder_zeroing",
                "Юстировка дальномера",
                "Rangefinder Alignment",
                "night_vision",
                2166,
                (
                    "coordination_bonus = 0.004",
                    "category_all_infantry = { soft_attack = 0.004 }",
                ),
            ),
            (
                "sight_mount_repeatability",
                "Повторяемая установка прицела",
                "Repeatable Sight Mounting",
                "night_vision",
                2166,
                (
                    "coordination_bonus = 0.004",
                    "category_all_infantry = { soft_attack = 0.004 }",
                ),
            ),
            (
                "modular_rifle_kits",
                "Газоотводная автоматика",
                "Gas-operated Action",
                "infantry_weapons3",
                2167,
                (
                    "category_all_infantry = { soft_attack = 0.018 breakthrough = 0.01 }",
                ),
            ),
            (
                "biometric_trigger_locks",
                "Запирание поворотным затвором",
                "Rotating-bolt Locking",
                "ADISCORD_weapon_03_standardized_battle_rifle",
                2168,
                (
                    "category_all_infantry = { defense = 0.028 breakthrough = 0.02 }",
                ),
            ),
            (
                "integrated_target_designation",
                "Электронно-оптические прицелы",
                "Integrated Electro-optical Sights",
                "ADISCORD_equipment_ballistic_sight",
                2169,
                (
                    "land_night_attack = 0.012",
                    "coordination_bonus = 0.016",
                ),
            ),
            (
                "gas_regulator_sealing",
                "Уплотнение газового регулятора",
                "Gas Regulator Sealing",
                "infantry_weapons",
                2169,
                (
                    "category_all_infantry = { soft_attack = 0.018 breakthrough = 0.01 }",
                ),
            ),
            (
                "programmable_ammunition",
                "Износостойкие покрытия ствола",
                "Chrome Lining and Wear-resistant Bore Coatings",
                "infantry_at2",
                2170,
                (
                    "category_all_infantry = { defense = 0.008 soft_attack = 0.003 }",
                ),
            ),
            (
                "bore_plating_control",
                "Равномерное покрытие канала ствола",
                "Uniform Bore Plating",
                "infantry_weapons",
                2170,
                (
                    "category_all_infantry = { defense = 0.008 soft_attack = 0.003 }",
                ),
            ),
            (
                "chamber_erosion_control",
                "Защита патронника от эрозии",
                "Chamber Erosion Protection",
                "infantry_weapons",
                2171,
                (
                    "category_all_infantry = { defense = 0.008 soft_attack = 0.003 }",
                ),
            ),
            (
                "barrel_heat_treatment",
                "Термообработка ствола",
                "Barrel Heat Treatment",
                "infantry_weapons",
                2171,
                (
                    "category_all_infantry = { defense = 0.008 soft_attack = 0.003 }",
                ),
            ),
            (
                "coil_assisted_service_rifles",
                "Оптимизация импульса отдачи",
                "Recoil Impulse Optimization",
                "infantry_weapons3",
                2172,
                (
                    "category_all_infantry = { breakthrough = 0.011 defense = 0.004 }",
                ),
            ),
            (
                "buffered_bolt_travel",
                "Буфер хода затвора",
                "Bolt Travel Buffer",
                "infantry_weapons",
                2173,
                (
                    "category_all_infantry = { breakthrough = 0.011 defense = 0.004 }",
                ),
            ),
            (
                "muzzle_compensation_ports",
                "Компенсационные окна ствола",
                "Muzzle Compensation Ports",
                "infantry_weapons",
                2174,
                (
                    "category_all_infantry = { breakthrough = 0.01 defense = 0.004 }",
                ),
            ),
            (
                "hybrid_kinetic_energy_carbines",
                "Полимерные и гибридные гильзы",
                "Polymer and Hybrid Cartridge Cases",
                "ADISCORD_equipment_ammunition",
                2175,
                (
                    "category_all_infantry = { defense = 0.024 soft_attack = 0.024 }",
                ),
            ),
            (
                "networked_service_rifles",
                "Программируемые боеприпасы",
                "Programmable Small-arms Ammunition",
                "night_vision2",
                2180,
                (
                    "category_all_infantry = { soft_attack = 0.04 }",
                    "coordination_bonus = 0.024",
                ),
            ),
        ),
    ),
    research_branch(
        "squad_weapons",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Групповое оружие и огневая поддержка",
        "Crew-served Weapons and Fire Support",
        "squad",
        (
            (
                "belt_fed_recovery",
                "Пулемёты с ленточным питанием",
                "Belt-fed Machine Guns",
                "ADISCORD_squad_01_recovered_fire_support",
                2150,
                ("category_all_infantry = { soft_attack = 0.024 defense = 0.04 }",),
            ),
            (
                "squad_grenade_launchers",
                "Стандартизация ленточных пулемётов",
                "Standardized Belt-fed Machine Guns",
                "ADISCORD_squad_01_recovered_fire_support",
                2155,
                (
                    "category_all_infantry = { soft_attack = 0.041 hard_attack = 0.025 }",
                ),
            ),
            (
                "portable_at_cells",
                "Противотанковое оружие расчёта",
                "Crew-served Anti-tank Weapons",
                "ADISCORD_squad_02_heavy_machine_guns",
                2158,
                ("category_all_infantry = { breakthrough = 0.043 ap_attack = 0.025 }",),
            ),
            (
                "recoilless_squad_launchers",
                "Модульные станковые гранатомёты",
                "Modular Mounted Grenade Launchers",
                "ADISCORD_squad_02_heavy_machine_guns",
                2160,
                (
                    "category_all_infantry = { soft_attack = 0.044 hard_attack = 0.026 }",
                ),
            ),
            (
                "field_ew_units",
                "Прицелы группового оружия",
                "Crew-served Weapon Sights",
                "ADISCORD_squad_03_optical_fire_support",
                2161,
                (
                    "category_all_infantry = { max_organisation = 0.902 default_morale = 0.027 }",
                ),
            ),
            (
                "programmable_grenade_fuzes",
                "Программируемые гранатные взрыватели",
                "Programmable Grenade Fuzes",
                "ADISCORD_equipment_ammunition",
                2162,
                (
                    "category_all_infantry = { soft_attack = 0.046 hard_attack = 0.027 }",
                ),
            ),
            (
                "man_portable_sensor_masts",
                "Переносные сенсорные мачты",
                "Man-Portable Sensor Masts",
                "ADISCORD_night_05_counter_illumination",
                2163,
                (
                    "coordination_bonus = 0.048",
                    "land_reinforce_rate = 0.014",
                ),
            ),
            (
                "drone_guided_support_fire",
                "Корректировка огня с дронов",
                "Drone-assisted Fire Adjustment",
                "ADISCORD_equipment_drone",
                2165,
                (
                    "category_all_infantry = { max_organisation = 1.053 default_morale = 0.029 }",
                ),
            ),
            (
                "networked_command_terminals",
                "Терминалы управления огнём",
                "Fire-control Terminals",
                "ADISCORD_equipment_radio",
                2166,
                (
                    "category_all_infantry = { max_organisation = 1.091 default_morale = 0.03 }",
                ),
            ),
            (
                "remote_weapon_tripods",
                "Дистанционные огневые установки",
                "Remote-controlled Weapon Mounts",
                "ADISCORD_squad_03_optical_fire_support",
                2167,
                ("category_all_infantry = { soft_attack = 0.053 defense = 0.03 }",),
            ),
            (
                "cooperative_target_handoff",
                "Передача целей между расчётами",
                "Cooperative Target Handoff",
                "ADISCORD_equipment_radio",
                2169,
                (
                    "coordination_bonus = 0.055",
                    "land_reinforce_rate = 0.016",
                ),
            ),
            (
                "autonomous_support_weapons",
                "Автоматизированные огневые установки",
                "Automated Fire-support Mounts",
                "ADISCORD_squad_04_advanced_fire_support",
                2170,
                (
                    "category_all_infantry = { soft_attack = 0.056 breakthrough = 0.032 }",
                ),
            ),
            (
                "autonomous_mortar_sections",
                "Автоматизированные миномёты",
                "Automated Mortars",
                "ADISCORD_equipment_mortar",
                2171,
                (
                    "category_all_infantry = { soft_attack = 0.058 breakthrough = 0.033 }",
                ),
            ),
            (
                "robotic_heavy_weapon_teams",
                "Роботизированные огневые расчёты",
                "Robotic Fire-support Teams",
                "ADISCORD_squad_04_advanced_fire_support",
                2174,
                ("category_all_infantry = { soft_attack = 0.061 defense = 0.035 }",),
            ),
            (
                "swarm_fireteams",
                "Единая сеть огневой поддержки",
                "Integrated Fire-support Network",
                "ADISCORD_squad_04_advanced_fire_support",
                2180,
                (
                    "category_all_infantry = { soft_attack = 0.093 defense = 0.093 max_organisation = 2.131 }",
                ),
            ),
        ),
    ),
    research_branch(
        "anti_tank_infantry",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Пехотные противотанковые средства",
        "Infantry Anti-tank Weapons",
        "anti_tank",
        (
            (
                "recovered_shaped_charge_cells",
                "Бутылки с зажигательной смесью",
                "Incendiary Bottles",
                "ADISCORD_antitank_01_incendiary_bottle",
                2150,
                ("category_all_infantry = { hard_attack = 0.012 ap_attack = 0.008 }",),
            ),
            (
                "disposable_launcher_standards",
                "Лёгкие противотанковые пушки",
                "Light Anti-tank Guns",
                "ADISCORD_antitank_02_satchel_charge",
                2155,
                (
                    "category_all_infantry = { hard_attack = 0.016 breakthrough = 0.008 }",
                ),
            ),
            (
                "tandem_penetrator_packages",
                "Ручные кумулятивные противотанковые гранаты",
                "Hand-thrown Shaped-charge Anti-tank Grenades",
                "ADISCORD_antitank_03_shaped_charge_grenade",
                2158,
                ("category_all_infantry = { hard_attack = 0.02 ap_attack = 0.016 }",),
            ),
            (
                "wire_guided_hunter_teams",
                "Станковое противотанковое оружие",
                "Crew-served Anti-tank Weapons",
                "ADISCORD_antitank_04_antitank_rifle",
                2161,
                ("category_all_infantry = { hard_attack = 0.028 ap_attack = 0.02 }",),
            ),
            (
                "recoilless_overmatch_cells",
                "Противотанковые мины",
                "Anti-tank Mines",
                "ADISCORD_antitank_05_wire_guidance",
                2161,
                (
                    "category_all_infantry = { ap_attack = 0.028 }",
                    "coordination_bonus = 0.008",
                ),
            ),
            (
                "fire_and_forget_seekers",
                "Станковые противотанковые пушки",
                "Mounted Anti-tank Guns",
                "ADISCORD_antitank_06_recoilless_launcher",
                2164,
                (
                    "category_all_infantry = { hard_attack = 0.032 breakthrough = 0.02 }",
                ),
            ),
            (
                "programmable_anti_armor_fuzes",
                "Ручные противотанковые гранатомёты",
                "Shoulder-fired Anti-tank Launchers",
                "ADISCORD_antitank_07_saclos_guidance",
                2164,
                (
                    "category_all_infantry = { ap_attack = 0.032 }",
                    "coordination_bonus = 0.012",
                ),
            ),
            (
                "top_attack_profiles",
                "Переносные противотанковые ракетные комплексы",
                "Portable Anti-tank Missile Systems",
                "ADISCORD_antitank_08_rocket_launcher",
                2168,
                ("category_all_infantry = { hard_attack = 0.036 ap_attack = 0.032 }",),
            ),
            (
                "loitering_armor_hunters",
                "Усовершенствованные противотанковые пушки",
                "Improved Anti-tank Guns",
                "ADISCORD_antitank_09_top_attack_seeker",
                2168,
                (
                    "category_all_infantry = { ap_attack = 0.036 }",
                    "coordination_bonus = 0.016",
                ),
            ),
            (
                "cooperative_hunter_cells",
                "Противотанковые ракеты",
                "Anti-tank Missiles",
                "ADISCORD_antitank_10_tandem_warhead",
                2172,
                ("category_all_infantry = { hard_attack = 0.04 ap_attack = 0.036 }",),
            ),
            (
                "terminal_overmatch_packages",
                "Противотанковые гранатомёты нового поколения",
                "Next-generation Anti-tank Launchers",
                "ADISCORD_antitank_11_loitering_munition",
                2172,
                (
                    "category_all_infantry = { ap_attack = 0.04 }",
                    "coordination_bonus = 0.02",
                ),
            ),
            (
                "distributed_anti_armor_net",
                "Противотанковые ракеты нового поколения",
                "Next-generation Anti-tank Missiles",
                "ADISCORD_antitank_12_multispectral_targeting",
                2180,
                (
                    "category_all_infantry = { hard_attack = 0.048 ap_attack = 0.048 breakthrough = 0.024 }",
                    "coordination_bonus = 0.024",
                ),
            ),
        ),
    ),
    research_branch(
        "night_combat",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Ночной бой",
        "Night Combat",
        "special_forces",
        (
            (
                "passive_intensifier_cells",
                "Усилители остаточного света",
                "Passive Intensifier Cells",
                "ADISCORD_night_01_passive_intensifier",
                2150,
                ("land_night_attack = 0.01",),
            ),
            (
                "sealed_night_mounts",
                "Защищённые корпуса ночных прицелов",
                "Sealed Night Mounts",
                "ADISCORD_night_01_passive_intensifier",
                2155,
                (
                    "land_night_attack = 0.01",
                    "category_all_infantry = { defense = 0.012 }",
                ),
            ),
            (
                "thermal_observation_channels",
                "Тепловизионные каналы наблюдения",
                "Thermal Observation Channels",
                "ADISCORD_night_02_thermal_channel",
                2158,
                (
                    "land_night_attack = 0.012",
                    "category_recon = { recon = 0.24 }",
                ),
            ),
            (
                "fused_low_light_sights",
                "Комбинированные ночные прицелы",
                "Fused Low-light Sights",
                "ADISCORD_night_03_fused_sight",
                2161,
                (
                    "land_night_attack = 0.014",
                    "category_all_infantry = { soft_attack = 0.012 }",
                ),
            ),
            (
                "low_signature_illumination",
                "Малозаметная подсветка",
                "Low-signature Illumination",
                "ADISCORD_night_05_counter_illumination",
                2161,
                (
                    "land_night_attack = 0.012",
                    "category_all_infantry = { breakthrough = 0.012 }",
                ),
            ),
            (
                "squad_target_sharing",
                "Обмен целями внутри отделения",
                "Squad Target Sharing",
                "ADISCORD_night_04_squad_target_sharing",
                2164,
                (
                    "land_night_attack = 0.014",
                    "coordination_bonus = 0.01",
                ),
            ),
            (
                "counter_illumination_warnings",
                "Датчики вражеской подсветки",
                "Counter-illumination Warnings",
                "ADISCORD_night_05_counter_illumination",
                2164,
                (
                    "land_night_attack = 0.014",
                    "category_all_infantry = { defense = 0.014 }",
                ),
            ),
            (
                "thermal_target_libraries",
                "Распознавание тепловых следов",
                "Thermal Target Libraries",
                "ADISCORD_night_02_thermal_channel",
                2168,
                (
                    "land_night_attack = 0.016",
                    "category_recon = { recon = 0.3 }",
                ),
            ),
            (
                "nocturnal_sensor_discipline",
                "Скрытное ночное наблюдение",
                "Nocturnal Sensor Discipline",
                "ADISCORD_night_03_fused_sight",
                2168,
                (
                    "land_night_attack = 0.016",
                    "category_all_infantry = { defense = 0.016 }",
                ),
            ),
            (
                "distributed_night_engagements",
                "Согласованный огонь ночью",
                "Distributed Night Engagements",
                "ADISCORD_night_06_distributed_engagement",
                2172,
                (
                    "land_night_attack = 0.018",
                    "coordination_bonus = 0.014",
                ),
            ),
            (
                "adaptive_spectrum_concealment",
                "Маскировка от ночных приборов",
                "Adaptive Spectrum Concealment",
                "ADISCORD_night_05_counter_illumination",
                2172,
                (
                    "land_night_attack = 0.018",
                    "category_all_infantry = { breakthrough = 0.018 }",
                ),
            ),
            (
                "nocturnal_combat_mesh",
                "Сеть ночного целеуказания",
                "Nocturnal Combat Mesh",
                "ADISCORD_night_06_distributed_engagement",
                2180,
                (
                    "land_night_attack = 0.024",
                    "coordination_bonus = 0.02",
                    "category_all_infantry = { defense = 0.024 breakthrough = 0.024 }",
                ),
            ),
        ),
    ),
    research_branch(
        "protection",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Защитное снаряжение",
        "Protective Equipment",
        "protection",
        (
            (
                "composite_protection_kits",
                "Композитные бронежилеты",
                "Composite Body Armour",
                "ADISCORD_equipment_armour",
                2150,
                ("category_all_infantry = { defense = 0.04 max_organisation = 0.75 }",),
            ),
            (
                "trauma_plates",
                "Амортизирующие вкладыши брони",
                "Armour Trauma Pads",
                "ADISCORD_equipment_armour",
                2155,
                ("category_all_infantry = { defense = 0.041 reliability = 0.025 }",),
            ),
            (
                "sealed_combat_suits",
                "Герметичные боевые костюмы",
                "Sealed Combat Suits",
                "ADISCORD_equipment_respirator",
                2158,
                (
                    "category_all_infantry = { defense = 0.043 supply_consumption = -0.013 }",
                ),
            ),
            (
                "ceramic_trauma_inserts",
                "Керамические бронепластины",
                "Ceramic Armour Plates",
                "ADISCORD_equipment_armour",
                2160,
                ("category_all_infantry = { defense = 0.044 breakthrough = 0.026 }",),
            ),
            (
                "sealed_respirator_interfaces",
                "Герметичные соединения респираторов",
                "Sealed Respirator Interfaces",
                "ADISCORD_equipment_respirator",
                2162,
                ("category_all_infantry = { default_morale = 0.046 defense = 0.027 }",),
            ),
            (
                "active_hearing_protection",
                "Активная защита слуха",
                "Active Hearing Protection",
                "ADISCORD_equipment_hearing_protection",
                2163,
                ("category_all_infantry = { defense = 0.048 reliability = 0.028 }",),
            ),
            (
                "thermal_signature_liners",
                "Тепломаскирующие подкладки",
                "Thermal-concealment Liners",
                "ADISCORD_equipment_camouflage",
                2164,
                (
                    "category_all_infantry = { defense = 0.049 supply_consumption = -0.014 }",
                ),
            ),
            (
                "powered_load_bearing_harnesses",
                "Силовые разгрузочные системы",
                "Powered Load-bearing Harnesses",
                "ADISCORD_equipment_exoskeleton",
                2165,
                ("category_all_infantry = { defense = 0.05 reliability = 0.029 }",),
            ),
            (
                "exoskeleton_load_frames",
                "Экзоскелетные рамы",
                "Exoskeleton Load Frames",
                "ADISCORD_equipment_exoskeleton",
                2166,
                ("category_all_infantry = { defense = 0.051 breakthrough = 0.03 }",),
            ),
            (
                "reactive_camouflage_textiles",
                "Ткани с изменяемой окраской",
                "Colour-changing Camouflage Fabrics",
                "ADISCORD_equipment_camouflage",
                2169,
                (
                    "category_all_infantry = { defense = 0.055 supply_consumption = -0.016 }",
                ),
            ),
            (
                "adaptive_camouflage",
                "Адаптивная маскировка",
                "Adaptive Camouflage",
                "ADISCORD_equipment_camouflage",
                2170,
                ("category_all_infantry = { default_morale = 0.056 defense = 0.032 }",),
            ),
            (
                "exosuit_joint_actuators",
                "Приводы суставов экзоскелета",
                "Exoskeleton Joint Actuators",
                "ADISCORD_equipment_exoskeleton",
                2171,
                ("category_all_infantry = { defense = 0.058 reliability = 0.033 }",),
            ),
            (
                "adaptive_radiation_shielding",
                "Адаптивная защита от радиации",
                "Adaptive Radiation Protection",
                "ADISCORD_equipment_armour",
                2173,
                (
                    "category_all_infantry = { defense = 0.06 supply_consumption = -0.017 }",
                ),
            ),
            (
                "closed_loop_combat_life_support",
                "Замкнутое жизнеобеспечение",
                "Closed-loop Life Support",
                "ADISCORD_equipment_life_support",
                2174,
                (
                    "category_all_infantry = { defense = 0.061 max_organisation = 1.394 }",
                ),
            ),
            (
                "self_sealing_combat_skins",
                "Самогерметизирующиеся защитные костюмы",
                "Self-Sealing Combat Skins",
                "ADISCORD_equipment_armour",
                2175,
                (
                    "category_all_infantry = { defense = 0.063 max_organisation = 1.432 }",
                ),
            ),
        ),
    ),
    research_branch(
        "assault_infantry",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Штурмовая пехота",
        "Assault Infantry",
        "special_forces",
        (
            (
                "assault_infantry_formations",
                "Штурмовые подразделения",
                "Assault Infantry Formations",
                "tech_advanced_special_forces_training",
                2162,
                (),
            ),
            (
                "assault_group_coordination",
                "Слаживание штурмовых групп",
                "Assault Group Coordination",
                "tech_advanced_special_forces_training",
                2163,
                ("ADISCORD_assault_infantry = { breakthrough = 0.05 }",),
            ),
            (
                "assault_fire_suppression",
                "Огневое подавление",
                "Assault Fire Suppression",
                "support_weapons2",
                2164,
                ("ADISCORD_assault_infantry = { soft_attack = 0.04 }",),
            ),
            (
                "assault_battle_control",
                "Управление штурмовым боем",
                "Assault Battle Control",
                "radio",
                2166,
                ("ADISCORD_assault_infantry = { max_organisation = 2 }",),
            ),
            (
                "assault_forward_supply",
                "Снабжение передовых групп",
                "Forward Assault Group Supply",
                "motorised_infantry",
                2169,
                ("ADISCORD_assault_infantry = { supply_consumption = -0.05 }",),
            ),
            (
                "assault_coordinated_attack",
                "Согласованный штурм",
                "Coordinated Assault",
                "tech_advanced_special_forces_training",
                2172,
                ("ADISCORD_assault_infantry = { breakthrough = 0.05 soft_attack = 0.04 }",),
            ),
        ),
    ),
    research_branch(
        "power_shields",
        "ADISCORD_special.txt",
        (SPECIAL_TECHNOLOGY_FOLDER,),
        "Щитовой спецназ",
        "Shield Special Forces",
        "special_forces",
        (
            (
                "kefreyt_shield_special_forces",
                "Силовые щиты",
                "Power Shields",
                "tech_special_forces",
                2163,
                (),
            ),
            (
                "shield_assault_drills",
                "Взаимодействие щитовых групп",
                "Shield Team Drills",
                "tech_advanced_special_forces_training",
                2166,
                ("ADISCORD_urban_breacher = { defense = 0.04 breakthrough = 0.04 max_organisation = 1 }",),
            ),
            (
                "compact_shield_generators",
                "Компактные генераторы щитов",
                "Compact Shield Generators",
                "tech_special_forces",
                2169,
                (),
            ),
            (
                "shield_field_maintenance",
                "Полевое обслуживание щитов",
                "Shield Field Maintenance",
                "basic_machine_tools",
                2172,
                ("ADISCORD_urban_breacher = { supply_consumption = -0.04 default_morale = 0.03 }",),
            ),
            (
                "adaptive_power_shields",
                "Адаптивные силовые щиты",
                "Adaptive Power Shields",
                "tech_special_forces",
                2175,
                (),
            ),
        ),
    ),
    research_branch(
        "special_forces",
        "ADISCORD_infantry.txt",
        ("infantry_folder",),
        "Разведка и спецназ",
        "Reconnaissance and Special Forces",
        "special_forces",
        (
            (
                "fieldcraft_manuals",
                "Полевая подготовка разведчиков",
                "Scout Fieldcraft Training",
                "ADISCORD_equipment_climbing",
                2150,
                (
                    "category_special_forces = { breakthrough = 0.04 maximum_speed = 0.012 }",
                ),
            ),
            (
                "urban_breaching",
                "Инструменты штурмового вскрытия",
                "Assault Breaching Tools",
                "ADISCORD_equipment_breaching",
                2155,
                (
                    "category_special_forces = { soft_attack = 0.041 breakthrough = 0.041 }",
                ),
            ),
            (
                "radiation_patrols",
                "Разведка заражённой местности",
                "Contaminated-area Reconnaissance",
                "ADISCORD_equipment_respirator",
                2158,
                (
                    "category_recon = { recon = 0.35 }",
                    "category_special_forces = { maximum_speed = 0.013 }",
                ),
            ),
            (
                "subterranean_route_reconnaissance",
                "Разведка подземных маршрутов",
                "Subterranean Route Reconnaissance",
                "ADISCORD_equipment_climbing",
                2160,
                ("category_special_forces = { breakthrough = 0.044 defense = 0.026 }",),
            ),
            (
                "combat_recon_drones",
                "Разведывательные дроны",
                "Combat Recon Drones",
                "ADISCORD_equipment_drone",
                2161,
                (
                    "category_recon = { recon = 0.34 }",
                    "land_night_attack = 0.013",
                ),
            ),
            (
                "urban_vertical_access_rigs",
                "Штурмовое альпинистское снаряжение",
                "Urban Vertical-Access Rigs",
                "ADISCORD_equipment_climbing",
                2162,
                (
                    "category_special_forces = { soft_attack = 0.046 breakthrough = 0.046 }",
                ),
            ),
            (
                "low_observable_infiltration_suits",
                "Маскировочные костюмы разведчиков",
                "Reconnaissance Concealment Suits",
                "ADISCORD_equipment_camouflage",
                2163,
                (
                    "category_recon = { recon = 0.43 }",
                    "category_special_forces = { maximum_speed = 0.014 }",
                ),
            ),
            (
                "autonomous_scout_microdrones",
                "Автономные разведывательные микродроны",
                "Autonomous Scout Microdrones",
                "ADISCORD_equipment_drone",
                2164,
                (
                    "category_recon = { recon = 0.47 }",
                    "category_special_forces = { maximum_speed = 0.014 }",
                ),
            ),
            (
                "vertical_assault_training",
                "Высотная штурмовая подготовка",
                "Vertical Assault Training",
                "ADISCORD_equipment_climbing",
                2166,
                (
                    "category_special_forces = { maximum_speed = 0.03 supply_consumption = -0.015 }",
                ),
            ),
            (
                "multispectral_concealment_discipline",
                "Маскировка от разведдатчиков",
                "Concealment from Reconnaissance Sensors",
                "ADISCORD_equipment_camouflage",
                2168,
                (
                    "category_recon = { recon = 0.55 }",
                    "category_special_forces = { maximum_speed = 0.015 }",
                ),
            ),
            (
                "deep_recon_cells",
                "Группы дальней разведки",
                "Long-range Reconnaissance Teams",
                "ADISCORD_night_04_squad_target_sharing",
                2170,
                (
                    "category_recon = { recon = 0.59 }",
                    "category_special_forces = { maximum_speed = 0.016 }",
                ),
            ),
            (
                "distributed_recon_sensor_caches",
                "Скрытые посты наблюдения",
                "Concealed Sensor Outposts",
                "ADISCORD_night_05_counter_illumination",
                2172,
                (
                    "category_recon = { recon = 0.67 }",
                    "category_special_forces = { maximum_speed = 0.017 }",
                ),
            ),
            (
                "augmented_special_forces",
                "Экзоскелеты спецназа",
                "Special Forces Exoskeletons",
                "ADISCORD_equipment_exoskeleton",
                2180,
                (
                    "category_special_forces = { breakthrough = 0.093 defense = 0.093 max_organisation = 2.131 }",
                ),
            ),
        ),
    ),
    research_branch(
        "combat_medicine",
        "ADISCORD_logistics_trains.txt",
        ('support_folder',),
        "Боевая медицина",
        "Combat Medicine",
        "protection",
        (
            (
                "casualty_evacuation",
                "Эвакуация раненых",
                "Casualty Evacuation",
                "advanced_machine_tools",
                2158,
                (
                    "field_hospital = { casualty_trickleback = 0.03 experience_loss_factor = -0.02 }",
                ),
            ),
            (
                "battlefield_medical_drones",
                "Медицинские дроны",
                "Battlefield Medical Drones",
                "ADISCORD_equipment_medical_drone",
                2161,
                (
                    "field_hospital = { casualty_trickleback = 0.045 experience_loss_factor = -0.027 }",
                ),
            ),
            (
                "trauma_registry_networks",
                "Полевой учёт ранений",
                "Field Casualty Records",
                "ADISCORD_equipment_casualty_monitor",
                2162,
                (
                    'field_hospital = { casualty_trickleback = 0.03 experience_loss_factor = -0.02 }',
                ),
            ),
            (
                "smart_tourniquet_systems",
                "Автоматические кровоостанавливающие жгуты",
                "Smart Tourniquet Systems",
                "ADISCORD_equipment_medical",
                2167,
                (
                    'field_hospital = { casualty_trickleback = 0.03 experience_loss_factor = -0.05 }',
                ),
            ),
            (
                "forward_surgical_cells",
                "Передовые хирургические группы",
                "Forward Surgical Teams",
                "ADISCORD_equipment_medical",
                2169,
                (
                    'field_hospital = { experience_loss_factor = -0.04 casualty_trickleback = 0.03 }',
                ),
            ),
            (
                "nanofiber_wound_dressings",
                "Повязки из нановолокна",
                "Nanofibre Wound Dressings",
                "ADISCORD_equipment_medical",
                2172,
                (
                    "field_hospital = { casualty_trickleback = 0.059 experience_loss_factor = -0.033 }",
                ),
            ),
            (
                "distributed_combat_medicine",
                "Сеть полевой медицинской помощи",
                "Field Medical Care Network",
                "ADISCORD_equipment_medical",
                2175,
                (
                    'field_hospital = { casualty_trickleback = 0.08 experience_loss_factor = -0.05 supply_consumption = -0.04 }',
                ),
            ),
        ),
    ),
    research_branch(
        "field_support",
        "ADISCORD_logistics_trains.txt",
        ('support_folder',),
        "Комплекты и ремонт",
        "Equipment Kits and Maintenance",
        "support",
        (
            (
                "field_workshop_tools",
                "Инструменты полевых мастерских",
                "Field Workshop Tools",
                "support_equipment_1",
                2150,
                (
                    'category_support_battalions = { reliability = 0.02 }',
                ),
            ),
            (
                "modular_support_kits",
                "Модульные комплекты обеспечения",
                "Modular Support Kits",
                "basic_construction",
                2155,
                (
                    'category_support_battalions = { supply_consumption = -0.02 }',
                ),
            ),
            (
                "combat_engineering_sections",
                "Инженерно-штурмовые отделения",
                "Combat Engineering Sections",
                "improved_machine_tools",
                2158,
                (
                    "engineer = { entrenchment = 0.5 defense = 0.04 }",
                    "ADISCORD_regimental_pioneers = { entrenchment = 0.15 defense = 0.02 }",
                ),
            ),
            (
                "standardized_field_tool_chests",
                "Стандартные наборы полевого инструмента",
                "Standardized Field Tool Chests",
                "radio",
                2160,
                (
                    'maintenance_company = { reliability_factor = 0.02 }',
                ),
            ),
            (
                "drone_delivered_repair_spares",
                "Доставка ремкомплектов дронами",
                "Drone-Delivered Repair Spares",
                "support_equipment_1",
                2165,
                (
                    'maintenance_company = { reliability_factor = 0.03 }',
                ),
            ),
            (
                "remote_repair_teams",
                "Дистанционные ремонтные группы",
                "Remote Repair Teams",
                "basic_construction",
                2166,
                (
                    'maintenance_company = { equipment_capture_factor = 0.03 }',
                ),
            ),
            (
                "autonomous_recovery",
                "Автономная эвакуация техники",
                "Autonomous Recovery",
                "improved_construction",
                2170,
                (
                    'maintenance_company = { equipment_capture_factor = 0.04 reliability_factor = 0.02 }',
                ),
            ),
            (
                "predictive_parts_prepositioning",
                "Предиктивное размещение запчастей",
                "Predictive Parts Prepositioning",
                "support_equipment_1",
                2173,
                (
                    'maintenance_company = { reliability_factor = 0.03 supply_consumption = -0.05 }',
                ),
            ),
            (
                "self_sustaining_support",
                "Самодостаточное обеспечение",
                "Self-sustaining Support",
                "support_equipment_1",
                2180,
                (
                    'maintenance_company = { reliability_factor = 0.04 equipment_capture_factor = 0.03 }',
                ),
            ),
        ),
    ),
    research_branch(
        "logistics",
        "ADISCORD_logistics_trains.txt",
        ('support_folder',),
        "Моторизация и логистика",
        "Motorization and Logistics",
        "logistics",
        (
            (
                "pack_transport",
                "Вьючный транспорт",
                "Pack Transport",
                "radio",
                2150,
                (
                    'supply_consumption_factor = -0.01',
                ),
            ),
            (
                "restored_truck_fleets",
                "Восстановленные автоколонны",
                "Restored Truck Fleets",
                "motorised_infantry",
                2155,
                (
                    'army_speed_factor = 0.01',
                ),
            ),
            (
                "standardized_transport_columns",
                "Стандартные транспортные колонны",
                "Standardized Transport Columns",
                "computing_machine",
                2158,
                (
                    'logistics_company = { supply_consumption_factor = -0.02 }',
                ),
            ),
            (
                "forward_supply_hubs",
                "Передовые узлы снабжения",
                "Forward Supply Hubs",
                "improved_computing_machine",
                2161,
                (
                    'logistics_company = { supply_consumption_factor = -0.02 }',
                ),
            ),
            (
                "hardened_logistics_nodes",
                "Защищённые логистические узлы",
                "Hardened Logistics Nodes",
                "train_equipment_3",
                2166,
                (
                    'logistics_company = { supply_consumption_factor = -0.03 }',
                ),
            ),
            (
                "drone_resupply_corridors",
                "Коридоры снабжения дронами",
                "Drone Resupply Corridors",
                "computing_machine",
                2167,
                (
                    'logistics_company = { supply_consumption_factor = -0.03 }',
                ),
            ),
            (
                "route_optimization_ai",
                "ИИ маршрутизации",
                "Route Optimization AI",
                "improved_construction",
                2170,
                (
                    'logistics_company = { supply_consumption_factor = -0.04 fuel_consumption_factor = -0.02 }',
                ),
            ),
            (
                "closed_loop_field_supply",
                "Замкнутый цикл полевого снабжения",
                "Closed-Loop Field Supply",
                "computing_machine",
                2175,
                (
                    'logistics_company = { supply_consumption_factor = -0.04 fuel_consumption_factor = -0.02 }',
                ),
            ),
            (
                "zero_loss_logistics",
                "Безотходная логистика",
                "Zero-loss Logistics",
                "assembly_line_production",
                2180,
                (
                    'logistics_company = { supply_consumption_factor = -0.05 fuel_consumption_factor = -0.03 }',
                ),
            ),
        ),
    ),
    research_branch(
        "rail",
        "ADISCORD_logistics_trains.txt",
        ('support_folder',),
        "Железные дороги",
        "Railway Systems",
        "rail",
        (
            (
                "restored_rail_stock",
                "Восстановленная тяга",
                "Restored Rail Stock",
                "train_equipment_1",
                2150,
                (
                    "supply_consumption_factor = -0.006",
                    "industry_repair_factor = 0.02",
                ),
            ),
            (
                "standard_gauge_recovery",
                "Восстановление единой колеи",
                "Standard Gauge Recovery",
                "basic_construction",
                2155,
                (
                    "supply_consumption_factor = -0.006",
                    "industry_repair_factor = 0.021",
                ),
            ),
            (
                "armored_rail_convoys",
                "Бронированные эшелоны",
                "Armored Rail Convoys",
                "train_equipment_2",
                2158,
                (
                    "supply_consumption_factor = -0.006",
                    "industry_repair_factor = 0.021",
                ),
            ),
            (
                "rail_repair_corps",
                "Корпуса ремонта путей",
                "Rail Repair Corps",
                "advanced_computing_machine",
                2166,
                (
                    "production_speed_infrastructure_factor = 0.015",
                    "industry_repair_factor = 0.026",
                ),
            ),
            (
                "autonomous_rail_dispatch",
                "Автономная диспетчеризация",
                "Autonomous Rail Dispatch",
                "train_equipment_3",
                2170,
                (
                    "supply_consumption_factor = -0.02",
                    "land_reinforce_rate = 0.01",
                ),
            ),
            (
                "smart_railbed_repair_swarms",
                "Рои ремонта железнодорожного полотна",
                "Smart Railbed Repair Swarms",
                "advanced_machine_tools",
                2173,
                (
                    "production_speed_infrastructure_factor = 0.017",
                    "industry_repair_factor = 0.03",
                ),
            ),
        ),
    ),
    research_branch(
        "combat_engineering",
        "ADISCORD_logistics_trains.txt",
        ('support_folder',),
        "Инженерное обеспечение",
        "Combat Engineering",
        "support",
        (
            (
                "battle_damage_survey_teams",
                "Группы оценки боевых повреждений",
                "Battle-damage Survey Teams",
                "basic_machine_tools",
                2162,
                (
                    'engineer = { entrenchment = 0.5 defense = 0.03 }',
                    'ADISCORD_regimental_pioneers = { entrenchment = 0.15 defense = 0.02 }',
                ),
            ),
            (
                "assault_breaching_packages",
                "Штурмовые комплекты разграждения",
                "Assault Breaching Packages",
                "basic_construction",
                2169,
                (
                    "engineer = { breakthrough = 0.05 soft_attack = 0.03 }",
                    "ADISCORD_regimental_pioneers = { breakthrough = 0.03 soft_attack = 0.02 }",
                    "planning_speed = 0.02",
                ),
            ),
            (
                "integrated_engineer_command",
                "Единое инженерное командование",
                "Integrated Engineer Command",
                "improved_machine_tools",
                2175,
                (
                    'engineer = { breakthrough = 0.10 defense = 0.08 }',
                    'ADISCORD_regimental_pioneers = { breakthrough = 0.05 defense = 0.04 }',
                ),
            ),
        ),
    ),
    research_branch(
        "officer_training",
        "ADISCORD_logistics_trains.txt",
        ('support_folder',),
        "Подготовка командного состава",
        "Officer Training",
        "support",
        (
            (
                "reconstituted_staff_academies",
                "Восстановленные штабные академии",
                "Reconstituted Staff Academies",
                "radio",
                2162,
                (
                    "planning_speed = 0.02",
                    "land_reinforce_rate = 0.005",
                    "max_command_power_mult = 0.02",
                ),
            ),
            (
                "assault_command_curriculum",
                "Курс наступательного командования",
                "Assault Command Curriculum",
                "mechanical_computing",
                2164,
                (
                    "planning_speed = 0.03",
                    "category_all_infantry = { breakthrough = 0.02 }",
                ),
            ),
            (
                "defensive_command_curriculum",
                "Курс оборонительного командования",
                "Defensive Command Curriculum",
                "basic_encryption",
                2165,
                (
                    "dig_in_speed_factor = 0.03",
                    "category_all_infantry = { defense = 0.02 }",
                ),
            ),
            (
                "operational_planning_exercises",
                "Оперативные штабные учения",
                "Operational Planning Exercises",
                "computing_machine",
                2167,
                (
                    "planning_speed = 0.04",
                    "max_planning = 0.02",
                    "coordination_bonus = 0.01",
                ),
            ),
            (
                "theater_logistics_wargames",
                "Тыловые манёвры театра",
                "Theater Logistics Wargames",
                "improved_encryption",
                2169,
                (
                    "supply_consumption_factor = -0.015",
                    "land_reinforce_rate = 0.01",
                    "org_loss_when_moving = -0.01",
                ),
            ),
            (
                "rotational_front_commands",
                "Ротация фронтовых командований",
                "Rotational Front Commands",
                "improved_computing_machine",
                2171,
                (
                    "planning_speed = 0.04",
                    "land_reinforce_rate = 0.015",
                    "max_command_power_mult = 0.03",
                ),
            ),
            (
                "predictive_staff_colleges",
                "Коллегии предиктивного планирования",
                "Predictive Staff Colleges",
                "advanced_encryption",
                2173,
                (
                    "coordination_bonus = 0.02",
                    "supply_consumption_factor = -0.02",
                    "max_planning = 0.02",
                ),
            ),
            (
                "adaptive_general_staff",
                "Адаптивный генеральный штаб",
                "Adaptive General Staff",
                "advanced_computing_machine",
                2175,
                (
                    "planning_speed = 0.06",
                    "coordination_bonus = 0.03",
                    "land_reinforce_rate = 0.02",
                    "max_command_power_mult = 0.05",
                ),
            ),
        ),
    ),
    research_branch(
        "artillery",
        "ADISCORD_artillery.txt",
        ('artillery_folder',),
        "Полевая артиллерия",
        "Field Artillery",
        "artillery",
        (
            (
                "restored_field_artillery",
                "Восстановленная артиллерия",
                "Restored Field Artillery",
                "artillery_equipment",
                2150,
                ("category_artillery = { soft_attack = 0.03 reliability = 0.02 }",),
            ),
            (
                "recoil_recovery",
                "Восстановление противооткатных систем",
                "Recoil Recovery",
                "artillery2",
                2155,
                ("category_artillery = { reliability = 0.04 breakthrough = 0.03 }",),
            ),
            (
                "modular_gun_carriages",
                "Модульные лафеты",
                "Modular Gun Carriages",
                "artillery3",
                2158,
                ("category_artillery = { maximum_speed = 0.05 reliability = 0.02 }",),
            ),
            (
                "electrohydraulic_gun_laying",
                "Электрогидравлическое наведение орудий",
                "Electrohydraulic Gun Laying",
                "artillery1",
                2160,
                ("category_artillery = { soft_attack = 0.05 breakthrough = 0.03 }",),
            ),
            (
                "smart_fire_control",
                "Умное управление огнём",
                "Smart Fire Control",
                "artillery4",
                2161,
                ("category_artillery = { soft_attack = 0.08 defense = 0.03 }",),
            ),
            (
                "counterbattery_radar_links",
                "Каналы контрбатарейных РЛС",
                "Counter-battery Radar Links",
                "artillery3",
                2163,
                ("category_artillery = { defense = 0.08 reliability = 0.04 }",),
            ),
            (
                "assisted_projectiles",
                "Корректируемые снаряды",
                "Assisted Projectiles",
                "artillery_equipment",
                2166,
                ("category_artillery = { soft_attack = 0.06 reliability = 0.03 }",),
            ),
            (
                "drone_spotted_batteries",
                "Дроновая корректировка",
                "Drone-spotted Batteries",
                "rocket_artillery_equipment",
                2170,
                ("category_artillery = { soft_attack = 0.08 reliability = 0.04 }",),
            ),
            (
                "uncrewed_howitzer_sections",
                "Необитаемые гаубичные расчёты",
                "Uncrewed Howitzer Sections",
                "rocket_artillery4",
                2175,
                ("category_artillery = { reliability = 0.05 supply_consumption = -0.05 }",),
            ),
            (
                "autonomous_battery_network",
                "Автономная батарейная сеть",
                "Autonomous Battery Network",
                "rocket_artillery4",
                2180,
                (
                    "category_artillery = { soft_attack = 0.10 defense = 0.06 }",
                ),
            ),
        ),
    ),
    research_branch(
        "railway_artillery",
        "ADISCORD_artillery.txt",
        ('artillery_folder',),
        "Железнодорожная артиллерия",
        "Railway Artillery",
        "rail",
        (
            (
                "railway_gun_reactivation",
                "Реактивация железнодорожных орудий",
                "Railway Gun Reactivation",
                "generic_railway_gun",
                2161,
                ("railway_gun = { reliability = 0.03 }",),
            ),
            (
                "recoil_braced_firing_sidings",
                "Огневые тупики с компенсацией отдачи",
                "Recoil-Braced Firing Sidings",
                "advanced_machine_tools",
                2163,
                ("railway_gun = { railway_gun_attack = 0.05 reliability = 0.02 }",),
            ),
            (
                "active_suspension_gun_carriages",
                "Орудийные платформы с активной подвеской",
                "Active-Suspension Gun Carriages",
                "improved_construction",
                2172,
                ("railway_gun = { maximum_speed = 0.05 reliability = 0.04 }",),
            ),
            (
                "over_the_horizon_fire_control",
                "Загоризонтный огонь",
                "Over-the-horizon Fire Control",
                "generic_super_heavy_railway_gun",
                2180,
                ("railway_gun = { railway_gun_attack = 0.08 reliability = 0.04 }",),
            ),
        ),
    ),
    research_branch(
        "anti_tank",
        "ADISCORD_artillery.txt",
        ('artillery_folder',),
        "Противотанковые системы",
        "Anti-tank Systems",
        "anti_tank",
        (
            (
                "salvaged_at_guns",
                "Трофейные противотанковые орудия",
                "Salvaged Anti-tank Guns",
                "antitank1",
                2150,
                ("category_anti_tank = { hard_attack = 0.04 ap_attack = 0.04 }",),
            ),
            (
                "shaped_charges",
                "Кумулятивные заряды",
                "Shaped Charges",
                "antitank2",
                2155,
                ("category_anti_tank = { hard_attack = 0.06 ap_attack = 0.05 }",),
            ),
            (
                "tandem_warheads",
                "Тандемные боевые части",
                "Tandem Warheads",
                "antitank3",
                2158,
                ("category_anti_tank = { ap_attack = 0.08 reliability = 0.02 }",),
            ),
            (
                "scrap_at_launchers",
                "Высокоскоростные противотанковые пушки",
                "High-velocity Anti-tank Guns",
                "anti_tank_equipment",
                2161,
                ("category_anti_tank = { hard_attack = 0.05 defense = 0.03 }",),
            ),
            (
                "imaging_infrared_seekers",
                "Матричные инфракрасные головки наведения",
                "Imaging Infrared Seekers",
                "antitank3",
                2163,
                ("category_anti_tank = { hard_attack = 0.06 reliability = 0.04 }",),
            ),
            (
                "top_attack_munitions",
                "Боеприпасы верхней атаки",
                "Top-attack Munitions",
                "antitank5",
                2166,
                ("category_anti_tank = { hard_attack = 0.06 ap_attack = 0.08 }",),
            ),
            (
                "coil_at_systems",
                "Катушечные ускорители ПТО",
                "Coil Anti-tank Systems",
                "antitank2",
                2170,
                ("category_anti_tank = { ap_attack = 0.08 reliability = 0.03 }",),
            ),
            (
                "superconducting_coil_barrels",
                "Сверхпроводящие катушечные стволы",
                "Superconducting Coil Barrels",
                "anti_tank_equipment",
                2171,
                ("category_anti_tank = { hard_attack = 0.06 defense = 0.04 }",),
            ),
            (
                "hypervelocity_at_networks",
                "Сеть гиперскоростной ПТО",
                "Hypervelocity Anti-tank Networks",
                "antitank2",
                2180,
                (
                    "category_anti_tank = { hard_attack = 0.093 ap_attack = 0.093 reliability = 0.052 }",
                ),
            ),
        ),
    ),
    research_branch(
        "anti_air",
        "ADISCORD_artillery.txt",
        ('artillery_folder',),
        "Противовоздушная оборона",
        "Air Defense",
        "anti_air",
        (
            (
                "improvised_air_defense",
                "Импровизированная ПВО",
                "Improvised Air Defense",
                "antiair1",
                2150,
                ("category_anti_air = { air_attack = 0.04 reliability = 0.012 }",),
            ),
            (
                "radar_laying",
                "Радиолокационное наведение",
                "Radar Laying",
                "antiair2",
                2155,
                ("category_anti_air = { air_attack = 0.06 defense = 0.03 }",),
            ),
            (
                "proximity_fuzes",
                "Радиовзрыватели",
                "Proximity Fuzes",
                "antiair3",
                2158,
                ("category_anti_air = { air_attack = 0.08 reliability = 0.02 }",),
            ),
            (
                "stabilized_autocannon_mounts",
                "Стабилизированные зенитные автопушки",
                "Stabilized Autocannon Mounts",
                "antiair1",
                2160,
                ("category_anti_air = { air_attack = 0.05 reliability = 0.03 }",),
            ),
            (
                "point_defense_aa",
                "Автопушки точечной обороны",
                "Point-defense Air Defense",
                "anti_air_equipment",
                2161,
                ("category_anti_air = { defense = 0.06 reliability = 0.04 }",),
            ),
            (
                "integrated_short_range_missile_cells",
                "Интегрированные ячейки ракет ближнего действия",
                "Integrated Short-range Missile Cells",
                "antiair5",
                2165,
                (
                    "category_anti_air = { air_attack = 0.06 reliability = 0.02 }",
                ),
            ),
            (
                "networked_air_defense",
                "Сетевая противовоздушная оборона",
                "Networked Air Defense",
                "antiair5",
                2166,
                (
                    "category_anti_air = { air_attack = 0.08 defense = 0.04 }",
                ),
            ),
            (
                "high_energy_laser_turrets",
                "Турели высокоэнергетических лазеров",
                "High-energy Laser Turrets",
                "anti_air_equipment",
                2173,
                (
                    "category_anti_air = { air_attack = 0.06 reliability = 0.04 }",
                ),
            ),
            (
                "predictive_airspace_denial_grid",
                "Предиктивная сеть блокирования воздушного пространства",
                "Predictive Airspace-denial Grid",
                "sp_nuclear_isotope_separation",
                2175,
                ("category_anti_air = { air_attack = 0.10 supply_consumption = -0.05 }",),
            ),
            (
                "directed_energy_air_defense",
                "Энергетическая противовоздушная оборона",
                "Directed-energy Air Defense",
                "advanced_centimetric_radar",
                2180,
                (
                    "category_anti_air = { air_attack = 0.093 reliability = 0.093 }",
                ),
            ),
        ),
    ),
    research_branch(
        "recon_armor",
        "ADISCORD_armor.txt",
        ('armour_folder', 'nsb_armour_folder'),
        "Разведывательная бронетехника",
        "Reconnaissance Armor",
        "recon_armor",
        (
            (
                "restored_armored_chassis",
                "Восстановленное лёгкое шасси",
                "Restored Armored Chassis",
                "nsb_engine_tech_1",
                2150,
                ("category_all_armor = { maximum_speed = 0.024 reliability = 0.024 }",),
            ),
            (
                "light_suspension",
                "Облегчённая подвеска",
                "Light Suspension",
                "nsb_armor_tech_1",
                2155,
                ("category_all_armor = { maximum_speed = 0.025 reliability = 0.025 }",),
            ),
            (
                "modular_recon_chassis",
                "Модульное разведывательное шасси",
                "Modular Recon Chassis",
                "basic_machine_tools",
                2158,
                ("category_all_armor = { maximum_speed = 0.025 reliability = 0.025 }",),
            ),
            (
                "sealed_electric_scout_drives",
                "Герметичные электроприводы разведмашин",
                "Sealed Electric Scout Drives",
                "radio",
                2160,
                ("category_all_armor = { maximum_speed = 0.026 reliability = 0.026 }",),
            ),
            (
                "drone_recon_swarms",
                "Программа Р-63 \"След\"",
                "R-63 “Trace” Programme",
                "advanced_light_tank",
                2161,
                ("category_all_armor = { maximum_speed = 0.027 reliability = 0.027 }",),
            ),
            (
                "multispectral_recon_suites",
                "Мультиспектральные разведывательные комплексы",
                "Multispectral Reconnaissance Suites",
                "improved_machine_tools",
                2164,
                (
                    "category_all_armor = { reliability = 0.028 defense = 0.049 }",
                    "category_recon = { recon = 0.4 }",
                ),
            ),
            (
                "signature_management_skins",
                "Обшивка управления сигнатурой",
                "Signature-management Skins",
                "basic_light_tank",
                2169,
                ("category_all_armor = { defense = 0.055 breakthrough = 0.032 }",),
            ),
            (
                "unmanned_recon_vehicles",
                "Необитаемые разведмашины",
                "Unmanned Recon Vehicles",
                "ger_armored_car_equipment_1",
                2170,
                (
                    "category_all_armor = { maximum_speed = 0.032 breakthrough = 0.056 }",
                ),
            ),
            (
                "autonomous_recon_screen",
                "Автономное разведывательное охранение",
                "Autonomous Recon Screen",
                "advanced_centimetric_radar",
                2180,
                (
                    "category_all_armor = { maximum_speed = 0.052 reliability = 0.093 defense = 0.093 }",
                ),
            ),
        ),
    ),
    research_branch(
        "mechanized_mobility",
        "ADISCORD_armor.txt",
        ('armour_folder', 'nsb_armour_folder'),
        "Механизированные войска",
        "Mechanized Forces",
        "recon_armor",
        (
            (
                "armored_carrier_program",
                "Программа М-63 \"Ковчег\"",
                "M-63 “Ark” Programme",
                "mechanized_equipment_1",
                2160,
                (
                    "ADISCORD_mechanized_infantry = { defense = 0.03 reliability = 0.03 }",
                ),
            ),
            (
                "protected_transport_standards",
                "Стандарты защищённой перевозки",
                "Protected Transport Standards",
                "nsb_armor_tech_1",
                2162,
                ("category_all_armor = { maximum_speed = 0.025 reliability = 0.025 }",),
            ),
            (
                "sealed_dismount_compartments",
                "Герметичные десантные отсеки",
                "Sealed Dismount Compartments",
                "nsb_armor_tech_1",
                2164,
                ("category_all_armor = { maximum_speed = 0.026 reliability = 0.026 }",),
            ),
            (
                "escort_protection_arrays",
                "Комплексы защиты машин сопровождения",
                "Escort Protection Arrays",
                "nsb_armor_tech_2",
                2166,
                ("category_all_armor = { maximum_speed = 0.027 reliability = 0.027 }",),
            ),
            (
                "infantry_combat_vehicle_program",
                "Контур М-70 \"Рубеж\"",
                "M-70 “Rampart” Combat Loop",
                "mechanized_equipment_2",
                2168,
                (
                    "ADISCORD_mechanized_infantry = { breakthrough = 0.05 soft_attack = 0.05 hard_attack = 0.03 }",
                ),
            ),
            (
                "unmanned_weapon_stations",
                "Необитаемые башенные установки",
                "Uncrewed Turret Mounts",
                "nsb_engine_tech_1",
                2170,
                ("category_all_armor = { maximum_speed = 0.031 reliability = 0.031 }",),
            ),
            (
                "cooperative_dismount_control",
                "Совместное управление спешиванием",
                "Cooperative Dismount Control",
                "improved_computing_machine",
                2172,
                ("category_all_armor = { maximum_speed = 0.034 reliability = 0.034 }",),
            ),
            (
                "networked_mechanized_cells",
                "Контур М-83 \"Свод\"",
                "M-83 “Vault” Mechanized Loop",
                "mechanized_equipment_3",
                2175,
                (
                    "ADISCORD_mechanized_infantry = { maximum_speed = 0.05 reliability = 0.05 }",
                    "coordination_bonus = 0.02",
                ),
            ),
        ),
    ),
    research_branch(
        "combat_armor",
        "ADISCORD_armor.txt",
        ('armour_folder', 'nsb_armour_folder'),
        "Основные боевые танки",
        "Main Battle Tanks",
        "combat_armor",
        (
            (
                "recovered_medium_chassis",
                "Восстановленный основной боевой танк",
                "Restored Main Battle Tank",
                "nsb_armor_tech_1",
                2150,
                ("category_all_armor = { breakthrough = 0.04 hard_attack = 0.024 }",),
            ),
            (
                "remote_weapon_stations",
                "Дистанционно управляемые башенные установки",
                "Remote-controlled Turret Mounts",
                "nsb_engine_tech_1",
                2155,
                ("category_all_armor = { breakthrough = 0.041 hard_attack = 0.025 }",),
            ),
            (
                "composite_armor_arrays",
                "Массивы композитной брони",
                "Composite Armor Arrays",
                "basic_machine_tools",
                2158,
                ("category_all_armor = { breakthrough = 0.043 hard_attack = 0.025 }",),
            ),
            (
                "electric_turret_drives",
                "Электрические приводы башни",
                "Electric Turret Drives",
                "nsb_engine_tech_2",
                2161,
                ("category_all_armor = { breakthrough = 0.045 hard_attack = 0.027 }",),
            ),
            (
                "semi_autonomous_combat_modules",
                "Контур БТ-62 \"Вожак\"",
                "BT-62 “Lead” Control Loop",
                "generic_modern_tank",
                2162,
                ("category_all_armor = { breakthrough = 0.046 hard_attack = 0.046 }",),
            ),
            (
                "hard_kill_protection_arrays",
                "Комплексы активной защиты жёсткого поражения",
                "Hard-kill Protection Arrays",
                "nsb_engine_tech_3",
                2164,
                ("category_all_armor = { soft_attack = 0.049 maximum_speed = 0.028 }",),
            ),
            (
                "adaptive_fire_control",
                "Адаптивное управление огнём",
                "Adaptive Fire Control",
                "nsb_armor_tech_4",
                2166,
                ("category_all_armor = { hard_attack = 0.051 reliability = 0.03 }",),
            ),
            (
                "multispectral_gunner_sights",
                "Мультиспектральные прицелы наводчика",
                "Multispectral Gunner Sights",
                "nsb_engine_tech_4",
                2167,
                ("category_all_armor = { armor_value = 0.053 default_morale = 0.03 }",),
            ),
            (
                "limited_battle_ai",
                "Ограниченный боевой ИИ",
                "Limited Battle AI",
                "generic_modern_tank",
                2172,
                ("category_all_armor = { hard_attack = 0.059 reliability = 0.033 }",),
            ),
            (
                "electromagnetic_main_guns",
                "Электромагнитные основные орудия",
                "Electromagnetic Main Guns",
                "nsb_engine_tech_2",
                2173,
                ("category_all_armor = { hard_attack = 0.06 breakthrough = 0.05 }",),
            ),
            (
                "adaptive_suspension_control",
                "Адаптивное управление подвеской",
                "Adaptive Suspension Control",
                "advanced_medium_tank",
                2175,
                ("category_all_armor = { maximum_speed = 0.05 reliability = 0.05 }",),
            ),
            (
                "distributed_battlegroup",
                "Распределённая бронегруппа",
                "Distributed Battlegroup",
                "generic_modern_tank",
                2180,
                (
                    "category_all_armor = { hard_attack = 0.09 breakthrough = 0.08 }",
                    "coordination_bonus = 0.02",
                ),
            ),
        ),
    ),
    research_branch(
        "heavy_armor",
        "ADISCORD_armor.txt",
        ('armour_folder', 'nsb_armour_folder'),
        "Тяжёлые и автономные танки",
        "Heavy and Autonomous Tanks",
        "heavy_armor",
        (
            (
                "heavy_recovery_frames",
                "Тяжёлые ремонтные рамы",
                "Heavy Recovery Frames",
                "nsb_armor_tech_1",
                2150,
                ("ADISCORD_heavy_platform = { armor_value = 0.04 defense = 0.024 }",),
            ),
            (
                "reinforced_powertrains",
                "Усиленные силовые установки",
                "Reinforced Powertrains",
                "nsb_engine_tech_1",
                2155,
                ("ADISCORD_heavy_platform = { armor_value = 0.041 defense = 0.025 }",),
            ),
            (
                "heavy_composite_cores",
                "Тяжёлые композитные ядра",
                "Heavy Composite Cores",
                "basic_machine_tools",
                2158,
                ("ADISCORD_heavy_platform = { armor_value = 0.043 defense = 0.025 }",),
            ),
            (
                "remote_repair_sections",
                "Дистанционные ремонтные машины",
                "Remote Repair Sections",
                "generic_armored_support_vehicle_recovery_1",
                2161,
                ("ADISCORD_heavy_platform = { armor_value = 0.045 defense = 0.027 }",),
            ),
            (
                "heavy_platform_cores",
                "Усиленный корпус тяжёлого танка",
                "Reinforced Heavy Tank Hull",
                "super_heavy_tank",
                2166,
                (
                    "ADISCORD_heavy_platform = { armor_value = 0.051 reliability = 0.03 }",
                ),
            ),
            (
                "active_mass_balancing_suspension",
                "Подвеска активного распределения массы",
                "Active Mass-balancing Suspension",
                "main_battle_tank",
                2167,
                (
                    "ADISCORD_heavy_platform = { maximum_speed = 0.03 reliability = 0.053 }",
                ),
            ),
            (
                "autonomous_breakthrough_platforms",
                "Программа Т-71 \"Таран\"",
                "T-71 “Ram” Programme",
                "nsb_engine_tech_1",
                2170,
                (
                    "ADISCORD_heavy_platform = { breakthrough = 0.056 hard_attack = 0.056 }",
                ),
            ),
            (
                "electromagnetic_siege_mortars",
                "Электромагнитные осадные мортиры",
                "Electromagnetic Siege Mortars",
                "nsb_armor_tech_2",
                2172,
                (
                    "ADISCORD_heavy_platform = { soft_attack = 0.059 breakthrough = 0.033 }",
                ),
            ),
            (
                "siege_platform_networks",
                "Контур Т-80 \"Жернов\"",
                "T-80 “Millstone” Siege Loop",
                "generic_land_cruiser_chassis",
                2180,
                (
                    "ADISCORD_heavy_platform = { armor_value = 0.093 breakthrough = 0.093 reliability = 0.052 }",
                ),
            ),
        ),
    ),
    research_branch(
        "unmanned_ground_systems",
        "ADISCORD_armor.txt",
        ('armour_folder', 'nsb_armour_folder'),
        "Беспилотные наземные системы",
        "Unmanned Ground Systems",
        "recon_armor",
        (
            (
                "teleoperated_scout_carts",
                "Телеуправляемые разведывательные машины",
                "Teleoperated Scout Vehicles",
                "nsb_engine_tech_1",
                2162,
                (
                    "category_recon = { recon = 0.5 defense = 0.02 }",
                    "category_all_armor = { reliability = 0.02 }",
                ),
            ),
            (
                "armed_recon_drones",
                "Вооружённые разведывательные платформы",
                "Armed Recon Vehicles",
                "sp_armored_signal",
                2169,
                (
                    "category_recon = { recon = 0.75 soft_attack = 0.04 }",
                    "category_all_armor = { maximum_speed = 0.02 }",
                ),
            ),
            (
                "distributed_ground_swarm_control",
                "Распределённое управление наземным роем",
                "Distributed Ground-swarm Control",
                "sp_armored_signal",
                2175,
                (
                    "category_all_armor = { breakthrough = 0.06 soft_attack = 0.05 }",
                    "coordination_bonus = 0.015",
                ),
            ),
        ),
    ),
    research_branch(
        "fighter",
        "ADISCORD_air.txt",
        ('air_techs_folder', 'bba_air_techs_folder'),
        "Истребительная авиация",
        "Fighter Aviation",
        "fighter",
        (
            (
                "reclaimed_jet_platforms",
                "Программа А-50 \"Искра\"",
                "A-50 “Spark” Programme",
                "early_fighter",
                2150,
                (
                    'fighter = { reliability = 0.02 }',
                ),
            ),
            (
                "standardized_airframes",
                "Стандартные планеры",
                "Standardized Airframes",
                "bba_tech_engines_1",
                2155,
                (
                    'fighter = { reliability = 0.04 air_defence = 0.03 }',
                    'ADISCORD_interceptor = { reliability = 0.04 air_defence = 0.03 }',
                ),
            ),
            (
                "pulse_doppler_radar",
                "Импульсно-доплеровская РЛС",
                "Pulse-Doppler Radar",
                "centimetric_radar",
                2158,
                (
                    'ADISCORD_interceptor = { air_attack = 0.05 }',
                ),
            ),
            (
                "composite_wing_spars",
                "Композитные лонжероны крыла",
                "Composite Wing Spars",
                "bba_tech_aircraft_construction",
                2160,
                (
                    'ADISCORD_interceptor = { air_defence = 0.06 air_agility = 0.03 }',
                ),
            ),
            (
                "high_altitude_interceptors",
                "Реактивные истребители",
                "Jet Fighters",
                "fighter2",
                2161,
                (
                    'fighter = { maximum_speed = 0.03 }',
                ),
            ),
            (
                "electronically_scanned_fighter_radar",
                "РЛС перехватчика с электронным сканированием",
                "Electronically Scanned Interceptor Radar",
                "bba_tech_aircraft_construction",
                2163,
                (
                    'ADISCORD_interceptor = { air_attack = 0.08 air_defence = 0.04 }',
                ),
            ),
            (
                "thrust_vectoring",
                "Управляемый вектор тяги",
                "Thrust Vectoring",
                "jet_fighter1",
                2166,
                (
                    'fighter = { air_agility = 0.06 }',
                ),
            ),
            (
                "low_observable_inlet_geometry",
                "Малозаметная геометрия воздухозаборников",
                "Low-observable Inlet Geometry",
                "fighter2",
                2168,
                (
                    'ADISCORD_interceptor = { air_defence = 0.06 }',
                ),
            ),
            (
                "loyal_wingmen",
                "Истребители с совместным целеуказанием",
                "Cooperative Targeting Fighters",
                "jet_fighter2",
                2170,
                (
                    'fighter = { air_attack = 0.05 }',
                ),
            ),
            (
                "autonomous_dogfight_controller",
                "Автономный контроллер воздушного боя",
                "Autonomous Dogfight Controller",
                "bba_tech_engines_1",
                2173,
                (
                    'ADISCORD_interceptor = { air_attack = 0.06 reliability = 0.04 }',
                ),
            ),
            (
                "distributed_interceptor_swarms",
                "Сетевые истребительные группы",
                "Networked Fighter Groups",
                "jet_fighter2",
                2175,
                (
                    'fighter = { air_agility = 0.04 air_defence = 0.04 }',
                ),
            ),
            (
                "aerospace_interceptors",
                "Высотные истребительные системы",
                "High-altitude Fighter Systems",
                "bba_tech_engines_1",
                2180,
                (
                    'fighter = { air_attack = 0.08 maximum_speed = 0.04 }',
                ),
            ),
        ),
    ),
    research_branch(
        "bomber_maritime",
        "ADISCORD_air.txt",
        ('air_techs_folder', 'bba_air_techs_folder'),
        "Бомбардировщики и морская авиация",
        "Bombers and Maritime Aircraft",
        "air_support",
        (
            (
                "twin_engine_aircraft",
                "Двухмоторные самолёты",
                "Twin-engine Aircraft",
                "tactical_bomber1",
                2160,
                ("ADISCORD_tactical_bomber = { reliability = 0.02 }",),
            ),
            (
                "maritime_patrol_aircraft",
                "Морские патрульные самолёты",
                "Maritime Patrol Aircraft",
                "naval_bomber2",
                2164,
                ("nav_bomber = { air_range = 0.04 }",),
            ),
            (
                "pressurized_bombers",
                "Бомбардировщики с гермокабиной",
                "Pressurized Bombers",
                "tactical_bomber2",
                2164,
                ("ADISCORD_tactical_bomber = { air_defence = 0.04 }",),
            ),
            (
                "airborne_homing_torpedoes",
                "Самонаводящиеся авиационные торпеды",
                "Airborne Homing Torpedoes",
                "bba_tech_armor_piercing_bombs",
                2168,
                (
                    "nav_bomber = { naval_strike_attack = 0.10 naval_strike_targetting = 0.08 }",
                ),
            ),
            (
                "stabilized_bomb_sights",
                "Стабилизированные бомбовые прицелы",
                "Stabilized Bomb Sights",
                "bba_tech_engines_1",
                2168,
                (
                    "ADISCORD_tactical_bomber = { strategic_attack = 0.08 air_ground_attack = 0.06 }",
                ),
            ),
            (
                "long_range_maritime_aircraft",
                "Дальние противокорабельные самолёты",
                "Long-range Maritime Strike Aircraft",
                "naval_bomber3",
                2172,
                ("nav_bomber = { naval_strike_targetting = 0.06 }",),
            ),
            (
                "jet_strike_bombers",
                "Реактивные ударные бомбардировщики",
                "Jet Strike Bombers",
                "jet_tactical_bomber1",
                2172,
                ("ADISCORD_tactical_bomber = { strategic_attack = 0.06 }",),
            ),
            (
                "integrated_strike_navigation",
                "Комплексная прицельно-навигационная система",
                "Integrated Strike Navigation",
                "advanced_centimetric_radar",
                2175,
                (
                    "ADISCORD_tactical_bomber = { air_range = 0.08 strategic_attack = 0.06 }",
                    "nav_bomber = { air_range = 0.08 naval_strike_targetting = 0.06 }",
                ),
            ),
        ),
    ),
    research_branch(
        "air_support",
        "ADISCORD_air.txt",
        ('air_techs_folder', 'bba_air_techs_folder'),
        "Штурмовая авиация",
        "Air Support",
        "air_support",
        (
            (
                "battlefield_attack_aircraft",
                "Программа АШ-50 \"Коршун\"",
                "AS-50 “Kite” Programme",
                "CAS1",
                2150,
                (
                    'cas = { reliability = 0.02 }',
                ),
            ),
            (
                "guided_munitions",
                "Управляемые боеприпасы",
                "Guided Munitions",
                "bba_tech_engines_1",
                2155,
                ("cas = { air_ground_attack = 0.08 }",),
            ),
            (
                "armored_cockpits",
                "Бронированные кабины",
                "Armored Cockpits",
                "radio",
                2158,
                (
                    'cas = { air_defence = 0.08 reliability = 0.03 }',
                ),
            ),
            (
                "vtol_assault_frames",
                "Реактивные штурмовики",
                "Jet Attack Aircraft",
                "CAS2",
                2161,
                (
                    'cas = { maximum_speed = 0.04 }',
                ),
            ),
            (
                "precision_glide_bomb_kits",
                "Штурмовики управляемого вооружения",
                "Precision-weapon Attack Aircraft",
                "CAS2",
                2163,
                (
                    'cas = { air_ground_attack = 0.06 }',
                ),
            ),
            (
                "drone_air_wings",
                "Контур А-65 \"Стая\"",
                "A-65 “Flock” Air-control Loop",
                "CAS3",
                2166,
                (
                    'ADISCORD_strike_drone = { reliability = 0.03 }',
                ),
            ),
            (
                "loitering_strike_drones",
                "Барражирующие ударные беспилотники",
                "Loitering Strike Drones",
                "radio",
                2168,
                (
                    'ADISCORD_strike_drone = { air_range = 0.10 air_ground_attack = 0.08 }',
                ),
            ),
            (
                "cooperative_close_air_control_links",
                "Совместное целеуказание ударных БПЛА",
                "Cooperative Strike Drone Targeting",
                "bba_tech_armor_piercing_bombs",
                2169,
                (
                    'ADISCORD_strike_drone = { air_ground_attack = 0.12 reliability = 0.06 }',
                ),
            ),
            (
                "autonomous_strike_wings",
                "Штурмовики с автоматизированным наведением",
                "Automated Targeting Attack Aircraft",
                "CAS3",
                2170,
                (
                    'cas = { air_ground_attack = 0.05 air_defence = 0.04 }',
                ),
            ),
            (
                "persistent_sensor_strike_loops",
                "Непрерывные разведывательно-ударные контуры",
                "Persistent Sensor-strike Loops",
                "CAS3",
                2175,
                (
                    'cas = { air_range = 0.05 reliability = 0.04 }',
                ),
            ),
            (
                "persistent_air_support",
                "Непрерывная воздушная поддержка",
                "Persistent Air Support",
                "sp_rockets_improved_guidance",
                2180,
                (
                    'cas = { air_ground_attack = 0.08 reliability = 0.06 }',
                ),
            ),
        ),
    ),
    research_branch(
        "strategic_air",
        "ADISCORD_air.txt",
        ('air_techs_folder', 'bba_air_techs_folder'),
        "Дальняя ударная авиация",
        "Long-range Strike Aviation",
        "strategic_air",
        (
            (
                "rocket_test_stands",
                "Проект дальнего ракетоносца",
                "Long-range Missile Carrier Project",
                "rocket_engines",
                2150,
                (
                    'tac_bomber = { reliability = 0.03 }',
                ),
            ),
            (
                "inertial_guidance",
                "Инерциальное наведение",
                "Inertial Guidance",
                "improved_rocket_engines",
                2155,
                (
                    'tac_bomber = { air_range = 0.06 strategic_attack = 0.03 }',
                ),
            ),
            (
                "cruise_missiles",
                "Носители крылатых ракет",
                "Cruise Missile Carriers",
                "centimetric_radar",
                2158,
                (
                    'tac_bomber = { strategic_attack = 0.04 }',
                ),
            ),
            (
                "strategic_rocket_architecture",
                "Усиленные отсеки вооружения",
                "Reinforced Weapon Bays",
                "advanced_rocket_engines",
                2161,
                (
                    'tac_bomber = { air_defence = 0.06 reliability = 0.04 }',
                ),
            ),
            (
                "orbital_tracking_relics",
                "Дальние ракетоносцы с цифровым наведением",
                "Digitally Guided Long-range Missile Carriers",
                "guided_missile_1",
                2166,
                (
                    'tac_bomber = { strategic_attack = 0.05 }',
                ),
            ),
            (
                "hypersonic_glide_vehicles",
                "Высокоскоростное ударное вооружение",
                "High-speed Strike Weapons",
                "centimetric_radar",
                2168,
                (
                    'tac_bomber = { strategic_attack = 0.08 maximum_speed = 0.04 }',
                ),
            ),
            (
                "deep_strike_targeting",
                "Координация глубоких ударов",
                "Deep Strike Targeting",
                "advanced_rocket_engines",
                2170,
                (
                    'tac_bomber = { strategic_attack = 0.10 air_range = 0.05 }',
                ),
            ),
            (
                "suborbital_skip_glide_guidance",
                "Ракетоносцы глубокого проникновения",
                "Deep-penetration Missile Carriers",
                "guided_missile_3",
                2174,
                (
                    'tac_bomber = { air_range = 0.05 air_defence = 0.04 }',
                ),
            ),
            (
                "suborbital_strike_systems",
                "Программа Р-80 \"Стрела\"",
                "R-80 “Arrow” Programme",
                "ballistic_missile_equipment_3",
                2180,
                (
                    'tac_bomber = { strategic_attack = 0.06 reliability = 0.04 }',
                ),
            ),
        ),
    ),
    research_branch(
        "air_mobility",
        "ADISCORD_air.txt",
        ('air_techs_folder', 'bba_air_techs_folder'),
        "Воздушная мобильность",
        "Air Mobility",
        "air_support",
        (
            (
                "restored_airlift_planning",
                "Восстановленное планирование воздушных перевозок",
                "Restored Airlift Planning",
                "radio",
                2162,
                (
                    'transport_plane = { reliability = 0.04 }',
                ),
            ),
            (
                "vertical_envelopment_control",
                "Управление вертикальным охватом",
                "Vertical Envelopment Control",
                "radio",
                2169,
                (
                    'transport_plane = { air_defence = 0.08 air_range = 0.05 }',
                ),
            ),
            (
                "precision_aerial_resupply",
                "Точное воздушное снабжение",
                "Precision Aerial Resupply",
                "bba_tech_armor_piercing_bombs",
                2175,
                (
                    'transport_plane = { air_range = 0.10 reliability = 0.06 }',
                ),
            ),
        ),
    ),
    research_branch(
        "naval_support",
        "ADISCORD_naval.txt",
        ('naval_folder', 'mtgnavalsupportfolder'),
        "Прибрежные силы и эскорт",
        "Littoral Forces and Escort",
        "naval_support",
        (
            (
                "restored_dockyards",
                "Восстановленные верфи",
                "Restored Dockyards",
                "sonar",
                2150,
                (
                    "convoy_escort_efficiency = 0.04",
                    "naval_detection = 0.024",
                ),
            ),
            (
                "coastal_patrols",
                "Прибрежные патрули",
                "Coastal Patrols",
                "basic_torpedo",
                2155,
                (
                    "convoy_escort_efficiency = 0.041",
                    "naval_detection = 0.025",
                ),
            ),
            (
                "convoy_routing",
                "Маршрутизация конвоев",
                "Convoy Routing",
                "improved_sonar",
                2158,
                (
                    "convoy_escort_efficiency = 0.043",
                    "naval_detection = 0.025",
                ),
            ),
            (
                "modular_escort_combat_systems",
                "Модульные боевые системы эскорта",
                "Modular Escort Combat Systems",
                "basic_naval_mines",
                2160,
                (
                    "convoy_escort_efficiency = 0.044",
                    "naval_detection = 0.026",
                ),
            ),
            (
                "variable_depth_sonar",
                "Гидролокаторы переменной глубины",
                "Variable-depth Sonar",
                "advanced_centimetric_radar",
                2163,
                (
                    "naval_detection = 0.028",
                    "naval_mines_effect_reduction = 0.048",
                ),
            ),
            (
                "unmanned_mine_countermeasure_boats",
                "Беспилотные противоминные катера",
                "Unmanned Mine-countermeasure Boats",
                "basic_torpedo",
                2168,
                (
                    "convoy_escort_efficiency = 0.054",
                    "naval_detection = 0.031",
                ),
            ),
            (
                "autonomous_escorts",
                "Автономные корабли эскорта",
                "Autonomous Escorts",
                "basic_naval_mines",
                2170,
                (
                    "naval_detection = 0.032",
                    "naval_mines_effect_reduction = 0.056",
                ),
            ),
            (
                "predictive_convoy_defense_network",
                "Предиктивная сеть обороны конвоев",
                "Predictive Convoy-defense Network",
                "modern_sonar",
                2175,
                (
                    "convoy_escort_efficiency = 0.063",
                    "naval_detection = 0.035",
                ),
            ),
            (
                "distributed_sea_control",
                "Распределённый контроль моря",
                "Distributed Sea Control",
                "homing_torpedo",
                2180,
                (
                    "convoy_escort_efficiency = 0.093",
                    "naval_detection = 0.093",
                    "naval_coordination = 0.052",
                ),
            ),
        ),
    ),
    research_branch(
        "surface_fleet",
        "ADISCORD_naval.txt",
        ('naval_folder', 'mtgnavalfolder'),
        "Надводный флот",
        "Surface Fleet",
        "surface_fleet",
        (
            (
                "recovered_fire_control",
                "Восстановленное управление огнём",
                "Recovered Fire Control",
                "basic_cruiser_armor_scheme",
                2150,
                (
                    "naval_hit_chance = 0.024",
                    "naval_coordination = 0.024",
                ),
            ),
            (
                "modular_hull_standards",
                "Модульные стандарты корпусов",
                "Modular Hull Standards",
                "decimetric_radar",
                2155,
                (
                    "naval_hit_chance = 0.025",
                    "naval_coordination = 0.025",
                ),
            ),
            (
                "radar_gunnery",
                "Радиолокационная стрельба",
                "Radar Gunnery",
                "improved_cruiser_armor_scheme",
                2158,
                ("heavy_cruiser = { hg_attack = 0.06 }",),
            ),
            (
                "missile_batteries",
                "Корабельные ракетные батареи",
                "Missile Batteries",
                "advanced_cruiser_armor_scheme",
                2161,
                ("heavy_cruiser = { hg_attack = 0.08 }",),
            ),
            (
                "modular_vertical_launch_cells",
                "Модульные установки вертикального пуска",
                "Modular Vertical-launch Cells",
                "naval_air_operations",
                2163,
                (
                    "naval_detection = 0.048",
                    "convoy_escort_efficiency = 0.028",
                ),
            ),
            (
                "networked_task_groups",
                "Сетевые оперативные группы",
                "Networked Task Groups",
                "decimetric_radar",
                2166,
                (
                    "naval_hit_chance = 0.051",
                    "naval_coordination = 0.03",
                ),
            ),
            (
                "railgun_batteries",
                "Корабельные рельсовые батареи",
                "Railgun Batteries",
                "advanced_centimetric_radar",
                2170,
                (
                    "naval_speed_factor = 0.032",
                    "naval_hit_chance = 0.056",
                ),
            ),
            (
                "drone_carrier_deck_systems",
                "Палубные комплексы носителей беспилотников",
                "Drone-carrier Deck Systems",
                "air_defence",
                2172,
                (
                    "naval_hit_chance = 0.059",
                    "naval_coordination = 0.033",
                ),
            ),
            (
                "distributed_horizon_targeting",
                "Распределённое загоризонтное целеуказание",
                "Distributed Horizon Targeting",
                "improved_cruiser_armor_scheme",
                2175,
                (
                    "naval_detection = 0.063",
                    "convoy_escort_efficiency = 0.035",
                ),
            ),
            (
                "horizon_fleet_command",
                "Загоризонтное управление флотом",
                "Horizon Fleet Command",
                "improved_centimetric_radar",
                2180,
                (
                    "naval_hit_chance = 0.093",
                    "naval_coordination = 0.093",
                    "naval_detection = 0.052",
                ),
            ),
        ),
    ),
    research_branch(
        "subsurface",
        "ADISCORD_naval.txt",
        ('naval_folder', 'mtgnavalfolder'),
        "Подводные силы",
        "Subsurface Forces",
        "subsurface",
        (
            (
                "sonar_archives",
                "Архивы гидроакустики",
                "Sonar Archives",
                "sonar",
                2150,
                (
                    "naval_detection = 0.024",
                    "naval_mines_effect_reduction = 0.04",
                ),
            ),
            (
                "quiet_propulsion",
                "Малошумные движители",
                "Quiet Propulsion",
                "basic_submarine_snorkel",
                2155,
                (
                    "naval_detection = 0.025",
                    "naval_mines_effect_reduction = 0.041",
                ),
            ),
            (
                "homing_torpedoes",
                "Самонаводящиеся торпеды",
                "Homing Torpedoes",
                "basic_torpedo",
                2158,
                ("submarine = { torpedo_attack = 0.08 }",),
            ),
            (
                "air_independent_cells",
                "Воздухонезависимые ячейки",
                "Air-independent Cells",
                "improved_sonar",
                2161,
                ("submarine = { naval_range = 0.10 }",),
            ),
            (
                "wake_homing_torpedo_seekers",
                "Головки наведения торпед по кильватерному следу",
                "Wake-homing Torpedo Seekers",
                "improved_submarine_snorkel",
                2163,
                (
                    "naval_hit_chance = 0.048",
                    "naval_coordination = 0.028",
                ),
            ),
            (
                "seabed_sensor_webs",
                "Донные сенсорные сети",
                "Seabed Sensor Webs",
                "advanced_submarine_warfare",
                2166,
                (
                    "naval_detection = 0.051",
                    "naval_mines_effect_reduction = 0.03",
                ),
            ),
            (
                "autonomous_submarines",
                "Автономные подлодки",
                "Autonomous Submarines",
                "submarine_mine_laying",
                2170,
                (
                    "naval_coordination = 0.056",
                    "naval_detection = 0.032",
                ),
            ),
            (
                "self_repairing_pressure_hulls",
                "Самовосстанавливающиеся прочные корпуса",
                "Self-repairing Pressure Hulls",
                "homing_torpedo",
                2175,
                (
                    "naval_detection = 0.035",
                    "naval_mines_effect_reduction = 0.063",
                ),
            ),
            (
                "deep_ocean_denial",
                "Глубоководное сдерживание",
                "Deep-ocean Denial",
                "advanced_submarine_warfare",
                2180,
                (
                    "naval_detection = 0.093",
                    "naval_mines_effect_reduction = 0.093",
                    "naval_coordination = 0.052",
                ),
            ),
        ),
    ),
    research_branch(
        "amphibious_operations",
        "ADISCORD_naval.txt",
        ("naval_folder", "mtgnavalsupportfolder"),
        "Морской десант",
        "Amphibious Operations",
        "naval_support",
        (
            (
                "amphibious_formation_organization",
                "Организация десантных соединений",
                "Amphibious Formation Organization",
                "transport",
                2160,
                ("naval_invasion_division_cap = 2",),
            ),
            (
                "amphibious_staff_sections",
                "Штабы десантных операций",
                "Amphibious Operation Staffs",
                "marines_expeditionary_medium",
                2161,
                ("naval_invasion_plan_cap = 1",),
            ),
            (
                "amphibious_embarkation_schedules",
                "Графики десантной погрузки",
                "Amphibious Embarkation Schedules",
                "transport",
                2162,
                ("naval_invasion_prep_days = -5",),
            ),
            (
                "amphibious_landing_craft",
                "Десантные катера",
                "Landing Craft",
                "landing_craft",
                2163,
                ("amphibious_invasion = 0.05",),
            ),
            (
                "amphibious_shore_parties",
                "Береговые разгрузочные команды",
                "Landing Shore Parties",
                "marines_shore_parties_medium",
                2164,
                ("amphibious_invasion = 0.05",),
            ),
            (
                "amphibious_loading_rehearsals",
                "Отработка десантной погрузки",
                "Amphibious Loading Rehearsals",
                "marines_expeditionary_support_medium",
                2166,
                ("naval_invasion_prep_days = -5",),
            ),
            (
                "amphibious_assault_landing_systems",
                "Штурмовые высадочные средства",
                "Assault Landing Systems",
                "tank_landing_craft",
                2169,
                ("naval_invasion_penalty = -0.05",),
            ),
            (
                "amphibious_wave_coordination",
                "Координация десантных волн",
                "Landing Wave Coordination",
                "marines_expeditionary_support_medium",
                2172,
                (
                    "naval_invasion_division_cap = 2",
                    "naval_invasion_plan_cap = 1",
                ),
            ),
            (
                "amphibious_integrated_operations",
                "Комплексные десантные операции",
                "Integrated Amphibious Operations",
                "tank_landing_craft",
                2175,
                (
                    "naval_invasion_prep_days = -10",
                    "amphibious_invasion = 0.05",
                ),
            ),
        ),
    ),
    research_branch(
        "riverine_warfare",
        "ADISCORD_naval.txt",
        ('naval_folder', 'mtgnavalfolder', 'mtgnavalsupportfolder'),
        "Речные и десантные операции",
        "Riverine and Amphibious Operations",
        "naval_support",
        (
            (
                "shallow_water_navigation_tables",
                "Таблицы мелководной навигации",
                "Shallow-water Navigation Tables",
                "sonar",
                2162,
                (
                    "naval_detection = 0.02",
                    "naval_mines_effect_reduction = 0.02",
                    "convoy_escort_efficiency = 0.02",
                ),
            ),
            (
                "modular_landing_causeways",
                "Модульные десантные эстакады",
                "Modular Landing Causeways",
                "advanced_sonar",
                2169,
                (
                    "naval_invasion_prep_speed = 0.05",
                    "naval_invasion_penalty = -0.03",
                    "shore_bombardment_bonus = 0.03",
                ),
            ),
            (
                "rapid_beachhead_logistics",
                "Быстрая логистика плацдарма",
                "Rapid Beachhead Logistics",
                "advanced_centimetric_radar",
                2175,
                (
                    "naval_invasion_planning_bonus_speed = 0.08",
                    "supply_consumption_factor = -0.01",
                    "convoy_escort_efficiency = 0.03",
                ),
            ),
        ),
    ),
    research_branch(
        "counter_drone_warfare",
        "ADISCORD_electronics.txt",
        ('electronics_folder',),
        "РЭБ и противодроновая борьба",
        "Electronic and Counter-drone Warfare",
        "signals",
        (
            (
                "spectrum_threat_libraries",
                "Библиотеки спектральных угроз",
                "Spectrum Threat Libraries",
                "radio",
                2162,
                (
                    "encryption_factor = 0.02",
                    "decryption_factor = 0.02",
                    "air_interception_detect_factor = 0.01",
                ),
            ),
            (
                "offensive_jamming_cells",
                "Ячейки наступательного подавления",
                "Offensive Jamming Cells",
                "basic_decryption",
                2169,
                (
                    "decryption_factor = 0.04",
                    "coordination_bonus = 0.01",
                    "air_mission_efficiency = 0.01",
                ),
            ),
            (
                "passive_drone_detection_meshes",
                "Пассивные сети обнаружения дронов",
                "Passive Drone-detection Meshes",
                "radio_detection",
                2169,
                (
                    "encryption_factor = 0.04",
                    "air_interception_detect_factor = 0.03",
                    "air_home_defence_factor = 0.02",
                ),
            ),
            (
                "cognitive_emitter_spoofing",
                "Когнитивная подмена излучателей",
                "Cognitive Emitter Spoofing",
                "improved_decryption",
                2172,
                (
                    "decryption_factor = 0.05",
                    "enemy_army_bonus_air_superiority_factor = -0.02",
                    "coordination_bonus = 0.01",
                ),
            ),
            (
                "hardened_command_waveforms",
                "Защищённые командные сигналы",
                "Hardened Command Waveforms",
                "improved_encryption",
                2172,
                (
                    "encryption_factor = 0.05",
                    "land_reinforce_rate = 0.01",
                    "air_accidents_factor = -0.01",
                ),
            ),
            (
                "adaptive_spectrum_dominance",
                "Адаптивное господство в спектре",
                "Adaptive Spectrum Dominance",
                "advanced_encryption",
                2175,
                (
                    "encryption_factor = 0.05",
                    "decryption_factor = 0.05",
                    "coordination_bonus = 0.03",
                    "air_mission_efficiency = 0.03",
                ),
            ),
            (
                "distributed_spectrum_monitoring",
                "Распределённый контроль спектра",
                "Distributed Spectrum Monitoring",
                "advanced_radar",
                2180,
                (
                    "air_interception_detect_factor = 0.03",
                    "decryption_factor = 0.03",
                ),
            ),
        ),
    ),
)


BRANCHES += (
    research_branch(
        "semiconductors",
        "ADISCORD_electronics.txt",
        ('electronics_folder',),
        "Полупроводники",
        "Semiconductors",
        "computing",
        (
            (
                "semiconductor_clean_rooms",
                "Чистые помещения микроэлектроники",
                "Semiconductor Clean Rooms",
                "electronic_mechanical_engineering",
                2160,
                (
                    "production_factory_efficiency_gain_factor = 0.02",
                ),
            ),
            (
                "silicon_feedstock_purification",
                "Очистка полупроводникового сырья",
                "Silicon Feedstock Purification",
                "mechanical_computing",
                2162,
                (
                    "production_factory_max_efficiency_factor = 0.02",
                    "research_speed_factor = 0.01",
                ),
            ),
            (
                "precision_photolithography",
                "Прецизионная фотолитография",
                "Precision Photolithography",
                "computing_machine",
                2164,
                (
                    "research_speed_factor = 0.015",
                    "production_factory_efficiency_gain_factor = 0.02",
                ),
            ),
            (
                "fault_tolerant_chip_packaging",
                "Отказоустойчивая сборка микросхем",
                "Fault-tolerant Chip Packaging",
                "improved_computing_machine",
                2167,
                (
                    "line_change_production_efficiency_factor = 0.03",
                    "production_factory_start_efficiency_factor = 0.02",
                ),
            ),
            (
                "high_density_integrated_circuits",
                "Интегральные схемы высокой плотности",
                "High-density Integrated Circuits",
                "improved_computing_machine",
                2170,
                (
                    "research_speed_factor = 0.015",
                    "industrial_capacity_factory = 0.02",
                    "factory_energy_consumption = 0.02",
                ),
            ),
            (
                "optical_chip_interconnects",
                "Оптические межсоединения микросхем",
                "Optical Chip Interconnects",
                "advanced_computing_machine",
                2173,
                (
                    "research_speed_factor = 0.015",
                    "factory_energy_consumption = -0.02",
                ),
            ),
            (
                "automated_wafer_inspection",
                "Автоматическая проверка пластин",
                "Automated Wafer Inspection",
                "advanced_computing_machine",
                2176,
                (
                    "production_factory_efficiency_gain_factor = 0.03",
                    "production_factory_max_efficiency_factor = 0.02",
                ),
            ),
            (
                "three_dimensional_chip_stacking",
                "Объёмная компоновка микросхем",
                "Three-dimensional Chip Stacking",
                "advanced_computing_machine",
                2180,
                (
                    "research_speed_factor = 0.02",
                    "industrial_capacity_factory = 0.02",
                    "factory_energy_consumption = 0.02",
                ),
            ),
        ),
    ),
)


# Hull research is separate from fleet-wide equipment and operational upgrades.
NAVAL_HULL_YEARS = (2155, 2163, 2170, 2175)
NAVAL_HULL_CLASSES = {
    "destroyer": ("Эсминцы", "Destroyers", "Эсминец", "Destroyer", "escort_ship", "naval_support"),
    "light_cruiser": ("Лёгкие крейсеры", "Light Cruisers", "Лёгкий крейсер", "Light Cruiser", "light_cruiser", "surface_fleet"),
    "heavy_cruiser": ("Тяжёлые крейсеры", "Heavy Cruisers", "Тяжёлый крейсер", "Heavy Cruiser", "cruiser", "surface_fleet"),
    "battleship": ("Линкоры", "Battleships", "Линкор", "Battleship", "battleship", "surface_fleet"),
    "carrier": ("Авианосцы", "Carriers", "Авианосец", "Carrier", "carrier", "surface_fleet"),
    "submarine": ("Подлодки", "Submarines", "Подводная лодка", "Submarine", "submarine", "subsurface"),
}
NAVAL_CARD_NAMES_RU = {
    "light_cruiser": "Лёгк. крейсер",
    "heavy_cruiser": "Тяж. крейсер",
    "submarine": "Подлодка",
}
NAVAL_HULL_BRANCH_KEYS = frozenset(f"{kind}_hulls" for kind in NAVAL_HULL_CLASSES)
NAVAL_HULL_ART = {
    f"ADISCORD_naval_{kind}_{year}": f"{era}_{kind}"
    for kind in NAVAL_HULL_CLASSES
    for year, era in zip(NAVAL_HULL_YEARS, ("basic", "improved", "advanced", "modern"), strict=True)
}


# Side programmes improve the existing fleet independently of hull replacement.
# Their IDs, effects and dates retain one authoritative definition above.
NAVAL_SIDE_PROGRAMMES = {
    "destroyer": (
        ("variable_depth_sonar", "unmanned_mine_countermeasure_boats", "predictive_convoy_defense_network"),
    ),
    "light_cruiser": (
        ("modular_escort_combat_systems", "autonomous_escorts"),
        ("networked_task_groups",),
    ),
    "heavy_cruiser": (
        ("missile_batteries", "modular_vertical_launch_cells"),
    ),
    "battleship": (
        ("railgun_batteries", "distributed_horizon_targeting"),
    ),
    "carrier": (
        tuple(f"cv_fighter_research_{year}" for year in NAVAL_HULL_YEARS),
        tuple(f"cv_bomber_research_{year}" for year in NAVAL_HULL_YEARS),
        ("drone_carrier_deck_systems",),
    ),
    "submarine": (
        ("wake_homing_torpedo_seekers", "autonomous_submarines"),
        ("air_independent_cells", "seabed_sensor_webs", "self_repairing_pressure_hulls"),
    ),
}
NAVAL_UPGRADE_ICONS = {
    "variable_depth_sonar": "improved_sonar",
    "unmanned_mine_countermeasure_boats": "basic_naval_mines",
    "predictive_convoy_defense_network": "improved_centimetric_radar",
    "modular_escort_combat_systems": "basic_fire_control_system",
    "autonomous_escorts": "advanced_fire_control_system",
    "networked_task_groups": "improved_fire_control_system",
    "missile_batteries": "ADISCORD_naval_missile_systems",
    "modular_vertical_launch_cells": "ADISCORD_naval_missile_systems",
    "railgun_batteries": "advanced_heavy_battery",
    "distributed_horizon_targeting": "improved_centimetric_radar",
    "drone_carrier_deck_systems": "naval_air_operations",
    "wake_homing_torpedo_seekers": "homing_torpedo",
    "autonomous_submarines": "advanced_sonar",
    "air_independent_cells": "improved_submarine_snorkel",
    "seabed_sensor_webs": "advanced_sonar",
    "self_repairing_pressure_hulls": "damage_control_3",
}

NAVAL_MOVED_TECH_KEYS = {
    key
    for programmes in NAVAL_SIDE_PROGRAMMES.values()
    for programme in programmes
    for key in programme
    if not key.startswith(("cv_fighter_research_", "cv_bomber_research_"))
}
NAVAL_UPGRADE_ORIGINS = {
    tech.key: (branch, index)
    for branch in BRANCHES
    for index, tech in enumerate(branch.techs)
    if tech.key in NAVAL_MOVED_TECH_KEYS
}
NAVAL_AIR_RESEARCH = {
    f"{family}_research_{year}": (f"ADISCORD_{family}_{year}", icon)
    for family, icons in (
        ("cv_fighter", ("fighter1", "fighter2", "fighter3", "jet_fighter1")),
        ("cv_bomber", ("naval_bomber1", "naval_bomber2", "naval_bomber3", "naval_bomber3")),
    )
    for year, icon in zip(NAVAL_HULL_YEARS, icons, strict=True)
}


def build_naval_hull_branches() -> tuple[Branch, ...]:
    branches = []
    for kind, (ru, en, model_ru, model_en, _, profile) in NAVAL_HULL_CLASSES.items():
        rows = [
            (
                year,
                Tech(
                    f"{kind}_hull_{year}",
                    f"{NAVAL_CARD_NAMES_RU.get(kind, model_ru)} {year}",
                    f"{model_en} {year}",
                    f"ADISCORD_naval_{kind}_{year}",
                ),
            )
            for year in NAVAL_HULL_YEARS
        ]
        for programme in NAVAL_SIDE_PROGRAMMES[kind]:
            for key in programme:
                if key in NAVAL_AIR_RESEARCH:
                    year = int(key.rsplit("_", 1)[1])
                    fighter = key.startswith("cv_fighter_")
                    rows.append((year, Tech(
                        key,
                        f"Пал. {'истребитель' if fighter else 'торпедоносец'} {year}",
                        f"Carrier {'Fighter' if fighter else 'Torpedo Bomber'} {year}",
                        NAVAL_AIR_RESEARCH[key][1],
                    )))
                else:
                    origin, index = NAVAL_UPGRADE_ORIGINS[key]
                    rows.append((origin.years[index], origin.techs[index]))
        # Hulls precede their same-year equipment packages in the native DAG.
        rows.sort(key=lambda row: row[0])
        branches.append(Branch(
            f"{kind}_hulls", "ADISCORD_naval.txt",
            ("naval_folder", "mtgnavalfolder"), ru, en, profile,
            tuple(tech for _, tech in rows), tuple(year for year, _ in rows),
        ))
    return tuple(branches)


def retain_shared_naval_programme(branch: Branch) -> Branch:
    rows = [
        (tech, year)
        for tech, year in zip(branch.techs, branch.years, strict=True)
        if tech.key not in NAVAL_MOVED_TECH_KEYS
    ]
    folders = branch.folders
    if branch.key in {"surface_fleet", "subsurface", "riverine_warfare"}:
        folders = ("naval_folder", "mtgnavalsupportfolder")
    return replace(
        branch, folders=folders,
        techs=tuple(tech for tech, _ in rows), years=tuple(year for _, year in rows),
    )


BRANCHES = build_naval_hull_branches() + tuple(
    retain_shared_naval_programme(branch) for branch in BRANCHES
)


SUPPORT_SERVICE_BRANCHES = (
    research_branch(
        "reserve_training",
        "ADISCORD_logistics_trains.txt",
        ("support_folder",),
        "Ополчение и территориальная оборона",
        "Militia and Territorial Defence",
        "support",
        (
            (
                "reserve_cadre_training",
                "Кадры местного резерва",
                "Local Reserve Cadres",
                "infantry_weapons",
                2158,
                (
                    "ADISCORD_militia = { max_organisation = 2 }",
                    "ADISCORD_territorial = { max_organisation = 2 }",
                ),
            ),
            (
                "militia_patrol_training",
                "Подготовка местных дозоров",
                "Local Patrol Training",
                "tech_recon",
                2160,
                (
                    "ADISCORD_militia = { defense = 0.05 default_morale = 0.03 }",
                ),
            ),
            (
                "territorial_defence_plans",
                "Планы территориальной обороны",
                "Territorial Defence Plans",
                "tech_engineers",
                2160,
                (
                    "ADISCORD_territorial = { defense = 0.05 entrenchment = 0.5 }",
                ),
            ),
            (
                "militia_replacement_cadres",
                "Учебные кадры ополчения",
                "Militia Replacement Cadres",
                "infantry_weapons",
                2163,
                (
                    "ADISCORD_militia = { max_organisation = 3 default_morale = 0.02 }",
                ),
            ),
            (
                "territorial_strongpoint_networks",
                "Сеть опорных пунктов",
                "Strongpoint Networks",
                "tech_engineers2",
                2163,
                (
                    "ADISCORD_territorial = { defense = 0.05 entrenchment = 0.5 }",
                ),
            ),
            (
                "militia_field_supply",
                "Снабжение местных отрядов",
                "Local Detachment Supply",
                "tech_logistics_company",
                2167,
                (
                    "ADISCORD_militia = { supply_consumption = -0.05 max_organisation = 2 }",
                ),
            ),
            (
                "territorial_reserve_rotation",
                "Ротация территориального резерва",
                "Territorial Reserve Rotation",
                "infantry_weapons",
                2167,
                (
                    "ADISCORD_territorial = { max_organisation = 2 default_morale = 0.04 }",
                ),
            ),
        ),
    ),
    research_branch(
        "field_reconnaissance",
        "ADISCORD_logistics_trains.txt",
        ("support_folder",),
        "Войсковая разведка",
        "Field Reconnaissance",
        "support",
        (
            (
                "foot_recon_sections",
                "Пешая разведывательная рота",
                "Foot Reconnaissance Company",
                "tech_recon",
                2158,
                (
                    "recon = { recon = 0.25 }",
                ),
            ),
            (
                "patrol_observation_posts",
                "Наблюдательные посты и дозоры",
                "Observation Posts and Patrols",
                "tech_recon",
                2162,
                (
                    "recon = { recon = 0.5 }",
                ),
            ),
            (
                "recon_target_handoffs",
                "Передача разведданных",
                "Reconnaissance Reporting",
                "radio",
                2166,
                (
                    "recon = { recon = 0.5 initiative = 0.02 }",
                ),
            ),
            (
                "persistent_recon_patrols",
                "Сменные разведывательные группы",
                "Rotating Reconnaissance Teams",
                "tech_recon",
                2170,
                (
                    "recon = { recon = 0.5 supply_consumption = -0.05 }",
                ),
            ),
        ),
    ),
    research_branch(
        "field_signals",
        "ADISCORD_logistics_trains.txt",
        ("support_folder",),
        "Полевая связь",
        "Field Signals",
        "support",
        (
            (
                "field_signal_sections",
                "Рота полевой связи",
                "Field Signal Company",
                "tech_signal_company",
                2160,
                (
                    "signal_company = { initiative = 0.03 }",
                ),
            ),
            (
                "redundant_field_lines",
                "Резервные линии связи",
                "Redundant Field Lines",
                "radio",
                2163,
                (
                    "signal_company = { initiative = 0.04 max_organisation = 2 }",
                ),
            ),
            (
                "mobile_signal_relays",
                "Подвижные узлы связи",
                "Mobile Signal Relays",
                "tech_signal_company",
                2167,
                (
                    "signal_company = { initiative = 0.05 }",
                ),
            ),
            (
                "integrated_field_dispatch",
                "Единая служба боевой связи",
                "Integrated Field Dispatch",
                "tech_signal_company",
                2172,
                (
                    "signal_company = { initiative = 0.06 default_morale = 0.05 }",
                ),
            ),
        ),
    ),
    research_branch(
        "garrison_security",
        "ADISCORD_logistics_trains.txt",
        ("support_folder",),
        "Гарнизонная служба",
        "Garrison Service",
        "support",
        (
            (
                "garrison_police_sections",
                "Рота военной полиции",
                "Military Police Company",
                "tech_military_police",
                2160,
                (
                    "military_police = { suppression_factor = 0.05 }",
                ),
            ),
            (
                "garrison_patrol_coordination",
                "Координация гарнизонных патрулей",
                "Garrison Patrol Coordination",
                "tech_military_police",
                2164,
                (
                    "military_police = { suppression_factor = 0.10 }",
                ),
            ),
            (
                "garrison_service_records",
                "Учёт гарнизонной службы",
                "Garrison Service Records",
                "tech_military_police",
                2168,
                (
                    "military_police = { suppression_factor = 0.10 supply_consumption = -0.05 }",
                ),
            ),
        ),
    ),
)
BRANCHES += SUPPORT_SERVICE_BRANCHES

SUPPORT_BRANCH_ORDER = (
    "field_support", "combat_engineering", "combat_medicine", "logistics",
    "field_signals", "field_reconnaissance", "reserve_training",
    "garrison_security", "officer_training", "rail",
)
_support_branches = {branch.key: branch for branch in BRANCHES if "support_folder" in branch.folders}
_ordered_support = iter(_support_branches[key] for key in SUPPORT_BRANCH_ORDER)
BRANCHES = tuple(
    next(_ordered_support) if "support_folder" in branch.folders else branch
    for branch in BRANCHES
)


SIDE_PROGRAMME_KEYS = frozenset(
    [
        'air_mobility',
        'combat_engineering',
        'counter_drone_warfare',
        'railway_artillery',
        'riverine_warfare',
        'unmanned_ground_systems',
    ]
)

MAIN_BRANCH_KEYS_BY_FOLDER = {
    "industry_folder": [
        'advanced_materials',
        'industry_organization',
        'production',
        'public_finance',
        'reconstruction',
        'resources',
        'synthetic_rubber',
        'synthetic_oil',
    ],
    "electronics_folder": ['semiconductors', 'computing', 'power', 'signals'],
    "infantry_folder": [
        'anti_tank_infantry',
        'night_combat',
        'protection',
        'small_arms',
        'assault_rifles',
        'squad_weapons',
        'special_forces',
        'assault_infantry',
    ],
    SPECIAL_TECHNOLOGY_FOLDER: ['power_shields'],
    "support_folder": [
        'reserve_training',
        'field_reconnaissance',
        'field_signals',
        'garrison_security',
        'combat_medicine',
        'field_support',
        'logistics',
        'officer_training',
        'rail',
    ],
    "artillery_folder": ['anti_air', 'anti_tank', 'artillery'],
    "armour_folder": [
        'combat_armor',
        'heavy_armor',
        'mechanized_mobility',
        'recon_armor',
    ],
    "air_techs_folder": ['air_support', 'bomber_maritime', 'fighter', 'strategic_air'],
    "naval_folder": [
        *(f"{kind}_hulls" for kind in NAVAL_HULL_CLASSES),
        "naval_support", "subsurface", "surface_fleet", "amphibious_operations",
    ],
}


def chain_edges(indices: tuple[int, ...]) -> list[tuple[int, int]]:
    return list(zip(indices, indices[1:]))


def make_graph(
    lanes: tuple[int, ...],
    edges: list[tuple[int, int]],
    synthesis_nodes: tuple[int, ...] = (),
) -> BranchGraph:
    """Build and validate a forward-only connected technology DAG."""

    count = len(lanes)
    successors: list[list[int]] = [[] for _ in range(count)]
    parents: list[list[int]] = [[] for _ in range(count)]
    for source, target in edges:
        if not (0 <= source < target < count):
            raise ValueError(
                f"Invalid technology edge {source}->{target} for {count} nodes"
            )
        if target not in successors[source]:
            successors[source].append(target)
            parents[target].append(source)

    roots = [index for index, incoming in enumerate(parents) if not incoming]
    if roots != [0]:
        raise ValueError(f"Technology graph must have root 0, got {roots}")
    reachable = {0}
    frontier = [0]
    while frontier:
        source = frontier.pop()
        for target in successors[source]:
            if target not in reachable:
                reachable.add(target)
                frontier.append(target)
    if len(reachable) != count:
        raise ValueError(
            f"Technology graph has unreachable nodes {sorted(set(range(count)) - reachable)}"
        )

    dependencies: list[tuple[int, ...]] = [() for _ in range(count)]
    for node in synthesis_nodes:
        if len(parents[node]) < 2:
            raise ValueError(f"Synthesis node {node} needs at least two parents")
        dependencies[node] = tuple(sorted(parents[node]))
    return BranchGraph(
        lanes=lanes,
        successors=tuple(tuple(sorted(targets)) for targets in successors),
        dependencies=tuple(dependencies),
    )


def linear_graph(count: int) -> BranchGraph:
    return make_graph((0,) * count, chain_edges(tuple(range(count))))


XOR_KIND_BY_BRANCH = {
    "production": "temporary",
    "industry_organization": "permanent",
    "reconstruction": "permanent",
    "public_finance": "temporary",
    "computing": "temporary",
    "power": "temporary",
    "counter_drone_warfare": "temporary",
}
XOR_INDEX_GROUPS_BY_BRANCH = {
    "production": (
        (
            6,
            7,
        ),
        (11, 13),
    ),
    "industry_organization": ((1, 2),),
    "reconstruction": (
        (
            7,
            8,
        ),
    ),
    "public_finance": (
        (
            3,
            4,
        ),
    ),
    "computing": ((5, 6),),
    "power": (
        (
            8,
            9,
        ),
    ),
    "counter_drone_warfare": (
        (
            1,
            2,
        ),
    ),
}


# Shared entries and endpoints stay centred; each distinct route has its own lane.
PROGRAMME_ROUTES = {
    "fighter": (
        ("reclaimed_jet_platforms", "standardized_airframes", "high_altitude_interceptors",
         "thrust_vectoring", "loyal_wingmen", "distributed_interceptor_swarms", "aerospace_interceptors"),
        ("reclaimed_jet_platforms", "standardized_airframes", "pulse_doppler_radar",
         "composite_wing_spars", "electronically_scanned_fighter_radar", "low_observable_inlet_geometry",
         "autonomous_dogfight_controller"),
    ),
    "air_support": (
        ("battlefield_attack_aircraft", "guided_munitions", "armored_cockpits", "vtol_assault_frames",
         "precision_glide_bomb_kits", "autonomous_strike_wings", "persistent_sensor_strike_loops", "persistent_air_support"),
        ("battlefield_attack_aircraft", "guided_munitions", "armored_cockpits", "drone_air_wings",
         "loitering_strike_drones", "cooperative_close_air_control_links"),
    ),
    "strategic_air": (
        ("rocket_test_stands", "inertial_guidance", "cruise_missiles", "strategic_rocket_architecture",
         "orbital_tracking_relics", "suborbital_skip_glide_guidance", "suborbital_strike_systems"),
        ("rocket_test_stands", "inertial_guidance", "hypersonic_glide_vehicles", "deep_strike_targeting"),
    ),
    "squad_weapons": (
        (
            "belt_fed_recovery",
            "squad_grenade_launchers",
            "portable_at_cells",
            "recoilless_squad_launchers",
            "programmable_grenade_fuzes",
            "remote_weapon_tripods",
            "autonomous_support_weapons",
            "autonomous_mortar_sections",
            "robotic_heavy_weapon_teams",
            "swarm_fireteams",
        ),
        (
            "belt_fed_recovery",
            "squad_grenade_launchers",
            "field_ew_units",
            "man_portable_sensor_masts",
            "drone_guided_support_fire",
            "networked_command_terminals",
            "cooperative_target_handoff",
            "swarm_fireteams",
        ),
    ),
    "anti_tank_infantry": (
        (
            "recovered_shaped_charge_cells",
            "disposable_launcher_standards",
            "tandem_penetrator_packages",
            "wire_guided_hunter_teams",
            "fire_and_forget_seekers",
            "top_attack_profiles",
            "cooperative_hunter_cells",
            "distributed_anti_armor_net",
        ),
        (
            "recovered_shaped_charge_cells",
            "disposable_launcher_standards",
            "tandem_penetrator_packages",
            "recoilless_overmatch_cells",
            "programmable_anti_armor_fuzes",
            "loitering_armor_hunters",
            "terminal_overmatch_packages",
            "distributed_anti_armor_net",
        ),
    ),
    "night_combat": (
        (
            "passive_intensifier_cells",
            "sealed_night_mounts",
            "thermal_observation_channels",
            "fused_low_light_sights",
            "squad_target_sharing",
            "thermal_target_libraries",
            "distributed_night_engagements",
            "nocturnal_combat_mesh",
        ),
        (
            "passive_intensifier_cells",
            "sealed_night_mounts",
            "thermal_observation_channels",
            "low_signature_illumination",
            "counter_illumination_warnings",
            "nocturnal_sensor_discipline",
            "adaptive_spectrum_concealment",
            "nocturnal_combat_mesh",
        ),
    ),
    "protection": (
        (
            "composite_protection_kits",
            "trauma_plates",
            "ceramic_trauma_inserts",
            "active_hearing_protection",
            "powered_load_bearing_harnesses",
            "exoskeleton_load_frames",
            "exosuit_joint_actuators",
            "self_sealing_combat_skins",
        ),
        (
            "composite_protection_kits",
            "sealed_combat_suits",
            "thermal_signature_liners",
            "reactive_camouflage_textiles",
            "adaptive_camouflage",
            "self_sealing_combat_skins",
        ),
        (
            "composite_protection_kits",
            "sealed_combat_suits",
            "sealed_respirator_interfaces",
            "adaptive_radiation_shielding",
            "closed_loop_combat_life_support",
            "self_sealing_combat_skins",
        ),
    ),
    "special_forces": (
        (
            "fieldcraft_manuals",
            "urban_breaching",
            "subterranean_route_reconnaissance",
            "urban_vertical_access_rigs",
            "vertical_assault_training",
            "augmented_special_forces",
        ),
        (
            "fieldcraft_manuals",
            "radiation_patrols",
            "combat_recon_drones",
            "low_observable_infiltration_suits",
            "autonomous_scout_microdrones",
            "multispectral_concealment_discipline",
            "deep_recon_cells",
            "distributed_recon_sensor_caches",
            "augmented_special_forces",
        ),
    ),
    "resources": (
        (
            "salvage_metallurgy",
            "grid_rationing",
            "refinery_reclamation",
            "spectral_ore_sorting",
            "borehole_sensor_grids",
            "geothermal_brine_extraction",
            "automated_deep_mining",
            "strategic_material_recovery",
        ),
        (
            "refinery_reclamation",
            "plasma_scrap_separation",
            "microbial_tailings_leaching",
            "synthetic_resource_cycles",
            "rare_earth_solvent_loops",
            "strategic_element_reclamation",
            "strategic_material_recovery",
        ),
        (
            "refinery_reclamation",
            "logistics_hub_networks",
            "carbon_feedstock_cracking",
            "isotope_selective_refining",
        ),
    ),
    "signals": (
        (
            "mesh_command_networks",
            "field_radio_networks",
            "encryption_rebuild",
            "frequency_hopping_field_sets",
            "adaptive_frequency_management",
            "self_healing_tactical_networks",
            "memetic_security_protocols",
        ),
        (
            "encryption_rebuild",
            "counterintelligence_filters",
            "memetic_security_protocols",
        ),
        (
            "field_radio_networks",
            "digital_radio_relays",
            "battlefield_analytics",
        ),
        (
            "field_radio_networks",
            "signal_intercept_arrays",
            "phased_array_signal_processing",
            "battlefield_sensor_fusion",
            "multistatic_radar_networks",
        ),
    ),
    "computing": (
        (
            "electromechanical_relays",
            "recovered_data_archives",
            "recovered_semiconductors",
            "scientific_computing_centres",
            "parallel_numerical_solvers",
            "photonic_research_processors",
            "quantum_material_simulation",
            "strategic_ai_coordination",
        ),
        (
            "recovered_semiconductors",
            "industrial_computing_centres",
            "industrial_process_optimizers",
            "adaptive_factory_scheduling",
            "autonomous_supply_planning",
            "strategic_ai_coordination",
        ),
        (
            "recovered_semiconductors",
            "hardened_computers",
            "error_correcting_field_computers",
            "predictive_logistics",
            "operational_ai_assistants",
            "strategic_digital_twins",
        ),
    ),
    "power": (
        (
            "local_grid_restoration",
            "substation_networks",
            "phase_synchronized_substations",
            "superconducting_power_busbars",
            "baseload_reactor_dispatch",
            "high_capacity_transmission",
            "continental_load_balancing",
        ),
        (
            "superconducting_power_busbars",
            "islandable_microgrids",
            "regional_energy_reserves",
            "continental_load_balancing",
        ),
        (
            "local_grid_restoration",
            "radiation_mapping",
            "reactor_safety_protocols",
            "load_following_microreactors",
            "microreactor_blocks",
            "emergency_core_suppression",
        ),
    ),
    "officer_training": (
        (
            "reconstituted_staff_academies",
            "assault_command_curriculum",
            "operational_planning_exercises",
            "rotational_front_commands",
            "adaptive_general_staff",
        ),
        (
            "reconstituted_staff_academies",
            "defensive_command_curriculum",
            "theater_logistics_wargames",
            "predictive_staff_colleges",
            "adaptive_general_staff",
        ),
    ),
    "artillery": (
        (
            "restored_field_artillery",
            "recoil_recovery",
            "modular_gun_carriages",
            "electrohydraulic_gun_laying",
            "assisted_projectiles",
            "uncrewed_howitzer_sections",
            "autonomous_battery_network",
        ),
        (
            "restored_field_artillery",
            "recoil_recovery",
            "modular_gun_carriages",
            "smart_fire_control",
            "counterbattery_radar_links",
            "drone_spotted_batteries",
        ),
    ),
    "anti_tank": (
        (
            "salvaged_at_guns",
            "shaped_charges",
            "tandem_warheads",
            "scrap_at_launchers",
            "coil_at_systems",
            "superconducting_coil_barrels",
            "hypervelocity_at_networks",
        ),
        (
            "salvaged_at_guns",
            "shaped_charges",
            "tandem_warheads",
            "imaging_infrared_seekers",
            "top_attack_munitions",
        ),
    ),
    "anti_air": (
        (
            "improvised_air_defense",
            "radar_laying",
            "proximity_fuzes",
            "stabilized_autocannon_mounts",
            "point_defense_aa",
            "high_energy_laser_turrets",
            "directed_energy_air_defense",
        ),
        (
            "improvised_air_defense",
            "radar_laying",
            "proximity_fuzes",
            "integrated_short_range_missile_cells",
            "networked_air_defense",
            "predictive_airspace_denial_grid",
        ),
    ),
    "recon_armor": (
        (
            "restored_armored_chassis",
            "light_suspension",
            "modular_recon_chassis",
            "sealed_electric_scout_drives",
            "signature_management_skins",
            "autonomous_recon_screen",
        ),
        (
            "restored_armored_chassis",
            "light_suspension",
            "modular_recon_chassis",
            "drone_recon_swarms",
            "multispectral_recon_suites",
            "unmanned_recon_vehicles",
            "autonomous_recon_screen",
        ),
    ),
    "mechanized_mobility": (
        (
            "armored_carrier_program",
            "protected_transport_standards",
            "sealed_dismount_compartments",
            "escort_protection_arrays",
            "infantry_combat_vehicle_program",
            "unmanned_weapon_stations",
            "networked_mechanized_cells",
        ),
        (
            "armored_carrier_program",
            "protected_transport_standards",
            "sealed_dismount_compartments",
            "infantry_combat_vehicle_program",
            "cooperative_dismount_control",
            "networked_mechanized_cells",
        ),
    ),
    "combat_armor": (
        (
            "recovered_medium_chassis",
            "remote_weapon_stations",
            "composite_armor_arrays",
            "semi_autonomous_combat_modules",
            "hard_kill_protection_arrays",
            "adaptive_suspension_control",
            "distributed_battlegroup",
        ),
        (
            "recovered_medium_chassis",
            "remote_weapon_stations",
            "electric_turret_drives",
            "semi_autonomous_combat_modules",
            "adaptive_fire_control",
            "multispectral_gunner_sights",
            "electromagnetic_main_guns",
            "distributed_battlegroup",
        ),
        (
            "recovered_medium_chassis",
            "remote_weapon_stations",
            "electric_turret_drives",
            "semi_autonomous_combat_modules",
            "limited_battle_ai",
            "distributed_battlegroup",
        ),
    ),
    "heavy_armor": (
        (
            "heavy_recovery_frames",
            "reinforced_powertrains",
            "heavy_composite_cores",
            "heavy_platform_cores",
            "active_mass_balancing_suspension",
            "autonomous_breakthrough_platforms",
            "electromagnetic_siege_mortars",
            "siege_platform_networks",
        ),
        (
            "heavy_recovery_frames",
            "reinforced_powertrains",
            "remote_repair_sections",
            "siege_platform_networks",
        ),
    ),
    "production": (
        (
            "standardized_machine_tools",
            "interchangeable_components",
            "precision_metrology_recovery",
            "numerical_machine_controls",
            "digital_tooling_libraries",
            "modular_fixture_systems",
            "predictive_maintenance",
            "flexible_robotic_tooling",
            "industrial_digital_twin_control",
            "distributed_manufacturing",
        ),
        (
            "numerical_machine_controls",
            "sensor_calibrated_machining",
            "closed_loop_quality_control",
            "predictive_maintenance",
            "machine_vision_inspection",
            "industrial_digital_twin_control",
        ),
        (
            "interchangeable_components",
            "industrial_cluster_planning",
        ),
        (
            "interchangeable_components",
            "automated_assembly",
            "autonomous_factory_cells",
        ),
    ),
    "industry_organization": (
        (
            "industrial_organization_baseline",
            "concentrated_industrial_zones",
            "integrated_factory_campuses",
            "megafactory_power_buses",
            "centralized_process_dispatch",
            "continuous_casting_lines",
            "strategic_production_complexes",
        ),
        (
            "industrial_organization_baseline",
            "distributed_workshop_networks",
            "regional_workshop_standards",
            "regional_spare_capacity",
            "interregional_backup_contracts",
            "mobile_fabrication_convoys",
            "resilient_production_meshes",
        ),
    ),
    "reconstruction": (
        (
            "salvage_standards",
            "ruin_workshops",
            "reconstruction_bureaus",
            "drone_construction_cartography",
            "standardized_utility_corridors",
            "modular_rebuilding",
            "serviced_industrial_sites",
            "prefabricated_districts",
            "multilevel_industrial_districts",
            "integrated_land_development",
            "integrated_city_complexes",
        ),
        (
            "reconstruction_bureaus",
            "public_repair_corps",
            "civil_defense_networks",
        ),
        (
            "modular_rebuilding",
            "automated_civil_works",
            "civil_defense_networks",
        ),
        (
            "modular_rebuilding",
            "compact_industrial_zoning",
            "vertical_factory_districts",
        ),
        (
            "modular_rebuilding",
            "rapid_reconstruction_standards",
            "resilient_utility_construction",
        ),
    ),
    "synthetic_rubber": (
        (
            "synthetic_rubber_plants",
            "rubber_production_lines",
            "integrated_rubber_complexes",
            "precision_polymer_blending",
        ),
        (
            "synthetic_rubber_plants",
            "emulsion_polymerization",
            "selective_polymer_catalysts",
            "closed_cycle_polymerization",
            "solvent_recovery_columns",
        ),
    ),
    "synthetic_oil": (
        (
            "synthetic_oil_synthesis",
            "catalytic_oil_synthesis",
            "closed_cycle_oil_synthesis",
            "precision_fuel_fractionation",
        ),
        (
            "synthetic_oil_synthesis",
            "synthetic_feedstock_purification",
            "synthetic_fuel_hydrocracking",
            "synthetic_fuel_process_control",
            "synthetic_heat_recovery",
        ),
    ),
    "public_finance": (
        (
            "treasury_accounting",
            "civilian_industrial_accounting",
            "industrial_investment_planning",
            "regional_development_contracts",
            "production_cost_accounting",
        ),
        (
            "civilian_industrial_accounting",
            "industrial_service_budgeting",
            "lifecycle_cost_audits",
            "production_cost_accounting",
        ),
        (
            "treasury_accounting",
            "public_procurement_standards",
            "administrative_digitization",
            "automated_treasury_audit",
        ),
    ),
    "advanced_materials": (
        (
            "precision_material_standards",
            "rare_components_industry",
            "precision_component_fabrication",
            "precision_ceramic_substrates",
            "advanced_material_recycling",
        ),
        (
            "precision_material_standards",
            "rare_alloy_metallurgy",
            "vacuum_alloy_refining",
            "powder_alloy_sintering",
            "advanced_material_recycling",
        ),
    ),
    "counter_drone_warfare": (
        (
            "spectrum_threat_libraries",
            "offensive_jamming_cells",
            "cognitive_emitter_spoofing",
            "adaptive_spectrum_dominance",
            "distributed_spectrum_monitoring",
        ),
        (
            "spectrum_threat_libraries",
            "passive_drone_detection_meshes",
            "hardened_command_waveforms",
            "adaptive_spectrum_dominance",
            "distributed_spectrum_monitoring",
        ),
    ),
    "semiconductors": (
        (
            "semiconductor_clean_rooms",
            "silicon_feedstock_purification",
            "precision_photolithography",
            "high_density_integrated_circuits",
            "optical_chip_interconnects",
            "three_dimensional_chip_stacking",
        ),
        (
            "silicon_feedstock_purification",
            "fault_tolerant_chip_packaging",
            "automated_wafer_inspection",
        ),
    ),
}

PROGRAMME_SYNTHESIS = {
    "squad_weapons": ('swarm_fireteams',),
    "anti_tank_infantry": ('distributed_anti_armor_net',),
    "night_combat": ('nocturnal_combat_mesh',),
    "signals": ('memetic_security_protocols',),
    "recon_armor": ('autonomous_recon_screen',),
    "mechanized_mobility": ('networked_mechanized_cells',),
    "combat_armor": ('distributed_battlegroup',),
    "heavy_armor": ("siege_platform_networks",),
    "advanced_materials": (
        "advanced_material_recycling",
    ),
}


# Lanes belong to capabilities, not to the number of path segments. A side
# project may end without forcing the next generation through its research.
PROGRAMME_LANES = {
    "production": (1, 1, 2, 1, 4, 1, 0, 2, 0, 2, 1, 0, 4, 2, 1, 1),
    "reconstruction": (2, 2, 2, 2, 2, 2, 2, 3, 4, 2, 0, 2, 3, 4, 1, 2, 0, 2),
    "resources": (2, 2, 2, 0, 4, 0, 2, 2, 2, 0, 2, 0, 4, 4, 2, 1),
    "synthetic_rubber": (1, 2, 0, 2, 0, 2, 2, 0),
    "synthetic_oil": (1, 2, 0, 2, 0, 2, 2, 0),
    "public_finance": (1, 4, 1, 0, 2, 4, 0, 2, 1, 4),
    "signals": (1, 1, 0, 0, 4, 2, 4, 2, 0, 2, 4, 4, 0, 1),
    "computing": (1, 1, 1, 4, 4, 0, 2, 4, 0, 2, 4, 0, 4, 2, 0, 2, 1),
    "power": (1, 1, 4, 1, 1, 4, 4, 4, 0, 2, 0, 2, 1, 4),
    "semiconductors": (1, 1, 0, 2, 0, 0, 2, 0),
}


def programme_graph(branch: Branch) -> BranchGraph:
    """Use explicit capability paths, never distribute unrelated nodes by index."""
    indices = {tech.key: index for index, tech in enumerate(branch.techs)}
    routes = PROGRAMME_ROUTES[branch.key]
    membership = {key: [] for key in indices}
    edges: list[tuple[int, int]] = []
    lane_ids = (0, 2) if len(routes) == 2 else tuple(range(len(routes)))
    for lane, route in zip(lane_ids, routes, strict=True):
        for key in route:
            if key not in indices:
                raise ValueError(f"{branch.key}: unknown programme technology {key}")
            membership[key].append(lane)
        edges.extend(chain_edges(tuple(indices[key] for key in route)))
    missing = [key for key, lanes in membership.items() if not lanes]
    if missing:
        raise ValueError(
            f"{branch.key}: technologies outside programme routes: {missing}"
        )
    lanes = tuple(
        values[0] if len(values) == 1 else 1 for values in membership.values()
    )
    lanes = PROGRAMME_LANES.get(branch.key, lanes)
    synthesis = tuple(indices[key] for key in PROGRAMME_SYNTHESIS.get(branch.key, ()))
    return make_graph(lanes, edges, synthesis)


def naval_programme_graph(branch: Branch) -> BranchGraph:
    """Hull progression and optional refits share a root, not a final merge."""
    kind = branch.key.removesuffix("_hulls")
    indices = {tech.key: index for index, tech in enumerate(branch.techs)}
    hulls = tuple(indices[f"{kind}_hull_{year}"] for year in NAVAL_HULL_YEARS)
    lanes = [1] * len(branch.techs)
    edges = chain_edges(hulls)
    mandatory = []
    for lane, programme in zip((0, 2, 3), NAVAL_SIDE_PROGRAMMES[kind]):
        members = tuple(indices[key] for key in programme)
        edges.extend(chain_edges(members))
        for index in members:
            lanes[index] = lane
        first = members[0]
        parent = hulls[0]
        if kind == "carrier" and lane == 3:
            parent = max(index for index in hulls if branch.years[index] <= branch.years[first])
        edges.append((parent, first))
        if kind == "carrier" and lane in {0, 2}:
            # A later air group requires its preceding aircraft and the deck
            # generation it operates from; neither prerequisite substitutes for the other.
            for hull, aircraft in zip(hulls[1:], members[1:], strict=True):
                edges.append((hull, aircraft))
                mandatory.append(aircraft)
    return make_graph(tuple(lanes), edges, tuple(mandatory))


def graph_for_branch(branch: Branch) -> BranchGraph:
    count = len(branch.techs)
    if branch.key == "reserve_training":
        graph = make_graph((1, 0, 2, 0, 2, 0, 2), [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6)])
    elif branch.key in NAVAL_HULL_BRANCH_KEYS:
        graph = naval_programme_graph(branch)
    elif branch.key in PROGRAMME_ROUTES:
        graph = programme_graph(branch)
    elif branch.key == "production":
        # Either tooling specialization opens the shared maintenance programme.
        graph = make_graph(
            (1, 1, 1, 1, 1, 0, 2, 1, 1, 1),
            chain_edges((0, 1, 2, 3, 4))
            + [(4, 5), (4, 6), (5, 7), (6, 7), (7, 8), (8, 9)],
        )
    elif branch.key == "industry_organization":
        graph = make_graph(
            (1, 0, 2, 0, 2, 0, 2, 0, 2),
            [(0, 1), (0, 2)] + chain_edges((1, 3, 5, 7)) + chain_edges((2, 4, 6, 8)),
        )
    elif branch.key == "advanced_materials":
        graph = make_graph(
            (1, 0, 2, 0, 2, 1), [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5)], (5,)
        )
    elif branch.key == "bomber_maritime":
        graph = make_graph(
            (1, 0, 2, 0, 2, 0, 2, 1),
            [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6), (5, 7), (6, 7)],
        )
    else:
        graph = linear_graph(count)
    if len(graph.lanes) != count:
        raise ValueError(f"{branch.key}: graph and research rows differ in length")
    for start, targets in enumerate(graph.successors):
        for end in targets:
            if branch.years[start] > branch.years[end]:
                raise ValueError(f"{branch.key}: non-chronological edge {start}->{end}")
    return graph


BRANCH_GRAPHS = {branch.key: graph_for_branch(branch) for branch in BRANCHES}


CURRENT_TECH_IDS = {tech.id for branch in BRANCHES for tech in branch.techs}
CURRENT_BRANCH_TECHS = {
    branch.key: tuple(zip(branch.techs, branch.years, strict=True))
    for branch in BRANCHES
}
LEGACY_MIGRATION_TARGET_BRANCH = {
    "finance": "computing",
    "administration": "computing",
    "civil_resilience": "reconstruction",
}


def closest_compact_technology(branch_key: str, year: int) -> str:
    target_branch = LEGACY_MIGRATION_TARGET_BRANCH.get(branch_key, branch_key)
    candidates = CURRENT_BRANCH_TECHS.get(target_branch)
    if target_branch == "small_arms":
        candidates += CURRENT_BRANCH_TECHS["assault_rifles"]
    if not candidates:
        raise ValueError(f"No compact migration target for legacy branch {branch_key}")
    tech, _ = min(
        candidates,
        key=lambda pair: (
            abs(pair[1] - year),
            pair[1] > year,
            pair[1],
            pair[0].id,
        ),
    )
    return tech.id


TECHNOLOGY_ID_MIGRATIONS = {}
for legacy_branch in LEGACY_BRANCHES:
    for legacy_tech_spec, legacy_year in zip(
        legacy_branch.techs, legacy_branch.years, strict=True
    ):
        if legacy_tech_spec.id in CURRENT_TECH_IDS:
            status = "preserved"
            replacement = legacy_tech_spec.id
        else:
            status = "replaced"
            replacement = closest_compact_technology(legacy_branch.key, legacy_year)
        TECHNOLOGY_ID_MIGRATIONS[legacy_tech_spec.id] = {
            "status": status,
            "replacement": replacement,
        }


def xor_siblings(branch: Branch, index: int) -> tuple[str, ...]:
    for group in XOR_INDEX_GROUPS_BY_BRANCH.get(branch.key, ()):
        if index in group:
            return tuple(
                branch.techs[sibling].id for sibling in group if sibling != index
            )
    return ()


FORBIDDEN_IDS = {
    tech.id
    for branch in BRANCHES
    if branch.profile.startswith("forbidden_")
    for tech in branch.techs
}


ENABLE_EQUIPMENT = {
    "ADISCORD_tech_pulse_doppler_radar": ("ADISCORD_interceptor_airframe_2158",),
    "ADISCORD_tech_autonomous_dogfight_controller": ("ADISCORD_interceptor_airframe_2173",),
    "ADISCORD_tech_cruise_missiles": ("ADISCORD_strike_airframe_2158",),
    "ADISCORD_tech_restored_airlift_planning": ("ADISCORD_transport_airframe_2162",),
    "ADISCORD_tech_vertical_envelopment_control": ("ADISCORD_transport_airframe_2169",),
    "ADISCORD_tech_precision_aerial_resupply": ("ADISCORD_transport_airframe_2175",),
    "ADISCORD_tech_kefreyt_shield_special_forces": ("ADISCORD_power_shield_equipment_1",),
    "ADISCORD_tech_compact_shield_generators": ("ADISCORD_power_shield_equipment_2",),
    "ADISCORD_tech_adaptive_power_shields": ("ADISCORD_power_shield_equipment_3",),
    "ADISCORD_tech_postwar_weapon_standardization": ("infantry_equipment_0",),
    "ADISCORD_tech_refurbished_receivers": ("ADISCORD_infantry_equipment_2156",),
    "ADISCORD_tech_sealed_receiver_assemblies": ("ADISCORD_infantry_equipment_2163",),
    "ADISCORD_tech_smart_recoil_compensators": ("ADISCORD_infantry_equipment_2168",),
    "ADISCORD_tech_smart_optics": ("ADISCORD_infantry_equipment_2170",),
    "ADISCORD_tech_modular_rifle_kits": ("ADISCORD_infantry_equipment_2178",),
    "ADISCORD_tech_programmable_ammunition": ("ADISCORD_infantry_equipment_2183",),
    "ADISCORD_tech_coil_assisted_service_rifles": ("ADISCORD_infantry_equipment_2193",),
    "ADISCORD_tech_networked_service_rifles": ("ADISCORD_infantry_equipment_2200",),
    "ADISCORD_tech_belt_fed_recovery": ("ADISCORD_squad_weapons_equipment_0",),
    "ADISCORD_tech_squad_grenade_launchers": ("ADISCORD_squad_weapons_equipment_2156",),
    "ADISCORD_tech_portable_at_cells": ("ADISCORD_squad_weapons_equipment_2163",),
    "ADISCORD_tech_recoilless_squad_launchers": (
        "ADISCORD_squad_weapons_equipment_2168",
    ),
    "ADISCORD_tech_field_ew_units": ("ADISCORD_squad_weapons_equipment_2170",),
    "ADISCORD_tech_remote_weapon_tripods": ("ADISCORD_squad_weapons_equipment_2178",),
    "ADISCORD_tech_autonomous_support_weapons": (
        "ADISCORD_squad_weapons_equipment_2183",
    ),
    "ADISCORD_tech_robotic_heavy_weapon_teams": (
        "ADISCORD_squad_weapons_equipment_2193",
    ),
    "ADISCORD_tech_swarm_fireteams": ("ADISCORD_squad_weapons_equipment_2200",),
    "ADISCORD_tech_field_workshop_tools": ("support_equipment_1",),
    "ADISCORD_tech_restored_truck_fleets": ("motorized_equipment_1",),
    "ADISCORD_tech_drone_delivered_repair_spares": ("ADISCORD_support_equipment_2170",),
    "ADISCORD_tech_predictive_parts_prepositioning": (
        "ADISCORD_support_equipment_2183",
    ),
    "ADISCORD_tech_self_sustaining_support": ("ADISCORD_support_equipment_2200",),
    "ADISCORD_tech_restored_rail_stock": ("train_equipment_1",),
    "ADISCORD_tech_armored_rail_convoys": ("armored_train_equipment_1",),
    "ADISCORD_tech_hardened_logistics_nodes": (
        "ADISCORD_hardened_train_equipment_2183",
    ),
    "ADISCORD_tech_autonomous_rail_dispatch": (
        "ADISCORD_autonomous_train_equipment_2183",
    ),
    "ADISCORD_tech_autonomous_yard_shunting": (
        "ADISCORD_autonomous_train_equipment_2183",
    ),
    "ADISCORD_tech_over_the_horizon_fire_control": (
        "ADISCORD_railway_gun_equipment_2200",
    ),
    "ADISCORD_tech_railway_gun_reactivation": ("railway_gun_equipment_1",),
    "ADISCORD_tech_restored_field_artillery": ("artillery_equipment_1",),
    "ADISCORD_tech_electrohydraulic_gun_laying": ("ADISCORD_artillery_equipment_2160",),
    "ADISCORD_tech_assisted_projectiles": ("ADISCORD_artillery_equipment_2170",),
    "ADISCORD_tech_uncrewed_howitzer_sections": ("ADISCORD_artillery_equipment_2183",),
    "ADISCORD_tech_salvaged_at_guns": ("ADISCORD_anti_tank_equipment_2163",),
    "ADISCORD_tech_scrap_at_launchers": ("ADISCORD_anti_tank_equipment_2161",),
    "ADISCORD_tech_top_attack_munitions": ("ADISCORD_anti_tank_equipment_2166",),
    "ADISCORD_tech_superconducting_coil_barrels": ("ADISCORD_anti_tank_equipment_2183",),
    "ADISCORD_tech_improvised_air_defense": ("ADISCORD_anti_air_equipment_2163",),
    "ADISCORD_tech_stabilized_autocannon_mounts": ("ADISCORD_anti_air_equipment_2160",),
    "ADISCORD_tech_integrated_short_range_missile_cells": ("ADISCORD_anti_air_equipment_2165",),
    "ADISCORD_tech_high_energy_laser_turrets": ("ADISCORD_anti_air_equipment_2183",),
    "ADISCORD_tech_restored_armored_chassis": ("ADISCORD_light_combat_platform_2163",),
    "ADISCORD_tech_recovered_medium_chassis": ("ADISCORD_combat_platform_2150",),
    "ADISCORD_tech_heavy_composite_cores": ("ADISCORD_heavy_combat_platform_2158",),
    "ADISCORD_tech_unmanned_recon_vehicles": ("ADISCORD_recon_drone_carrier_2170",),
    "ADISCORD_tech_signature_management_skins": ("ADISCORD_recon_drone_carrier_2170",),
    "ADISCORD_tech_armored_carrier_program": ("ADISCORD_armored_carrier_2163",),
    "ADISCORD_tech_infantry_combat_vehicle_program": ("ADISCORD_ifv_2170",),
    "ADISCORD_tech_networked_mechanized_cells": ("ADISCORD_networked_ifv_2183",),
    "ADISCORD_tech_semi_autonomous_combat_modules": ("ADISCORD_combat_platform_2170",),
    "ADISCORD_tech_remote_repair_sections": ("ADISCORD_repair_platform_2183",),
    "ADISCORD_tech_limited_battle_ai": ("ADISCORD_combat_platform_2183",),
    "ADISCORD_tech_adaptive_suspension_control": ("ADISCORD_combat_platform_2183",),
    "ADISCORD_tech_distributed_battlegroup": ("ADISCORD_combat_platform_2200",),
    "ADISCORD_tech_heavy_platform_cores": ("ADISCORD_heavy_combat_platform_2183",),
    "ADISCORD_tech_active_mass_balancing_suspension": (
        "ADISCORD_heavy_combat_platform_2183",
    ),
    "ADISCORD_tech_siege_platform_networks": ("ADISCORD_heavy_combat_platform_2200",),
    "ADISCORD_tech_reclaimed_jet_platforms": ("ADISCORD_fighter_airframe_2163",),
    "ADISCORD_tech_low_observable_inlet_geometry": (
        "ADISCORD_interceptor_airframe_2183",
    ),
    "ADISCORD_tech_loyal_wingmen": ("ADISCORD_interceptor_airframe_2183",),
    "ADISCORD_tech_battlefield_attack_aircraft": ("ADISCORD_cas_airframe_2170",),
    "ADISCORD_tech_vtol_assault_frames": ("ADISCORD_vtol_airframe_2170",),
    "ADISCORD_tech_drone_air_wings": ("ADISCORD_drone_airframe_2183",),
    "ADISCORD_tech_orbital_tracking_relics": ("ADISCORD_rocket_strike_platform_2183",),
    "ADISCORD_tech_low_observable_cruise_missile_skins": (
        "ADISCORD_rocket_strike_platform_2183",
    ),
    "ADISCORD_tech_suborbital_skip_glide_guidance": (
        "ADISCORD_deep_strike_airframe_2200",
    ),
    "ADISCORD_tech_autonomous_strategic_strike_planning": (
        "ADISCORD_deep_strike_airframe_2200",
    ),
    "ADISCORD_tech_suborbital_strike_systems": (
        "ADISCORD_orbital_tracking_platform_2200",
    ),
}


# Production milestones identify the equipment families used by scripted armies.
NAVAL_AIR_UNLOCKS = {
    "high_altitude_interceptors": ("ADISCORD_fighter_airframe_2161", "fighter2"),
    "thrust_vectoring": ("ADISCORD_fighter_airframe_2166", "jet_fighter1"),
    "loyal_wingmen": ("ADISCORD_fighter_airframe_2170", "jet_fighter2"),
    "distributed_interceptor_swarms": (
        "ADISCORD_fighter_airframe_2175",
        "jet_fighter2",
    ),
    "precision_glide_bomb_kits": ("ADISCORD_attack_airframe_2163", "CAS2"),
    "autonomous_strike_wings": ("ADISCORD_attack_airframe_2170", "CAS3"),
    "persistent_sensor_strike_loops": ("ADISCORD_attack_airframe_2175", "CAS3"),
    "maritime_patrol_aircraft": ("ADISCORD_naval_aircraft_2164", "naval_bomber2"),
    "pressurized_bombers": ("ADISCORD_bomber_2164", "tactical_bomber2"),
    "long_range_maritime_aircraft": ("ADISCORD_naval_aircraft_2172", "naval_bomber3"),
    "jet_strike_bombers": ("ADISCORD_bomber_2172", "jet_tactical_bomber1"),
}
ENABLE_EQUIPMENT.update(
    {
        f"ADISCORD_tech_{key}": (equipment,)
        for key, (equipment, _) in NAVAL_AIR_UNLOCKS.items()
    }
)
for kind, (_, _, _, _, equipment, _) in NAVAL_HULL_CLASSES.items():
    for year in NAVAL_HULL_YEARS:
        unlocks = (f"ADISCORD_{equipment}_{year}",)
        ENABLE_EQUIPMENT[f"ADISCORD_tech_{kind}_hull_{year}"] = unlocks

ENABLE_EQUIPMENT.update({
    f"ADISCORD_tech_{key}": (equipment,)
    for key, (equipment, _) in NAVAL_AIR_RESEARCH.items()
})

ENABLE_EQUIPMENT["ADISCORD_tech_twin_engine_aircraft"] = (
    "ADISCORD_bomber_2160",
    "ADISCORD_naval_aircraft_2160",
)
ENABLE_EQUIPMENT = {
    key: value for key, value in ENABLE_EQUIPMENT.items() if key in CURRENT_TECH_IDS
}


# Cross-row integration is intentionally dependency-only: drawing paths
# between separate grid boxes is fragile in HOI4, while dependencies provide
# the required AND gate in the technology tooltip and research logic.
EXTRA_TECH_DEPENDENCIES = {
    "ADISCORD_tech_sealed_receiver_assemblies": ("ADISCORD_tech_primer_consistency",),
    "ADISCORD_tech_heavy_cruiser_hull_2163": ("ADISCORD_tech_light_cruiser_hull_2155",),
    "ADISCORD_tech_battleship_hull_2163": ("ADISCORD_tech_heavy_cruiser_hull_2163",),
    "ADISCORD_tech_carrier_hull_2163": ("ADISCORD_tech_heavy_cruiser_hull_2155",),
    "ADISCORD_tech_amphibious_formation_organization": ("ADISCORD_tech_restored_dockyards",),
    "ADISCORD_tech_synthetic_oil_synthesis": ("ADISCORD_tech_synthetic_rubber_plants",),
    "ADISCORD_tech_casualty_evacuation": ('ADISCORD_tech_field_workshop_tools',),
    "ADISCORD_tech_reserve_cadre_training": ('ADISCORD_tech_field_workshop_tools',),
    "ADISCORD_tech_foot_recon_sections": ('ADISCORD_tech_field_workshop_tools',),
    "ADISCORD_tech_garrison_police_sections": ('ADISCORD_tech_field_workshop_tools',),
    "ADISCORD_tech_field_signal_sections": (
        'ADISCORD_tech_field_workshop_tools', 'ADISCORD_tech_field_radio_networks',
    ),
    "ADISCORD_tech_battle_damage_survey_teams": (
        'ADISCORD_tech_standardized_field_tool_chests',
    ),
    "ADISCORD_tech_spectrum_threat_libraries": (
        'ADISCORD_tech_frequency_hopping_field_sets',
    ),
    "ADISCORD_tech_restored_airlift_planning": ('ADISCORD_tech_composite_wing_spars',),
    "ADISCORD_tech_shallow_water_navigation_tables": (
        'ADISCORD_tech_modular_escort_combat_systems',
    ),
    "ADISCORD_tech_teleoperated_scout_carts": (
        'ADISCORD_tech_sealed_electric_scout_drives',
        'ADISCORD_tech_hardened_computers',
    ),
    "ADISCORD_tech_armored_carrier_program": (
        'ADISCORD_tech_sealed_electric_scout_drives',
        'ADISCORD_tech_remote_weapon_stations',
    ),
    "ADISCORD_tech_reconstituted_staff_academies": (
        'ADISCORD_tech_hardened_computers',
    ),
    "ADISCORD_tech_railway_gun_reactivation": ('ADISCORD_tech_armored_rail_convoys',),
    "ADISCORD_tech_remote_weapon_tripods": ('ADISCORD_tech_modular_rifle_kits',),
    "ADISCORD_tech_autonomous_support_weapons": (
        'ADISCORD_tech_programmable_ammunition',
    ),
    "ADISCORD_tech_swarm_fireteams": ('ADISCORD_tech_networked_service_rifles',),
    "ADISCORD_tech_autonomous_factory_cells": ('ADISCORD_tech_predictive_logistics',),
    "ADISCORD_tech_distributed_manufacturing": (
        'ADISCORD_tech_strategic_digital_twins',
    ),
    "ADISCORD_tech_high_energy_laser_turrets": (
        'ADISCORD_tech_superconducting_power_busbars',
    ),
    "ADISCORD_tech_autonomous_breakthrough_platforms": (
        'ADISCORD_tech_operational_ai_assistants',
    ),
    "ADISCORD_tech_autonomous_strike_wings": (
        'ADISCORD_tech_operational_ai_assistants',
    ),
    "ADISCORD_tech_autonomous_submarines": ('ADISCORD_tech_operational_ai_assistants',),
}


BRANCH_BY_KEY = {branch.key: branch for branch in BRANCHES}
# Connected programmes share a native grid and a calendar. Only paths within
# that grid are drawn; cross-folder integrations remain explicit dependencies.
CIVIL_TREE_ATTACHMENTS = {
    "industry_organization": ("production", "standardized_machine_tools"),
    "synthetic_rubber": ("resources", "refinery_reclamation"),
    "synthetic_oil": ("synthetic_rubber", "synthetic_rubber_plants"),
    "semiconductors": ("computing", "recovered_semiconductors"),
    "counter_drone_warfare": ("signals", "frequency_hopping_field_sets"),
}


def vertical_tree_key(branch: Branch) -> str:
    key = branch.key
    while key in CIVIL_TREE_ATTACHMENTS:
        key = CIVIL_TREE_ATTACHMENTS[key][0]
    return key


def vertical_tree_branches(branch: Branch) -> tuple[Branch, ...]:
    owner = vertical_tree_key(branch)
    return tuple(b for b in BRANCHES if vertical_tree_key(b) == owner)


def vertical_branch_span(branch: Branch) -> int:
    lanes = BRANCH_GRAPHS[branch.key].lanes
    multiplier = (
        CIVIL_LANE_SLOT_MULTIPLIER
        if branch.file in CIVIL_TECHNOLOGY_FILES
        else LANE_SLOT_MULTIPLIER
    )
    return (max(lanes) - min(lanes) + 1) * multiplier


def vertical_tree_span(branch: Branch) -> int:
    members = vertical_tree_branches(branch)
    gaps = (len(members) - 1) * VERTICAL_PROGRAMME_GAP_SLOTS
    return sum(vertical_branch_span(b) for b in members) + gaps


def vertical_branch_offset(branch: Branch) -> int:
    offset = 0
    for member in vertical_tree_branches(branch):
        if member.key == branch.key:
            return offset
        offset += vertical_branch_span(member) + VERTICAL_PROGRAMME_GAP_SLOTS
    raise ValueError(f"Missing vertical programme {branch.key}")


TECH_POSITION_BY_ID = {
    tech.id: (branch, index)
    for branch in BRANCHES
    for index, tech in enumerate(branch.techs)
}


def branch_technology_ids_through(branch_key: str, year: int) -> tuple[str, ...]:
    branch = BRANCH_BY_KEY[branch_key]
    return tuple(
        tech.id
        for tech, tech_year in zip(branch.techs, branch.years, strict=True)
        if tech_year <= year
    )


def technology_prerequisite_closure(seed_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Resolve every generated parent and dependency for a starting package."""

    resolved: set[str] = set()
    pending = list(seed_ids)
    while pending:
        tech_id = pending.pop()
        if tech_id in resolved:
            continue
        if tech_id not in TECH_POSITION_BY_ID:
            raise ValueError(f"Unknown starting technology {tech_id}")
        resolved.add(tech_id)
        branch, index = TECH_POSITION_BY_ID[tech_id]
        for parent_index, successors in enumerate(BRANCH_GRAPHS[branch.key].successors):
            if index in successors:
                pending.append(branch.techs[parent_index].id)
        if index == 0 and branch.key in CIVIL_TREE_ATTACHMENTS:
            pending.append(f"ADISCORD_tech_{CIVIL_TREE_ATTACHMENTS[branch.key][1]}")
        pending.extend(EXTRA_TECH_DEPENDENCIES.get(tech_id, ()))
    return tuple(sorted(resolved))


COMMON_STARTING_ROOTS = tuple(
    sorted(
        tech.id
        for branch_keys in MAIN_BRANCH_KEYS_BY_FOLDER.values()
        for branch_key in branch_keys
        if SPECIAL_TECHNOLOGY_FOLDER not in BRANCH_BY_KEY[branch_key].folders
        # These programmes begin with research during the campaign. Making
        # their UI headings prominent must not grant their roots at startup.
        if branch_key not in NAVAL_HULL_BRANCH_KEYS and branch_key not in {
            "officer_training",
            "reserve_training",
            "field_reconnaissance",
            "field_signals",
            "garrison_security",
            "bomber_maritime",
            "combat_medicine",
            "synthetic_rubber",
            "synthetic_oil",
            "semiconductors",
            "power_shields",
            "assault_infantry",
            "assault_rifles",
            "amphibious_operations",
        }
        for tech in BRANCH_BY_KEY[branch_key].techs[:4 if branch_key == "small_arms" else 1]
    )
)

STARTING_TECH_PROFILE_SEEDS = {
    "common": COMMON_STARTING_ROOTS,
    "industrial": tuple(
        tech_id
        for branch_key in (
            "production",
            "reconstruction",
            "resources",
            "advanced_materials",
        )
        for tech_id in branch_technology_ids_through(branch_key, 2158)
    ),
    "energy": branch_technology_ids_through("power", 2160),
    "advanced_materials": branch_technology_ids_through("advanced_materials", 2158),
    "institutional": (
        *branch_technology_ids_through("signals", 2158),
        *branch_technology_ids_through("computing", 2158),
    ),
    "land": tuple(
        tech_id
        for branch_key in (
            "small_arms",
            "squad_weapons",
            "protection",
            "field_support",
            "logistics",
            "rail",
            "artillery",
            "anti_tank",
            "anti_air",
        )
        for tech_id in branch_technology_ids_through(branch_key, 2158)
    ),
    # Recovered armored doctrine is deliberately not part of the generic land
    # profile.  Only the major industrial powers begin with enough preserved
    # drivetrain, turret and carrier knowledge to field a modern armored core.
    "armored_core": (
        "ADISCORD_tech_armored_carrier_program",
        "ADISCORD_tech_semi_autonomous_combat_modules",
    ),
    "recon_platform": ("ADISCORD_tech_drone_recon_swarms",),
    "field_air_defense": ("ADISCORD_tech_point_defense_aa",),
    "air": tuple(
        tech_id
        for branch_key in ("fighter", "air_support", "strategic_air")
        for tech_id in branch_technology_ids_through(branch_key, 2158)
    ),
    "naval_taskforce": ("ADISCORD_tech_light_cruiser_hull_2155",),
    "naval": tuple(
        tech_id
        for branch_key in (
            "naval_support", "surface_fleet", "subsurface",
            "destroyer_hulls", "heavy_cruiser_hulls", "submarine_hulls",
        )
        for tech_id in branch_technology_ids_through(branch_key, 2158)
    ),
    "fragment_low_tech": (
        "ADISCORD_tech_ruin_workshops",
        "ADISCORD_tech_refurbished_receivers",
        "ADISCORD_tech_restored_truck_fleets",
    ),
    "hazard_infantry": (
        "ADISCORD_tech_sealed_combat_suits",
        "ADISCORD_tech_radiation_patrols",
    ),
    # The late bookmark receives a bounded recovered-generation package, not
    # every technology whose nominal date is earlier than 2183.
    "late_2183": (
        "ADISCORD_tech_precision_metrology_recovery",
        "ADISCORD_tech_drone_construction_cartography",
        "ADISCORD_tech_spectral_ore_sorting",
        "ADISCORD_tech_frequency_hopping_field_sets",
        "ADISCORD_tech_hardened_computers",
        "ADISCORD_tech_phase_synchronized_substations",
        "ADISCORD_tech_smart_recoil_compensators",
        "ADISCORD_tech_standardized_field_tool_chests",
        "ADISCORD_tech_electrohydraulic_gun_laying",
        "ADISCORD_tech_electric_turret_drives",
        "ADISCORD_tech_composite_wing_spars",
        "ADISCORD_tech_modular_escort_combat_systems",
    ),
}

STARTING_TECH_PROFILE_SEEDS["land"] += (
    "ADISCORD_tech_casualty_evacuation",
    "ADISCORD_tech_urban_breaching",
)

STARTING_TECH_PROFILES = {
    profile: technology_prerequisite_closure(seeds)
    for profile, seeds in STARTING_TECH_PROFILE_SEEDS.items()
}

# Manual, lore-aware mapping for every tag owning at least one state on
# 2160.1.1.  Empty tuples are intentional common-only assignments.
STARTING_COUNTRY_TECH_PROFILES = {
    "YOR": ("fragment_low_tech",),
    "RIV": ("fragment_low_tech", "advanced_materials"),
    "EYR": ("fragment_low_tech",),
    "EGC": ("fragment_low_tech",),
    "AIN": ("fragment_low_tech", "institutional"),
    "APH": ("fragment_low_tech",),
    "ARS": ("fragment_low_tech",),
    "AUR": ("fragment_low_tech",),
    "AZH": ("fragment_low_tech", "naval"),
    "BBV": ("fragment_low_tech",),
    "BCM": ("fragment_low_tech",),
    "BGT": ("fragment_low_tech",),
    "BHG": ("fragment_low_tech",),
    "BJK": ("fragment_low_tech",),
    "BLD": ("fragment_low_tech",),
    "BOR": ("institutional", "land"),
    "BRN": ("fragment_low_tech",),
    "BTL": ("fragment_low_tech", "land"),
    "CIN": ("fragment_low_tech",),
    "COF": ("fragment_low_tech", "field_air_defense", "air"),
    "DAN": ("fragment_low_tech", "land"),
    "DOL": ("fragment_low_tech",),
    "DRV": ("fragment_low_tech",),
    "VEL": ("fragment_low_tech",),
    "EFL": ("fragment_low_tech", "land", "naval"),
    "ELN": ("institutional",),
    "EXZ": (),
    "RSV": (),
    "FRS": ("fragment_low_tech",),
    "GLP": ("fragment_low_tech", "naval"),
    "HON": ("institutional", "land"),
    "IIA": ("fragment_low_tech",),
    "IVN": ("institutional", "land", "air", "armored_core"),
    "KDR": ("fragment_low_tech",),
    "KDL": ("fragment_low_tech",),
    "KHV": ("fragment_low_tech",),
    "KRL": ("fragment_low_tech", "land"),
    "KYZ": ("fragment_low_tech", "energy"),
    "LYS": ("fragment_low_tech", "institutional"),
    "MON": ("industrial", "institutional", "land", "air"),
    "MZR": ("fragment_low_tech", "energy"),
    "NAM": ("fragment_low_tech", "naval"),
    "NOD": (
        "industrial",
        "energy",
        "institutional",
        "land",
        "air",
        "naval",
        "naval_taskforce",
        "armored_core",
    ),
    "NVR": ("fragment_low_tech", "land"),
    "OSF": ("fragment_low_tech",),
    "PIV": ("fragment_low_tech", "land"),
    "PWR": (),
    "RHM": ("fragment_low_tech", "energy"),
    "RIN": ("fragment_low_tech", "land"),
    "ROM": ("fragment_low_tech",),
    "RLY": ("fragment_low_tech",),
    "RUS": ("fragment_low_tech",),
    "SRV": ("fragment_low_tech",),
    "SDR": ("fragment_low_tech",),
    "SHL": ("fragment_low_tech", "industrial"),
    "SKN": ("fragment_low_tech", "land"),
    "SLI": ("fragment_low_tech",),
    "SOL": ("fragment_low_tech",),
    "STP": (
        "industrial",
        "energy",
        "institutional",
        "land",
        "air",
        "naval",
        "naval_taskforce",
        "recon_platform",
        "field_air_defense",
    ),
    "SVL": ("fragment_low_tech",),
    "TFF": ("fragment_low_tech", "land", "field_air_defense", "air"),
    "TMR": ("industrial",),
    "TRU": ("industrial", "institutional", "land"),
    "VAL": (
        "industrial",
        "energy",
        "institutional",
        "land",
        "air",
        "naval",
        "naval_taskforce",
        "field_air_defense",
    ),
    "VES": ("fragment_low_tech", "land"),
    "VRA": ("fragment_low_tech",),
    "VLA": ("institutional", "land", "air"),
    "WEF": ("institutional", "land", "air"),
    "WIT": ("institutional", "land", "naval"),
    "WRK": (
        "industrial",
        "energy",
        "institutional",
        "land",
        "air",
        "naval",
        "armored_core",
    ),
    "WCG": ("fragment_low_tech", "land"),
    "YPR": ("fragment_low_tech", "land", "field_air_defense", "air"),
    "ZAO": ("fragment_low_tech",),
}

STARTING_COUNTRY_TECH_PROFILE_RATIONALE = {
    "YOR": "Autonomous republic maintains territorial militia and basic workshop production.",
    "RIV": "River administration supplies local garrisons from modest inherited workshops.",
    "EYR": "Autonomous district administration maintains basic workshops and territorial infantry.",
    "EGC": "Confederal garrison retains local workshops and inherited infantry equipment.",
    "AIN": "Nodrul's licensed frontier mandate preserves imported legal and administrative institutions over a small local workshop base.",
    "APH": "Traditional extraction polity with a small arms base and no advanced infrastructure.",
    "ARS": "Small eastern republic retains militia practice and basic workshops without advanced institutions.",
    "AUR": "Civic republic with restored public utilities but only a modest material base.",
    "AZH": "Black Basin levy couples a small field formation with an operating dockyard and coastal flotilla.",
    "BBV": "Single-state Besjaysk fragment with one inherited formation and no industrial plant.",
    "BCM": "Besjaysk fragment sustained by one civilian workshop base.",
    "BGT": "Single-state Besjaysk fragment without an established industrial or institutional base.",
    "BHG": "Single-state Besjaysk fragment with one civilian workshop base.",
    "BJK": "Besjaysk core survives as a small fragment rather than a modern institutional state.",
    "BLD": "Dispersed Besjaysk fragment with no starting factories or advanced service base.",
    "BOR": "Itora-supported frontier republic combines functioning civil institutions with a trained border army.",
    "BRN": "Polar protectorate retains radio, heating, and grid practice but little heavy industry.",
    "BTL": "Multi-state polity with several formations but only a minimal civilian economy.",
    "CIN": "Agrarian ash tribe with informal education and artisan production.",
    "COF": "Forest communes maintain local workshops and a small militia reserve without advanced military institutions.",
    "DAN": "Small military polity with an army but no industrial or energy system to support advanced profiles.",
    "DOL": "Loose road-district union supports militia and workshops without a durable advanced institution base.",
    "DRV": "Decentralized valley communes rely on local workshops and militia organization.",
    "VEL": "Self-governing cantons pool workshop output and maintain a small common militia.",
    "EFL": "Small regional state maintains a standing army, an operating dockyard, and a coastal flotilla despite limited industrial depth.",
    "ELN": "Technocratic census state retains institutional and grid expertise without a full industrial package.",
    "EXZ": "Exclusion-zone placeholder intentionally receives only the common base before its scripted breakup.",
    "RSV": "The isolated northern reservation intentionally receives only the common base pending its gameplay design.",
    "FRS": "Sparse northern federation maintains basic workshops without specialized institutions.",
    "GLP": "Glass Ports trade compact retains maritime practice despite its fragmentary workshop economy.",
    "HON": "Stable civic republic supports institutional research and a trained territorial army.",
    "IIA": "Small island administration retains basic workshops and militia practice without the institutions for an advanced package.",
    "IVN": "Large territory with five research slots, an organized army, and operating air bases.",
    "KDR": "Caravan union relies on mobile low-technology logistics rather than fixed institutions.",
    "KDL": "Island port republic retains basic workshops and militia organization without a heavy industrial base.",
    "KHV": "The reduced northern conclave preserves geothermal practice but its small workshop base no longer supports an industrial package.",
    "KRL": "Winter kingdom fields disciplined formations from a largely traditional material base.",
    "KYZ": "Qanat confederation adds grid and water-system expertise to a fragmentary material base.",
    "LYS": "Trade league preserves administrative practice but lacks advanced heavy industry or a fleet base.",
    "MON": "Northern imperial power combines the Vald coast, a large arsenal belt, four research slots, a modern army, and operating airfields.",
    "MZR": "Water syndicate adds grid engineering to a fragmentary material base.",
    "NAM": "Thinly industrialized regional administration retains an operating dockyard and coastal fleet beside its small field force.",
    "NOD": "High-output military-industrial power with a dockyard and advanced institutional continuity.",
    "NVR": "Pragmatic federation maintains a modest trained army on top of dispersed workshops.",
    "OSF": "Agrarian traditional federation with informal education and limited industrial depth.",
    "PIV": "Small regional army supported by a fragmentary industrial base.",
    "PWR": "Post-war zone intentionally receives only common equipment-enabling roots.",
    "RHM": "Cistern parliament adds grid and water-system expertise to a fragmentary material base.",
    "RIN": "Palatinate maintains a trained palace army while its wider economy remains politically and materially fragmented.",
    "ROM": "Small Vorkerland successor with little intact industry and one inherited formation.",
    "RLY": "Isolated relay enclave retains only fragmentary workshop practice; its tiny economy has no operating power site.",
    "RUS": "One-state, one-slot polity without the institutions needed for advanced profile packages.",
    "SRV": "Long island-chain republic maintains local workshops and a small standing force without advanced specialization.",
    "SDR": "Dry River patrol compact retains local logistics but no advanced industrial specialization.",
    "SHL": "Nine Furnaces compact has the southern region's clearest concentrated workshop base.",
    "SKN": "Military directorate devotes its fragmentary economy to a drilled reserve army.",
    "SLI": "Island council maintains one civilian workshop and a small port without a standing army or heavy industry.",
    "SOL": "Small Vorkerland successor with no intact starting factory base.",
    "STP": "Major industrial state with dockyards, restored air and naval doctrines, and a large standing army.",
    "SVL": "One-island mining republic has basic workshops and militia organization but no advanced institutional base.",
    "TFF": "Frontier districts retain defensive land practice and a small standing army over a fragmentary workshop economy.",
    "TMR": "Utility chamber retains a modest industrial grid while limiting military specialization.",
    "TRU": "Organized Vorkerland successor with enough factories, infrastructure, and army continuity for core profiles.",
    "VAL": "Weapons superpower with twelve military factories, three research slots, and a large convoy reserve.",
    "VES": "Border league maintains defensive land practice over a small regional workshop base.",
    "VRA": "Dispersed lighthouse islands preserve basic workshops and militia practice without advanced institutions.",
    "VLA": "Institutionally capable successor with four research slots, a standing army, and an air base.",
    "WEF": "Organized frontier administration with factories, a standing formation, and an air base.",
    "WIT": "Organized state with a standing army and a large inherited convoy reserve.",
    "WRK": "Largest surviving industrial state with five research slots, power sites, air bases, and convoy capacity.",
    "WCG": "Vorkerland's sealed border administration fields defensive infantry while requisitions and quarantine suppress broader development.",
    "YPR": "Army-bearing regional polity whose small economy remains fragmentary.",
    "ZAO": "High-slot autonomous zone still lacks the factories and infrastructure for broad recovered packages.",
}


STARTING_COUNTRY_TECH_PROFILES.update({
    tag: tuple(country["technology_profiles"])
    for tag, country in REMAINDER_COUNTRIES.items()
})
STARTING_COUNTRY_TECH_PROFILE_RATIONALE.update({
    tag: country["description"]["english"]
    for tag, country in REMAINDER_COUNTRIES.items()
})


ENABLE_SUBUNITS = {
    "ADISCORD_tech_standardized_transport_columns": ("logistics_company", "hq_logistics"),
    "ADISCORD_tech_foot_recon_sections": ("recon", "hq_recon"),
    "ADISCORD_tech_garrison_police_sections": ("military_police", "hq_military_police"),
    "ADISCORD_tech_field_signal_sections": ("signal_company", "hq_signal"),
    "ADISCORD_tech_radiation_patrols": ("ADISCORD_hazard_infantry",),
    "ADISCORD_tech_kefreyt_shield_special_forces": ("ADISCORD_urban_breacher",),
    "ADISCORD_tech_belt_fed_recovery": ("ADISCORD_regimental_fire_support",),
    "ADISCORD_tech_portable_at_cells": ("ADISCORD_regimental_anti_tank",),
    "ADISCORD_tech_shaped_charges": ("ADISCORD_line_anti_tank",),
    "ADISCORD_tech_radar_laying": ("ADISCORD_regimental_anti_air", "ADISCORD_line_anti_air"),
    "ADISCORD_tech_urban_breaching": ("ADISCORD_regimental_pioneers",),
    "ADISCORD_tech_combat_recon_drones": ("ADISCORD_regimental_drone_observers",),
    "ADISCORD_tech_assault_infantry_formations": ("ADISCORD_assault_infantry",),
    # Thunder at Our Gates Army HQ modules.  common/technologies is replaced,
    # so the vanilla unlocks must be attached to A-Discord's own technology
    # graph or every non-basic HQ component remains permanently inactive.
    "ADISCORD_tech_combat_engineering_sections": ("hq_engineer",),
    "ADISCORD_tech_fieldcraft_manuals": ("hq_recon",),
    "ADISCORD_tech_reconstituted_staff_academies": ("hq_military_police",),
    "ADISCORD_tech_standardized_field_tool_chests": (
        "maintenance_company",
        "hq_maintenance",
    ),
    "ADISCORD_tech_frequency_hopping_field_sets": (
        "signal_company",
        "hq_signal",
    ),
    "ADISCORD_tech_casualty_evacuation": (
        "field_hospital",
        "hq_field_hospital",
    ),
    "ADISCORD_tech_forward_supply_hubs": (
        "logistics_company",
        "hq_logistics",
    ),
    "ADISCORD_tech_vertical_assault_training": ("hq_paratrooper",),
    "ADISCORD_tech_restored_armored_chassis": (
        "ADISCORD_light_tank",
        "ADISCORD_recon_platform",
        "hq_light_armor",
    ),
    "ADISCORD_tech_armored_carrier_program": ("ADISCORD_mechanized_infantry",),
    "ADISCORD_tech_recovered_medium_chassis": (
        "ADISCORD_combat_platform",
        "hq_medium_armor",
    ),
    "ADISCORD_tech_heavy_composite_cores": (
        "ADISCORD_heavy_platform",
        "hq_heavy_armor",
    ),
    "ADISCORD_tech_remote_repair_sections": ("ADISCORD_recovery_platform",),
    "ADISCORD_tech_heavy_platform_cores": (
        "ADISCORD_heavy_platform",
        "hq_heavy_armor",
    ),
    "ADISCORD_tech_active_mass_balancing_suspension": (
        "ADISCORD_heavy_platform",
        "hq_heavy_armor",
    ),
}


# `level` is an absolute technology cap, not a +1 increment.
ENABLE_BUILDINGS = {
    "ADISCORD_tech_rare_components_industry": (("ADISCORD_rare_components_plant", 1),),
    "ADISCORD_tech_rare_alloy_metallurgy": (("ADISCORD_rare_alloy_foundry", 1),),
    # Heavy strategic-resource complexes.
    "ADISCORD_tech_logistics_hub_networks": (("ADISCORD_thermal_power_complex", 1),),
    "ADISCORD_tech_borehole_sensor_grids": (("ADISCORD_strategic_mining_complex", 1),),
    "ADISCORD_tech_plasma_scrap_separation": (("ADISCORD_electrolysis_complex", 1),),
    "ADISCORD_tech_microbial_tailings_leaching": (
        ("ADISCORD_metallurgical_complex", 1),
    ),
    # Storage and the absolute regional caps of petrochemical plants.
    "ADISCORD_tech_grid_rationing": (("fuel_silo", 3),),
    "ADISCORD_tech_synthetic_rubber_plants": (("synthetic_refinery", 1),),
    "ADISCORD_tech_rubber_production_lines": (("synthetic_refinery", 2),),
    "ADISCORD_tech_integrated_rubber_complexes": (("synthetic_refinery", 3),),
    # Air defence and detection caps.
    "ADISCORD_tech_radar_laying": (("anti_air_building", 1),),
    "ADISCORD_tech_point_defense_aa": (("anti_air_building", 3),),
    "ADISCORD_tech_networked_air_defense": (("anti_air_building", 4),),
    "ADISCORD_tech_directed_energy_air_defense": (("anti_air_building", 5),),
    "ADISCORD_tech_field_radio_networks": (("radar_station", 1),),
    "ADISCORD_tech_signal_intercept_arrays": (("radar_station", 2),),
    "ADISCORD_tech_phased_array_signal_processing": (("radar_station", 3),),
    "ADISCORD_tech_battlefield_analytics": (("radar_station", 4),),
    "ADISCORD_tech_battlefield_sensor_fusion": (("radar_station", 5),),
    "ADISCORD_tech_memetic_security_protocols": (("radar_station", 6),),
    # Strategic facilities.
    "ADISCORD_tech_strategic_rocket_architecture": (("rocket_site", 1),),
    "ADISCORD_tech_deep_strike_targeting": (("rocket_site", 2),),
    "ADISCORD_tech_suborbital_strike_systems": (("rocket_site", 3),),
    "ADISCORD_tech_reactor_safety_protocols": (("nuclear_reactor_heavy_water", 1),),
    "ADISCORD_tech_microreactor_blocks": (("nuclear_reactor", 1),),
    "ADISCORD_tech_continental_load_balancing": (("commercial_nuclear_reactor", 1),),
    "ADISCORD_tech_civil_defense_networks": (("stronghold_network", 1),),
    "ADISCORD_tech_over_the_horizon_fire_control": (("mega_gun_emplacement", 1),),
}


BUILDING_RESOURCE_UPGRADES = {
    "ADISCORD_tech_precision_polymer_blending": (("synthetic_refinery", "rubber", 1),),
    "ADISCORD_tech_precision_fuel_fractionation": (("synthetic_refinery", "oil", 1),),
    "ADISCORD_tech_precision_component_fabrication": (
        ("ADISCORD_rare_components_plant", "rare_components", 2),
    ),
    "ADISCORD_tech_vacuum_alloy_refining": (
        ("ADISCORD_rare_alloy_foundry", "rare_alloys", 1),
    ),
    "ADISCORD_tech_advanced_material_recycling": (
        ("ADISCORD_rare_components_plant", "rare_components", 1),
        ("ADISCORD_rare_alloy_foundry", "rare_alloys", 1),
    ),
    "ADISCORD_tech_rare_earth_solvent_loops": (
        ("ADISCORD_electrolysis_complex", "aluminium", 2),
    ),
    "ADISCORD_tech_strategic_element_reclamation": (
        ("ADISCORD_electrolysis_complex", "aluminium", 1),
    ),
    "ADISCORD_tech_emulsion_polymerization": (
        ("synthetic_refinery", "rubber", 1),
    ),
    "ADISCORD_tech_selective_polymer_catalysts": (
        ("synthetic_refinery", "rubber", 1),
    ),
    "ADISCORD_tech_closed_cycle_polymerization": (
        ("synthetic_refinery", "rubber", 1),
    ),
    "ADISCORD_tech_synthetic_oil_synthesis": (
        ("synthetic_refinery", "oil", 1),
    ),
    "ADISCORD_tech_catalytic_oil_synthesis": (
        ("synthetic_refinery", "oil", 1),
    ),
    "ADISCORD_tech_closed_cycle_oil_synthesis": (
        ("synthetic_refinery", "oil", 1),
    ),
    "ADISCORD_tech_automated_deep_mining": (
        ("ADISCORD_strategic_mining_complex", "tungsten", 1),
    ),
}


# One-shot research discounts granted for reaching an integration milestone, so
# finishing both arms of a fork or committing to a permanent industrial school
# visibly accelerates the field it belongs to instead of only adding another
# percentage. Every entry names a category the branch already declares, sits at
# or before 2174 so the bonus can still be spent, and must not land on a
# technology that already spends its on_research_complete elsewhere.
RESEARCH_PAYOFFS = {
    # Industry: shop-floor integration and the permanent organisation choice.
    "ADISCORD_tech_predictive_maintenance": ("industry", 0.25, 1),
    # Both organisation schools grant the same industrial bonus; they already
    # differ sharply in their modifiers, so the payoff must not tilt the choice.
    "ADISCORD_tech_centralized_process_control": ("industry", 0.30, 1),
    "ADISCORD_tech_distributed_scheduling_mesh": ("industry", 0.30, 1),
    "ADISCORD_tech_swarm_masonry_platforms": ("construction_tech", 0.25, 1),
    "ADISCORD_tech_public_repair_corps": ("industry", 0.25, 1),
    # Electronics: the two signals routes, computing, and reactor safety.
    "ADISCORD_tech_battlefield_sensor_fusion": ("electronics", 0.30, 1),
    "ADISCORD_tech_counterintelligence_filters": ("decryption_tech", 0.30, 1),
    "ADISCORD_tech_strategic_digital_twins": ("computing_tech", 0.35, 1),
    "ADISCORD_tech_reactor_safety_protocols": ("nuclear", 0.30, 1),
    # Fighting arms: one milestone per combat tab.
    "ADISCORD_tech_autonomous_support_weapons": ("infantry_weapons", 0.30, 1),
    "ADISCORD_tech_limited_battle_ai": ("armor", 0.30, 1),
    "ADISCORD_tech_cooperative_engagement_links": ("artillery", 0.30, 1),
    "ADISCORD_tech_hypersonic_glide_vehicles": ("rocketry", 0.30, 1),
    "ADISCORD_tech_over_horizon_escort_radar": ("naval_equipment", 0.30, 1),
    "ADISCORD_tech_terrain_adaptive_cargo_carriers": ("support_tech", 0.30, 1),
}

RESEARCH_PAYOFFS = {
    key: value for key, value in RESEARCH_PAYOFFS.items() if key in CURRENT_TECH_IDS
}
for _payoff_id, (_, _payoff_bonus, _payoff_uses) in RESEARCH_PAYOFFS.items():
    if _payoff_id not in TECH_POSITION_BY_ID:
        raise ValueError(f"Research payoff targets unknown technology {_payoff_id}")
    _payoff_branch, _payoff_index = TECH_POSITION_BY_ID[_payoff_id]
    if _payoff_branch.years[_payoff_index] > 2174:
        raise ValueError(f"Research payoff on {_payoff_id} lands too late to be spent")
    if not 0 < _payoff_bonus <= 0.5 or _payoff_uses < 1:
        raise ValueError(f"Research payoff on {_payoff_id} is out of range")


CATEGORY_BY_PROFILE = {
    "construction": "industry construction_tech",
    "production": "industry",
    "resources": "industry synth_resources",
    "finance": "industry computing_tech",
    "administration": "industry computing_tech",
    "civil": "industry construction_tech",
    "power": "electronics nuclear",
    "signals": "electronics encryption_tech decryption_tech",
    "computing": "electronics computing_tech",
    "forbidden_energy": "electronics nuclear",
    "forbidden_automation": "electronics computing_tech industry",
    "infantry": "infantry_weapons",
    "squad": "infantry_weapons support_tech",
    "protection": "infantry_weapons support_tech",
    "special_forces": "infantry_weapons support_tech",
    "support": "support_tech",
    "logistics": "support_tech",
    "rail": "support_tech industry",
    "artillery": "artillery",
    "anti_tank": "artillery",
    "anti_air": "artillery electronics",
    "recon_armor": "armor",
    "combat_armor": "armor",
    "heavy_armor": "armor",
    "fighter": "air_equipment electronics",
    "air_support": "air_equipment",
    "strategic_air": "air_equipment rocketry electronics",
    "naval_support": "naval_equipment electronics",
    "surface_fleet": "naval_equipment electronics",
    "subsurface": "naval_equipment electronics",
}


def n(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


# Weapon teams scale with formation doctrine and equipment density. Rifle-only
# formations retain a smaller training benefit without acquiring crew weapons.
SQUAD_WEAPON_TRAINING_SCALE = {
    "ADISCORD_militia": 0.20,
    "ADISCORD_territorial": 0.35,
    "infantry": 1.0,
    "ADISCORD_assault_infantry": 1.0,
    "ADISCORD_urban_breacher": 0.75,
    "ADISCORD_hazard_infantry": 1.0,
    "ADISCORD_mechanized_infantry": 1.0,
    "ADISCORD_marine_infantry": 1.0,
    "mountaineers": 1.0,
    "hq_infantry": 0.35,
    "hq_paratrooper": 0.35,
    "ADISCORD_regimental_fire_support": 1.0,
}


def effects_for(branch: Branch, tier: int) -> tuple[str, ...]:
    effects = branch.techs[tier].effects
    armor_targets = {
        "recon_armor": ("ADISCORD_light_tank", "ADISCORD_recon_platform"),
        "combat_armor": ("ADISCORD_combat_platform",),
        "mechanized_mobility": ("ADISCORD_mechanized_infantry",),
    }
    if branch.key in armor_targets:
        result = []
        for effect in effects:
            if effect.startswith("category_all_armor ="):
                result.extend(
                    effect.replace("category_all_armor =", f"{unit} =", 1)
                    for unit in armor_targets[branch.key]
                )
            else:
                result.append(effect)
        return tuple(result)
    if branch.key != "squad_weapons":
        return effects
    result: list[str] = []
    for effect in effects:
        match = re.fullmatch(r"category_all_infantry = \{ (.+) \}", effect)
        if not match:
            result.append(effect)
            continue
        modifiers = re.findall(r"(\w+) = (-?[0-9.]+)", match[1])
        for unit, scale in SQUAD_WEAPON_TRAINING_SCALE.items():
            payload = " ".join(
                f"{name} = {n(float(value) * scale)}"
                for name, value in modifiers
            )
            result.append(f"{unit} = {{ {payload} }}")
    return tuple(result)


NAVAL_AIR_WEAPON_EFFECTS = {
    "air_independent_cells": ('submarine = { naval_range = 0.10 }',),
    "airborne_homing_torpedoes": (
        'nav_bomber = { naval_strike_attack = 0.10 naval_strike_targetting = 0.08 }',
    ),
    "electronically_scanned_fighter_radar": (
        'ADISCORD_interceptor = { air_attack = 0.08 air_defence = 0.04 }',
    ),
    "guided_munitions": ('cas = { air_ground_attack = 0.08 }',),
    "homing_torpedoes": ('submarine = { torpedo_attack = 0.08 }',),
    "integrated_strike_navigation": (
        'ADISCORD_tactical_bomber = { air_range = 0.08 strategic_attack = 0.06 }',
        'nav_bomber = { air_range = 0.08 naval_strike_targetting = 0.06 }',
    ),
    "jet_strike_bombers": ('ADISCORD_tactical_bomber = { strategic_attack = 0.06 }',),
    "long_range_maritime_aircraft": (
        'nav_bomber = { naval_strike_targetting = 0.06 }',
    ),
    "maritime_patrol_aircraft": ('nav_bomber = { air_range = 0.04 }',),
    "missile_batteries": ('heavy_cruiser = { hg_attack = 0.08 }',),
    "pressurized_bombers": ('ADISCORD_tactical_bomber = { air_defence = 0.04 }',),
    "radar_gunnery": ('heavy_cruiser = { hg_attack = 0.06 }',),
    "stabilized_bomb_sights": (
        'ADISCORD_tactical_bomber = { strategic_attack = 0.08 air_ground_attack = 0.06 }',
    ),
    "twin_engine_aircraft": ('ADISCORD_tactical_bomber = { reliability = 0.02 }',),
}


ALLOW = {
    "ADISCORD_tech_kefreyt_shield_special_forces": (
        "is_special_project_completed = sp:ADISCORD_sp_power_shields",
    ),
    "ADISCORD_tech_old_generator_fragments": (
        "ADISCORD_has_forbidden_legacy_access = yes",
    ),
    "ADISCORD_tech_dead_reactor_salvage": (
        "ADISCORD_has_forbidden_legacy_access = yes",
    ),
    "ADISCORD_tech_legacy_reactor_compactification": (
        "ADISCORD_has_forbidden_legacy_access = yes",
    ),
    "ADISCORD_tech_dirty_energy_munitions": (
        "ADISCORD_has_forbidden_legacy_access = yes",
        "ADISCORD_has_radiation_mapping_tech = yes",
    ),
    "ADISCORD_tech_singularity_cooling_systems": (
        "ADISCORD_has_forbidden_legacy_access = yes",
    ),
    "ADISCORD_tech_black_grid_protocols": ("ADISCORD_has_black_grid_access = yes",),
    "ADISCORD_tech_self_repairing_industrial_swarms": (
        "ADISCORD_has_forbidden_legacy_access = yes",
        "has_tech = ADISCORD_tech_autonomous_factory_cells",
    ),
    "ADISCORD_tech_neural_command_cores": (
        "ADISCORD_has_forbidden_legacy_access = yes",
        "has_tech = ADISCORD_tech_operational_ai_assistants",
    ),
    "ADISCORD_tech_forbidden_automation_doctrine": (
        "ADISCORD_has_black_grid_access = yes",
        "has_tech = ADISCORD_tech_neural_command_cores",
        "has_tech = ADISCORD_tech_self_repairing_industrial_swarms",
    ),
}


FOLDER_BACKGROUNDS = {
    SPECIAL_TECHNOLOGY_FOLDER: "GFX_ADISCORD_technology_transparent_tile",
    "infantry_folder": "GFX_infantry_techtree_bg",
    "support_folder": "GFX_support_techtree_bg",
    "armour_folder": "GFX_armortech_bg",
    "nsb_armour_folder": "GFX_armortech_bg",
    "artillery_folder": "GFX_artillery_techtree_bg",
    "naval_folder": "GFX_naval_techtree_bg",
    "mtgnavalfolder": "GFX_naval_techtree_bg",
    "mtgnavalsupportfolder": "GFX_naval_techtree_bg",
    "air_techs_folder": "GFX_air_techtree_bg",
    "bba_air_techs_folder": "GFX_air_techtree_bg",
    "industry_folder": "GFX_industry_techtree_bg",
    "electronics_folder": "GFX_engineering_techtree_bg",
}


ICON_ALIASES = {
    "advanced_mainframe": "advanced_computing_machine",
    "advanced_modern_tank": "generic_modern_tank",
    "advanced_nuclear_reactor": "nuclear_reactor",
    "armored_car1": "ger_armored_car_equipment_1",
    "armored_car3": "ger_armored_car_equipment_3",
    "armored_train": "train_equipment_2",
    "basic_mainframe": "computing_machine",
    "basic_modern_tank": "generic_modern_tank",
    "basic_small_computer": "mechanical_computing",
    "concentrated_industry1": "concentrated_industry",
    "construction4": "advanced_construction",
    "construction5": "advanced_construction",
    "decryption1": "basic_decryption",
    "decryption2": "improved_decryption",
    "electrical_mechanical_engineering": "electronic_mechanical_engineering",
    "encryption1": "basic_encryption",
    "encryption2": "improved_encryption",
    "encryption3": "advanced_encryption",
    "guided_missile": "guided_missile_1",
    "guided_missile2": "guided_missile_2",
    "guided_missile3": "guided_missile_3",
    "improved_mainframe": "improved_computing_machine",
    "improved_modern_tank": "generic_modern_tank",
    "improved_nuclear_reactor": "nuclear_reactor",
    "improved_small_computer": "improved_computing_machine",
    "jet_CAS1": "CAS2",
    "jet_CAS2": "CAS3",
    "land_cruiser": "generic_land_cruiser_chassis",
    "maintenance_company": "tech_maintenance_company",
    "motorized_infantry": "motorised_infantry",
    "naval_mines1": "basic_naval_mines",
    "naval_mines3": "advanced_naval_mines",
    "naval_radar4": "advanced_centimetric_radar",
    "night_vision1": "night_vision",
    # Never turn an abstract energy programme into a nuclear-warhead card.
    "nuclear_bomb": "sp_nuclear_isotope_separation",
    "railgun": "generic_railway_gun",
    "railway_gun": "generic_railway_gun",
    "railway_gun2": "generic_super_heavy_railway_gun",
    "rocket_engines2": "improved_rocket_engines",
    "signal_company": "tech_signal_company",
    "sonar1": "sonar",
    "sonar2": "improved_sonar",
    "special_forces": "tech_special_forces",
    "special_project_air_guided_missile": "sp_rockets_glide_bombs",
    "special_project_air_icbm": "guided_missile_3",
    "special_project_air_nuclear_missile": "sp_rockets_improved_guidance",
    "special_project_land_railgun": "generic_super_heavy_railway_gun",
    "special_project_nuclear_reactor": "nuclear_reactor",
    "special_project_thermonuclear_bomb": "advanced_centimetric_radar",
    "tech_engineers": "engineers",
    "tech_engineers2": "engineers2",
    "tech_engineers3": "engineers3",
    "tech_engineers4": "engineers4",
    "tech_recon": "recon",
    "tech_recon2": "recon2",
    "tech_recon3": "recon3",
    "tech_recon4": "recon4",
    "torpedo1": "basic_torpedo",
    "train_tech": "train_equipment_1",
    "train_tech2": "train_equipment_2",
    "train_tech3": "train_equipment_3",
}


# Equipment silhouettes in the vanilla technology atlas can be 150-285 px
# wide.  They are useful on the few nodes that actually unlock equipment, but
# overlap neighbouring 140 px columns when reused for every dense incremental
# technology.  Oversized non-unlock icons are therefore replaced with compact
# 64 px symbols while keeping real equipment unlocks visually distinctive.
COMPACT_ICONS_BY_PROFILE = {
    "construction": (
        "basic_construction",
        "improved_construction",
        "advanced_construction",
    ),
    "production": ("basic_machine_tools", "flexible_line", "assembly_line_production"),
    "resources": ("excavation1", "oil_processing", "rubber_processing"),
    "finance": ("mechanical_computing", "computing_machine"),
    "administration": ("radio", "computing_machine"),
    "civil": ("basic_construction", "improved_construction", "radio"),
    "power": ("electronic_mechanical_engineering", "atomic_research", "radio"),
    "signals": ("radio", "basic_encryption", "basic_decryption"),
    "computing": (
        "mechanical_computing",
        "computing_machine",
        "improved_computing_machine",
    ),
    "forbidden_energy": ("atomic_research", "nuclear_reactor"),
    "forbidden_automation": ("flexible_line", "advanced_computing_machine"),
    "infantry": ("infantry_weapons", "infantry_weapons2", "night_vision"),
    "squad": ("support_weapons", "support_weapons2", "infantry_at"),
    "protection": ("night_vision", "basic_construction", "improved_construction"),
    "special_forces": ("night_vision", "radio", "basic_decryption"),
    "support": ("basic_machine_tools", "improved_construction", "radio"),
    "logistics": ("radio", "computing_machine", "assembly_line_production"),
    "rail": ("basic_machine_tools", "basic_construction", "assembly_line_production"),
    "artillery": ("artillery1", "artillery2", "artillery3"),
    "anti_tank": ("antitank1", "antitank2", "antitank3"),
    "anti_air": ("antiair1", "antiair2", "antiair3"),
    "recon_armor": ("nsb_engine_tech_1", "nsb_armor_tech_1", "basic_machine_tools"),
    "combat_armor": ("nsb_armor_tech_1", "nsb_engine_tech_1", "advanced_machine_tools"),
    "heavy_armor": ("nsb_armor_tech_1", "nsb_engine_tech_2", "advanced_machine_tools"),
    "fighter": (
        "bba_tech_aircraft_construction",
        "bba_tech_engines_1",
        "centimetric_radar",
    ),
    "air_support": ("bba_tech_armor_piercing_bombs", "bba_tech_engines_1", "radio"),
    "strategic_air": ("rocket_engines", "advanced_rocket_engines", "centimetric_radar"),
    "naval_support": ("sonar", "advanced_sonar", "advanced_centimetric_radar"),
    "surface_fleet": (
        "basic_cruiser_armor_scheme",
        "advanced_centimetric_radar",
        "naval_air_operations",
    ),
    "subsurface": ("sonar", "basic_naval_mines", "advanced_sonar"),
}


# Wide cards are reserved for technologies that unlock something the player
# can actually put on a production line. Give those cards the corresponding
# equipment silhouette instead of a 64px support-company badge.
EQUIPMENT_UNLOCK_ICONS = {
    "ADISCORD_tech_pulse_doppler_radar": "heavy_fighter1",
    "ADISCORD_tech_autonomous_dogfight_controller": "heavy_fighter3",
    "ADISCORD_tech_cruise_missiles": "strategic_bomber1",
    "ADISCORD_tech_restored_airlift_planning": "transport_plane_equipment",
    "ADISCORD_tech_vertical_envelopment_control": "transport_plane_equipment",
    "ADISCORD_tech_precision_aerial_resupply": "transport_plane_equipment",
    "ADISCORD_tech_restored_armored_chassis": "basic_light_tank",
    "ADISCORD_tech_recovered_medium_chassis": "basic_medium_tank",
    "ADISCORD_tech_heavy_composite_cores": "basic_heavy_tank",
    "ADISCORD_tech_postwar_weapon_standardization": "ADISCORD_weapon_01_reclaimed_arsenal",
    "ADISCORD_tech_refurbished_receivers": "ADISCORD_weapon_02_recovered_service_rifle",
    "ADISCORD_tech_sealed_receiver_assemblies": "ADISCORD_weapon_03_standardized_battle_rifle",
    "ADISCORD_tech_smart_recoil_compensators": "ADISCORD_weapon_04_transitional_modular_weapon",
    "ADISCORD_tech_smart_optics": "ADISCORD_weapon_05_suppressed_assault_system",
    "ADISCORD_tech_modular_rifle_kits": "ADISCORD_weapon_06_networked_smart_rifle",
    "ADISCORD_tech_programmable_ammunition": "ADISCORD_weapon_07_programmable_munition_weapon",
    "ADISCORD_tech_coil_assisted_service_rifles": "ADISCORD_weapon_08_advanced_impulse_weapon",
    "ADISCORD_tech_networked_service_rifles": "ADISCORD_weapon_09_resilient_combat_network_weapon",
    "ADISCORD_tech_belt_fed_recovery": "ADISCORD_squad_01_recovered_fire_support",
    "ADISCORD_tech_squad_grenade_launchers": "ADISCORD_squad_02_belt_fed_sections",
    "ADISCORD_tech_portable_at_cells": "ADISCORD_squad_03_standardized_heavy_weapons",
    "ADISCORD_tech_recoilless_squad_launchers": "ADISCORD_squad_04_modular_support_weapons",
    "ADISCORD_tech_field_ew_units": "ADISCORD_squad_05_sensor_linked_fireteams",
    "ADISCORD_tech_remote_weapon_tripods": "ADISCORD_squad_06_programmable_support_systems",
    "ADISCORD_tech_autonomous_support_weapons": "ADISCORD_squad_07_networked_precision_support",
    "ADISCORD_tech_robotic_heavy_weapon_teams": "ADISCORD_squad_08_autonomous_fire_control",
    "ADISCORD_tech_swarm_fireteams": "ADISCORD_squad_09_swarm_coordinated_support",
    "ADISCORD_tech_field_workshop_tools": "ADISCORD_support_01_field_kit",
    "ADISCORD_tech_drone_delivered_repair_spares": "ADISCORD_support_02_drone_kit",
    "ADISCORD_tech_predictive_parts_prepositioning": "ADISCORD_support_02_drone_kit",
    "ADISCORD_tech_self_sustaining_support": "ADISCORD_support_02_drone_kit",
    "ADISCORD_tech_hardened_logistics_nodes": "train_equipment_3",
    "ADISCORD_tech_restored_field_artillery": "artillery_equipment",
    "ADISCORD_tech_electrohydraulic_gun_laying": "artillery_equipment",
    "ADISCORD_tech_assisted_projectiles": "artillery_equipment",
    "ADISCORD_tech_uncrewed_howitzer_sections": "artillery_equipment",
    "ADISCORD_tech_salvaged_at_guns": "anti_tank_equipment",
    "ADISCORD_tech_scrap_at_launchers": "anti_tank_equipment",
    "ADISCORD_tech_top_attack_munitions": "anti_tank_equipment",
    "ADISCORD_tech_superconducting_coil_barrels": "anti_tank_equipment",
    "ADISCORD_tech_improvised_air_defense": "anti_air_equipment",
    "ADISCORD_tech_stabilized_autocannon_mounts": "anti_air_equipment",
    "ADISCORD_tech_integrated_short_range_missile_cells": "anti_air_equipment",
    "ADISCORD_tech_high_energy_laser_turrets": "anti_air_equipment",
    "ADISCORD_tech_remote_repair_sections": "generic_armored_support_vehicle_recovery_1",
    "ADISCORD_tech_low_observable_inlet_geometry": "fighter2",
    "ADISCORD_tech_cooperative_fighter_sensor_fusion": "jet_fighter2",
    "ADISCORD_tech_loyal_wingmen": "jet_fighter2",
    "ADISCORD_tech_orbital_tracking_relics": "strategic_bomber2",
    "ADISCORD_tech_low_observable_cruise_missile_skins": "guided_missile_2",
    "ADISCORD_tech_suborbital_skip_glide_guidance": "strategic_bomber3",
    "ADISCORD_tech_autonomous_strategic_strike_planning": "guided_missile_3",
    "ADISCORD_tech_suborbital_strike_systems": "jet_strategic_bomber1",
}


EQUIPMENT_UNLOCK_ICONS.update(
    {f"ADISCORD_tech_{key}": icon for key, (_, icon) in NAVAL_AIR_UNLOCKS.items()}
)
EQUIPMENT_UNLOCK_ICONS.update({
    f"ADISCORD_tech_{key}": icon for key, (_, icon) in NAVAL_AIR_RESEARCH.items()
})
EQUIPMENT_UNLOCK_ICONS["ADISCORD_tech_twin_engine_aircraft"] = "tactical_bomber1"


# Infantry effect-only cards show the equipment being improved. Their art
# must stay attached to the technology when the branch order changes.
REGIONAL_SERVICE_ICON_TAGS = ("STP", "VAL")

INFANTRY_COMPACT_ICONS = {
    key: icon
    for icon, keys in {
        "ADISCORD_equipment_ammunition": (
            "standardized_cartridges",
            "caseless_ammunition_trials",
            "hybrid_kinetic_energy_carbines",
            "programmable_grenade_fuzes",
            "deep_area_sustainment_pods",
        ),
        "ADISCORD_equipment_mechanism": (
            "electrothermal_ignition",
            "biometric_trigger_locks",
        ),
        "ADISCORD_equipment_armour": (
            "composite_protection_kits",
            "trauma_plates",
            "ceramic_trauma_inserts",
            "adaptive_radiation_shielding",
            "self_sealing_combat_skins",
        ),
        "ADISCORD_equipment_camouflage": (
            "thermal_signature_liners",
            "reactive_camouflage_textiles",
            "adaptive_camouflage",
            "low_observable_infiltration_suits",
            "multispectral_concealment_discipline",
        ),
        "ADISCORD_equipment_medical": (
            "smart_tourniquet_systems",
            "nanofiber_wound_dressings",
        ),
        "ADISCORD_equipment_respirator": (
            "sealed_combat_suits",
            "sealed_respirator_interfaces",
            "radiation_patrols",
        ),
        "ADISCORD_equipment_drone": (
            "drone_guided_support_fire",
            "combat_recon_drones",
            "autonomous_scout_microdrones",
            "robotic_breaching_companions",
        ),
        "ADISCORD_equipment_radio": (
            "networked_command_terminals",
            "cooperative_target_handoff",
            "swarm_coordinated_fire_support",
            "remote_beacon_extraction",
            "contested_zone_navigation",
            "augmented_mission_rehearsal",
        ),
        "ADISCORD_equipment_climbing": (
            "fieldcraft_manuals",
            "subterranean_route_reconnaissance",
            "urban_vertical_access_rigs",
            "vertical_assault_training",
        ),
        "ADISCORD_equipment_breaching": (
            "urban_breaching",
            "assault_sapper_kits",
        ),
        "ADISCORD_equipment_exoskeleton": (
            "powered_load_bearing_harnesses",
            "exoskeleton_load_frames",
            "exosuit_joint_actuators",
            "augmented_special_forces",
        ),
        "ADISCORD_equipment_ballistic_sight": (
            "networked_weapon_sights",
            "integrated_target_designation",
        ),
        "ADISCORD_night_01_passive_intensifier": (
            "passive_intensifier_cells",
            "sealed_night_mounts",
            "fused_low_light_sights",
            "nocturnal_sensor_discipline",
        ),
        "ADISCORD_night_02_thermal_channel": (
            "thermal_observation_channels",
            "thermal_target_libraries",
        ),
        "ADISCORD_night_04_squad_target_sharing": (
            "squad_target_sharing",
            "distributed_night_engagements",
            "nocturnal_combat_mesh",
            "deep_recon_cells",
            "predictive_patrol_evasion",
        ),
        "ADISCORD_night_05_counter_illumination": (
            "low_signature_illumination",
            "counter_illumination_warnings",
            "man_portable_sensor_masts",
            "distributed_recon_sensor_caches",
        ),
        "ADISCORD_antitank_11_loitering_munition": ("loitering_munition_teams",),
        "ADISCORD_equipment_mortar": ("autonomous_mortar_sections",),
        "ADISCORD_equipment_medical_drone": ("battlefield_medical_drones",),
        "ADISCORD_equipment_insertion_pod": ("high_altitude_insertion_capsules",),
        "ADISCORD_equipment_hearing_protection": ("active_hearing_protection",),
        "ADISCORD_equipment_casualty_monitor": ("autonomous_casualty_monitors",),
        "ADISCORD_equipment_life_support": ("closed_loop_combat_life_support",),
        "ADISCORD_equipment_ammunition_carrier": ("distributed_ammunition_carriers",),
        "ADISCORD_equipment_drone_jammer": ("microdrone_suppression_nets",),
        "ADISCORD_antitank_04_antitank_rifle": (
            "electromagnetic_anti_armor_launchers",
        ),
    }.items()
    for key in keys
}


def technology_icon_size(icon: str) -> tuple[int, int] | None:
    relative = Path("gfx") / "interface" / "technologies" / f"{icon}.dds"
    for root in (ROOT, BASE_GAME):
        path = root / relative
        if not path.exists():
            continue
        with path.open("rb") as stream:
            header = stream.read(20)
        if len(header) >= 20 and header[:4] == b"DDS ":
            height = int.from_bytes(header[12:16], "little")
            width = int.from_bytes(header[16:20], "little")
            return width, height
    return None


WEAPON_CATEGORY_ICONS = {
    tech.key: "ADISCORD_squad_01_recovered_fire_support"
    for tech in BRANCH_BY_KEY["squad_weapons"].techs
    if tech.id in ENABLE_EQUIPMENT
}
WEAPON_CATEGORY_ICONS.update(
    {
        "portable_at_cells": "ADISCORD_squad_02_heavy_machine_guns",
        "recoilless_squad_launchers": "ADISCORD_squad_02_heavy_machine_guns",
        "field_ew_units": "ADISCORD_squad_03_optical_fire_support",
        "remote_weapon_tripods": "ADISCORD_squad_03_optical_fire_support",
        "autonomous_support_weapons": "ADISCORD_squad_04_advanced_fire_support",
        "robotic_heavy_weapon_teams": "ADISCORD_squad_04_advanced_fire_support",
        "swarm_fireteams": "ADISCORD_squad_04_advanced_fire_support",
        "electrothermal_ignition": "ADISCORD_weapon_03_standardized_battle_rifle",
        "biometric_trigger_locks": "ADISCORD_weapon_03_standardized_battle_rifle",
        "field_workshop_tools": EQUIPMENT_UNLOCK_ICONS["ADISCORD_tech_field_workshop_tools"],
        "drone_delivered_repair_spares": EQUIPMENT_UNLOCK_ICONS["ADISCORD_tech_drone_delivered_repair_spares"],
        "predictive_parts_prepositioning": EQUIPMENT_UNLOCK_ICONS["ADISCORD_tech_predictive_parts_prepositioning"],
        "self_sustaining_support": EQUIPMENT_UNLOCK_ICONS["ADISCORD_tech_self_sustaining_support"],
    }
)


PROTECTION_TECH_ICONS = {
    "thermal_signature_liners": "ADISCORD_equipment_protection_camouflage",
    "reactive_camouflage_textiles": "ADISCORD_equipment_protection_camouflage",
    "adaptive_camouflage": "ADISCORD_equipment_protection_camouflage",
    "composite_protection_kits": "ADISCORD_equipment_protection_body_armour",
    "trauma_plates": "ADISCORD_equipment_protection_trauma_pads",
    "ceramic_trauma_inserts": "ADISCORD_equipment_protection_ceramic_plates",
    "sealed_combat_suits": "ADISCORD_equipment_protection_respirator",
    "sealed_respirator_interfaces": "ADISCORD_equipment_protection_respirator",
    "active_hearing_protection": "ADISCORD_equipment_protection_hearing",
    "powered_load_bearing_harnesses": "ADISCORD_equipment_protection_exoskeleton",
    "exoskeleton_load_frames": "ADISCORD_equipment_protection_exoskeleton",
    "exosuit_joint_actuators": "ADISCORD_equipment_protection_exoskeleton",
}


def icon_for_technology(branch: Branch, index: int) -> str:
    tech = branch.techs[index]
    if tech.key in PROTECTION_TECH_ICONS:
        return PROTECTION_TECH_ICONS[tech.key]
    if tech.icon in NAVAL_HULL_ART:
        return tech.icon
    if tech.key in NAVAL_UPGRADE_ICONS:
        return NAVAL_UPGRADE_ICONS[tech.key]
    if tech.key in WEAPON_CATEGORY_ICONS:
        return WEAPON_CATEGORY_ICONS[tech.key]
    if branch.key in {"small_arms", "assault_rifles"} and tech.id in ENABLE_EQUIPMENT:
        generation = {
            "postwar_weapon_standardization": 1,
            "refurbished_receivers": 2,
        }.get(tech.key, 3)
        return (
            "ADISCORD_weapon_01_reclaimed_arsenal",
            "ADISCORD_weapon_02_recovered_service_rifle",
            "ADISCORD_weapon_03_standardized_battle_rifle",
        )[generation - 1]
    if branch.key == "night_combat":
        if tech.key in INFANTRY_COMPACT_ICONS:
            return INFANTRY_COMPACT_ICONS[tech.key]
        return (
            "night_vision"
            if tech.key
            in {
                "passive_intensifier_cells",
                "thermal_observation_channels",
            }
            else "night_vision2"
        )
    if tech.key == "fire_and_forget_seekers":
        return "ADISCORD_antitank_09_top_attack_seeker"
    candidates = (
        EQUIPMENT_UNLOCK_ICONS.get(tech.id, ""),
        INFANTRY_COMPACT_ICONS.get(tech.key, ""),
        ICON_ALIASES.get(tech.icon, tech.icon),
        *COMPACT_ICONS_BY_PROFILE[branch.profile],
    )
    max_width, max_height = (190, 84) if tech.id in ENABLE_EQUIPMENT else (72, 72)
    for candidate in candidates:
        size = technology_icon_size(candidate)
        if (
            size
            and candidate.startswith("ADISCORD_")
            and size[0] <= 190
            and size[1] <= 84
        ):
            return candidate
        if size and size[0] <= max_width and size[1] <= max_height:
            return candidate
    raise ValueError(f"{tech.id}: no available artwork fits its research card")


BRANCH_DESCRIPTION_RU = {
    "construction": "ускоряет восстановление инфраструктуры и ремонт разрушенных объектов",
    "production": "повышает эффективность, гибкость и автоматизацию производства",
    "resources": "увеличивает добычу, переработку и возврат стратегических материалов",
    "finance": "улучшает управление бюджетом, резервами и государственными контрактами",
    "administration": "ускоряет исследования и координацию государственного аппарата",
    "civil": "укрепляет гражданскую оборону и устойчивость населения",
    "power": "развивает энергосети, реакторные технологии и защищённую энергетику",
    "signals": "совершенствует защищённую связь, разведку сигналов и киберзащиту",
    "computing": "развивает вычислительные комплексы и системы поддержки решений",
    "forbidden_energy": "открывает опасные технологии старого мира ценой общественной стабильности",
    "forbidden_automation": "передаёт производство и управление запрещённым автономным системам",
    "infantry": "повышает огневую мощь и пробивную способность линейной пехоты",
    "squad": "усиливает отделение коллективным оружием и сетевым управлением",
    "anti_tank_infantry": "развивает переносные средства поражения бронетехники и связывает охотничьи расчёты в единый контур",
    "night_combat": "развивает пассивное наблюдение, тепловизионное обнаружение и скрытую координацию боя ночью",
    "protection": "улучшает защиту, выживаемость и медицинское обеспечение бойцов",
    "special_forces": "повышает мобильность и эффективность разведки и специальных сил",
    "support": "усиливает инженерные, ремонтные и медицинские подразделения",
    "logistics": "снижает расход снабжения и ускоряет переброску резервов",
    "rail": "повышает устойчивость железнодорожного снабжения и ремонта путей",
    "artillery": "повышает точность, надёжность и огневую мощь артиллерии",
    "anti_tank": "увеличивает бронепробитие и эффективность против тяжёлых целей",
    "anti_air": "усиливает обнаружение и поражение воздушных целей",
    "recon_armor": "повышает скорость и надёжность разведывательной бронетехники",
    "combat_armor": "усиливает огневую мощь и прорыв основных боевых танков",
    "heavy_armor": "повышает защиту и живучесть тяжёлых автономных танков",
    "fighter": "повышает эффективность перехвата и снижает аварийность авиации",
    "air_support": "повышает эффективность непосредственной поддержки наземных войск",
    "strategic_air": "развивает дальние ракетные удары и стратегическое наведение",
    "naval_support": "улучшает охранение конвоев и обнаружение угроз на море",
    "surface_fleet": "повышает точность и координацию надводных соединений",
    "subsurface": "развивает подводное обнаружение, скрытность и морское сдерживание",
}


BRANCH_DESCRIPTION_EN = {
    key: {
        "construction": "accelerates reconstruction and repair of damaged infrastructure",
        "production": "improves the efficiency, flexibility, and automation of production",
        "resources": "increases extraction, processing, and recovery of strategic materials",
        "finance": "improves budget, reserve, and public-contract management",
        "administration": "accelerates research and coordination of the state apparatus",
        "civil": "strengthens civil defense and population resilience",
        "power": "develops power grids, reactors, and hardened energy systems",
        "signals": "improves secure communications, signals intelligence, and cyber defense",
        "computing": "develops computing complexes and decision-support systems",
        "forbidden_energy": "unlocks dangerous old-world technology at the cost of stability",
        "forbidden_automation": "hands production and command to prohibited autonomous systems",
        "infantry": "improves the firepower and penetration of line infantry",
        "squad": "strengthens squads with support weapons and networked command",
        "anti_tank_infantry": "develops portable anti-armor weapons and links hunter teams into one engagement mesh",
        "night_combat": "develops passive observation, thermal detection, and concealed coordination in darkness",
        "protection": "improves soldier protection, survival, and battlefield medicine",
        "special_forces": "improves the mobility and effectiveness of recon and special forces",
        "support": "strengthens engineering, repair, and medical units",
        "logistics": "reduces supply use and accelerates movement of reserves",
        "rail": "improves the resilience of railway supply and track repair",
        "artillery": "improves artillery accuracy, reliability, and firepower",
        "anti_tank": "increases armor penetration and performance against heavy targets",
        "anti_air": "improves detection and destruction of aerial targets",
        "recon_armor": "improves the speed and reliability of reconnaissance armor",
        "combat_armor": "improves the firepower and breakthrough of main battle tanks",
        "heavy_armor": "improves protection and survivability of heavy autonomous tanks",
        "fighter": "improves interception efficiency and reduces aviation accidents",
        "air_support": "improves close support for ground forces",
        "strategic_air": "develops long-range missile strikes and strategic guidance",
        "naval_support": "improves convoy protection and detection of maritime threats",
        "surface_fleet": "improves accuracy and coordination of surface task forces",
        "subsurface": "develops underwater detection, stealth, and maritime denial",
    }[key]
    for key in BRANCH_DESCRIPTION_RU
}


SUPPORT_BRANCH_DESCRIPTIONS = {
    "reserve_training": (
        "Подготовка местного резерва усиливает указанные ополченческие или территориальные батальоны. Две линии развиваются независимо; регулярная пехота сохраняет преимущество в наступлении",
        "Local reserve training improves the specified militia or territorial battalions. Both lines develop independently; regular infantry retains its offensive advantage",
    ),
    "field_reconnaissance": (
        "Пешая разведка поддерживает дивизии без бронемашин и топлива. Улучшения действуют на пешую разведывательную роту, которую нужно добавить в шаблон и снабдить оснащением",
        "Foot reconnaissance supports divisions without armored vehicles or fuel. Upgrades apply to foot reconnaissance companies, which must be included in a template and equipped",
    ),
    "field_signals": (
        "Подготовка связистов и организация полевых сетей улучшают роту связи в составе дивизии. Производство радиокомпонентов и общая электроника исследуются отдельно",
        "Signal training and field network organization improve a division's signal company. Radio components and general electronics are researched separately",
    ),
    "garrison_security": (
        "Военная полиция повышает подавление сопротивления в гарнизонном шаблоне. Исследование не размещает части автоматически: роту нужно включить в шаблон и обеспечить людьми и снаряжением",
        "Military police improves resistance suppression in a garrison template. Research does not deploy troops automatically: include the company in the template and provide personnel and equipment",
    ),
    "field_support": (
        "Полевые комплекты обеспечивают работу служб дивизии. Специализированные ремонтные исследования повышают надёжность и сбор трофеев через оснащённую ремонтную роту",
        "Field kits supply divisional services. Specialized maintenance research improves reliability and equipment recovery through an equipped maintenance company",
    ),
    "logistics": (
        "Транспортная служба доставляет боеприпасы и горючее. Улучшения роты снабжения действуют в дивизиях с этой ротой и требуют её полного оснащения",
        "Transport services deliver ammunition and fuel. Logistics company upgrades apply to divisions using that company and require its equipment",
    ),
    "combat_medicine": (
        "Полевой госпиталь возвращает часть раненых в строй и уменьшает потерю опыта. Для применения медицинских улучшений госпиталь должен входить в состав дивизии",
        "Field hospitals return some casualties to service and reduce experience loss. Medical upgrades require a hospital in the division template",
    ),
}


TECHNICAL_TECH_DESCRIPTIONS = {
    "baseload_reactor_dispatch": (
        "Единая диспетчерская согласует нагрузку промышленных узлов, сокращает потери энергии и поддерживает непрерывный выпуск",
        "Central dispatch balances industrial loads, reduces energy losses and sustains continuous production",
    ),
    "reconstruction_bureaus": (
        "Строительные бюро открывают отдельные программы освоения площадок и ремонта. Ремонтные корпуса не требуются для расширения мест под здания",
        "Construction bureaus open separate land-development and repair programmes. Repair corps are not required to expand building capacity",
    ),
    "recovered_semiconductors": (
        "Восстановленная элементная база позволяет независимо развивать защищённые полевые вычисления, специализированные вычислительные центры и производство микросхем",
        "Recovered components support independent development of rugged field computing, specialised computing centres and chip manufacturing",
    ),
    "local_grid_restoration": (
        "Восстановление электроснабжения открывает самостоятельные программы энергосетей и реакторной энергетики. Модернизация сети не требует изучения реакторов",
        "Restored power supply opens independent grid and reactor programmes. Grid modernisation does not require reactor research",
    ),
    "flexible_robotic_tooling": (
        "Перенастраиваемые роботы ускоряют освоение новой продукции и сохраняют эффективность при смене заказов. Эта специализация выбирается независимо от ранней школы станкостроения",
        "Reconfigurable robots accelerate new production runs and retain efficiency when orders change. This specialisation is independent of the earlier tooling choice",
    ),
    "machine_vision_inspection": (
        "Машинное зрение повышает выпуск и предельную эффективность серийных линий за счёт непрерывного контроля качества. Эта специализация выбирается независимо от ранней школы станкостроения",
        "Machine vision improves output and maximum efficiency through continuous quality inspection. This specialisation is independent of the earlier tooling choice",
    ),
    "restored_armored_chassis": (
        "Восстановленное лёгкое шасси открывает производство лёгких танков, линейный лёгкий танковый батальон и роту бронеразведки. Батальоны можно добавлять в бронетанковые полки через конструктор дивизий; разведрота занимает ячейку поддержки",
        "Restored light chassis unlock light tank production, line light tank battalions and armored reconnaissance companies. Add battalions to armored regiments in the division designer; reconnaissance uses a support slot",
    ),
    "recovered_medium_chassis": (
        "Открывает производство восстановленного основного танка и танковый батальон. Сочетайте танки с пехотой для организации и удержания позиций, затем заменяйте пешее сопровождение механизированным по мере развития промышленности",
        "Unlocks restored main battle tank production and tank battalions. Combine tanks with infantry for organization and holding ground, then introduce mechanized infantry as industry develops",
    ),
    "heavy_composite_cores": (
        "Открывает ранний тяжёлый танк и тяжёлый танковый батальон. Усиленная броня и прорыв оплачиваются более высокой стоимостью, расходом топлива и меньшей скоростью",
        "Unlocks an early heavy tank and heavy tank battalions. Stronger armor and breakthrough come with higher production and fuel costs and lower speed",
    ),
    "standardized_utility_corridors": (
        "Единые трассы электроснабжения, воды и транспорта освобождают площадки для новой застройки",
        "Shared power, water and transport corridors release additional land for construction",
    ),
    "serviced_industrial_sites": (
        "Подготовленные фундаменты и инженерные подключения расширяют число доступных заводских площадок",
        "Prepared foundations and utility connections expand the available factory sites",
    ),
    "compact_industrial_zoning": (
        "Совместное использование подъездных путей и складов позволяет размещать больше предприятий в одном районе",
        "Shared access roads and warehouses fit more factories into each district",
    ),
    "rapid_reconstruction_standards": (
        "Типовые проекты и ремонтные комплекты сокращают сроки строительства и восстановления предприятий",
        "Standard designs and repair kits shorten construction and factory restoration",
    ),
    "multilevel_industrial_districts": (
        "Разделение производственных, складских и транспортных уровней увеличивает вместимость промышленных районов",
        "Separate production, storage and transport levels increase industrial district capacity",
    ),
    "vertical_factory_districts": (
        "Многоэтажные производственные корпуса позволяют плотной застройке освоить дополнительные площадки",
        "Multistorey factory buildings extend the capacity of densely developed districts",
    ),
    "resilient_utility_construction": (
        "Сменные секции коммуникаций и резервные подключения ускоряют стройку и восстановление после разрушений",
        "Replaceable utility sections and backup connections speed construction and recovery from damage",
    ),
    "integrated_land_development": (
        "Согласованное освоение земли и инженерных сетей открывает новые территории для предприятий",
        "Coordinated land and utility development opens new territory for factories",
    ),
    "integrated_city_complexes": (
        "Совместное планирование жилых, производственных и транспортных зон расширяет строительную вместимость региона",
        "Integrated residential, industrial and transport planning expands state building capacity",
    ),
    "scientific_computing_centres": (
        "Вычислительные мощности направляются на научные модели и обработку экспериментов, ускоряя дальнейшие исследования",
        "Computing capacity supports scientific models and experimental analysis, accelerating further research",
    ),
    "parallel_numerical_solvers": (
        "Распределение сложных расчётов между вычислительными узлами ускоряет исследовательские проекты",
        "Distributing complex calculations across computing nodes accelerates research projects",
    ),
    "photonic_research_processors": (
        "Оптические вычислительные узлы увеличивают скорость научного моделирования и требуют дополнительного энергоснабжения",
        "Optical computing nodes accelerate scientific modelling and require additional power",
    ),
    "industrial_process_optimizers": (
        "Расчёт загрузки оборудования сокращает простои и ускоряет освоение серийного выпуска",
        "Machine-load optimisation reduces downtime and accelerates production-line ramp-up",
    ),
    "semiconductor_clean_rooms": (
        "Контроль загрязнения при сборке микроэлектроники сокращает брак и ускоряет выход производства на рабочий режим",
        "Contamination control in microelectronics assembly reduces defects and speeds production ramp-up",
    ),
    "industrial_computing_centres": (
        "Прикладные вычисления распределяют заводские заказы и загрузку станков, повышая выпуск и скорость освоения производства",
        "Applied computing allocates factory orders and machine loads, improving output and production ramp-up",
    ),
    "silicon_feedstock_purification": (
        "Очистка кремния повышает выход годных микросхем и надёжность исследовательской аппаратуры",
        "Silicon purification improves usable chip yields and research equipment reliability",
    ),
    "precision_photolithography": (
        "Точное нанесение рисунка микросхем ускоряет освоение новых серий и изготовление научных приборов",
        "Precision circuit patterning speeds new production runs and scientific instrument development",
    ),
    "fault_tolerant_chip_packaging": (
        "Стандартизированная сборка микросхем упрощает замену компонентов при переналадке производственных линий",
        "Standard chip packaging simplifies component replacement when production lines change",
    ),
    "high_density_integrated_circuits": (
        "Более плотные схемы увеличивают вычислительные возможности приборов и производственного оборудования",
        "Denser circuits expand the computing capabilities of instruments and factory equipment",
    ),
    "optical_chip_interconnects": (
        "Оптическая передача между вычислительными узлами ускоряет обработку данных и сокращает электрические потери",
        "Optical links between computing nodes accelerate data processing and reduce electrical losses",
    ),
    "automated_wafer_inspection": (
        "Автоматическое обнаружение дефектов пластин стабилизирует серийное производство микроэлектроники",
        "Automatic wafer-defect detection stabilises serial microelectronics production",
    ),
    "three_dimensional_chip_stacking": (
        "Объёмная сборка кристаллов повышает вычислительную плотность научных и промышленных систем",
        "Stacked chips increase the computing density of scientific and industrial systems",
    ),
    "solvent_recovery_columns": (
        "Возврат растворителей и тепла снижает энергетические и строительные издержки химического производства",
        "Solvent and heat recovery reduces the energy and construction costs of chemical production",
    ),
    "precision_polymer_blending": (
        "Точное дозирование компонентов повышает выпуск резины действующими и будущими нефтехимическими заводами",
        "Precise ingredient dosing increases rubber output from existing and future petrochemical plants",
    ),
    "synthetic_heat_recovery": (
        "Повторное использование тепла повышает прямой выпуск топлива и снижает расход энергии; количество нефти не меняется",
        "Heat recovery increases direct fuel output and reduces energy demand without changing oil output",
    ),
    "precision_fuel_fractionation": (
        "Точное разделение продуктов синтеза увеличивает выход нефти действующими и будущими заводами",
        "Precise separation of synthesis products increases oil output from existing and future plants",
    ),
    "assault_infantry_formations": (
        "Специализированные батальоны объединяют усиленные стрелковые группы и расчёты тяжёлого оружия для прорыва подготовленных позиций",
        "Specialized battalions combine reinforced rifle teams and heavy weapon crews to breach prepared positions",
    ),
    "assault_group_coordination": (
        "Штурмовые группы отрабатывают смену огневых позиций и взаимное прикрытие при продвижении к противнику",
        "Assault groups rehearse changes of firing position and mutual cover while advancing towards the enemy",
    ),
    "assault_fire_suppression": (
        "Расчёты штурмовых батальонов сосредоточивают огонь на выявленных позициях пехоты, обеспечивая продвижение передовых групп",
        "Assault battalion crews concentrate fire on identified infantry positions to support the advance of their forward groups",
    ),
    "assault_battle_control": (
        "Единые сигналы и подготовленные заместители позволяют штурмовым подразделениям сохранять управление в ближнем бою",
        "Common signals and trained deputies help assault units maintain command and cohesion in close combat",
    ),
    "assault_forward_supply": (
        "Распределение переносимого боезапаса и согласованные пункты пополнения сокращают расход снабжения штурмовых батальонов",
        "Distributed ammunition loads and coordinated replenishment points reduce assault battalion supply consumption",
    ),
    "assault_coordinated_attack": (
        "Огневые расчёты и передовые группы действуют по общему порядку смены целей, сочетая подавление пехоты с непрерывным продвижением",
        "Weapon crews and forward groups follow a shared target sequence, combining infantry suppression with a continuous advance",
    ),
    "amphibious_formation_organization": (
        "Единые нормы распределения транспорта и боевых частей позволяют включать больше дивизий в один план высадки",
        "Common transport and troop allocation standards allow more divisions in a single landing plan",
    ),
    "amphibious_staff_sections": (
        "Специализированные штабные группы обеспечивают подготовку дополнительного плана морского десанта одновременно с остальными",
        "Dedicated staff sections prepare an additional naval invasion plan alongside existing operations",
    ),
    "amphibious_embarkation_schedules": (
        "Согласованные графики прибытия частей и подачи конвоев сокращают подготовку морской десантной операции",
        "Coordinated troop arrival and convoy schedules shorten naval invasion preparation",
    ),
    "amphibious_landing_craft": (
        "Мелкосидящие катера с носовой аппарелью ускоряют доставку штурмовых групп с транспортов на берег",
        "Shallow-draft craft with bow ramps speed the transfer of assault groups from transports to shore",
    ),
    "amphibious_shore_parties": (
        "Береговые команды обозначают выходы с пляжей и направляют прибывающие подразделения, ускоряя высадку",
        "Shore parties mark beach exits and direct arriving units to accelerate landings",
    ),
    "amphibious_loading_rehearsals": (
        "Совместные тренировки войск и экипажей устраняют задержки при сборе и погрузке десанта",
        "Joint troop and crew rehearsals reduce delays during landing-force assembly and embarkation",
    ),
    "amphibious_assault_landing_systems": (
        "Защищённые высадочные средства и отработанные выходы на берег уменьшают боевой штраф при морском вторжении",
        "Protected landing systems and rehearsed beach exits reduce the combat penalty during naval invasions",
    ),
    "amphibious_wave_coordination": (
        "Общий график подхода десантных волн позволяет управлять дополнительным планом и большим числом дивизий в каждой высадке",
        "A shared landing-wave schedule supports an additional plan and more divisions in each landing",
    ),
    "amphibious_integrated_operations": (
        "Единое управление погрузкой, переходом и выходом на берег сокращает подготовку операции и ускоряет высадку войск",
        "Integrated control of embarkation, transit and beach access shortens preparation and speeds troop landings",
    ),
    "kefreyt_shield_special_forces": (
        "Открывает щитовые батальоны и производство первого поколения силовых щитов",
        "Unlocks shield battalions and first-generation power shield production",
    ),
    "shield_assault_drills": (
        "Согласованные действия щитовых групп улучшают оборону, прорыв и организацию щитовиков",
        "Coordinated shield teams improve shield infantry defense, breakthrough and organization",
    ),
    "compact_shield_generators": (
        "Компактные генераторы усиливают защиту и повышают надёжность силовых щитов",
        "Compact generators improve shield protection and reliability",
    ),
    "shield_field_maintenance": (
        "Полевые мастерские снижают расход снабжения и ускоряют восстановление организации щитовиков",
        "Field workshops reduce shield infantry supply consumption and improve organization recovery",
    ),
    "adaptive_power_shields": (
        "Адаптивные генераторы дают дополнительную защиту ценой большего расхода редких сплавов",
        "Adaptive generators provide additional protection at a higher rare-alloy production cost",
    ),
    "synthetic_rubber_plants": (
        "Нефтехимические заводы выпускают синтетическую резину и сопутствующее топливо",
        "Petrochemical plants produce synthetic rubber and fuel as a by-product",
    ),
    "emulsion_polymerization": (
        "Устойчивая эмульсия повышает выход резины при полимеризации",
        "A stable emulsion increases rubber yield during polymerization",
    ),
    "rubber_production_lines": (
        "Дополнительные производственные линии позволяют расширять нефтехимические площадки",
        "Additional production lines allow petrochemical sites to expand",
    ),
    "selective_polymer_catalysts": (
        "Селективные катализаторы уменьшают потери сырья при выпуске резины",
        "Selective catalysts reduce feedstock losses in rubber production",
    ),
    "integrated_rubber_complexes": (
        "Общие коммуникации и переработка побочных продуктов позволяют расширить нефтехимические комплексы",
        "Shared utilities and by-product processing allow larger petrochemical complexes",
    ),
    "closed_cycle_polymerization": (
        "Возврат непрореагировавшего сырья повышает выпуск резины",
        "Recovering unreacted feedstock increases rubber output",
    ),
    "synthetic_oil_synthesis": (
        "Открывает выпуск нефти на нефтехимических заводах. Требует технологию \"Заводы синтетической резины\"; число заводов в регионе расширяется в резиновой ветке",
        "Enables oil output at petrochemical plants. Requires Synthetic Rubber Plants; regional plant capacity is expanded in the rubber branch",
    ),
    "synthetic_feedstock_purification": (
        "Очистка сырья увеличивает прямой выпуск топлива заводами; количество нефти не меняется",
        "Feedstock purification increases direct fuel output from refineries without changing oil output",
    ),
    "catalytic_oil_synthesis": (
        "Улучшенные катализаторы повышают выпуск синтетической нефти",
        "Improved catalysts increase synthetic oil output",
    ),
    "synthetic_fuel_hydrocracking": (
        "Гидрокрекинг повышает прямой выпуск топлива заводами; количество нефти не меняется",
        "Hydrocracking increases direct fuel output from refineries without changing oil output",
    ),
    "closed_cycle_oil_synthesis": (
        "Повторная переработка остаточных фракций повышает выпуск синтетической нефти",
        "Reprocessing residual fractions increases synthetic oil output",
    ),
    "synthetic_fuel_process_control": (
        "Точное управление переработкой повышает прямой выпуск топлива заводами; количество нефти не меняется",
        "Precise process control increases direct fuel output from refineries without changing oil output",
    ),
    "rifling_alignment": (
        "Точная соосность канала ствола уменьшает рассеивание пуль",
        "Precise bore alignment reduces bullet dispersion",
    ),
    "bolt_head_fitting": (
        "Равномерное прилегание боевых упоров стабилизирует запирание затвора",
        "Even contact between locking lugs stabilizes the locked bolt",
    ),
    "chamber_polishing": (
        "Чистовая обработка патронника обеспечивает устойчивую подачу и извлечение гильзы",
        "Finishing the chamber improves feeding and cartridge extraction",
    ),
    "primer_consistency": (
        "Контроль капсюльного состава сокращает число осечек",
        "Primer composition control reduces misfires",
    ),
    "magazine_feed_geometry": (
        "Согласованные углы подачи удерживают патрон на линии досылания",
        "Matched feed angles keep the cartridge aligned with the chamber",
    ),
    "extractor_heat_treatment": (
        "Закалённый зацеп надёжнее извлекает гильзу после интенсивной стрельбы",
        "A hardened extractor claw removes cases reliably after sustained firing",
    ),
    "recoil_spring_tuning": (
        "Подбор жёсткости возвратной пружины стабилизирует цикл перезаряжания",
        "Tuning the recoil spring stabilizes the reloading cycle",
    ),
    "bolt_carrier_guides": (
        "Обработанные направляющие уменьшают перекос затворной рамы",
        "Machined guides reduce bolt carrier misalignment",
    ),
    "trigger_reset_geometry": (
        "Геометрия спускового механизма сокращает ход повторного нажатия",
        "Trigger geometry shortens the reset travel for follow-up shots",
    ),
    "rangefinder_zeroing": (
        "Юстировка совмещает ось дальномера с линией прицеливания",
        "Alignment brings the rangefinder axis onto the aiming line",
    ),
    "sight_mount_repeatability": (
        "Жёсткое крепление сохраняет пристрелку после обслуживания оружия",
        "A rigid mount preserves the sight zero after weapon maintenance",
    ),
    "gas_regulator_sealing": (
        "Уплотнение газового регулятора поддерживает работу автоматики при загрязнении",
        "Sealing the gas regulator keeps the action cycling under fouling",
    ),
    "bore_plating_control": (
        "Контроль толщины покрытия сохраняет геометрию нарезов по всей длине ствола",
        "Plating thickness control preserves rifling geometry along the entire bore",
    ),
    "chamber_erosion_control": (
        "Стойкое покрытие замедляет износ патронника горячими пороховыми газами",
        "A durable coating slows chamber erosion from hot propellant gases",
    ),
    "barrel_heat_treatment": (
        "Термообработка снижает остаточные напряжения и увод ствола при нагреве",
        "Heat treatment reduces residual stress and thermal barrel distortion",
    ),
    "buffered_bolt_travel": (
        "Буфер смягчает удар затворной группы в крайнем заднем положении",
        "A buffer softens the bolt group impact at the rear of its travel",
    ),
    "muzzle_compensation_ports": (
        "Отвод газов через компенсационные окна уменьшает подброс оружия",
        "Venting gas through compensation ports reduces muzzle rise",
    ),
    "treasury_accounting": (
        "Единые реестры налогов и платежей уменьшают потери при сборе доходов и стоимость работы казначейства",
        "Unified tax and payment registers reduce collection losses and treasury administration costs",
    ),
    "public_procurement_standards": (
        "Типовые контракты и проверка смет сокращают бюджетные расходы на строительство и содержание военной промышленности",
        "Standard contracts and cost reviews reduce budget spending on construction and military industry upkeep",
    ),
    "civilian_industrial_accounting": (
        "Учёт выпуска и оборота предприятий повышает доходы от гражданской промышленности и собираемость налогов",
        "Factory output and turnover accounting improve civilian industrial revenue and tax collection",
    ),
    "customs_clearance_networks": (
        "Общий учёт грузов и сырьевых контрактов уменьшает потери торговых доходов и ресурсной ренты",
        "Shared cargo and commodity contract records reduce losses in trade revenue and resource rents",
    ),
    "administrative_digitization": (
        "Обмен документами между ведомствами сокращает административные издержки и расходы на организацию исследований",
        "Interdepartmental document exchange reduces administrative overhead and research programme costs",
    ),
    "production_cost_accounting": (
        "Сопоставление затрат и выпуска военных заводов повышает их бюджетную отдачу и снижает содержание",
        "Comparing military factory costs and output increases their budget contribution and reduces upkeep",
    ),
    "integrated_budget_forecasts": (
        "Согласование строительных заказов с бюджетным планом сокращает издержки управления и финансирования строительства",
        "Coordinating construction orders with the budget plan reduces administrative and construction spending",
    ),
    "automated_treasury_audit": (
        "Автоматическая сверка счетов выявляет недоимки и потери промышленных доходов",
        "Automated account reconciliation identifies unpaid taxes and lost industrial revenue",
    ),
    "precision_material_standards": (
        "Единые допуски по чистоте сырья подготавливают производство электронной компонентной базы и специальных сплавов",
        "Common material purity tolerances prepare the production of electronic components and special alloys",
    ),
    "rare_components_industry": (
        "Чистые сборочные линии выпускают редкие компоненты для датчиков, вычислителей, беспилотников и систем управления",
        "Clean assembly lines produce rare components for sensors, computers, drones and control systems",
    ),
    "rare_alloy_metallurgy": (
        "Контролируемая выплавка редких сплавов обеспечивает жаропрочные детали авиации, тяжёлую броню и артиллерийские узлы",
        "Controlled rare alloy smelting supplies heat-resistant aircraft parts, heavy armour and artillery assemblies",
    ),
    "precision_component_fabrication": (
        "Автоматический контроль сборки увеличивает выпуск завода редких компонентов с 4 до 6 единиц до региональных модификаторов",
        "Automated assembly control increases rare components plant output from 4 to 6 units before regional modifiers",
    ),
    "vacuum_alloy_refining": (
        "Удаление примесей в вакууме увеличивает выпуск завода редких сплавов с 3 до 4 единиц до региональных модификаторов",
        "Vacuum impurity removal increases rare alloy foundry output from 3 to 4 units before regional modifiers",
    ),
    "advanced_material_recycling": (
        "Возврат производственного брака увеличивает выпуск каждого завода ещё на единицу: до 7 компонентов или 5 сплавов, до региональных модификаторов",
        "Recovering production scrap adds one further unit to each plant: 7 components or 5 alloys, before regional modifiers",
    ),
    "distributed_ammunition_carriers": (
        "Небольшие колёсные роботы перевозят ящики с боеприпасами и разгружают расчёты группового оружия",
        "Small wheeled robots carry ammunition crates and reduce the carrying burden on weapon crews",
    ),
    "microdrone_suppression_nets": (
        "Переносные средства радиоэлектронного подавления мешают работе разведывательных микродронов",
        "Portable electronic jammers disrupt reconnaissance microdrones",
    ),
    "remote_weapon_tripods": (
        "Огневая установка на станке управляется с вынесенного пульта; оператор остаётся частью расчёта",
        "A mounted weapon is controlled from a separate console, with its operator remaining part of the crew",
    ),
    "thermal_signature_liners": (
        "Подкладки и накидки уменьшают тепловую заметность бойца; это маскировочное оснащение, а не дополнительная броня",
        "Liners and capes reduce a soldier's thermal visibility; they are concealment equipment rather than additional armour",
    ),
    "reactive_camouflage_textiles": (
        "Маскировочная ткань меняет окраску под окружающую местность и служит основой адаптивного снаряжения",
        "Camouflage fabric changes colour to match the surroundings and forms the basis of adaptive field equipment",
    ),
    "autonomous_casualty_monitors": (
        "Носимые приборы отслеживают состояние раненого и передают показатели медицинскому персоналу",
        "Wearable monitors track a casualty's condition and relay readings to medical personnel",
    ),
    "closed_loop_combat_life_support": (
        "Ранцевая система очищает выдыхаемый воздух и поддерживает дыхание бойца в герметичном защитном снаряжении",
        "A backpack system recycles exhaled air and supports breathing inside sealed protective equipment",
    ),
    "distributed_recon_sensor_caches": (
        "Скрытно размещённые приборы наблюдения передают разведгруппе сведения об обстановке без постоянного присутствия наблюдателя",
        "Concealed observation devices relay information to a reconnaissance team without requiring an observer to remain on site",
    ),
    "augmented_mission_rehearsal": (
        "Тренажёры дополненной реальности позволяют разведгруппам отрабатывать взаимодействие перед выходом на задание",
        "Augmented-reality simulators let reconnaissance teams rehearse coordination before a mission",
    ),
    "augmented_special_forces": (
        "Экзоскелеты для разведывательных и штурмовых групп помогают переносить специальное снаряжение при длительных действиях",
        "Exoskeletons for reconnaissance and assault teams assist with carrying specialist equipment during extended operations",
    ),
    "forward_surgical_cells": (
        "Мобильные хирургические группы оказывают срочную помощь раненым в передовых медицинских пунктах",
        "Mobile surgical teams provide urgent care at forward medical posts",
    ),
    "radiation_patrols": (
        "Противогазы, защитные костюмы и дозиметры позволяют готовить спецназ РХБ-защиты для боя и разведки на заражённой местности",
        "Respirators, protective suits and dosimeters enable CBRN special forces trained to fight and reconnoiter contaminated terrain",
    ),
    "postwar_weapon_standardization": (
        "Восстановленные нарезные станки и измерительный контроль обеспечивают повторяемую геометрию канала ствола, шаг нарезов и соосность патронника",
        "Restored rifling machinery and inspection gauges make bore geometry, twist rate, and chamber alignment repeatable",
    ),
    "refurbished_receivers": (
        "Контроль размеров патронника и зеркального зазора удерживает пороховые газы в казённой части и предотвращает разрыв гильзы",
        "Controlled chamber dimensions and headspace keep propellant gases sealed at the breech and prevent case rupture",
    ),
    "standardized_cartridges": (
        "Гильза, капсюль, метательный заряд и пуля объединяются в взаимозаменяемый патрон единого производственного стандарта",
        "Case, primer, propellant, and projectile are combined into an interchangeable cartridge built to one production standard",
    ),
    "caseless_ammunition_trials": (
        "Форма зерна, стабилизаторы и состав нитроцеллюлозного пороха задают воспроизводимую скорость горения и давление в канале ствола",
        "Grain geometry, stabilizers, and nitrocellulose composition provide a repeatable burn rate and bore-pressure curve",
    ),
    "smart_optics": (
        "Импульсный лазерный дальномер измеряет дистанцию до цели и передаёт её в прицельный канал без ручной оценки",
        "A pulsed laser rangefinder measures target distance and passes it to the sight without manual estimation",
    ),
    "sealed_receiver_assemblies": (
        "Промежуточный патрон сочетает достаточную энергию у цели с импульсом, допускающим управляемый автоматический огонь из индивидуального оружия",
        "An intermediate cartridge balances useful terminal energy with an impulse that permits controllable automatic fire from an individual weapon",
    ),
    "electrothermal_ignition": (
        "Легирование, термообработка и неразрушающий контроль ствольных сталей позволяют безопасно выдерживать повышенное давление и нагрев",
        "Alloying, heat treatment, and non-destructive inspection let barrel steels withstand greater pressure and heat safely",
    ),
    "smart_recoil_compensators": (
        "Часть энергии выстрела приводит механизм экстракции, досылания и взведения, сокращая задержку между прицельными выстрелами",
        "Part of the firing energy powers extraction, feeding, and cocking, reducing the delay between aimed shots",
    ),
    "networked_weapon_sights": (
        "Вычислитель объединяет дальность, параметры патрона, угол места и атмосферные данные в готовую баллистическую поправку",
        "A computer combines range, cartridge data, sight angle, and atmospheric inputs into an immediate ballistic correction",
    ),
    "modular_rifle_kits": (
        "Дозированный отвод пороховых газов приводит затворную группу и обеспечивает устойчивый цикл автоматики при загрязнении и нагреве",
        "Metered propellant gas drives the bolt group and maintains a stable operating cycle under fouling and heat",
    ),
    "biometric_trigger_locks": (
        "Поворотный затвор вводит боевые упоры в зацепление со ствольной коробкой, удерживая давление до безопасного извлечения гильзы",
        "A rotating bolt locks multiple lugs into the receiver and contains pressure until the case can be extracted safely",
    ),
    "integrated_target_designation": (
        "Дневной, малосветовой и тепловизионный каналы сводятся к общей оптической оси и одной рассчитанной точке прицеливания",
        "Daylight, low-light, and thermal channels share one optical axis and one computed point of aim",
    ),
    "programmable_ammunition": (
        "Твёрдое покрытие канала ствола снижает коррозию и эрозию, сохраняя геометрию при интенсивной стрельбе",
        "A hard bore coating limits corrosion and erosion, preserving barrel geometry during sustained fire",
    ),
    "coil_assisted_service_rifles": (
        "Массы подвижных частей, газовый импульс, буфер и геометрия оружия согласуются для уменьшения подброса и рассеивания очереди",
        "Moving mass, gas impulse, buffer, and weapon geometry are tuned together to reduce muzzle rise and burst dispersion",
    ),
    "hybrid_kinetic_energy_carbines": (
        "Полимерный корпус с металлическим донцем уменьшает массу боекомплекта, сохраняя обтюрацию и прочность при экстракции",
        "A polymer body with a metallic case head reduces ammunition mass while preserving obturation and extraction strength",
    ),
    "networked_service_rifles": (
        "Электронный взрыватель получает от прицела дальность или режим подрыва и реализует его после выстрела",
        "An electronic fuze receives range or function data from the sight and executes the programmed effect after firing",
    ),
    "recovered_shaped_charge_cells": (
        "Стеклянная ёмкость с загущённой горючей смесью разбивается о броню и воспламеняет наружное оборудование, воздухозаборники и моторный отсек",
        "A glass vessel filled with thickened fuel breaks against armor and ignites external equipment, air intakes, and the engine deck",
    ),
    "disposable_launcher_standards": (
        "Лёгкая буксируемая пушка на колёсном лафете даёт пехотному расчёту средство борьбы с бронетехникой",
        "A light towed gun on a wheeled carriage gives infantry crews a weapon against armored vehicles",
    ),
    "tandem_penetrator_packages": (
        "Ручная граната с кумулятивной воронкой формирует направленную струю при подрыве на броне, не полагаясь на кинетическую скорость",
        "A hand-thrown grenade with a shaped-charge liner forms a focused jet on armor without relying on impact velocity",
    ),
    "wire_guided_hunter_teams": (
        "Тяжёлое оружие на устойчивом станке усиливает огонь пехоты по лёгкой бронетехнике",
        "A heavy weapon on a stable mount strengthens infantry fire against lightly armored vehicles",
    ),
    "recoilless_overmatch_cells": (
        "Противотанковые мины усиливают оборонительные заграждения и затрудняют продвижение бронетехники",
        "Anti-tank mines reinforce defensive obstacles and hinder armored advances",
    ),
    "fire_and_forget_seekers": (
        "Противотанковая пушка с усиленным станком и прицелом поддерживает пехотные подразделения огнём по бронетехнике",
        "An anti-tank gun with a reinforced mount and sight supports infantry against armored vehicles",
    ),
    "programmable_anti_armor_fuzes": (
        "Компактный ручной гранатомёт позволяет пехотинцу нести собственное противотанковое оружие",
        "A compact shoulder-fired launcher gives individual infantry soldiers a portable anti-tank weapon",
    ),
    "top_attack_profiles": (
        "Переносная пусковая установка с прицелом и противотанковой ракетой усиливает возможности пехотного расчёта",
        "A portable launcher with a sight and anti-tank missile strengthens the infantry crew's anti-armor capability",
    ),
    "loitering_armor_hunters": (
        "Усовершенствованные прицелы и боеприпасы повышают эффективность станковой противотанковой пушки",
        "Improved sights and ammunition increase the effectiveness of mounted anti-tank guns",
    ),
    "cooperative_hunter_cells": (
        "Новые противотанковые ракеты расширяют возможности переносных пусковых установок против защищённых целей",
        "New anti-tank missiles improve the capability of portable launchers against protected targets",
    ),
    "terminal_overmatch_packages": (
        "Ручной противотанковый гранатомёт нового поколения объединяет облегчённый корпус и встроенное прицельное оборудование",
        "A next-generation shoulder-fired anti-tank launcher combines a lightweight body with integrated sighting equipment",
    ),
    "distributed_anti_armor_net": (
        "Противотанковые ракеты нового поколения дополняют перспективные пусковые комплексы пехоты",
        "Next-generation anti-tank missiles equip advanced infantry launcher systems",
    ),
}


BUILDING_DISPLAY_NAMES = {
    "ADISCORD_rare_components_plant": (
        "завод редких компонентов",
        "Rare Components Plant",
    ),
    "ADISCORD_rare_alloy_foundry": ("завод редких сплавов", "Rare Alloy Foundry"),
    "ADISCORD_metallurgical_complex": (
        "металлургический комплекс",
        "Metallurgical Complex",
    ),
    "ADISCORD_electrolysis_complex": ("электролизный комплекс", "Electrolysis Complex"),
    "ADISCORD_strategic_mining_complex": (
        "комплекс стратегической добычи",
        "Strategic Mining Complex",
    ),
    "ADISCORD_thermal_power_complex": (
        "энергогенерирующий комплекс",
        "Power Generation Complex",
    ),
    "synthetic_refinery": (
        "нефтехимический завод",
        "Petrochemical Plant",
    ),
    "fuel_silo": ("топливное хранилище", "Fuel Silo"),
    "anti_air_building": ("региональную ПВО", "State Anti-Air"),
    "radar_station": ("радиолокационную станцию", "Radar Station"),
    "rocket_site": ("ракетную площадку", "Rocket Site"),
    "nuclear_reactor": ("ядерный реактор", "Nuclear Reactor"),
    "nuclear_reactor_heavy_water": ("тяжеловодный реактор", "Heavy-Water Reactor"),
    "commercial_nuclear_reactor": (
        "коммерческий энергореактор",
        "Commercial Power Reactor",
    ),
    "stronghold_network": ("сеть укрепрайонов", "Stronghold Network"),
    "mega_gun_emplacement": ("позицию сверхтяжёлого орудия", "Mega-Gun Emplacement"),
}


TECHNICAL_TECH_DESCRIPTIONS.update(
    {
        "twin_engine_aircraft": (
            "Общий двухмоторный планер открывает производство бомбардировщика и морского торпедоносца. Их вооружение и боевые задачи различаются",
            "A common twin-engine airframe opens production of a bomber and a maritime torpedo aircraft with distinct weapons and missions",
        ),
        "maritime_patrol_aircraft": (
            "Увеличенный запас топлива и поисковое оборудование позволяют новому морскому самолёту патрулировать удалённые коммуникации",
            "Additional fuel and search equipment let the new maritime aircraft patrol distant shipping routes",
        ),
        "pressurized_bombers": (
            "Гермокабина и усиленный планер повышают защищённость нового дальнего бомбардировщика",
            "A pressure cabin and reinforced airframe improve protection on the new long-range bomber",
        ),
        "airborne_homing_torpedoes": (
            "Самонаводящаяся торпеда повышает точность и поражающее действие морской авиации против кораблей",
            "A homing torpedo improves maritime aircraft targeting and damage against ships",
        ),
        "stabilized_bomb_sights": (
            "Стабилизация линии визирования уменьшает рассеивание бомб при ударах по наземным целям",
            "Stabilized sight lines reduce bomb dispersion against ground targets",
        ),
        "long_range_maritime_aircraft": (
            "Новый морской самолёт сочетает большую дальность с усиленным торпедным вооружением и средствами обнаружения кораблей",
            "The new maritime aircraft combines longer range with heavier torpedo armament and improved ship detection",
        ),
        "jet_strike_bombers": (
            "Реактивная силовая установка позволяет новому бомбардировщику быстрее выходить к цели с увеличенной боевой нагрузкой",
            "Jet propulsion lets the new bomber reach its target faster while carrying a heavier weapons load",
        ),
        "integrated_strike_navigation": (
            "Общая навигационная система увеличивает рабочую дальность и точность ударов бомбардировочной и морской авиации",
            "An integrated navigation system improves operational range and strike accuracy for bomber and maritime aircraft",
        ),
    }
)


def technology_description_notes(branch: Branch, index: int, is_ru: bool) -> list[str]:
    notes: list[str] = []
    tech = branch.techs[index]
    if any(effect.startswith("global_building_slots_factor") for effect in tech.effects):
        notes.append(
            "Увеличивает общую вместимость регионов относительно их базового числа строительных ячеек. Итог зависит от размера региона и предела общих ячеек."
            if is_ru else
            "Expands shared state building capacity relative to each state's base slots. The result depends on state size and the shared-slot limit."
        )
    if branch.key == "reconstruction" and xor_siblings(branch, index):
        notes.append(
            "Общая линия освоения территорий доступна при любом выборе. Плотная застройка даёт дополнительные места, скоростное восстановление ускоряет стройку и ремонт."
            if is_ru else
            "The common land-development line remains available after either choice. Dense development adds capacity; rapid reconstruction improves construction and repairs."
        )
    if branch.key == "computing" and xor_siblings(branch, index):
        notes.append(
            "Научные центры ускоряют исследования; прикладные вычисления повышают выпуск и эффективность производства и снабжения."
            if is_ru else
            "Scientific centres accelerate research; applied computing improves production, efficiency and supply."
        )
    if branch.key == "power_shields":
        if index == 0:
            notes.append(
                "Базовая технология выдаётся завершённым спецпроектом \"Силовые щиты\". Кефрейт, Партия и Шабрат также получают завершённый проект по своим фокусам."
                if is_ru else
                "The Power Shields special project grants this base technology. Kefreyt, the Party and Shabrat can also complete the project through their national focuses."
            )
        notes.append(
            "Щитовые батальоны требуют 20 силовых щитов; производство расходует редкие компоненты и редкие сплавы."
            if is_ru else
            "Shield battalions require 20 power shields; production consumes rare components and rare alloys."
        )
    if branch.key == "squad_weapons":
        notes.append(
            "Подготовка расчётов: ополчение 20%, территориалы и штабная пехота 35%, щитовики 75%, остальные оснащённые части 100% эффекта."
            if is_ru else
            "Crew training: militia 20%, territorial and HQ infantry 35%, shield troops 75%, other equipped formations 100% of the effect."
        )
    if branch.key in {"synthetic_rubber", "synthetic_oil"}:
        tech_id = branch.techs[index].id
        for _, level in ENABLE_BUILDINGS.get(tech_id, ()):
            notes.append(
                f"Нефтехимические заводы: до {level} в регионе."
                if is_ru
                else f"Petrochemical plants: up to {level} per state."
            )
        for _, resource, amount in BUILDING_RESOURCE_UPGRADES.get(tech_id, ()):
            frame = {"rubber": 3, "oil": 1}[resource]
            notes.append(
                f"§G+{amount}§! £resources_strip|{frame} с каждого действующего и будущего завода."
                if is_ru
                else f"§G+{amount}§! £resources_strip|{frame} from each existing and future plant."
            )
        return notes
    if branch.key == "carrier_hulls" and "_hull_" in branch.techs[index].key:
        notes.append(
            "Палубные истребители и торпедоносцы исследуются в отдельных ответвлениях. Самолёты нужно произвести на военных заводах и назначить в палубные авиакрылья."
            if is_ru else
            "Carrier fighters and torpedo bombers are researched in separate branches. Produce aircraft in military factories and assign them to carrier air wings."
        )
    if branch.key in {"small_arms", "assault_rifles"} and index % 4:
        model = branch.techs[index - index % 4]
        equipment = ENABLE_EQUIPMENT[model.id][0]
        model_name = LAND_EQUIPMENT_LOCALISATION[equipment][2 if is_ru else 3]
        notes.append(
            f"Модификация {index % 4}/3 для {model_name}; обязательная ступень перед следующей моделью."
            if is_ru
            else f"Modification {index % 4}/3 for {model_name}; required before the next model."
        )
    siblings = xor_siblings(branch, index)
    if siblings:
        names_by_id = {
            tech.id: (tech.ru if is_ru else tech.en) for tech in branch.techs
        }
        alternatives = ", ".join(names_by_id[sibling] for sibling in siblings)
        if XOR_KIND_BY_BRANCH[branch.key] == "temporary":
            notes.append(
                f"Взаимоисключающий проект с вариантом: {alternatives}; общая линия продолжится после любого выбора."
                if is_ru
                else f"Mutually exclusive with: {alternatives}; the common line continues after either choice."
            )
        else:
            notes.append(
                f"Постоянный выбор специализации: альтернатива \"{alternatives}\" останется закрыта до конца магистрали."
                if is_ru
                else f"Permanent specialization choice: {alternatives} remains locked for the rest of the branch."
            )
    for effect in effects_for(branch, index):
        energy_match = re.fullmatch(r"factory_energy_consumption = ([0-9.]+)", effect)
        if energy_match and float(energy_match.group(1)) > 0:
            percent = f"{float(energy_match.group(1)) * 100:g}"
            notes.append(
                f"Энергетическая цена: потребление энергии фабриками +{percent}%."
                if is_ru
                else f"Energy price: factory energy consumption +{percent}%."
            )
    if len(BRANCH_GRAPHS[branch.key].dependencies[index]) >= 2:
        notes.append(
            "Требует завершения всех входящих программ и объединяет их результаты."
            if is_ru
            else "Requires every incoming programme and integrates their results."
        )
    buildings = ENABLE_BUILDINGS.get(branch.techs[index].id, ())
    if buildings:
        names = [
            BUILDING_DISPLAY_NAMES[building][0 if is_ru else 1]
            for building, _ in buildings
        ]
        notes.append(
            f"Открывает строительство: {', '.join(names)}."
            if is_ru
            else f"Unlocks construction: {', '.join(names)}."
        )
    if branch.techs[index].id in BUILDING_RESOURCE_UPGRADES:
        notes.append(
            "Повышает выпуск уже построенных и будущих ресурсных комплексов."
            if is_ru
            else "Raises the output of both existing and future resource complexes."
        )
    return notes


POST_2160_RESEARCH_COST_BY_PROFILE = {
    "construction": 1.20,
    "production": 1.30,
    "resources": 1.35,
    "finance": 1.20,
    "administration": 1.20,
    "civil": 1.15,
    "power": 1.40,
    "signals": 1.35,
    "computing": 1.40,
    "infantry": 1.30,
    "squad": 1.35,
    "protection": 1.20,
    "special_forces": 1.25,
    "support": 1.25,
    "logistics": 1.25,
    "rail": 1.30,
    "artillery": 1.35,
    "anti_tank": 1.35,
    "anti_air": 1.35,
    "recon_armor": 1.40,
    "combat_armor": 1.45,
    "heavy_armor": 1.55,
    "fighter": 1.45,
    "air_support": 1.40,
    "strategic_air": 1.55,
    "naval_support": 1.35,
    "surface_fleet": 1.50,
    "subsurface": 1.40,
}


AI_RESEARCH_WEIGHT_BY_PROFILE = {
    "construction": 30,
    "production": 30,
    "resources": 28,
    "finance": 18,
    "administration": 20,
    "civil": 18,
    "power": 20,
    "signals": 24,
    "computing": 24,
    "infantry": 32,
    "squad": 30,
    "protection": 24,
    "special_forces": 14,
    "support": 26,
    "logistics": 24,
    "rail": 18,
    "artillery": 26,
    "anti_tank": 20,
    "anti_air": 20,
    "recon_armor": 12,
    "combat_armor": 12,
    "heavy_armor": 8,
    "fighter": 14,
    "air_support": 12,
    "strategic_air": 8,
    "naval_support": 10,
    "surface_fleet": 8,
    "subsurface": 9,
}


def research_cost_for(
    branch: Branch,
    index: int,
    dependencies: tuple[str, ...],
    xor: tuple[str, ...],
) -> float:
    """Price recovered baseline cheaply and live choices by commitment.

    The campaign grants ordinary pre-2160 knowledge on startup, so its listed
    cost is mainly a historical fallback. Live programmes are intentionally
    closer to the 1.5-2.5 range used by dense total conversions: a two-slot
    state can develop several coherent arms, but cannot casually finish every
    specialisation before the late game.
    """

    tech = branch.techs[index]
    year = branch.years[index]
    if tech.key in NAVAL_UPGRADE_ORIGINS and branch.key in NAVAL_HULL_BRANCH_KEYS:
        origin, origin_index = NAVAL_UPGRADE_ORIGINS[tech.key]
        return research_cost_for(origin, origin_index, dependencies, xor)
    if branch.profile.startswith("forbidden_"):
        return 2.60 + index * (0.18 if len(branch.techs) > 3 else 0.35)
    if branch.key in {"small_arms", "assault_rifles"} and tech.id not in ENABLE_EQUIPMENT:
        # Intermediate upgrades need room for saved research and focus bonuses.
        return 1.20
    if year <= 2158:
        return 0.55

    progress = max(0.0, min(1.0, (year - 2160) / 20))
    cost = POST_2160_RESEARCH_COST_BY_PROFILE[branch.profile] + progress * 0.55
    if xor:
        cost = max(cost, 1.75)
    if (
        tech.id in ENABLE_EQUIPMENT
        or tech.id in ENABLE_SUBUNITS
        or tech.id in ENABLE_BUILDINGS
    ):
        cost = max(cost, 2.05)
    if tech.id in BUILDING_RESOURCE_UPGRADES:
        cost = max(cost, 1.75)
    if len(dependencies) >= 2:
        cost = max(cost, 2.40)
    if index == len(branch.techs) - 1 and year >= 2180:
        cost = max(cost, 2.55)
    return cost


def ai_will_do_for(branch: Branch, index: int) -> tuple[str, ...]:
    """Give AI research a role and capacity-aware score."""

    tech = branch.techs[index]
    year = branch.years[index]
    if branch.profile.startswith("forbidden_"):
        return ("factor = 1",)

    base = AI_RESEARCH_WEIGHT_BY_PROFILE[branch.profile]
    if year <= 2160:
        base *= 1.25
    if tech.id in ENABLE_EQUIPMENT or tech.id in ENABLE_SUBUNITS:
        base *= 1.35
    if tech.id in ENABLE_BUILDINGS:
        base *= 1.20

    entries = [f"factor = {n(base)}"]
    profile = branch.profile
    if branch.key in {"synthetic_rubber", "synthetic_oil"}:
        entries.extend(
            (
                "modifier = { factor = 0.30 ADISCORD_economy_ai_is_crisis = yes }",
                "modifier = { factor = 0.25 num_of_civilian_factories < 5 }",
            )
        )
    elif profile in {"construction", "resources", "civil", "rail"} and not (
        branch.key == "reconstruction" and year > 2160
    ):
        entries.append(
            "modifier = { factor = 1.35 ADISCORD_economy_ai_is_crisis = yes }"
        )
    if profile in {"production", "finance", "administration", "computing"}:
        entries.append(
            "modifier = { factor = 1.20 ADISCORD_economy_ai_is_healthy = yes }"
        )
    if branch.key == "public_finance":
        entries.append(
            "modifier = { factor = 1.40 ADISCORD_economy_ai_is_crisis = yes }"
        )
    if profile in {
        "infantry",
        "squad",
        "protection",
        "support",
        "logistics",
        "artillery",
        "anti_tank",
        "anti_air",
        "recon_armor",
        "combat_armor",
        "heavy_armor",
        "fighter",
        "air_support",
        "strategic_air",
    }:
        entries.append("modifier = { factor = 1.25 has_war = yes }")
        entries.append(
            "modifier = { factor = 0.30 ADISCORD_economy_ai_is_crisis = yes }"
        )
    if profile in {"recon_armor", "combat_armor", "heavy_armor"}:
        entries.append("modifier = { factor = 0.15 num_of_military_factories < 8 }")
        entries.append(
            "modifier = { factor = 1.45 ADISCORD_economy_ai_can_fund_advanced_forces = yes }"
        )
    if profile in {"fighter", "air_support", "strategic_air"}:
        entries.append("modifier = { factor = 0.20 num_of_military_factories < 8 }")
        entries.append(
            "modifier = { factor = 1.35 ADISCORD_economy_ai_can_fund_advanced_forces = yes }"
        )
    if profile in {"naval_support", "surface_fleet", "subsurface"}:
        entries.append("modifier = { factor = 0.05 num_of_naval_factories < 1 }")
        entries.append("modifier = { factor = 1.35 num_of_naval_factories > 3 }")
    if branch.key in {"battleship_hulls", "carrier_hulls"}:
        entries.append("modifier = { factor = 0.10 num_of_naval_factories < 8 }")
        entries.append("modifier = { factor = 0.25 ADISCORD_economy_ai_is_crisis = yes }")
    if branch.key == "power":
        entries.append("modifier = { factor = 1.75 energy_ratio < 0.80 }")
    if branch.key in {"signals", "computing"} and year <= 2167:
        entries.append("modifier = { factor = 1.20 has_war = yes }")

    lane = BRANCH_GRAPHS[branch.key].lanes[index]
    if branch.key == "industry_organization" and lane == 0:
        entries.append("modifier = { factor = 1.50 energy_ratio > 0.94 }")
        entries.append(
            "modifier = { factor = 1.25 ADISCORD_economy_ai_is_healthy = yes }"
        )
        entries.append("modifier = { factor = 0.35 has_war = yes }")
    elif branch.key == "industry_organization" and lane == 2:
        entries.append("modifier = { factor = 1.60 energy_ratio < 0.80 }")
        entries.append("modifier = { factor = 1.35 has_war = yes }")
        entries.append(
            "modifier = { factor = 1.35 ADISCORD_economy_ai_is_crisis = yes }"
        )

    if branch.key == "computing" and lane == 2:
        entries.append("modifier = { factor = 1.35 energy_ratio > 0.94 }")
        entries.append("modifier = { factor = 0.25 energy_ratio < 0.80 }")
    elif branch.key == "computing" and tech.key in {
        "scientific_computing_centres", "parallel_numerical_solvers",
        "photonic_research_processors", "quantum_material_simulation",
    }:
        entries.append("modifier = { factor = 1.25 energy_ratio < 0.80 }")

    if branch.key == "production" and lane in {0, 2}:
        if lane == 0:
            entries.append(
                "modifier = { factor = 1.20 ADISCORD_economy_ai_is_stressed = yes }"
            )
        else:
            entries.append(
                "modifier = { factor = 1.20 ADISCORD_economy_ai_is_healthy = yes }"
            )

    if tech.key in {
        "compact_industrial_zoning", "industrial_investment_planning",
        "baseload_reactor_dispatch", "offensive_jamming_cells",
    }:
        entries.append(
            "modifier = { factor = 1.25 ADISCORD_economy_ai_is_healthy = yes }"
        )
    elif tech.key in {
        "rapid_reconstruction_standards", "industrial_service_budgeting",
        "islandable_microgrids", "passive_drone_detection_meshes",
    }:
        entries.append(
            "modifier = { factor = 1.25 ADISCORD_economy_ai_is_stressed = yes }"
        )
        entries.append("modifier = { factor = 1.25 has_war = yes }")
    return tuple(entries)


def render_leader_training_effect(tech: Tech) -> list[str]:
    """Award each selected general once, then release the temporary selection."""

    training = LEADER_TRAINING.get(tech.key)
    if training is None:
        return []
    attribute, count = training
    flag = f"ADISCORD_training_pick_{attribute}"
    lines = [
        "\t\tshow_effect_as_desc = yes",
        "\t\ton_research_complete = {",
        f"\t\t\tcustom_effect_tooltip = {tech.id}_leader_effect_tt",
        "\t\t\thidden_effect = {",
    ]
    for _ in range(count):
        lines.extend(
            (
                "\t\t\t\trandom_army_leader = {",
                f"\t\t\t\t\tlimit = {{ NOT = {{ has_unit_leader_flag = {flag} }} }}",
                f"\t\t\t\t\tset_unit_leader_flag = {flag}",
                f"\t\t\t\t\tadd_{attribute} = 1",
                "\t\t\t\t}",
            )
        )
    lines.extend(
        (
            "\t\t\t\tevery_army_leader = {",
            f"\t\t\t\t\tlimit = {{ has_unit_leader_flag = {flag} }}",
            f"\t\t\t\t\tclr_unit_leader_flag = {flag}",
            "\t\t\t\t}",
            "\t\t\t}",
            "\t\t}",
        )
    )
    return lines


def folder_grid_format(folder: str) -> str:
    """Return the Clausewitz grid direction matching the folder time axis."""

    return "LEFT" if folder in HORIZONTAL_FOLDERS else "UP"


def technology_year_occurrence(branch: Branch, index: int) -> int:
    """Parallel infantry and naval nodes share dates; dependent steps do not."""
    if branch.key not in NAVAL_HULL_BRANCH_KEYS and "infantry_folder" not in branch.folders:
        return branch.years[:index].count(branch.years[index])
    graph = BRANCH_GRAPHS[branch.key]
    depths = [0] * len(branch.techs)
    for source, targets in enumerate(graph.successors):
        for target in targets:
            if branch.years[source] == branch.years[target]:
                depths[target] = max(depths[target], depths[source] + 1)
    return depths[index]


def horizontal_year_columns(folder: str) -> tuple[tuple[int, int], ...]:
    """Reserve columns for years and successive same-year research steps."""
    timeline_folder = "naval_folder" if folder == "mtgnavalfolder" else folder
    branches = [branch for branch in BRANCHES if timeline_folder in branch.folders]
    if folder in {"naval_folder", "mtgnavalfolder"}:
        years = sorted({year for branch in branches for year in branch.years})
    else:
        years = YEARS
    return tuple(
        (year, occurrence)
        for year in years
        for occurrence in range(max([
            1,
            *(technology_year_occurrence(branch, i) + 1
              for branch in branches
              for i, candidate in enumerate(branch.years) if candidate == year),
        ]))
    )


def chronological_grid_slot(
    year: int, *, horizontal: bool, folder: str | None = None, occurrence: int = 0
) -> int:
    """Map a research year to the single slot used by nodes and year labels."""

    slot = YEAR_TO_Y[year]
    if horizontal and folder is not None:
        slot = horizontal_year_columns(folder).index((year, occurrence))
    multiplier = (
        HORIZONTAL_YEAR_SLOT_MULTIPLIER if horizontal else VERTICAL_YEAR_SLOT_MULTIPLIER
    )
    return slot * multiplier


def horizontal_visual_slots(branch: Branch) -> tuple[int, ...]:
    """Keep every node under its actual research year, including fork arms."""

    folder = next(folder for folder in branch.folders if folder in HORIZONTAL_FOLDERS)
    slots = tuple(
        chronological_grid_slot(
            year,
            horizontal=True,
            folder=folder,
            occurrence=technology_year_occurrence(branch, index),
        )
        for index, year in enumerate(branch.years)
    )
    for source, targets in enumerate(BRANCH_GRAPHS[branch.key].successors):
        for target in targets:
            if slots[source] >= slots[target]:
                raise ValueError(
                    f"{branch.key}: non-chronological visual edge {source}->{target}"
                )
    return slots


def technology_time_slot(branch: Branch, index: int) -> int:
    """Return the chronological slot of a node regardless of tab orientation."""

    if HORIZONTAL_FOLDERS.intersection(branch.folders):
        return horizontal_visual_slots(branch)[index]
    years = sorted({
        year
        for member in vertical_tree_branches(branch)
        for year in member.years
    })
    return years.index(branch.years[index]) * VERTICAL_YEAR_SLOT_MULTIPLIER


def technology_grid_position(branch: Branch, index: int) -> tuple[int, int]:
    """Return signed cross-axis slots and chronological time slots.

    Native technology grids centre cross-axis slot zero inside the gridbox.
    ``UP`` spends position.x across and position.y down; ``LEFT`` swaps those
    screen axes. Both therefore need signed lane offsets around the midpoint
    of the occupied lanes, not offsets measured from the box's upper-left.
    """

    graph = BRANCH_GRAPHS[branch.key]
    multiplier = (
        HORIZONTAL_LANE_SLOT_MULTIPLIER
        if HORIZONTAL_FOLDERS.intersection(branch.folders)
        else LANE_SLOT_MULTIPLIER
    )
    if branch.file in CIVIL_TECHNOLOGY_FILES:
        multiplier = CIVIL_LANE_SLOT_MULTIPLIER
    doubled_slot = (
        2 * graph.lanes[index] - min(graph.lanes) - max(graph.lanes)
    ) * multiplier
    if not HORIZONTAL_FOLDERS.intersection(branch.folders):
        doubled_slot += (
            2 * vertical_branch_offset(branch)
            + vertical_branch_span(branch)
            - vertical_tree_span(branch)
        )
    if doubled_slot % 2:
        raise ValueError(f"{branch.key}: lane spacing cannot centre integer grid slots")
    return doubled_slot // 2, technology_time_slot(branch, index)


def render_research_completion_effects(tech: Tech) -> list[str]:
    """Emit the one post-path ``on_research_complete`` block for a technology.

    Resource upgrades, research rewards and budget invalidation share one
    callback because the engine keeps only one ``on_research_complete``.
    The block follows paths so research-balance checks distinguish immediate
    rewards from persistent numeric modifiers.
    """

    building_upgrades = BUILDING_RESOURCE_UPGRADES.get(tech.id, ())
    payoff = RESEARCH_PAYOFFS.get(tech.id)
    branch, index = TECH_POSITION_BY_ID[tech.id]
    railway_bonuses = [
        effect.replace("railway_gun =", "railway_gun_equipment =", 1)
        for effect in effects_for(branch, index)
        if effect.startswith("railway_gun =")
    ]
    budget_effect = any(
        effect.startswith("ADISCORD_economy_") for effect in effects_for(branch, index)
    )
    if (
        not building_upgrades
        and payoff is None
        and not budget_effect
        and not railway_bonuses
    ):
        return []
    if LEADER_TRAINING.get(tech.key) is not None:
        raise ValueError(
            f"{tech.id} already spends its on_research_complete on leader training"
        )
    lines = ["\t\ton_research_complete = {"]
    for bonus in railway_bonuses:
        lines.extend(
            render_payload(
                f"add_equipment_bonus = {{ name = {tech.id} bonus = {{ {bonus} }} }}", 3
            )
        )
    if budget_effect:
        lines.append("\t\t\thidden_effect = { ADISCORD_economy_mark_dirty = yes }")
    for building, resource, amount in building_upgrades:
        lines.extend(
            (
                "\t\t\tmodify_building_resources = {",
                f"\t\t\t\tbuilding = {building}",
                f"\t\t\t\tresource = {resource}",
                f"\t\t\t\tamount = {amount}",
                "\t\t\t}",
            )
        )
    if payoff is not None:
        category, bonus, uses = payoff
        branch, _ = TECH_POSITION_BY_ID[tech.id]
        declared = CATEGORY_BY_PROFILE[branch.profile].split()
        if category not in declared:
            raise ValueError(
                f"{tech.id} cannot grant {category} research; its branch declares "
                f"{declared}"
            )
        lines.extend(
            (
                "\t\t\tadd_tech_bonus = {",
                f"\t\t\t\tbonus = {n(bonus)}",
                f"\t\t\t\tuses = {uses}",
                f"\t\t\t\tcategory = {category}",
                "\t\t\t}",
            )
        )
    lines.extend(("\t\t}", "\t\tshow_effect_as_desc = yes"))
    return lines


def render_payload(payload: str, indent: int) -> list[str]:
    """Expand nested effect and AI clauses without combining statements."""
    tokens = re.findall(r'"[^"]*"|[{}]|[^\s{}]+', payload)
    lines: list[str] = []
    position = 0
    while position < len(tokens):
        token = tokens[position]
        if token == "}":
            indent -= 1
            lines.append("\t" * indent + "}")
            position += 1
        elif position + 2 < len(tokens) and tokens[position + 1] in {
            "=",
            ">",
            "<",
            ">=",
            "<=",
        }:
            value = tokens[position + 2]
            lines.append("\t" * indent + " ".join(tokens[position : position + 3]))
            if value == "{":
                indent += 1
            position += 3
        else:
            lines.append("\t" * indent + token)
            position += 1
    return lines


BRANCH_CONTINUATIONS = {"assault_rifles": "small_arms"}


def technology_tree_root(branch: Branch) -> str:
    owner = BRANCH_BY_KEY[BRANCH_CONTINUATIONS.get(branch.key, vertical_tree_key(branch))]
    return owner.techs[0].id


def technology_successors(branch: Branch, index: int) -> tuple[str, ...]:
    targets = tuple(
        branch.techs[target].id for target in BRANCH_GRAPHS[branch.key].successors[index]
    )
    targets += tuple(
        BRANCH_BY_KEY[child].techs[0].id
        for child, (parent, source) in CIVIL_TREE_ATTACHMENTS.items()
        if parent == branch.key and source == branch.techs[index].key
    )
    if index == len(branch.techs) - 1:
        targets += tuple(
            BRANCH_BY_KEY[child].techs[0].id
            for child, parent in BRANCH_CONTINUATIONS.items()
            if parent == branch.key
        )
    return targets


def research_allow_for(branch: Branch, index: int) -> tuple[str, ...]:
    explicit = ALLOW.get(branch.techs[index].id)
    if explicit:
        return explicit
    if SPECIAL_TECHNOLOGY_FOLDER in branch.folders:
        if branch.key == "power_shields" and index > 0:
            return (f"has_tech = {branch.techs[0].id}",)
        # New special programmes remain closed until they have an authored unlock.
        return (
            "custom_trigger_tooltip = { "
            "tooltip = ADISCORD_special_technology_locked_tt always = no }",
        )
    return ()


def render_technology(branch: Branch, index: int) -> str:
    tech = branch.techs[index]
    year = branch.years[index]
    graph = BRANCH_GRAPHS[branch.key]
    lines = [f"\t{tech.id} = {{"]
    if branch.key in {"production", "computing"}:
        lines.append("\t\tspecial_project_specialization = { specialization_land }")
    allow = research_allow_for(branch, index)
    if allow:
        lines.append("\t\tallow = {")
        for entry in allow:
            lines.extend(render_payload(entry, 3))
        lines.append("\t\t}")
    for effect in effects_for(branch, index):
        if effect.startswith("railway_gun ="):
            continue
        lines.extend(render_payload(effect, 2))
    if tech.id == "ADISCORD_tech_restored_dockyards":
        # Native transport permission is separate from the invasion plan and
        # division caps, which retain their engine defaults.
        lines.append("\t\tnaval_invasion_capacity = 100")
    lines.extend(render_leader_training_effect(tech))
    for target in technology_successors(branch, index):
        lines.extend(
            (
                "\t\tpath = {",
                f"\t\t\tleads_to_tech = {target}",
                "\t\t\tresearch_cost_coeff = 1",
                "\t\t}",
            )
        )
    extra_dependencies = EXTRA_TECH_DEPENDENCIES.get(tech.id, ())
    dependency_indices = graph.dependencies[index]
    if extra_dependencies:
        # Once a dependency block exists, list the visual path parents too so
        # a cross-row requirement cannot accidentally turn the local path into
        # an OR prerequisite.
        dependency_indices = tuple(
            source
            for source, targets in enumerate(graph.successors)
            if index in targets
        )
    dependencies = tuple(branch.techs[parent].id for parent in dependency_indices)
    dependencies += extra_dependencies
    if dependencies:
        lines.append("\t\tdependencies = {")
        lines.extend(f"\t\t\t{parent} = 1" for parent in dependencies)
        lines.append("\t\t}")
    xor = xor_siblings(branch, index)
    if xor:
        lines.append("\t\tXOR = {")
        lines.extend(f"\t\t\t{sibling}" for sibling in xor)
        lines.append("\t\t}")
    equipment = ENABLE_EQUIPMENT.get(tech.id)
    if equipment:
        lines.append(f"\t\tenable_equipments = {{ {' '.join(equipment)} }}")
    subunits = ENABLE_SUBUNITS.get(tech.id)
    if subunits:
        lines.append(f"\t\tenable_subunits = {{ {' '.join(subunits)} }}")
    for building, level in ENABLE_BUILDINGS.get(tech.id, ()):
        lines.extend(
            (
                "\t\tenable_building = {",
                f"\t\t\tbuilding = {building}",
                f"\t\t\tlevel = {level}",
                "\t\t}",
            )
        )
    lines.extend(render_research_completion_effects(tech))
    research_cost = research_cost_for(branch, index, dependencies, xor)
    lines.extend(
        (
            f"\t\tresearch_cost = {n(research_cost)}",
            f"\t\tstart_year = {year}",
        )
    )
    position_x, position_y = technology_grid_position(branch, index)
    for folder in sorted(branch.folders):
        lines.extend(
            (
                "\t\tfolder = {",
                f"\t\t\tname = {folder}",
                f"\t\t\tposition = {{ x = {position_x} y = {position_y} }}",
                "\t\t}",
            )
        )
    lines.append("\t\tai_will_do = {")
    for entry in ai_will_do_for(branch, index):
        lines.extend(render_payload(entry, 3))
    lines.extend(
        (
            "\t\t}",
            f"\t\tcategories = {{ {CATEGORY_BY_PROFILE[branch.profile]} }}",
            "\t}",
        )
    )
    return "\n".join(lines)


def technology_file_outputs() -> dict[Path, str]:
    technology_dir = ROOT / "common" / "technologies"
    files = sorted({branch.file for branch in BRANCHES})
    outputs = {}
    for filename in files:
        blocks = [
            render_technology(branch, index)
            for branch in BRANCHES
            if branch.file == filename
            for index in range(len(branch.techs))
        ]
        content = "technologies = {\n" + "\n\n".join(blocks) + "\n}\n"
        outputs[technology_dir / filename] = content
    return outputs


def write_technology_files() -> None:
    for path, content in technology_file_outputs().items():
        path.write_text(content, encoding="utf-8")


def technology_folder_tags() -> str:
    return (
        "# Generated by tools/builders/build_adiscord_technology_system.py\n"
        "technology_folders = {\n"
        f"\t{SPECIAL_TECHNOLOGY_FOLDER} = {{\n"
        "\t\tledger = army\n"
        "\t}\n"
        "}\n"
    )


def write_technology_folder_tags() -> None:
    path = ROOT / "common/technology_tags/ADISCORD_technology.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(technology_folder_tags(), encoding="utf-8")


def render_starting_technology_effect() -> str:
    """Render the common baseline, profile packages and explicit tag dispatch."""

    lines = [
        "# Generated by tools/build_adiscord_technology_system.py.",
        "# The campaign begins in 2160.  Common roots and bounded country profiles",
        "# preserve technological differences instead of granting every pre-2160 node.",
        "",
    ]
    for profile, technology_ids in STARTING_TECH_PROFILES.items():
        lines.extend(
            (
                f"ADISCORD_grant_technology_profile_{profile} = {{",
                "\tset_technology = {",
            )
        )
        lines.extend(f"\t\t{tech_id} = 1" for tech_id in technology_ids)
        lines.extend(
            (
                "\t\tpopup = no",
                "\t}",
            )
        )
        # Startup calculates the first budget after granting profiles. Later
        # grants must invalidate it without reinitializing an existing country.
        if any(
            effect.startswith("ADISCORD_economy_")
            for tech_id in technology_ids
            for effect in effects_for(*TECH_POSITION_BY_ID[tech_id])
        ):
            lines.extend(
                (
                    "\thidden_effect = {",
                    "\t\tif = {",
                    "\t\t\tlimit = { has_variable = ADISCORD_economy_initialized }",
                    "\t\t\tADISCORD_economy_mark_dirty = yes",
                    "\t\t}",
                    "\t}",
                )
            )
        lines.extend(
            (
                "}",
                "",
            )
        )

    lines.extend(
        (
            "# The legacy effect ID is retained for collapse scripts and old callers,",
            "# but now contains only the minimum common base and transition stockpiles.",
            "ADISCORD_grant_2150_technology_baseline = {",
            "\tADISCORD_grant_technology_profile_common = yes",
            "\t# Existing line battalions now require squad fire-support kits.  Give",
            "\t# every country a modest transition reserve while AI production catches up.",
            "\tif = {",
            "\t\tlimit = { num_of_military_factories > 6 }",
            "\t\tadd_equipment_to_stockpile = {",
            "\t\t\ttype = ADISCORD_squad_weapons_equipment_0",
            "\t\t\tamount = 400",
            "\t\t\tproducer = ROOT",
            "\t\t}",
            "\t\tadd_equipment_to_stockpile = {",
            "\t\t\ttype = support_equipment_1",
            "\t\t\tamount = 300",
            "\t\t\tproducer = ROOT",
            "\t\t}",
            "\t}",
            "\telse = {",
            "\t\tadd_equipment_to_stockpile = {",
            "\t\t\ttype = ADISCORD_squad_weapons_equipment_0",
            "\t\t\tamount = 200",
            "\t\t\tproducer = ROOT",
            "\t\t}",
            "\t\tadd_equipment_to_stockpile = {",
            "\t\t\ttype = support_equipment_1",
            "\t\t\tamount = 150",
            "\t\t\tproducer = ROOT",
            "\t\t}",
            "\t}",
            "}",
            "",
            "ADISCORD_grant_starting_technology_profile = {",
            "\tADISCORD_grant_2150_technology_baseline = yes",
        )
    )
    for tag, profiles in sorted(STARTING_COUNTRY_TECH_PROFILES.items()):
        lines.extend(
            (
                "\tif = {",
                f"\t\tlimit = {{ tag = {tag} }}",
            )
        )
        if profiles:
            lines.extend(
                f"\t\tADISCORD_grant_technology_profile_{profile} = yes"
                for profile in profiles
            )
        else:
            lines.extend(
                (
                    "\t\t# Intentional common-only assignment.",
                    "\t\tADISCORD_grant_technology_profile_common = yes",
                )
            )
        lines.append("\t}")
    lines.extend(
        (
            "\tif = {",
            "\t\tlimit = { date > 2183.1.1 }",
            "\t\tADISCORD_grant_technology_profile_late_2183 = yes",
            "\t}",
            "}",
            "",
        )
    )
    return "\n".join(lines)


def write_starting_technology_effect() -> None:
    path = (
        ROOT
        / "common"
        / "scripted_effects"
        / "ADISCORD_technology_baseline_effects.txt"
    )
    path.write_text(render_starting_technology_effect(), encoding="utf-8")


def collect_starting_country_profile_evidence() -> dict[str, dict[str, object]]:
    evidence = {
        tag: {
            "states": 0,
            "civilian_factories": 0,
            "military_factories": 0,
            "dockyards": 0,
            "air_bases": 0,
            "power_sites": 0,
            "infrastructure_levels": 0,
            "research_slots": 0,
            "convoys": 0,
            "oob_divisions": 0,
            "starting_doctrines": [],
        }
        for tag in STARTING_COUNTRY_TECH_PROFILES
    }
    building_fields = {
        "industrial_complex": "civilian_factories",
        "arms_factory": "military_factories",
        "dockyard": "dockyards",
        "air_base": "air_bases",
        "infrastructure": "infrastructure_levels",
        "nuclear_reactor": "power_sites",
        "commercial_nuclear_reactor": "power_sites",
        "ADISCORD_thermal_power_complex": "power_sites",
    }
    for state_path in (ROOT / "history" / "states").glob("*.txt"):
        state_text = state_path.read_text(encoding="utf-8-sig")
        owner_match = re.search(r"(?m)^\s*owner\s*=\s*([A-Z0-9]{3})\s*$", state_text)
        if not owner_match or owner_match.group(1) not in evidence:
            continue
        row = evidence[owner_match.group(1)]
        row["states"] += 1
        for building, field in building_fields.items():
            row[field] += sum(
                int(value)
                for value in re.findall(
                    rf"(?m)^\s*{re.escape(building)}\s*=\s*(\d+)",
                    state_text,
                )
            )
    for tag, row in evidence.items():
        country_paths = sorted((ROOT / "history" / "countries").glob(f"{tag} - *.txt"))
        if country_paths:
            country_text = country_paths[0].read_text(encoding="utf-8-sig")
            slots = re.search(r"\bset_research_slots\s*=\s*(\d+)", country_text)
            convoys = re.search(r"\bset_convoys\s*=\s*(\d+)", country_text)
            row["research_slots"] = int(slots.group(1)) if slots else 0
            row["convoys"] = int(convoys.group(1)) if convoys else 0
            row["starting_doctrines"] = re.findall(
                r"\bset_grand_doctrine\s*=\s*([A-Za-z0-9_]+)",
                country_text,
            )
        history_paths = sorted((ROOT / "history" / "countries").glob(f"{tag} - *.txt"))
        history_text = (
            history_paths[0].read_text(encoding="utf-8-sig") if history_paths else ""
        )
        oob_match = re.search(r'(?m)^\s*oob\s*=\s*"([^"\n]+)"', history_text)
        oob_name = oob_match.group(1) if oob_match else tag
        oob_path = ROOT / "history" / "units" / f"{oob_name}.txt"
        if oob_path.exists():
            oob_text = oob_path.read_text(encoding="utf-8-sig")
            row["oob_divisions"] = len(
                re.findall(r"(?m)^\s*division\s*=\s*\{", oob_text)
            )
    return evidence


def render_starting_technology_profile_manifest() -> str:
    countries = {}
    evidence = collect_starting_country_profile_evidence()
    common = set(STARTING_TECH_PROFILES["common"])
    for tag, profiles in sorted(STARTING_COUNTRY_TECH_PROFILES.items()):
        technologies = set(common)
        for profile in profiles:
            technologies.update(STARTING_TECH_PROFILES[profile])
        countries[tag] = {
            "profiles": ["common", *profiles],
            "common_only": not profiles,
            "rationale": STARTING_COUNTRY_TECH_PROFILE_RATIONALE[tag],
            "evidence": evidence[tag],
            "technologies_2160": sorted(technologies),
        }
    payload = {
        "schema": 1,
        "campaign_start": "2160.1.1",
        "active_country_count": len(countries),
        "profiles": {
            profile: {
                "seeds": list(STARTING_TECH_PROFILE_SEEDS[profile]),
                "technologies": list(STARTING_TECH_PROFILES[profile]),
            }
            for profile in STARTING_TECH_PROFILES
        },
        "countries": countries,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_starting_technology_profile_manifest() -> None:
    path = ROOT / "tools/data/adiscord_starting_technology_profiles.json"
    path.write_text(render_starting_technology_profile_manifest(), encoding="utf-8")


CUSTOM_TECH_TEXTURES = {
    "kefreyt_shield_special_forces": "gfx/interface/technologies/ADISCORD_power_shield_equipment.dds",
    "compact_shield_generators": "gfx/interface/technologies/ADISCORD_power_shield_equipment.dds",
    "adaptive_power_shields": "gfx/interface/technologies/ADISCORD_power_shield_equipment.dds",
    "recovered_medium_chassis": "gfx/interface/technologies/armor/ADISCORD_restored_main_battle_tank.dds",
    "recovered_shaped_charge_cells": "gfx/interface/technologies/ADISCORD_antitank_01_incendiary_bottle.dds",
    "disposable_launcher_standards": "gfx/interface/technologies/ADISCORD_antitank_02_satchel_charge.dds",
    "tandem_penetrator_packages": "gfx/interface/technologies/ADISCORD_antitank_03_shaped_charge_grenade.dds",
    "wire_guided_hunter_teams": "gfx/interface/technologies/ADISCORD_antitank_04_antitank_rifle.dds",
    "top_attack_profiles": "gfx/interface/technologies/ADISCORD_antitank_08_rocket_launcher.dds",
    "loitering_armor_hunters": "gfx/interface/technologies/ADISCORD_antitank_09_top_attack_seeker.dds",
}


def write_naval_hull_cards() -> None:
    """Fit native ship art into wide equipment nodes without fallback badges."""
    artwork_sources = {**NAVAL_HULL_ART, "ADISCORD_naval_missile_systems": "guided_missile_1"}
    for icon, source_icon in artwork_sources.items():
        size = (176, 72) if icon in NAVAL_HULL_ART else (72, 72)
        source = BASE_GAME / "gfx/interface/technologies" / f"{source_icon}.dds"
        target = ROOT / "gfx/interface/technologies" / f"{icon}.dds"
        with Image.open(source) as original:
            artwork = original.convert("RGBA")
            bounds = artwork.getchannel("A").getbbox()
            if bounds is None:
                raise ValueError(f"Empty naval artwork: {source}")
            artwork = artwork.crop(bounds)
            artwork.thumbnail((size[0] - 4, size[1] - 8), Image.Resampling.LANCZOS)
            card = Image.new("RGBA", size)
            card.alpha_composite(artwork, ((size[0] - artwork.width) // 2, (size[1] - artwork.height) // 2))
            card.save(target, format="DDS")


COUNTRY_AIRCRAFT_CARD_FAMILIES = {
    "VAL": "VAL",
    "NOD": "party",
    "STP": "party",
    "STS": "STS",
    "SRP": "STS",
}

# Ready-to-use cards can cover one role without overriding the other role's art or names.
COUNTRY_AIRCRAFT_ROLE_TEXTURES = {
    "RUS": {
        "fighter": tuple(
            f"gfx/interface/technologies/ADISCORD_aircraft_RUS_{tier}.png"
            for tier in range(1, 4)
        ),
        "cas": tuple(
            f"gfx/interface/technologies/ADISCORD_aircraft_cas_RUS_{tier}.png"
            for tier in range(1, 4)
        ),
    },
}

# Rank by the research unlock, not by the older year suffix in an equipment ID.
# The supplied third card also represents every subsequent production model.
AIRCRAFT_CARD_TIERS = {
    "ADISCORD_fighter_airframe_2163": 1,
    "ADISCORD_fighter_airframe_2161": 2,
    "ADISCORD_fighter_airframe_2166": 3,
    "ADISCORD_interceptor_airframe_2183": 3,
    "ADISCORD_fighter_airframe_2170": 3,
    "ADISCORD_fighter_airframe_2175": 3,
    "ADISCORD_cas_airframe_2170": 1,
    "ADISCORD_vtol_airframe_2170": 2,
    "ADISCORD_attack_airframe_2163": 3,
    "ADISCORD_drone_airframe_2183": 3,
    "ADISCORD_attack_airframe_2170": 3,
    "ADISCORD_attack_airframe_2175": 3,
}
AIRCRAFT_CARDS_BEGIN = "\t# BEGIN ADISCORD country aircraft cards\n"
AIRCRAFT_CARDS_END = "\t# END ADISCORD country aircraft cards\n"

# The production card's second line uses the generic equipment name even
# when its model name and picture have country-specific overrides.
AIRCRAFT_TYPE_LOCALISATION = {
    "ADISCORD_fighter_airframe_2163": (
        "Винтовой истребитель", "Propeller Fighter",
        "Восстановленный истребитель с поршневым двигателем и воздушным винтом.",
        "A restored fighter powered by a piston engine and propeller.",
    ),
    "ADISCORD_cas_airframe_2170": (
        "Винтовой штурмовик", "Propeller Attack Aircraft",
        "Поршневой самолёт непосредственной поддержки наземных войск.",
        "A piston-engine aircraft for close support of ground forces.",
    ),
    "ADISCORD_vtol_airframe_2170": (
        "Реактивный штурмовик", "Jet Attack Aircraft",
        "Реактивный самолёт непосредственной поддержки наземных войск.",
        "A jet-powered aircraft for close support of ground forces.",
    ),
}


def country_aircraft_names(language: str) -> dict[str, str]:
    is_ru = language == "russian"
    families = {
        "VAL": ("В", "V", (("Сокол", "Falcon"), ("Беркут", "Eagle"), ("Грифон", "Griffin"))),
        "party": ("Н", "N", (("Ворон", "Raven"), ("Кречет", "Gyrfalcon"), ("Фантом", "Phantom"))),
        "STS": ("С", "S", (("Чайка", "Gull"), ("Стриж", "Swift"), ("Сапсан", "Peregrine"))),
    }
    unlocks = {
        item: (tech.id, branch.years[index])
        for branch in BRANCHES
        for index, tech in enumerate(branch.techs)
        for item in ENABLE_EQUIPMENT.get(tech.id, ())
        if item in AIRCRAFT_CARD_TIERS
    }
    names = {}
    for tag, family in COUNTRY_AIRCRAFT_CARD_FAMILIES.items():
        prefix_ru, prefix_en, titles = families[family]
        for equipment, tier in AIRCRAFT_CARD_TIERS.items():
            tech, year = unlocks[equipment]
            if "interceptor" in equipment:
                role_ru, role_en = "П", "I"
                kind_ru, kind_en = "Перехватчик нового поколения", "Next-generation interceptor"
            elif "fighter" in equipment:
                role_ru, role_en = "И", "F"
                kind_ru = ("Винтовой истребитель", "Реактивный истребитель", "Истребитель нового поколения")[tier - 1]
                kind_en = ("Propeller fighter", "Jet fighter", "Next-generation fighter")[tier - 1]
            elif "drone" in equipment:
                role_ru, role_en = "Б", "U"
                kind_ru, kind_en = "Беспилотный ударный самолёт", "Unmanned strike aircraft"
            else:
                role_ru, role_en = "Ш", "A"
                kind_ru = ("Винтовой штурмовик", "Реактивный штурмовик", "Ударный самолёт нового поколения")[tier - 1]
                kind_en = ("Propeller attack aircraft", "Jet attack aircraft", "Next-generation strike aircraft")[tier - 1]
            if is_ru:
                short = f"{prefix_ru}{role_ru}-{year % 100:02d}"
                name = f"{short} \"{titles[tier - 1][0]}\""
                description = f"{kind_ru} {name}."
            else:
                short = f"{prefix_en}{role_en}-{year % 100:02d}"
                name = f"{short} “{titles[tier - 1][1]}”"
                description = f"{kind_en} {name}."
            names[f"{tag}_{tech}"] = name
            names[f"{tag}_{tech}_desc"] = description
            names[f"{tag}_{equipment}"] = name
            names[f"{tag}_{equipment}_short"] = short
            names[f"{tag}_{equipment}_desc"] = description
    return names


def country_aircraft_gfx_entries() -> str:
    entries = [AIRCRAFT_CARDS_BEGIN]

    def add(sprite: str, texture: str) -> None:
        entries.append(
            "\tSpriteType = {\n"
            f'\t\tname = "{sprite}"\n'
            f'\t\ttextureFile = "{texture}"\n'
            "\t}\n\n"
        )

    for equipment in AIRCRAFT_CARD_TIERS:
        kind = "fighter" if "fighter" in equipment or "interceptor" in equipment else "CAS"
        add(
            f"GFX_{equipment}_medium",
            f"gfx/interface/archetypes/archetype_{kind}_equipment.dds",
        )
    cards = {
        equipment: (tier, "fighter" if "fighter" in equipment or "interceptor" in equipment else "cas")
        for equipment, tier in AIRCRAFT_CARD_TIERS.items()
    }
    cards["archetype_fighter_equipment"] = (1, "fighter")
    cards["archetype_CAS_equipment"] = (1, "cas")
    for tech_id, equipment in ENABLE_EQUIPMENT.items():
        unlocked_cards = {cards[item] for item in equipment if item in AIRCRAFT_CARD_TIERS}
        if unlocked_cards:
            if len(unlocked_cards) != 1:
                raise ValueError(f"Aircraft unlock spans several card roles or tiers: {tech_id}")
            cards[tech_id] = unlocked_cards.pop()
    for tag, family in COUNTRY_AIRCRAFT_CARD_FAMILIES.items():
        for key, (tier, role) in cards.items():
            prefix = "aircraft_cas" if role == "cas" else "aircraft"
            add(
                f"GFX_{tag}_{key}_medium",
                f"gfx/interface/technologies/ADISCORD_{prefix}_{family}_{tier}.dds",
            )
    for tag, roles in COUNTRY_AIRCRAFT_ROLE_TEXTURES.items():
        for key, (tier, role) in cards.items():
            if role in roles:
                add(f"GFX_{tag}_{key}_medium", roles[role][tier - 1])
    entries.append(AIRCRAFT_CARDS_END)
    return "".join(entries)


def aircraft_icon_outputs(role: str = "all") -> dict[Path, bytes]:
    outputs = {}
    roles = ("fighter", "cas") if role == "all" else (role,)
    for selected_role in roles:
        if selected_role not in {"fighter", "cas"}:
            raise ValueError(f"Unknown aircraft card role: {selected_role}")
        prefix = "aircraft_cas" if selected_role == "cas" else "aircraft"
        directory = "country_cas" if selected_role == "cas" else "country_vehicles"
        for family in sorted(set(COUNTRY_AIRCRAFT_CARD_FAMILIES.values())):
            for tier in range(1, 4):
                source = ROOT / "tools/assets/source" / directory / f"{prefix}_{family}_{tier}.png"
                with Image.open(source) as image:
                    if image.mode != "RGBA" or image.size != (176, 72):
                        raise ValueError(f"Aircraft card must be 176x72 RGBA: {source}")
                    pixels = image.tobytes()
                    stream = BytesIO()
                    image.save(stream, format="DDS")
                content = stream.getvalue()
                with Image.open(BytesIO(content)) as decoded:
                    if decoded.convert("RGBA").tobytes() != pixels:
                        raise ValueError(f"DDS encoding altered aircraft artwork: {source}")
                target = ROOT / "gfx/interface/technologies" / f"ADISCORD_{prefix}_{family}_{tier}.dds"
                outputs[target] = content
    outputs[ROOT / "interface/ADISCORD_technologies.gfx"] = aircraft_gfx_output()
    return outputs


def aircraft_gfx_output() -> bytes:
    """Refresh sprite bindings independently of optional authoring PNG sources."""
    path = ROOT / "interface/ADISCORD_technologies.gfx"
    original = path.read_bytes()
    text = path.read_text(encoding="utf-8")
    if AIRCRAFT_CARDS_BEGIN in text:
        start = text.index(AIRCRAFT_CARDS_BEGIN)
        end = text.index(AIRCRAFT_CARDS_END, start) + len(AIRCRAFT_CARDS_END)
        text = text[:start] + country_aircraft_gfx_entries() + text[end:]
    else:
        last_brace = text.rfind("}")
        text = text[:last_brace] + country_aircraft_gfx_entries() + text[last_brace:]
    if b"\r\n" in original:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


APC_CARDS_BEGIN = "\t# BEGIN ADISCORD country APC cards\n"
APC_CARDS_END = "\t# END ADISCORD country APC cards\n"
COUNTRY_APC_CARD_TEXTURES = {
    "VAL": "gfx/interface/technologies/ADISCORD_apc_VAL.png",
    "STP": "gfx/interface/technologies/ADISCORD_apc_STP.png",
    "STS": "gfx/interface/technologies/ADISCORD_apc_STS.png",
    "NAM": "gfx/interface/technologies/ADISCORD_apc_NAM.png",
    "NOD": "gfx/interface/technologies/ADISCORD_apc_NOD.png",
}
APC_CARD_EQUIPMENT = (
    "ADISCORD_armored_carrier_2163",
    "ADISCORD_ifv_2170",
    "ADISCORD_networked_ifv_2183",
)


def country_apc_gfx_entries() -> str:
    keys = ["ADISCORD_armored_carrier_archetype", *APC_CARD_EQUIPMENT]
    keys.extend(
        tech_id for tech_id, equipment in ENABLE_EQUIPMENT.items()
        if any(item in APC_CARD_EQUIPMENT for item in equipment)
    )
    entries = [APC_CARDS_BEGIN]
    for tag, texture in COUNTRY_APC_CARD_TEXTURES.items():
        for key in keys:
            entries.append(
                "\tSpriteType = {\n"
                f'\t\tname = "GFX_{tag}_{key}_medium"\n'
                f'\t\ttextureFile = "{texture}"\n'
                "\t}\n\n"
            )
    entries.append(APC_CARDS_END)
    return "".join(entries)


def apc_gfx_output() -> bytes:
    """Refresh APC bindings without changing supplied runtime artwork."""
    path = ROOT / "interface/ADISCORD_technologies.gfx"
    original = path.read_bytes()
    text = path.read_text(encoding="utf-8")
    if APC_CARDS_BEGIN in text:
        start = text.index(APC_CARDS_BEGIN)
        end = text.index(APC_CARDS_END, start) + len(APC_CARDS_END)
    else:
        start = end = text.rfind("}")
    text = text[:start] + country_apc_gfx_entries() + text[end:]
    if b"\r\n" in original:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


UNIFORM_CARDS_BEGIN = "\t# BEGIN ADISCORD country uniform cards\n"
UNIFORM_CARDS_END = "\t# END ADISCORD country uniform cards\n"


def country_uniform_gfx_entries() -> str:
    entries = [UNIFORM_CARDS_BEGIN]
    early_families = {
        "ADISCORD_tech_postwar_weapon_standardization": "01_reclaimed_arsenal",
        "ADISCORD_tech_refurbished_receivers": "02_recovered_service_rifle",
    }
    for tech, icon in EQUIPMENT_UNLOCK_ICONS.items():
        if not icon.startswith("ADISCORD_weapon_"):
            continue
        family = early_families.get(tech, "03_standardized_battle_rifle")
        entries.append(
            "\tSpriteType = {\n"
            f'\t\tname = "GFX_STS_{tech}_medium"\n'
            f'\t\ttextureFile = "gfx/interface/technologies/ADISCORD_STS_weapon_{family}.dds"\n'
            "\t}\n"
        )
        for key in (tech, *ENABLE_EQUIPMENT[tech]):
            entries.append(
                "\tSpriteType = {\n"
                f'\t\tname = "GFX_RUS_{key}_medium"\n'
                f'\t\ttextureFile = "gfx/interface/technologies/ADISCORD_RUS_weapon_{family}.dds"\n'
                "\t}\n"
            )
    entries.append(UNIFORM_CARDS_END)
    return "".join(entries)


def with_country_uniform_gfx(text: str) -> str:
    if UNIFORM_CARDS_BEGIN in text:
        start = text.index(UNIFORM_CARDS_BEGIN)
        end = text.index(UNIFORM_CARDS_END, start) + len(UNIFORM_CARDS_END)
        text = text[:start] + text[end:]
    last_brace = text.rfind("}")
    return text[:last_brace] + country_uniform_gfx_entries() + text[last_brace:]


def infantry_card_outputs() -> dict[Path, bytes]:
    """Preserve supplied card pixels and update only their research/production routes."""
    outputs = {}
    names = (
        "ADISCORD_RUS_weapon_01_reclaimed_arsenal",
        "ADISCORD_RUS_weapon_02_recovered_service_rifle",
        "ADISCORD_RUS_weapon_03_standardized_battle_rifle",
        "ADISCORD_power_shield_equipment",
    )
    for name in names:
        source = ROOT / "tools/assets/source/country_uniforms" / f"{name}.png"
        with Image.open(source) as image:
            if image.mode != "RGBA" or image.size != (176, 72):
                raise ValueError(f"Infantry card must be 176x72 RGBA: {source}")
            pixels = image.tobytes()
            stream = BytesIO()
            image.save(stream, format="DDS")
        content = stream.getvalue()
        with Image.open(BytesIO(content)) as decoded:
            if decoded.convert("RGBA").tobytes() != pixels:
                raise ValueError(f"DDS encoding altered infantry artwork: {source}")
        outputs[ROOT / "gfx/interface/technologies" / f"{name}.dds"] = content
    shield_texture = CUSTOM_TECH_TEXTURES["kefreyt_shield_special_forces"]
    routes = {
        ROOT / "interface/ADISCORD_technologies.gfx": {
            f"GFX_{tech}_medium": shield_texture
            for tech in ENABLE_EQUIPMENT
            if tech.removeprefix("ADISCORD_tech_") in {
                "kefreyt_shield_special_forces", "compact_shield_generators",
                "adaptive_power_shields",
            }
        },
        ROOT / "interface/ADISCORD_subuniticons.gfx": {
            "GFX_ADISCORD_power_shield_equipment_medium": shield_texture,
        },
    }
    for path, sprites in routes.items():
        original = path.read_bytes()
        text = path.read_text(encoding="utf-8")
        if path.name == "ADISCORD_technologies.gfx":
            text = with_country_uniform_gfx(text)
        for sprite, texture in sprites.items():
            pattern = rf'\t[Ss]priteType = \{{\s*name = "{re.escape(sprite)}"[^{{}}]*\}}'
            replacement = (
                "\tSpriteType = {\n"
                f'\t\tname = "{sprite}"\n'
                f'\t\ttextureFile = "{texture}"\n'
                "\t}"
            )
            text, count = re.subn(pattern, lambda match: replacement, text)
            if count != 1:
                raise ValueError(f"Expected one infantry sprite {sprite}, found {count}")
        if b"\r\n" in original:
            text = text.replace("\n", "\r\n")
        outputs[path] = text.encode("utf-8")
    return outputs


def country_uniform_names(language: str) -> dict[str, str]:
    is_ru = language == "russian"
    models = (
        ("КП-50", "\"Дозор\"", "IK-50", "“Watch”"),
        ("КП-55", "\"Рубеж\"", "IK-55", "“Frontier”"),
        ("КП-62", "\"Бастион\"", "IK-62", "“Bastion”"),
    )
    names = {}
    for tech, icon in EQUIPMENT_UNLOCK_ICONS.items():
        if not icon.startswith("ADISCORD_weapon_"):
            continue
        generation = int(icon.split("_")[2])
        model = models[min(generation, 3) - 1]
        short, title = model[:2] if is_ru else model[2:]
        modification = ""
        if generation > 3:
            modification = (" М" if is_ru else " M") + str(generation - 3)
        name = f"{short} {title}{modification}"
        equipment = ENABLE_EQUIPMENT[tech][0]
        names[f"STS_{tech}"] = name
        names[f"STS_{equipment}"] = name
        names[f"STS_{equipment}_short"] = short + modification
    return names


def escape_localisation_value(value: str) -> str:
    value = value.translate(str.maketrans({char: '"' for char in "\u00ab\u00bb“”„"}))
    value = re.sub(r"(\b[A-Z][A-Z0-9]*-\d+\s+)'([^'\r\n]+)'", r'\1"\2"', value)
    return re.sub(r'(?<!\\)"', r'\\"', value)


def localisation_entry(key: str, value: str) -> str:
    return f' {key}:0 "{escape_localisation_value(value)}"'


def normalise_localisation_quotes(text: str) -> str:
    return re.sub(
        r'(?m)^([ \t]*[\w]+:\d*[ \t]*")((?:[^"\\\r\n]|\\.)*)(")',
        lambda match: match[1] + escape_localisation_value(match[2]) + match[3],
        text,
    )


def with_country_names(data: bytes, section: str, names: dict[str, str]) -> bytes:
    text = data.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    begin = f" # BEGIN {section} generated by build_adiscord_technology_system.py" + newline
    end = f" # END {section}" + newline
    entries = newline.join(localisation_entry(key, value) for key, value in names.items())
    block = begin + entries + newline + end
    if begin in text:
        start = text.index(begin)
        stop = text.index(end, start) + len(end)
        return (text[:start] + block + text[stop:]).encode("utf-8-sig")
    if not text.endswith(newline):
        text += newline
    return (text + block).encode("utf-8-sig")


def country_uniform_localisation_outputs() -> dict[Path, bytes]:
    outputs = {}
    for language in ("russian", "english"):
        path = ROOT / f"localisation/{language}/ADISCORD_STP_l_{language}.yml"
        outputs[path] = with_country_names(
            path.read_bytes(), "STS uniform names", country_uniform_names(language)
        )
    return outputs


def country_equipment_localisation_outputs() -> dict[Path, bytes]:
    outputs = country_uniform_localisation_outputs()
    updated_keys = {
        tech.id + suffix
        for branch in BRANCHES if branch.key in {"squad_weapons", "anti_tank_infantry"}
        for tech in branch.techs
        for suffix in ("", "_desc")
    }
    updated_keys.update(
        equipment + suffix
        for equipment in AIRCRAFT_TYPE_LOCALISATION
        for suffix in ("", "_short", "_desc")
    )
    for language in ("russian", "english"):
        names = country_aircraft_names(language)
        for country_file in (True, False):
            stem = "ADISCORD_STP" if country_file else "ADISCORD_technology_doctrine"
            path = ROOT / f"localisation/{language}/{stem}_l_{language}.yml"
            selected = {
                key: value for key, value in names.items()
                if (key.split("_", 1)[0] in {"STP", "STS", "SRP"}) == country_file
            }
            outputs[path] = with_country_names(
                outputs.get(path, path.read_bytes()), "Country aircraft names", selected
            )
            if not country_file:
                text = outputs[path].decode("utf-8-sig")
                entries = {
                    line.split(":", 1)[0].strip(): line
                    for line in generated_localisation(language)
                    if line.split(":", 1)[0].strip() in updated_keys
                }
                seen = set()

                def replace_entry(match: re.Match[str]) -> str:
                    key = match[1]
                    if key not in entries:
                        return match[0]
                    if key in seen:
                        raise ValueError(f"Duplicate technology localisation: {key}")
                    seen.add(key)
                    return entries[key]

                text = re.sub(
                    r'(?m)^[ \t]*([\w]+):\d*[ \t]*"(?:[^"\\\r\n]|\\.)*"',
                    replace_entry, text,
                )
                missing = entries.keys() - seen
                if missing:
                    raise ValueError(f"Missing technology localisation: {sorted(missing)}")
                # Preserved equipment names share the same display convention.
                text = normalise_localisation_quotes(text)
                outputs[path] = text.encode("utf-8-sig")
    return outputs


def write_gfx() -> None:
    entries = [
        "\tframeAnimatedSpriteType = {\n"
        f'\t\tname = "GFX_technology_{SPECIAL_TECHNOLOGY_FOLDER}_small_currently_researching_item_bg"\n'
        '\t\ttextureFile = "gfx/interface/techtree/tech_doctrine_researching_anim_strip.dds"\n'
        "\t\tnoOfFrames = 9\n"
        '\t\tloadType = "INGAME"\n'
        "\t\ttransparencecheck = yes\n"
        "\t\tanimation_rate_fps = 15\n"
        "\t\tlooping = yes\n"
        "\t\tplay_on_show = yes\n"
        "\t\tpause_on_loop = 0.0\n"
        "\t}\n"
    ]
    for branch in BRANCHES:
        for index, tech in enumerate(branch.techs):
            icon = icon_for_technology(branch, index)
            custom_texture = CUSTOM_TECH_TEXTURES.get(tech.key)
            variants = [(f"GFX_{tech.id}_medium", custom_texture or icon)]
            if (
                not custom_texture
                and icon.startswith("ADISCORD_weapon_")
                and tech.id in ENABLE_EQUIPMENT
            ):
                variants.extend(
                    (
                        f"GFX_{tag}_{tech.id}_medium",
                        icon.replace("ADISCORD_", f"ADISCORD_{tag}_", 1),
                    )
                    for tag in REGIONAL_SERVICE_ICON_TAGS
                )
            for sprite, texture in variants:
                texture_file = (
                    texture
                    if texture.startswith("gfx/")
                    else f"gfx/interface/technologies/{texture}.dds"
                )
                if tech.key in {
                    "electrothermal_ignition",
                    "biometric_trigger_locks",
                    "recovered_medium_chassis",
                }:
                    source = ROOT / texture_file
                    target = source.with_name(source.stem + "_card.dds")
                    with Image.open(source) as original:
                        card = original.convert("RGBA")
                        card.thumbnail((64, 64), Image.Resampling.LANCZOS)
                        card.save(target, format="DDS")
                    texture_file = target.relative_to(ROOT).as_posix()
                entries.append(
                    "\tSpriteType = {\n"
                    f"\t\tname = \"{sprite}\"\n"
                    f"\t\ttextureFile = \"{texture_file}\"\n"
                    + (
                        "\t\tnoOfFrames = 2\n"
                        if custom_texture and custom_texture.startswith("gfx/interface/counters/")
                        else ""
                    )
                    + "\t}\n"
                )
    content = (
        "spriteTypes = {\n" + "\n".join(entries) + technology_tree_gfx_entries()
        + country_aircraft_gfx_entries() + country_uniform_gfx_entries()
        + country_apc_gfx_entries() + "}\n"
    )
    (ROOT / "interface" / "ADISCORD_technologies.gfx").write_text(
        content, encoding="utf-8"
    )


def weapon_category_gfx_output(branch_key: str | None = None) -> str:
    """Regenerate category sprites without rebuilding unrelated UI declarations."""
    path = ROOT / "interface" / "ADISCORD_technologies.gfx"
    text = path.read_text(encoding="utf-8")
    icons = INFANTRY_COMPACT_ICONS if branch_key == "night_combat" else WEAPON_CATEGORY_ICONS
    if branch_key == "protection":
        icons = PROTECTION_TECH_ICONS
    for branch in BRANCHES:
        if branch_key is not None and branch.key != branch_key:
            continue
        for tech in branch.techs:
            if tech.key not in icons:
                continue
            sprite = f"GFX_{tech.id}_medium"
            pattern = rf'\tSpriteType = \{{\s*name = "{re.escape(sprite)}"[^{{}}]*\}}'
            texture = (
                f"gfx/interface/technologies/{icons[tech.key]}.dds"
            )
            if tech.key in {"electrothermal_ignition", "biometric_trigger_locks"}:
                texture = texture.removesuffix(".dds") + "_card.dds"
            replacement = (
                "\tSpriteType = {\n"
                f'\t\tname = "{sprite}"\n'
                f'\t\ttextureFile = "{texture}"\n' + "\t}"
            )
            text, count = re.subn(pattern, lambda match: replacement, text)
            if count != 1:
                raise ValueError(
                    f"Expected one category sprite {sprite}, found {count}"
                )
    return text


ACCESS_REQUIREMENT_LOCALISATION = {
    SPECIAL_TECHNOLOGY_FOLDER: ("Особые технологии", "Special Technologies"),
    f"{SPECIAL_TECHNOLOGY_FOLDER}_desc": (
        "Закрытые программы исследований. Доступ открывается специальными проектами, национальными фокусами или событиями.",
        "Restricted research programmes. Access is granted by special projects, national focuses or events.",
    ),
    "ADISCORD_special_technology_locked_tt": (
        "Доступ к этой особой технологии пока не открыт",
        "Access to this special technology has not been unlocked",
    ),
    "ADISCORD_forbidden_legacy_access": (
        "Доступ к запретному наследию",
        "Forbidden legacy access",
    ),
    "ADISCORD_legacy_research_authorized": (
        "Разрешено исследование наследия",
        "Legacy research authorized",
    ),
    "ADISCORD_legacy_site_secured": (
        "Защищённый объект старого мира",
        "Secured old-world site",
    ),
    "ADISCORD_forbidden_relic_complex": (
        "Комплекс с запретными реликтами",
        "Forbidden relic complex",
    ),
    "ADISCORD_black_grid_protocols_authorized": (
        "Разрешены протоколы чёрной энергосети",
        "Black-grid protocols authorized",
    ),
    "ADISCORD_black_grid_node": (
        "Узел чёрной энергосети",
        "Black-grid node",
    ),
}


# Names for equipment generations shown in production and logistics screens.
# These are generated alongside the technology tree so newly unlocked series
# cannot silently fall back to raw technical IDs.
LAND_EQUIPMENT_LOCALISATION = {
    "ADISCORD_combat_platform_2150": (
        "Восстановленный основной танк", "Restored Main Battle Tank",
        "Основной танк I", "Main Battle Tank I",
        "Ремонтопригодный танк с обычной пушкой. Доступная основа танковых батальонов, уступающая новым моделям в защите и огневой мощи.",
        "A maintainable tank with a conventional gun. An affordable foundation for tank battalions, with less protection and firepower than later models.",
    ),
    "ADISCORD_heavy_combat_platform_2158": (
        "Тяжёлый танк прорыва", "Heavy Breakthrough Tank",
        "Тяжёлый танк I", "Heavy Tank I",
        "Медленный танк с усиленной бронёй для прорыва подготовленной обороны. Требует больше стали, топлива и производственных мощностей, чем основной танк.",
        "A slow, heavily armored tank for breaking prepared defenses. Requires more steel, fuel and industrial capacity than a main battle tank.",
    ),
    "ADISCORD_power_shield_equipment": ("Силовые щиты", "Power Shields", "Силовые щиты", "Power Shields", "Силовой щит для щитового спецназа; требует редких компонентов и редких сплавов.", "Power shields for shield infantry; require rare components and rare alloys."),
    "ADISCORD_power_shield_equipment_1": ("Силовые щиты 2163", "Power Shields 2163", "Силовые щиты", "Power Shields", "Силовой щит для щитового спецназа; требует редких компонентов и редких сплавов.", "Power shields for shield infantry; require rare components and rare alloys."),
    "ADISCORD_power_shield_equipment_2": ("Силовые щиты 2169", "Power Shields 2169", "Силовые щиты", "Power Shields", "Силовой щит для щитового спецназа; требует редких компонентов и редких сплавов.", "Power shields for shield infantry; require rare components and rare alloys."),
    "ADISCORD_power_shield_equipment_3": ("Силовые щиты 2175", "Power Shields 2175", "Силовые щиты", "Power Shields", "Силовой щит для щитового спецназа; требует редких компонентов и редких сплавов.", "Power shields for shield infantry; require rare components and rare alloys."),
    "motorized_equipment": (
        "Грузовые автомобили",
        "Cargo Trucks",
        "Грузовики",
        "Trucks",
        "Автомобили для доставки боеприпасов, продовольствия и топлива от узлов снабжения к войскам.",
        "Vehicles carrying ammunition, food and fuel from supply hubs to the troops.",
    ),
    "motorized_equipment_1": (
        "Восстановленные грузовики",
        "Rebuilt Cargo Trucks",
        "Грузовики I",
        "Trucks I",
        "Простые грузовики с восстановленными двигателями и ходовой частью. Обеспечивают моторизацию узлов снабжения.",
        "Simple trucks with rebuilt engines and running gear. Used to motorize supply hubs.",
    ),
    "infantry_equipment_0": (
        "ОВ-40 \"Лом\"",
        "SR-40 “Crowbar”",
        "ОВ-40",
        "SR-40",
        "Восстановленный комплект винтовок с заново нарезанными стволами, едиными калибрами и измерительным контролем.",
        "A recovered rifle set rebuilt with newly rifled barrels, common calibres, and gauged inspection.",
    ),
    "ADISCORD_infantry_equipment_2156": (
        "ОВ-56 \"Шов\"",
        "SR-56 “Seam”",
        "ОВ-56",
        "SR-56",
        "Первая серийная винтовка новой сборки с контролируемой обтюрацией казённой части и взаимозаменяемым затвором.",
        "The first newly manufactured service rifle with controlled breech obturation and an interchangeable bolt.",
    ),
    "ADISCORD_infantry_equipment_2163": (
        "АВ-63 \"Рёв\"",
        "AR-63 “Roar”",
        "АВ-63",
        "AR-63",
        "Автоматическое оружие под промежуточный патрон, рассчитанный на управляемый огонь короткими очередями.",
        "An automatic weapon chambered for an intermediate cartridge intended for controllable short bursts.",
    ),
    "ADISCORD_infantry_equipment_2168": (
        "АВ-68 \"Срез\"",
        "AR-68 “Cut”",
        "АВ-68",
        "AR-68",
        "Самозарядная винтовка с серийным механизмом экстракции, досылания и взведения от энергии выстрела.",
        "A self-loading rifle with a production-standard mechanism for extraction, feeding, and cocking from firing energy.",
    ),
    "ADISCORD_infantry_equipment_2170": (
        "АВ-70 \"Контур\"",
        "AR-70 “Contour”",
        "АВ-70",
        "AR-70",
        "Автоматическая винтовка с лазерным дальномером и прицельной сеткой, рассчитанной под штатную баллистику патрона.",
        "An automatic rifle with a laser rangefinder and reticle calibrated to the service cartridge trajectory.",
    ),
    "ADISCORD_infantry_equipment_2178": (
        "АВ-78 \"Клык\"",
        "AR-78 “Fang”",
        "АВ-78",
        "AR-78",
        "Газоотводная автоматическая винтовка с регулируемым узлом отвода газов и устойчивым циклом при загрязнении.",
        "A gas-operated automatic rifle with an adjustable gas system and a stable cycle under fouling.",
    ),
    "ADISCORD_infantry_equipment_2183": (
        "АВ-83 \"Призма\"",
        "AR-83 “Prism”",
        "АВ-83",
        "AR-83",
        "Автоматическая винтовка с хромированным каналом ствола, сохраняющим ресурс при высоком темпе огня.",
        "An automatic rifle with a chrome-lined bore that preserves barrel life under a high rate of fire.",
    ),
    "ADISCORD_infantry_equipment_2193": (
        "АВ-93 \"Игла\"",
        "AR-93 “Needle”",
        "АВ-93",
        "AR-93",
        "Автоматическая винтовка с согласованным импульсом отдачи, буфером затворной группы и уменьшенным подбросом.",
        "An automatic rifle with tuned recoil impulse, a buffered bolt group, and reduced muzzle rise.",
    ),
    "ADISCORD_infantry_equipment_2200": (
        "ИСК-00 \"Предел\"",
        "IWS-00 “Limit”",
        "ИСК-00",
        "IWS-00",
        "Индивидуальная система под программируемый боеприпас, получающий дальность и режим подрыва от прицела.",
        "An individual weapon for programmable ammunition that receives range and fuze mode from the sight.",
    ),
    "ADISCORD_squad_weapons_equipment_0": (
        "КОП-40 \"Скат\"",
        "FSC-40 “Ray”",
        "КОП-40",
        "FSC-40",
        "Восстановленные пулемёты, оптика и боеприпасы для тяжёлой группы отделения.",
        "Recovered machine guns, optics, and ammunition issued to the squad heavy group.",
    ),
    "ADISCORD_squad_weapons_equipment_2156": (
        "КОП-56 \"Жгут\"",
        "FSC-56 “Cord”",
        "КОП-56",
        "FSC-56",
        "Единый ленточный комплекс с серийными коробами и переносным запасом стволов.",
        "A common belt-fed system with standardized boxes and portable spare barrels.",
    ),
    "ADISCORD_squad_weapons_equipment_2163": (
        "КОП-63 \"Зуб\"",
        "FSC-63 “Tooth”",
        "КОП-63",
        "FSC-63",
        "Противотанковая установка расчёта с усиленным станком, оптикой и переносным боезапасом.",
        "A crew-operated anti-tank launcher with a reinforced mount, optics, and portable ammunition.",
    ),
    "ADISCORD_squad_weapons_equipment_2168": (
        "КОП-68 \"Вал\"",
        "FSC-68 “Shaft”",
        "КОП-68",
        "FSC-68",
        "Станковый гранатомёт со сменными узлами, общей оптикой и переносным боезапасом.",
        "A mounted grenade launcher with interchangeable assemblies, shared optics, and portable ammunition.",
    ),
    "ADISCORD_squad_weapons_equipment_2170": (
        "КОП-70 \"Гул\"",
        "FSC-70 “Rumble”",
        "КОП-70",
        "FSC-70",
        "Пулемётный комплект с дальномером и передачей целей на планшет расчёта.",
        "A machine-gun system with a rangefinder and target sharing through the crew tablet.",
    ),
    "ADISCORD_squad_weapons_equipment_2178": (
        "КОП-78 \"Узел\"",
        "FSC-78 “Knot”",
        "КОП-78",
        "FSC-78",
        "Станковый гранатомёт с программируемыми взрывателями и защищённой передачей целей.",
        "A mounted grenade launcher with programmable fuzes and protected target sharing.",
    ),
    "ADISCORD_squad_weapons_equipment_2183": (
        "КОП-83 \"Маяк\"",
        "FSC-83 “Beacon”",
        "КОП-83",
        "FSC-83",
        "Дистанционно управляемая огневая установка с многоканальными датчиками и планшетом расчёта.",
        "A remotely controlled fire-support mount with multichannel sensors and a crew tablet.",
    ),
    "ADISCORD_squad_weapons_equipment_2193": (
        "КОП-93 \"Рой\"",
        "FSC-93 “Swarm”",
        "КОП-93",
        "FSC-93",
        "Роботизированная опора тяжёлого оружия с автоматическим сопровождением целей и ручным управлением расчёта.",
        "A robotic heavy-weapon carrier with automatic target tracking and manual crew control.",
    ),
    "ADISCORD_squad_weapons_equipment_2200": (
        "КОП-00 \"Хор\"",
        "FSC-00 “Chorus”",
        "КОП-00",
        "FSC-00",
        "Согласованная сеть огневых роботов и разведывательных дронов под управлением расчёта.",
        "A coordinated network of armed robots and scout drones under crew control.",
    ),
}


INFANTRY_FAMILY_LOCALISATION = {
    "ADISCORD_militia": ("Ополчение", "Militia"),
    "ADISCORD_militia_desc": (
        "Быстрое пополнение фронта: 1000 человек, 900 единиц личного оружия, 45 дней подготовки. Дешевле в снабжении, но уступает регулярной пехоте в организации и огневой мощи. Лучше обороняется в лесах и на холмах; медленнее марширует и плохо наступает. Подготовка местного резерва улучшает устойчивость, не превращая ополчение в штурмовые части.",
        "Rapid frontline reinforcement: 1,000 personnel, 900 personal weapons and 45 days of training. Uses less supply, but has lower organization and firepower than regular infantry. Defends better in forests and hills; marches more slowly and attacks poorly. Local reserve training improves endurance without turning militia into assault troops.",
    ),
    "ADISCORD_territorial": ("Территориальная оборона", "Territorial Defence"),
    "ADISCORD_hazard_infantry": ("Спецназ РХБ-защиты", "CBRN Special Forces"),
    "ADISCORD_hazard_infantry_desc": (
        "Бойцы в противогазах и защитных костюмах уверенно сражаются и передвигаются на заражённой местности. Маски, фильтры и дозиметры входят во вспомогательное снаряжение. Длительная подготовка и лимит спецвойск ограничивают развёртывание; опасная местность по-прежнему изнашивает оснащение.",
        "Troops in respirators and protective suits fight and move effectively in contaminated terrain. Support equipment includes masks, filters and dosimeters. Long training and the special forces cap limit deployment; hazardous terrain still wears down their equipment.",
    ),
    "ADISCORD_territorial_desc": (
        "Части удержания территории: 1000 человек, 900 единиц личного оружия, 70 дней подготовки. Сильнее в обороне городов и укреплений, эффективнее несут гарнизонную службу. Низкие скорость и прорыв ограничивают наступление; отсутствие группового оружия сохраняет преимущество регулярной пехоты в огневой мощи.",
        "Territory-holding formations: 1,000 personnel, 900 personal weapons and 70 days of training. Better at defending cities and fortifications and conducting garrison service. Low speed and breakthrough limit offensives; the absence of crew-served weapons preserves regular infantry's firepower advantage.",
    ),
    "recon": ("Пешая разведывательная рота", "Foot Reconnaissance Company"),
    "recon_desc": (
        "Пешие дозоры и наблюдатели: 200 человек, 180 единиц личного оружия и 10 комплектов обеспечения. Дают разведку без танков и топлива. Занимают ту же ячейку специализации, что и рота бронеразведки; совместить обе в одной дивизии нельзя.",
        "Foot patrols and observers: 200 personnel, 180 personal weapons and 10 support kits. Provide reconnaissance without tanks or fuel. Share the reconnaissance support type with armored scouts; a division cannot use both.",
    ),
    "military_police": ("Рота военной полиции", "Military Police Company"),
    "military_police_desc": (
        "400 человек, 360 единиц личного оружия и 10 комплектов обеспечения. Усиливает подавление сопротивления гарнизоном. Почти не добавляет огневой мощи и занимает ячейку поддержки; это средство контроля территории, а не усиление наступления.",
        "400 personnel, 360 personal weapons and 10 support kits. Improves garrison resistance suppression. Adds little firepower and occupies a support slot; intended for territorial control rather than offensive combat.",
    ),
    "infantry_equipment": ("Личное стрелковое оружие", "Personal Small Arms"),
    "infantry_equipment_short": ("Личное оружие", "Personal Weapons"),
    "infantry_equipment_desc": (
        "Винтовки, карабины и автоматы, которыми вооружён каждый пехотинец.",
        "Rifles, carbines, and automatic weapons carried by individual infantry soldiers.",
    ),
    "ADISCORD_squad_weapons_equipment": (
        "Групповое оружие отделения",
        "Squad Crew-served Weapons",
    ),
    "ADISCORD_squad_weapons_equipment_short": (
        "Групповое оружие",
        "Crew-served Weapons",
    ),
    "ADISCORD_squad_weapons_equipment_desc": (
        "Пулемёты, станковые гранатомёты и тяжёлые огневые установки. Расчёты обслуживают оружие, переносят его и боезапас, обеспечивая огневую поддержку отделения.",
        "Machine guns, mounted grenade launchers, and heavy fire-support mounts. Crews operate the weapons and carry their ammunition to support the squad.",
    ),
}


NAVAL_AIR_UNIT_LOCALISATION = {
    "ADISCORD_tactical_bomber": ("Бомбардировщик", "Bomber"),
    "ADISCORD_tactical_bomber_desc": (
        "Бомбардировочная авиация для ударов по промышленности, снабжению и сухопутным войскам.",
        "Bomber aircraft for attacks on industry, supply and ground forces.",
    ),
}


NAVAL_AIR_EQUIPMENT_LOCALISATION = {
    "ADISCORD_escort_ship_2155": (
        "Эскортный корабль обр. 2155",
        "Escort Ship Model 2155",
        "Противолодочный корабль охранения с зенитным вооружением и средствами поиска подводных целей.",
        "An escort with anti-submarine weapons, air defence and underwater detection.",
    ),
    "ADISCORD_escort_ship_2163": (
        "Эскортный корабль обр. 2163",
        "Escort Ship Model 2163",
        "Противолодочный корабль охранения с зенитным вооружением и средствами поиска подводных целей.",
        "An escort with anti-submarine weapons, air defence and underwater detection.",
    ),
    "ADISCORD_escort_ship_2170": (
        "Эскортный корабль обр. 2170",
        "Escort Ship Model 2170",
        "Противолодочный корабль охранения с зенитным вооружением и средствами поиска подводных целей.",
        "An escort with anti-submarine weapons, air defence and underwater detection.",
    ),
    "ADISCORD_escort_ship_2175": (
        "Эскортный корабль обр. 2175",
        "Escort Ship Model 2175",
        "Противолодочный корабль охранения с зенитным вооружением и средствами поиска подводных целей.",
        "An escort with anti-submarine weapons, air defence and underwater detection.",
    ),
    "ADISCORD_cruiser_2155": (
        "Тяжёлый крейсер обр. 2155",
        "Heavy Cruiser Model 2155",
        "Крупный надводный корабль с дальней артиллерией, броневой защитой и эшелонированной ПВО. Требует прикрытия эскортом.",
        "An armored capital ship with long-range guns and layered air defence. Requires screening escorts.",
    ),
    "ADISCORD_cruiser_2163": (
        "Тяжёлый крейсер обр. 2163",
        "Heavy Cruiser Model 2163",
        "Крупный надводный корабль с дальней артиллерией, броневой защитой и эшелонированной ПВО. Требует прикрытия эскортом.",
        "An armored capital ship with long-range guns and layered air defence. Requires screening escorts.",
    ),
    "ADISCORD_cruiser_2170": (
        "Тяжёлый крейсер обр. 2170",
        "Heavy Cruiser Model 2170",
        "Крупный надводный корабль с дальней артиллерией, броневой защитой и эшелонированной ПВО. Требует прикрытия эскортом.",
        "An armored capital ship with long-range guns and layered air defence. Requires screening escorts.",
    ),
    "ADISCORD_cruiser_2175": (
        "Тяжёлый крейсер обр. 2175",
        "Heavy Cruiser Model 2175",
        "Крупный надводный корабль с дальней артиллерией, броневой защитой и эшелонированной ПВО. Требует прикрытия эскортом.",
        "An armored capital ship with long-range guns and layered air defence. Requires screening escorts.",
    ),
    "ADISCORD_submarine_2155": (
        "Подводная лодка обр. 2155",
        "Submarine Model 2155",
        "Торпедная подводная лодка для скрытного перехвата транспортов и атак надводных кораблей.",
        "A torpedo submarine for covert convoy interdiction and attacks on surface ships.",
    ),
    "ADISCORD_submarine_2163": (
        "Подводная лодка обр. 2163",
        "Submarine Model 2163",
        "Торпедная подводная лодка для скрытного перехвата транспортов и атак надводных кораблей.",
        "A torpedo submarine for covert convoy interdiction and attacks on surface ships.",
    ),
    "ADISCORD_submarine_2170": (
        "Подводная лодка обр. 2170",
        "Submarine Model 2170",
        "Торпедная подводная лодка для скрытного перехвата транспортов и атак надводных кораблей.",
        "A torpedo submarine for covert convoy interdiction and attacks on surface ships.",
    ),
    "ADISCORD_submarine_2175": (
        "Подводная лодка обр. 2175",
        "Submarine Model 2175",
        "Торпедная подводная лодка для скрытного перехвата транспортов и атак надводных кораблей.",
        "A torpedo submarine for covert convoy interdiction and attacks on surface ships.",
    ),
    "ADISCORD_fighter_airframe_2161": (
        "Истребитель обр. 2161",
        "Fighter Model 2161",
        "Серийный истребитель с улучшенным вооружением, скоростью и дальностью перехвата.",
        "A production fighter with improved weapons, speed and interception range.",
    ),
    "ADISCORD_fighter_airframe_2166": (
        "Истребитель обр. 2166",
        "Fighter Model 2166",
        "Серийный истребитель с улучшенным вооружением, скоростью и дальностью перехвата.",
        "A production fighter with improved weapons, speed and interception range.",
    ),
    "ADISCORD_fighter_airframe_2170": (
        "Истребитель обр. 2170",
        "Fighter Model 2170",
        "Серийный истребитель с улучшенным вооружением, скоростью и дальностью перехвата.",
        "A production fighter with improved weapons, speed and interception range.",
    ),
    "ADISCORD_fighter_airframe_2175": (
        "Истребитель обр. 2175",
        "Fighter Model 2175",
        "Серийный истребитель с улучшенным вооружением, скоростью и дальностью перехвата.",
        "A production fighter with improved weapons, speed and interception range.",
    ),
    "ADISCORD_attack_airframe_2163": (
        "Ударный самолёт обр. 2163",
        "Attack Aircraft Model 2163",
        "Самолёт непосредственной поддержки войск с усиленным ударным вооружением и защитой.",
        "A close-support aircraft with improved strike weapons and protection.",
    ),
    "ADISCORD_attack_airframe_2170": (
        "Ударный самолёт обр. 2170",
        "Attack Aircraft Model 2170",
        "Самолёт непосредственной поддержки войск с усиленным ударным вооружением и защитой.",
        "A close-support aircraft with improved strike weapons and protection.",
    ),
    "ADISCORD_attack_airframe_2175": (
        "Ударный самолёт обр. 2175",
        "Attack Aircraft Model 2175",
        "Самолёт непосредственной поддержки войск с усиленным ударным вооружением и защитой.",
        "A close-support aircraft with improved strike weapons and protection.",
    ),
    "ADISCORD_bomber_2160": (
        "Бомбардировщик обр. 2160",
        "Bomber Model 2160",
        "Дальний бомбардировщик для ударов по промышленности, коммуникациям и наземным войскам.",
        "A long-range bomber for attacks on industry, logistics and ground forces.",
    ),
    "ADISCORD_bomber_2164": (
        "Бомбардировщик обр. 2164",
        "Bomber Model 2164",
        "Дальний бомбардировщик для ударов по промышленности, коммуникациям и наземным войскам.",
        "A long-range bomber for attacks on industry, logistics and ground forces.",
    ),
    "ADISCORD_bomber_2172": (
        "Бомбардировщик обр. 2172",
        "Bomber Model 2172",
        "Дальний бомбардировщик для ударов по промышленности, коммуникациям и наземным войскам.",
        "A long-range bomber for attacks on industry, logistics and ground forces.",
    ),
    "ADISCORD_naval_aircraft_2160": (
        "Морской ударный самолёт обр. 2160",
        "Maritime Strike Aircraft Model 2160",
        "Самолёт морского патрулирования с торпедным вооружением для ударов по кораблям и портам.",
        "A maritime patrol aircraft with torpedoes for attacks on ships and ports.",
    ),
    "ADISCORD_naval_aircraft_2164": (
        "Морской ударный самолёт обр. 2164",
        "Maritime Strike Aircraft Model 2164",
        "Самолёт морского патрулирования с торпедным вооружением для ударов по кораблям и портам.",
        "A maritime patrol aircraft with torpedoes for attacks on ships and ports.",
    ),
    "ADISCORD_naval_aircraft_2172": (
        "Морской ударный самолёт обр. 2172",
        "Maritime Strike Aircraft Model 2172",
        "Самолёт морского патрулирования с торпедным вооружением для ударов по кораблям и портам.",
        "A maritime patrol aircraft with torpedoes for attacks on ships and ports.",
    ),
    "ADISCORD_cruiser_archetype": (
        "Тяжёлые крейсеры",
        "Heavy Cruisers",
        "Тяжёлые крейсеры.",
        "Heavy Cruisers.",
    ),
    "ADISCORD_submarine_archetype": (
        "Подводные лодки",
        "Submarines",
        "Подводные лодки.",
        "Submarines.",
    ),
    "ADISCORD_bomber_archetype": (
        "Бомбардировщики",
        "Bombers",
        "Бомбардировщики.",
        "Bombers.",
    ),
    "ADISCORD_naval_aircraft_archetype": (
        "Морская авиация",
        "Maritime Aircraft",
        "Морская авиация.",
        "Maritime Aircraft.",
    ),
}

NAVAL_HULL_DESCRIPTIONS = {
    "destroyer": ("Быстрый корабль охранения для защиты конвоев, поиска подлодок и прикрытия крупных кораблей", "A fast screen for convoy protection, submarine hunting and capital-ship escort"),
    "light_cruiser": ("Крейсер охранения с лёгкой артиллерией и усиленной ПВО; борется с вражеским эскортом", "A screening cruiser with light artillery and strong air defence, designed to defeat enemy screens"),
    "heavy_cruiser": ("Крупный артиллерийский корабль для ударной группы; нуждается в охранении эсминцев и лёгких крейсеров", "A capital gunship for strike groups, requiring destroyer and light-cruiser screens"),
    "battleship": ("Тяжёлый бронированный корабль с мощным главным калибром для боя с крупными кораблями и обстрела берега", "A heavily armoured capital ship with powerful main guns for surface combat and shore bombardment"),
    "carrier": ("Плавучий аэродром для палубной авиации; нуждается в самолётах, кораблях охранения и прикрытии крупных кораблей", "A floating airfield requiring carrier aircraft, screens and capital-ship protection"),
    "submarine": ("Скрытный торпедный корабль для перехвата конвоев и нападения на незащищённые соединения", "A stealthy torpedo boat for convoy interdiction and attacks on unprotected fleets"),
}
for kind, (_, _, model_ru, model_en, equipment, _) in NAVAL_HULL_CLASSES.items():
    description_ru, description_en = NAVAL_HULL_DESCRIPTIONS[kind]
    for year in NAVAL_HULL_YEARS:
        NAVAL_AIR_EQUIPMENT_LOCALISATION[f"ADISCORD_{equipment}_{year}"] = (
            f"{model_ru} обр. {year}", f"{model_en} Model {year}",
            description_ru + ".", description_en + ".",
        )
        TECHNICAL_TECH_DESCRIPTIONS[f"{kind}_hull_{year}"] = (description_ru, description_en)
    if kind in {"light_cruiser", "battleship", "carrier"}:
        NAVAL_AIR_EQUIPMENT_LOCALISATION[f"ADISCORD_{equipment}_archetype"] = (
            model_ru, model_en, description_ru + ".", description_en + ".",
        )
for kind, ru, en, description_ru, description_en in (
    ("cv_fighter", "Палубный истребитель", "Carrier Fighter", "Защищает авианосное соединение и завоёвывает превосходство в воздухе", "Protects the carrier group and contests air superiority"),
    ("cv_bomber", "Палубный торпедоносец", "Carrier Torpedo Bomber", "Наносит удары по кораблям с палубы авианосца", "Attacks enemy shipping from a carrier deck"),
):
    NAVAL_AIR_EQUIPMENT_LOCALISATION[f"ADISCORD_{kind}_archetype"] = (
        ru, en, description_ru + ".", description_en + ".",
    )
    for year in NAVAL_HULL_YEARS:
        NAVAL_AIR_EQUIPMENT_LOCALISATION[f"ADISCORD_{kind}_{year}"] = (
            f"{ru} обр. {year}", f"{en} Model {year}", description_ru + ".", description_en + ".",
        )
        TECHNICAL_TECH_DESCRIPTIONS[f"{kind}_research_{year}"] = (description_ru, description_en)


REGIMENTAL_SUPPORT_LOCALISATION = {
    "ADISCORD_regimental_fire_support": (
        "Полковая огневая группа",
        "Regimental Fire-support Group",
    ),
    "ADISCORD_regimental_fire_support_desc": (
        "Расчёты пулемётов и станкового оружия для непосредственной поддержки полка. Используют групповое оружие, усиливая огонь по пехоте. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Machine-gun and crew-served weapon teams for close regimental support. Use crew-served weapons to reinforce anti-infantry fire. Occupy the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_anti_tank": (
        "Полковой противотанковый взвод",
        "Regimental Anti-tank Platoon",
    ),
    "ADISCORD_regimental_anti_tank_desc": (
        "Небольшой противотанковый резерв полка. Требует противотанкового вооружения и повышает бронепробитие; заметно слабее полной батареи. Занимает полковую ячейку под столбцом из не менее трёх батальонов.",
        "A small regimental anti-tank reserve. Requires anti-tank weapons and improves piercing; substantially weaker than a full battery. Occupies the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_anti_air": (
        "Полковой взвод ПВО",
        "Regimental Air-defense Platoon",
    ),
    "ADISCORD_regimental_anti_air_desc": (
        "Зенитные расчёты для прикрытия позиций полка и борьбы с низколетящими целями. Используют производимое зенитное вооружение. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Anti-aircraft teams covering regimental positions against low-flying targets. Use the country's produced anti-aircraft weapons. Occupy the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_pioneers": (
        "Полковой сапёрный взвод",
        "Regimental Pioneer Platoon",
    ),
    "ADISCORD_regimental_pioneers_desc": (
        "Сапёры с подрывным инструментом и полевыми комплектами. Улучшают укрепление позиций, штурм городской застройки и укреплений. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Pioneers with demolition tools and field kits. Improve entrenchment and assaults on urban positions and fortifications. Occupy the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_drone_observers": (
        "Полковая группа воздушной разведки",
        "Regimental Drone Observation Team",
    ),
    "ADISCORD_regimental_drone_observers_desc": (
        "Наблюдатели с разведывательными дронами, средствами связи и запасными частями из полевых комплектов. Повышают разведку и инициативу, но почти не добавляют огневой мощи. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Observers using reconnaissance drones, radios and spares supplied as field equipment. Improve reconnaissance and initiative with little added firepower. Occupy the regimental slot below a column of at least three battalions.",
    ),
}


NAVAL_AIR_EQUIPMENT_LOCALISATION.update(AIRCRAFT_TYPE_LOCALISATION)

AIR_BRANCH_DESCRIPTIONS = {
    "fighter": (
        "Истребители завоёвывают превосходство в воздухе. Перехватчики исследуются отдельной линией, используют собственное оснащение и формируют отдельные авиакрылья: мощное вооружение и защита оплачиваются меньшей манёвренностью и дальностью. Улучшения действуют только на указанный тип самолётов",
        "Fighters contest air superiority. Interceptors follow a separate research line and use their own equipment and wings: heavier weapons and protection cost agility and range. Improvements affect only the named aircraft role",
    ),
    "air_support": (
        "Штурмовики поддерживают сухопутные войска и атакуют снабжение противника. Ударные БПЛА имеют отдельные авиакрылья: дешевле самолётов, требуют меньше персонала и топлива, но несут меньшую нагрузку. Исследование БПЛА не требуется для новых поколений пилотируемых штурмовиков",
        "Attack aircraft support ground troops and strike enemy logistics. Strike drones form separate wings: cheaper and less demanding in personnel and fuel, but with a smaller payload. Drone research is not required for new manned attack aircraft",
    ),
    "bomber_maritime": (
        "Общий двухмоторный планер открывает тактический бомбардировщик и морской самолёт. Далее роли развиваются независимо: бомбардировщики атакуют наземные цели, морская авиация ведёт патрулирование и наносит удары по кораблям и портам. Общая навигация доступна после любой из двух линий",
        "A common twin-engine airframe opens tactical bombers and maritime aircraft. Their roles then develop independently: bombers strike ground targets, while maritime aircraft patrol and attack ships and ports. Shared navigation follows either line",
    ),
    "strategic_air": (
        "Дальние ракетоносцы формируют авиакрылья для стратегических бомбардировок. Это возвращающиеся на аэродром самолёты с ударным вооружением, а не одноразовые ракеты. Поколения планеров и отдельная линия наведения улучшают только дальнюю ударную авиацию",
        "Long-range missile carriers form wings for strategic bombing. These are aircraft that return to their airfields, not expendable missiles. Airframe generations and a separate guidance line improve only long-range strike aircraft",
    ),
    "air_mobility": (
        "Транспортные самолёты обеспечивают воздушное снабжение и перевозку десанта. Их необходимо произвести и разместить в авиакрыльях; исследования не снабжают армию автоматически. Поколения отличаются дальностью, скоростью, защитой и ценой",
        "Transport planes provide air supply and carry paratroopers. They must be produced and deployed in wings; research does not supply armies automatically. Generations differ in range, speed, protection and price",
    ),
}


AIR_ROLE_LOCALISATION = {
    "ADISCORD_interceptor": ("Перехватчик", "Interceptor"),
    "ADISCORD_interceptor_desc": ("Отдельное авиакрыло тяжело вооружённых перехватчиков. Использует собственные самолёты для перехвата и завоевания превосходства в воздухе.", "A separate wing of heavily armed interceptors. Uses its own aircraft for interception and air superiority."),
    "ADISCORD_strike_drone": ("Ударный БПЛА", "Strike Drone"),
    "ADISCORD_strike_drone_desc": ("Отдельное авиакрыло беспилотной непосредственной поддержки. Низкая стоимость и небольшой штат наземных операторов сочетаются с меньшей боевой нагрузкой и уязвимостью к истребителям.", "A separate unmanned close-support wing. Low cost and a small ground operator complement come with a smaller payload and vulnerability to fighters."),
    "transport_plane": ("Транспортный самолёт", "Transport Plane"),
    "transport_plane_desc": ("Воздушное снабжение и перевозка десантников. Не имеет ударных миссий; нуждается в аэродроме, топливе и прикрытии.", "Air supply and paratrooper transport. Has no attack missions and needs an airfield, fuel and protection."),
    "ADISCORD_interceptor_archetype": ("Перехватчики", "Interceptors"),
    "ADISCORD_strike_drone_archetype": ("Ударные беспилотники", "Strike Drones"),
    "transport_plane_equipment": ("Транспортная авиация", "Transport Aircraft"),
    "ADISCORD_rocket_strike_archetype": ("Дальние ракетоносцы", "Long-range Missile Carriers"),
    "tac_bomber": ("Дальний ракетоносец", "Long-range Missile Carrier"),
}

for _model, _ru, _en, _ru_desc, _en_desc in (
    ("ADISCORD_interceptor_airframe_2158", "Ранний радиолокационный перехватчик", "Early Radar Interceptor",
     "Тяжёлое вооружение для перехвата бомбардировщиков. Меньше манёвренность и дальность, чем у универсального истребителя.",
     "Heavy armament for intercepting bombers. Less agility and range than a general-purpose fighter."),
    ("ADISCORD_interceptor_airframe_2183", "Малозаметный перехватчик", "Low-observable Interceptor",
     "Скоростной перехватчик с усиленной защитой и вооружением. Требует редких компонентов и сплавов.",
     "A fast interceptor with stronger protection and weapons. Requires rare components and alloys."),
    ("ADISCORD_interceptor_airframe_2173", "Перехватчик с автоматизацией воздушного боя", "Automated Combat Interceptor",
     "Поздний специализированный перехватчик. Сильнее против тяжёлых самолётов, но менее манёвренен, чем современный истребитель.",
     "A late specialized interceptor. Stronger against heavy aircraft but less agile than a contemporary fighter."),
    ("ADISCORD_drone_airframe_2183", "Лёгкий ударный БПЛА", "Light Strike Drone",
     "Дешёвый беспилотный носитель небольшой нагрузки. Используется отдельным авиакрылом и не вытесняет пилотируемые штурмовики из их частей.",
     "An inexpensive unmanned aircraft with a small payload. Uses a separate wing and does not replace manned attack aircraft in their units."),
    ("ADISCORD_strike_airframe_2158", "Восстановленный дальний ракетоносец", "Restored Long-range Missile Carrier",
     "Доступный самолёт стратегического удара с ограниченной дальностью и защитой. Потребляет топливо и возвращается на аэродром после вылета.",
     "An accessible strategic strike aircraft with limited range and protection. Uses fuel and returns to its airfield after a sortie."),
    ("ADISCORD_rocket_strike_platform_2183", "Дальний ракетоносец с цифровым наведением", "Digitally Guided Missile Carrier",
     "Усиленное ударное вооружение и дальность полёта для бомбардировки промышленности и инфраструктуры.",
     "Improved strike weapons and range for bombing industry and infrastructure."),
    ("ADISCORD_deep_strike_airframe_2200", "Ракетоносец глубокого проникновения", "Deep-penetration Missile Carrier",
     "Большая дальность и защита для ударов в глубине вражеской территории. Дорогое производство требует редких материалов.",
     "Long range and protection for strikes deep inside enemy territory. Expensive production requires rare materials."),
    ("ADISCORD_orbital_tracking_platform_2200", "Дальний ракетоносец \"Стрела\"", "Strela Long-range Missile Carrier",
     "Поздний самолёт стратегического удара с максимальной дальностью и боевой нагрузкой своей линии.",
     "A late strategic strike aircraft with the greatest range and payload in its line."),
    ("ADISCORD_transport_airframe_2162", "Восстановленный транспортный самолёт", "Restored Transport Plane",
     "Недорогой транспорт для воздушного снабжения и десантирования на ближних направлениях.",
     "An affordable transport for air supply and short-range airborne operations."),
    ("ADISCORD_transport_airframe_2169", "Дальний транспортный самолёт", "Long-range Transport Plane",
     "Увеличенная дальность, скорость и живучесть для снабжения удалённых войск.",
     "Improved range, speed and survivability for supplying distant troops."),
    ("ADISCORD_transport_airframe_2175", "Усовершенствованный транспортный самолёт", "Advanced Transport Plane",
     "Дальний транспорт с улучшенной навигацией и защитой. Требует больше производственных затрат и электроники.",
     "A long-range transport with improved navigation and protection. Requires more production capacity and electronics."),
):
    AIR_ROLE_LOCALISATION[_model] = (_ru, _en)
    AIR_ROLE_LOCALISATION[f"{_model}_short"] = (_ru, _en)
    AIR_ROLE_LOCALISATION[f"{_model}_desc"] = (_ru_desc, _en_desc)


ARTILLERY_BRANCH_DESCRIPTIONS = {
    "artillery": (
        "Полевые орудия дают огневую поддержку против пехоты. Улучшения действуют на батареи поддержки и линейную артиллерию. Новые орудия открываются в основной линии; управление огнём, контрбатарейная разведка и беспилотная корректировка исследуются отдельно",
        "Field guns provide fire support against infantry. Upgrades affect support batteries and line artillery. The main line unlocks new guns; fire control, counter-battery detection and drone spotting are independent projects",
    ),
    "anti_tank": (
        "Противотанковые части поражают бронетехнику, но уступают артиллерии против пехоты. Улучшения действуют на полковые секции, батареи поддержки и линейные батальоны ПТО. Управляемые ракеты дают отдельный путь перевооружения; для катушечных орудий их изучение не требуется",
        "Anti-tank units defeat armor but are less effective against infantry than artillery. Upgrades affect regimental sections, support batteries and line battalions. Guided missiles offer a separate rearmament path and are not required for coil guns",
    ),
    "anti_air": (
        "Войсковая ПВО прикрывает дивизии от авиации. Улучшения действуют на полковые секции, батареи поддержки и линейные зенитные батальоны. Ракетная линия развивается отдельно от автопушек и лазерных установок. Новые модели требуют производства и пополнения частей",
        "Divisional air defense protects troops from aircraft. Upgrades affect regimental sections, support batteries and line AA battalions. Missiles develop independently of autocannons and laser mounts. New models must be produced and delivered to units",
    ),
}


ARTILLERY_LOCALISATION = {
    "ADISCORD_line_anti_tank": ("Линейный противотанковый батальон", "Line Anti-tank Battalion"),
    "ADISCORD_line_anti_tank_desc": (
        "500 военнослужащих, 450 единиц личного оружия и 36 противотанковых орудий или пусковых установок. Занимает 2 единицы ширины фронта. Сильнее батареи поддержки против бронетехники, но требует больше оснащения и снижает среднюю организацию дивизии.",
        "500 personnel, 450 personal weapons and 36 anti-tank guns or launchers. Uses 2 combat width. More effective against armor than a support battery, but requires more equipment and lowers average division organization.",
    ),
    "ADISCORD_line_anti_air": ("Линейный зенитный батальон", "Line Anti-air Battalion"),
    "ADISCORD_line_anti_air_desc": (
        "500 военнослужащих, 450 единиц личного оружия и 32 зенитные установки. Занимает 2 единицы ширины фронта. Усиливает прикрытие дивизии от авиации, но не заменяет противотанковые части или истребители.",
        "500 personnel, 450 personal weapons and 32 anti-air mounts. Uses 2 combat width. Improves a division's protection from aircraft, but does not replace anti-tank units or fighters.",
    ),
}

for _equipment, _ru, _en, _description_ru, _description_en in (
    (
        "artillery_equipment_1", "Восстановленные полевые орудия", "Restored Field Guns",
        "Буксируемые орудия для линейной артиллерии и батарей поддержки. Простая конструкция и доступные материалы позволяют наладить массовое производство.",
        "Towed guns for line artillery and support batteries. A simple design and common materials permit mass production.",
    ),
    (
        "ADISCORD_artillery_equipment_2160", "Полевые гаубицы с приводами наведения", "Power-laid Field Howitzers",
        "Унифицированный лафет и приводы наведения повышают темп огня. Буксируемая артиллерия, не самоходная установка.",
        "A standardized carriage and powered laying improve fire delivery. Towed artillery, not a self-propelled vehicle.",
    ),
    (
        "ADISCORD_artillery_equipment_2170", "Гаубицы с корректируемыми боеприпасами", "Precision-ammunition Howitzers",
        "Буксируемые гаубицы с аппаратурой подготовки корректируемых снарядов. Усиливают огонь по пехоте и подготовленным позициям.",
        "Towed howitzers with equipment for programming corrected shells. Improve fire against infantry and prepared positions.",
    ),
    (
        "ADISCORD_artillery_equipment_2183", "Автоматизированные гаубицы \"Гул\"", "Gul Automated Howitzers",
        "Буксируемые гаубицы с автоматизированной подачей снарядов и дистанционным наведением. Мощный огонь требует редких сплавов и электронных компонентов.",
        "Towed howitzers with automated shell handling and remote laying. Powerful fire requires rare alloys and electronic components.",
    ),
    (
        "ADISCORD_anti_tank_equipment_2163", "Восстановленные противотанковые пушки", "Restored Anti-tank Guns",
        "Недорогие буксируемые пушки для борьбы с ранней бронетехникой. Используются линейными батальонами, батареями поддержки и полковыми секциями ПТО.",
        "Affordable towed guns for defeating early armor. Used by line battalions, support batteries and regimental anti-tank sections.",
    ),
    (
        "ADISCORD_anti_tank_equipment_2161", "Высокоскоростные противотанковые пушки", "High-velocity Anti-tank Guns",
        "Усиленный ствол и новые бронебойные боеприпасы повышают пробитие. Для производства нужны сталь и вольфрам.",
        "A reinforced barrel and new armor-piercing rounds improve penetration. Production requires steel and tungsten.",
    ),
    (
        "ADISCORD_anti_tank_equipment_2166", "Управляемые противотанковые комплексы", "Guided Anti-tank Systems",
        "Ракеты с наведением и атакой верхней проекции дают ранний доступ к мощному ПТО. Дороже пушек, требуют электроники и тщательного обслуживания.",
        "Guided top-attack missiles offer earlier access to powerful anti-tank weapons. Costlier than guns and dependent on electronics and careful maintenance.",
    ),
    (
        "ADISCORD_anti_tank_equipment_2183", "Катушечные противотанковые орудия", "Coil Anti-tank Guns",
        "Электромагнитное ускорение обеспечивает высокое пробитие тяжёлой брони. Сложное производство расходует редкие сплавы и компоненты.",
        "Electromagnetic acceleration provides strong penetration against heavy armor. Complex production consumes rare alloys and components.",
    ),
    (
        "ADISCORD_anti_air_equipment_2163", "Восстановленные зенитные орудия", "Restored Anti-air Guns",
        "Простые буксируемые зенитные пушки. Прикрывают дивизии от авиации без редких материалов.",
        "Simple towed anti-air guns. Protect divisions from aircraft without requiring rare materials.",
    ),
    (
        "ADISCORD_anti_air_equipment_2160", "Стабилизированные зенитные автопушки", "Stabilized Anti-air Autocannons",
        "Приводы сопровождения цели и скорострельные стволы улучшают ближнее прикрытие. Сохраняют доступную производственную базу.",
        "Target-tracking drives and rapid-fire barrels improve close protection while retaining an affordable production base.",
    ),
    (
        "ADISCORD_anti_air_equipment_2165", "Зенитные ракетные комплексы \"Заслон\"", "Zaslon Surface-to-air Missiles",
        "Управляемые ракеты усиливают войсковую ПВО, но почти бесполезны против брони. Для производства нужны редкие компоненты.",
        "Guided missiles strengthen divisional air defense but are poorly suited to fighting armor. Production requires rare components.",
    ),
    (
        "ADISCORD_anti_air_equipment_2183", "Лазерные установки войсковой ПВО", "Divisional Laser Air Defense",
        "Высокоэнергетические установки для перехвата воздушных целей. Дороги в производстве и не заменяют специализированные противотанковые орудия.",
        "High-energy mounts for intercepting aerial targets. Expensive to produce and no substitute for dedicated anti-tank guns.",
    ),
):
    ARTILLERY_LOCALISATION[_equipment] = (_ru, _en)
    ARTILLERY_LOCALISATION[f"{_equipment}_short"] = (_ru, _en)
    ARTILLERY_LOCALISATION[f"{_equipment}_desc"] = (_description_ru, _description_en)


ARMOR_UNIT_LOCALISATION = {
    "ADISCORD_light_tank": ("Лёгкий танковый батальон", "Light Tank Battalion"),
    "ADISCORD_light_tank_desc": (
        "Линейный батальон из 40 лёгких танков и 400 военнослужащих. Быстрее и дешевле основных танков, но слабее защищён. Использует те же машины, что и рота бронеразведки, и занимает место в бронетанковом полку.",
        "A line battalion of 40 light tanks and 400 personnel. Faster and cheaper than main battle tanks, but less protected. Uses the same vehicles as armored reconnaissance and occupies an armored regiment slot.",
    ),
}


def generated_localisation(language: str) -> list[str]:
    is_ru = language == "russian"
    lines = [
        localisation_entry(key, names[0 if is_ru else 1])
        for mapping in (
            ACCESS_REQUIREMENT_LOCALISATION,
            INFANTRY_FAMILY_LOCALISATION,
            ARTILLERY_LOCALISATION,
            AIR_ROLE_LOCALISATION,
            NAVAL_AIR_UNIT_LOCALISATION,
            REGIMENTAL_SUPPORT_LOCALISATION,
            ARMOR_UNIT_LOCALISATION,
        )
        for key, names in mapping.items()
    ]
    lines.append("")
    for equipment_id, values in LAND_EQUIPMENT_LOCALISATION.items():
        if is_ru:
            name, short, description = values[0], values[2], values[4]
        else:
            name, short, description = values[1], values[3], values[5]
        if equipment_id.startswith("ADISCORD_squad_weapons_equipment_"):
            name = ("Групповое оружие " if is_ru else "Crew-served weapons ") + name
            short = ("Групп. " if is_ru else "Crew ") + short
        elif not equipment_id.startswith(("ADISCORD_power_shield_equipment", "ADISCORD_combat_platform_", "ADISCORD_heavy_combat_platform_")):
            name = ("Личное оружие " if is_ru else "Personal weapon ") + name
            short = ("Личн. " if is_ru else "Personal ") + short
        lines.extend(
            (
                localisation_entry(equipment_id, name),
                localisation_entry(f"{equipment_id}_short", short),
                localisation_entry(f"{equipment_id}_desc", description),
            )
        )
    lines.append("")
    for equipment_id, (
        ru,
        en,
        description_ru,
        description_en,
    ) in NAVAL_AIR_EQUIPMENT_LOCALISATION.items():
        name, description = (ru, description_ru) if is_ru else (en, description_en)
        lines.extend(
            (
                localisation_entry(equipment_id, name),
                localisation_entry(f"{equipment_id}_short", name),
                localisation_entry(f"{equipment_id}_desc", description),
            )
        )
    lines.append("")
    for branch in BRANCHES:
        key = f"ADISCORD_TECH_BRANCH_{branch.key.upper()}"
        lines.append(localisation_entry(key, branch.ru if is_ru else branch.en))
    lines.append("")
    for branch in BRANCHES:
        if is_ru:
            branch_description = APPLIED_DESCRIPTION_RU_BY_BRANCH.get(
                branch.key, BRANCH_DESCRIPTION_RU[branch.profile]
            )
        else:
            branch_description = APPLIED_DESCRIPTION_EN_BY_BRANCH.get(
                branch.key, BRANCH_DESCRIPTION_EN[branch.profile]
            )
        for index, tech in enumerate(branch.techs):
            name = tech.ru if is_ru else tech.en
            if branch.key in {"small_arms", "assault_rifles", "squad_weapons"} and tech.id in ENABLE_EQUIPMENT:
                equipment = ENABLE_EQUIPMENT[tech.id][0]
                name = LAND_EQUIPMENT_LOCALISATION[equipment][0 if is_ru else 1]
            year = branch.years[index]
            technical = TECHNICAL_TECH_DESCRIPTIONS.get(tech.key)
            technical = (
                technical or AIR_BRANCH_DESCRIPTIONS.get(branch.key)
                or ARTILLERY_BRANCH_DESCRIPTIONS.get(branch.key)
                or SUPPORT_BRANCH_DESCRIPTIONS.get(branch.key)
            )
            description = (
                technical[0 if is_ru else 1] if technical else branch_description
            )
            if is_ru:
                desc = f"{description}. Технологический уровень {year} года."
            else:
                desc = f"{description}. Technology level: {year}."
            notes = technology_description_notes(branch, index, is_ru)
            if notes:
                desc += " " + " ".join(notes)
            lines.append(localisation_entry(tech.id, name))
            lines.append(localisation_entry(f"{tech.id}_desc", desc))
            training = LEADER_TRAINING.get(tech.key)
            if training:
                attribute, count = training
                attribute_ru = {
                    "attack": "атаке",
                    "defense": "обороне",
                    "planning": "планированию",
                    "logistics": "логистике",
                }[attribute]
                if is_ru:
                    tooltip = (
                        f"{count} случайных генерала получают §G+1§! к {attribute_ru}."
                    )
                else:
                    tooltip = (
                        f"{count} random army leaders gain §G+1§! {attribute.title()}."
                    )
                lines.append(localisation_entry(f"{tech.id}_leader_effect_tt", tooltip))
    return lines


def write_localisation() -> None:
    targets = {
        "russian": ROOT
        / "localisation"
        / "russian"
        / "ADISCORD_technology_doctrine_l_russian.yml",
        "english": ROOT
        / "localisation"
        / "english"
        / "ADISCORD_technology_doctrine_l_english.yml",
    }
    generated_key = re.compile(r"^\s+([A-Za-z0-9_]+)\s*:")
    generated_equipment_keys = {
        suffix
        for equipment_id in (
            *LAND_EQUIPMENT_LOCALISATION,
            *NAVAL_AIR_EQUIPMENT_LOCALISATION,
        )
        for suffix in (equipment_id, f"{equipment_id}_short", f"{equipment_id}_desc")
    }
    for language, path in targets.items():
        if path.exists():
            original = path.read_text(encoding="utf-8-sig").splitlines()
        else:
            original = [f"l_{language}:"]
        preserved = []
        for line in original:
            match = generated_key.match(line)
            key = match.group(1) if match else ""
            if (
                key.startswith("ADISCORD_tech_")
                or key.startswith("ADISCORD_TECH_BRANCH_")
                or key in ACCESS_REQUIREMENT_LOCALISATION
                or key in INFANTRY_FAMILY_LOCALISATION
                or key in ARTILLERY_LOCALISATION
                or key in AIR_ROLE_LOCALISATION
                or key in NAVAL_AIR_UNIT_LOCALISATION
                or key in REGIMENTAL_SUPPORT_LOCALISATION
                or key in ARMOR_UNIT_LOCALISATION
                or key in generated_equipment_keys
            ):
                continue
            preserved.append(normalise_localisation_quotes(line))
        while preserved and not preserved[-1].strip():
            preserved.pop()
        output = preserved + [""] + generated_localisation(language)
        path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8-sig")


def find_block_end(text: str, open_brace: int) -> int:
    depth = 0
    in_quote = False
    in_comment = False
    escaped = False
    for index in range(open_brace, len(text)):
        char = text[index]
        if in_comment:
            if char == "\n":
                in_comment = False
            continue
        if in_quote:
            if char == "\\" and not escaped:
                escaped = True
                continue
            if char == '"' and not escaped:
                in_quote = False
            escaped = False
            continue
        if char == "#":
            in_comment = True
        elif char == '"':
            in_quote = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError(f"Unclosed block at {open_brace}")


def render_folder(folder: str) -> str:
    branches = [branch for branch in BRANCHES if folder in branch.folders]
    horizontal = folder in HORIZONTAL_FOLDERS
    branch_layouts: list[tuple[Branch, int, int, int, int]] = []
    vertical_tree_layouts: dict[str, tuple[int, int, int, int]] = {}
    if horizontal:
        grid_width = (
            len(horizontal_year_columns(folder)) * HORIZONTAL_YEAR_SLOT_MULTIPLIER
        ) * GRID_SLOT
        cursor_y = GRID_Y
        for branch in branches:
            if branch.key in BRANCH_CONTINUATIONS:
                # Connected native paths share their root grid; a separate grid
                # would detach the continuation from its prerequisite row.
                parent = BRANCH_CONTINUATIONS[branch.key]
                layout = next(item for item in branch_layouts if item[0].key == parent)
                branch_layouts.append((branch, *layout[1:]))
                continue
            graph = BRANCH_GRAPHS[branch.key]
            grid_height = (
                (max(graph.lanes) - min(graph.lanes) + 1)
                * HORIZONTAL_LANE_SLOT_MULTIPLIER
                * GRID_SLOT
            )
            branch_layouts.append((branch, GRID_X, cursor_y, grid_width, grid_height))
            branch_gap = INFANTRY_BRANCH_GAP if folder == "infantry_folder" else BRANCH_GAP
            cursor_y += grid_height + branch_gap
        content_width = max(1180, GRID_X + grid_width + 80)
        height = max(700, cursor_y + 80)
    else:
        cursor_x = GRID_X
        for branch in branches:
            if branch.key in CIVIL_TREE_ATTACHMENTS:
                continue
            members = vertical_tree_branches(branch)
            grid_height = (
                max(
                    technology_time_slot(member, i)
                    for member in members
                    for i in range(len(member.techs))
                )
                + 2
            ) * GRID_SLOT
            grid_width = vertical_tree_span(branch) * GRID_SLOT
            vertical_tree_layouts[branch.key] = (cursor_x, GRID_Y, grid_width, grid_height)
            for member in members:
                branch_layouts.append((
                    member,
                    cursor_x + vertical_branch_offset(member) * GRID_SLOT,
                    GRID_Y,
                    vertical_branch_span(member) * GRID_SLOT,
                    grid_height,
                ))
            cursor_x += grid_width + BRANCH_GAP
        content_width = max(1180, cursor_x + 80)
        height = max(700, GRID_Y + max(layout[4] for layout in branch_layouts) + 100)
    # Vanilla folder art embeds a fixed diagram unrelated to these branches.
    background = "GFX_ADISCORD_technology_transparent_tile"
    lines = [
        "\t\tcontainerWindowType = {",
        f"\t\t\tname = \"{folder}\"",
        "\t\t\tposition = { x = 0 y = 47 }",
        "\t\t\tsize = { width = 100%% height = 100%% }",
        "\t\t\tmargin = { top = 13 left = 13 bottom = 24 right = 25 }",
        "\t\t\tdrag_scroll = { left middle }",
        "\t\t\tverticalScrollbar = \"right_vertical_slider\"",
        "\t\t\thorizontalScrollbar = \"bottom_horizontal_slider\"",
        "\t\t\tscroll_wheel_factor = 40",
        "\t\t\tbackground = { name = \"Background\" quadTextureSprite = \"GFX_tiled_window_2b_border\" }",
        "\t\t\tcontainerWindowType = {",
        "\t\t\t\tname = \"techtree_stripes\"",
        "\t\t\t\tposition = { x = 0 y = 0 }",
        f"\t\t\t\tsize = {{ width = {content_width} height = {height} min = {{ width = 100%% height = 100%% }} }}",
        "\t\t\t\tclipping = no",
        "\t\t\t\tbackground = { name = \"Background\" quadTextureSprite = \"GFX_techtree_stripes\" }",
        "\t\t\t\ticonType = {",
        "\t\t\t\t\tname = \"ADISCORD_tech_background\"",
        f"\t\t\t\t\tspriteType = \"{background}\"",
        "\t\t\t\t\tposition = { x = 0 y = 0 }",
        "\t\t\t\t\talwaystransparent = yes",
        "\t\t\t\t}",
    ]
    # Connected vertical programmes share dated rows; each heading repeats the
    # ruler locally so dates remain visible while scrolling a wide tree.
    if horizontal:
        year_labels = [
            (
                str(year) if occurrence == 0 else f"{year}_{occurrence}",
                year,
                GRID_X
                + chronological_grid_slot(
                    year, horizontal=True, folder=folder, occurrence=occurrence
                ) * GRID_SLOT
                + (GRID_SLOT - YEAR_LABEL_WIDTH) // 2,
                84,
            )
            for year, occurrence in horizontal_year_columns(folder)
        ]
    else:
        year_labels = [
            (
                f"{branch.key}_{year}",
                year,
                grid_x - 62,
                grid_y
                + technology_time_slot(branch, branch.years.index(year)) * GRID_SLOT
                + (GRID_SLOT - YEAR_LABEL_HEIGHT) // 2,
            )
            for branch, grid_x, grid_y, _, _ in branch_layouts
            for year in sorted(set(branch.years))
        ]
    for label, year, year_x, year_y in year_labels:
        lines.extend(
            (
                "\t\t\t\tinstantTextBoxType = {",
                f"\t\t\t\t\tname = \"ADISCORD_{folder}_year_{label}\"",
                f"\t\t\t\t\tposition = {{ x = {year_x} y = {year_y} }}",
                "\t\t\t\t\tfont = \"hoi_18b\"",
                f"\t\t\t\t\ttext = \"{year}\"",
                f"\t\t\t\t\tmaxWidth = {YEAR_LABEL_WIDTH}",
                f"\t\t\t\t\tmaxHeight = {YEAR_LABEL_HEIGHT}",
                f"\t\t\t\t\tformat = {'center' if horizontal else 'left'}",
                "\t\t\t\t\tOrientation = \"UPPER_LEFT\"",
                "\t\t\t\t}",
            )
        )
    # Technology grid boxes must be direct children of the folder container.
    # The game does not discover grids nested inside the decorative
    # ``techtree_stripes`` container and reports every technology as having
    # no grid box even when the grid name itself is correct.
    lines.append("\t\t\t}")
    if folder == SPECIAL_TECHNOLOGY_FOLDER:
        lines.extend(
            (
                "\t\t\tinstantTextBoxType = {",
                '\t\t\t\tname = "ADISCORD_special_technology_access_note"',
                '\t\t\t\tposition = { x = 88 y = 15 }',
                '\t\t\t\tfont = "hoi_16mbs"',
                f'\t\t\t\ttext = "{SPECIAL_TECHNOLOGY_FOLDER}_desc"',
                "\t\t\t\tmaxWidth = 900",
                "\t\t\t\tmaxHeight = 48",
                "\t\t\t\tformat = left",
                "\t\t\t}",
            )
        )
    for branch, grid_x, grid_y, grid_width, grid_height in branch_layouts:
        if horizontal:
            title_x = grid_x
            if branch.key in BRANCH_CONTINUATIONS:
                title_x += technology_time_slot(branch, 0) * GRID_SLOT
            title_y = grid_y - 30
            title_width = min(900, grid_width)
            title_format = "left"
        else:
            title_x = grid_x
            title_y = 76
            title_width = grid_width
            title_format = "center"
        lines.extend(
            (
                "\t\t\tinstantTextBoxType = {",
                f"\t\t\t\tname = \"ADISCORD_branch_{branch.key}\"",
                f"\t\t\t\tposition = {{ x = {title_x} y = {title_y} }}",
                "\t\t\t\tfont = \"hoi_18b\"",
                f"\t\t\t\ttext = \"ADISCORD_TECH_BRANCH_{branch.key.upper()}\"",
                f"\t\t\t\tmaxWidth = {title_width}",
                "\t\t\t\tmaxHeight = 24",
                f"\t\t\t\tformat = {title_format}",
                "\t\t\t\tOrientation = \"UPPER_LEFT\"",
                "\t\t\t}",
            )
        )
        if branch.key in BRANCH_CONTINUATIONS or branch.key in CIVIL_TREE_ATTACHMENTS:
            continue
        if not horizontal:
            grid_x, grid_y, grid_width, grid_height = vertical_tree_layouts[branch.key]
        lines.extend(
            (
                "\t\t\tgridboxtype = {",
                f"\t\t\t\tname = \"{branch.techs[0].id}_tree\"",
                f"\t\t\t\tposition = {{ x = {grid_x} y = {grid_y} }}",
                f"\t\t\t\tsize = {{ width = {grid_width} height = {grid_height} }}",
                f"\t\t\t\tslotsize = {{ width = {GRID_SLOT} height = {GRID_SLOT} }}",
                f"\t\t\t\tformat = \"{folder_grid_format(folder)}\"",
                "\t\t\t}",
            )
        )
    lines.append("\t\t}")
    return "\n".join(lines)


def render_special_technology_tab() -> str:
    return "\n".join(
        (
            "\t\t\tbuttonType = {",
            f'\t\t\t\tname = "{SPECIAL_TECHNOLOGY_FOLDER}_tab"',
            "\t\t\t\tposition = { x = 823 y = 0 }",
            '\t\t\t\tquadTextureSprite = "GFX_secret_weapons_folder_tab"',
            "\t\t\t\tframe = 1",
            "\t\t\t\tclicksound = ui_research_tab_engineering",
            "\t\t\t}",
        )
    )


def render_tree_gui() -> str:
    base_gui = BASE_GAME / "interface" / "countrytechtreeview.gui"
    source = (
        base_gui
        if base_gui.exists()
        else ROOT / "interface" / "countrytechtreeview.gui"
    )
    text = source.read_text(encoding="utf-8-sig")
    starts = [
        match.start() for match in re.finditer(r"containerWindowType\s*=\s*\{", text)
    ]
    replacements: list[tuple[int, int, str]] = []
    found: set[str] = set()
    named_blocks: dict[str, tuple[int, int, str]] = {}
    for start in starts:
        open_brace = text.find("{", start)
        end = find_block_end(text, open_brace)
        head = text[open_brace + 1 : min(end, open_brace + 300)]
        name_match = re.search(r"\bname\s*=\s*\"([^\"]+)\"", head)
        if not name_match:
            continue
        name = name_match.group(1)
        named_blocks[name] = (start, end, text[start:end])
        if name in FOLDER_BACKGROUNDS:
            # Replace indentation with the generated block instead of adding
            # another prefix on every repository-GUI regeneration.
            line_start = text.rfind("\n", 0, start) + 1
            if text[line_start:start].strip():
                raise ValueError(f"Technology folder {name} must begin on its own line")
            replacements.append((line_start, end, render_folder(name)))
            found.add(name)
    missing = set(FOLDER_BACKGROUNDS) - found - {SPECIAL_TECHNOLOGY_FOLDER}
    if missing:
        raise ValueError(f"Missing technology folder containers: {sorted(missing)}")

    tabs_start, tabs_end, tabs = named_blocks["folder_tabs"]
    if SPECIAL_TECHNOLOGY_FOLDER not in found:
        line_start = text.rfind("\n", 0, tabs_start) + 1
        replacements.append(
            (line_start, line_start, render_folder(SPECIAL_TECHNOLOGY_FOLDER) + "\n\n")
        )
    if f'name = "{SPECIAL_TECHNOLOGY_FOLDER}_tab"' not in tabs:
        tabs = tabs.rstrip()[:-1].rstrip() + "\n\n" + render_special_technology_tab() + "\n\t\t}"
        replacements.append((tabs_start, tabs_end, tabs))

    # Native lookup requires both item templates for every custom folder.
    new_templates = []
    for suffix in ("item", "small_item"):
        source_name = f"techtree_infantry_folder_{suffix}"
        target_name = f"techtree_{SPECIAL_TECHNOLOGY_FOLDER}_{suffix}"
        template = named_blocks[source_name][2].replace(source_name, target_name, 1)
        template = "\n".join(line.rstrip() for line in template.splitlines())
        if target_name in named_blocks:
            start, end, _ = named_blocks[target_name]
            replacements.append((start, end, template))
        else:
            new_templates.append("\t" + template)
    if new_templates:
        end = text.rfind("}")
        replacements.append((end, end, "\n\n".join(new_templates) + "\n\n"))

    # Industry and electronics contain no production-equipment unlocks, so
    # their vanilla 204x72 all-purpose item would incorrectly make every
    # abstract method look like a vehicle model. Reuse the complete 72x72
    # small-item template there. Infantry, support, armor, artillery, air, and
    # naval folders retain both templates: equipment unlocks are wide, while
    # stat/method technologies are compact.
    compact_source_name = "techtree_infantry_folder_small_item"
    compact_targets = (
        "techtree_industry_folder_item",
        "techtree_electronics_folder_item",
    )
    if compact_source_name not in named_blocks:
        raise ValueError(f"Missing GUI template {compact_source_name}")
    compact_source = named_blocks[compact_source_name][2]
    for target in compact_targets:
        if target not in named_blocks:
            raise ValueError(f"Missing GUI template {target}")
        compact = re.sub(
            rf'(\bname\s*=\s*"){re.escape(compact_source_name)}(")',
            rf'\g<1>{target}\g<2>',
            compact_source,
            count=1,
        )
        start, end, _ = named_blocks[target]
        replacements.append((start, end, compact))
    # Native naval cards reserve a 300px label area. These trees use the same
    # 183px equipment cards and 70px connectors as the other generated folders.
    naval_source_name = "techtree_infantry_folder_item"
    naval_source = "\n".join(line.rstrip() for line in named_blocks[naval_source_name][2].splitlines())
    for target in ("techtree_naval_folder_item", "techtree_mtgnavalfolder_item"):
        card = naval_source.replace(naval_source_name, target, 1)
        card = card.replace('font = "hoi_20bs"', 'font = "hoi_16mbs"')
        start, end, _ = named_blocks[target]
        replacements.append((start, end, card))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    text = apply_tree_skin(text)
    return text


def write_gui() -> None:
    (ROOT / "interface" / "countrytechtreeview.gui").write_text(render_tree_gui(), encoding="utf-8")


def render_technology_migration_manifest() -> str:
    payload = {
        "schema": 1,
        "legacy_count": len(TECHNOLOGY_ID_MIGRATIONS),
        "current_count": len(CURRENT_TECH_IDS),
        "migrations": {
            tech_id: TECHNOLOGY_ID_MIGRATIONS[tech_id]
            for tech_id in sorted(TECHNOLOGY_ID_MIGRATIONS)
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_technology_migration_manifest() -> None:
    path = ROOT / "tools/data/adiscord_technology_id_migrations.json"
    path.write_text(render_technology_migration_manifest(), encoding="utf-8")


def replace_named_gui_block(text: str, name: str, replacement: str) -> str:
    match = re.search(rf'\bname\s*=\s*"{re.escape(name)}"', text)
    if match is None:
        raise ValueError(f"Missing technology folder {name}")
    start = text.rfind("containerWindowType = {", 0, match.start())
    if start < 0:
        raise ValueError(f"Missing container for {name}")
    while start > 0 and text[start - 1] in "\t ":
        start -= 1
    end = find_block_end(text, text.index("{", start))
    prefix, suffix = text[:start], text[end:]
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    if suffix and not suffix.startswith("\n"):
        suffix = "\n" + suffix
    return prefix + replacement + suffix


def civil_technology_outputs() -> dict[Path, bytes]:
    """Render civil research without re-exporting unrelated country artwork.

    Shared files preserve non-civil definitions. The normal full builder remains
    their owner; this mode limits updates to the two researched folders.
    """
    branches = [branch for branch in BRANCHES if branch.file in CIVIL_TECHNOLOGY_FILES]
    outputs = {
        path: text.encode("utf-8")
        for path, text in technology_file_outputs().items()
        if path.name in CIVIL_TECHNOLOGY_FILES
    }
    gui_path = ROOT / "interface/countrytechtreeview.gui"
    gui = gui_path.read_text(encoding="utf-8")
    for folder in ("industry_folder", "electronics_folder"):
        gui = replace_named_gui_block(gui, folder, render_folder(folder))
    outputs[gui_path] = apply_tree_skin(gui).encode("utf-8")

    gfx_path = ROOT / "interface/ADISCORD_technologies.gfx"
    gfx = gfx_path.read_text(encoding="utf-8")
    for branch in branches:
        for index, tech in enumerate(branch.techs):
            name = f"GFX_{tech.id}_medium"
            icon = icon_for_technology(branch, index)
            sprite = (
                "\tSpriteType = {\n"
                f'\t\tname = "{name}"\n'
                f'\t\ttextureFile = "gfx/interface/technologies/{icon}.dds"\n'
                "\t}"
            )
            pattern = rf'(?im)^\tSpriteType\s*=\s*\{{\s*name\s*=\s*"{re.escape(name)}"[^}}]*\}}'
            if re.search(pattern, gfx):
                gfx = re.sub(pattern, lambda _: sprite, gfx, count=1)
            else:
                closing = gfx.rfind("}")
                gfx = gfx[:closing] + sprite + "\n" + gfx[closing:]
    outputs[gfx_path] = gfx.encode("utf-8")

    keys = {
        key
        for branch in branches
        for tech in branch.techs
        for key in (tech.id, f"{tech.id}_desc")
    }
    keys.update(f"ADISCORD_TECH_BRANCH_{branch.key.upper()}" for branch in branches)
    key_pattern = re.compile(r"^\s+([A-Za-z0-9_]+)\s*:")
    for language in ("russian", "english"):
        path = ROOT / f"localisation/{language}/ADISCORD_technology_doctrine_l_{language}.yml"
        original = path.read_text(encoding="utf-8-sig").splitlines()
        preserved = [line for line in original if not ((match := key_pattern.match(line)) and match[1] in keys)]
        selected = [line for line in generated_localisation(language) if (match := key_pattern.match(line)) and match[1] in keys]
        text = "\n".join(preserved).rstrip() + "\n\n" + "\n".join(selected) + "\n"
        outputs[path] = text.encode("utf-8-sig")

    outputs[ROOT / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt"] = render_starting_technology_effect().encode("utf-8")
    outputs[ROOT / "tools/data/adiscord_starting_technology_profiles.json"] = render_starting_technology_profile_manifest().encode("utf-8")
    outputs[ROOT / "tools/data/adiscord_technology_id_migrations.json"] = render_technology_migration_manifest().encode("utf-8")
    return outputs


def selected_land_technology_outputs(file_name: str, extra_keys: set[str]) -> dict[Path, bytes]:
    """Regenerate a land research file, its sprites and selected localisation."""
    branches = [branch for branch in BRANCHES if branch.file == file_name]
    outputs = {
        path: text.encode("utf-8")
        for path, text in technology_file_outputs().items()
        if path.name == file_name
    }
    gfx_path = ROOT / "interface/ADISCORD_technologies.gfx"
    gfx = gfx_path.read_text(encoding="utf-8")
    for branch in branches:
        for index, tech in enumerate(branch.techs):
            name = f"GFX_{tech.id}_medium"
            icon = icon_for_technology(branch, index)
            # Existing sprites differ in field spacing, but keep their other fields.
            pattern = rf'(name\s*=\s*"{re.escape(name)}"\s+textureFile\s*=\s*")[^"]+(")'
            gfx, count = re.subn(
                pattern,
                lambda match: match[1] + f"gfx/interface/technologies/{icon}.dds" + match[2],
                gfx,
                count=1,
                flags=re.IGNORECASE,
            )
            if count == 0:
                sprite = (
                    "\tSpriteType = {\n"
                    f'\t\tname = "{name}"\n'
                    f'\t\ttextureFile = "gfx/interface/technologies/{icon}.dds"\n'
                    "\t}\n"
                )
                closing = gfx.rfind("}")
                gfx = gfx[:closing] + sprite + gfx[closing:]
    outputs[gfx_path] = gfx.encode("utf-8")
    keys = set(extra_keys)
    for branch in branches:
        keys.add(f"ADISCORD_TECH_BRANCH_{branch.key.upper()}")
        for tech in branch.techs:
            keys.update((tech.id, f"{tech.id}_desc", f"{tech.id}_leader_effect_tt"))
    key_pattern = re.compile(r"^\s+([A-Za-z0-9_]+)\s*:")
    for language in ("russian", "english"):
        path = ROOT / f"localisation/{language}/ADISCORD_technology_doctrine_l_{language}.yml"
        replacements = {}
        for line in generated_localisation(language):
            match = key_pattern.match(line)
            if match and match[1] in keys:
                replacements[match[1]] = line
        lines = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = key_pattern.match(line)
            key = match[1] if match else None
            lines.append(replacements.pop(key, line))
        lines.extend(replacements.values())
        outputs[path] = ("\n".join(lines) + "\n").encode("utf-8-sig")
    return outputs


def air_technology_outputs() -> dict[Path, bytes]:
    outputs = selected_land_technology_outputs("ADISCORD_air.txt", set(AIR_ROLE_LOCALISATION))
    gui_path = ROOT / "interface/countrytechtreeview.gui"
    gui = gui_path.read_text(encoding="utf-8")
    for folder in ("air_techs_folder", "bba_air_techs_folder"):
        gui = replace_named_gui_block(gui, folder, render_folder(folder))
    outputs[gui_path] = apply_tree_skin(gui).encode("utf-8")
    return outputs


def artillery_technology_outputs() -> dict[Path, bytes]:
    outputs = selected_land_technology_outputs("ADISCORD_artillery.txt", set(ARTILLERY_LOCALISATION))
    gui_path = ROOT / "interface/countrytechtreeview.gui"
    gui = replace_named_gui_block(
        gui_path.read_text(encoding="utf-8"), "artillery_folder", render_folder("artillery_folder")
    )
    outputs[gui_path] = apply_tree_skin(gui).encode("utf-8")
    return outputs


def armor_technology_outputs() -> dict[Path, bytes]:
    keys = set(ARMOR_UNIT_LOCALISATION)
    for model in ("ADISCORD_combat_platform_2150", "ADISCORD_heavy_combat_platform_2158"):
        keys.update((model, f"{model}_short", f"{model}_desc"))
    return selected_land_technology_outputs("ADISCORD_armor.txt", keys)


def support_technology_outputs() -> dict[Path, bytes]:
    keys = {
        suffix
        for unit in ("ADISCORD_militia", "ADISCORD_territorial", "recon", "military_police")
        for suffix in (unit, f"{unit}_desc")
    }
    outputs = selected_land_technology_outputs("ADISCORD_logistics_trains.txt", keys)
    gui_path = ROOT / "interface/countrytechtreeview.gui"
    gui = replace_named_gui_block(
        gui_path.read_text(encoding="utf-8"), "support_folder", render_folder("support_folder")
    )
    outputs[gui_path] = apply_tree_skin(gui).encode("utf-8")
    outputs[ROOT / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt"] = render_starting_technology_effect().encode("utf-8")
    outputs[ROOT / "tools/data/adiscord_starting_technology_profiles.json"] = render_starting_technology_profile_manifest().encode("utf-8")
    outputs[ROOT / "tools/data/adiscord_technology_id_migrations.json"] = render_technology_migration_manifest().encode("utf-8")
    return outputs


def apply() -> None:
    ensure_technology_state_gfx_current()
    all_ids = [tech.id for branch in BRANCHES for tech in branch.techs]
    duplicates = sorted({tech_id for tech_id in all_ids if all_ids.count(tech_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate technology IDs: {duplicates}")
    write_technology_files()
    write_technology_folder_tags()
    write_starting_technology_effect()
    write_naval_hull_cards()
    write_gfx()
    for path, content in infantry_card_outputs().items():
        if not path.is_file() or path.read_bytes() != content:
            path.write_bytes(content)
    for path, content in aircraft_icon_outputs().items():
        if not path.is_file() or path.read_bytes() != content:
            path.write_bytes(content)
    write_localisation()
    for path, content in country_equipment_localisation_outputs().items():
        if path.read_bytes() != content:
            path.write_bytes(content)
    write_gui()
    write_technology_migration_manifest()
    write_starting_technology_profile_manifest()
    print(
        f"Generated {len(all_ids)} technologies in {len(BRANCHES)} content branches; "
        f"{len(SIDE_PROGRAMME_KEYS)} branches are attached specialisations."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the A-Discord technology system."
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="validate current generated outputs (default)",
    )
    actions.add_argument(
        "--apply",
        action="store_true",
        help="write technology files, manifests, GUI and localisation",
    )
    actions.add_argument(
        "--apply-starting-profiles",
        action="store_true",
        help="write only starting technology effects and the country profile manifest",
    )
    parser.add_argument(
        "--air-only", action="store_true",
        help="check or apply aviation research, both air tabs and role descriptions",
    )
    parser.add_argument(
        "--artillery-only", action="store_true",
        help="check or apply artillery, anti-tank and anti-air research and their tab",
    )
    parser.add_argument(
        "--support-only", action="store_true",
        help="check or apply support research, its tab and unit descriptions",
    )
    parser.add_argument(
        "--armor-only", action="store_true",
        help="check or apply armor research and its localisation only",
    )
    parser.add_argument(
        "--civil-only", action="store_true",
        help="check or apply industry/electronics and their shared definitions without exporting unrelated artwork",
    )
    parser.add_argument(
        "--technology-data-only",
        action="store_true",
        help="check or apply technology scripts without regenerating UI, localisation or country history",
    )
    parser.add_argument(
        "--aircraft-icons-only",
        action="store_true",
        help="check or apply supplied country aircraft cards and their GFX routes",
    )
    parser.add_argument(
        "--aircraft-role", choices=("all", "fighter", "cas"), default="all",
        help="limit aircraft card conversion to one role with --aircraft-icons-only",
    )
    parser.add_argument(
        "--weapon-icons-only",
        action="store_true",
        help="check or apply weapon category sprites without rebuilding other UI",
    )
    parser.add_argument(
        "--uniform-icons-only",
        action="store_true",
        help="check or apply country uniform sprites and names without rebuilding other UI",
    )
    parser.add_argument(
        "--equipment-names-only", action="store_true",
        help="check or apply equipment and technology localisation only",
    )
    parser.add_argument(
        "--night-icons-only",
        action="store_true",
        help="check or apply night combat sprites without rebuilding other UI",
    )
    parser.add_argument(
        "--protection-icons-only",
        action="store_true",
        help="check or apply protective equipment sprites without rebuilding other UI",
    )
    parser.add_argument(
        "--gui-only", action="store_true",
        help="check or apply the technology tree GUI without gameplay outputs",
    )
    parser.add_argument(
        "--infantry-cards-only", action="store_true",
        help="check or apply supplied infantry equipment cards and their GFX routes",
    )
    parser.add_argument(
        "--apc-icons-only", action="store_true",
        help="check or apply country APC sprites without rebuilding other UI",
    )
    args = parser.parse_args()
    if args.apc_icons_only:
        if any(value for key, value in vars(args).items()
               if key not in {"check", "apply", "apc_icons_only", "aircraft_role"}) or args.aircraft_role != "all":
            parser.error("--apc-icons-only cannot be combined with other partial output modes")
        for texture in COUNTRY_APC_CARD_TEXTURES.values():
            with Image.open(ROOT / texture) as image:
                if image.mode != "RGBA" or image.size != (176, 72):
                    raise ValueError(f"APC card must be 176x72 RGBA: {texture}")
        path = ROOT / "interface/ADISCORD_technologies.gfx"
        content = apc_gfx_output()
        changed = path.read_bytes() != content
        if args.apply and changed:
            path.write_bytes(content)
        print(f"Country APC sprites {'updated' if args.apply else 'different'}: {int(changed)}")
        return int(changed and not args.apply)
    if args.air_only:
        if any(value for key, value in vars(args).items()
               if key not in {"check", "apply", "air_only", "aircraft_role"}) or args.aircraft_role != "all":
            parser.error("--air-only cannot be combined with other partial output modes")
        outputs = air_technology_outputs()
        changed = [path for path, data in outputs.items() if path.read_bytes() != data]
        if args.apply:
            for path in changed:
                path.write_bytes(outputs[path])
        print(f"Aviation outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.artillery_only:
        if any(value for key, value in vars(args).items()
               if key not in {"check", "apply", "artillery_only", "aircraft_role"}) or args.aircraft_role != "all":
            parser.error("--artillery-only cannot be combined with other partial output modes")
        outputs = artillery_technology_outputs()
        changed = [path for path, data in outputs.items() if path.read_bytes() != data]
        if args.apply:
            for path in changed:
                path.write_bytes(outputs[path])
        print(f"Artillery outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.support_only:
        if any(value for key, value in vars(args).items()
               if key not in {"check", "apply", "support_only", "aircraft_role"}) or args.aircraft_role != "all":
            parser.error("--support-only cannot be combined with other partial output modes")
        outputs = support_technology_outputs()
        changed = [path for path, data in outputs.items() if path.read_bytes() != data]
        if args.apply:
            for path in changed:
                path.write_bytes(outputs[path])
        print(f"Support outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.armor_only:
        if any(value for key, value in vars(args).items()
               if key not in {"check", "apply", "armor_only", "aircraft_role"}):
            parser.error("--armor-only cannot be combined with other partial output modes")
        outputs = armor_technology_outputs()
        changed = [path for path, data in outputs.items() if path.read_bytes() != data]
        if args.apply:
            for path in changed:
                path.write_bytes(outputs[path])
        print(f"Armor outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.civil_only:
        other_modes = {
            key: value for key, value in vars(args).items()
            if key not in {"check", "apply", "civil_only", "aircraft_role"}
        }
        if any(other_modes.values()) or args.aircraft_role != "all":
            parser.error("--civil-only cannot be combined with other partial output modes")
        outputs = civil_technology_outputs()
        changed = [path for path, data in outputs.items() if not path.exists() or path.read_bytes() != data]
        if args.apply:
            for path in changed:
                path.write_bytes(outputs[path])
        print(f"Civil technology outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT).as_posix())
        return 0 if args.apply or not changed else 1
    if args.infantry_cards_only:
        if (args.gui_only or args.technology_data_only or args.aircraft_icons_only
                or args.weapon_icons_only or args.uniform_icons_only or args.equipment_names_only
                or args.night_icons_only or args.protection_icons_only
                or args.apply_starting_profiles or args.aircraft_role != "all"):
            parser.error("--infantry-cards-only cannot be combined with other partial output modes")
        changed = []
        for path, content in infantry_card_outputs().items():
            if not path.is_file() or path.read_bytes() != content:
                changed.append(path)
                if args.apply:
                    path.write_bytes(content)
        print(f"Infantry card outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.gui_only:
        if (args.technology_data_only or args.aircraft_icons_only or args.weapon_icons_only
                or args.uniform_icons_only or args.equipment_names_only or args.night_icons_only
                or args.protection_icons_only or args.apply_starting_profiles):
            parser.error("--gui-only cannot be combined with other partial output modes")
        path = ROOT / "interface/countrytechtreeview.gui"
        content = render_tree_gui()
        changed = path.read_text(encoding="utf-8") != content
        if args.apply and changed:
            write_gui()
        print(f"Technology GUI {'updated' if args.apply else 'different'}: {int(changed)}")
        return int(changed and not args.apply)
    if args.aircraft_role != "all" and not args.aircraft_icons_only:
        parser.error("--aircraft-role requires --aircraft-icons-only")
    if args.night_icons_only or args.protection_icons_only:
        if args.night_icons_only and args.protection_icons_only:
            parser.error("select only one infantry icon branch")
        if (args.weapon_icons_only or args.uniform_icons_only or args.aircraft_icons_only
                or args.equipment_names_only or args.technology_data_only
                or args.apply_starting_profiles):
            parser.error("infantry icon branches cannot be combined with other partial output modes")
        path = ROOT / "interface/ADISCORD_technologies.gfx"
        branch_key = "protection" if args.protection_icons_only else "night_combat"
        content = weapon_category_gfx_output(branch_key)
        changed = path.read_text(encoding="utf-8") != content
        if args.apply and changed:
            path.write_text(content, encoding="utf-8")
        print(f"{branch_key} sprites {'updated' if args.apply else 'different'}: {int(changed)}")
        return int(changed and not args.apply)
    if args.equipment_names_only:
        if args.uniform_icons_only or args.aircraft_icons_only or args.weapon_icons_only or args.technology_data_only or args.apply_starting_profiles:
            parser.error("--equipment-names-only cannot be combined with other partial output modes")
        changed = []
        for path, content in country_equipment_localisation_outputs().items():
            if path.read_bytes() != content:
                changed.append(path)
                if args.apply:
                    path.write_bytes(content)
        print(f"Country equipment names {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.uniform_icons_only:
        if args.aircraft_icons_only or args.weapon_icons_only or args.technology_data_only or args.apply_starting_profiles:
            parser.error("--uniform-icons-only cannot be combined with other partial output modes")
        path = ROOT / "interface/ADISCORD_technologies.gfx"
        original_bytes = path.read_bytes()
        current = path.read_text(encoding="utf-8")
        content = with_country_uniform_gfx(current)
        outputs = country_uniform_localisation_outputs()
        if b"\r\n" in original_bytes:
            content = content.replace("\n", "\r\n")
        outputs[path] = content.encode("utf-8")
        changed = []
        for path, content in outputs.items():
            if path.read_bytes() != content:
                changed.append(path)
                if args.apply:
                    path.write_bytes(content)
        print(f"Country uniform outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.aircraft_icons_only:
        if args.weapon_icons_only or args.technology_data_only or args.apply_starting_profiles:
            parser.error("--aircraft-icons-only cannot be combined with other partial output modes")
        changed = []
        for path, content in aircraft_icon_outputs(args.aircraft_role).items():
            if not path.is_file() or path.read_bytes() != content:
                changed.append(path)
                if args.apply:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
        print(f"Aircraft card outputs {'updated' if args.apply else 'different'}: {len(changed)}")
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.weapon_icons_only:
        if args.technology_data_only or args.apply_starting_profiles:
            parser.error(
                "--weapon-icons-only cannot be combined with other partial output modes"
            )
        path = ROOT / "interface" / "ADISCORD_technologies.gfx"
        content = weapon_category_gfx_output()
        changed = path.read_text(encoding="utf-8") != content
        if args.apply and changed:
            path.write_text(content, encoding="utf-8")
        print(
            f"Weapon category sprites {'updated' if args.apply else 'different'}: {int(changed)}"
        )
        return int(changed and not args.apply)
    if args.technology_data_only:
        if args.apply_starting_profiles:
            parser.error("--technology-data-only cannot update starting profiles")
        changed = [
            path
            for path, content in technology_file_outputs().items()
            if not path.exists() or path.read_text(encoding="utf-8-sig") != content
        ]
        if args.apply:
            write_technology_files()
        print(
            f"Technology scripts {'updated' if args.apply else 'different'}: {len(changed)}"
        )
        for path in changed:
            print(path.relative_to(ROOT))
        return int(bool(changed) and not args.apply)
    if args.apply_starting_profiles:
        write_starting_technology_effect()
        write_starting_technology_profile_manifest()
        return 0
    if args.apply:
        apply()
        return 0
    ensure_technology_state_gfx_current()
    from tools.validators.validate_adiscord_tech_doctrine import main as validate_main

    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
