from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import json
import re

from tools.lib.paths import repository_root

ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
# The campaign starts in 2160. Keep only a short recovered baseline before
# that date, place the overwhelming majority of research in the playable
# 2160-2175 window, and leave one small 2180 endgame generation. This follows
# Darkest Hour's useful cadence: dense playable eras, not decades of empty
# waiting between otherwise interesting nodes.
LEGACY_YEARS = (
    2100, 2120, 2140, 2150,
    2160, 2162, 2164, 2166, 2168,
    2170, 2173, 2176, 2179,
    2182, 2185, 2188,
    2191, 2194, 2197, 2200,
)
YEARS = (
    2150, 2155, 2158,
    2160, 2161, 2162, 2163, 2164,
    2165, 2166, 2167, 2168,
    2169, 2170, 2171, 2172,
    2173, 2174, 2175,
    2180,
)
LEGACY_TO_CAMPAIGN_YEAR = dict(zip(LEGACY_YEARS, YEARS, strict=True))
MILESTONE_YEARS = tuple(
    LEGACY_TO_CAMPAIGN_YEAR[year]
    for year in (2100, 2120, 2140, 2160, 2170, 2182, 2200)
)
# Most tabs retain the compact vertical timeline. Infantry weapons and armor
# use a horizontal timeline so development reads left-to-right while each
# capability family keeps a stable row, matching their wider equipment cards.
YEAR_TO_Y = {year: index for index, year in enumerate(YEARS)}
GRID_X = 150
GRID_Y = 130
GRID_SLOT = 70
HORIZONTAL_LANE_SLOT = 96
LANE_SLOT_MULTIPLIER = 3
BRANCH_GAP = 90
HORIZONTAL_YEAR_SLOT_MULTIPLIER = 3
HORIZONTAL_FOLDERS = frozenset({
    "infantry_folder",
    "armour_folder",
    "nsb_armour_folder",
})


@dataclass(frozen=True)
class Tech:
    key: str
    ru: str
    en: str
    icon: str

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
            raise ValueError(f"{self.key}: {len(self.techs)} techs for {len(self.years)} years")


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
        "reconstruction", "ADISCORD_industry.txt", ("industry_folder",),
        "Реконструкция", "Reconstruction", "construction",
        techs("""
salvage_standards|Стандарты утилизации|Salvage Standards|basic_machine_tools
ruin_workshops|Мастерские среди руин|Ruin Workshops|improved_machine_tools
reconstruction_bureaus|Бюро реконструкции|Reconstruction Bureaus|basic_construction
modular_rebuilding|Модульная застройка|Modular Rebuilding|improved_construction
prefabricated_districts|Сборные кварталы|Prefabricated Districts|advanced_construction
automated_civil_works|Автоматизированные стройки|Automated Civil Works|construction4
arcology_repair_networks|Ремонтные сети аркологий|Arcology Repair Networks|construction5
"""),
    ),
    Branch(
        "production", "ADISCORD_industry.txt", ("industry_folder",),
        "Производство", "Production", "production",
        techs("""
standardized_machine_tools|Стандартные станки|Standardized Machine Tools|basic_machine_tools
interchangeable_components|Взаимозаменяемые узлы|Interchangeable Components|improved_machine_tools
industrial_cluster_planning|Промышленные кластеры|Industrial Cluster Planning|concentrated_industry1
automated_assembly|Автоматизированная сборка|Automated Assembly|assembly_line_production
predictive_maintenance|Предиктивное обслуживание|Predictive Maintenance|advanced_machine_tools
autonomous_factory_cells|Автономные заводские ячейки|Autonomous Factory Cells|flexible_line
distributed_manufacturing|Распределённое производство|Distributed Manufacturing|streamlined_line
"""),
    ),
    Branch(
        "resources", "ADISCORD_industry.txt", ("industry_folder",),
        "Ресурсы и энергия", "Resources and Energy", "resources",
        techs("""
salvage_metallurgy|Утилизационная металлургия|Salvage Metallurgy|excavation1
grid_rationing|Нормирование энергосети|Grid Rationing|oil_processing
refinery_reclamation|Восстановление НПЗ|Refinery Reclamation|improved_oil_processing
logistics_hub_networks|Сети логистических узлов|Logistics Hub Networks|excavation2
synthetic_resource_cycles|Синтетические циклы|Synthetic Resource Cycles|rubber_processing
closed_loop_smelting|Замкнутая выплавка|Closed-loop Smelting|excavation4
strategic_material_recovery|Извлечение редких материалов|Strategic Material Recovery|excavation5
"""),
    ),
    Branch(
        "finance", "ADISCORD_industry.txt", ("industry_folder",),
        "Финансы", "Public Finance", "finance",
        techs("""
basic_fiscal_records|Базовый фискальный учёт|Basic Fiscal Records|mechanical_computing
reconstruction_contracts|Контракты реконструкции|Reconstruction Contracts|basic_small_computer
state_debt_instruments|Государственные облигации|State Debt Instruments|improved_small_computer
reserve_management|Управление резервами|Reserve Management|basic_mainframe
fiscal_administration_1|Фискальная администрация I|Fiscal Administration I|improved_mainframe
fiscal_administration_2|Фискальная администрация II|Fiscal Administration II|advanced_mainframe
predictive_budgeting|Предиктивный бюджет|Predictive Budgeting|computing_machine
"""),
    ),
    Branch(
        "administration", "ADISCORD_industry.txt", ("industry_folder",),
        "Государственное управление", "State Administration", "administration",
        techs("""
municipal_ledgers|Муниципальные реестры|Municipal Ledgers|mechanical_computing
tax_census_network|Сеть налоговой переписи|Tax Census Network|basic_small_computer
standard_civil_codes|Единые гражданские нормы|Standard Civil Codes|improved_small_computer
technical_institutes|Технические институты|Technical Institutes|computing_machine
automated_bureaucracy|Автоматизированная бюрократия|Automated Bureaucracy|basic_mainframe
automated_civil_registry|Автоматический реестр|Automated Civil Registry|improved_mainframe
predictive_administration|Предиктивное управление|Predictive Administration|advanced_mainframe
"""),
    ),
    Branch(
        "civil_resilience", "ADISCORD_industry.txt", ("industry_folder",),
        "Гражданская устойчивость", "Civil Resilience", "civil",
        techs("""
modular_shelters|Модульные убежища|Modular Shelters|basic_construction
ration_distribution_systems|Распределение пайков|Ration Distribution Systems|basic_machine_tools
urban_radiation_sanitation|Дезактивация городов|Urban Radiation Sanitation|improved_construction
municipal_repair_depots|Муниципальные рембазы|Municipal Repair Depots|advanced_machine_tools
public_repair_corps|Общественные ремонтные корпуса|Public Repair Corps|construction4
population_resilience_planning|Устойчивость населения|Population Resilience Planning|construction5
civil_defense_networks|Комплексная гражданская оборона|Civil Defense Networks|concentrated_industry5
"""),
    ),
    Branch(
        "power", "ADISCORD_electronics.txt", ("electronics_folder",),
        "Энергетика и реакторы", "Power and Reactors", "power",
        techs("""
local_grid_restoration|Локальные энергосети|Local Grid Restoration|electrical_mechanical_engineering
substation_networks|Восстановление подстанций|Substation Networks|radio
radiation_mapping|Радиационное картирование|Radiation Mapping|atomic_research
shielded_engineering_corps|Экранированная инженерия|Shielded Engineering Corps|nuclear_reactor
reactor_safety_protocols|Безопасность реакторов|Reactor Safety Protocols|improved_nuclear_reactor
microreactor_blocks|Массивы микрореакторов|Microreactor Blocks|advanced_nuclear_reactor
emergency_core_suppression|Аварийное глушение ядра|Emergency Core Suppression|special_project_nuclear_reactor
"""),
    ),
    Branch(
        "signals", "ADISCORD_electronics.txt", ("electronics_folder",),
        "Связь и кибервойна", "Signals and Cyberwarfare", "signals",
        techs("""
mesh_command_networks|Ячеистые сети управления|Mesh Command Networks|radio
field_radio_networks|Полевые радиосети|Field Radio Networks|radio_detection
encryption_rebuild|Восстановление шифрования|Encryption Rebuild|encryption1
signal_intercept_arrays|Массивы радиоперехвата|Signal Intercept Arrays|decryption1
battlefield_analytics|Аналитика поля боя|Battlefield Analytics|encryption2
counterintelligence_filters|Автоматизация контрразведки|Counterintelligence Filters|decryption2
memetic_security_protocols|Протоколы меметической защиты|Memetic Security Protocols|encryption3
"""),
    ),
    Branch(
        "computing", "ADISCORD_electronics.txt", ("electronics_folder",),
        "Вычисления и ИИ", "Computing and AI", "computing",
        techs("""
electromechanical_relays|Электромеханические реле|Electromechanical Relays|mechanical_computing
recovered_data_archives|Восстановленные архивы|Recovered Data Archives|computing_machine
recovered_semiconductors|Восстановленные полупроводники|Recovered Semiconductors|basic_small_computer
hardened_computers|Защищённые вычислители|Hardened Computers|improved_small_computer
predictive_logistics|Предиктивная логистика|Predictive Logistics|basic_mainframe
operational_ai_assistants|Операционные ИИ-ассистенты|Operational AI Assistants|improved_mainframe
strategic_ai_coordination|Стратегическая ИИ-координация|Strategic AI Coordination|advanced_mainframe
"""),
    ),
    Branch(
        "forbidden_energy", "ADISCORD_forbidden.txt", ("electronics_folder",),
        "Запретная энергетика", "Forbidden Energy", "forbidden_energy",
        techs("""
old_generator_fragments|Фрагменты старого генератора|Old Generator Fragments|atomic_research
dead_reactor_salvage|Разбор мёртвых реакторов|Dead Reactor Salvage|nuclear_reactor
legacy_reactor_compactification|Компактификация реакторов|Legacy Reactor Compactification|improved_nuclear_reactor
dirty_energy_munitions|Боеприпасы грязной энергии|Dirty Energy Munitions|nuclear_bomb
singularity_cooling_systems|Сингулярное охлаждение|Singularity Cooling Systems|advanced_nuclear_reactor
black_grid_protocols|Протоколы чёрной энергосети|Black Grid Protocols|special_project_nuclear_reactor
"""),
        (2164, 2166, 2168, 2170, 2173, 2180),
    ),
    Branch(
        "forbidden_automation", "ADISCORD_forbidden.txt", ("electronics_folder",),
        "Запретная автоматизация", "Forbidden Automation", "forbidden_automation",
        techs("""
self_repairing_industrial_swarms|Самовосстанавливающиеся рои|Self-repairing Industrial Swarms|flexible_line
neural_command_cores|Нейронные командные ядра|Neural Command Cores|improved_mainframe
forbidden_automation_doctrine|Доктрина запретной автоматизации|Forbidden Automation Doctrine|advanced_mainframe
"""),
        (2168, 2172, 2180),
    ),
    Branch(
        "small_arms", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Винтовки и индивидуальное оружие", "Rifles and Individual Weapons", "infantry",
        techs("""
postwar_weapon_standardization|Стандартизация оружия|Weapon Standardization|infantry_equipment_0
refurbished_receivers|Восстановленные ствольные коробки|Refurbished Receivers|infantry_weapons
standardized_cartridges|Стандартные боеприпасы|Standardized Cartridges|infantry_weapons2
smart_optics|Умная оптика|Smart Optics|night_vision1
modular_rifle_kits|Модульные оружейные комплекты|Modular Rifle Kits|infantry_weapons3
programmable_ammunition|Программируемые боеприпасы|Programmable Ammunition|infantry_at2
networked_service_rifles|Сетевые штурмовые комплексы|Networked Service Rifles|night_vision2
"""),
    ),
    Branch(
        "squad_weapons", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Автоматическое и групповое оружие", "Automatic and Squad Weapons", "squad",
        techs("""
belt_fed_recovery|Восстановление ленточного оружия|Belt-fed Weapon Recovery|support_weapons
squad_grenade_launchers|Гранатомёты отделения|Squad Grenade Launchers|support_weapons2
portable_at_cells|Переносные противотанковые группы|Portable Anti-tank Cells|infantry_at
field_ew_units|Полевые подразделения РЭБ|Field EW Units|support_weapons3
networked_command_terminals|Сетевые командные терминалы|Networked Command Terminals|signal_company
autonomous_support_weapons|Автономное оружие поддержки|Autonomous Support Weapons|support_weapons4
swarm_fireteams|Роевые огневые группы|Swarm Fireteams|special_forces
"""),
    ),
    Branch(
        "protection", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Защита и медицина", "Protection and Medicine", "protection",
        techs("""
composite_protection_kits|Композитные комплекты защиты|Composite Protection Kits|tech_engineers
trauma_plates|Травмозащитные пластины|Trauma Plates|tech_field_hospital
sealed_combat_suits|Герметичные боевые костюмы|Sealed Combat Suits|tech_engineers2
battlefield_medical_drones|Медицинские дроны|Battlefield Medical Drones|tech_field_hospital2
exoskeleton_load_frames|Экзоскелетные рамы|Exoskeleton Load Frames|tech_engineers3
adaptive_camouflage|Адаптивная маскировка|Adaptive Camouflage|tech_recon3
assault_sapper_kits|Комплекты штурмовых сапёров|Assault Sapper Kits|tech_engineers4
"""),
    ),
    Branch(
        "special_forces", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Разведка и спецназ", "Reconnaissance and Special Forces", "special_forces",
        techs("""
fieldcraft_manuals|Полевые наставления|Fieldcraft Manuals|tech_recon
urban_breaching|Городской штурм|Urban Breaching|special_forces
radiation_patrols|Радиационные патрули|Radiation Patrols|tech_recon2
combat_recon_drones|Разведывательные дроны|Combat Recon Drones|paratroopers
vertical_assault_training|Вертикальный охват|Vertical Assault Training|paratroopers2
deep_recon_cells|Группы глубинной разведки|Deep Recon Cells|tech_recon4
augmented_special_forces|Усиленный спецназ|Augmented Special Forces|paratroopers3
"""),
    ),
    Branch(
        "field_support", "ADISCORD_logistics_trains.txt", ("support_folder",),
        "Полевое обеспечение", "Field Support", "support",
        techs("""
field_workshop_tools|Инструменты полевых мастерских|Field Workshop Tools|tech_maintenance_company
modular_support_kits|Модульные комплекты обеспечения|Modular Support Kits|tech_engineers
combat_engineering_sections|Инженерно-штурмовые отделения|Combat Engineering Sections|tech_engineers2
casualty_evacuation|Эвакуация раненых|Casualty Evacuation|tech_field_hospital2
remote_repair_teams|Дистанционные ремонтные группы|Remote Repair Teams|tech_maintenance_company3
autonomous_recovery|Автономная эвакуация техники|Autonomous Recovery|tech_maintenance_company4
self_sustaining_support|Самодостаточное обеспечение|Self-sustaining Support|tech_logistics_company4
"""),
    ),
    Branch(
        "logistics", "ADISCORD_logistics_trains.txt", ("support_folder",),
        "Моторизация и логистика", "Motorization and Logistics", "logistics",
        techs("""
pack_transport|Вьючный транспорт|Pack Transport|tech_logistics_company
restored_truck_fleets|Восстановленные автоколонны|Restored Truck Fleets|motorized_infantry
standardized_transport_columns|Стандартные транспортные колонны|Standardized Transport Columns|tech_logistics_company2
forward_supply_hubs|Передовые узлы снабжения|Forward Supply Hubs|tech_signal_company2
hardened_logistics_nodes|Защищённые логистические узлы|Hardened Logistics Nodes|tech_logistics_company3
route_optimization_ai|ИИ маршрутизации|Route Optimization AI|tech_signal_company3
zero_loss_logistics|Безотходная логистика|Zero-loss Logistics|tech_signal_company4
"""),
    ),
    Branch(
        "rail", "ADISCORD_logistics_trains.txt", ("support_folder",),
        "Железные дороги", "Railway Systems", "rail",
        techs("""
restored_rail_stock|Восстановленная тяга|Restored Rail Stock|train_tech
standard_gauge_recovery|Восстановление единой колеи|Standard Gauge Recovery|train_tech2
armored_rail_convoys|Бронированные эшелоны|Armored Rail Convoys|armored_train
railway_gun_reactivation|Реактивация железнодорожных орудий|Railway Gun Reactivation|railway_gun
rail_repair_corps|Корпуса ремонта путей|Rail Repair Corps|tech_engineers3
autonomous_rail_dispatch|Автономная диспетчеризация|Autonomous Rail Dispatch|train_tech3
over_the_horizon_fire_control|Загоризонтный огонь|Over-the-horizon Fire Control|railway_gun2
"""),
    ),
    Branch(
        "artillery", "ADISCORD_artillery.txt", ("artillery_folder",),
        "Полевая артиллерия", "Field Artillery", "artillery",
        techs("""
restored_field_artillery|Восстановленная артиллерия|Restored Field Artillery|artillery1
recoil_recovery|Восстановление противооткатных систем|Recoil Recovery|artillery2
modular_gun_carriages|Модульные лафеты|Modular Gun Carriages|artillery3
smart_fire_control|Умное управление огнём|Smart Fire Control|artillery4
assisted_projectiles|Корректируемые снаряды|Assisted Projectiles|artillery5
drone_spotted_batteries|Дроновая корректировка|Drone-spotted Batteries|rocket_artillery2
autonomous_battery_network|Автономная батарейная сеть|Autonomous Battery Network|rocket_artillery4
"""),
    ),
    Branch(
        "anti_tank", "ADISCORD_artillery.txt", ("artillery_folder",),
        "Противотанковые системы", "Anti-tank Systems", "anti_tank",
        techs("""
salvaged_at_guns|Трофейные противотанковые орудия|Salvaged Anti-tank Guns|antitank1
shaped_charges|Кумулятивные заряды|Shaped Charges|antitank2
tandem_warheads|Тандемные боевые части|Tandem Warheads|antitank3
scrap_at_launchers|Кустарные противотанковые орудия|Scrap Anti-tank Launchers|antitank4
top_attack_munitions|Боеприпасы верхней атаки|Top-attack Munitions|antitank5
coil_at_systems|Катушечные ускорители ПТО|Coil Anti-tank Systems|railgun
hypervelocity_at_networks|Сеть гиперскоростной ПТО|Hypervelocity Anti-tank Networks|special_project_land_railgun
"""),
    ),
    Branch(
        "anti_air", "ADISCORD_artillery.txt", ("artillery_folder",),
        "Противовоздушная оборона", "Air Defense", "anti_air",
        techs("""
improvised_air_defense|Импровизированная ПВО|Improvised Air Defense|antiair1
radar_laying|Радиолокационное наведение|Radar Laying|antiair2
proximity_fuzes|Радиовзрыватели|Proximity Fuzes|antiair3
point_defense_aa|Автопушки точечной обороны|Point-defense Air Defense|antiair4
networked_air_defense|Сетевая противовоздушная оборона|Networked Air Defense|antiair5
rail_assisted_aa|Рельсовые системы ПВО|Rail-assisted Air Defense|special_project_land_railgun
directed_energy_air_defense|Энергетическая противовоздушная оборона|Directed-energy Air Defense|special_project_thermonuclear_bomb
"""),
    ),
    Branch(
        "recon_armor", "ADISCORD_armor.txt", ("armour_folder", "nsb_armour_folder"),
        "Разведывательная бронетехника", "Reconnaissance Armor", "recon_armor",
        techs("""
restored_armored_chassis|Восстановленное лёгкое шасси|Restored Armored Chassis|gwtank
light_suspension|Облегчённая подвеска|Light Suspension|basic_light_tank
modular_recon_chassis|Модульное разведывательное шасси|Modular Recon Chassis|improved_light_tank
drone_recon_swarms|Беспилотные разведмашины|Drone Recon Swarms|advanced_light_tank
active_scouting_suites|Комплексы активной разведки|Active Scouting Suites|recon
unmanned_recon_vehicles|Необитаемые разведмашины|Unmanned Recon Vehicles|armored_car1
autonomous_recon_screen|Автономное разведывательное охранение|Autonomous Recon Screen|armored_car3
"""),
    ),
    Branch(
        "combat_armor", "ADISCORD_armor.txt", ("armour_folder", "nsb_armour_folder"),
        "Основные боевые танки", "Main Battle Tanks", "combat_armor",
        techs("""
recovered_medium_chassis|Восстановленное среднее шасси|Recovered Medium Chassis|basic_medium_tank
remote_weapon_stations|Дистанционно управляемые башенные установки|Remote-controlled Turret Mounts|improved_medium_tank
composite_armor_arrays|Массивы композитной брони|Composite Armor Arrays|advanced_medium_tank
semi_autonomous_combat_modules|Полуавтономное управление танком|Semi-autonomous Tank Control|basic_modern_tank
adaptive_fire_control|Адаптивное управление огнём|Adaptive Fire Control|improved_modern_tank
limited_battle_ai|Ограниченный боевой ИИ|Limited Battle AI|advanced_modern_tank
distributed_battlegroup|Распределённая бронегруппа|Distributed Battlegroup|generic_modern_tank
"""),
    ),
    Branch(
        "heavy_armor", "ADISCORD_armor.txt", ("armour_folder", "nsb_armour_folder"),
        "Тяжёлые и автономные танки", "Heavy and Autonomous Tanks", "heavy_armor",
        techs("""
heavy_recovery_frames|Тяжёлые ремонтные рамы|Heavy Recovery Frames|basic_heavy_tank
reinforced_powertrains|Усиленные силовые установки|Reinforced Powertrains|improved_heavy_tank
heavy_composite_cores|Тяжёлые композитные ядра|Heavy Composite Cores|advanced_heavy_tank
remote_repair_sections|Дистанционные ремонтные машины|Remote Repair Sections|maintenance_company
heavy_platform_cores|Усиленный корпус тяжёлого танка|Reinforced Heavy Tank Hull|super_heavy_tank
autonomous_breakthrough_platforms|Автономные танки прорыва|Autonomous Breakthrough Tanks|main_battle_tank
siege_platform_networks|Сеть осадных танков|Networked Siege Tanks|land_cruiser
"""),
    ),
    Branch(
        "fighter", "ADISCORD_air.txt", ("air_techs_folder", "bba_air_techs_folder"),
        "Истребительная авиация", "Fighter Aviation", "fighter",
        techs("""
reclaimed_jet_platforms|Восстановленные реактивные планеры|Reclaimed Jet Platforms|early_fighter
standardized_airframes|Стандартные планеры|Standardized Airframes|fighter1
pulse_doppler_radar|Импульсно-доплеровская РЛС|Pulse-Doppler Radar|fighter2
high_altitude_interceptors|Высотные перехватчики|High-altitude Interceptors|fighter3
thrust_vectoring|Управляемый вектор тяги|Thrust Vectoring|jet_fighter1
loyal_wingmen|Ведомые беспилотники|Loyal Wingmen|jet_fighter2
aerospace_interceptors|Воздушно-космические перехватчики|Aerospace Interceptors|special_project_air_icbm
"""),
    ),
    Branch(
        "air_support", "ADISCORD_air.txt", ("air_techs_folder", "bba_air_techs_folder"),
        "Штурмовая авиация", "Air Support", "air_support",
        techs("""
battlefield_attack_aircraft|Самолёты поля боя|Battlefield Attack Aircraft|CAS1
guided_munitions|Управляемые боеприпасы|Guided Munitions|CAS2
armored_cockpits|Бронированные кабины|Armored Cockpits|CAS3
vtol_assault_frames|Ударные СВВП|VTOL Assault Frames|jet_CAS1
drone_air_wings|Беспилотная авиаподдержка|Drone Air Wings|jet_CAS2
autonomous_strike_wings|Автономные ударные крылья|Autonomous Strike Wings|special_project_air_guided_missile
persistent_air_support|Непрерывная воздушная поддержка|Persistent Air Support|special_project_air_nuclear_missile
"""),
    ),
    Branch(
        "strategic_air", "ADISCORD_air.txt", ("air_techs_folder", "bba_air_techs_folder"),
        "Ракетные и стратегические системы", "Rocket and Strategic Systems", "strategic_air",
        techs("""
rocket_test_stands|Ракетные испытательные стенды|Rocket Test Stands|rocket_engines
inertial_guidance|Инерциальное наведение|Inertial Guidance|rocket_engines2
cruise_missiles|Крылатые ракеты|Cruise Missiles|guided_missile
strategic_rocket_architecture|Стратегическая ракетная артиллерия|Strategic Rocket Architecture|guided_missile2
orbital_tracking_relics|Орбитальные комплексы слежения|Orbital Tracking Relics|radio_detection
deep_strike_targeting|Координация глубоких ударов|Deep Strike Targeting|guided_missile3
suborbital_strike_systems|Суборбитальные ударные системы|Suborbital Strike Systems|special_project_air_icbm
"""),
    ),
    Branch(
        "naval_support", "ADISCORD_naval.txt", ("naval_folder", "mtgnavalsupportfolder"),
        "Прибрежные силы и эскорт", "Littoral Forces and Escort", "naval_support",
        techs("""
restored_dockyards|Восстановленные верфи|Restored Dockyards|basic_destroyer
coastal_patrols|Прибрежные патрули|Coastal Patrols|improved_destroyer
convoy_routing|Маршрутизация конвоев|Convoy Routing|sonar1
escort_datalinks|Каналы связи эскорта|Escort Datalinks|sonar2
drone_pickets|Беспилотные дозоры|Drone Pickets|advanced_destroyer
autonomous_escorts|Автономные корабли эскорта|Autonomous Escorts|modern_destroyer
distributed_sea_control|Распределённый контроль моря|Distributed Sea Control|naval_radar4
"""),
    ),
    Branch(
        "surface_fleet", "ADISCORD_naval.txt", ("naval_folder", "mtgnavalfolder"),
        "Надводный флот", "Surface Fleet", "surface_fleet",
        techs("""
recovered_fire_control|Восстановленное управление огнём|Recovered Fire Control|basic_light_cruiser
modular_hull_standards|Модульные стандарты корпусов|Modular Hull Standards|improved_light_cruiser
radar_gunnery|Радиолокационная стрельба|Radar Gunnery|basic_heavy_cruiser
missile_batteries|Корабельные ракетные батареи|Missile Batteries|advanced_heavy_cruiser
networked_task_groups|Сетевые оперативные группы|Networked Task Groups|basic_battleship
railgun_batteries|Корабельные рельсовые батареи|Railgun Batteries|advanced_battleship
horizon_fleet_command|Загоризонтное управление флотом|Horizon Fleet Command|modern_battleship
"""),
    ),
    Branch(
        "subsurface", "ADISCORD_naval.txt", ("naval_folder", "mtgnavalfolder"),
        "Подводные силы", "Subsurface Forces", "subsurface",
        techs("""
sonar_archives|Архивы гидроакустики|Sonar Archives|basic_submarine
quiet_propulsion|Малошумные движители|Quiet Propulsion|improved_submarine
homing_torpedoes|Самонаводящиеся торпеды|Homing Torpedoes|torpedo1
air_independent_cells|Воздухонезависимые ячейки|Air-independent Cells|advanced_submarine
seabed_sensor_webs|Донные сенсорные сети|Seabed Sensor Webs|naval_mines1
autonomous_submarines|Автономные подлодки|Autonomous Submarines|modern_submarine
deep_ocean_denial|Глубоководное сдерживание|Deep-ocean Denial|naval_mines3
"""),
    ),
)


from tools.lib.adiscord_technology_expansions_civil import EXPANSIONS as CIVIL_EXPANSIONS
from tools.lib.adiscord_technology_expansions_combat import EXPANSIONS as COMBAT_EXPANSIONS
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
        raise ValueError(f"{branch.key}: bad expansion years; missing={missing}, extra={extra}")

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
        "Программа Р-63 «След»", "R-63 “Trace” Programme",
    ),
    "active_scouting_suites": (
        "Контур Р-66 «Эхо»", "R-66 “Echo” Reconnaissance Loop",
    ),
    "semi_autonomous_combat_modules": (
        "Контур БТ-62 «Вожак»", "BT-62 “Lead” Control Loop",
    ),
    "autonomous_breakthrough_platforms": (
        "Программа Т-71 «Таран»", "T-71 “Ram” Programme",
    ),
    "siege_platform_networks": (
        "Контур Т-80 «Жернов»", "T-80 “Millstone” Siege Loop",
    ),
    "reclaimed_jet_platforms": (
        "Программа А-50 «Искра»", "A-50 “Spark” Programme",
    ),
    "battlefield_attack_aircraft": (
        "Программа АШ-50 «Коршун»", "AS-50 “Kite” Programme",
    ),
    "drone_air_wings": (
        "Контур А-65 «Стая»", "A-65 “Flock” Air-control Loop",
    ),
    "directed_energy_defensive_suites": (
        "Контур А-73 «Призма»", "A-73 “Prism” Defensive Loop",
    ),
    "suborbital_strike_systems": (
        "Программа Р-80 «Стрела»", "R-80 “Arrow” Programme",
    ),
    "refinery_catalyst_recovery": (
        "Сейсмическая томография залежей", "Seismic Deposit Tomography",
    ),
    "plasma_scrap_separation": (
        "Промышленный электролиз", "Industrial Electrolysis",
    ),
    "microbial_tailings_leaching": (
        "Микробиологическое извлечение металлов", "Microbial Metal Recovery",
    ),
    "high_pressure_polymer_synthesis": (
        "Высокобарическое восстановление руды", "High-Pressure Ore Reduction",
    ),
    # This remains a risky energy-storage programme, not an early bomb.
    # Preserve the internal key for saves while correcting the visible concept.
    "dirty_energy_munitions": (
        "Нестабильные изотопные накопители", "Unstable Isotope Storage",
    ),
}


def apply_tech_text_overrides(branch: Branch) -> Branch:
    changed = []
    for tech in branch.techs:
        override = TECH_TEXT_OVERRIDES.get(tech.key)
        changed.append(replace(tech, ru=override[0], en=override[1]) if override else tech)
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
APPLIED_PROGRAMME_KEYS = {programme["key"] for programme in APPLIED_PROGRAMMES}


def build_applied_branches() -> tuple[Branch, ...]:
    """Create optional TDA-style programmes without lengthening old trunks."""

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

# Preserve the pre-compact data set for the migration contract.  The generated
# tree below intentionally contains fewer nodes, but every one of these legacy
# IDs receives a deterministic migration outcome.
LEGACY_BRANCHES = BRANCHES
LEGACY_BRANCH_BY_KEY = {branch.key: branch for branch in LEGACY_BRANCHES}
LEGACY_TECH_BY_KEY = {
    tech.key: tech
    for branch in LEGACY_BRANCHES
    for tech in branch.techs
}


def compact_years(count: int) -> tuple[int, ...]:
    """Spread a compact linear programme across the live campaign window."""

    if count < 1:
        raise ValueError("A technology programme cannot be empty")
    baseline = (2150, 2155, 2158)[:count]
    if count <= len(baseline):
        return baseline
    live_count = count - len(baseline)
    live_years = YEARS[3:]
    if live_count > len(live_years):
        raise ValueError(f"Cannot place {count} compact technology nodes")
    if live_count == 1:
        selected = (2160,)
    else:
        selected_indices = tuple(
            round(index * (len(live_years) - 1) / (live_count - 1))
            for index in range(live_count)
        )
        if len(set(selected_indices)) != live_count:
            raise ValueError(f"Could not distribute {live_count} live technology years")
        selected = tuple(live_years[index] for index in selected_indices)
    return baseline + selected


def legacy_tech(key: str) -> Tech:
    try:
        return LEGACY_TECH_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f"Unknown legacy technology key {key}") from exc


def compact_legacy_branch(
    key: str,
    tech_keys: tuple[str, ...],
    *,
    years: tuple[int, ...] | None = None,
    file: str | None = None,
    folders: tuple[str, ...] | None = None,
    ru: str | None = None,
    en: str | None = None,
    profile: str | None = None,
) -> Branch:
    source = LEGACY_BRANCH_BY_KEY.get(key)
    if source is None:
        if not all((file, folders, ru, en, profile)):
            raise ValueError(f"New branch {key} is missing metadata")
        source_file = file
        source_folders = folders
        source_ru = ru
        source_en = en
        source_profile = profile
    else:
        source_file = file or source.file
        source_folders = folders or source.folders
        source_ru = ru or source.ru
        source_en = en or source.en
        source_profile = profile or source.profile
    branch_years = years or compact_years(len(tech_keys))
    return Branch(
        key,
        source_file,
        source_folders,
        source_ru,
        source_en,
        source_profile,
        tuple(legacy_tech(tech_key) for tech_key in tech_keys),
        branch_years,
    )


def new_branch(
    key: str,
    file: str,
    folders: tuple[str, ...],
    ru: str,
    en: str,
    profile: str,
    rows: tuple[tuple[str, str, str, str, int], ...],
) -> Branch:
    return Branch(
        key,
        file,
        folders,
        ru,
        en,
        profile,
        tuple(Tech(row[0], row[1], row[2], row[3]) for row in rows),
        tuple(row[4] for row in rows),
    )


PRODUCTION_BRANCH = compact_legacy_branch(
    "production",
    (
        "standardized_machine_tools",
        "interchangeable_components",
        "industrial_cluster_planning",
        "precision_metrology_recovery",
        "automated_assembly",
        "digital_tooling_libraries",
        "sensor_calibrated_machining",
        "predictive_maintenance",
        "autonomous_factory_cells",
        "lights_out_microfactories",
        "distributed_manufacturing",
    ),
    years=(2150, 2155, 2158, 2160, 2161, 2162, 2162, 2165, 2169, 2175, 2180),
    ru="Станки и автоматизация",
    en="Machine Tools and Automation",
)

INDUSTRY_ORGANIZATION_BRANCH = new_branch(
    "industry_organization",
    "ADISCORD_industry.txt",
    ("industry_folder",),
    "Организация промышленности",
    "Industrial Organization",
    "production",
    (
        ("industrial_organization_baseline", "Организация производственных сетей", "Production Network Organization", "basic_machine_tools", 2160),
        ("concentrated_industrial_zones", "Концентрированные промышленные зоны", "Concentrated Industrial Zones", "basic_machine_tools", 2162),
        ("distributed_workshop_networks", "Распределённые сети мастерских", "Distributed Workshop Networks", "basic_machine_tools", 2162),
        ("megafactory_power_buses", "Энергоконтуры мегафабрик", "Megafactory Power Buses", "basic_machine_tools", 2168),
        ("regional_spare_capacity", "Региональный резерв мощностей", "Regional Spare Capacity", "basic_machine_tools", 2168),
        ("strategic_production_complexes", "Стратегические производственные комплексы", "Strategic Production Complexes", "basic_machine_tools", 2180),
        ("resilient_production_meshes", "Устойчивые производственные сети", "Resilient Production Meshes", "basic_machine_tools", 2180),
    ),
)

RECONSTRUCTION_BRANCH = compact_legacy_branch(
    "reconstruction",
    (
        "salvage_standards",
        "ruin_workshops",
        "reconstruction_bureaus",
        "drone_construction_cartography",
        "modular_rebuilding",
        "prefabricated_districts",
        "public_repair_corps",
        "automated_civil_works",
        "civil_defense_networks",
    ),
    ru="Строительство и восстановление",
    en="Construction and Recovery",
)

RESOURCES_BRANCH = compact_legacy_branch(
    "resources",
    (
        "salvage_metallurgy",
        "grid_rationing",
        "refinery_reclamation",
        "spectral_ore_sorting",
        "logistics_hub_networks",
        "borehole_sensor_grids",
        "plasma_scrap_separation",
        "microbial_tailings_leaching",
        "synthetic_resource_cycles",
        "high_pressure_polymer_synthesis",
        "rare_earth_solvent_loops",
        "closed_loop_smelting",
        "automated_deep_mining",
        "carbon_feedstock_cracking",
        "isotope_selective_refining",
        "urban_mine_cartography",
        "strategic_element_reclamation",
        "strategic_material_recovery",
    ),
    ru="Ресурсы и промышленные резервы",
    en="Resources and Industrial Reserves",
)

SIGNALS_BRANCH = compact_legacy_branch(
    "signals",
    (
        "mesh_command_networks",
        "field_radio_networks",
        "encryption_rebuild",
        "frequency_hopping_field_sets",
        "signal_intercept_arrays",
        "passive_emitter_geolocation",
        "battlefield_analytics",
        "counterintelligence_filters",
        "battlefield_sensor_fusion",
        "self_healing_tactical_networks",
        "memetic_security_protocols",
    ),
    ru="Связь, обнаружение и безопасность",
    en="Communications, Detection, and Security",
)

COMPUTING_BRANCH = compact_legacy_branch(
    "computing",
    (
        "electromechanical_relays",
        "recovered_data_archives",
        "recovered_semiconductors",
        "hardened_computers",
        "error_correcting_field_computers",
        "analog_ai_accelerators",
        "predictive_logistics",
        "operational_ai_assistants",
        "strategic_digital_twins",
        "bounded_general_planning_cores",
        "strategic_ai_coordination",
        "predictive_budgeting",
    ),
    years=(2150, 2155, 2158, 2161, 2163, 2163, 2167, 2167, 2171, 2174, 2180, 2180),
    ru="Вычисления и управление",
    en="Computing and Control",
)

POWER_BRANCH = compact_legacy_branch(
    "power",
    (
        "local_grid_restoration",
        "substation_networks",
        "radiation_mapping",
        "phase_synchronized_substations",
        "solid_state_grid_breakers",
        "reactor_safety_protocols",
        "load_following_microreactors",
        "superconducting_power_busbars",
        "microreactor_blocks",
        "passive_decay_heat_sinks",
        "autonomous_reactor_diagnostics",
        "high_density_thermal_storage",
        "continental_load_balancing",
        "emergency_core_suppression",
    ),
    ru="Энергосети и реакторы",
    en="Power Grids and Reactors",
)


LINEAR_COMPACT_INDICES = {
    "small_arms": (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 18, 19),
    "squad_weapons": (0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 13, 15, 17, 18, 19),
    "protection": (0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 13, 15, 16, 18, 19),
    "special_forces": (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 15, 16, 18, 19),
    "field_support": tuple(range(20)),
    "logistics": tuple(range(20)),
    "rail": tuple(range(20)),
    "anti_tank": tuple(range(20)),
    "anti_air": tuple(range(20)),
    "recon_armor": tuple(range(20)),
    "heavy_armor": tuple(range(20)),
    "air_support": tuple(range(20)),
    "strategic_air": tuple(range(20)),
    "naval_support": tuple(range(20)),
    "surface_fleet": tuple(range(20)),
    "subsurface": tuple(range(20)),
}
AUTHORED_YEAR_COMPACT_BRANCHES = {
    "small_arms",
    "squad_weapons",
    "protection",
    "special_forces",
    "recon_armor",
    "heavy_armor",
    "field_support",
    "logistics",
    "rail",
    "anti_tank",
    "anti_air",
    "air_support",
    "strategic_air",
    "naval_support",
    "surface_fleet",
    "subsurface",
}


def compact_linear_branch(key: str) -> Branch:
    source = LEGACY_BRANCH_BY_KEY[key]
    indices = LINEAR_COMPACT_INDICES[key]
    keys = tuple(source.techs[index].key for index in indices)
    years = (
        tuple(source.years[index] for index in indices)
        if key in AUTHORED_YEAR_COMPACT_BRANCHES
        else None
    )
    return compact_legacy_branch(key, keys, years=years)


def full_authored_legacy_branch(key: str) -> Branch:
    """Restore every authored node and its original campaign chronology."""

    source = LEGACY_BRANCH_BY_KEY[key]
    return compact_legacy_branch(
        key,
        tuple(tech.key for tech in source.techs),
        years=source.years,
    )


ARTILLERY_BRANCH = full_authored_legacy_branch("artillery")

COMBAT_ARMOR_BRANCH = compact_legacy_branch(
    "combat_armor",
    (
        "recovered_medium_chassis",
        "remote_weapon_stations",
        "composite_armor_arrays",
        "modular_ceramic_armor_blocks",
        "electric_turret_drives",
        "semi_autonomous_combat_modules",
        "digital_fire_control_buses",
        "hard_kill_protection_arrays",
        "distributed_crew_stations",
        "adaptive_fire_control",
        "multispectral_gunner_sights",
        "unmanned_turret_capsules",
        "armored_platoon_target_handoff",
        "self_healing_armor_matrices",
        "autonomous_platoon_control",
        "limited_battle_ai",
        "electromagnetic_main_guns",
        "adaptive_suspension_control",
        "distributed_battlegroup",
        "resilient_combat_cloud_nodes",
    ),
    years=(2150, 2155, 2158, 2160, 2161, 2162, 2163, 2164, 2165, 2166, 2167, 2168, 2169, 2170, 2171, 2172, 2173, 2173, 2180, 2180),
)

MECHANIZED_MOBILITY_BRANCH = Branch(
    "mechanized_mobility",
    "ADISCORD_armor.txt",
    ("armour_folder", "nsb_armour_folder"),
    "Механизированные войска",
    "Mechanized Forces",
    "recon_armor",
    techs("""
armored_carrier_program|Программа М-63 «Ковчег»|M-63 “Ark” Programme|mechanized_equipment_1
protected_transport_standards|Стандарты защищённой перевозки|Protected Transport Standards|basic_light_tank
sealed_dismount_compartments|Герметичные десантные отсеки|Sealed Dismount Compartments|nsb_armor_tech_1
escort_protection_arrays|Комплексы защиты машин сопровождения|Escort Protection Arrays|nsb_armor_tech_2
dismount_sensor_suites|Сенсорные комплексы десанта|Dismount Sensor Suites|centimetric_radar
infantry_combat_vehicle_program|Контур М-70 «Рубеж»|M-70 “Rampart” Combat Loop|mechanized_equipment_2
unmanned_weapon_stations|Необитаемые башенные установки|Uncrewed Turret Mounts|improved_medium_tank
hybrid_cross_country_drives|Гибридные маршевые приводы|Hybrid Cross-country Drives|nsb_engine_tech_2
drone_screen_coordination|Координация беспилотного охранения|Drone Screen Coordination|radio
cooperative_dismount_control|Совместное управление спешиванием|Cooperative Dismount Control|improved_computing_machine
mechanized_battle_cloud|Механизированное боевое облако|Mechanized Battle Cloud|advanced_computing_machine
networked_mechanized_cells|Контур М-83 «Свод»|M-83 “Vault” Mechanized Loop|mechanized_equipment_3
"""),
    years=(2160, 2162, 2164, 2166, 2166, 2168, 2170, 2170, 2172, 2172, 2174, 2175),
)

FIGHTER_BRANCH = full_authored_legacy_branch("fighter")

SMALL_ARMS_BRANCH = new_branch(
    "small_arms",
    "ADISCORD_infantry.txt",
    ("infantry_folder",),
    "Винтовки и индивидуальное оружие",
    "Rifles and Individual Weapons",
    "infantry",
    (
        ("postwar_weapon_standardization", "Прецизионная нарезка каналов стволов", "Precision Rifling of Barrel Bores", "infantry_equipment_0", 2150),
        ("refurbished_receivers", "Обтюрация казённой части", "Breech Obturation", "infantry_weapons", 2155),
        ("standardized_cartridges", "Унитарный металлический патрон", "Metallic Self-contained Cartridge", "infantry_weapons2", 2158),
        ("caseless_ammunition_trials", "Нитроцеллюлозные метательные составы", "Nitrocellulose Propellant Formulations", "infantry_weapons2", 2160),
        ("smart_optics", "Лазерное измерение дальности", "Laser Rangefinding", "night_vision1", 2161),
        ("sealed_receiver_assemblies", "Промежуточные патроны", "Intermediate Cartridges", "infantry_weapons", 2162),
        ("electrothermal_ignition", "Высокопрочные ствольные стали", "High-strength Barrel Steels", "infantry_weapons3", 2163),
        ("smart_recoil_compensators", "Самозарядная автоматика", "Self-loading Action", "infantry_weapons3", 2164),
        ("networked_weapon_sights", "Вычислительное определение баллистической поправки", "Computerized Ballistic Correction", "night_vision", 2165),
        ("modular_rifle_kits", "Газоотводная автоматика", "Gas-operated Action", "infantry_weapons3", 2166),
        ("biometric_trigger_locks", "Запирание поворотным затвором", "Rotating-bolt Locking", "infantry_weapons3", 2167),
        ("integrated_target_designation", "Интегрированные электронно-оптические прицелы", "Integrated Electro-optical Sights", "night_vision2", 2169),
        ("programmable_ammunition", "Хромирование и износостойкие покрытия ствола", "Chrome Lining and Wear-resistant Bore Coatings", "infantry_at2", 2170),
        ("coil_assisted_service_rifles", "Оптимизация импульса отдачи", "Recoil Impulse Optimization", "infantry_weapons3", 2172),
        ("hybrid_kinetic_energy_carbines", "Полимерные и гибридные гильзы", "Polymer and Hybrid Cartridge Cases", "infantry_weapons3", 2175),
        ("networked_service_rifles", "Программируемые боеприпасы", "Programmable Small-arms Ammunition", "night_vision2", 2180),
    ),
)

INFANTRY_ANTI_TANK_BRANCH = new_branch(
    "anti_tank_infantry",
    "ADISCORD_infantry.txt",
    ("infantry_folder",),
    "Индивидуальные противотанковые средства",
    "Individual Anti-tank Weapons",
    "anti_tank",
    (
        ("recovered_shaped_charge_cells", "Бутылочные зажигательные смеси", "Bottle Incendiary Mixtures", "ADISCORD_antitank_01_incendiary_bottle", 2150),
        ("disposable_launcher_standards", "Динамитные и ранцевые подрывные заряды", "Dynamite and Satchel Demolition Charges", "ADISCORD_antitank_02_satchel_charge", 2155),
        ("tandem_penetrator_packages", "Ручные кумулятивные противотанковые гранаты", "Hand-thrown Shaped-charge Anti-tank Grenades", "ADISCORD_antitank_03_shaped_charge_grenade", 2158),
        ("wire_guided_hunter_teams", "Крупнокалиберные противотанковые ружья", "Large-calibre Anti-tank Rifles", "ADISCORD_antitank_04_antitank_rifle", 2161),
        ("recoilless_overmatch_cells", "Командное наведение по проводной линии", "Command Guidance over Wire", "ADISCORD_antitank_05_wire_guidance", 2161),
        ("fire_and_forget_seekers", "Безоткатные противотанковые системы", "Recoilless Anti-tank Systems", "ADISCORD_antitank_06_recoilless_launcher", 2164),
        ("programmable_anti_armor_fuzes", "Полуавтоматическое наведение по линии визирования", "Semi-automatic Command to Line of Sight", "ADISCORD_antitank_07_saclos_guidance", 2164),
        ("top_attack_profiles", "Реактивные гранатомёты с кумулятивной боевой частью", "Shaped-charge Rocket Launchers", "ADISCORD_antitank_08_rocket_launcher", 2168),
        ("loitering_armor_hunters", "Инфракрасное самонаведение верхней атаки", "Imaging-infrared Top-attack Homing", "ADISCORD_antitank_09_top_attack_seeker", 2168),
        ("cooperative_hunter_cells", "Тандемные кумулятивные боевые части", "Tandem Shaped-charge Warheads", "ADISCORD_antitank_10_tandem_warhead", 2172),
        ("terminal_overmatch_packages", "Барражирующие противотанковые боеприпасы", "Loitering Anti-armor Munitions", "ADISCORD_antitank_11_loitering_munition", 2172),
        ("distributed_anti_armor_net", "Кооперативное мультиспектральное целеуказание", "Cooperative Multispectral Targeting", "ADISCORD_antitank_12_multispectral_targeting", 2180),
    ),
)

NIGHT_COMBAT_BRANCH = new_branch(
    "night_combat",
    "ADISCORD_infantry.txt",
    ("infantry_folder",),
    "Ночной бой",
    "Night Combat",
    "special_forces",
    (
        ("passive_intensifier_cells", "Ячейки пассивного усиления", "Passive Intensifier Cells", "ADISCORD_night_01_passive_intensifier", 2150),
        ("sealed_night_mounts", "Герметичные ночные крепления", "Sealed Night Mounts", "ADISCORD_night_02_thermal_channel", 2155),
        ("thermal_observation_channels", "Тепловизионные каналы наблюдения", "Thermal Observation Channels", "ADISCORD_night_03_fused_sight", 2158),
        ("fused_low_light_sights", "Совмещённые прицелы слабого света", "Fused Low-light Sights", "ADISCORD_night_04_squad_target_sharing", 2161),
        ("low_signature_illumination", "Малозаметная подсветка", "Low-signature Illumination", "ADISCORD_night_05_counter_illumination", 2161),
        ("squad_target_sharing", "Обмен целями внутри отделения", "Squad Target Sharing", "ADISCORD_night_06_distributed_engagement", 2164),
        ("counter_illumination_warnings", "Предупреждение о встречной подсветке", "Counter-illumination Warnings", "ADISCORD_night_01_passive_intensifier", 2164),
        ("thermal_target_libraries", "Тепловые библиотеки целей", "Thermal Target Libraries", "ADISCORD_night_02_thermal_channel", 2168),
        ("nocturnal_sensor_discipline", "Ночная сенсорная дисциплина", "Nocturnal Sensor Discipline", "ADISCORD_night_03_fused_sight", 2168),
        ("distributed_night_engagements", "Распределённое ночное поражение", "Distributed Night Engagements", "ADISCORD_night_04_squad_target_sharing", 2172),
        ("adaptive_spectrum_concealment", "Адаптивное спектральное скрытие", "Adaptive Spectrum Concealment", "ADISCORD_night_05_counter_illumination", 2172),
        ("nocturnal_combat_mesh", "Ночной боевой контур", "Nocturnal Combat Mesh", "ADISCORD_night_06_distributed_engagement", 2180),
    ),
)


SIDE_PROGRAMME_SELECTIONS = {
    "combat_medicine": ("trauma_registry_networks", "forward_surgical_cells", "distributed_combat_medicine"),
    "combat_engineering": ("battle_damage_survey_teams", "assault_breaching_packages", "integrated_engineer_command"),
    "counter_drone_warfare": ("spectrum_threat_libraries", "offensive_jamming_cells", "adaptive_spectrum_dominance"),
    "air_mobility": ("restored_airlift_planning", "vertical_envelopment_control", "precision_aerial_resupply"),
    "riverine_warfare": ("shallow_water_navigation_tables", "modular_landing_causeways", "rapid_beachhead_logistics"),
    "unmanned_ground_systems": ("teleoperated_scout_carts", "armed_recon_drones", "distributed_ground_swarm_control"),
    "officer_training": ("reconstituted_staff_academies", "operational_planning_exercises", "adaptive_general_staff"),
}
SIDE_PROGRAMME_KEYS = set(SIDE_PROGRAMME_SELECTIONS)


def compact_side_branch(key: str) -> Branch:
    return compact_legacy_branch(
        key,
        SIDE_PROGRAMME_SELECTIONS[key],
        years=(2162, 2169, 2175),
    )


BRANCHES = (
    PRODUCTION_BRANCH,
    INDUSTRY_ORGANIZATION_BRANCH,
    RECONSTRUCTION_BRANCH,
    RESOURCES_BRANCH,
    SIGNALS_BRANCH,
    COMPUTING_BRANCH,
    POWER_BRANCH,
    LEGACY_BRANCH_BY_KEY["forbidden_energy"],
    LEGACY_BRANCH_BY_KEY["forbidden_automation"],
    SMALL_ARMS_BRANCH,
    compact_linear_branch("squad_weapons"),
    INFANTRY_ANTI_TANK_BRANCH,
    NIGHT_COMBAT_BRANCH,
    compact_linear_branch("protection"),
    compact_linear_branch("special_forces"),
    compact_side_branch("combat_medicine"),
    compact_linear_branch("field_support"),
    compact_linear_branch("logistics"),
    compact_linear_branch("rail"),
    compact_side_branch("combat_engineering"),
    compact_side_branch("officer_training"),
    ARTILLERY_BRANCH,
    compact_linear_branch("anti_tank"),
    compact_linear_branch("anti_air"),
    compact_linear_branch("recon_armor"),
    MECHANIZED_MOBILITY_BRANCH,
    COMBAT_ARMOR_BRANCH,
    compact_linear_branch("heavy_armor"),
    compact_side_branch("unmanned_ground_systems"),
    FIGHTER_BRANCH,
    compact_linear_branch("air_support"),
    compact_linear_branch("strategic_air"),
    compact_side_branch("air_mobility"),
    compact_linear_branch("naval_support"),
    compact_linear_branch("surface_fleet"),
    compact_linear_branch("subsurface"),
    compact_side_branch("riverine_warfare"),
    compact_side_branch("counter_drone_warfare"),
)

MAIN_BRANCH_KEYS_BY_FOLDER = {
    "industry_folder": {"production", "industry_organization", "reconstruction", "resources"},
    "electronics_folder": {"signals", "computing", "power"},
    "infantry_folder": {
        "small_arms", "squad_weapons", "anti_tank_infantry", "night_combat",
        "protection", "special_forces",
    },
    "support_folder": {"field_support", "logistics", "rail"},
    "artillery_folder": {"artillery", "anti_tank", "anti_air"},
    "armour_folder": {"recon_armor", "combat_armor", "heavy_armor"},
    "air_techs_folder": {"fighter", "air_support", "strategic_air"},
    "naval_folder": {"naval_support", "surface_fleet", "subsurface"},
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
            raise ValueError(f"Invalid technology edge {source}->{target} for {count} nodes")
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
        raise ValueError(f"Technology graph has unreachable nodes {sorted(set(range(count)) - reachable)}")

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


def dual_synthesis_graph() -> BranchGraph:
    left = (5, 7, 9, 11, 13, 15, 17)
    right = (6, 8, 10, 12, 14, 16, 18)
    edges = chain_edges((0, 1, 2, 3, 4))
    edges += [(4, left[0]), (4, right[0])]
    edges += chain_edges(left) + chain_edges(right)
    edges += [(left[-1], 19), (right[-1], 19)]
    lanes = [1] * 20
    for index in left:
        lanes[index] = 0
    for index in right:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (19,))


def dual_choice_graph() -> BranchGraph:
    """Two persistent schools that share a late, OR-gated capstone."""

    left = (5, 7, 9, 11, 13, 15, 17)
    right = (6, 8, 10, 12, 14, 16, 18)
    edges = chain_edges((0, 1, 2, 3, 4))
    edges += [(4, left[0]), (4, right[0])]
    edges += chain_edges(left) + chain_edges(right)
    edges += [(left[-1], 19), (right[-1], 19)]
    lanes = [1] * 20
    for index in left:
        lanes[index] = 0
    for index in right:
        lanes[index] = 2
    # No explicit dependency at 19: two incoming paths are an OR gate, as in
    # the vanilla flexible/streamlined industry choice.
    return make_graph(tuple(lanes), edges)


def double_diamond_graph() -> BranchGraph:
    left_one = (5, 7, 9)
    right_one = (6, 8, 10)
    left_two = (12, 14, 16)
    right_two = (13, 15, 17)
    edges = chain_edges((0, 1, 2, 3, 4))
    edges += [(4, left_one[0]), (4, right_one[0])]
    edges += chain_edges(left_one) + chain_edges(right_one)
    edges += [(left_one[-1], 11), (right_one[-1], 11)]
    edges += [(11, left_two[0]), (11, right_two[0])]
    edges += chain_edges(left_two) + chain_edges(right_two)
    edges += [(left_two[-1], 18), (right_two[-1], 18), (18, 19)]
    lanes = [1] * 20
    for index in left_one + left_two:
        lanes[index] = 0
    for index in right_one + right_two:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (11, 18))


def double_choice_graph() -> BranchGraph:
    """Two successive XOR decisions, each followed by an OR merge."""

    left_one = (5, 7, 9)
    right_one = (6, 8, 10)
    left_two = (12, 14, 16)
    right_two = (13, 15, 17)
    edges = chain_edges((0, 1, 2, 3, 4))
    edges += [(4, left_one[0]), (4, right_one[0])]
    edges += chain_edges(left_one) + chain_edges(right_one)
    edges += [(left_one[-1], 11), (right_one[-1], 11)]
    edges += [(11, left_two[0]), (11, right_two[0])]
    edges += chain_edges(left_two) + chain_edges(right_two)
    edges += [(left_two[-1], 18), (right_two[-1], 18), (18, 19)]
    lanes = [1] * 20
    for index in left_one + left_two:
        lanes[index] = 0
    for index in right_one + right_two:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges)


def alternating_diamonds_graph() -> BranchGraph:
    edges = chain_edges((0, 1, 2, 3, 4))
    edges += [(4, 5), (4, 6), (5, 8), (6, 7), (7, 8)]
    edges += [(8, 9), (8, 10), (9, 12), (10, 11), (11, 12)]
    edges += [(12, 13), (12, 14), (13, 16), (14, 15), (15, 16)]
    edges += [(16, 17), (16, 18), (17, 19), (18, 19)]
    lanes = [1] * 20
    for index in (6, 7, 14, 15):
        lanes[index] = 0
    for index in (10, 11, 18):
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (8, 12, 16, 19))


def alternating_choices_graph() -> BranchGraph:
    """Four field decisions; each selected project rejoins the main line."""

    edges = chain_edges((0, 1, 2, 3, 4))
    edges += [(4, 5), (4, 6), (5, 8), (6, 7), (7, 8)]
    edges += [(8, 9), (8, 10), (9, 12), (10, 11), (11, 12)]
    edges += [(12, 13), (12, 14), (13, 16), (14, 15), (15, 16)]
    edges += [(16, 17), (16, 18), (17, 19), (18, 19)]
    lanes = [1] * 20
    for index in (6, 7, 14, 15):
        lanes[index] = 0
    for index in (10, 11, 18):
        lanes[index] = 2
    return make_graph(tuple(lanes), edges)


def applied_dual_choice_graph() -> BranchGraph:
    """A compact optional programme with two persistent applied schools."""

    return make_graph(
        (1, 0, 2, 0, 2, 0, 2, 1),
        [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6), (5, 7), (6, 7)],
    )


def infantry_integration_graph() -> BranchGraph:
    """Rifle mechanisms, ammunition, and optics form three real programmes."""

    ammunition = (2, 3, 6, 12, 14)
    rifles = (2, 5, 7, 9, 10, 13)
    optics = (2, 4, 8, 11)
    edges = chain_edges((0, 1, 2))
    edges += chain_edges(ammunition) + chain_edges(rifles) + chain_edges(optics)
    edges += [(ammunition[-1], 15), (rifles[-1], 15), (optics[-1], 15)]
    lanes = [1] * 16
    for index in rifles[1:]:
        lanes[index] = 0
    for index in ammunition[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (15,))


def squad_integration_graph() -> BranchGraph:
    """Integrate automatic weapons, guided launchers, and squad C2."""

    firepower = (0, 1, 2, 3, 5, 7, 10)
    command = (0, 4, 6, 8, 9, 12)
    edges = chain_edges(firepower) + chain_edges(command)
    edges += [(firepower[-1], 11), (9, 11), (11, 13)]
    edges += [(13, 14), (command[-1], 14), (14, 15)]
    lanes = [1] * 16
    for index in firepower[1:]:
        lanes[index] = 0
    for index in command[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (11, 14))


def compact_dual_synthesis_graph() -> BranchGraph:
    """Two five-project field schools converging on one operational mesh."""

    left = (2, 3, 5, 7, 9)
    right = (2, 4, 6, 8, 10)
    edges = chain_edges((0, 1, 2))
    edges += chain_edges(left) + chain_edges(right)
    edges += [(left[-1], 11), (right[-1], 11)]
    lanes = [1] * 12
    for index in left[1:]:
        lanes[index] = 0
    for index in right[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (11,))


def compact_two_row_synthesis_graph() -> BranchGraph:
    """Keep the same two routes inside one compact two-row programme band."""

    graph = compact_dual_synthesis_graph()
    lanes = tuple(0 if lane < 2 else 1 for lane in graph.lanes)
    return BranchGraph(lanes, graph.successors, graph.dependencies)


def variable_dual_synthesis_graph(count: int) -> BranchGraph:
    """Fit a two-route programme to a compact branch of at least seven nodes."""

    if count < 7:
        raise ValueError("A variable dual programme needs at least seven nodes")
    body = tuple(range(3, count - 1))
    left = body[::2]
    right = body[1::2]
    if not left or not right:
        raise ValueError("A variable dual programme needs two non-empty routes")
    capstone = count - 1
    edges = chain_edges((0, 1, 2))
    edges += [(2, left[0]), (2, right[0])]
    edges += chain_edges(left) + chain_edges(right)
    edges += [(left[-1], capstone), (right[-1], capstone)]
    lanes = [1] * count
    for index in left:
        lanes[index] = 0
    for index in right:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (capstone,))


def protection_programmes_graph() -> BranchGraph:
    """Body systems, combat medicine, and environmental protection."""

    body = (0, 1, 3, 6, 8, 14)
    medicine = (0, 4, 9, 10, 12)
    environment = (0, 2, 5, 7, 11, 13)
    edges = chain_edges(body) + chain_edges(medicine) + chain_edges(environment)
    edges += [(body[-1], 15), (medicine[-1], 15), (environment[-1], 15)]
    lanes = [1] * 16
    for index in body[1:]:
        lanes[index] = 0
    for index in environment[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (15,))


def special_forces_programmes_graph() -> BranchGraph:
    """Urban assault, deep reconnaissance, and airborne insertion."""

    urban = (0, 1, 3, 5, 13)
    reconnaissance = (0, 2, 4, 6, 7, 8, 11, 12, 14)
    airborne = (0, 9, 10)
    edges = chain_edges(urban) + chain_edges(reconnaissance) + chain_edges(airborne)
    edges += [(urban[-1], 15), (reconnaissance[-1], 15), (airborne[-1], 15)]
    lanes = [1] * 16
    for index in urban[1:]:
        lanes[index] = 0
    for index in airborne[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (15,))


def reconnaissance_armor_programmes_graph() -> BranchGraph:
    """Mobility, sensors, and autonomy converge on a reconnaissance screen."""

    mobility = (2, 3, 6, 8, 9, 12, 15)
    sensors = (2, 4, 5, 7, 10, 14, 17)
    autonomy = (2, 11, 13, 16, 18)
    edges = chain_edges((0, 1, 2))
    edges += chain_edges(mobility) + chain_edges(sensors) + chain_edges(autonomy)
    edges += [(mobility[-1], 19), (sensors[-1], 19), (autonomy[-1], 19)]
    lanes = [1] * 20
    for index in mobility[1:]:
        lanes[index] = 0
    for index in autonomy[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (19,))


def combat_armor_programmes_graph() -> BranchGraph:
    """Protection, fire control, and autonomy precede the late armor choice."""

    protection = (2, 3, 7, 13)
    fire_control = (2, 4, 6, 9, 10, 12)
    autonomy = (2, 5, 8, 11, 14)
    edges = chain_edges((0, 1, 2))
    edges += chain_edges(protection) + chain_edges(fire_control) + chain_edges(autonomy)
    edges += [(protection[-1], 15), (fire_control[-1], 15), (autonomy[-1], 15)]
    edges += [(15, 16), (15, 17), (16, 18), (17, 19)]
    lanes = [1] * 20
    for index in protection[1:] + (16, 18):
        lanes[index] = 0
    for index in autonomy[1:] + (17, 19):
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (15,))


def heavy_armor_programmes_graph() -> BranchGraph:
    """Survivability, power, and engineering converge into siege warfare."""

    survivability = (2, 3, 6, 7, 8, 12, 16)
    power = (2, 5, 9, 10, 14, 17)
    engineering = (2, 4, 11, 13, 15, 18)
    edges = chain_edges((0, 1, 2))
    edges += chain_edges(survivability) + chain_edges(power) + chain_edges(engineering)
    edges += [(survivability[-1], 19), (power[-1], 19), (engineering[-1], 19)]
    lanes = [1] * 20
    for index in survivability[1:]:
        lanes[index] = 0
    for index in engineering[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (19,))


def mechanized_mobility_programmes_graph() -> BranchGraph:
    """Protection and dismount integration lead into a networked IFV force."""

    edges = chain_edges((0, 1, 2))
    edges += [(2, 3), (2, 4), (3, 5), (4, 5)]
    edges += [(5, 6), (5, 7), (6, 8), (7, 9)]
    edges += [(8, 10), (9, 10), (10, 11)]
    return make_graph(
        (1, 1, 1, 0, 2, 1, 0, 2, 0, 2, 1, 1),
        edges,
        (5, 10),
    )


def linear_graph(count: int) -> BranchGraph:
    return make_graph((1,) * count, chain_edges(tuple(range(count))))


def temporary_production_graph() -> BranchGraph:
    edges = chain_edges((0, 1, 2, 3, 4))
    edges += [(4, 5), (4, 6), (5, 7), (6, 7)]
    edges += chain_edges((7, 8, 9, 10))
    lanes = (1, 1, 1, 1, 1, 0, 2, 1, 1, 1, 1)
    return make_graph(lanes, edges)


def industry_organization_graph() -> BranchGraph:
    return make_graph(
        (1, 0, 2, 0, 2, 0, 2),
        [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6)],
    )


def compact_computing_graph() -> BranchGraph:
    edges = chain_edges((0, 1, 2, 3))
    edges += [(3, 4), (3, 5), (4, 6), (5, 7), (6, 8), (7, 8)]
    edges += chain_edges((8, 9, 10))
    edges += [(8, 11)]
    lanes = (1, 1, 1, 1, 0, 2, 0, 2, 1, 1, 1, 2)
    return make_graph(lanes, edges)


def permanent_tail_choice_graph(count: int) -> BranchGraph:
    if count < 5:
        raise ValueError("A persistent choice needs a trunk and two two-node paths")
    fork = count - 5
    left_entry, right_entry, left_final, right_final = range(count - 4, count)
    edges = chain_edges(tuple(range(fork + 1)))
    edges += [
        (fork, left_entry),
        (fork, right_entry),
        (left_entry, left_final),
        (right_entry, right_final),
    ]
    lanes = [1] * count
    lanes[left_entry] = lanes[left_final] = 0
    lanes[right_entry] = lanes[right_final] = 2
    return make_graph(tuple(lanes), edges)


XOR_KIND_BY_BRANCH = {
    "production": "temporary",
    "industry_organization": "permanent",
    "computing": "temporary",
    "artillery": "permanent",
    "combat_armor": "permanent",
    "fighter": "permanent",
}

XOR_INDEX_GROUPS_BY_BRANCH = {
    "production": ((5, 6),),
    "industry_organization": ((1, 2),),
    "computing": ((4, 5),),
    "artillery": ((len(ARTILLERY_BRANCH.techs) - 4, len(ARTILLERY_BRANCH.techs) - 3),),
    "combat_armor": ((len(COMBAT_ARMOR_BRANCH.techs) - 4, len(COMBAT_ARMOR_BRANCH.techs) - 3),),
    "fighter": ((len(FIGHTER_BRANCH.techs) - 4, len(FIGHTER_BRANCH.techs) - 3),),
}


def graph_for_branch(branch: Branch) -> BranchGraph:
    if branch.key == "production":
        graph = temporary_production_graph()
    elif branch.key == "industry_organization":
        graph = industry_organization_graph()
    elif branch.key == "computing":
        graph = compact_computing_graph()
    elif branch.key in {"reconstruction", "resources", "signals", "power"}:
        graph = variable_dual_synthesis_graph(len(branch.techs))
    elif branch.key == "small_arms":
        graph = infantry_integration_graph()
    elif branch.key == "squad_weapons":
        graph = squad_integration_graph()
    elif branch.key == "anti_tank_infantry":
        graph = compact_two_row_synthesis_graph()
    elif branch.key == "night_combat":
        graph = compact_dual_synthesis_graph()
    elif branch.key == "protection":
        graph = protection_programmes_graph()
    elif branch.key == "special_forces":
        graph = special_forces_programmes_graph()
    elif branch.key in {"field_support", "anti_tank", "strategic_air", "subsurface"}:
        graph = double_diamond_graph()
    elif branch.key in {"logistics", "anti_air", "naval_support"}:
        graph = alternating_diamonds_graph()
    elif branch.key in {"rail", "air_support", "surface_fleet"}:
        graph = dual_synthesis_graph()
    elif branch.key == "recon_armor":
        graph = reconnaissance_armor_programmes_graph()
    elif branch.key == "mechanized_mobility":
        graph = mechanized_mobility_programmes_graph()
    elif branch.key == "combat_armor":
        graph = combat_armor_programmes_graph()
    elif branch.key == "heavy_armor":
        graph = heavy_armor_programmes_graph()
    elif branch.key in {"artillery", "fighter"}:
        graph = permanent_tail_choice_graph(len(branch.techs))
    elif branch.key == "forbidden_energy":
        graph = make_graph(
            (1, 1, 1, 0, 2, 1),
            [(0, 1), (1, 2), (2, 3), (2, 4), (3, 5), (4, 5)],
            (5,),
        )
    elif branch.key == "forbidden_automation":
        graph = make_graph((1, 0, 2), [(0, 1), (0, 2)])
    else:
        graph = linear_graph(len(branch.techs))
    if len(graph.lanes) != len(branch.techs):
        raise ValueError(
            f"{branch.key}: graph has {len(graph.lanes)} nodes for {len(branch.techs)} techs"
        )
    for source, targets in enumerate(graph.successors):
        for target in targets:
            if branch.years[target] <= branch.years[source]:
                raise ValueError(f"{branch.key}: non-chronological edge {source}->{target}")
    return graph


BRANCH_GRAPHS = {branch.key: graph_for_branch(branch) for branch in BRANCHES}

# Compatibility name retained for older validator imports.  Geometry is no
# longer selected from a global pattern library.
GRAPH_PATTERN_BY_BRANCH = {branch.key: "explicit" for branch in BRANCHES}


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
            return tuple(branch.techs[sibling].id for sibling in group if sibling != index)
    return ()


FORBIDDEN_IDS = {
    tech.id
    for branch in BRANCHES
    if branch.profile.startswith("forbidden_")
    for tech in branch.techs
}


ENABLE_EQUIPMENT = {
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
    "ADISCORD_tech_recoilless_squad_launchers": ("ADISCORD_squad_weapons_equipment_2168",),
    "ADISCORD_tech_field_ew_units": ("ADISCORD_squad_weapons_equipment_2170",),
    "ADISCORD_tech_remote_weapon_tripods": ("ADISCORD_squad_weapons_equipment_2178",),
    "ADISCORD_tech_autonomous_support_weapons": ("ADISCORD_squad_weapons_equipment_2183",),
    "ADISCORD_tech_robotic_heavy_weapon_teams": ("ADISCORD_squad_weapons_equipment_2193",),
    "ADISCORD_tech_swarm_fireteams": ("ADISCORD_squad_weapons_equipment_2200",),
    "ADISCORD_tech_field_workshop_tools": ("support_equipment_1",),
    "ADISCORD_tech_drone_delivered_repair_spares": ("ADISCORD_support_equipment_2170",),
    "ADISCORD_tech_predictive_parts_prepositioning": ("ADISCORD_support_equipment_2183",),
    "ADISCORD_tech_self_sustaining_support": ("ADISCORD_support_equipment_2200",),
    "ADISCORD_tech_restored_rail_stock": ("train_equipment_1",),
    "ADISCORD_tech_armored_rail_convoys": ("armored_train_equipment_1",),
    "ADISCORD_tech_hardened_logistics_nodes": ("ADISCORD_hardened_train_equipment_2183",),
    "ADISCORD_tech_autonomous_rail_dispatch": ("ADISCORD_autonomous_train_equipment_2183",),
    "ADISCORD_tech_autonomous_yard_shunting": ("ADISCORD_autonomous_train_equipment_2183",),
    "ADISCORD_tech_over_the_horizon_fire_control": ("ADISCORD_railway_gun_equipment_2200",),
    "ADISCORD_tech_railway_gun_reactivation": ("railway_gun_equipment_1",),
    "ADISCORD_tech_restored_field_artillery": ("artillery_equipment_1",),
    # Each artillery specialization receives the same generational chassis;
    # its chosen programme determines the stat package, not production access.
    "ADISCORD_tech_inertial_battery_survey": ("ADISCORD_artillery_equipment_2170",),
    "ADISCORD_tech_assisted_projectiles": ("ADISCORD_artillery_equipment_2170",),
    "ADISCORD_tech_course_correcting_fuzes": ("ADISCORD_artillery_equipment_2170",),
    "ADISCORD_tech_multispectral_spotter_drones": ("ADISCORD_artillery_equipment_2183",),
    "ADISCORD_tech_robotic_shell_handling": ("ADISCORD_artillery_equipment_2183",),
    "ADISCORD_tech_drone_spotted_batteries": ("ADISCORD_artillery_equipment_2183",),
    "ADISCORD_tech_scrap_at_launchers": ("ADISCORD_anti_tank_equipment_2163",),
    "ADISCORD_tech_superconducting_coil_barrels": ("ADISCORD_anti_tank_equipment_2183",),
    "ADISCORD_tech_guided_hypervelocity_penetrators": ("ADISCORD_anti_tank_equipment_2183",),
    "ADISCORD_tech_point_defense_aa": ("ADISCORD_anti_air_equipment_2163",),
    "ADISCORD_tech_high_energy_laser_turrets": ("ADISCORD_anti_air_equipment_2183",),
    "ADISCORD_tech_drone_recon_swarms": ("ADISCORD_light_combat_platform_2163",),
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
    "ADISCORD_tech_active_mass_balancing_suspension": ("ADISCORD_heavy_combat_platform_2183",),
    "ADISCORD_tech_siege_platform_networks": ("ADISCORD_heavy_combat_platform_2200",),
    "ADISCORD_tech_reclaimed_jet_platforms": ("ADISCORD_fighter_airframe_2163",),
    "ADISCORD_tech_low_observable_inlet_geometry": ("ADISCORD_interceptor_airframe_2183",),
    "ADISCORD_tech_cooperative_fighter_sensor_fusion": ("ADISCORD_interceptor_airframe_2183",),
    "ADISCORD_tech_loyal_wingmen": ("ADISCORD_interceptor_airframe_2183",),
    "ADISCORD_tech_battlefield_attack_aircraft": ("ADISCORD_cas_airframe_2170",),
    "ADISCORD_tech_vtol_assault_frames": ("ADISCORD_vtol_airframe_2170",),
    "ADISCORD_tech_electromagnetic_cannon_pods": ("ADISCORD_drone_airframe_2183",),
    "ADISCORD_tech_orbital_tracking_relics": ("ADISCORD_rocket_strike_platform_2183",),
    "ADISCORD_tech_low_observable_cruise_missile_skins": ("ADISCORD_rocket_strike_platform_2183",),
    "ADISCORD_tech_suborbital_skip_glide_guidance": ("ADISCORD_deep_strike_airframe_2200",),
    "ADISCORD_tech_autonomous_strategic_strike_planning": ("ADISCORD_deep_strike_airframe_2200",),
    "ADISCORD_tech_suborbital_strike_systems": ("ADISCORD_orbital_tracking_platform_2200",),
}


# Cross-row integration is intentionally dependency-only: drawing paths
# between separate grid boxes is fragile in HOI4, while dependencies provide
# the required AND gate in the technology tooltip and research logic.
EXTRA_TECH_DEPENDENCIES = {
    # Short side programmes attach to contemporary core capabilities.  Long
    # cross-grid cables are deliberately avoided because HOI4 renders them
    # unreliably; dependencies still provide the gameplay gate and tooltip.
    "ADISCORD_tech_trauma_registry_networks": (
        "ADISCORD_tech_combat_engineering_sections",
    ),
    "ADISCORD_tech_battle_damage_survey_teams": (
        "ADISCORD_tech_standardized_field_tool_chests",
    ),
    "ADISCORD_tech_spectrum_threat_libraries": (
        "ADISCORD_tech_frequency_hopping_field_sets",
        "ADISCORD_tech_stabilized_autocannon_mounts",
    ),
    "ADISCORD_tech_restored_airlift_planning": (
        "ADISCORD_tech_composite_wing_spars",
    ),
    "ADISCORD_tech_shallow_water_navigation_tables": (
        "ADISCORD_tech_modular_escort_combat_systems",
    ),
    "ADISCORD_tech_teleoperated_scout_carts": (
        "ADISCORD_tech_sealed_electric_scout_drives",
        "ADISCORD_tech_hardened_computers",
    ),
    "ADISCORD_tech_armored_carrier_program": (
        "ADISCORD_tech_sealed_electric_scout_drives",
        "ADISCORD_tech_remote_weapon_stations",
    ),
    "ADISCORD_tech_reconstituted_staff_academies": (
        "ADISCORD_tech_hardened_computers",
    ),
    "ADISCORD_tech_remote_weapon_tripods": ("ADISCORD_tech_modular_rifle_kits",),
    "ADISCORD_tech_autonomous_support_weapons": ("ADISCORD_tech_programmable_ammunition",),
    "ADISCORD_tech_swarm_fireteams": ("ADISCORD_tech_networked_service_rifles",),
    # Late industrial automation is an information-system project, not a
    # parallel percentage ladder.  A production beeline therefore picks up a
    # compact set of useful computing and secure-network technologies without
    # forcing the player through an entire second tree.
    "ADISCORD_tech_autonomous_factory_cells": (
        "ADISCORD_tech_predictive_logistics",
        "ADISCORD_tech_battlefield_analytics",
    ),
    "ADISCORD_tech_distributed_manufacturing": (
        "ADISCORD_tech_strategic_digital_twins",
        "ADISCORD_tech_self_healing_tactical_networks",
    ),
    # Late autonomous and directed-energy systems are integrations, not
    # isolated percentage ladders.  Cross-folder paths are deliberately not
    # drawn because the HOI4 grid renderer handles them unreliably.
    "ADISCORD_tech_high_energy_laser_turrets": (
        "ADISCORD_tech_superconducting_power_busbars",
    ),
    "ADISCORD_tech_autonomous_breakthrough_platforms": (
        "ADISCORD_tech_operational_ai_assistants",
    ),
    "ADISCORD_tech_autonomous_strike_wings": (
        "ADISCORD_tech_operational_ai_assistants",
    ),
    "ADISCORD_tech_autonomous_submarines": (
        "ADISCORD_tech_operational_ai_assistants",
    ),
    "ADISCORD_tech_swarm_coordinated_fire_support": (
        "ADISCORD_tech_battlefield_sensor_fusion",
    ),
    "ADISCORD_tech_distributed_battlegroup": (
        "ADISCORD_tech_self_healing_tactical_networks",
    ),
    "ADISCORD_tech_siege_platform_networks": (
        "ADISCORD_tech_battlefield_sensor_fusion",
    ),
    "ADISCORD_tech_distributed_sea_control": (
        "ADISCORD_tech_self_healing_tactical_networks",
    ),
}


BRANCH_BY_KEY = {branch.key: branch for branch in BRANCHES}
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
        pending.extend(EXTRA_TECH_DEPENDENCIES.get(tech_id, ()))
    return tuple(sorted(resolved))


COMMON_STARTING_ROOTS = tuple(
    sorted(
        BRANCH_BY_KEY[branch_key].techs[0].id
        for branch_keys in MAIN_BRANCH_KEYS_BY_FOLDER.values()
        for branch_key in branch_keys
    )
)

STARTING_TECH_PROFILE_SEEDS = {
    "common": COMMON_STARTING_ROOTS,
    "industrial": tuple(
        tech_id
        for branch_key in ("production", "reconstruction", "resources")
        for tech_id in branch_technology_ids_through(branch_key, 2158)
    ),
    "energy": branch_technology_ids_through("power", 2160),
    "institutional": (
        *branch_technology_ids_through("signals", 2158),
        *branch_technology_ids_through("computing", 2158),
    ),
    "land": tuple(
        tech_id
        for branch_key in (
            "small_arms", "squad_weapons", "protection", "field_support",
            "logistics", "rail", "artillery", "anti_tank", "anti_air",
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
    "air": tuple(
        tech_id
        for branch_key in ("fighter", "air_support", "strategic_air")
        for tech_id in branch_technology_ids_through(branch_key, 2158)
    ),
    "naval": tuple(
        tech_id
        for branch_key in ("naval_support", "surface_fleet", "subsurface")
        for tech_id in branch_technology_ids_through(branch_key, 2158)
    ),
    "fragment_low_tech": (
        "ADISCORD_tech_ruin_workshops",
        "ADISCORD_tech_refurbished_receivers",
        "ADISCORD_tech_restored_truck_fleets",
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
        "ADISCORD_tech_caseless_ammunition_trials",
        "ADISCORD_tech_standardized_field_tool_chests",
        "ADISCORD_tech_electrohydraulic_gun_laying",
        "ADISCORD_tech_electric_turret_drives",
        "ADISCORD_tech_composite_wing_spars",
        "ADISCORD_tech_modular_escort_combat_systems",
    ),
}

STARTING_TECH_PROFILES = {
    profile: technology_prerequisite_closure(seeds)
    for profile, seeds in STARTING_TECH_PROFILE_SEEDS.items()
}

# Manual, lore-aware mapping for every tag owning at least one state on
# 2160.1.1.  Empty tuples are intentional common-only assignments.
STARTING_COUNTRY_TECH_PROFILES = {
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
    "COF": (),
    "DAN": ("fragment_low_tech", "land"),
    "DOL": ("fragment_low_tech",),
    "DRV": ("fragment_low_tech",),
    "EFL": ("fragment_low_tech", "land", "naval"),
    "ELN": ("institutional",),
    "EXZ": (),
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
    "NOD": ("industrial", "energy", "institutional", "land", "air", "naval"),
    "NVR": ("fragment_low_tech", "land"),
    "ORV": ("fragment_low_tech", "land"),
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
    "SOL": ("fragment_low_tech",),
    "STP": ("industrial", "energy", "institutional", "land", "air", "naval"),
    "SVL": ("fragment_low_tech",),
    "TFF": ("fragment_low_tech",),
    "TMR": ("industrial",),
    "TRU": ("industrial", "institutional", "land"),
    "VAD": ("industrial", "energy", "institutional", "land", "air", "naval", "armored_core"),
    "VAL": ("industrial", "energy", "institutional", "land", "air", "naval"),
    "VES": ("fragment_low_tech", "land"),
    "VLD": ("fragment_low_tech",),
    "VRA": ("fragment_low_tech",),
    "VLA": ("institutional", "land", "air"),
    "WEF": ("institutional", "land", "air"),
    "WIT": ("institutional", "land", "naval"),
    "WRK": ("industrial", "energy", "institutional", "land", "air", "naval", "armored_core"),
    "WCG": ("fragment_low_tech", "land"),
    "YPR": ("fragment_low_tech", "land"),
    "ZAO": ("fragment_low_tech",),
}

STARTING_COUNTRY_TECH_PROFILE_RATIONALE = {
    "AIN": "Nodrul's licensed frontier mandate preserves imported legal and administrative institutions over a small local workshop base.",
    "APH": "Traditional extraction polity with a small arms base and no advanced infrastructure.",
    "ARS": "Small eastern republic retains militia practice and basic workshops without advanced institutions.",
    "AUR": "Civic republic with restored public utilities but only a modest material base.",
    "AZH": "Black Basin levy couples a small field formation with an operating dockyard and coastal flotilla.",
    "BBV": "Single-state Besjaysk fragment with one inherited formation and no industrial plant.",
    "BCM": "Single-state Besjaysk fragment sustained by one civilian workshop base.",
    "BGT": "Single-state Besjaysk fragment without an established industrial or institutional base.",
    "BHG": "Single-state Besjaysk fragment with one civilian workshop base.",
    "BJK": "Besjaysk core survives as a small fragment rather than a modern institutional state.",
    "BLD": "Dispersed Besjaysk fragment with no starting factories or advanced service base.",
    "BOR": "Itora-supported frontier republic combines functioning civil institutions with a trained border army.",
    "BRN": "Polar protectorate retains radio, heating, and grid practice but little heavy industry.",
    "BTL": "Multi-state polity with several formations but only a minimal civilian economy.",
    "CIN": "Agrarian ash tribe with informal education and artisan production.",
    "COF": "Forest cult intentionally receives only the common equipment-enabling roots.",
    "DAN": "Small military polity with an army but no industrial or energy system to support advanced profiles.",
    "DOL": "Loose road-district union supports militia and workshops without a durable advanced institution base.",
    "DRV": "Decentralized valley communes rely on local workshops and militia organization.",
    "EFL": "Small regional state maintains a standing army, an operating dockyard, and a coastal flotilla despite limited industrial depth.",
    "ELN": "Technocratic census state retains institutional and grid expertise without a full industrial package.",
    "EXZ": "Exclusion-zone placeholder intentionally receives only the common base before its scripted breakup.",
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
    "MON": "Third-ranked starting power combines a large arsenal belt, four research slots, a modern army, and operating airfields.",
    "MZR": "Water syndicate adds grid engineering to a fragmentary material base.",
    "NAM": "Thinly industrialized regional administration retains an operating dockyard and coastal fleet beside its small field force.",
    "NOD": "High-output military-industrial power with a dockyard and advanced institutional continuity.",
    "NVR": "Pragmatic federation maintains a modest trained army on top of dispersed workshops.",
    "ORV": "Regional union supports a small standing army but no advanced industrial specialization.",
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
    "SOL": "Small Vorkerland successor with no intact starting factory base.",
    "STP": "Major industrial state with dockyards, restored air and naval doctrines, and a large standing army.",
    "SVL": "One-island mining republic has basic workshops and militia organization but no advanced institutional base.",
    "TFF": "Frontier polity has a small army and fragmentary production without advanced institutions.",
    "TMR": "Utility chamber retains a modest industrial grid while limiting military specialization.",
    "TRU": "Organized Vorkerland successor with enough factories, infrastructure, and army continuity for core profiles.",
    "VAD": "Major Vorkerland successor with dense industry, a live power site, dockyards, and ten air bases.",
    "VAL": "Weapons superpower with twelve military factories, three research slots, and a large convoy reserve.",
    "VES": "Border league maintains defensive land practice over a small regional workshop base.",
    "VLD": "Small southern coastal union protects an inherited oil field with militia and a fragmentary workshop base.",
    "VRA": "Dispersed lighthouse islands preserve basic workshops and militia practice without advanced institutions.",
    "VLA": "Institutionally capable successor with four research slots, a standing army, and an air base.",
    "WEF": "Organized frontier administration with factories, a standing formation, and an air base.",
    "WIT": "Organized state with a standing army and a large inherited convoy reserve.",
    "WRK": "Largest surviving industrial state with five research slots, power sites, air bases, and convoy capacity.",
    "WCG": "Vorkerland's sealed border administration fields defensive infantry while requisitions and quarantine suppress broader development.",
    "YPR": "Army-bearing regional polity whose small economy remains fragmentary.",
    "ZAO": "High-slot autonomous zone still lacks the factories and infrastructure for broad recovered packages.",
}


ENABLE_SUBUNITS = {
    "ADISCORD_tech_remote_weapon_tripods": ("ADISCORD_assault_infantry",),
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
    "ADISCORD_tech_drone_recon_swarms": (
        "ADISCORD_recon_platform",
        "hq_light_armor",
    ),
    "ADISCORD_tech_armored_carrier_program": (
        "ADISCORD_mechanized_infantry",
    ),
    "ADISCORD_tech_semi_autonomous_combat_modules": (
        "ADISCORD_combat_platform",
        "hq_medium_armor",
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
    # Heavy strategic-resource complexes.
    "ADISCORD_tech_logistics_hub_networks": (("ADISCORD_thermal_power_complex", 1),),
    "ADISCORD_tech_borehole_sensor_grids": (("ADISCORD_strategic_mining_complex", 1),),
    "ADISCORD_tech_plasma_scrap_separation": (("ADISCORD_electrolysis_complex", 1),),
    "ADISCORD_tech_microbial_tailings_leaching": (("ADISCORD_metallurgical_complex", 1),),
    # Rubber and fuel infrastructure lost when common/technologies was replaced.
    "ADISCORD_tech_grid_rationing": (("fuel_silo", 3),),
    "ADISCORD_tech_synthetic_resource_cycles": (("synthetic_refinery", 1),),
    "ADISCORD_tech_rare_earth_solvent_loops": (("synthetic_refinery", 2),),
    "ADISCORD_tech_carbon_feedstock_cracking": (("synthetic_refinery", 3),),
    # Air defence and detection caps.
    "ADISCORD_tech_radar_laying": (("anti_air_building", 1),),
    "ADISCORD_tech_point_defense_aa": (("anti_air_building", 3),),
    "ADISCORD_tech_networked_air_defense": (("anti_air_building", 4),),
    "ADISCORD_tech_directed_energy_air_defense": (("anti_air_building", 5),),
    "ADISCORD_tech_field_radio_networks": (("radar_station", 1),),
    "ADISCORD_tech_signal_intercept_arrays": (("radar_station", 2),),
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
    "ADISCORD_tech_high_pressure_polymer_synthesis": (
        ("ADISCORD_metallurgical_complex", "steel", 2),
    ),
    "ADISCORD_tech_isotope_selective_refining": (
        ("ADISCORD_metallurgical_complex", "steel", 2),
    ),
    "ADISCORD_tech_rare_earth_solvent_loops": (
        ("ADISCORD_electrolysis_complex", "aluminium", 2),
        ("synthetic_refinery", "rubber", 1),
    ),
    "ADISCORD_tech_strategic_element_reclamation": (
        ("ADISCORD_electrolysis_complex", "aluminium", 1),
        ("synthetic_refinery", "rubber", 2),
    ),
    "ADISCORD_tech_automated_deep_mining": (
        ("ADISCORD_strategic_mining_complex", "tungsten", 1),
    ),
    "ADISCORD_tech_urban_mine_cartography": (
        ("ADISCORD_strategic_mining_complex", "tungsten", 1),
    ),
}


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


PROGRAMME_INDEX_SETS = {
    "production": {
        "flexible_tooling": (5, 7, 9, 12, 14, 16),
        "volume_automation": (6, 8, 10, 13, 15, 17),
    },
    "resources": {
        "primary_extraction": (5, 7, 9, 12, 14, 16),
        "circular_recovery": (6, 8, 10, 13, 15, 17),
    },
    "administration": {
        "local_services": (5, 7, 9, 12, 14, 16),
        "automated_state": (6, 8, 10, 13, 15, 17),
    },
    "civil_resilience": {
        "emergency_services": (5, 7, 9, 12, 14, 16),
        "distributed_resilience": (6, 8, 10, 13, 15, 17),
    },
    "small_arms": {
        "rifles": (5, 7, 9, 10, 15, 18),
        "ammunition": (3, 6, 11, 13, 14, 16),
        "optics": (4, 8, 12, 17),
    },
    "squad_weapons": {
        "explosive": (1, 2, 3, 5, 11, 16),
        "command": (4, 6, 8, 9, 12, 15),
        "automatic": (7, 10, 13, 14, 17),
    },
    "protection": {
        "body": (1, 3, 6, 8, 9, 14),
        "medicine": (4, 10, 11, 15),
        "environment": (2, 5, 7, 12, 13, 16),
    },
    "special_forces": {
        "urban": (1, 3, 5, 16),
        "reconnaissance": (2, 4, 6, 7, 8, 11, 13, 14, 15),
        "airborne": (9, 10, 12, 17),
    },
    "field_support": {
        "field_services": (5, 7, 9, 12, 14, 16),
        "engineering": (6, 8, 10, 13, 15, 17),
    },
    "logistics": {
        "resilience": (5, 7, 9, 11, 13, 15, 17),
        "automation": (6, 8, 10, 12, 14, 16, 18),
    },
    "rail": {
        "network": (5, 7, 9, 12, 14, 16),
        "railway_artillery": (6, 8, 10, 13, 15, 17),
    },
    "anti_tank": {
        "missile": (5, 7, 9),
        "seeker": (6, 8, 10),
        "ambush": (12, 14, 16),
        "coil": (13, 15, 17),
    },
    "artillery": {
        "fire_control": (5, 7, 9),
        "guided_munitions": (6, 8, 10),
        "mass_fire": (12, 14, 16),
        "autonomous_battery": (13, 15, 17),
    },
    "anti_air": {
        "sensors": (5, 7, 9, 12, 14, 16),
        "directed_energy": (6, 8, 10, 13, 15, 17),
    },
    "recon_armor": {
        "active_sensors": (5, 7, 9),
        "silent_mobility": (6, 8, 10),
        "signature_control": (12, 14, 16),
        "autonomous_screen": (13, 15, 17),
    },
    "combat_armor": {
        "armored_offense": (5, 7, 9, 11, 13, 15, 17),
        "armored_survival": (6, 8, 10, 12, 14, 16, 18),
    },
    "heavy_armor": {
        "survivability": (5, 7, 9, 12, 14, 16),
        "siege": (6, 8, 10, 13, 15, 17),
    },
    "air_support": {
        "precision": (5, 7, 9, 12, 14, 16),
        "persistent": (6, 8, 10, 13, 15, 17),
    },
    "fighter": {
        "flight_control": (5, 7, 9),
        "interception": (6, 8, 10),
        "endurance": (12, 14, 16),
        "wingmen": (13, 15, 17),
    },
    "naval_support": {
        "sensors": (5, 7, 9, 12, 14, 16),
        "unmanned_screen": (6, 8, 10, 13, 15, 17),
    },
    "surface_fleet": {
        "fleet_strike": (5, 7, 9, 11, 13, 15, 17),
        "fleet_defense": (6, 8, 10, 12, 14, 16, 18),
    },
    "subsurface": {
        "silent_hunter": (5, 7, 9),
        "torpedo_boat": (6, 8, 10),
        "deep_network": (12, 14, 16),
        "autonomous_pack": (13, 15, 17),
    },
}


def programme_for(branch_key: str, index: int) -> tuple[str | None, int]:
    for programme, indices in PROGRAMME_INDEX_SETS.get(branch_key, {}).items():
        if index in indices:
            return programme, indices.index(index)
    return None, 0


def integrated_capstone_effects(
    branch_key: str,
    small: float,
    medium: float,
    organisation: float,
) -> tuple[str, ...] | None:
    packages = {
        "production": (
            f"industrial_capacity_factory = {n(medium)}",
            f"production_factory_efficiency_gain_factor = {n(small)}",
            f"line_change_production_efficiency_factor = {n(medium)}",
        ),
        "resources": (
            f"local_resources_factor = {n(medium)}",
            f"fuel_gain_factor = {n(small)}",
            f"production_lack_of_resource_penalty_factor = -{n(small)}",
        ),
        "administration": (
            f"research_speed_factor = {n(small)}",
            f"consumer_goods_factor = -{n(small / 2)}",
            f"political_power_gain = {n(small / 2)}",
        ),
        "small_arms": (
            f"category_all_infantry = {{ soft_attack = {n(medium)} hard_attack = {n(medium)} breakthrough = {n(small)} }}",
        ),
        "civil_resilience": (
            f"industry_repair_factor = {n(medium)}",
            f"stability_factor = {n(small)}",
            f"production_speed_infrastructure_factor = {n(small)}",
        ),
        "squad_weapons": (
            f"category_all_infantry = {{ soft_attack = {n(medium)} defense = {n(medium)} max_organisation = {n(organisation)} }}",
        ),
        "protection": (
            f"category_all_infantry = {{ defense = {n(medium)} default_morale = {n(small)} supply_consumption = -{n(small / 2)} }}",
        ),
        "special_forces": (
            f"category_special_forces = {{ breakthrough = {n(medium)} defense = {n(medium)} max_organisation = {n(organisation)} }}",
        ),
        "field_support": (
            f"category_support_battalions = {{ defense = {n(medium)} default_morale = {n(small)} max_organisation = {n(organisation)} }}",
        ),
        "logistics": (
            f"supply_consumption_factor = -{n(medium)}",
            f"land_reinforce_rate = {n(small)}",
            f"org_loss_when_moving = -{n(small)}",
        ),
        "rail": (
            f"artillery = {{ soft_attack = {n(medium)} reliability = {n(small)} }}",
            f"industry_repair_factor = {n(medium)}",
        ),
        "artillery": (
            f"artillery = {{ soft_attack = {n(medium)} hard_attack = {n(medium)} reliability = {n(small)} }}",
            f"coordination_bonus = {n(small)}",
        ),
        "anti_tank": (
            f"category_anti_tank = {{ hard_attack = {n(medium)} ap_attack = {n(medium)} reliability = {n(small)} }}",
        ),
        "anti_air": (
            f"anti_air = {{ air_attack = {n(medium)} reliability = {n(medium)} }}",
            f"air_intercept_efficiency = {n(small)}",
        ),
        "recon_armor": (
            f"category_all_armor = {{ maximum_speed = {n(small)} reliability = {n(medium)} defense = {n(medium)} }}",
        ),
        "combat_armor": (
            f"category_all_armor = {{ breakthrough = {n(medium)} armor_value = {n(medium)} reliability = {n(small)} }}",
        ),
        "heavy_armor": (
            f"category_all_armor = {{ armor_value = {n(medium)} breakthrough = {n(medium)} reliability = {n(small)} }}",
        ),
        "air_support": (
            f"ground_attack_factor = {n(medium)}",
            f"air_mission_efficiency = {n(medium)}",
            f"air_accidents_factor = -{n(small)}",
        ),
        "fighter": (
            f"air_intercept_efficiency = {n(medium)}",
            f"air_mission_efficiency = {n(medium)}",
            f"air_accidents_factor = -{n(small)}",
        ),
        "naval_support": (
            f"convoy_escort_efficiency = {n(medium)}",
            f"naval_detection = {n(medium)}",
            f"naval_coordination = {n(small)}",
        ),
        "surface_fleet": (
            f"naval_hit_chance = {n(medium)}",
            f"naval_coordination = {n(medium)}",
            f"naval_detection = {n(small)}",
        ),
        "subsurface": (
            f"naval_detection = {n(medium)}",
            f"naval_mines_effect_reduction = {n(medium)}",
            f"naval_coordination = {n(small)}",
        ),
    }
    return packages.get(branch_key)


def integrated_stage_effects(
    branch_key: str,
    stage: int,
    small: float,
    medium: float,
    organisation: float,
) -> tuple[str, ...] | None:
    """Reward intermediate programme convergence with a mixed capability."""

    packages = {
        "production": (
            (
                f"industrial_capacity_factory = {n(small)}",
                f"production_factory_efficiency_gain_factor = {n(medium)}",
            ),
            (
                f"production_factory_max_efficiency_factor = {n(medium)}",
                f"line_change_production_efficiency_factor = {n(medium)}",
            ),
        ),
        "resources": (
            (
                f"local_resources_factor = {n(medium)}",
                f"production_lack_of_resource_penalty_factor = -{n(small)}",
            ),
            (
                f"fuel_gain_factor = {n(medium)}",
                f"industry_repair_factor = {n(small)}",
            ),
        ),
        "administration": (
            (
                f"research_speed_factor = {n(small)}",
                f"political_power_gain = {n(small)}",
            ),
            (
                f"consumer_goods_factor = -{n(small)}",
                f"coordination_bonus = {n(medium)}",
            ),
        ),
        "field_support": (
            (
                f"engineer = {{ entrenchment = {n(organisation / 2)} defense = {n(small)} }}",
                f"field_hospital = {{ casualty_trickleback = {n(small)} }}",
            ),
            (
                f"maintenance_company = {{ reliability = {n(medium)} }}",
                f"category_support_battalions = {{ max_organisation = {n(organisation)} }}",
            ),
        ),
        "rail": (
            (
                f"industry_repair_factor = {n(medium)}",
                f"artillery = {{ reliability = {n(small)} }}",
            ),
            (
                f"supply_consumption_factor = -{n(small)}",
                f"artillery = {{ soft_attack = {n(medium)} }}",
            ),
        ),
        "artillery": (
            (
                f"artillery = {{ soft_attack = {n(medium)} reliability = {n(small)} }}",
                f"planning_speed = {n(small)}",
            ),
            (
                f"artillery = {{ hard_attack = {n(medium)} breakthrough = {n(small)} }}",
                f"coordination_bonus = {n(small)}",
            ),
        ),
        "anti_air": (
            (
                f"anti_air = {{ air_attack = {n(medium)} reliability = {n(small)} }}",
                f"air_intercept_efficiency = {n(small)}",
            ),
            (
                f"anti_air = {{ air_attack = {n(medium)} defense = {n(small)} }}",
                f"coordination_bonus = {n(small)}",
            ),
        ),
        "heavy_armor": (
            (
                f"category_all_armor = {{ armor_value = {n(medium)} breakthrough = {n(small)} }}",
            ),
            (
                f"category_all_armor = {{ reliability = {n(medium)} defense = {n(small)} }}",
            ),
        ),
        "fighter": (
            (
                f"air_intercept_efficiency = {n(medium)}",
                f"air_agility_factor = {n(small)}",
            ),
            (
                f"air_mission_efficiency = {n(medium)}",
                f"air_accidents_factor = -{n(small)}",
            ),
        ),
        "air_support": (
            (
                f"ground_attack_factor = {n(medium)}",
                f"air_range_factor = {n(small)}",
            ),
            (
                f"air_mission_efficiency = {n(medium)}",
                f"air_accidents_factor = -{n(small)}",
            ),
        ),
        "naval_support": (
            (
                f"naval_detection = {n(medium)}",
                f"convoy_escort_efficiency = {n(small)}",
            ),
            (
                f"naval_mines_effect_reduction = {n(medium)}",
                f"naval_coordination = {n(small)}",
            ),
        ),
    }
    stages = packages.get(branch_key)
    return stages[stage % len(stages)] if stages else None


def themed_programme_effects(
    branch_key: str,
    programme: str,
    step: int,
    small: float,
    medium: float,
    organisation: float,
) -> tuple[str, ...]:
    """Give programme nodes distinct roles instead of a repeated branch bonus."""

    phase = step % 3
    if programme == "flexible_tooling":
        return (
            f"line_change_production_efficiency_factor = {n(medium * 1.5)}",
            f"production_factory_efficiency_gain_factor = {n(small)}",
        ) if phase % 2 == 0 else (
            f"production_factory_start_efficiency_factor = {n(medium)}",
            f"production_lack_of_resource_penalty_factor = -{n(small)}",
        )
    if programme == "volume_automation":
        return (
            f"industrial_capacity_factory = {n(medium)}",
            f"production_factory_max_efficiency_factor = {n(small)}",
        ) if phase % 2 == 0 else (
            f"production_factory_max_efficiency_factor = {n(medium)}",
            f"industrial_capacity_factory = {n(small)}",
        )
    if programme == "primary_extraction":
        return (
            f"local_resources_factor = {n(medium)}",
            f"fuel_gain_factor = {n(small)}",
        ) if phase % 2 == 0 else (
            f"local_resources_factor = {n(medium * 1.25)}",
            f"production_lack_of_resource_penalty_factor = -{n(small / 2)}",
        )
    if programme == "circular_recovery":
        return (
            f"production_lack_of_resource_penalty_factor = -{n(medium)}",
            f"industry_repair_factor = {n(small)}",
        ) if phase % 2 == 0 else (
            f"local_resources_factor = {n(small)}",
            f"fuel_gain_factor = {n(medium)}",
        )
    if programme == "local_services":
        return (
            f"consumer_goods_factor = -{n(small)}",
            f"political_power_gain = {n(small / 2)}",
        ) if phase % 2 == 0 else (
            f"stability_factor = {n(small / 2)}",
            f"production_factory_start_efficiency_factor = {n(small)}",
        )
    if programme == "automated_state":
        return (
            f"research_speed_factor = {n(small)}",
            f"coordination_bonus = {n(small / 2)}",
        ) if phase % 2 == 0 else (
            f"planning_speed = {n(medium)}",
            f"production_factory_efficiency_gain_factor = {n(small / 2)}",
        )
    if programme == "emergency_services":
        return (
            f"industry_repair_factor = {n(medium)}",
            f"production_speed_infrastructure_factor = {n(small)}",
        ) if phase == 0 else (
            f"stability_factor = {n(small)}",
            f"industry_repair_factor = {n(medium)}",
        ) if phase == 1 else (
            f"production_speed_buildings_factor = {n(small)}",
            f"industry_repair_factor = {n(medium)}",
        )
    if programme == "distributed_resilience":
        return (
            f"stability_factor = {n(medium / 2)}",
            f"supply_consumption_factor = -{n(small / 2)}",
        ) if phase == 0 else (
            f"production_speed_infrastructure_factor = {n(small)}",
            f"stability_factor = {n(small)}",
        ) if phase == 1 else (
            f"consumer_goods_factor = -{n(small / 2)}",
            f"industry_repair_factor = {n(small)}",
        )
    infantry_packages = {
        "rifles": (
            (f"category_all_infantry = {{ soft_attack = {n(medium)} breakthrough = {n(small)} }}",),
            (f"category_all_infantry = {{ soft_attack = {n(medium)} reliability = {n(small)} }}",),
        ),
        "ammunition": (
            (f"category_all_infantry = {{ hard_attack = {n(medium)} ap_attack = {n(medium)} }}",),
            (f"category_all_infantry = {{ soft_attack = {n(medium)} hard_attack = {n(small)} }}",),
        ),
        "optics": (
            (f"coordination_bonus = {n(medium)}", f"land_night_attack = {n(small / 2)}"),
            (f"planning_speed = {n(medium)}", f"land_reinforce_rate = {n(small / 2)}"),
        ),
        "explosive": (
            (f"category_all_infantry = {{ soft_attack = {n(medium)} hard_attack = {n(small)} }}",),
            (f"category_all_infantry = {{ breakthrough = {n(medium)} ap_attack = {n(small)} }}",),
        ),
        "command": (
            (f"category_all_infantry = {{ max_organisation = {n(organisation)} default_morale = {n(small)} }}",),
            (f"coordination_bonus = {n(medium)}", f"land_reinforce_rate = {n(small / 2)}"),
        ),
        "automatic": (
            (f"category_all_infantry = {{ soft_attack = {n(medium)} breakthrough = {n(small)} }}",),
            (f"category_all_infantry = {{ soft_attack = {n(medium)} defense = {n(small)} }}",),
        ),
        "body": (
            (f"category_all_infantry = {{ defense = {n(medium)} reliability = {n(small)} }}",),
            (f"category_all_infantry = {{ defense = {n(medium)} breakthrough = {n(small)} }}",),
        ),
        "environment": (
            (f"category_all_infantry = {{ defense = {n(medium)} supply_consumption = -{n(small / 2)} }}",),
            (f"category_all_infantry = {{ default_morale = {n(medium)} defense = {n(small)} }}",),
        ),
        "urban": (
            (f"category_special_forces = {{ soft_attack = {n(medium)} breakthrough = {n(medium)} }}",),
            (f"category_special_forces = {{ breakthrough = {n(medium)} defense = {n(small)} }}",),
        ),
        "reconnaissance": (
            (f"category_recon = {{ recon = {n(0.35 + step * 0.04)} }}", f"category_special_forces = {{ maximum_speed = {n(small / 2)} }}"),
            (f"category_recon = {{ recon = {n(0.30 + step * 0.04)} }}", f"land_night_attack = {n(small / 2)}"),
        ),
        "airborne": (
            (f"category_special_forces = {{ maximum_speed = {n(small)} supply_consumption = -{n(small / 2)} }}",),
            (f"category_special_forces = {{ max_organisation = {n(organisation)} breakthrough = {n(small)} }}",),
        ),
    }
    if programme in infantry_packages:
        return infantry_packages[programme][phase % len(infantry_packages[programme])]

    if branch_key == "protection" and programme == "medicine":
        return (
            f"field_hospital = {{ casualty_trickleback = {n(medium)} experience_loss_factor = -{n(small)} }}",
        ) if phase % 2 == 0 else (
            f"field_hospital = {{ casualty_trickleback = {n(small)} experience_loss_factor = -{n(medium)} }}",
            f"category_all_infantry = {{ default_morale = {n(small)} }}",
        )
    if programme == "field_services":
        return (
            f"field_hospital = {{ casualty_trickleback = {n(medium)} experience_loss_factor = -{n(small)} }}",
            f"category_support_battalions = {{ default_morale = {n(small)} }}",
        ) if phase % 2 == 0 else (
            f"maintenance_company = {{ reliability = {n(medium)} }}",
            f"category_support_battalions = {{ max_organisation = {n(organisation)} }}",
        )
    if programme == "engineering":
        return (
            f"engineer = {{ entrenchment = {n(organisation / 2)} defense = {n(small)} }}",
        ) if phase % 2 == 0 else (
            f"category_support_battalions = {{ breakthrough = {n(medium)} defense = {n(small)} }}",
        )
    if programme == "resilience":
        return (
            f"logistics_company = {{ supply_consumption = -{n(medium)} }}",
            f"industry_repair_factor = {n(small)}",
        ) if phase % 2 == 0 else (
            f"supply_consumption_factor = -{n(medium)}",
            f"category_support_battalions = {{ default_morale = {n(small)} }}",
        )
    if programme == "automation":
        return (
            f"land_reinforce_rate = {n(medium)}",
            f"org_loss_when_moving = -{n(small)}",
        ) if phase == 0 else (
            f"planning_speed = {n(medium)}",
            f"supply_consumption_factor = -{n(small)}",
        ) if phase == 1 else (
            f"logistics_company = {{ supply_consumption = -{n(small)} }}",
            f"coordination_bonus = {n(medium)}",
        )
    if programme == "network":
        return (
            f"supply_consumption_factor = -{n(small)}",
            f"industry_repair_factor = {n(medium)}",
        ) if phase == 0 else (
            f"land_reinforce_rate = {n(small)}",
            f"supply_consumption_factor = -{n(medium)}",
        ) if phase == 1 else (
            f"production_speed_infrastructure_factor = {n(small)}",
            f"industry_repair_factor = {n(medium)}",
        )
    if programme == "railway_artillery":
        return (
            f"artillery = {{ soft_attack = {n(medium)} hard_attack = {n(small)} }}",
        ) if phase == 0 else (
            f"artillery = {{ reliability = {n(medium)} breakthrough = {n(small)} }}",
        ) if phase == 1 else (
            f"planning_speed = {n(medium)}",
            f"coordination_bonus = {n(small)}",
        )

    anti_tank_packages = {
        "missile": (f"category_anti_tank = {{ hard_attack = {n(medium)} ap_attack = {n(medium)} }}",),
        "seeker": (f"category_anti_tank = {{ reliability = {n(medium)} defense = {n(small)} }}",),
        "ambush": (f"category_anti_tank = {{ hard_attack = {n(medium)} defense = {n(small)} }}",),
        "coil": (f"category_anti_tank = {{ ap_attack = {n(medium)} breakthrough = {n(small)} }}",),
    }
    if programme in anti_tank_packages:
        return anti_tank_packages[programme]

    artillery_packages = {
        "fire_control": (
            (f"artillery = {{ soft_attack = {n(medium)} reliability = {n(small)} }}",),
            (f"coordination_bonus = {n(medium)}", f"planning_speed = {n(small)}"),
        ),
        "guided_munitions": (
            (f"artillery = {{ hard_attack = {n(medium)} ap_attack = {n(medium)} }}",),
            (f"artillery = {{ soft_attack = {n(medium)} breakthrough = {n(small)} }}",),
        ),
        "mass_fire": (
            (f"artillery = {{ soft_attack = {n(medium)} breakthrough = {n(small)} }}",),
            (f"artillery = {{ soft_attack = {n(medium)} reliability = {n(medium)} }}",),
        ),
        "autonomous_battery": (
            (f"artillery = {{ hard_attack = {n(medium)} reliability = {n(small)} }}",),
            (f"coordination_bonus = {n(medium)}", f"planning_speed = {n(small)}"),
        ),
    }
    if programme in artillery_packages:
        packages = artillery_packages[programme]
        return packages[phase % len(packages)]

    anti_air_packages = {
        "sensors": (f"anti_air = {{ air_attack = {n(small)} reliability = {n(medium)} }}", f"coordination_bonus = {n(small / 2)}"),
        "kinetic": (f"anti_air = {{ air_attack = {n(medium)} soft_attack = {n(small)} }}",),
        "directed_energy": (f"anti_air = {{ air_attack = {n(medium)} reliability = {n(medium)} }}", f"air_intercept_efficiency = {n(small)}"),
    }
    if branch_key == "anti_air" and programme in anti_air_packages:
        return anti_air_packages[programme]

    recon_armor_packages = {
        "active_sensors": (f"category_all_armor = {{ reliability = {n(small)} defense = {n(medium)} }}", f"category_recon = {{ recon = {n(0.35 + step * 0.05)} }}"),
        "silent_mobility": (f"category_all_armor = {{ maximum_speed = {n(medium)} reliability = {n(small)} }}",),
        "signature_control": (f"category_all_armor = {{ defense = {n(medium)} breakthrough = {n(small)} }}",),
        "autonomous_screen": (f"category_all_armor = {{ maximum_speed = {n(small)} breakthrough = {n(medium)} }}",),
    }
    if programme in recon_armor_packages:
        return recon_armor_packages[programme]

    if programme == "armored_offense":
        return (
            f"category_all_armor = {{ breakthrough = {n(medium)} hard_attack = {n(medium)} }}",
        ) if phase == 0 else (
            f"category_all_armor = {{ soft_attack = {n(medium)} maximum_speed = {n(small)} }}",
        ) if phase == 1 else (
            f"category_all_armor = {{ hard_attack = {n(medium)} reliability = {n(small)} }}",
        )
    if programme == "armored_survival":
        return (
            f"category_all_armor = {{ armor_value = {n(medium)} defense = {n(medium)} }}",
        ) if phase == 0 else (
            f"category_all_armor = {{ reliability = {n(medium)} defense = {n(small)} }}",
        ) if phase == 1 else (
            f"category_all_armor = {{ armor_value = {n(medium)} default_morale = {n(small)} }}",
        )

    if programme == "survivability":
        return (
            f"category_all_armor = {{ armor_value = {n(medium)} reliability = {n(small)} }}",
        ) if phase % 2 == 0 else (
            f"category_all_armor = {{ defense = {n(medium)} reliability = {n(medium)} }}",
        )
    if programme == "siege":
        return (
            f"category_all_armor = {{ breakthrough = {n(medium)} hard_attack = {n(medium)} }}",
        ) if phase == 0 else (
            f"category_all_armor = {{ soft_attack = {n(medium)} breakthrough = {n(small)} }}",
        ) if phase == 1 else (
            f"category_all_armor = {{ maximum_speed = {n(small)} reliability = {n(medium)} }}",
        )
    if programme == "precision":
        return (
            f"ground_attack_factor = {n(medium)}",
            f"air_mission_efficiency = {n(small)}",
        ) if phase % 2 == 0 else (
            f"air_attack_factor = {n(small)}",
            f"air_range_factor = {n(medium)}",
        )
    if programme == "persistent":
        return (
            f"ground_attack_factor = {n(medium)}",
            f"air_accidents_factor = -{n(small)}",
        ) if phase == 0 else (
            f"air_agility_factor = {n(medium)}",
            f"air_mission_efficiency = {n(small)}",
        ) if phase == 1 else (
            f"air_mission_efficiency = {n(medium)}",
            f"air_accidents_factor = -{n(medium)}",
        )

    if programme == "flight_control":
        return (
            f"air_agility_factor = {n(medium)}",
            f"air_accidents_factor = -{n(small)}",
        ) if phase % 2 == 0 else (
            f"air_range_factor = {n(medium)}",
            f"air_mission_efficiency = {n(small)}",
        )
    if programme == "interception":
        return (
            f"air_intercept_efficiency = {n(medium)}",
            f"air_attack_factor = {n(small)}",
        ) if phase % 2 == 0 else (
            f"air_mission_efficiency = {n(medium)}",
            f"air_agility_factor = {n(small)}",
        )
    if programme == "endurance":
        return (
            f"air_range_factor = {n(medium)}",
            f"air_accidents_factor = -{n(small)}",
        ) if phase % 2 == 0 else (
            f"air_mission_efficiency = {n(medium)}",
            f"air_agility_factor = {n(small)}",
        )
    if programme == "wingmen":
        return (
            f"air_attack_factor = {n(medium)}",
            f"air_mission_efficiency = {n(small)}",
        ) if phase % 2 == 0 else (
            f"air_accidents_factor = -{n(medium)}",
            f"air_intercept_efficiency = {n(small)}",
        )

    if programme == "fleet_strike":
        return (
            f"naval_hit_chance = {n(medium)}",
            f"naval_coordination = {n(small)}",
        ) if phase % 2 == 0 else (
            f"naval_speed_factor = {n(small)}",
            f"naval_hit_chance = {n(medium)}",
        )
    if programme == "fleet_defense":
        return (
            f"naval_detection = {n(medium)}",
            f"convoy_escort_efficiency = {n(small)}",
        ) if phase % 2 == 0 else (
            f"naval_mines_effect_reduction = {n(medium)}",
            f"naval_coordination = {n(small)}",
        )

    naval_packages = {
        "sensors": (f"naval_detection = {n(medium)}", f"naval_coordination = {n(small)}"),
        "escort_hulls": (f"convoy_escort_efficiency = {n(medium)}", f"naval_speed_factor = {n(small)}"),
        "unmanned_screen": (f"naval_detection = {n(small)}", f"naval_mines_effect_reduction = {n(medium)}"),
        "silent_hunter": (f"naval_detection = {n(medium)}", f"naval_mines_effect_reduction = {n(small)}"),
        "torpedo_boat": (f"naval_hit_chance = {n(medium)}", f"naval_coordination = {n(small)}"),
        "deep_network": (f"naval_detection = {n(medium)}", f"convoy_escort_efficiency = {n(small)}"),
        "autonomous_pack": (f"naval_coordination = {n(medium)}", f"naval_detection = {n(small)}"),
    }
    return naval_packages[programme]


# Deliberate packages for the compact strategic trunks.  These are keyed by
# stable technology keys rather than list positions so later layout tweaks do
# not silently change the economic model.
COMPACT_EFFECTS_BY_TECH_KEY = {
    "armored_carrier_program": (
        "ADISCORD_mechanized_infantry = { defense = 0.03 reliability = 0.03 }",
    ),
    "infantry_combat_vehicle_program": (
        "ADISCORD_mechanized_infantry = { breakthrough = 0.05 soft_attack = 0.05 hard_attack = 0.03 }",
    ),
    "networked_mechanized_cells": (
        "ADISCORD_mechanized_infantry = { maximum_speed = 0.05 reliability = 0.05 }",
        "coordination_bonus = 0.02",
    ),
    "standardized_machine_tools": (
        "production_factory_max_efficiency_factor = 0.03",
        "production_factory_efficiency_gain_factor = 0.02",
    ),
    "interchangeable_components": (
        "production_factory_start_efficiency_factor = 0.03",
        "line_change_production_efficiency_factor = 0.04",
    ),
    "industrial_cluster_planning": (
        "production_speed_industrial_complex_factor = 0.03",
        "production_speed_arms_factory_factor = 0.03",
    ),
    "precision_metrology_recovery": (
        "production_factory_max_efficiency_factor = 0.04",
        "production_factory_efficiency_gain_factor = 0.03",
    ),
    "automated_assembly": (
        "industrial_capacity_factory = 0.015",
        "production_factory_efficiency_gain_factor = 0.03",
    ),
    "digital_tooling_libraries": (
        "production_factory_start_efficiency_factor = 0.05",
        "line_change_production_efficiency_factor = 0.08",
    ),
    "sensor_calibrated_machining": (
        "production_factory_max_efficiency_factor = 0.06",
        "production_factory_efficiency_gain_factor = 0.04",
    ),
    "predictive_maintenance": (
        "production_factory_efficiency_gain_factor = 0.05",
        "industry_repair_factor = 0.04",
    ),
    "autonomous_factory_cells": (
        "industrial_capacity_factory = 0.025",
        "factory_energy_consumption = 0.04",
        "production_factory_max_efficiency_factor = 0.05",
    ),
    "lights_out_microfactories": (
        "industrial_capacity_factory = 0.03",
        "factory_energy_consumption = 0.06",
        "production_factory_efficiency_gain_factor = 0.04",
    ),
    "distributed_manufacturing": (
        "industrial_capacity_factory = 0.035",
        "industrial_capacity_dockyard = 0.025",
        "factory_energy_consumption = 0.07",
        "production_factory_max_efficiency_factor = 0.06",
    ),
    "industrial_organization_baseline": (
        "production_factory_start_efficiency_factor = 0.02",
        "production_factory_efficiency_gain_factor = 0.02",
    ),
    "concentrated_industrial_zones": (
        "industrial_capacity_factory = 0.04",
        "industrial_capacity_dockyard = 0.03",
        "factory_energy_consumption = 0.08",
        "industry_air_damage_factor = 0.05",
    ),
    "megafactory_power_buses": (
        "industrial_capacity_factory = 0.05",
        "industrial_capacity_dockyard = 0.04",
        "factory_energy_consumption = 0.12",
        "line_change_production_efficiency_factor = -0.10",
    ),
    "strategic_production_complexes": (
        "industrial_capacity_factory = 0.07",
        "industrial_capacity_dockyard = 0.06",
        "factory_energy_consumption = 0.18",
        "industry_air_damage_factor = 0.10",
        "line_change_production_efficiency_factor = -0.10",
    ),
    "distributed_workshop_networks": (
        "industrial_capacity_factory = 0.02",
        "factory_energy_consumption = 0.015",
        "production_factory_start_efficiency_factor = 0.05",
        "industry_air_damage_factor = -0.05",
    ),
    "regional_spare_capacity": (
        "industrial_capacity_factory = 0.02",
        "factory_energy_consumption = 0.015",
        "line_change_production_efficiency_factor = 0.10",
        "industry_repair_factor = 0.08",
    ),
    "resilient_production_meshes": (
        "industrial_capacity_factory = 0.03",
        "factory_energy_consumption = 0.025",
        "production_factory_start_efficiency_factor = 0.07",
        "line_change_production_efficiency_factor = 0.15",
        "industry_air_damage_factor = -0.12",
        "industry_repair_factor = 0.15",
    ),
    "mesh_command_networks": (
        "coordination_bonus = 0.01",
        "encryption_factor = 0.01",
    ),
    "field_radio_networks": (
        "land_reinforce_rate = 0.01",
        "encryption_factor = 0.02",
    ),
    "encryption_rebuild": (
        "encryption_factor = 0.03",
        "coordination_bonus = 0.01",
    ),
    "frequency_hopping_field_sets": (
        "encryption_factor = 0.04",
        "land_reinforce_rate = 0.01",
    ),
    "signal_intercept_arrays": (
        "decryption_factor = 0.04",
        "air_interception_detect_factor = 0.02",
    ),
    "passive_emitter_geolocation": (
        "decryption_factor = 0.04",
        "recon_factor = 0.02",
    ),
    "battlefield_analytics": (
        "coordination_bonus = 0.02",
        "decryption_factor = 0.03",
    ),
    "counterintelligence_filters": (
        "encryption_factor = 0.05",
        "decryption_factor = 0.02",
    ),
    "battlefield_sensor_fusion": (
        "coordination_bonus = 0.03",
        "air_interception_detect_factor = 0.04",
    ),
    "self_healing_tactical_networks": (
        "encryption_factor = 0.06",
        "land_reinforce_rate = 0.02",
    ),
    "memetic_security_protocols": (
        "encryption_factor = 0.07",
        "decryption_factor = 0.04",
        "coordination_bonus = 0.03",
    ),
    "electromechanical_relays": (
        "research_speed_factor = 0.01",
        "production_factory_efficiency_gain_factor = 0.01",
    ),
    "recovered_data_archives": (
        "research_speed_factor = 0.015",
        "planning_speed = 0.01",
    ),
    "recovered_semiconductors": (
        "research_speed_factor = 0.02",
        "production_factory_efficiency_gain_factor = 0.02",
    ),
    "hardened_computers": (
        "research_speed_factor = 0.025",
        "encryption_factor = 0.02",
    ),
    "error_correcting_field_computers": (
        "research_speed_factor = 0.03",
        "encryption_factor = 0.035",
        "supply_consumption_factor = -0.015",
    ),
    "analog_ai_accelerators": (
        "research_speed_factor = 0.03",
        "production_factory_efficiency_gain_factor = 0.04",
        "factory_energy_consumption = 0.05",
    ),
    "predictive_logistics": (
        "research_speed_factor = 0.025",
        "supply_consumption_factor = -0.03",
        "encryption_factor = 0.03",
    ),
    "operational_ai_assistants": (
        "research_speed_factor = 0.025",
        "coordination_bonus = 0.035",
        "factory_energy_consumption = 0.06",
    ),
    "strategic_digital_twins": (
        "research_speed_factor = 0.03",
        "planning_speed = 0.03",
        "production_factory_efficiency_gain_factor = 0.03",
    ),
    "bounded_general_planning_cores": (
        "research_speed_factor = 0.035",
        "coordination_bonus = 0.04",
        "factory_energy_consumption = 0.03",
    ),
    "strategic_ai_coordination": (
        "research_speed_factor = 0.04",
        "coordination_bonus = 0.05",
        "production_factory_efficiency_gain_factor = 0.04",
        "factory_energy_consumption = 0.04",
    ),
    "predictive_budgeting": (
        "consumer_goods_factor = -0.015",
        "production_factory_start_efficiency_factor = 0.03",
    ),
    "local_grid_restoration": (
        "factory_energy_consumption = -0.03",
        "industry_repair_factor = 0.02",
    ),
    "substation_networks": (
        "factory_energy_consumption = -0.035",
        "production_speed_infrastructure_factor = 0.025",
    ),
    "radiation_mapping": (
        "factory_energy_consumption = -0.025",
        "nuclear_production_factor = 0.03",
    ),
    "phase_synchronized_substations": (
        "factory_energy_consumption = -0.04",
        "industry_repair_factor = 0.03",
    ),
    "solid_state_grid_breakers": (
        "factory_energy_consumption = -0.04",
        "industry_air_damage_factor = -0.03",
    ),
    "reactor_safety_protocols": (
        "factory_energy_consumption = -0.04",
        "nuclear_production_factor = 0.05",
    ),
    "load_following_microreactors": (
        "factory_energy_consumption = -0.05",
        "nuclear_production_factor = 0.06",
    ),
    "superconducting_power_busbars": (
        "factory_energy_consumption = -0.05",
        "industrial_capacity_factory = 0.01",
    ),
    "microreactor_blocks": (
        "factory_energy_consumption = -0.055",
        "nuclear_production_factor = 0.07",
    ),
    "passive_decay_heat_sinks": (
        "factory_energy_consumption = -0.035",
        "industry_repair_factor = 0.05",
    ),
    "autonomous_reactor_diagnostics": (
        "factory_energy_consumption = -0.04",
        "nuclear_production_factor = 0.06",
    ),
    "high_density_thermal_storage": (
        "factory_energy_consumption = -0.05",
        "fuel_gain_factor = 0.04",
    ),
    "continental_load_balancing": (
        "factory_energy_consumption = -0.06",
        "production_speed_buildings_factor = 0.04",
    ),
    "emergency_core_suppression": (
        "factory_energy_consumption = -0.07",
        "nuclear_production_factor = 0.08",
        "industry_repair_factor = 0.06",
    ),
    "electromagnetic_recoil_brakes": (
        "artillery = { soft_attack = 0.05 breakthrough = 0.03 }",
    ),
    "predictive_fire_mission_control": (
        "artillery = { soft_attack = 0.08 breakthrough = 0.05 }",
        "planning_speed = 0.02",
    ),
    "loitering_artillery_observers": (
        "artillery = { reliability = 0.05 defense = 0.04 }",
    ),
    "autonomous_battery_network": (
        "artillery = { reliability = 0.08 defense = 0.06 }",
        "coordination_bonus = 0.02",
    ),
    "electromagnetic_main_guns": (
        "category_all_armor = { hard_attack = 0.06 breakthrough = 0.05 }",
    ),
    "distributed_battlegroup": (
        "category_all_armor = { hard_attack = 0.09 breakthrough = 0.08 }",
        "coordination_bonus = 0.02",
    ),
    "adaptive_suspension_control": (
        "category_all_armor = { maximum_speed = 0.05 reliability = 0.05 }",
    ),
    "resilient_combat_cloud_nodes": (
        "category_all_armor = { maximum_speed = 0.07 reliability = 0.08 defense = 0.05 }",
    ),
    "autonomous_dogfight_controller": (
        "air_intercept_efficiency = 0.05",
        "air_accidents_factor = -0.03",
    ),
    "aerospace_interceptors": (
        "air_intercept_efficiency = 0.08",
        "air_mission_efficiency = 0.04",
    ),
    "directed_energy_defensive_suites": (
        "air_mission_efficiency = 0.05",
        "air_accidents_factor = -0.04",
    ),
    "distributed_interceptor_swarms": (
        "air_mission_efficiency = 0.08",
        "air_power_projection_factor = 0.05",
    ),
}


def effects_for(branch: Branch, tier: int) -> tuple[str, ...]:
    """Return an effect package that reflects the actual programme selected.

    Filler-sized 0.4% effects made the old dense tree feel cosmetic.  A narrow
    technology is now normally worth about 1.2-1.8%, while a role-specific
    technology is worth 2-3%.  XOR branches replace, rather than stack, one
    another, keeping their cumulative strength under control.
    """

    tech = branch.techs[tier]
    if branch.key == "small_arms":
        packages = (
            ("category_all_infantry = { soft_attack = 0.012 }",),
            ("category_all_infantry = { defense = 0.012 }",),
            ("category_all_infantry = { soft_attack = 0.014 }",),
            ("category_all_infantry = { soft_attack = 0.014 breakthrough = 0.004 }",),
            ("coordination_bonus = 0.006", "category_all_infantry = { soft_attack = 0.006 }"),
            ("category_all_infantry = { breakthrough = 0.012 soft_attack = 0.006 }",),
            ("category_all_infantry = { defense = 0.014 breakthrough = 0.004 }",),
            ("category_all_infantry = { soft_attack = 0.016 breakthrough = 0.008 }",),
            ("coordination_bonus = 0.008", "category_all_infantry = { soft_attack = 0.008 }"),
            ("category_all_infantry = { soft_attack = 0.018 breakthrough = 0.01 }",),
            ("category_all_infantry = { defense = 0.014 breakthrough = 0.01 }",),
            ("land_night_attack = 0.006", "coordination_bonus = 0.008"),
            ("category_all_infantry = { defense = 0.016 soft_attack = 0.006 }",),
            ("category_all_infantry = { breakthrough = 0.016 defense = 0.006 }",),
            ("category_all_infantry = { defense = 0.012 soft_attack = 0.012 }",),
            ("category_all_infantry = { soft_attack = 0.02 }", "coordination_bonus = 0.012"),
        )
        return packages[tier]
    if branch.key == "anti_tank_infantry":
        packages = (
            ("category_all_infantry = { hard_attack = 0.006 ap_attack = 0.004 }",),
            ("category_all_infantry = { hard_attack = 0.008 breakthrough = 0.004 }",),
            ("category_all_infantry = { hard_attack = 0.01 ap_attack = 0.008 }",),
            ("category_all_infantry = { hard_attack = 0.014 ap_attack = 0.01 }",),
            ("category_all_infantry = { ap_attack = 0.014 }", "coordination_bonus = 0.004"),
            ("category_all_infantry = { hard_attack = 0.016 breakthrough = 0.01 }",),
            ("category_all_infantry = { ap_attack = 0.016 }", "coordination_bonus = 0.006"),
            ("category_all_infantry = { hard_attack = 0.018 ap_attack = 0.016 }",),
            ("category_all_infantry = { ap_attack = 0.018 }", "coordination_bonus = 0.008"),
            ("category_all_infantry = { hard_attack = 0.02 ap_attack = 0.018 }",),
            ("category_all_infantry = { ap_attack = 0.02 }", "coordination_bonus = 0.01"),
            ("category_all_infantry = { hard_attack = 0.024 ap_attack = 0.024 breakthrough = 0.012 }", "coordination_bonus = 0.012"),
        )
        return packages[tier]
    if branch.key == "night_combat":
        packages = (
            ("land_night_attack = 0.005",),
            ("land_night_attack = 0.005", "category_all_infantry = { defense = 0.006 }"),
            ("land_night_attack = 0.006", "category_recon = { recon = 0.12 }"),
            ("land_night_attack = 0.007", "category_all_infantry = { soft_attack = 0.006 }"),
            ("land_night_attack = 0.006", "category_all_infantry = { breakthrough = 0.006 }"),
            ("land_night_attack = 0.007", "coordination_bonus = 0.005"),
            ("land_night_attack = 0.007", "category_all_infantry = { defense = 0.007 }"),
            ("land_night_attack = 0.008", "category_recon = { recon = 0.15 }"),
            ("land_night_attack = 0.008", "category_all_infantry = { defense = 0.008 }"),
            ("land_night_attack = 0.009", "coordination_bonus = 0.007"),
            ("land_night_attack = 0.009", "category_all_infantry = { breakthrough = 0.009 }"),
            ("land_night_attack = 0.012", "coordination_bonus = 0.01", "category_all_infantry = { defense = 0.012 breakthrough = 0.012 }"),
        )
        return packages[tier]
    if tech.key in APPLIED_EFFECTS:
        return tuple(APPLIED_EFFECTS[tech.key])
    compact_effects = COMPACT_EFFECTS_BY_TECH_KEY.get(tech.key)
    if compact_effects:
        return compact_effects

    profile = branch.profile
    tier_count = len(branch.techs)
    progress = 0 if tier_count <= 1 else tier * 6 / (tier_count - 1)
    capstone_scale = 1.45 if tier == tier_count - 1 else 1.0
    small = (0.012 + progress * 0.001) * capstone_scale
    medium = (0.020 + progress * 0.002) * capstone_scale
    organisation = (0.75 + progress * 0.12) * capstone_scale

    if branch.key == "forbidden_energy":
        packages = (
            (f"nuclear_production_factor = {n(0.04)}", f"industry_repair_factor = {n(0.02)}", f"stability_factor = -{n(0.005)}"),
            (f"nuclear_production_factor = {n(0.06)}", f"local_resources_factor = {n(0.02)}", f"stability_factor = -{n(0.008)}"),
            (f"nuclear_production_factor = {n(0.08)}", f"production_speed_buildings_factor = {n(0.025)}", f"stability_factor = -{n(0.011)}"),
            (f"nuclear_production_factor = {n(0.10)}", f"fuel_gain_factor = {n(0.03)}", f"stability_factor = -{n(0.014)}"),
            (f"nuclear_production_factor = {n(0.12)}", f"research_speed_factor = {n(0.025)}", f"stability_factor = -{n(0.017)}"),
            (f"nuclear_production_factor = {n(0.16)}", f"industrial_capacity_factory = {n(0.04)}", f"stability_factor = -{n(0.025)}"),
        )
        return packages[tier]
    if branch.key == "forbidden_automation":
        packages = (
            (f"production_factory_max_efficiency_factor = {n(0.04)}", f"industry_repair_factor = {n(0.03)}", f"stability_factor = -{n(0.01)}"),
            (f"coordination_bonus = {n(0.05)}", f"land_reinforce_rate = {n(0.03)}", f"stability_factor = -{n(0.02)}"),
            (f"production_factory_max_efficiency_factor = {n(0.08)}", f"research_speed_factor = {n(0.04)}", f"stability_factor = -{n(0.035)}"),
        )
        return packages[tier]

    pattern = GRAPH_PATTERN_BY_BRANCH.get(branch.key)
    lane = BRANCH_GRAPHS[branch.key].lanes[tier]
    xor_group = next(
        (group for group in XOR_INDEX_GROUPS_BY_BRANCH.get(branch.key, ()) if tier in group),
        (),
    )
    xor_option = xor_group.index(tier) if xor_group else None

    if tier == tier_count - 1:
        capstone = integrated_capstone_effects(
            branch.key, small, medium, organisation,
        )
        if capstone:
            return capstone

    if BRANCH_GRAPHS[branch.key].dependencies[tier]:
        synthesis_nodes = [
            index
            for index, parents in enumerate(BRANCH_GRAPHS[branch.key].dependencies)
            if parents
        ]
        stage_effects = integrated_stage_effects(
            branch.key,
            synthesis_nodes.index(tier),
            small,
            medium,
            organisation,
        )
        if stage_effects:
            return stage_effects

    programme, programme_step = programme_for(branch.key, tier)
    if programme:
        return themed_programme_effects(
            branch.key, programme, programme_step, small, medium, organisation,
        )

    # Persistent strategic schools.
    if pattern == "dual_choice" and tier >= 5 and tier != 19:
        dual = {
            "reconstruction": {
                # Expansion is the peacetime construction route.  It keeps a
                # small infrastructure dividend so its value is not limited
                # to factory spam.
                0: (
                    f"production_speed_buildings_factor = {n(medium)}",
                    f"production_speed_industrial_complex_factor = {n(small)}",
                    f"production_speed_infrastructure_factor = {n(small / 2)}",
                ),
                # Repair used to be a trap choice: repair speed matters only
                # after damage, while its rival accelerated expansion every
                # day.  Faster restoration now also represents less factory
                # downtime, granting a modest always-on output bonus.
                2: (
                    f"industry_repair_factor = {n(medium * 1.35)}",
                    f"production_speed_infrastructure_factor = {n(small)}",
                    f"industrial_capacity_factory = {n(small / 2)}",
                ),
            },
            "finance": {
                0: (f"production_factory_start_efficiency_factor = {n(medium)}", f"production_factory_efficiency_gain_factor = {n(small)}"),
                2: (f"consumer_goods_factor = -{n(small)}", f"production_lack_of_resource_penalty_factor = -{n(small)}"),
            },
            "combat_armor": {
                0: (f"category_all_armor = {{ breakthrough = {n(medium)} hard_attack = {n(medium)} }}",),
                2: (f"category_all_armor = {{ armor_value = {n(medium)} defense = {n(medium)} reliability = {n(small)} }}",),
            },
            "strategic_air": {
                0: (f"ground_attack_factor = {n(medium)}", f"air_mission_efficiency = {n(small)}"),
                2: (f"strategic_bomb_visibility = -{n(medium)}", f"air_accidents_factor = -{n(small)}"),
            },
            "surface_fleet": {
                0: (f"naval_hit_chance = {n(medium)}", f"naval_coordination = {n(small)}"),
                2: (f"naval_detection = {n(medium)}", f"convoy_escort_efficiency = {n(small)}"),
            },
        }
        return dual[branch.key][lane]

    # Repeated field choices: option A and B consistently favour different
    # operational priorities, while the shared merge nodes use the base line.
    if xor_option is not None and pattern in {"double_choice", "alternating_choices"}:
        choices = {
            "field_support": (
                (f"category_support_battalions = {{ max_organisation = {n(organisation)} defense = {n(small)} }}",),
                (f"category_support_battalions = {{ default_morale = {n(medium)} breakthrough = {n(small)} }}",),
            ),
            "logistics": (
                (f"land_reinforce_rate = {n(medium)}", f"supply_consumption_factor = -{n(small / 2)}"),
                (f"supply_consumption_factor = -{n(medium)}", f"org_loss_when_moving = -{n(small)}"),
            ),
            "rail": (
                (f"industry_repair_factor = {n(medium)}", f"supply_consumption_factor = -{n(small / 2)}"),
                (f"supply_consumption_factor = -{n(medium)}", f"land_reinforce_rate = {n(small)}"),
            ),
            "anti_air": (
                (f"anti_air = {{ air_attack = {n(medium)} reliability = {n(small)} }}",),
                (f"anti_air = {{ defense = {n(medium)} soft_attack = {n(small)} }}",),
            ),
            "heavy_armor": (
                (f"category_all_armor = {{ breakthrough = {n(medium)} hard_attack = {n(medium)} }}",),
                (f"category_all_armor = {{ armor_value = {n(medium)} defense = {n(medium)} }}",),
            ),
            "air_support": (
                (f"ground_attack_factor = {n(medium)}", f"air_mission_efficiency = {n(small)}"),
                (f"air_mission_efficiency = {n(medium)}", f"air_accidents_factor = -{n(small)}"),
            ),
            "naval_support": (
                (f"convoy_escort_efficiency = {n(medium)}", f"naval_coordination = {n(small)}"),
                (f"naval_detection = {n(medium)}", f"naval_mines_effect_reduction = {n(small)}"),
            ),
            "anti_tank": (
                (f"category_anti_tank = {{ hard_attack = {n(medium)} ap_attack = {n(medium)} }}",),
                (f"category_anti_tank = {{ reliability = {n(medium)} defense = {n(small)} }}",),
            ),
            "recon_armor": (
                (f"category_all_armor = {{ maximum_speed = {n(medium)} reliability = {n(small)} }}",),
                (f"category_all_armor = {{ defense = {n(medium)} breakthrough = {n(small)} }}",),
            ),
            "subsurface": (
                (f"naval_detection = {n(medium)}", f"naval_coordination = {n(small)}"),
                (f"naval_mines_effect_reduction = {n(medium)}", f"naval_detection = {n(small)}"),
            ),
        }
        return choices[branch.key][min(xor_option, 1)]

    # Parallel civil and electronics programmes should feel like distinct
    # research projects, not twenty copies of the same global percentage.
    # These lanes ultimately merge, so each package is deliberately narrow:
    # choosing a route changes the order in which a country gains capabilities
    # without creating a permanent all-purpose super-modifier.
    if tier >= 5 and branch.key in {"administration", "computing", "signals", "power"}:
        programme_effects = {
            "administration": {
                0: (
                    f"consumer_goods_factor = -{n(small / 2)}",
                    f"production_factory_start_efficiency_factor = {n(small / 2)}",
                ),
                1: (
                    f"research_speed_factor = {n(small * 0.65)}",
                    f"political_power_gain = {n(small / 2)}",
                ),
                2: (
                    f"coordination_bonus = {n(small)}",
                    f"planning_speed = {n(small / 2)}",
                ),
            },
            "computing": {
                0: (
                    f"supply_consumption_factor = -{n(small / 2)}",
                    f"production_factory_efficiency_gain_factor = {n(small / 2)}",
                ),
                1: (
                    f"research_speed_factor = {n(small * 0.75)}",
                    f"encryption_factor = {n(small)}",
                ),
                2: (
                    f"coordination_bonus = {n(small)}",
                    f"land_reinforce_rate = {n(small / 2)}",
                ),
            },
            "signals": {
                0: (
                    f"encryption_factor = {n(medium)}",
                    f"decryption_factor = {n(small / 2)}",
                    f"production_factory_efficiency_gain_factor = {n(small / 2)}",
                ),
                1: (
                    f"coordination_bonus = {n(small)}",
                    f"land_reinforce_rate = {n(small / 2)}",
                ),
                2: (
                    f"decryption_factor = {n(medium)}",
                    f"encryption_factor = {n(small / 2)}",
                    f"research_speed_factor = {n(small / 2)}",
                ),
            },
            "power": {
                0: (
                    f"nuclear_production_factor = {n(medium)}",
                    f"industrial_capacity_factory = {n(small / 2)}",
                ),
                1: (
                    f"industry_repair_factor = {n(medium)}",
                    f"fuel_gain_factor = {n(small)}",
                ),
                2: (
                    f"production_speed_buildings_factor = {n(small)}",
                    f"local_resources_factor = {n(small)}",
                ),
            },
        }
        return programme_effects[branch.key][lane]

    profiles = {
        "construction": (
            f"production_speed_buildings_factor = {n(small)}",
            f"industry_repair_factor = {n(medium)}",
        ),
        "production": (
            f"industrial_capacity_factory = {n(small)}",
            f"production_factory_efficiency_gain_factor = {n(small)}",
        ),
        "resources": (
            f"local_resources_factor = {n(medium)}",
            f"fuel_gain_factor = {n(small)}",
        ),
        "finance": (
            f"production_factory_start_efficiency_factor = {n(small)}",
            f"consumer_goods_factor = -{n(small / 2)}",
        ),
        "administration": (
            f"research_speed_factor = {n(small / 2)}",
            f"coordination_bonus = {n(small / 2)}",
        ),
        "civil": (
            f"industry_repair_factor = {n(medium)}",
            f"stability_factor = {n(small / 2)}",
        ),
        "power": (
            f"industrial_capacity_factory = {n(small)}",
            f"nuclear_production_factor = {n(medium)}",
        ),
        "signals": (
            f"encryption_factor = {n(medium)}",
            f"decryption_factor = {n(medium)}",
        ),
        "computing": (
            f"research_speed_factor = {n(small)}",
            f"coordination_bonus = {n(small / 2)}",
        ),
        "forbidden_energy": (
            f"nuclear_production_factor = {n(0.04 + tier * 0.02)}",
            f"stability_factor = -{n(0.005 + tier * 0.003)}",
        ),
        "forbidden_automation": (
            f"production_factory_max_efficiency_factor = {n(0.02 + tier * 0.01)}",
            f"stability_factor = -{n(0.01 + tier * 0.005)}",
        ),
        "infantry": (f"category_all_infantry = {{ soft_attack = {n(medium)} breakthrough = {n(small)} }}",),
        "squad": (f"category_all_infantry = {{ soft_attack = {n(small)} defense = {n(medium)} }}",),
        "protection": (f"category_all_infantry = {{ defense = {n(medium)} max_organisation = {n(organisation)} }}",),
        "special_forces": (f"category_special_forces = {{ breakthrough = {n(medium)} maximum_speed = {n(small / 2)} }}",),
        "support": (f"category_support_battalions = {{ defense = {n(medium)} soft_attack = {n(small)} }}",),
        "logistics": (f"supply_consumption_factor = -{n(small)}", f"land_reinforce_rate = {n(small / 2)}"),
        "rail": (f"supply_consumption_factor = -{n(small / 2)}", f"industry_repair_factor = {n(medium)}"),
        "artillery": (f"artillery = {{ soft_attack = {n(medium)} reliability = {n(small / 2)} }}",),
        "anti_tank": (f"category_anti_tank = {{ hard_attack = {n(medium)} ap_attack = {n(medium)} }}",),
        "anti_air": (f"anti_air = {{ air_attack = {n(medium)} reliability = {n(small / 2)} }}",),
        "recon_armor": (f"category_all_armor = {{ maximum_speed = {n(small)} reliability = {n(small)} }}",),
        "combat_armor": (f"category_all_armor = {{ breakthrough = {n(medium)} hard_attack = {n(small)} }}",),
        "heavy_armor": (f"category_all_armor = {{ armor_value = {n(medium)} defense = {n(small)} }}",),
        "fighter": (f"air_mission_efficiency = {n(small)}", f"air_accidents_factor = -{n(small)}"),
        "air_support": (f"air_mission_efficiency = {n(small)}", f"ground_attack_factor = {n(medium)}"),
        "strategic_air": (f"air_mission_efficiency = {n(small)}", f"strategic_bomb_visibility = -{n(small)}"),
        "naval_support": (f"convoy_escort_efficiency = {n(medium)}", f"naval_detection = {n(small)}"),
        "surface_fleet": (f"naval_hit_chance = {n(small)}", f"naval_coordination = {n(small)}"),
        "subsurface": (f"naval_detection = {n(small)}", f"naval_mines_effect_reduction = {n(medium)}"),
    }
    return profiles[profile]


ALLOW = {
    "ADISCORD_tech_old_generator_fragments": ("ADISCORD_has_forbidden_legacy_access = yes",),
    "ADISCORD_tech_dead_reactor_salvage": ("ADISCORD_has_forbidden_legacy_access = yes",),
    "ADISCORD_tech_legacy_reactor_compactification": ("ADISCORD_has_forbidden_legacy_access = yes",),
    "ADISCORD_tech_dirty_energy_munitions": (
        "ADISCORD_has_forbidden_legacy_access = yes",
        "ADISCORD_has_radiation_mapping_tech = yes",
    ),
    "ADISCORD_tech_singularity_cooling_systems": ("ADISCORD_has_forbidden_legacy_access = yes",),
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
    "construction": ("basic_construction", "improved_construction", "advanced_construction"),
    "production": ("basic_machine_tools", "flexible_line", "assembly_line_production"),
    "resources": ("excavation1", "oil_processing", "rubber_processing"),
    "finance": ("mechanical_computing", "computing_machine"),
    "administration": ("radio", "computing_machine"),
    "civil": ("basic_construction", "improved_construction", "radio"),
    "power": ("electronic_mechanical_engineering", "atomic_research", "radio"),
    "signals": ("radio", "basic_encryption", "basic_decryption"),
    "computing": ("mechanical_computing", "computing_machine", "improved_computing_machine"),
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
    "fighter": ("bba_tech_aircraft_construction", "bba_tech_engines_1", "centimetric_radar"),
    "air_support": ("bba_tech_armor_piercing_bombs", "bba_tech_engines_1", "radio"),
    "strategic_air": ("rocket_engines", "advanced_rocket_engines", "centimetric_radar"),
    "naval_support": ("sonar", "advanced_sonar", "advanced_centimetric_radar"),
    "surface_fleet": ("basic_cruiser_armor_scheme", "advanced_centimetric_radar", "naval_air_operations"),
    "subsurface": ("sonar", "basic_naval_mines", "advanced_sonar"),
}


# Several of the original dense branches were built from dark equipment
# silhouettes or just three repeated symbols.  Rotate a compact engine-owned
# thematic palette for those entire branches so chronology and function are
# readable at a glance inside a 72x72 cell.
BRANCH_ICON_PALETTES = {
    "small_arms": (
        "infantry_weapons", "infantry_weapons2", "support_weapons", "night_vision",
        "infantry_at", "basic_encryption", "radio", "support_weapons2",
        "night_vision2", "improved_encryption",
    ),
    "squad_weapons": (
        "support_weapons", "support_weapons2", "infantry_at", "radio",
        "support_weapons3", "centimetric_radar", "infantry_at2",
        "support_weapons4", "advanced_centimetric_radar",
    ),
    "protection": (
        "basic_construction", "night_vision", "improved_construction",
        "basic_encryption", "radio", "advanced_construction",
        "improved_encryption", "night_vision2",
    ),
    "special_forces": (
        "night_vision", "radio", "basic_decryption", "centimetric_radar",
        "improved_decryption", "night_vision2", "advanced_decryption",
        "advanced_centimetric_radar",
    ),
    "field_support": (
        "basic_machine_tools", "basic_construction", "improved_machine_tools",
        "radio", "advanced_machine_tools", "improved_construction",
        "assembly_line_production", "advanced_construction",
    ),
    "logistics": (
        "radio", "basic_machine_tools", "computing_machine",
        "assembly_line_production", "improved_computing_machine",
        "improved_construction", "advanced_computing_machine",
        "advanced_construction",
    ),
    "rail": (
        "basic_machine_tools", "basic_construction", "improved_machine_tools",
        "radio", "assembly_line_production", "improved_construction",
        "advanced_machine_tools", "computing_machine",
        "advanced_construction", "advanced_computing_machine",
    ),
    "combat_medicine": (
        "basic_construction", "radio", "improved_construction",
        "computing_machine", "advanced_construction", "improved_computing_machine",
        "night_vision", "advanced_computing_machine",
    ),
    "combat_engineering": (
        "basic_machine_tools", "basic_construction", "improved_machine_tools",
        "improved_construction", "advanced_machine_tools", "radio",
        "advanced_construction", "assembly_line_production",
    ),
    "officer_training": (
        "radio", "mechanical_computing", "basic_encryption",
        "computing_machine", "improved_encryption", "improved_computing_machine",
        "advanced_encryption", "advanced_computing_machine",
    ),
    "finance": (
        "mechanical_computing", "computing_machine", "improved_computing_machine",
        "advanced_computing_machine", "basic_encryption", "radio",
        "improved_machine_tools", "dispersed_industry",
    ),
    "administration": (
        "radio", "mechanical_computing", "basic_encryption", "computing_machine",
        "improved_encryption", "improved_computing_machine", "advanced_encryption",
        "advanced_computing_machine",
    ),
    "power": (
        "electronic_mechanical_engineering", "oil_plant", "atomic_research",
        "nuclear_reactor", "advanced_oil_plant", "sp_nuclear_isotope_separation",
        "sp_physics_improved_radio", "sp_physics_advanced_radio",
    ),
    "computing": (
        "mechanical_computing", "electronic_mechanical_engineering", "computing_machine",
        "basic_encryption", "radio_detection", "improved_computing_machine",
        "centimetric_radar", "advanced_computing_machine",
    ),
    "forbidden_energy": (
        "atomic_research", "nuclear_reactor", "sp_nuclear_isotope_separation",
        "experimental_rockets", "advanced_rocket_engines", "sp_physics_advanced_radio",
    ),
    "recon_armor": (
        "nsb_engine_tech_1", "nsb_armor_tech_1", "basic_machine_tools",
        "radio", "nsb_engine_tech_2", "centimetric_radar",
        "nsb_armor_tech_2", "improved_machine_tools", "nsb_engine_tech_3",
        "advanced_centimetric_radar",
    ),
    "combat_armor": (
        "nsb_armor_tech_1", "nsb_engine_tech_1", "basic_machine_tools",
        "nsb_armor_tech_2", "nsb_engine_tech_2", "radio",
        "nsb_armor_tech_3", "nsb_engine_tech_3", "advanced_machine_tools",
        "nsb_armor_tech_4", "nsb_engine_tech_4", "advanced_centimetric_radar",
    ),
    "heavy_armor": (
        "nsb_armor_tech_1", "nsb_engine_tech_1", "basic_machine_tools",
        "nsb_armor_tech_2", "nsb_engine_tech_2", "improved_machine_tools",
        "nsb_armor_tech_3", "nsb_engine_tech_3", "advanced_machine_tools",
        "nsb_armor_tech_4", "nsb_engine_tech_4", "advanced_construction",
    ),
    "naval_support": (
        "sonar", "basic_torpedo", "improved_sonar", "basic_naval_mines",
        "advanced_sonar", "improved_naval_mines", "advanced_centimetric_radar",
        "advanced_naval_mines", "modern_sonar", "homing_torpedo",
    ),
    "surface_fleet": (
        "basic_cruiser_armor_scheme", "decimetric_radar", "improved_cruiser_armor_scheme",
        "improved_centimetric_radar", "advanced_cruiser_armor_scheme",
        "advanced_centimetric_radar", "naval_air_operations", "air_defence",
    ),
    "subsurface": (
        "sonar", "basic_submarine_snorkel", "basic_torpedo", "submarine_mine_laying",
        "improved_sonar", "electric_torpedo", "improved_submarine_snorkel",
        "advanced_sonar", "homing_torpedo", "advanced_submarine_warfare",
    ),
}


# Wide cards are reserved for technologies that unlock something the player
# can actually put on a production line. Give those cards the corresponding
# equipment silhouette instead of a 64px support-company badge.
EQUIPMENT_UNLOCK_ICONS = {
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
    "ADISCORD_tech_field_workshop_tools": "support_equipment_1",
    "ADISCORD_tech_drone_delivered_repair_spares": "support_equipment_1",
    "ADISCORD_tech_predictive_parts_prepositioning": "support_equipment_1",
    "ADISCORD_tech_self_sustaining_support": "support_equipment_1",
    "ADISCORD_tech_hardened_logistics_nodes": "train_equipment_3",
    "ADISCORD_tech_restored_field_artillery": "artillery_equipment",
    "ADISCORD_tech_inertial_battery_survey": "artillery_equipment",
    "ADISCORD_tech_assisted_projectiles": "artillery_equipment",
    "ADISCORD_tech_course_correcting_fuzes": "rocket_artillery_equipment",
    "ADISCORD_tech_multispectral_spotter_drones": "rocket_artillery_equipment",
    "ADISCORD_tech_robotic_shell_handling": "artillery_equipment",
    "ADISCORD_tech_drone_spotted_batteries": "rocket_artillery_equipment",
    "ADISCORD_tech_scrap_at_launchers": "anti_tank_equipment",
    "ADISCORD_tech_superconducting_coil_barrels": "anti_tank_equipment",
    "ADISCORD_tech_guided_hypervelocity_penetrators": "anti_tank_equipment",
    "ADISCORD_tech_point_defense_aa": "anti_air_equipment",
    "ADISCORD_tech_high_energy_laser_turrets": "anti_air_equipment",
    "ADISCORD_tech_remote_repair_sections": "generic_armored_support_vehicle_recovery_1",
    "ADISCORD_tech_low_observable_inlet_geometry": "fighter2",
    "ADISCORD_tech_cooperative_fighter_sensor_fusion": "jet_fighter2",
    "ADISCORD_tech_loyal_wingmen": "jet_fighter2",
    "ADISCORD_tech_orbital_tracking_relics": "guided_missile_1",
    "ADISCORD_tech_low_observable_cruise_missile_skins": "guided_missile_2",
    "ADISCORD_tech_suborbital_skip_glide_guidance": "guided_missile_3",
    "ADISCORD_tech_autonomous_strategic_strike_planning": "guided_missile_3",
    "ADISCORD_tech_suborbital_strike_systems": "ballistic_missile_equipment_3",
}

COMPACT_ICON_OVERRIDES = {
    "dirty_energy_munitions": "sp_nuclear_isotope_separation",
}

# These vanilla sprites are valid 64x64 files but are composed as support
# company badges with a soldier silhouette. They read badly when repeated as
# generic research icons, so effect-only nodes use neutral technical art.
UNSUITABLE_COMPACT_ICON_PREFIXES = (
    "engineers",
    "recon",
    "tech_field_hospital",
    "tech_logistics_company",
    "tech_maintenance_company",
    "tech_signal_company",
    "tech_special_forces",
)


def technology_icon_size(icon: str) -> tuple[int, int] | None:
    relative = Path("gfx") / "interface" / "technologies" / f"{icon}.dds"
    for root in (ROOT, BASE_GAME):
        path = root / relative
        if not path.exists():
            continue
        header = path.read_bytes()[:20]
        if len(header) >= 20 and header[:4] == b"DDS ":
            height = int.from_bytes(header[12:16], "little")
            width = int.from_bytes(header[16:20], "little")
            return width, height
    return None


def icon_for_technology(branch: Branch, index: int) -> str:
    tech = branch.techs[index]
    icon = ICON_ALIASES.get(tech.icon, tech.icon)

    # The GUI selects the wide item template for equipment unlocks. Preserve a
    # readable vehicle/weapon silhouette there; the old code compacted these
    # sprites and turned trains and tanks into unrelated support-company icons.
    if tech.id in ENABLE_EQUIPMENT:
        candidate = EQUIPMENT_UNLOCK_ICONS.get(tech.id, icon)
        size = technology_icon_size(candidate)
        if size and size[0] <= 190 and size[1] <= 84:
            return candidate

    palette = BRANCH_ICON_PALETTES.get(branch.key)
    if palette:
        candidate = palette[index % len(palette)]
        if technology_icon_size(candidate):
            icon = candidate
    icon = COMPACT_ICON_OVERRIDES.get(tech.key, icon)
    size = technology_icon_size(icon)
    unsuitable = icon.startswith(UNSUITABLE_COMPACT_ICON_PREFIXES)
    # Effect-only nodes use the 72x72 compact template. Oversized equipment art
    # and support-company silhouettes are replaced with technical symbols.
    if size and (size[0] > 72 or size[1] > 72 or unsuitable):
        compact = COMPACT_ICONS_BY_PROFILE[branch.profile]
        return compact[index % len(compact)]
    return icon


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


TECHNICAL_TECH_DESCRIPTIONS = {
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
        "Динамит или пластичный заряд в переносной сумке сосредотачивает взрыв у гусеницы, днища или неподвижного узла машины",
        "Dynamite or plastic explosive carried in a satchel concentrates blast against a track, belly plate, or fixed vehicle component",
    ),
    "tandem_penetrator_packages": (
        "Ручная граната с кумулятивной воронкой формирует направленную струю при подрыве на броне, не полагаясь на кинетическую скорость",
        "A hand-thrown grenade with a shaped-charge liner forms a focused jet on armor without relying on impact velocity",
    ),
    "wire_guided_hunter_teams": (
        "Крупнокалиберный ствол и высокоскоростной бронебойный сердечник поражают раннюю бронетехнику прямым кинетическим пробитием",
        "A large-calibre barrel and high-velocity armor-piercing core defeat early armored vehicles by direct kinetic penetration",
    ),
    "recoilless_overmatch_cells": (
        "Команды оператора передаются ракете по разматываемому проводу, устойчивому к радиопомехам и не требующему бортовой головки самонаведения",
        "Operator commands reach the missile through a payed-out wire, resisting radio jamming without an onboard seeker",
    ),
    "fire_and_forget_seekers": (
        "Истечение части пороховых газов назад уравновешивает отдачу и позволяет переносному стволу метать боеприпас достаточного калибра",
        "Rearward venting of propellant gas balances recoil and lets a portable tube fire a sufficiently large projectile",
    ),
    "programmable_anti_armor_fuzes": (
        "Оператор удерживает перекрестие на цели, а аппаратура автоматически вычисляет команды наведения ракеты относительно линии визирования",
        "The operator keeps the sight on target while the control unit automatically computes missile corrections relative to the line of sight",
    ),
    "top_attack_profiles": (
        "Реактивный двигатель разгоняет гранату с кумулятивной боевой частью после выхода из пусковой трубы, сохраняя переносимость оружия",
        "A rocket motor accelerates a shaped-charge grenade after it leaves the launch tube, preserving weapon portability",
    ),
    "loitering_armor_hunters": (
        "Матричная инфракрасная головка распознаёт тепловой образ цели и направляет ракету в менее защищённую верхнюю полусферу",
        "An imaging-infrared seeker recognizes the target heat signature and guides the missile into the less protected upper hemisphere",
    ),
    "cooperative_hunter_cells": (
        "Предзаряд разрушает динамическую защиту, после чего основной кумулятивный заряд формирует струю против основной брони",
        "A precursor charge disrupts reactive armor before the main shaped charge forms its jet against the base armor",
    ),
    "terminal_overmatch_packages": (
        "Переносной беспилотный боеприпас длительно ищет цель, передаёт изображение оператору и атакует после подтверждения",
        "A portable unmanned munition searches for a target, relays imagery to the operator, and attacks after confirmation",
    ),
    "distributed_anti_armor_net": (
        "Тепловизионные, телевизионные и лазерные наблюдатели передают единую координату разнесённым пусковым расчётам и барражирующим боеприпасам",
        "Thermal, television, and laser observers pass one target solution to separated launch teams and loitering munitions",
    ),
}


BUILDING_DISPLAY_NAMES = {
    "ADISCORD_metallurgical_complex": ("металлургический комплекс", "Metallurgical Complex"),
    "ADISCORD_electrolysis_complex": ("электролизный комплекс", "Electrolysis Complex"),
    "ADISCORD_strategic_mining_complex": ("комплекс стратегической добычи", "Strategic Mining Complex"),
    "ADISCORD_thermal_power_complex": ("энергогенерирующий комплекс", "Power Generation Complex"),
    "synthetic_refinery": ("завод синтетических материалов", "Synthetic Materials Plant"),
    "fuel_silo": ("топливное хранилище", "Fuel Silo"),
    "anti_air_building": ("региональную ПВО", "State Anti-Air"),
    "radar_station": ("радиолокационную станцию", "Radar Station"),
    "rocket_site": ("ракетную площадку", "Rocket Site"),
    "nuclear_reactor": ("ядерный реактор", "Nuclear Reactor"),
    "nuclear_reactor_heavy_water": ("тяжеловодный реактор", "Heavy-Water Reactor"),
    "commercial_nuclear_reactor": ("коммерческий энергореактор", "Commercial Power Reactor"),
    "stronghold_network": ("сеть укрепрайонов", "Stronghold Network"),
    "mega_gun_emplacement": ("позицию сверхтяжёлого орудия", "Mega-Gun Emplacement"),
}


def technology_description_notes(branch: Branch, index: int, is_ru: bool) -> list[str]:
    notes: list[str] = []
    siblings = xor_siblings(branch, index)
    if siblings:
        names_by_id = {tech.id: (tech.ru if is_ru else tech.en) for tech in branch.techs}
        alternatives = ", ".join(names_by_id[sibling] for sibling in siblings)
        if XOR_KIND_BY_BRANCH[branch.key] == "temporary":
            notes.append(
                f"Взаимоисключающий проект с вариантом: {alternatives}; общая линия продолжится после любого выбора."
                if is_ru else
                f"Mutually exclusive with: {alternatives}; the common line continues after either choice."
            )
        else:
            notes.append(
                f"Постоянный выбор специализации: альтернатива «{alternatives}» останется закрыта до конца магистрали."
                if is_ru else
                f"Permanent specialization choice: {alternatives} remains locked for the rest of the branch."
            )
    for effect in effects_for(branch, index):
        energy_match = re.fullmatch(r"factory_energy_consumption = ([0-9.]+)", effect)
        if energy_match and float(energy_match.group(1)) > 0:
            percent = f"{float(energy_match.group(1)) * 100:g}"
            notes.append(
                f"Энергетическая цена: потребление энергии фабриками +{percent}%."
                if is_ru else
                f"Energy price: factory energy consumption +{percent}%."
            )
    if len(BRANCH_GRAPHS[branch.key].dependencies[index]) >= 2:
        notes.append(
            "Требует завершения всех входящих программ и объединяет их результаты."
            if is_ru else
            "Requires every incoming programme and integrates their results."
        )
    buildings = ENABLE_BUILDINGS.get(branch.techs[index].id, ())
    if buildings:
        names = [BUILDING_DISPLAY_NAMES[building][0 if is_ru else 1] for building, _ in buildings]
        notes.append(
            f"Открывает строительство: {', '.join(names)}."
            if is_ru else
            f"Unlocks construction: {', '.join(names)}."
        )
    if branch.techs[index].id in BUILDING_RESOURCE_UPGRADES:
        notes.append(
            "Повышает выпуск уже построенных и будущих ресурсных комплексов."
            if is_ru else
            "Raises the output of both existing and future resource complexes."
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
    if branch.profile.startswith("forbidden_"):
        return 2.60 + index * (0.18 if len(branch.techs) > 3 else 0.35)
    if year <= 2158:
        return 0.55

    progress = max(0.0, min(1.0, (year - 2160) / 20))
    cost = POST_2160_RESEARCH_COST_BY_PROFILE[branch.profile] + progress * 0.55
    if xor:
        cost = max(cost, 1.75)
    if tech.id in ENABLE_EQUIPMENT or tech.id in ENABLE_SUBUNITS or tech.id in ENABLE_BUILDINGS:
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
    if profile in {"construction", "resources", "civil", "rail"} and not (
        branch.key == "reconstruction" and year > 2160
    ):
        entries.append("modifier = { factor = 1.35 ADISCORD_economy_ai_is_crisis = yes }")
    if profile in {"production", "finance", "administration", "computing"}:
        entries.append("modifier = { factor = 1.20 ADISCORD_economy_ai_is_healthy = yes }")
    if profile in {
        "infantry", "squad", "protection", "support", "logistics", "artillery",
        "anti_tank", "anti_air", "recon_armor", "combat_armor", "heavy_armor",
        "fighter", "air_support", "strategic_air",
    }:
        entries.append("modifier = { factor = 1.25 has_war = yes }")
        entries.append("modifier = { factor = 0.30 ADISCORD_economy_ai_is_crisis = yes }")
    if profile in {"recon_armor", "combat_armor", "heavy_armor"}:
        entries.append("modifier = { factor = 0.15 num_of_military_factories < 8 }")
        entries.append("modifier = { factor = 1.45 ADISCORD_economy_ai_can_fund_advanced_forces = yes }")
    if profile in {"fighter", "air_support", "strategic_air"}:
        entries.append("modifier = { factor = 0.20 num_of_military_factories < 8 }")
        entries.append("modifier = { factor = 1.35 ADISCORD_economy_ai_can_fund_advanced_forces = yes }")
    if profile in {"naval_support", "surface_fleet", "subsurface"}:
        entries.append("modifier = { factor = 0.05 num_of_naval_factories < 1 }")
        entries.append("modifier = { factor = 1.35 num_of_naval_factories > 3 }")
    if branch.key == "power":
        entries.append("modifier = { factor = 1.75 energy_ratio < 0.80 }")
    if branch.key in {"signals", "computing"} and year <= 2167:
        entries.append("modifier = { factor = 1.20 has_war = yes }")

    lane = BRANCH_GRAPHS[branch.key].lanes[index]
    if branch.key == "industry_organization" and lane == 0:
        entries.append("modifier = { factor = 1.50 energy_ratio > 0.94 }")
        entries.append("modifier = { factor = 1.25 ADISCORD_economy_ai_is_healthy = yes }")
        entries.append("modifier = { factor = 0.35 has_war = yes }")
    elif branch.key == "industry_organization" and lane == 2:
        entries.append("modifier = { factor = 1.60 energy_ratio < 0.80 }")
        entries.append("modifier = { factor = 1.35 has_war = yes }")
        entries.append("modifier = { factor = 1.35 ADISCORD_economy_ai_is_crisis = yes }")

    if branch.key == "computing" and lane == 2:
        entries.append("modifier = { factor = 1.35 energy_ratio > 0.94 }")
        entries.append("modifier = { factor = 0.25 energy_ratio < 0.80 }")
    elif branch.key == "computing" and lane == 0:
        entries.append("modifier = { factor = 1.25 energy_ratio < 0.80 }")

    if branch.key == "production" and lane in {0, 2}:
        if lane == 0:
            entries.append("modifier = { factor = 1.20 ADISCORD_economy_ai_is_stressed = yes }")
        else:
            entries.append("modifier = { factor = 1.20 ADISCORD_economy_ai_is_healthy = yes }")

    xor = xor_siblings(branch, index)
    if xor and branch.key not in {"production", "industry_organization", "computing"}:
        if lane == 0:
            entries.append("modifier = { factor = 1.25 ADISCORD_economy_ai_is_stressed = yes }")
        elif lane == 2:
            entries.append("modifier = { factor = 1.25 ADISCORD_economy_ai_is_healthy = yes }")
    return tuple(entries)


def render_leader_training_effect(tech: Tech) -> list[str]:
    """Render the bounded random-general improvement pattern used by TDA."""

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
        lines.extend((
            "\t\t\t\trandom_army_leader = {",
            f"\t\t\t\t\tlimit = {{ NOT = {{ has_unit_leader_flag = {flag} }} }}",
            f"\t\t\t\t\tset_unit_leader_flag = {flag}",
            f"\t\t\t\t\tadd_{attribute} = 1",
            "\t\t\t\t}",
        ))
    lines.extend((
        "\t\t\t\tevery_army_leader = {",
        f"\t\t\t\t\tlimit = {{ has_unit_leader_flag = {flag} }}",
        f"\t\t\t\t\tclr_unit_leader_flag = {flag}",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
    ))
    return lines


def folder_grid_format(folder: str) -> str:
    """Return the Clausewitz grid direction matching the folder time axis."""

    return "LEFT" if folder in HORIZONTAL_FOLDERS else "UP"


def chronological_grid_slot(year: int, *, horizontal: bool) -> int:
    """Map a research year to the single slot used by nodes and year labels."""

    slot = YEAR_TO_Y[year]
    return slot * HORIZONTAL_YEAR_SLOT_MULTIPLIER if horizontal else slot


def graph_distances(
    start: int,
    adjacency: tuple[tuple[int, ...], ...],
) -> dict[int, int]:
    """Return shortest edge distances from one node in a small acyclic graph."""

    distances = {start: 0}
    frontier = [start]
    while frontier:
        source = frontier.pop(0)
        for target in adjacency[source]:
            distance = distances[source] + 1
            if target in distances and distances[target] <= distance:
                continue
            distances[target] = distance
            frontier.append(target)
    return distances


def balanced_binary_pairs(graph: BranchGraph) -> tuple[tuple[int, int], ...]:
    """Find symmetric fork entries and merge exits that should share a column.

    Clausewitz draws every path independently. If the two arms of a balanced
    diamond start or end in different chronological columns, their elbows
    overlap without sharing a centrepiece and leave the visible breaks seen in
    horizontal trees. Unequal arms remain staggered because aligning those
    would create backwards or misleading routes.
    """

    reverse: list[list[int]] = [[] for _ in graph.lanes]
    for source, targets in enumerate(graph.successors):
        for target in targets:
            reverse[target].append(source)
    reverse_adjacency = tuple(tuple(parents) for parents in reverse)

    pairs: set[tuple[int, int]] = set()
    for targets in graph.successors:
        if len(targets) != 2:
            continue
        left, right = targets
        left_distances = graph_distances(left, graph.successors)
        right_distances = graph_distances(right, graph.successors)
        common = set(left_distances).intersection(right_distances)
        if common:
            meeting = min(
                common,
                key=lambda node: (
                    max(left_distances[node], right_distances[node]),
                    left_distances[node] + right_distances[node],
                    node,
                ),
            )
            if left_distances[meeting] == right_distances[meeting]:
                pairs.add(tuple(sorted((left, right))))

    for parents in reverse_adjacency:
        if len(parents) != 2:
            continue
        left, right = parents
        left_distances = graph_distances(left, reverse_adjacency)
        right_distances = graph_distances(right, reverse_adjacency)
        common = set(left_distances).intersection(right_distances)
        if common:
            meeting = min(
                common,
                key=lambda node: (
                    max(left_distances[node], right_distances[node]),
                    left_distances[node] + right_distances[node],
                    node,
                ),
            )
            if left_distances[meeting] == right_distances[meeting]:
                pairs.add(tuple(sorted((left, right))))
    return tuple(sorted(pairs))


def horizontal_visual_slots(branch: Branch) -> tuple[int, ...]:
    """Align balanced diamonds without changing their gameplay start years."""

    graph = BRANCH_GRAPHS[branch.key]
    base = tuple(
        chronological_grid_slot(year, horizontal=True)
        for year in branch.years
    )
    slots = list(base)
    reverse: list[list[int]] = [[] for _ in graph.lanes]
    for source, targets in enumerate(graph.successors):
        for target in targets:
            reverse[target].append(source)
    multi_arm_groups = {
        tuple(sorted(group))
        for group in (*graph.successors, *(tuple(parents) for parents in reverse))
        if len(group) >= 3
    }
    alignment_groups = {
        *balanced_binary_pairs(graph),
        *multi_arm_groups,
    }

    for group in sorted(alignment_groups):
        candidate = max(base[index] for index in group)
        neighbours = tuple(
            source
            for source, targets in enumerate(graph.successors)
            if any(index in targets for index in group)
        )
        successors = tuple(
            target
            for index in group
            for target in graph.successors[index]
        )
        if neighbours and candidate <= max(base[index] for index in neighbours):
            continue
        if successors and candidate >= min(base[index] for index in successors):
            continue
        for index in group:
            slots[index] = candidate

    for source, targets in enumerate(graph.successors):
        for target in targets:
            if slots[source] >= slots[target]:
                raise ValueError(
                    f"{branch.key}: non-chronological visual edge {source}->{target}"
                )
    return tuple(slots)


def technology_grid_position(branch: Branch, index: int) -> tuple[int, int]:
    """Keep the lane in x; grid direction maps chronological y to screen time."""

    graph = BRANCH_GRAPHS[branch.key]
    horizontal = bool(HORIZONTAL_FOLDERS.intersection(branch.folders))
    lane = graph.lanes[index]
    if not horizontal:
        lane *= LANE_SLOT_MULTIPLIER
        chronological_slot = chronological_grid_slot(branch.years[index], horizontal=False)
    else:
        chronological_slot = horizontal_visual_slots(branch)[index]
    return lane, chronological_slot


def render_technology(branch: Branch, index: int) -> str:
    tech = branch.techs[index]
    year = branch.years[index]
    graph = BRANCH_GRAPHS[branch.key]
    lines = [f"\t{tech.id} = {{"]
    allow = ALLOW.get(tech.id)
    if allow:
        lines.append("\t\tallow = {")
        lines.extend(f"\t\t\t{entry}" for entry in allow)
        lines.append("\t\t}")
    lines.extend(
        f"\t\t{effect}"
        for effect in effects_for(branch, index)
    )
    lines.extend(render_leader_training_effect(tech))
    for target in graph.successors[index]:
        lines.append(
            f"\t\tpath = {{ leads_to_tech = {branch.techs[target].id} research_cost_coeff = 1 }}"
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
        lines.extend(
            f"\t\t\t{parent} = 1"
            for parent in dependencies
        )
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
        lines.extend((
            "\t\tenable_building = {",
            f"\t\t\tbuilding = {building}",
            f"\t\t\tlevel = {level}",
            "\t\t}",
        ))
    building_upgrades = BUILDING_RESOURCE_UPGRADES.get(tech.id, ())
    if building_upgrades:
        lines.append("\t\ton_research_complete = {")
        for building, resource, amount in building_upgrades:
            lines.extend((
                "\t\t\tmodify_building_resources = {",
                f"\t\t\t\tbuilding = {building}",
                f"\t\t\t\tresource = {resource}",
                f"\t\t\t\tamount = {amount}",
                "\t\t\t}",
            ))
        lines.extend(("\t\t}", "\t\tshow_effect_as_desc = yes"))
    research_cost = research_cost_for(branch, index, dependencies, xor)
    lines.extend((
        f"\t\tresearch_cost = {n(research_cost)}",
        f"\t\tstart_year = {year}",
    ))
    position_x, position_y = technology_grid_position(branch, index)
    for folder in sorted(branch.folders):
        lines.extend((
            "\t\tfolder = {",
            f"\t\t\tname = {folder}",
            f"\t\t\tposition = {{ x = {position_x} y = {position_y} }}",
            "\t\t}",
        ))
    lines.append("\t\tai_will_do = {")
    lines.extend(f"\t\t\t{entry}" for entry in ai_will_do_for(branch, index))
    lines.extend((
        "\t\t}",
        f"\t\tcategories = {{ {CATEGORY_BY_PROFILE[branch.profile]} }}",
        "\t}",
    ))
    return "\n".join(lines)


def write_technology_files() -> None:
    technology_dir = ROOT / "common" / "technologies"
    files = sorted({branch.file for branch in BRANCHES})
    for filename in files:
        blocks = [
            render_technology(branch, index)
            for branch in BRANCHES
            if branch.file == filename
            for index in range(len(branch.techs))
        ]
        content = "technologies = {\n" + "\n\n".join(blocks) + "\n}\n"
        (technology_dir / filename).write_text(content, encoding="utf-8")


def write_starting_technology_effect() -> None:
    """Render the common baseline, profile packages and explicit tag dispatch."""

    lines = [
        "# Generated by tools/build_adiscord_technology_system.py.",
        "# The campaign begins in 2160.  Common roots and bounded country profiles",
        "# preserve technological differences instead of granting every pre-2160 node.",
        "",
    ]
    for profile, technology_ids in STARTING_TECH_PROFILES.items():
        lines.extend((
            f"ADISCORD_grant_technology_profile_{profile} = {{",
            "\tset_technology = {",
        ))
        lines.extend(f"\t\t{tech_id} = 1" for tech_id in technology_ids)
        lines.extend((
            "\t\tpopup = no",
            "\t}",
            "}",
            "",
        ))

    lines.extend((
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
    ))
    for tag, profiles in sorted(STARTING_COUNTRY_TECH_PROFILES.items()):
        lines.extend((
            "\tif = {",
            f"\t\tlimit = {{ tag = {tag} }}",
        ))
        if profiles:
            lines.extend(
                f"\t\tADISCORD_grant_technology_profile_{profile} = yes"
                for profile in profiles
            )
        else:
            lines.extend((
                "\t\t# Intentional common-only assignment.",
                "\t\tADISCORD_grant_technology_profile_common = yes",
            ))
        lines.append("\t}")
    lines.extend((
        "\tif = {",
        "\t\tlimit = { date > 2183.1.1 }",
        "\t\tADISCORD_grant_technology_profile_late_2183 = yes",
        "\t}",
        "}",
        "",
    ))
    path = ROOT / "common" / "scripted_effects" / "ADISCORD_technology_baseline_effects.txt"
    path.write_text("\n".join(lines), encoding="utf-8")


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
        oob_path = ROOT / "history" / "units" / f"{tag}.txt"
        if oob_path.exists():
            oob_text = oob_path.read_text(encoding="utf-8-sig")
            row["oob_divisions"] = len(
                re.findall(r"(?m)^\s*division\s*=\s*\{", oob_text)
            )
    return evidence


def write_starting_technology_profile_manifest() -> None:
    path = ROOT / "tools" / "data" / "adiscord_starting_technology_profiles.json"
    path.parent.mkdir(parents=True, exist_ok=True)
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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_gfx() -> None:
    entries = []
    for branch in BRANCHES:
        for index, tech in enumerate(branch.techs):
            icon = icon_for_technology(branch, index)
            entries.append(
                "\tSpriteType = {\n"
                f"\t\tname = \"GFX_{tech.id}_medium\"\n"
                f"\t\ttextureFile = \"gfx/interface/technologies/{icon}.dds\"\n"
                "\t}\n"
            )
    content = "spriteTypes = {\n" + "\n".join(entries) + "}\n"
    (ROOT / "interface" / "ADISCORD_technologies.gfx").write_text(content, encoding="utf-8")


ACCESS_REQUIREMENT_LOCALISATION = {
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
    "infantry_equipment_0": (
        "ОВ-40 «Лом»", "SR-40 “Crowbar”", "ОВ-40", "SR-40",
        "Восстановленный комплект винтовок с заново нарезанными стволами, едиными калибрами и измерительным контролем.",
        "A recovered rifle set rebuilt with newly rifled barrels, common calibres, and gauged inspection.",
    ),
    "ADISCORD_infantry_equipment_2156": (
        "ОВ-56 «Шов»", "SR-56 “Seam”", "ОВ-56", "SR-56",
        "Первая серийная винтовка новой сборки с контролируемой обтюрацией казённой части и взаимозаменяемым затвором.",
        "The first newly manufactured service rifle with controlled breech obturation and an interchangeable bolt.",
    ),
    "ADISCORD_infantry_equipment_2163": (
        "АВ-63 «Рёв»", "AR-63 “Roar”", "АВ-63", "AR-63",
        "Автоматическое оружие под промежуточный патрон, рассчитанный на управляемый огонь короткими очередями.",
        "An automatic weapon chambered for an intermediate cartridge intended for controllable short bursts.",
    ),
    "ADISCORD_infantry_equipment_2168": (
        "АВ-68 «Срез»", "AR-68 “Cut”", "АВ-68", "AR-68",
        "Самозарядная винтовка с серийным механизмом экстракции, досылания и взведения от энергии выстрела.",
        "A self-loading rifle with a production-standard mechanism for extraction, feeding, and cocking from firing energy.",
    ),
    "ADISCORD_infantry_equipment_2170": (
        "АВ-70 «Контур»", "AR-70 “Contour”", "АВ-70", "AR-70",
        "Автоматическая винтовка с лазерным дальномером и прицельной сеткой, рассчитанной под штатную баллистику патрона.",
        "An automatic rifle with a laser rangefinder and reticle calibrated to the service cartridge trajectory.",
    ),
    "ADISCORD_infantry_equipment_2178": (
        "АВ-78 «Клык»", "AR-78 “Fang”", "АВ-78", "AR-78",
        "Газоотводная автоматическая винтовка с регулируемым узлом отвода газов и устойчивым циклом при загрязнении.",
        "A gas-operated automatic rifle with an adjustable gas system and a stable cycle under fouling.",
    ),
    "ADISCORD_infantry_equipment_2183": (
        "АВ-83 «Призма»", "AR-83 “Prism”", "АВ-83", "AR-83",
        "Автоматическая винтовка с хромированным каналом ствола, сохраняющим ресурс при высоком темпе огня.",
        "An automatic rifle with a chrome-lined bore that preserves barrel life under a high rate of fire.",
    ),
    "ADISCORD_infantry_equipment_2193": (
        "АВ-93 «Игла»", "AR-93 “Needle”", "АВ-93", "AR-93",
        "Автоматическая винтовка с согласованным импульсом отдачи, буфером затворной группы и уменьшенным подбросом.",
        "An automatic rifle with tuned recoil impulse, a buffered bolt group, and reduced muzzle rise.",
    ),
    "ADISCORD_infantry_equipment_2200": (
        "ИСК-00 «Предел»", "IWS-00 “Limit”", "ИСК-00", "IWS-00",
        "Индивидуальная система под программируемый боеприпас, получающий дальность и режим подрыва от прицела.",
        "An individual weapon for programmable ammunition that receives range and fuze mode from the sight.",
    ),
    "ADISCORD_squad_weapons_equipment_0": (
        "КОП-40 «Скат»", "FSC-40 “Ray”", "КОП-40", "FSC-40",
        "Восстановленные пулемёты, оптика и боеприпасы для тяжёлой группы отделения.",
        "Recovered machine guns, optics, and ammunition issued to the squad heavy group.",
    ),
    "ADISCORD_squad_weapons_equipment_2156": (
        "КОП-56 «Жгут»", "FSC-56 “Cord”", "КОП-56", "FSC-56",
        "Единый ленточный комплекс с серийными коробами и переносным запасом стволов.",
        "A common belt-fed system with standardized boxes and portable spare barrels.",
    ),
    "ADISCORD_squad_weapons_equipment_2163": (
        "КОП-63 «Зуб»", "FSC-63 “Tooth”", "КОП-63", "FSC-63",
        "Групповой комплект с усиленным пулемётом, точной винтовкой и лёгкими пусковыми средствами.",
        "A group kit combining a reinforced machine gun, precision rifle, and light launchers.",
    ),
    "ADISCORD_squad_weapons_equipment_2168": (
        "КОП-68 «Вал»", "FSC-68 “Shaft”", "КОП-68", "FSC-68",
        "Модульное групповое оружие с общей оптикой, дальномерами и корректируемыми зарядами.",
        "Modular group weapons sharing optics, rangefinding, and corrected charges.",
    ),
    "ADISCORD_squad_weapons_equipment_2170": (
        "КОП-70 «Гул»", "FSC-70 “Rumble”", "КОП-70", "FSC-70",
        "Сенсорно-связанный комплект для подавления, точного огня и пристрелки отделения.",
        "A sensor-linked kit for suppression, precision fire, and squad ranging.",
    ),
    "ADISCORD_squad_weapons_equipment_2178": (
        "КОП-78 «Узел»", "FSC-78 “Knot”", "КОП-78", "FSC-78",
        "Программируемый огневой узел с электронными взрывателями и защищённым обменом целями.",
        "A programmable fire node with electronic fuzes and protected target exchange.",
    ),
    "ADISCORD_squad_weapons_equipment_2183": (
        "КОП-83 «Маяк»", "FSC-83 “Beacon”", "КОП-83", "FSC-83",
        "Сетевая система точной поддержки с мультиспектральной разведкой и удалённым наведением.",
        "A networked precision-support system with multispectral scouting and remote guidance.",
    ),
    "ADISCORD_squad_weapons_equipment_2193": (
        "КОП-93 «Рой»", "FSC-93 “Swarm”", "КОП-93", "FSC-93",
        "Полуавтономный комплект управления тяжёлым оружием и распределёнными сенсорами.",
        "A semi-autonomous controller for heavy weapons and distributed sensors.",
    ),
    "ADISCORD_squad_weapons_equipment_2200": (
        "КОП-00 «Хор»", "FSC-00 “Chorus”", "КОП-00", "FSC-00",
        "Поздняя сеть группового огня, сводящая пулемёты, точные системы и роботизированные носители.",
        "A late group-fire network combining machine guns, precision systems, and robotic carriers.",
    ),
}


def generated_localisation(language: str) -> list[str]:
    is_ru = language == "russian"
    lines = [
        f' {key}:0 "{names[0 if is_ru else 1]}"'
        for key, names in ACCESS_REQUIREMENT_LOCALISATION.items()
    ]
    lines.append("")
    for equipment_id, values in LAND_EQUIPMENT_LOCALISATION.items():
        if is_ru:
            name, short, description = values[0], values[2], values[4]
        else:
            name, short, description = values[1], values[3], values[5]
        lines.extend((
            f' {equipment_id}:0 "{name}"',
            f' {equipment_id}_short:0 "{short}"',
            f' {equipment_id}_desc:0 "{description}"',
        ))
    lines.append("")
    for branch in BRANCHES:
        key = f"ADISCORD_TECH_BRANCH_{branch.key.upper()}"
        lines.append(f" {key}:0 \"{branch.ru if is_ru else branch.en}\"")
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
            year = branch.years[index]
            technical = TECHNICAL_TECH_DESCRIPTIONS.get(tech.key)
            description = (
                technical[0 if is_ru else 1]
                if technical
                else branch_description
            )
            if is_ru:
                desc = f"{description}. Технологический уровень {year} года."
            else:
                desc = f"{description}. Technology level: {year}."
            notes = technology_description_notes(branch, index, is_ru)
            if notes:
                desc += " " + " ".join(notes)
            lines.append(f" {tech.id}:0 \"{name}\"")
            lines.append(f" {tech.id}_desc:0 \"{desc}\"")
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
                lines.append(f" {tech.id}_leader_effect_tt:0 \"{tooltip}\"")
    return lines


def write_localisation() -> None:
    targets = {
        "russian": ROOT / "localisation" / "russian" / "ADISCORD_technology_doctrine_l_russian.yml",
        "english": ROOT / "localisation" / "english" / "ADISCORD_technology_doctrine_l_english.yml",
    }
    generated_key = re.compile(r"^\s+([A-Za-z0-9_]+)\s*:")
    generated_equipment_keys = {
        suffix
        for equipment_id in LAND_EQUIPMENT_LOCALISATION
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
                or key in generated_equipment_keys
            ):
                continue
            preserved.append(line)
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
    if horizontal:
        grid_width = (
            max(YEAR_TO_Y.values()) * HORIZONTAL_YEAR_SLOT_MULTIPLIER
            + HORIZONTAL_YEAR_SLOT_MULTIPLIER
        ) * GRID_SLOT
        cursor_y = GRID_Y
        for branch in branches:
            graph = BRANCH_GRAPHS[branch.key]
            grid_height = (max(graph.lanes) + 1) * HORIZONTAL_LANE_SLOT
            branch_layouts.append((branch, GRID_X, cursor_y, grid_width, grid_height))
            cursor_y += grid_height + BRANCH_GAP
        content_width = max(1180, GRID_X + grid_width + 80)
        height = max(700, cursor_y + 80)
    else:
        cursor_x = GRID_X
        grid_height = (max(YEAR_TO_Y.values()) + 1) * GRID_SLOT
        for branch in branches:
            graph = BRANCH_GRAPHS[branch.key]
            grid_width = (
                max(graph.lanes) * LANE_SLOT_MULTIPLIER + LANE_SLOT_MULTIPLIER
            ) * GRID_SLOT
            branch_layouts.append((branch, cursor_x, GRID_Y, grid_width, grid_height))
            cursor_x += grid_width + BRANCH_GAP
        content_width = max(1180, cursor_x + 80)
        height = max(700, GRID_Y + grid_height + 100)
    background = FOLDER_BACKGROUNDS[folder]
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
    for index, year in enumerate(YEARS):
        if horizontal:
            year_x = (
                GRID_X
                + chronological_grid_slot(year, horizontal=True) * GRID_SLOT
                + 18
            )
            year_y = 84
        else:
            year_x = 24
            year_y = GRID_Y + index * GRID_SLOT + 18
        lines.extend((
            "\t\t\t\tinstantTextBoxType = {",
            f"\t\t\t\t\tname = \"ADISCORD_{folder}_year_{year}\"",
            f"\t\t\t\t\tposition = {{ x = {year_x} y = {year_y} }}",
            "\t\t\t\t\tfont = \"hoi_18b\"",
            f"\t\t\t\t\ttext = \"{year}\"",
            "\t\t\t\t\tmaxWidth = 94",
            "\t\t\t\t\tmaxHeight = 22",
            "\t\t\t\t\tformat = left",
            "\t\t\t\t\tOrientation = \"UPPER_LEFT\"",
            "\t\t\t\t}",
        ))
    # Technology grid boxes must be direct children of the folder container.
    # The game does not discover grids nested inside the decorative
    # ``techtree_stripes`` container and reports every technology as having
    # no grid box even when the grid name itself is correct.
    lines.append("\t\t\t}")
    for branch, grid_x, grid_y, grid_width, grid_height in branch_layouts:
        slot_height = HORIZONTAL_LANE_SLOT if horizontal else GRID_SLOT
        if horizontal:
            title_x = grid_x
            title_y = grid_y - 30
            title_width = min(900, grid_width)
            title_format = "left"
        else:
            title_x = grid_x
            title_y = 76
            title_width = grid_width
            title_format = "center"
        lines.extend((
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
            "\t\t\tgridboxtype = {",
            f"\t\t\t\tname = \"{branch.techs[0].id}_tree\"",
            f"\t\t\t\tposition = {{ x = {grid_x} y = {grid_y} }}",
            f"\t\t\t\tsize = {{ width = {grid_width} height = {grid_height} }}",
            f"\t\t\t\tslotsize = {{ width = {GRID_SLOT} height = {slot_height} }}",
            f"\t\t\t\tformat = \"{folder_grid_format(folder)}\"",
            "\t\t\t}",
        ))
    lines.append("\t\t}")
    return "\n".join(lines)


def write_gui() -> None:
    base_gui = BASE_GAME / "interface" / "countrytechtreeview.gui"
    source = base_gui if base_gui.exists() else ROOT / "interface" / "countrytechtreeview.gui"
    text = source.read_text(encoding="utf-8-sig")
    starts = [match.start() for match in re.finditer(r"containerWindowType\s*=\s*\{", text)]
    replacements: list[tuple[int, int, str]] = []
    found: set[str] = set()
    named_blocks: dict[str, tuple[int, int, str]] = {}
    for start in starts:
        open_brace = text.find("{", start)
        end = find_block_end(text, open_brace)
        head = text[open_brace + 1:min(end, open_brace + 300)]
        name_match = re.search(r"\bname\s*=\s*\"([^\"]+)\"", head)
        if not name_match:
            continue
        name = name_match.group(1)
        named_blocks[name] = (start, end, text[start:end])
        if name in FOLDER_BACKGROUNDS:
            replacements.append((start, end, render_folder(name)))
            found.add(name)
    missing = set(FOLDER_BACKGROUNDS) - found
    if missing:
        raise ValueError(f"Missing technology folder containers: {sorted(missing)}")

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
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    (ROOT / "interface" / "countrytechtreeview.gui").write_text(text, encoding="utf-8")


def write_technology_migration_manifest() -> None:
    path = ROOT / "tools" / "data" / "adiscord_technology_id_migrations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "legacy_count": len(TECHNOLOGY_ID_MIGRATIONS),
        "current_count": len(CURRENT_TECH_IDS),
        "migrations": {
            tech_id: TECHNOLOGY_ID_MIGRATIONS[tech_id]
            for tech_id in sorted(TECHNOLOGY_ID_MIGRATIONS)
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def apply() -> None:
    all_ids = [tech.id for branch in BRANCHES for tech in branch.techs]
    duplicates = sorted({tech_id for tech_id in all_ids if all_ids.count(tech_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate technology IDs: {duplicates}")
    write_technology_files()
    write_starting_technology_effect()
    write_gfx()
    write_localisation()
    write_gui()
    write_technology_migration_manifest()
    write_starting_technology_profile_manifest()
    print(
        f"Generated {len(all_ids)} technologies in {len(BRANCHES)} content branches; "
        f"{len(APPLIED_PROGRAMME_KEYS)} applied branches are attached specialisations."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the A-Discord technology system.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate current generated outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write technology files, manifests, GUI and localisation")
    args = parser.parse_args()
    if args.apply:
        apply()
        return 0
    from tools.validators.validate_adiscord_tech_doctrine import main as validate_main

    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
