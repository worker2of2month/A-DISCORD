from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import json
import re

from tools.lib.paths import repository_root
from tools.builders.build_adiscord_technology_ui_assets import (
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
BRANCH_GAP = 90
HORIZONTAL_YEAR_SLOT_MULTIPLIER = 3
# A one-slot step puts a 72px icon 70px from its neighbour and leaves no room for
# the connector, so vertical tabs spend two slots per rung exactly as vanilla
# does. Left-to-right tabs already spend three because their cards are 183px wide.
VERTICAL_YEAR_SLOT_MULTIPLIER = 2
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
        "Личное оружие и боеприпасы", "Personal Weapons and Ammunition", "infantry",
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
        "Групповое оружие и огневая поддержка", "Crew-served Weapons and Fire Support", "squad",
        techs("""
belt_fed_recovery|Пулемёты с ленточным питанием|Belt-fed Machine Guns|support_weapons
squad_grenade_launchers|Стандартизация ленточных пулемётов|Standardized Belt-fed Machine Guns|support_weapons2
portable_at_cells|Противотанковое оружие расчёта|Crew-served Anti-tank Weapons|infantry_at
field_ew_units|Прицелы группового оружия|Crew-served Weapon Sights|support_weapons3
networked_command_terminals|Терминалы управления огнём|Fire-control Terminals|signal_company
autonomous_support_weapons|Автоматизированные огневые установки|Automated Fire-support Mounts|support_weapons4
swarm_fireteams|Единая сеть огневой поддержки|Integrated Fire-support Network|special_forces
"""),
    ),
    Branch(
        "protection", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Защита и медицина", "Protection and Medicine", "protection",
        techs("""
composite_protection_kits|Композитные бронежилеты|Composite Body Armour|tech_engineers
trauma_plates|Амортизирующие вкладыши брони|Armour Trauma Pads|tech_field_hospital
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
fieldcraft_manuals|Полевая подготовка разведчиков|Scout Fieldcraft Training|tech_recon
urban_breaching|Инструменты штурмового вскрытия|Assault Breaching Tools|special_forces
radiation_patrols|Разведка заражённой местности|Contaminated-area Reconnaissance|tech_recon2
combat_recon_drones|Разведывательные дроны|Combat Recon Drones|paratroopers
vertical_assault_training|Высотная штурмовая подготовка|Vertical Assault Training|paratroopers2
deep_recon_cells|Группы дальней разведки|Long-range Reconnaissance Teams|tech_recon4
augmented_special_forces|Экзоскелеты спецназа|Special Forces Exoskeletons|paratroopers3
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
recovered_medium_chassis|Восстановленный основной боевой танк|Restored Main Battle Tank|basic_medium_tank
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
    tech.key: tech
    for branch in LEGACY_BRANCHES
    for tech in branch.techs
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
        key, file, folders, ru, en, profile,
        tuple(Tech(row[0], row[1], row[2], row[3], tuple(row[5])) for row in rows),
        tuple(row[4] for row in rows),
    )


BRANCHES = (
    research_branch(
        "production", "ADISCORD_industry.txt", ('industry_folder',),
        "Станки и автоматизация", "Machine Tools and Automation", "production",
        (
            ("standardized_machine_tools", "Стандартные станки", "Standardized Machine Tools", "basic_machine_tools", 2150, (
                "production_factory_max_efficiency_factor = 0.03",
                "production_factory_efficiency_gain_factor = 0.02",
            )),
            ("interchangeable_components", "Взаимозаменяемые узлы", "Interchangeable Components", "improved_machine_tools", 2155, (
                "production_factory_start_efficiency_factor = 0.03",
                "line_change_production_efficiency_factor = 0.04",
            )),
            ("industrial_cluster_planning", "Промышленные кластеры", "Industrial Cluster Planning", "concentrated_industry", 2158, (
                "production_speed_industrial_complex_factor = 0.03",
                "production_speed_arms_factory_factor = 0.03",
            )),
            ("precision_metrology_recovery", "Восстановление точной метрологии", "Precision Metrology Recovery", "improved_machine_tools", 2160, (
                "production_factory_max_efficiency_factor = 0.04",
                "production_factory_efficiency_gain_factor = 0.03",
            )),
            ("automated_assembly", "Автоматизированная сборка", "Automated Assembly", "assembly_line_production", 2161, (
                "industrial_capacity_factory = 0.015",
                "production_factory_efficiency_gain_factor = 0.03",
                "ADISCORD_economy_civilian_factory_income_factor = 0.02",
            )),
            ("digital_tooling_libraries", "Цифровые библиотеки оснастки", "Digital Tooling Libraries", "advanced_machine_tools", 2163, (
                "production_factory_start_efficiency_factor = 0.05",
                "line_change_production_efficiency_factor = 0.08",
            )),
            ("sensor_calibrated_machining", "Сенсорная калибровка станков", "Sensor-Calibrated Machining", "advanced_machine_tools", 2163, (
                "production_factory_max_efficiency_factor = 0.06",
                "production_factory_efficiency_gain_factor = 0.04",
            )),
            ("predictive_maintenance", "Предиктивное обслуживание", "Predictive Maintenance", "advanced_machine_tools", 2167, (
                "production_factory_efficiency_gain_factor = 0.05",
                "industry_repair_factor = 0.04",
                "ADISCORD_economy_military_factory_expense_factor = -0.02",
            )),
            ("autonomous_factory_cells", "Автономные заводские ячейки", "Autonomous Factory Cells", "flexible_line", 2172, (
                "industrial_capacity_factory = 0.04",
                "factory_energy_consumption = 0.06",
                "production_factory_max_efficiency_factor = 0.06",
                "ADISCORD_economy_civilian_factory_income_factor = 0.03",
            )),
            ("distributed_manufacturing", "Распределённое производство", "Distributed Manufacturing", "streamlined_line", 2180, (
                "industrial_capacity_factory = 0.10",
                "industrial_capacity_dockyard = 0.07",
                "factory_energy_consumption = 0.12",
                "production_factory_max_efficiency_factor = 0.09",
            )),
        ),
    ),
    research_branch(
        "industry_organization", "ADISCORD_industry.txt", ('industry_folder',),
        "Организация промышленности", "Industrial Organization", "production",
        (
            ("industrial_organization_baseline", "Организация производственных сетей", "Production Network Organization", "basic_machine_tools", 2160, (
                "production_factory_start_efficiency_factor = 0.02",
                "production_factory_efficiency_gain_factor = 0.02",
            )),
            ("concentrated_industrial_zones", "Концентрированные промышленные зоны", "Concentrated Industrial Zones", "basic_machine_tools", 2162, (
                "industrial_capacity_factory = 0.05",
                "industrial_capacity_dockyard = 0.04",
                "factory_energy_consumption = 0.10",
                "industry_air_damage_factor = 0.07",
            )),
            ("distributed_workshop_networks", "Распределённые сети мастерских", "Distributed Workshop Networks", "basic_machine_tools", 2162, (
                "industrial_capacity_factory = 0.03",
                "factory_energy_consumption = 0.02",
                "production_factory_start_efficiency_factor = 0.07",
                "industry_air_damage_factor = -0.08",
            )),
            ("megafactory_power_buses", "Энергоконтуры мегафабрик", "Megafactory Power Buses", "basic_machine_tools", 2167, (
                "industrial_capacity_factory = 0.07",
                "industrial_capacity_dockyard = 0.05",
                "factory_energy_consumption = 0.15",
                "line_change_production_efficiency_factor = -0.12",
            )),
            ("regional_spare_capacity", "Региональный резерв мощностей", "Regional Spare Capacity", "basic_machine_tools", 2167, (
                "industrial_capacity_factory = 0.03",
                "factory_energy_consumption = 0.02",
                "line_change_production_efficiency_factor = 0.14",
                "industry_repair_factor = 0.12",
            )),
            ("continuous_casting_lines", "Линии непрерывного литья", "Continuous Casting Lines", "basic_machine_tools", 2173, (
                "industrial_capacity_factory = 0.09",
                "production_factory_max_efficiency_factor = 0.07",
                "factory_energy_consumption = 0.19",
                "industry_air_damage_factor = 0.12",
            )),
            ("mobile_fabrication_convoys", "Мобильные производственные колонны", "Mobile Fabrication Convoys", "basic_machine_tools", 2173, (
                "industrial_capacity_factory = 0.04",
                "factory_energy_consumption = 0.03",
                "industry_air_damage_factor = -0.15",
                "industry_repair_factor = 0.15",
            )),
            ("strategic_production_complexes", "Стратегические производственные комплексы", "Strategic Production Complexes", "basic_machine_tools", 2180, (
                "industrial_capacity_factory = 0.12",
                "industrial_capacity_dockyard = 0.10",
                "factory_energy_consumption = 0.24",
                "industry_air_damage_factor = 0.20",
                "line_change_production_efficiency_factor = -0.15",
            )),
            ("resilient_production_meshes", "Устойчивые производственные сети", "Resilient Production Meshes", "basic_machine_tools", 2180, (
                "industrial_capacity_factory = 0.06",
                "factory_energy_consumption = 0.04",
                "production_factory_start_efficiency_factor = 0.10",
                "line_change_production_efficiency_factor = 0.22",
                "industry_air_damage_factor = -0.20",
                "industry_repair_factor = 0.22",
            )),
        ),
    ),
    research_branch(
        "reconstruction", "ADISCORD_industry.txt", ('industry_folder',),
        "Строительство и восстановление", "Construction and Recovery", "construction",
        (
            ("salvage_standards", "Стандарты утилизации", "Salvage Standards", "basic_machine_tools", 2150, (
                "production_speed_buildings_factor = 0.02",
                "industry_repair_factor = 0.02",
            )),
            ("ruin_workshops", "Мастерские среди руин", "Ruin Workshops", "improved_machine_tools", 2155, (
                "production_speed_buildings_factor = 0.02",
                "industry_repair_factor = 0.03",
            )),
            ("reconstruction_bureaus", "Бюро реконструкции", "Reconstruction Bureaus", "basic_construction", 2158, (
                "production_speed_buildings_factor = 0.03",
                "industry_repair_factor = 0.03",
            )),
            ("drone_construction_cartography", "Картография строительных дронов", "Construction Drone Cartography", "basic_construction", 2160, (
                "production_speed_buildings_factor = 0.03",
                "production_speed_infrastructure_factor = 0.04",
            )),
            ("modular_rebuilding", "Модульная застройка", "Modular Rebuilding", "improved_construction", 2165, (
                "production_speed_buildings_factor = 0.04",
                "production_speed_industrial_complex_factor = 0.03",
            )),
            ("prefabricated_districts", "Сборные кварталы", "Prefabricated Districts", "advanced_construction", 2169, (
                "production_speed_buildings_factor = 0.04",
                "consumer_goods_factor = -0.02",
            )),
            ("public_repair_corps", "Общественные ремонтные корпуса", "Public Repair Corps", "advanced_construction", 2171, (
                "industry_repair_factor = 0.08",
                "industry_air_damage_factor = -0.05",
            )),
            ("automated_civil_works", "Автоматизированные стройки", "Automated Civil Works", "advanced_construction", 2175, (
                "production_speed_buildings_factor = 0.06",
                "production_speed_industrial_complex_factor = 0.05",
            )),
            ("civil_defense_networks", "Комплексная гражданская оборона", "Civil Defense Networks", "concentrated_industry5", 2180, (
                "production_speed_buildings_factor = 0.06",
                "production_speed_infrastructure_factor = 0.05",
                "industry_repair_factor = 0.10",
                "industry_air_damage_factor = -0.10",
            )),
        ),
    ),
    research_branch(
        "resources", "ADISCORD_industry.txt", ('industry_folder',),
        "Ресурсы и энергия", "Resources and Energy", "resources",
        (
            ("salvage_metallurgy", "Утилизационная металлургия", "Salvage Metallurgy", "excavation1", 2150, (
                "local_resources_factor = 0.02",
                "fuel_gain_factor = 0.012",
            )),
            ("grid_rationing", "Нормирование энергосети", "Grid Rationing", "oil_processing", 2155, (
                "local_resources_factor = 0.021",
                "fuel_gain_factor = 0.012",
            )),
            ("refinery_reclamation", "Восстановление НПЗ", "Refinery Reclamation", "improved_oil_processing", 2158, (
                "local_resources_factor = 0.021",
                "fuel_gain_factor = 0.013",
            )),
            ("spectral_ore_sorting", "Спектральная сортировка руды", "Spectral Ore Sorting", "excavation2", 2160, (
                "local_resources_factor = 0.022",
                "fuel_gain_factor = 0.013",
            )),
            ("logistics_hub_networks", "Сети логистических узлов", "Logistics Hub Networks", "excavation2", 2161, (
                "local_resources_factor = 0.023",
                "fuel_gain_factor = 0.013",
            )),
            ("borehole_sensor_grids", "Сети скважинных датчиков", "Borehole Sensor Grids", "excavation1", 2162, (
                "local_resources_factor = 0.023",
                "fuel_gain_factor = 0.014",
            )),
            ("plasma_scrap_separation", "Промышленный электролиз", "Industrial Electrolysis", "excavation2", 2163, (
                "production_lack_of_resource_penalty_factor = -0.024",
                "industry_repair_factor = 0.014",
            )),
            ("microbial_tailings_leaching", "Микробиологическое извлечение металлов", "Microbial Metal Recovery", "excavation4", 2164, (
                "local_resources_factor = 0.031",
                "production_lack_of_resource_penalty_factor = -0.007",
            )),
            ("synthetic_resource_cycles", "Синтетические циклы", "Synthetic Resource Cycles", "rubber_processing", 2166, (
                "local_resources_factor = 0.026",
                "fuel_gain_factor = 0.015",
            )),
            ("rare_earth_solvent_loops", "Замкнутые циклы редкоземельной экстракции", "Rare-Earth Solvent Loops", "excavation4", 2169, (
                "local_resources_factor = 0.028",
                "fuel_gain_factor = 0.016",
            )),
            ("automated_deep_mining", "Автоматизированная глубокая добыча", "Automated Deep Mining", "excavation5", 2171, (
                "local_resources_factor = 0.036",
                "production_lack_of_resource_penalty_factor = -0.008",
            )),
            ("carbon_feedstock_cracking", "Крекинг углеродного сырья", "Carbon Feedstock Cracking", "oil_processing", 2172, (
                "local_resources_factor = 0.017",
                "fuel_gain_factor = 0.029",
            )),
            ("strategic_element_reclamation", "Регенерация стратегических элементов", "Strategic Element Reclamation", "excavation5", 2175, (
                "local_resources_factor = 0.031",
                "fuel_gain_factor = 0.018",
            )),
            ("strategic_material_recovery", "Извлечение редких материалов", "Strategic Material Recovery", "excavation5", 2180, (
                "local_resources_factor = 0.046",
                "fuel_gain_factor = 0.026",
                "production_lack_of_resource_penalty_factor = -0.026",
            )),
        ),
    ),
    research_branch(
        "public_finance", "ADISCORD_industry.txt", ('industry_folder',),
        "Экономика и управление", "Economy and Administration", "finance",
        (
            ("treasury_accounting", "Казначейский учёт", "Treasury Accounting", "mechanical_computing", 2155, (
                "ADISCORD_economy_tax_collection_factor = 0.02",
                "ADISCORD_economy_admin_expense_factor = -0.02",
            )),
            ("public_procurement_standards", "Стандарты государственных закупок", "Public Procurement Standards", "computing_machine", 2160, (
                "ADISCORD_economy_construction_expense_factor = -0.03",
                "ADISCORD_economy_military_factory_expense_factor = -0.02",
            )),
            ("civilian_industrial_accounting", "Промышленный учёт", "Industrial Accounting", "improved_machine_tools", 2162, (
                "ADISCORD_economy_civilian_factory_income_factor = 0.04",
                "ADISCORD_economy_tax_collection_factor = 0.02",
            )),
            ("administrative_digitization", "Цифровое делопроизводство", "Digital Administration", "improved_computing_machine", 2166, (
                "ADISCORD_economy_admin_expense_factor = -0.04",
                "ADISCORD_economy_research_expense_factor = -0.03",
            )),
            ("production_cost_accounting", "Учёт производственных затрат", "Production Cost Accounting", "advanced_machine_tools", 2169, (
                "ADISCORD_economy_military_industry_income_factor = 0.04",
                "ADISCORD_economy_military_factory_expense_factor = -0.03",
            )),
            ("automated_treasury_audit", "Автоматизированный финансовый контроль", "Automated Treasury Audit", "advanced_computing_machine", 2175, (
                "ADISCORD_economy_tax_collection_factor = 0.03",
                "ADISCORD_economy_civilian_factory_income_factor = 0.04",
            )),
        ),
    ),
    research_branch(
        "advanced_materials", "ADISCORD_industry.txt", ('industry_folder',),
        "Редкие материалы", "Advanced Materials", "resources",
        (
            ("precision_material_standards", "Стандарты чистоты материалов", "Material Purity Standards", "improved_machine_tools", 2155, (
                "production_lack_of_resource_penalty_factor = -0.01",
                "production_factory_efficiency_gain_factor = 0.01",
            )),
            ("rare_components_industry", "Производство редких компонентов", "Rare Components Industry", "computing_machine", 2158, (
                "production_factory_efficiency_gain_factor = 0.02",
                "production_factory_max_efficiency_factor = 0.01",
            )),
            ("rare_alloy_metallurgy", "Металлургия редких сплавов", "Rare Alloy Metallurgy", "excavation2", 2158, (
                "production_lack_of_resource_penalty_factor = -0.02",
                "production_factory_max_efficiency_factor = 0.01",
            )),
            ("precision_component_fabrication", "Прецизионная сборка компонентов", "Precision Component Fabrication", "advanced_computing_machine", 2166, (
                "production_factory_efficiency_gain_factor = 0.02",
                "factory_energy_consumption = 0.02",
            )),
            ("vacuum_alloy_refining", "Вакуумная очистка сплавов", "Vacuum Alloy Refining", "excavation4", 2166, (
                "production_factory_max_efficiency_factor = 0.02",
                "factory_energy_consumption = 0.02",
            )),
            ("advanced_material_recycling", "Переработка редких материалов", "Advanced Material Recycling", "excavation5", 2173, (
                "production_lack_of_resource_penalty_factor = -0.02",
                "factory_energy_consumption = -0.02",
            )),
        ),
    ),
    research_branch(
        "signals", "ADISCORD_electronics.txt", ('electronics_folder',),
        "Связь и кибервойна", "Signals and Cyberwarfare", "signals",
        (
            ("mesh_command_networks", "Ячеистые сети управления", "Mesh Command Networks", "radio", 2150, (
                "coordination_bonus = 0.01",
                "encryption_factor = 0.01",
            )),
            ("field_radio_networks", "Полевые радиосети", "Field Radio Networks", "radio_detection", 2155, (
                "land_reinforce_rate = 0.01",
                "encryption_factor = 0.02",
            )),
            ("encryption_rebuild", "Восстановление шифрования", "Encryption Rebuild", "basic_encryption", 2158, (
                "encryption_factor = 0.03",
                "coordination_bonus = 0.01",
            )),
            ("frequency_hopping_field_sets", "Полевые станции со скачками частоты", "Frequency-Hopping Field Sets", "radio", 2160, (
                "encryption_factor = 0.04",
                "land_reinforce_rate = 0.01",
            )),
            ("signal_intercept_arrays", "Массивы радиоперехвата", "Signal Intercept Arrays", "basic_decryption", 2161, (
                "decryption_factor = 0.04",
                "air_interception_detect_factor = 0.02",
            )),
            ("battlefield_analytics", "Аналитика поля боя", "Battlefield Analytics", "improved_encryption", 2166, (
                "coordination_bonus = 0.02",
                "decryption_factor = 0.03",
            )),
            ("counterintelligence_filters", "Автоматизация контрразведки", "Counterintelligence Filters", "improved_decryption", 2170, (
                "encryption_factor = 0.05",
                "decryption_factor = 0.02",
            )),
            ("battlefield_sensor_fusion", "Сведение датчиков поля боя", "Battlefield Sensor Fusion", "radio_detection", 2172, (
                "coordination_bonus = 0.03",
                "air_interception_detect_factor = 0.04",
            )),
            ("self_healing_tactical_networks", "Самовосстанавливающиеся тактические сети", "Self-Healing Tactical Networks", "advanced_encryption", 2175, (
                "encryption_factor = 0.06",
                "land_reinforce_rate = 0.02",
            )),
            ("memetic_security_protocols", "Протоколы меметической защиты", "Memetic Security Protocols", "advanced_encryption", 2180, (
                "encryption_factor = 0.07",
                "decryption_factor = 0.04",
                "coordination_bonus = 0.03",
            )),
        ),
    ),
    research_branch(
        "computing", "ADISCORD_electronics.txt", ('electronics_folder',),
        "Вычисления и управление", "Computing and Control", "computing",
        (
            ("electromechanical_relays", "Электромеханические реле", "Electromechanical Relays", "mechanical_computing", 2150, (
                "research_speed_factor = 0.01",
                "production_factory_efficiency_gain_factor = 0.01",
            )),
            ("recovered_data_archives", "Восстановленные архивы", "Recovered Data Archives", "electronic_mechanical_engineering", 2155, (
                "research_speed_factor = 0.015",
                "planning_speed = 0.01",
            )),
            ("recovered_semiconductors", "Восстановленные полупроводники", "Recovered Semiconductors", "computing_machine", 2158, (
                "research_speed_factor = 0.02",
                "production_factory_efficiency_gain_factor = 0.02",
            )),
            ("hardened_computers", "Защищённые вычислители", "Hardened Computers", "basic_encryption", 2160, (
                "research_speed_factor = 0.025",
                "encryption_factor = 0.02",
            )),
            ("error_correcting_field_computers", "Полевые вычислители с коррекцией ошибок", "Error-Correcting Field Computers", "radio_detection", 2162, (
                "research_speed_factor = 0.03",
                "encryption_factor = 0.035",
                "supply_consumption_factor = -0.015",
            )),
            ("predictive_logistics", "Предиктивная логистика", "Predictive Logistics", "mechanical_computing", 2166, (
                "research_speed_factor = 0.025",
                "supply_consumption_factor = -0.03",
                "encryption_factor = 0.03",
            )),
            ("operational_ai_assistants", "Операционные ИИ-ассистенты", "Operational AI Assistants", "radio_detection", 2170, (
                "research_speed_factor = 0.025",
                "coordination_bonus = 0.035",
                "factory_energy_consumption = 0.06",
            )),
            ("strategic_digital_twins", "Стратегические цифровые двойники", "Strategic Digital Twins", "advanced_computing_machine", 2174, (
                "research_speed_factor = 0.03",
                "planning_speed = 0.03",
                "production_factory_efficiency_gain_factor = 0.03",
            )),
            ("strategic_ai_coordination", "Стратегическая ИИ-координация", "Strategic AI Coordination", "computing_machine", 2180, (
                "research_speed_factor = 0.04",
                "coordination_bonus = 0.05",
                "production_factory_efficiency_gain_factor = 0.04",
                "factory_energy_consumption = 0.04",
            )),
        ),
    ),
    research_branch(
        "power", "ADISCORD_electronics.txt", ('electronics_folder',),
        "Энергетика и реакторы", "Power and Reactors", "power",
        (
            ("local_grid_restoration", "Локальные энергосети", "Local Grid Restoration", "electronic_mechanical_engineering", 2150, (
                "factory_energy_consumption = -0.03",
                "industry_repair_factor = 0.02",
            )),
            ("substation_networks", "Восстановление подстанций", "Substation Networks", "oil_plant", 2155, (
                "factory_energy_consumption = -0.035",
                "production_speed_infrastructure_factor = 0.025",
            )),
            ("radiation_mapping", "Радиационное картирование", "Radiation Mapping", "atomic_research", 2158, (
                "factory_energy_consumption = -0.025",
                "nuclear_production_factor = 0.03",
            )),
            ("phase_synchronized_substations", "Фазосинхронизированные подстанции", "Phase-Synchronized Substations", "nuclear_reactor", 2160, (
                "factory_energy_consumption = -0.04",
                "industry_repair_factor = 0.03",
                "ADISCORD_economy_military_factory_expense_factor = -0.01",
            )),
            ("reactor_safety_protocols", "Безопасность реакторов", "Reactor Safety Protocols", "oil_plant", 2166, (
                "factory_energy_consumption = -0.04",
                "nuclear_production_factor = 0.05",
            )),
            ("load_following_microreactors", "Маневренные микрореакторы", "Load-Following Microreactors", "nuclear_reactor", 2168, (
                "factory_energy_consumption = -0.05",
                "nuclear_production_factor = 0.06",
                "ADISCORD_economy_military_factory_expense_factor = -0.02",
            )),
            ("superconducting_power_busbars", "Сверхпроводящие силовые шины", "Superconducting Power Busbars", "advanced_oil_plant", 2169, (
                "factory_energy_consumption = -0.05",
                "industrial_capacity_factory = 0.01",
            )),
            ("microreactor_blocks", "Массивы микрореакторов", "Microreactor Blocks", "sp_nuclear_isotope_separation", 2170, (
                "factory_energy_consumption = -0.055",
                "nuclear_production_factor = 0.07",
            )),
            ("continental_load_balancing", "Континентальная балансировка нагрузки", "Continental Load Balancing", "atomic_research", 2175, (
                "factory_energy_consumption = -0.06",
                "production_speed_buildings_factor = 0.04",
                "ADISCORD_economy_military_factory_expense_factor = -0.02",
            )),
            ("emergency_core_suppression", "Аварийное глушение ядра", "Emergency Core Suppression", "nuclear_reactor", 2180, (
                "factory_energy_consumption = -0.07",
                "nuclear_production_factor = 0.08",
                "industry_repair_factor = 0.06",
            )),
        ),
    ),
    research_branch(
        "forbidden_energy", "ADISCORD_forbidden.txt", ('electronics_folder',),
        "Запретная энергетика", "Forbidden Energy", "forbidden_energy",
        (
            ("old_generator_fragments", "Фрагменты старого генератора", "Old Generator Fragments", "atomic_research", 2164, (
                "nuclear_production_factor = 0.04",
                "industry_repair_factor = 0.02",
                "stability_factor = -0.005",
            )),
            ("legacy_reactor_compactification", "Компактификация реакторов", "Legacy Reactor Compactification", "sp_nuclear_isotope_separation", 2168, (
                "nuclear_production_factor = 0.08",
                "production_speed_buildings_factor = 0.025",
                "stability_factor = -0.011",
            )),
            ("singularity_cooling_systems", "Сингулярное охлаждение", "Singularity Cooling Systems", "advanced_rocket_engines", 2173, (
                "nuclear_production_factor = 0.12",
                "research_speed_factor = 0.025",
                "stability_factor = -0.017",
            )),
            ("black_grid_protocols", "Протоколы чёрной энергосети", "Black Grid Protocols", "sp_physics_advanced_radio", 2180, (
                "nuclear_production_factor = 0.16",
                "industrial_capacity_factory = 0.04",
                "stability_factor = -0.025",
            )),
        ),
    ),
    research_branch(
        "forbidden_automation", "ADISCORD_forbidden.txt", ('electronics_folder',),
        "Запретная автоматизация", "Forbidden Automation", "forbidden_automation",
        (
            ("self_repairing_industrial_swarms", "Самовосстанавливающиеся рои", "Self-repairing Industrial Swarms", "flexible_line", 2168, (
                "production_factory_max_efficiency_factor = 0.04",
                "industry_repair_factor = 0.03",
                "stability_factor = -0.01",
            )),
            ("neural_command_cores", "Нейронные командные ядра", "Neural Command Cores", "improved_computing_machine", 2172, (
                "coordination_bonus = 0.05",
                "land_reinforce_rate = 0.03",
                "stability_factor = -0.02",
            )),
            ("forbidden_automation_doctrine", "Доктрина запретной автоматизации", "Forbidden Automation Doctrine", "advanced_computing_machine", 2180, (
                "production_factory_max_efficiency_factor = 0.08",
                "research_speed_factor = 0.04",
                "stability_factor = -0.035",
            )),
        ),
    ),
    research_branch(
        "small_arms", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Личное оружие и боеприпасы", "Personal Weapons and Ammunition", "infantry",
        (
            ("postwar_weapon_standardization", "Высокоточная нарезка стволов", "Precision Rifling of Barrel Bores", "infantry_weapons", 2150, (
                "category_all_infantry = { soft_attack = 0.024 }",
            )),
            ("refurbished_receivers", "Герметизация казённой части", "Breech Obturation", "infantry_weapons", 2155, (
                "category_all_infantry = { defense = 0.024 }",
            )),
            ("standardized_cartridges", "Унитарный металлический патрон", "Metallic Self-contained Cartridge", "ADISCORD_equipment_ammunition", 2158, (
                "category_all_infantry = { soft_attack = 0.028 }",
            )),
            ("caseless_ammunition_trials", "Нитроцеллюлозные метательные составы", "Nitrocellulose Propellant Formulations", "ADISCORD_equipment_ammunition", 2160, (
                "category_all_infantry = { soft_attack = 0.028 breakthrough = 0.008 }",
            )),
            ("sealed_receiver_assemblies", "Промежуточные патроны", "Intermediate Cartridges", "infantry_weapons", 2162, (
                "category_all_infantry = { breakthrough = 0.024 soft_attack = 0.012 }",
            )),
            ("electrothermal_ignition", "Высокопрочные ствольные стали", "High-strength Barrel Steels", "ADISCORD_weapon_03_standardized_battle_rifle", 2163, (
                "category_all_infantry = { defense = 0.028 breakthrough = 0.008 }",
            )),
            ("smart_recoil_compensators", "Самозарядная автоматика", "Self-loading Action", "infantry_weapons3", 2164, (
                "category_all_infantry = { soft_attack = 0.032 breakthrough = 0.016 }",
            )),
            ("smart_optics", "Лазерное измерение дальности", "Laser Rangefinding", "night_vision", 2165, (
                "coordination_bonus = 0.012",
                "category_all_infantry = { soft_attack = 0.012 }",
            )),
            ("networked_weapon_sights", "Баллистические вычислители", "Computerized Ballistic Correction", "ADISCORD_equipment_ballistic_sight", 2166, (
                "coordination_bonus = 0.016",
                "category_all_infantry = { soft_attack = 0.016 }",
            )),
            ("modular_rifle_kits", "Газоотводная автоматика", "Gas-operated Action", "infantry_weapons3", 2167, (
                "category_all_infantry = { soft_attack = 0.036 breakthrough = 0.02 }",
            )),
            ("biometric_trigger_locks", "Запирание поворотным затвором", "Rotating-bolt Locking", "ADISCORD_weapon_03_standardized_battle_rifle", 2168, (
                "category_all_infantry = { defense = 0.028 breakthrough = 0.02 }",
            )),
            ("integrated_target_designation", "Электронно-оптические прицелы", "Integrated Electro-optical Sights", "ADISCORD_equipment_ballistic_sight", 2169, (
                "land_night_attack = 0.012",
                "coordination_bonus = 0.016",
            )),
            ("programmable_ammunition", "Износостойкие покрытия ствола", "Chrome Lining and Wear-resistant Bore Coatings", "infantry_at2", 2170, (
                "category_all_infantry = { defense = 0.032 soft_attack = 0.012 }",
            )),
            ("coil_assisted_service_rifles", "Оптимизация импульса отдачи", "Recoil Impulse Optimization", "infantry_weapons3", 2172, (
                "category_all_infantry = { breakthrough = 0.032 defense = 0.012 }",
            )),
            ("hybrid_kinetic_energy_carbines", "Полимерные и гибридные гильзы", "Polymer and Hybrid Cartridge Cases", "ADISCORD_equipment_ammunition", 2175, (
                "category_all_infantry = { defense = 0.024 soft_attack = 0.024 }",
            )),
            ("networked_service_rifles", "Программируемые боеприпасы", "Programmable Small-arms Ammunition", "night_vision2", 2180, (
                "category_all_infantry = { soft_attack = 0.04 }",
                "coordination_bonus = 0.024",
            )),
        ),
    ),
    research_branch(
        "squad_weapons", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Групповое оружие и огневая поддержка", "Crew-served Weapons and Fire Support", "squad",
        (
            ("belt_fed_recovery", "Пулемёты с ленточным питанием", "Belt-fed Machine Guns", "ADISCORD_squad_01_recovered_fire_support", 2150, (
                "category_all_infantry = { soft_attack = 0.024 defense = 0.04 }",
            )),
            ("squad_grenade_launchers", "Стандартизация ленточных пулемётов", "Standardized Belt-fed Machine Guns", "ADISCORD_squad_01_recovered_fire_support", 2155, (
                "category_all_infantry = { soft_attack = 0.041 hard_attack = 0.025 }",
            )),
            ("portable_at_cells", "Противотанковое оружие расчёта", "Crew-served Anti-tank Weapons", "ADISCORD_squad_02_heavy_machine_guns", 2158, (
                "category_all_infantry = { breakthrough = 0.043 ap_attack = 0.025 }",
            )),
            ("recoilless_squad_launchers", "Модульные станковые гранатомёты", "Modular Mounted Grenade Launchers", "ADISCORD_squad_02_heavy_machine_guns", 2160, (
                "category_all_infantry = { soft_attack = 0.044 hard_attack = 0.026 }",
            )),
            ("field_ew_units", "Прицелы группового оружия", "Crew-served Weapon Sights", "ADISCORD_squad_03_optical_fire_support", 2161, (
                "category_all_infantry = { max_organisation = 0.902 default_morale = 0.027 }",
            )),
            ("programmable_grenade_fuzes", "Программируемые гранатные взрыватели", "Programmable Grenade Fuzes", "ADISCORD_equipment_ammunition", 2162, (
                "category_all_infantry = { soft_attack = 0.046 hard_attack = 0.027 }",
            )),
            ("man_portable_sensor_masts", "Переносные сенсорные мачты", "Man-Portable Sensor Masts", "ADISCORD_night_05_counter_illumination", 2163, (
                "coordination_bonus = 0.048",
                "land_reinforce_rate = 0.014",
            )),
            ("drone_guided_support_fire", "Корректировка огня с дронов", "Drone-assisted Fire Adjustment", "ADISCORD_equipment_drone", 2165, (
                "category_all_infantry = { max_organisation = 1.053 default_morale = 0.029 }",
            )),
            ("networked_command_terminals", "Терминалы управления огнём", "Fire-control Terminals", "ADISCORD_equipment_radio", 2166, (
                "category_all_infantry = { max_organisation = 1.091 default_morale = 0.03 }",
            )),
            ("remote_weapon_tripods", "Дистанционные огневые установки", "Remote-controlled Weapon Mounts", "ADISCORD_squad_03_optical_fire_support", 2167, (
                "category_all_infantry = { soft_attack = 0.053 defense = 0.03 }",
            )),
            ("cooperative_target_handoff", "Передача целей между расчётами", "Cooperative Target Handoff", "ADISCORD_equipment_radio", 2169, (
                "coordination_bonus = 0.055",
                "land_reinforce_rate = 0.016",
            )),
            ("autonomous_support_weapons", "Автоматизированные огневые установки", "Automated Fire-support Mounts", "ADISCORD_squad_04_advanced_fire_support", 2170, (
                "category_all_infantry = { soft_attack = 0.056 breakthrough = 0.032 }",
            )),
            ("autonomous_mortar_sections", "Автоматизированные миномёты", "Automated Mortars", "ADISCORD_equipment_mortar", 2171, (
                "category_all_infantry = { soft_attack = 0.058 breakthrough = 0.033 }",
            )),
            ("robotic_heavy_weapon_teams", "Роботизированные огневые расчёты", "Robotic Fire-support Teams", "ADISCORD_squad_04_advanced_fire_support", 2174, (
                "category_all_infantry = { soft_attack = 0.061 defense = 0.035 }",
            )),
            ("swarm_fireteams", "Единая сеть огневой поддержки", "Integrated Fire-support Network", "ADISCORD_squad_04_advanced_fire_support", 2180, (
                "category_all_infantry = { soft_attack = 0.093 defense = 0.093 max_organisation = 2.131 }",
            )),
        ),
    ),
    research_branch(
        "anti_tank_infantry", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Пехотные противотанковые средства", "Infantry Anti-tank Weapons", "anti_tank",
        (
            ("recovered_shaped_charge_cells", "Бутылочные зажигательные смеси", "Bottle Incendiary Mixtures", "ADISCORD_antitank_01_incendiary_bottle", 2150, (
                "category_all_infantry = { hard_attack = 0.012 ap_attack = 0.008 }",
            )),
            ("disposable_launcher_standards", "Динамитные и ранцевые подрывные заряды", "Dynamite and Satchel Demolition Charges", "ADISCORD_antitank_02_satchel_charge", 2155, (
                "category_all_infantry = { hard_attack = 0.016 breakthrough = 0.008 }",
            )),
            ("tandem_penetrator_packages", "Ручные кумулятивные противотанковые гранаты", "Hand-thrown Shaped-charge Anti-tank Grenades", "ADISCORD_antitank_03_shaped_charge_grenade", 2158, (
                "category_all_infantry = { hard_attack = 0.02 ap_attack = 0.016 }",
            )),
            ("wire_guided_hunter_teams", "Тяжёлые противотанковые ружья", "Large-calibre Anti-tank Rifles", "ADISCORD_antitank_04_antitank_rifle", 2161, (
                "category_all_infantry = { hard_attack = 0.028 ap_attack = 0.02 }",
            )),
            ("recoilless_overmatch_cells", "Наведение ракет по проводам", "Command Guidance over Wire", "ADISCORD_antitank_05_wire_guidance", 2161, (
                "category_all_infantry = { ap_attack = 0.028 }",
                "coordination_bonus = 0.008",
            )),
            ("fire_and_forget_seekers", "Безоткатные противотанковые системы", "Recoilless Anti-tank Systems", "ADISCORD_antitank_06_recoilless_launcher", 2164, (
                "category_all_infantry = { hard_attack = 0.032 breakthrough = 0.02 }",
            )),
            ("programmable_anti_armor_fuzes", "Полуавтоматическое наведение ракет", "Semi-automatic Command to Line of Sight", "ADISCORD_antitank_07_saclos_guidance", 2164, (
                "category_all_infantry = { ap_attack = 0.032 }",
                "coordination_bonus = 0.012",
            )),
            ("top_attack_profiles", "Кумулятивные реактивные гранатомёты", "Shaped-charge Rocket Launchers", "ADISCORD_antitank_08_rocket_launcher", 2168, (
                "category_all_infantry = { hard_attack = 0.036 ap_attack = 0.032 }",
            )),
            ("loitering_armor_hunters", "Самонаведение для атаки сверху", "Imaging-infrared Top-attack Homing", "ADISCORD_antitank_09_top_attack_seeker", 2168, (
                "category_all_infantry = { ap_attack = 0.036 }",
                "coordination_bonus = 0.016",
            )),
            ("cooperative_hunter_cells", "Тандемные кумулятивные боевые части", "Tandem Shaped-charge Warheads", "ADISCORD_antitank_10_tandem_warhead", 2172, (
                "category_all_infantry = { hard_attack = 0.04 ap_attack = 0.036 }",
            )),
            ("terminal_overmatch_packages", "Барражирующие противотанковые боеприпасы", "Loitering Anti-armor Munitions", "ADISCORD_antitank_11_loitering_munition", 2172, (
                "category_all_infantry = { ap_attack = 0.04 }",
                "coordination_bonus = 0.02",
            )),
            ("distributed_anti_armor_net", "Общее целеуказание по данным датчиков", "Cooperative Multispectral Targeting", "ADISCORD_antitank_12_multispectral_targeting", 2180, (
                "category_all_infantry = { hard_attack = 0.048 ap_attack = 0.048 breakthrough = 0.024 }",
                "coordination_bonus = 0.024",
            )),
        ),
    ),
    research_branch(
        "night_combat", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Ночной бой", "Night Combat", "special_forces",
        (
            ("passive_intensifier_cells", "Усилители остаточного света", "Passive Intensifier Cells", "ADISCORD_night_01_passive_intensifier", 2150, (
                "land_night_attack = 0.01",
            )),
            ("sealed_night_mounts", "Защищённые корпуса ночных прицелов", "Sealed Night Mounts", "ADISCORD_night_01_passive_intensifier", 2155, (
                "land_night_attack = 0.01",
                "category_all_infantry = { defense = 0.012 }",
            )),
            ("thermal_observation_channels", "Тепловизионные каналы наблюдения", "Thermal Observation Channels", "ADISCORD_night_02_thermal_channel", 2158, (
                "land_night_attack = 0.012",
                "category_recon = { recon = 0.24 }",
            )),
            ("fused_low_light_sights", "Комбинированные ночные прицелы", "Fused Low-light Sights", "ADISCORD_night_03_fused_sight", 2161, (
                "land_night_attack = 0.014",
                "category_all_infantry = { soft_attack = 0.012 }",
            )),
            ("low_signature_illumination", "Малозаметная подсветка", "Low-signature Illumination", "ADISCORD_night_05_counter_illumination", 2161, (
                "land_night_attack = 0.012",
                "category_all_infantry = { breakthrough = 0.012 }",
            )),
            ("squad_target_sharing", "Обмен целями внутри отделения", "Squad Target Sharing", "ADISCORD_night_04_squad_target_sharing", 2164, (
                "land_night_attack = 0.014",
                "coordination_bonus = 0.01",
            )),
            ("counter_illumination_warnings", "Датчики вражеской подсветки", "Counter-illumination Warnings", "ADISCORD_night_05_counter_illumination", 2164, (
                "land_night_attack = 0.014",
                "category_all_infantry = { defense = 0.014 }",
            )),
            ("thermal_target_libraries", "Распознавание тепловых следов", "Thermal Target Libraries", "ADISCORD_night_02_thermal_channel", 2168, (
                "land_night_attack = 0.016",
                "category_recon = { recon = 0.3 }",
            )),
            ("nocturnal_sensor_discipline", "Скрытное ночное наблюдение", "Nocturnal Sensor Discipline", "ADISCORD_night_03_fused_sight", 2168, (
                "land_night_attack = 0.016",
                "category_all_infantry = { defense = 0.016 }",
            )),
            ("distributed_night_engagements", "Согласованный огонь ночью", "Distributed Night Engagements", "ADISCORD_night_06_distributed_engagement", 2172, (
                "land_night_attack = 0.018",
                "coordination_bonus = 0.014",
            )),
            ("adaptive_spectrum_concealment", "Маскировка от ночных приборов", "Adaptive Spectrum Concealment", "ADISCORD_night_05_counter_illumination", 2172, (
                "land_night_attack = 0.018",
                "category_all_infantry = { breakthrough = 0.018 }",
            )),
            ("nocturnal_combat_mesh", "Сеть ночного целеуказания", "Nocturnal Combat Mesh", "ADISCORD_night_06_distributed_engagement", 2180, (
                "land_night_attack = 0.024",
                "coordination_bonus = 0.02",
                "category_all_infantry = { defense = 0.024 breakthrough = 0.024 }",
            )),
        ),
    ),
    research_branch(
        "protection", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Защитное снаряжение", "Protective Equipment", "protection",
        (
            ("composite_protection_kits", "Композитные бронежилеты", "Composite Body Armour", "ADISCORD_equipment_armour", 2150, (
                "category_all_infantry = { defense = 0.04 max_organisation = 0.75 }",
            )),
            ("trauma_plates", "Амортизирующие вкладыши брони", "Armour Trauma Pads", "ADISCORD_equipment_armour", 2155, (
                "category_all_infantry = { defense = 0.041 reliability = 0.025 }",
            )),
            ("sealed_combat_suits", "Герметичные боевые костюмы", "Sealed Combat Suits", "ADISCORD_equipment_respirator", 2158, (
                "category_all_infantry = { defense = 0.043 supply_consumption = -0.013 }",
            )),
            ("ceramic_trauma_inserts", "Керамические бронепластины", "Ceramic Armour Plates", "ADISCORD_equipment_armour", 2160, (
                "category_all_infantry = { defense = 0.044 breakthrough = 0.026 }",
            )),
            ("sealed_respirator_interfaces", "Герметичные соединения респираторов", "Sealed Respirator Interfaces", "ADISCORD_equipment_respirator", 2162, (
                "category_all_infantry = { default_morale = 0.046 defense = 0.027 }",
            )),
            ("active_hearing_protection", "Активная защита слуха", "Active Hearing Protection", "ADISCORD_equipment_hearing_protection", 2163, (
                "category_all_infantry = { defense = 0.048 reliability = 0.028 }",
            )),
            ("thermal_signature_liners", "Тепломаскирующие подкладки", "Thermal-concealment Liners", "ADISCORD_equipment_camouflage", 2164, (
                "category_all_infantry = { defense = 0.049 supply_consumption = -0.014 }",
            )),
            ("powered_load_bearing_harnesses", "Силовые разгрузочные системы", "Powered Load-bearing Harnesses", "ADISCORD_equipment_exoskeleton", 2165, (
                "category_all_infantry = { defense = 0.05 reliability = 0.029 }",
            )),
            ("exoskeleton_load_frames", "Экзоскелетные рамы", "Exoskeleton Load Frames", "ADISCORD_equipment_exoskeleton", 2166, (
                "category_all_infantry = { defense = 0.051 breakthrough = 0.03 }",
            )),
            ("reactive_camouflage_textiles", "Ткани с изменяемой окраской", "Colour-changing Camouflage Fabrics", "ADISCORD_equipment_camouflage", 2169, (
                "category_all_infantry = { defense = 0.055 supply_consumption = -0.016 }",
            )),
            ("adaptive_camouflage", "Адаптивная маскировка", "Adaptive Camouflage", "ADISCORD_equipment_camouflage", 2170, (
                "category_all_infantry = { default_morale = 0.056 defense = 0.032 }",
            )),
            ("exosuit_joint_actuators", "Приводы суставов экзоскелета", "Exoskeleton Joint Actuators", "ADISCORD_equipment_exoskeleton", 2171, (
                "category_all_infantry = { defense = 0.058 reliability = 0.033 }",
            )),
            ("adaptive_radiation_shielding", "Адаптивная защита от радиации", "Adaptive Radiation Protection", "ADISCORD_equipment_armour", 2173, (
                "category_all_infantry = { defense = 0.06 supply_consumption = -0.017 }",
            )),
            ("closed_loop_combat_life_support", "Замкнутое жизнеобеспечение", "Closed-loop Life Support", "ADISCORD_equipment_life_support", 2174, (
                "category_all_infantry = { defense = 0.061 max_organisation = 1.394 }",
            )),
            ("self_sealing_combat_skins", "Самогерметизирующиеся защитные костюмы", "Self-Sealing Combat Skins", "ADISCORD_equipment_armour", 2175, (
                "category_all_infantry = { defense = 0.063 max_organisation = 1.432 }",
            )),
        ),
    ),
    research_branch(
        "special_forces", "ADISCORD_infantry.txt", ("infantry_folder",),
        "Разведка и спецназ", "Reconnaissance and Special Forces", "special_forces",
        (
            ("fieldcraft_manuals", "Полевая подготовка разведчиков", "Scout Fieldcraft Training", "ADISCORD_equipment_climbing", 2150, (
                "category_special_forces = { breakthrough = 0.04 maximum_speed = 0.012 }",
            )),
            ("urban_breaching", "Инструменты штурмового вскрытия", "Assault Breaching Tools", "ADISCORD_equipment_breaching", 2155, (
                "category_special_forces = { soft_attack = 0.041 breakthrough = 0.041 }",
            )),
            ("radiation_patrols", "Разведка заражённой местности", "Contaminated-area Reconnaissance", "ADISCORD_equipment_respirator", 2158, (
                "category_recon = { recon = 0.35 }",
                "category_special_forces = { maximum_speed = 0.013 }",
            )),
            ("subterranean_route_reconnaissance", "Разведка подземных маршрутов", "Subterranean Route Reconnaissance", "ADISCORD_equipment_climbing", 2160, (
                "category_special_forces = { breakthrough = 0.044 defense = 0.026 }",
            )),
            ("combat_recon_drones", "Разведывательные дроны", "Combat Recon Drones", "ADISCORD_equipment_drone", 2161, (
                "category_recon = { recon = 0.34 }",
                "land_night_attack = 0.013",
            )),
            ("urban_vertical_access_rigs", "Штурмовое альпинистское снаряжение", "Urban Vertical-Access Rigs", "ADISCORD_equipment_climbing", 2162, (
                "category_special_forces = { soft_attack = 0.046 breakthrough = 0.046 }",
            )),
            ("low_observable_infiltration_suits", "Маскировочные костюмы разведчиков", "Reconnaissance Concealment Suits", "ADISCORD_equipment_camouflage", 2163, (
                "category_recon = { recon = 0.43 }",
                "category_special_forces = { maximum_speed = 0.014 }",
            )),
            ("autonomous_scout_microdrones", "Автономные разведывательные микродроны", "Autonomous Scout Microdrones", "ADISCORD_equipment_drone", 2164, (
                "category_recon = { recon = 0.47 }",
                "category_special_forces = { maximum_speed = 0.014 }",
            )),
            ("vertical_assault_training", "Высотная штурмовая подготовка", "Vertical Assault Training", "ADISCORD_equipment_climbing", 2166, (
                "category_special_forces = { maximum_speed = 0.03 supply_consumption = -0.015 }",
            )),
            ("multispectral_concealment_discipline", "Маскировка от разведдатчиков", "Concealment from Reconnaissance Sensors", "ADISCORD_equipment_camouflage", 2168, (
                "category_recon = { recon = 0.55 }",
                "category_special_forces = { maximum_speed = 0.015 }",
            )),
            ("deep_recon_cells", "Группы дальней разведки", "Long-range Reconnaissance Teams", "ADISCORD_night_04_squad_target_sharing", 2170, (
                "category_recon = { recon = 0.59 }",
                "category_special_forces = { maximum_speed = 0.016 }",
            )),
            ("distributed_recon_sensor_caches", "Скрытые посты наблюдения", "Concealed Sensor Outposts", "ADISCORD_night_05_counter_illumination", 2172, (
                "category_recon = { recon = 0.67 }",
                "category_special_forces = { maximum_speed = 0.017 }",
            )),
            ("augmented_special_forces", "Экзоскелеты спецназа", "Special Forces Exoskeletons", "ADISCORD_equipment_exoskeleton", 2180, (
                "category_special_forces = { breakthrough = 0.093 defense = 0.093 max_organisation = 2.131 }",
            )),
        ),
    ),
    research_branch(
        "combat_medicine", "ADISCORD_logistics_trains.txt", ('support_folder',),
        "Боевая медицина", "Combat Medicine", "protection",
        (
            ("casualty_evacuation", "Эвакуация раненых", "Casualty Evacuation", "advanced_machine_tools", 2158, (
                "field_hospital = { casualty_trickleback = 0.03 experience_loss_factor = -0.02 }",
            )),
            ("battlefield_medical_drones", "Медицинские дроны", "Battlefield Medical Drones", "ADISCORD_equipment_medical_drone", 2161, (
                "field_hospital = { casualty_trickleback = 0.045 experience_loss_factor = -0.027 }",
            )),
            ("trauma_registry_networks", "Полевой учёт ранений", "Field Casualty Records", "ADISCORD_equipment_casualty_monitor", 2162, (
                "field_hospital = { casualty_trickleback = 0.03 experience_loss_factor = -0.02 }",
                "category_all_infantry = { default_morale = 0.02 }",
            )),
            ("smart_tourniquet_systems", "Автоматические кровоостанавливающие жгуты", "Smart Tourniquet Systems", "ADISCORD_equipment_medical", 2167, (
                "field_hospital = { casualty_trickleback = 0.03 experience_loss_factor = -0.053 }",
                "category_all_infantry = { default_morale = 0.03 }",
            )),
            ("forward_surgical_cells", "Передовые хирургические группы", "Forward Surgical Teams", "ADISCORD_equipment_medical", 2169, (
                "field_hospital = { experience_loss_factor = -0.04 casualty_trickleback = 0.03 }",
                "category_all_infantry = { max_organisation = 1 }",
            )),
            ("nanofiber_wound_dressings", "Повязки из нановолокна", "Nanofibre Wound Dressings", "ADISCORD_equipment_medical", 2172, (
                "field_hospital = { casualty_trickleback = 0.059 experience_loss_factor = -0.033 }",
            )),
            ("distributed_combat_medicine", "Сеть полевой медицинской помощи", "Field Medical Care Network", "ADISCORD_equipment_medical", 2175, (
                "field_hospital = { casualty_trickleback = 0.08 experience_loss_factor = -0.05 supply_consumption = -0.04 }",
                "category_all_infantry = { default_morale = 0.04 }",
            )),
        ),
    ),
    research_branch(
        "field_support", "ADISCORD_logistics_trains.txt", ('support_folder',),
        "Полевое обеспечение", "Field Support", "support",
        (
            ("field_workshop_tools", "Инструменты полевых мастерских", "Field Workshop Tools", "support_equipment_1", 2150, (
                "category_support_battalions = { reliability = 0.02 defense = 0.02 }",
            )),
            ("modular_support_kits", "Модульные комплекты обеспечения", "Modular Support Kits", "basic_construction", 2155, (
                "category_support_battalions = { reliability = 0.02 supply_consumption = -0.02 }",
            )),
            ("combat_engineering_sections", "Инженерно-штурмовые отделения", "Combat Engineering Sections", "improved_machine_tools", 2158, (
                "engineer = { entrenchment = 0.5 defense = 0.04 }",
                "ADISCORD_regimental_pioneers = { entrenchment = 0.15 defense = 0.02 }",
            )),
            ("standardized_field_tool_chests", "Стандартные наборы полевого инструмента", "Standardized Field Tool Chests", "radio", 2160, (
                "maintenance_company = { equipment_capture_factor = 0.02 }",
                "category_support_battalions = { reliability = 0.03 }",
            )),
            ("drone_delivered_repair_spares", "Доставка ремкомплектов дронами", "Drone-Delivered Repair Spares", "support_equipment_1", 2165, (
                "category_support_battalions = { reliability = 0.04 default_morale = 0.03 }",
            )),
            ("remote_repair_teams", "Дистанционные ремонтные группы", "Remote Repair Teams", "basic_construction", 2166, (
                "maintenance_company = { equipment_capture_factor = 0.03 }",
                "category_support_battalions = { reliability = 0.04 }",
            )),
            ("autonomous_recovery", "Автономная эвакуация техники", "Autonomous Recovery", "improved_construction", 2170, (
                "category_support_battalions = { reliability = 0.04 default_morale = 0.04 }",
            )),
            ("predictive_parts_prepositioning", "Предиктивное размещение запчастей", "Predictive Parts Prepositioning", "support_equipment_1", 2173, (
                "category_support_battalions = { reliability = 0.05 supply_consumption = -0.03 }",
            )),
            ("self_sustaining_support", "Самодостаточное обеспечение", "Self-sustaining Support", "support_equipment_1", 2180, (
                "category_support_battalions = { defense = 0.093 default_morale = 0.052 max_organisation = 2.131 }",
            )),
        ),
    ),
    research_branch(
        "logistics", "ADISCORD_logistics_trains.txt", ('support_folder',),
        "Моторизация и логистика", "Motorization and Logistics", "logistics",
        (
            ("pack_transport", "Вьючный транспорт", "Pack Transport", "radio", 2150, (
                "supply_consumption_factor = -0.012",
                "land_reinforce_rate = 0.006",
            )),
            ("restored_truck_fleets", "Восстановленные автоколонны", "Restored Truck Fleets", "motorised_infantry", 2155, (
                "supply_consumption_factor = -0.012",
                "land_reinforce_rate = 0.006",
            )),
            ("standardized_transport_columns", "Стандартные транспортные колонны", "Standardized Transport Columns", "computing_machine", 2158, (
                "supply_consumption_factor = -0.013",
                "land_reinforce_rate = 0.006",
            )),
            ("forward_supply_hubs", "Передовые узлы снабжения", "Forward Supply Hubs", "improved_computing_machine", 2161, (
                "supply_consumption_factor = -0.013",
                "land_reinforce_rate = 0.007",
            )),
            ("hardened_logistics_nodes", "Защищённые логистические узлы", "Hardened Logistics Nodes", "train_equipment_3", 2166, (
                "logistics_company = { supply_consumption = -0.026 }",
                "industry_repair_factor = 0.015",
            )),
            ("drone_resupply_corridors", "Коридоры снабжения дронами", "Drone Resupply Corridors", "computing_machine", 2167, (
                "logistics_company = { supply_consumption = -0.015 }",
                "coordination_bonus = 0.026",
            )),
            ("route_optimization_ai", "ИИ маршрутизации", "Route Optimization AI", "improved_construction", 2170, (
                "supply_consumption_factor = -0.028",
                "category_support_battalions = { default_morale = 0.016 }",
            )),
            ("closed_loop_field_supply", "Замкнутый цикл полевого снабжения", "Closed-Loop Field Supply", "computing_machine", 2175, (
                "land_reinforce_rate = 0.031",
                "org_loss_when_moving = -0.018",
            )),
            ("zero_loss_logistics", "Безотходная логистика", "Zero-loss Logistics", "assembly_line_production", 2180, (
                "supply_consumption_factor = -0.046",
                "land_reinforce_rate = 0.026",
                "org_loss_when_moving = -0.026",
            )),
        ),
    ),
    research_branch(
        "rail", "ADISCORD_logistics_trains.txt", ('support_folder',),
        "Железные дороги", "Railway Systems", "rail",
        (
            ("restored_rail_stock", "Восстановленная тяга", "Restored Rail Stock", "train_equipment_1", 2150, (
                "supply_consumption_factor = -0.006",
                "industry_repair_factor = 0.02",
            )),
            ("standard_gauge_recovery", "Восстановление единой колеи", "Standard Gauge Recovery", "basic_construction", 2155, (
                "supply_consumption_factor = -0.006",
                "industry_repair_factor = 0.021",
            )),
            ("armored_rail_convoys", "Бронированные эшелоны", "Armored Rail Convoys", "train_equipment_2", 2158, (
                "supply_consumption_factor = -0.006",
                "industry_repair_factor = 0.021",
            )),
            ("rail_repair_corps", "Корпуса ремонта путей", "Rail Repair Corps", "advanced_computing_machine", 2166, (
                "production_speed_infrastructure_factor = 0.015",
                "industry_repair_factor = 0.026",
            )),
            ("autonomous_rail_dispatch", "Автономная диспетчеризация", "Autonomous Rail Dispatch", "train_equipment_3", 2170, (
                "supply_consumption_factor = -0.02",
                "land_reinforce_rate = 0.01",
            )),
            ("smart_railbed_repair_swarms", "Рои ремонта железнодорожного полотна", "Smart Railbed Repair Swarms", "advanced_machine_tools", 2173, (
                "production_speed_infrastructure_factor = 0.017",
                "industry_repair_factor = 0.03",
            )),
        ),
    ),
    research_branch(
        "combat_engineering", "ADISCORD_logistics_trains.txt", ('support_folder',),
        "Инженерное обеспечение", "Combat Engineering", "support",
        (
            ("battle_damage_survey_teams", "Группы оценки боевых повреждений", "Battle-damage Survey Teams", "basic_machine_tools", 2162, (
                "industry_repair_factor = 0.03",
                "category_support_battalions = { defense = 0.02 }",
            )),
            ("assault_breaching_packages", "Штурмовые комплекты разграждения", "Assault Breaching Packages", "basic_construction", 2169, (
                "engineer = { breakthrough = 0.05 soft_attack = 0.03 }",
                "ADISCORD_regimental_pioneers = { breakthrough = 0.03 soft_attack = 0.02 }",
                "planning_speed = 0.02",
            )),
            ("integrated_engineer_command", "Единое инженерное командование", "Integrated Engineer Command", "improved_machine_tools", 2175, (
                "engineer = { breakthrough = 0.10 defense = 0.08 }",
                "ADISCORD_regimental_pioneers = { breakthrough = 0.05 defense = 0.04 }",
                "category_support_battalions = { max_organisation = 2 }",
                "planning_speed = 0.04",
            )),
        ),
    ),
    research_branch(
        "officer_training", "ADISCORD_logistics_trains.txt", ('support_folder',),
        "Подготовка командного состава", "Officer Training", "support",
        (
            ("reconstituted_staff_academies", "Восстановленные штабные академии", "Reconstituted Staff Academies", "radio", 2162, (
                "planning_speed = 0.02",
                "land_reinforce_rate = 0.005",
                "max_command_power_mult = 0.02",
            )),
            ("assault_command_curriculum", "Курс наступательного командования", "Assault Command Curriculum", "mechanical_computing", 2164, (
                "planning_speed = 0.03",
                "category_all_infantry = { breakthrough = 0.02 }",
            )),
            ("defensive_command_curriculum", "Курс оборонительного командования", "Defensive Command Curriculum", "basic_encryption", 2165, (
                "dig_in_speed_factor = 0.03",
                "category_all_infantry = { defense = 0.02 }",
            )),
            ("operational_planning_exercises", "Оперативные штабные учения", "Operational Planning Exercises", "computing_machine", 2167, (
                "planning_speed = 0.04",
                "max_planning = 0.02",
                "coordination_bonus = 0.01",
            )),
            ("theater_logistics_wargames", "Тыловые манёвры театра", "Theater Logistics Wargames", "improved_encryption", 2169, (
                "supply_consumption_factor = -0.015",
                "land_reinforce_rate = 0.01",
                "org_loss_when_moving = -0.01",
            )),
            ("rotational_front_commands", "Ротация фронтовых командований", "Rotational Front Commands", "improved_computing_machine", 2171, (
                "planning_speed = 0.04",
                "land_reinforce_rate = 0.015",
                "max_command_power_mult = 0.03",
            )),
            ("predictive_staff_colleges", "Коллегии предиктивного планирования", "Predictive Staff Colleges", "advanced_encryption", 2173, (
                "coordination_bonus = 0.02",
                "supply_consumption_factor = -0.02",
                "max_planning = 0.02",
            )),
            ("adaptive_general_staff", "Адаптивный генеральный штаб", "Adaptive General Staff", "advanced_computing_machine", 2175, (
                "planning_speed = 0.06",
                "coordination_bonus = 0.03",
                "land_reinforce_rate = 0.02",
                "max_command_power_mult = 0.05",
            )),
        ),
    ),
    research_branch(
        "artillery", "ADISCORD_artillery.txt", ('artillery_folder',),
        "Полевая артиллерия", "Field Artillery", "artillery",
        (
            ("restored_field_artillery", "Восстановленная артиллерия", "Restored Field Artillery", "artillery_equipment", 2150, (
                "artillery = { soft_attack = 0.04 reliability = 0.012 }",
            )),
            ("recoil_recovery", "Восстановление противооткатных систем", "Recoil Recovery", "artillery2", 2155, (
                "artillery = { soft_attack = 0.041 reliability = 0.012 }",
            )),
            ("modular_gun_carriages", "Модульные лафеты", "Modular Gun Carriages", "artillery3", 2158, (
                "artillery = { soft_attack = 0.043 reliability = 0.013 }",
            )),
            ("electrohydraulic_gun_laying", "Электрогидравлическое наведение орудий", "Electrohydraulic Gun Laying", "artillery1", 2160, (
                "artillery = { soft_attack = 0.044 reliability = 0.013 }",
            )),
            ("smart_fire_control", "Умное управление огнём", "Smart Fire Control", "artillery4", 2161, (
                "artillery = { soft_attack = 0.045 reliability = 0.013 }",
            )),
            ("counterbattery_radar_links", "Каналы контрбатарейных РЛС", "Counter-battery Radar Links", "artillery3", 2163, (
                "artillery = { hard_attack = 0.048 ap_attack = 0.048 }",
            )),
            ("assisted_projectiles", "Корректируемые снаряды", "Assisted Projectiles", "artillery_equipment", 2166, (
                "artillery = { soft_attack = 0.051 reliability = 0.03 }",
            )),
            ("drone_spotted_batteries", "Дроновая корректировка", "Drone-spotted Batteries", "rocket_artillery_equipment", 2170, (
                "artillery = { hard_attack = 0.056 reliability = 0.032 }",
            )),
            ("uncrewed_howitzer_sections", "Необитаемые гаубичные расчёты", "Uncrewed Howitzer Sections", "rocket_artillery4", 2175, (
                "artillery = { soft_attack = 0.063 reliability = 0.018 }",
            )),
            ("autonomous_battery_network", "Автономная батарейная сеть", "Autonomous Battery Network", "rocket_artillery4", 2180, (
                "artillery = { reliability = 0.08 defense = 0.06 }",
                "coordination_bonus = 0.02",
            )),
        ),
    ),
    research_branch(
        "railway_artillery", "ADISCORD_artillery.txt", ('artillery_folder',),
        "Железнодорожная артиллерия", "Railway Artillery", "rail",
        (
            ("railway_gun_reactivation", "Реактивация железнодорожных орудий", "Railway Gun Reactivation", "generic_railway_gun", 2161, (
                "railway_gun = { reliability = 0.03 }",
            )),
            ("recoil_braced_firing_sidings", "Огневые тупики с компенсацией отдачи", "Recoil-Braced Firing Sidings", "advanced_machine_tools", 2163, (
                "railway_gun = { railway_gun_attack = 0.05 reliability = 0.02 }",
            )),
            ("active_suspension_gun_carriages", "Орудийные платформы с активной подвеской", "Active-Suspension Gun Carriages", "improved_construction", 2172, (
                "railway_gun = { maximum_speed = 0.05 reliability = 0.04 }",
            )),
            ("over_the_horizon_fire_control", "Загоризонтный огонь", "Over-the-horizon Fire Control", "generic_super_heavy_railway_gun", 2180, (
                "railway_gun = { railway_gun_attack = 0.08 reliability = 0.04 }",
            )),
        ),
    ),
    research_branch(
        "anti_tank", "ADISCORD_artillery.txt", ('artillery_folder',),
        "Противотанковые системы", "Anti-tank Systems", "anti_tank",
        (
            ("salvaged_at_guns", "Трофейные противотанковые орудия", "Salvaged Anti-tank Guns", "antitank1", 2150, (
                "category_anti_tank = { hard_attack = 0.04 ap_attack = 0.04 }",
            )),
            ("shaped_charges", "Кумулятивные заряды", "Shaped Charges", "antitank2", 2155, (
                "category_anti_tank = { hard_attack = 0.041 ap_attack = 0.041 }",
            )),
            ("tandem_warheads", "Тандемные боевые части", "Tandem Warheads", "antitank3", 2158, (
                "category_anti_tank = { hard_attack = 0.043 ap_attack = 0.043 }",
            )),
            ("scrap_at_launchers", "Кустарные противотанковые орудия", "Scrap Anti-tank Launchers", "anti_tank_equipment", 2161, (
                "category_anti_tank = { hard_attack = 0.045 ap_attack = 0.045 }",
            )),
            ("imaging_infrared_seekers", "Матричные инфракрасные головки наведения", "Imaging Infrared Seekers", "antitank3", 2163, (
                "category_anti_tank = { reliability = 0.048 defense = 0.028 }",
            )),
            ("top_attack_munitions", "Боеприпасы верхней атаки", "Top-attack Munitions", "antitank5", 2166, (
                "category_anti_tank = { hard_attack = 0.051 ap_attack = 0.051 }",
            )),
            ("coil_at_systems", "Катушечные ускорители ПТО", "Coil Anti-tank Systems", "antitank2", 2170, (
                "category_anti_tank = { ap_attack = 0.056 breakthrough = 0.032 }",
            )),
            ("superconducting_coil_barrels", "Сверхпроводящие катушечные стволы", "Superconducting Coil Barrels", "anti_tank_equipment", 2171, (
                "category_anti_tank = { hard_attack = 0.058 defense = 0.033 }",
            )),
            ("hypervelocity_at_networks", "Сеть гиперскоростной ПТО", "Hypervelocity Anti-tank Networks", "antitank2", 2180, (
                "category_anti_tank = { hard_attack = 0.093 ap_attack = 0.093 reliability = 0.052 }",
            )),
        ),
    ),
    research_branch(
        "anti_air", "ADISCORD_artillery.txt", ('artillery_folder',),
        "Противовоздушная оборона", "Air Defense", "anti_air",
        (
            ("improvised_air_defense", "Импровизированная ПВО", "Improvised Air Defense", "antiair1", 2150, (
                "category_anti_air = { air_attack = 0.04 reliability = 0.012 }",
            )),
            ("radar_laying", "Радиолокационное наведение", "Radar Laying", "antiair2", 2155, (
                "category_anti_air = { air_attack = 0.041 reliability = 0.012 }",
            )),
            ("proximity_fuzes", "Радиовзрыватели", "Proximity Fuzes", "antiair3", 2158, (
                "category_anti_air = { air_attack = 0.043 reliability = 0.013 }",
            )),
            ("stabilized_autocannon_mounts", "Стабилизированные зенитные автопушки", "Stabilized Autocannon Mounts", "antiair1", 2160, (
                "category_anti_air = { air_attack = 0.044 reliability = 0.013 }",
            )),
            ("point_defense_aa", "Автопушки точечной обороны", "Point-defense Air Defense", "anti_air_equipment", 2161, (
                "category_anti_air = { air_attack = 0.045 reliability = 0.013 }",
            )),
            ("integrated_short_range_missile_cells", "Интегрированные ячейки ракет ближнего действия", "Integrated Short-range Missile Cells", "antiair5", 2165, (
                "category_anti_air = { air_attack = 0.05 reliability = 0.029 }",
                "air_intercept_efficiency = 0.029",
            )),
            ("networked_air_defense", "Сетевая противовоздушная оборона", "Networked Air Defense", "antiair5", 2166, (
                "category_anti_air = { air_attack = 0.03 reliability = 0.051 }",
                "coordination_bonus = 0.015",
            )),
            ("high_energy_laser_turrets", "Турели высокоэнергетических лазеров", "High-energy Laser Turrets", "anti_air_equipment", 2173, (
                "category_anti_air = { air_attack = 0.06 reliability = 0.034 }",
                "air_intercept_efficiency = 0.034",
            )),
            ("predictive_airspace_denial_grid", "Предиктивная сеть блокирования воздушного пространства", "Predictive Airspace-denial Grid", "sp_nuclear_isotope_separation", 2175, (
                "category_anti_air = { air_attack = 0.063 reliability = 0.018 }",
            )),
            ("directed_energy_air_defense", "Энергетическая противовоздушная оборона", "Directed-energy Air Defense", "advanced_centimetric_radar", 2180, (
                "category_anti_air = { air_attack = 0.093 reliability = 0.093 }",
                "air_intercept_efficiency = 0.052",
            )),
        ),
    ),
    research_branch(
        "recon_armor", "ADISCORD_armor.txt", ('armour_folder', 'nsb_armour_folder'),
        "Разведывательная бронетехника", "Reconnaissance Armor", "recon_armor",
        (
            ("restored_armored_chassis", "Восстановленное лёгкое шасси", "Restored Armored Chassis", "nsb_engine_tech_1", 2150, (
                "category_all_armor = { maximum_speed = 0.024 reliability = 0.024 }",
            )),
            ("light_suspension", "Облегчённая подвеска", "Light Suspension", "nsb_armor_tech_1", 2155, (
                "category_all_armor = { maximum_speed = 0.025 reliability = 0.025 }",
            )),
            ("modular_recon_chassis", "Модульное разведывательное шасси", "Modular Recon Chassis", "basic_machine_tools", 2158, (
                "category_all_armor = { maximum_speed = 0.025 reliability = 0.025 }",
            )),
            ("sealed_electric_scout_drives", "Герметичные электроприводы разведмашин", "Sealed Electric Scout Drives", "radio", 2160, (
                "category_all_armor = { maximum_speed = 0.026 reliability = 0.026 }",
            )),
            ("drone_recon_swarms", "Программа Р-63 «След»", "R-63 “Trace” Programme", "advanced_light_tank", 2161, (
                "category_all_armor = { maximum_speed = 0.027 reliability = 0.027 }",
            )),
            ("multispectral_recon_suites", "Мультиспектральные разведывательные комплексы", "Multispectral Reconnaissance Suites", "improved_machine_tools", 2164, (
                "category_all_armor = { reliability = 0.028 defense = 0.049 }",
                "category_recon = { recon = 0.4 }",
            )),
            ("signature_management_skins", "Обшивка управления сигнатурой", "Signature-management Skins", "basic_light_tank", 2169, (
                "category_all_armor = { defense = 0.055 breakthrough = 0.032 }",
            )),
            ("unmanned_recon_vehicles", "Необитаемые разведмашины", "Unmanned Recon Vehicles", "ger_armored_car_equipment_1", 2170, (
                "category_all_armor = { maximum_speed = 0.032 breakthrough = 0.056 }",
            )),
            ("autonomous_recon_screen", "Автономное разведывательное охранение", "Autonomous Recon Screen", "advanced_centimetric_radar", 2180, (
                "category_all_armor = { maximum_speed = 0.052 reliability = 0.093 defense = 0.093 }",
            )),
        ),
    ),
    research_branch(
        "mechanized_mobility", "ADISCORD_armor.txt", ('armour_folder', 'nsb_armour_folder'),
        "Механизированные войска", "Mechanized Forces", "recon_armor",
        (
            ("armored_carrier_program", "Программа М-63 «Ковчег»", "M-63 “Ark” Programme", "mechanized_equipment_1", 2160, (
                "ADISCORD_mechanized_infantry = { defense = 0.03 reliability = 0.03 }",
            )),
            ("protected_transport_standards", "Стандарты защищённой перевозки", "Protected Transport Standards", "nsb_armor_tech_1", 2162, (
                "category_all_armor = { maximum_speed = 0.025 reliability = 0.025 }",
            )),
            ("sealed_dismount_compartments", "Герметичные десантные отсеки", "Sealed Dismount Compartments", "nsb_armor_tech_1", 2164, (
                "category_all_armor = { maximum_speed = 0.026 reliability = 0.026 }",
            )),
            ("escort_protection_arrays", "Комплексы защиты машин сопровождения", "Escort Protection Arrays", "nsb_armor_tech_2", 2166, (
                "category_all_armor = { maximum_speed = 0.027 reliability = 0.027 }",
            )),
            ("infantry_combat_vehicle_program", "Контур М-70 «Рубеж»", "M-70 “Rampart” Combat Loop", "mechanized_equipment_2", 2168, (
                "ADISCORD_mechanized_infantry = { breakthrough = 0.05 soft_attack = 0.05 hard_attack = 0.03 }",
            )),
            ("unmanned_weapon_stations", "Необитаемые башенные установки", "Uncrewed Turret Mounts", "nsb_engine_tech_1", 2170, (
                "category_all_armor = { maximum_speed = 0.031 reliability = 0.031 }",
            )),
            ("cooperative_dismount_control", "Совместное управление спешиванием", "Cooperative Dismount Control", "improved_computing_machine", 2172, (
                "category_all_armor = { maximum_speed = 0.034 reliability = 0.034 }",
            )),
            ("networked_mechanized_cells", "Контур М-83 «Свод»", "M-83 “Vault” Mechanized Loop", "mechanized_equipment_3", 2175, (
                "ADISCORD_mechanized_infantry = { maximum_speed = 0.05 reliability = 0.05 }",
                "coordination_bonus = 0.02",
            )),
        ),
    ),
    research_branch(
        "combat_armor", "ADISCORD_armor.txt", ('armour_folder', 'nsb_armour_folder'),
        "Основные боевые танки", "Main Battle Tanks", "combat_armor",
        (
            ("recovered_medium_chassis", "Восстановленный основной боевой танк", "Restored Main Battle Tank", "nsb_armor_tech_1", 2150, (
                "category_all_armor = { breakthrough = 0.04 hard_attack = 0.024 }",
            )),
            ("remote_weapon_stations", "Дистанционно управляемые башенные установки", "Remote-controlled Turret Mounts", "nsb_engine_tech_1", 2155, (
                "category_all_armor = { breakthrough = 0.041 hard_attack = 0.025 }",
            )),
            ("composite_armor_arrays", "Массивы композитной брони", "Composite Armor Arrays", "basic_machine_tools", 2158, (
                "category_all_armor = { breakthrough = 0.043 hard_attack = 0.025 }",
            )),
            ("electric_turret_drives", "Электрические приводы башни", "Electric Turret Drives", "nsb_engine_tech_2", 2161, (
                "category_all_armor = { breakthrough = 0.045 hard_attack = 0.027 }",
            )),
            ("semi_autonomous_combat_modules", "Контур БТ-62 «Вожак»", "BT-62 “Lead” Control Loop", "generic_modern_tank", 2162, (
                "category_all_armor = { breakthrough = 0.046 hard_attack = 0.046 }",
            )),
            ("hard_kill_protection_arrays", "Комплексы активной защиты жёсткого поражения", "Hard-kill Protection Arrays", "nsb_engine_tech_3", 2164, (
                "category_all_armor = { soft_attack = 0.049 maximum_speed = 0.028 }",
            )),
            ("adaptive_fire_control", "Адаптивное управление огнём", "Adaptive Fire Control", "nsb_armor_tech_4", 2166, (
                "category_all_armor = { hard_attack = 0.051 reliability = 0.03 }",
            )),
            ("multispectral_gunner_sights", "Мультиспектральные прицелы наводчика", "Multispectral Gunner Sights", "nsb_engine_tech_4", 2167, (
                "category_all_armor = { armor_value = 0.053 default_morale = 0.03 }",
            )),
            ("limited_battle_ai", "Ограниченный боевой ИИ", "Limited Battle AI", "generic_modern_tank", 2172, (
                "category_all_armor = { hard_attack = 0.059 reliability = 0.033 }",
            )),
            ("electromagnetic_main_guns", "Электромагнитные основные орудия", "Electromagnetic Main Guns", "nsb_engine_tech_2", 2173, (
                "category_all_armor = { hard_attack = 0.06 breakthrough = 0.05 }",
            )),
            ("adaptive_suspension_control", "Адаптивное управление подвеской", "Adaptive Suspension Control", "advanced_medium_tank", 2175, (
                "category_all_armor = { maximum_speed = 0.05 reliability = 0.05 }",
            )),
            ("distributed_battlegroup", "Распределённая бронегруппа", "Distributed Battlegroup", "generic_modern_tank", 2180, (
                "category_all_armor = { hard_attack = 0.09 breakthrough = 0.08 }",
                "coordination_bonus = 0.02",
            )),
        ),
    ),
    research_branch(
        "heavy_armor", "ADISCORD_armor.txt", ('armour_folder', 'nsb_armour_folder'),
        "Тяжёлые и автономные танки", "Heavy and Autonomous Tanks", "heavy_armor",
        (
            ("heavy_recovery_frames", "Тяжёлые ремонтные рамы", "Heavy Recovery Frames", "nsb_armor_tech_1", 2150, (
                "ADISCORD_heavy_platform = { armor_value = 0.04 defense = 0.024 }",
            )),
            ("reinforced_powertrains", "Усиленные силовые установки", "Reinforced Powertrains", "nsb_engine_tech_1", 2155, (
                "ADISCORD_heavy_platform = { armor_value = 0.041 defense = 0.025 }",
            )),
            ("heavy_composite_cores", "Тяжёлые композитные ядра", "Heavy Composite Cores", "basic_machine_tools", 2158, (
                "ADISCORD_heavy_platform = { armor_value = 0.043 defense = 0.025 }",
            )),
            ("remote_repair_sections", "Дистанционные ремонтные машины", "Remote Repair Sections", "generic_armored_support_vehicle_recovery_1", 2161, (
                "ADISCORD_heavy_platform = { armor_value = 0.045 defense = 0.027 }",
            )),
            ("heavy_platform_cores", "Усиленный корпус тяжёлого танка", "Reinforced Heavy Tank Hull", "super_heavy_tank", 2166, (
                "ADISCORD_heavy_platform = { armor_value = 0.051 reliability = 0.03 }",
            )),
            ("active_mass_balancing_suspension", "Подвеска активного распределения массы", "Active Mass-balancing Suspension", "main_battle_tank", 2167, (
                "ADISCORD_heavy_platform = { maximum_speed = 0.03 reliability = 0.053 }",
            )),
            ("autonomous_breakthrough_platforms", "Программа Т-71 «Таран»", "T-71 “Ram” Programme", "nsb_engine_tech_1", 2170, (
                "ADISCORD_heavy_platform = { breakthrough = 0.056 hard_attack = 0.056 }",
            )),
            ("electromagnetic_siege_mortars", "Электромагнитные осадные мортиры", "Electromagnetic Siege Mortars", "nsb_armor_tech_2", 2172, (
                "ADISCORD_heavy_platform = { soft_attack = 0.059 breakthrough = 0.033 }",
            )),
            ("siege_platform_networks", "Контур Т-80 «Жернов»", "T-80 “Millstone” Siege Loop", "generic_land_cruiser_chassis", 2180, (
                "ADISCORD_heavy_platform = { armor_value = 0.093 breakthrough = 0.093 reliability = 0.052 }",
            )),
        ),
    ),
    research_branch(
        "unmanned_ground_systems", "ADISCORD_armor.txt", ('armour_folder', 'nsb_armour_folder'),
        "Беспилотные наземные системы", "Unmanned Ground Systems", "recon_armor",
        (
            ("teleoperated_scout_carts", "Телеуправляемые разведывательные машины", "Teleoperated Scout Vehicles", "nsb_engine_tech_1", 2162, (
                "category_recon = { recon = 0.5 defense = 0.02 }",
                "category_all_armor = { reliability = 0.02 }",
            )),
            ("armed_recon_drones", "Вооружённые разведывательные платформы", "Armed Recon Vehicles", "sp_armored_signal", 2169, (
                "category_recon = { recon = 0.75 soft_attack = 0.04 }",
                "category_all_armor = { maximum_speed = 0.02 }",
            )),
            ("distributed_ground_swarm_control", "Распределённое управление наземным роем", "Distributed Ground-swarm Control", "sp_armored_signal", 2175, (
                "category_all_armor = { breakthrough = 0.06 soft_attack = 0.05 }",
                "coordination_bonus = 0.015",
            )),
        ),
    ),
    research_branch(
        "fighter", "ADISCORD_air.txt", ('air_techs_folder', 'bba_air_techs_folder'),
        "Истребительная авиация", "Fighter Aviation", "fighter",
        (
            ("reclaimed_jet_platforms", "Программа А-50 «Искра»", "A-50 “Spark” Programme", "early_fighter", 2150, (
                "air_mission_efficiency = 0.024",
                "air_accidents_factor = -0.024",
            )),
            ("standardized_airframes", "Стандартные планеры", "Standardized Airframes", "bba_tech_engines_1", 2155, (
                "air_mission_efficiency = 0.025",
                "air_accidents_factor = -0.025",
            )),
            ("pulse_doppler_radar", "Импульсно-доплеровская РЛС", "Pulse-Doppler Radar", "centimetric_radar", 2158, (
                "air_mission_efficiency = 0.025",
                "air_accidents_factor = -0.025",
            )),
            ("composite_wing_spars", "Композитные лонжероны крыла", "Composite Wing Spars", "bba_tech_aircraft_construction", 2160, (
                "air_mission_efficiency = 0.026",
                "air_accidents_factor = -0.026",
            )),
            ("high_altitude_interceptors", "Высотные перехватчики", "High-altitude Interceptors", "fighter2", 2161, (
                "air_mission_efficiency = 0.027",
                "air_accidents_factor = -0.027",
            )),
            ("electronically_scanned_fighter_radar", "РЛС истребителя с электронным сканированием", "Electronically Scanned Fighter Radar", "bba_tech_aircraft_construction", 2163, (
                "fighter = { air_attack = 0.06 air_defence = 0.04 }",
            )),
            ("thrust_vectoring", "Управляемый вектор тяги", "Thrust Vectoring", "jet_fighter1", 2166, (
                "air_agility_factor = 0.051",
                "air_accidents_factor = -0.03",
            )),
            ("low_observable_inlet_geometry", "Малозаметная геометрия воздухозаборников", "Low-observable Inlet Geometry", "fighter2", 2168, (
                "air_mission_efficiency = 0.031",
                "air_accidents_factor = -0.031",
            )),
            ("loyal_wingmen", "Ведомые беспилотники", "Loyal Wingmen", "jet_fighter2", 2170, (
                "air_attack_factor = 0.056",
                "air_mission_efficiency = 0.032",
            )),
            ("autonomous_dogfight_controller", "Автономный контроллер воздушного боя", "Autonomous Dogfight Controller", "bba_tech_engines_1", 2173, (
                "air_intercept_efficiency = 0.05",
                "air_accidents_factor = -0.03",
            )),
            ("distributed_interceptor_swarms", "Распределённые рои перехватчиков", "Distributed Interceptor Swarms", "jet_fighter2", 2175, (
                "air_mission_efficiency = 0.08",
                "air_power_projection_factor = 0.05",
            )),
            ("aerospace_interceptors", "Воздушно-космические перехватчики", "Aerospace Interceptors", "bba_tech_engines_1", 2180, (
                "air_intercept_efficiency = 0.08",
                "air_mission_efficiency = 0.04",
            )),
        ),
    ),
    research_branch(
        "bomber_maritime", "ADISCORD_air.txt", ('air_techs_folder', 'bba_air_techs_folder'),
        "Бомбардировщики и морская авиация", "Bombers and Maritime Aircraft", "air_support",
        (
            ("twin_engine_aircraft", "Двухмоторные самолёты", "Twin-engine Aircraft", "tactical_bomber1", 2160, (
                "ADISCORD_tactical_bomber = { reliability = 0.02 }",
            )),
            ("maritime_patrol_aircraft", "Морские патрульные самолёты", "Maritime Patrol Aircraft", "naval_bomber2", 2164, (
                "nav_bomber = { air_range = 0.04 }",
            )),
            ("pressurized_bombers", "Бомбардировщики с гермокабиной", "Pressurized Bombers", "tactical_bomber2", 2164, (
                "ADISCORD_tactical_bomber = { air_defence = 0.04 }",
            )),
            ("airborne_homing_torpedoes", "Самонаводящиеся авиационные торпеды", "Airborne Homing Torpedoes", "bba_tech_armor_piercing_bombs", 2168, (
                "nav_bomber = { naval_strike_attack = 0.10 naval_strike_targetting = 0.08 }",
            )),
            ("stabilized_bomb_sights", "Стабилизированные бомбовые прицелы", "Stabilized Bomb Sights", "bba_tech_engines_1", 2168, (
                "ADISCORD_tactical_bomber = { strategic_attack = 0.08 air_ground_attack = 0.06 }",
            )),
            ("long_range_maritime_aircraft", "Дальние противокорабельные самолёты", "Long-range Maritime Strike Aircraft", "naval_bomber3", 2172, (
                "nav_bomber = { naval_strike_targetting = 0.06 }",
            )),
            ("jet_strike_bombers", "Реактивные ударные бомбардировщики", "Jet Strike Bombers", "jet_tactical_bomber1", 2172, (
                "ADISCORD_tactical_bomber = { strategic_attack = 0.06 }",
            )),
            ("integrated_strike_navigation", "Комплексная прицельно-навигационная система", "Integrated Strike Navigation", "advanced_centimetric_radar", 2175, (
                "ADISCORD_tactical_bomber = { air_range = 0.08 strategic_attack = 0.06 }",
                "nav_bomber = { air_range = 0.08 naval_strike_targetting = 0.06 }",
            )),
        ),
    ),
    research_branch(
        "air_support", "ADISCORD_air.txt", ('air_techs_folder', 'bba_air_techs_folder'),
        "Штурмовая авиация", "Air Support", "air_support",
        (
            ("battlefield_attack_aircraft", "Программа АШ-50 «Коршун»", "AS-50 “Kite” Programme", "CAS1", 2150, (
                "air_mission_efficiency = 0.024",
                "ground_attack_factor = 0.04",
            )),
            ("guided_munitions", "Управляемые боеприпасы", "Guided Munitions", "bba_tech_engines_1", 2155, (
                "cas = { air_ground_attack = 0.08 }",
            )),
            ("armored_cockpits", "Бронированные кабины", "Armored Cockpits", "radio", 2158, (
                "air_mission_efficiency = 0.025",
                "ground_attack_factor = 0.043",
            )),
            ("vtol_assault_frames", "Ударные СВВП", "VTOL Assault Frames", "CAS2", 2161, (
                "air_mission_efficiency = 0.027",
                "ground_attack_factor = 0.045",
            )),
            ("precision_glide_bomb_kits", "Комплекты планирующих высокоточных бомб", "Precision Glide-bomb Kits", "CAS2", 2163, (
                "ground_attack_factor = 0.048",
                "air_accidents_factor = -0.028",
            )),
            ("drone_air_wings", "Контур А-65 «Стая»", "A-65 “Flock” Air-control Loop", "CAS3", 2166, (
                "ground_attack_factor = 0.051",
                "air_mission_efficiency = 0.03",
            )),
            ("loitering_strike_drones", "Барражирующие ударные беспилотники", "Loitering Strike Drones", "radio", 2168, (
                "air_mission_efficiency = 0.031",
                "ground_attack_factor = 0.054",
            )),
            ("cooperative_close_air_control_links", "Каналы совместного управления авиаподдержкой", "Cooperative Close-air-control Links", "bba_tech_armor_piercing_bombs", 2169, (
                "ground_attack_factor = 0.055",
                "air_mission_efficiency = 0.032",
            )),
            ("autonomous_strike_wings", "Автономные ударные крылья", "Autonomous Strike Wings", "CAS3", 2170, (
                "ground_attack_factor = 0.056",
                "air_accidents_factor = -0.032",
            )),
            ("persistent_sensor_strike_loops", "Непрерывные разведывательно-ударные контуры", "Persistent Sensor-strike Loops", "CAS3", 2175, (
                "air_mission_efficiency = 0.035",
                "ground_attack_factor = 0.063",
            )),
            ("persistent_air_support", "Непрерывная воздушная поддержка", "Persistent Air Support", "sp_rockets_improved_guidance", 2180, (
                "ground_attack_factor = 0.093",
                "air_mission_efficiency = 0.093",
                "air_accidents_factor = -0.052",
            )),
        ),
    ),
    research_branch(
        "strategic_air", "ADISCORD_air.txt", ('air_techs_folder', 'bba_air_techs_folder'),
        "Ракетные и стратегические системы", "Rocket and Strategic Systems", "strategic_air",
        (
            ("rocket_test_stands", "Ракетные испытательные стенды", "Rocket Test Stands", "rocket_engines", 2150, (
                "air_mission_efficiency = 0.024",
                "strategic_bomb_visibility = -0.024",
            )),
            ("inertial_guidance", "Инерциальное наведение", "Inertial Guidance", "improved_rocket_engines", 2155, (
                "air_mission_efficiency = 0.025",
                "strategic_bomb_visibility = -0.025",
            )),
            ("cruise_missiles", "Крылатые ракеты", "Cruise Missiles", "centimetric_radar", 2158, (
                "air_mission_efficiency = 0.025",
                "strategic_bomb_visibility = -0.025",
            )),
            ("strategic_rocket_architecture", "Стратегическая ракетная артиллерия", "Strategic Rocket Architecture", "advanced_rocket_engines", 2161, (
                "air_mission_efficiency = 0.027",
                "strategic_bomb_visibility = -0.027",
            )),
            ("orbital_tracking_relics", "Орбитальные комплексы слежения", "Orbital Tracking Relics", "guided_missile_1", 2166, (
                "air_mission_efficiency = 0.03",
                "strategic_bomb_visibility = -0.03",
            )),
            ("hypersonic_glide_vehicles", "Гиперзвуковые планирующие блоки", "Hypersonic Glide Vehicles", "centimetric_radar", 2168, (
                "air_mission_efficiency = 0.031",
                "strategic_bomb_visibility = -0.031",
            )),
            ("deep_strike_targeting", "Координация глубоких ударов", "Deep Strike Targeting", "advanced_rocket_engines", 2170, (
                "air_mission_efficiency = 0.032",
                "strategic_bomb_visibility = -0.032",
            )),
            ("suborbital_skip_glide_guidance", "Наведение суборбитального рикошетирующего полёта", "Suborbital Skip-glide Guidance", "guided_missile_3", 2174, (
                "air_mission_efficiency = 0.035",
                "strategic_bomb_visibility = -0.035",
            )),
            ("suborbital_strike_systems", "Программа Р-80 «Стрела»", "R-80 “Arrow” Programme", "ballistic_missile_equipment_3", 2180, (
                "air_mission_efficiency = 0.052",
                "strategic_bomb_visibility = -0.052",
            )),
        ),
    ),
    research_branch(
        "air_mobility", "ADISCORD_air.txt", ('air_techs_folder', 'bba_air_techs_folder'),
        "Воздушная мобильность", "Air Mobility", "air_support",
        (
            ("restored_airlift_planning", "Восстановленное планирование воздушных перевозок", "Restored Airlift Planning", "radio", 2162, (
                "air_mission_efficiency = 0.02",
                "air_mission_xp_gain_factor = 0.03",
                "supply_consumption_factor = -0.005",
            )),
            ("vertical_envelopment_control", "Управление вертикальным охватом", "Vertical Envelopment Control", "radio", 2169, (
                "air_cas_efficiency = 0.04",
                "planning_speed = 0.03",
                "land_reinforce_rate = 0.005",
            )),
            ("precision_aerial_resupply", "Точное воздушное снабжение", "Precision Aerial Resupply", "bba_tech_armor_piercing_bombs", 2175, (
                "air_mission_efficiency = 0.04",
                "supply_consumption_factor = -0.02",
                "air_accidents_factor = -0.015",
            )),
        ),
    ),
    research_branch(
        "naval_support", "ADISCORD_naval.txt", ('naval_folder', 'mtgnavalsupportfolder'),
        "Прибрежные силы и эскорт", "Littoral Forces and Escort", "naval_support",
        (
            ("restored_dockyards", "Восстановленные верфи", "Restored Dockyards", "sonar", 2150, (
                "convoy_escort_efficiency = 0.04",
                "naval_detection = 0.024",
            )),
            ("coastal_patrols", "Прибрежные патрули", "Coastal Patrols", "basic_torpedo", 2155, (
                "convoy_escort_efficiency = 0.041",
                "naval_detection = 0.025",
            )),
            ("convoy_routing", "Маршрутизация конвоев", "Convoy Routing", "improved_sonar", 2158, (
                "convoy_escort_efficiency = 0.043",
                "naval_detection = 0.025",
            )),
            ("modular_escort_combat_systems", "Модульные боевые системы эскорта", "Modular Escort Combat Systems", "basic_naval_mines", 2160, (
                "convoy_escort_efficiency = 0.044",
                "naval_detection = 0.026",
            )),
            ("variable_depth_sonar", "Гидролокаторы переменной глубины", "Variable-depth Sonar", "advanced_centimetric_radar", 2163, (
                "naval_detection = 0.028",
                "naval_mines_effect_reduction = 0.048",
            )),
            ("unmanned_mine_countermeasure_boats", "Беспилотные противоминные катера", "Unmanned Mine-countermeasure Boats", "basic_torpedo", 2168, (
                "convoy_escort_efficiency = 0.054",
                "naval_detection = 0.031",
            )),
            ("autonomous_escorts", "Автономные корабли эскорта", "Autonomous Escorts", "basic_naval_mines", 2170, (
                "naval_detection = 0.032",
                "naval_mines_effect_reduction = 0.056",
            )),
            ("predictive_convoy_defense_network", "Предиктивная сеть обороны конвоев", "Predictive Convoy-defense Network", "modern_sonar", 2175, (
                "convoy_escort_efficiency = 0.063",
                "naval_detection = 0.035",
            )),
            ("distributed_sea_control", "Распределённый контроль моря", "Distributed Sea Control", "homing_torpedo", 2180, (
                "convoy_escort_efficiency = 0.093",
                "naval_detection = 0.093",
                "naval_coordination = 0.052",
            )),
        ),
    ),
    research_branch(
        "surface_fleet", "ADISCORD_naval.txt", ('naval_folder', 'mtgnavalfolder'),
        "Надводный флот", "Surface Fleet", "surface_fleet",
        (
            ("recovered_fire_control", "Восстановленное управление огнём", "Recovered Fire Control", "basic_cruiser_armor_scheme", 2150, (
                "naval_hit_chance = 0.024",
                "naval_coordination = 0.024",
            )),
            ("modular_hull_standards", "Модульные стандарты корпусов", "Modular Hull Standards", "decimetric_radar", 2155, (
                "naval_hit_chance = 0.025",
                "naval_coordination = 0.025",
            )),
            ("radar_gunnery", "Радиолокационная стрельба", "Radar Gunnery", "improved_cruiser_armor_scheme", 2158, (
                "heavy_cruiser = { hg_attack = 0.06 }",
            )),
            ("missile_batteries", "Корабельные ракетные батареи", "Missile Batteries", "advanced_cruiser_armor_scheme", 2161, (
                "heavy_cruiser = { hg_attack = 0.08 }",
            )),
            ("modular_vertical_launch_cells", "Модульные установки вертикального пуска", "Modular Vertical-launch Cells", "naval_air_operations", 2163, (
                "naval_detection = 0.048",
                "convoy_escort_efficiency = 0.028",
            )),
            ("networked_task_groups", "Сетевые оперативные группы", "Networked Task Groups", "decimetric_radar", 2166, (
                "naval_hit_chance = 0.051",
                "naval_coordination = 0.03",
            )),
            ("railgun_batteries", "Корабельные рельсовые батареи", "Railgun Batteries", "advanced_centimetric_radar", 2170, (
                "naval_speed_factor = 0.032",
                "naval_hit_chance = 0.056",
            )),
            ("drone_carrier_deck_systems", "Палубные комплексы носителей беспилотников", "Drone-carrier Deck Systems", "air_defence", 2172, (
                "naval_hit_chance = 0.059",
                "naval_coordination = 0.033",
            )),
            ("distributed_horizon_targeting", "Распределённое загоризонтное целеуказание", "Distributed Horizon Targeting", "improved_cruiser_armor_scheme", 2175, (
                "naval_detection = 0.063",
                "convoy_escort_efficiency = 0.035",
            )),
            ("horizon_fleet_command", "Загоризонтное управление флотом", "Horizon Fleet Command", "improved_centimetric_radar", 2180, (
                "naval_hit_chance = 0.093",
                "naval_coordination = 0.093",
                "naval_detection = 0.052",
            )),
        ),
    ),
    research_branch(
        "subsurface", "ADISCORD_naval.txt", ('naval_folder', 'mtgnavalfolder'),
        "Подводные силы", "Subsurface Forces", "subsurface",
        (
            ("sonar_archives", "Архивы гидроакустики", "Sonar Archives", "sonar", 2150, (
                "naval_detection = 0.024",
                "naval_mines_effect_reduction = 0.04",
            )),
            ("quiet_propulsion", "Малошумные движители", "Quiet Propulsion", "basic_submarine_snorkel", 2155, (
                "naval_detection = 0.025",
                "naval_mines_effect_reduction = 0.041",
            )),
            ("homing_torpedoes", "Самонаводящиеся торпеды", "Homing Torpedoes", "basic_torpedo", 2158, (
                "submarine = { torpedo_attack = 0.08 }",
            )),
            ("air_independent_cells", "Воздухонезависимые ячейки", "Air-independent Cells", "improved_sonar", 2161, (
                "submarine = { naval_range = 0.10 }",
            )),
            ("wake_homing_torpedo_seekers", "Головки наведения торпед по кильватерному следу", "Wake-homing Torpedo Seekers", "improved_submarine_snorkel", 2163, (
                "naval_hit_chance = 0.048",
                "naval_coordination = 0.028",
            )),
            ("seabed_sensor_webs", "Донные сенсорные сети", "Seabed Sensor Webs", "advanced_submarine_warfare", 2166, (
                "naval_detection = 0.051",
                "naval_mines_effect_reduction = 0.03",
            )),
            ("autonomous_submarines", "Автономные подлодки", "Autonomous Submarines", "submarine_mine_laying", 2170, (
                "naval_coordination = 0.056",
                "naval_detection = 0.032",
            )),
            ("self_repairing_pressure_hulls", "Самовосстанавливающиеся прочные корпуса", "Self-repairing Pressure Hulls", "homing_torpedo", 2175, (
                "naval_detection = 0.035",
                "naval_mines_effect_reduction = 0.063",
            )),
            ("deep_ocean_denial", "Глубоководное сдерживание", "Deep-ocean Denial", "advanced_submarine_warfare", 2180, (
                "naval_detection = 0.093",
                "naval_mines_effect_reduction = 0.093",
                "naval_coordination = 0.052",
            )),
        ),
    ),
    research_branch(
        "riverine_warfare", "ADISCORD_naval.txt", ('naval_folder', 'mtgnavalfolder', 'mtgnavalsupportfolder'),
        "Речные и десантные операции", "Riverine and Amphibious Operations", "naval_support",
        (
            ("shallow_water_navigation_tables", "Таблицы мелководной навигации", "Shallow-water Navigation Tables", "sonar", 2162, (
                "naval_detection = 0.02",
                "naval_mines_effect_reduction = 0.02",
                "convoy_escort_efficiency = 0.02",
            )),
            ("modular_landing_causeways", "Модульные десантные эстакады", "Modular Landing Causeways", "advanced_sonar", 2169, (
                "naval_invasion_prep_speed = 0.05",
                "naval_invasion_penalty = -0.03",
                "shore_bombardment_bonus = 0.03",
            )),
            ("rapid_beachhead_logistics", "Быстрая логистика плацдарма", "Rapid Beachhead Logistics", "advanced_centimetric_radar", 2175, (
                "naval_invasion_planning_bonus_speed = 0.08",
                "supply_consumption_factor = -0.01",
                "convoy_escort_efficiency = 0.03",
            )),
        ),
    ),
    research_branch(
        "counter_drone_warfare", "ADISCORD_electronics.txt", ('electronics_folder',),
        "РЭБ и противодроновая борьба", "Electronic and Counter-drone Warfare", "signals",
        (
            ("spectrum_threat_libraries", "Библиотеки спектральных угроз", "Spectrum Threat Libraries", "radio", 2162, (
                "encryption_factor = 0.02",
                "decryption_factor = 0.02",
                "air_interception_detect_factor = 0.01",
            )),
            ("offensive_jamming_cells", "Ячейки наступательного подавления", "Offensive Jamming Cells", "basic_decryption", 2169, (
                "decryption_factor = 0.04",
                "coordination_bonus = 0.01",
                "air_mission_efficiency = 0.01",
            )),
            ("adaptive_spectrum_dominance", "Адаптивное господство в спектре", "Adaptive Spectrum Dominance", "advanced_encryption", 2175, (
                "encryption_factor = 0.05",
                "decryption_factor = 0.05",
                "coordination_bonus = 0.03",
                "air_mission_efficiency = 0.03",
            )),
        ),
    ),
)


SIDE_PROGRAMME_KEYS = frozenset(['air_mobility', 'combat_engineering', 'counter_drone_warfare', 'railway_artillery', 'riverine_warfare', 'unmanned_ground_systems'])

MAIN_BRANCH_KEYS_BY_FOLDER = {
    "industry_folder": ['advanced_materials', 'industry_organization', 'production', 'public_finance', 'reconstruction', 'resources'],
    "electronics_folder": ['computing', 'power', 'signals'],
    "infantry_folder": ['anti_tank_infantry', 'night_combat', 'protection', 'small_arms', 'squad_weapons', 'special_forces'],
    "support_folder": ['combat_medicine', 'field_support', 'logistics', 'officer_training', 'rail'],
    "artillery_folder": ['anti_air', 'anti_tank', 'artillery'],
    "armour_folder": ['combat_armor', 'heavy_armor', 'mechanized_mobility', 'recon_armor'],
    "air_techs_folder": ['air_support', 'bomber_maritime', 'fighter', 'strategic_air'],
    "naval_folder": ['naval_support', 'subsurface', 'surface_fleet'],
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


def linear_graph(count: int) -> BranchGraph:
    return make_graph((0,) * count, chain_edges(tuple(range(count))))


XOR_KIND_BY_BRANCH = {"production": "temporary", "industry_organization": "permanent"}
XOR_INDEX_GROUPS_BY_BRANCH = {"production": ((5, 6),), "industry_organization": ((1, 2),)}


# Shared entries and endpoints stay centred; each distinct route has its own lane.
PROGRAMME_ROUTES = {
    "small_arms": (
        (
            "postwar_weapon_standardization",
            "refurbished_receivers",
            "standardized_cartridges",
            "sealed_receiver_assemblies",
            "smart_recoil_compensators",
            "modular_rifle_kits",
            "biometric_trigger_locks",
            "coil_assisted_service_rifles",
            "networked_service_rifles",
        ),
        (
            "postwar_weapon_standardization",
            "refurbished_receivers",
            "standardized_cartridges",
            "smart_optics",
            "networked_weapon_sights",
            "integrated_target_designation",
            "networked_service_rifles",
        ),
        (
            "postwar_weapon_standardization",
            "refurbished_receivers",
            "standardized_cartridges",
            "caseless_ammunition_trials",
            "electrothermal_ignition",
            "programmable_ammunition",
            "hybrid_kinetic_energy_carbines",
            "networked_service_rifles",
        ),
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
            "plasma_scrap_separation",
            "synthetic_resource_cycles",
            "carbon_feedstock_cracking",
            "strategic_material_recovery",
        ),
        (
            "salvage_metallurgy",
            "spectral_ore_sorting",
            "borehole_sensor_grids",
            "automated_deep_mining",
            "strategic_material_recovery",
        ),
        (
            "salvage_metallurgy",
            "logistics_hub_networks",
            "microbial_tailings_leaching",
            "rare_earth_solvent_loops",
            "strategic_element_reclamation",
            "strategic_material_recovery",
        ),
    ),
    "signals": (
        (
            "mesh_command_networks",
            "field_radio_networks",
            "encryption_rebuild",
            "frequency_hopping_field_sets",
            "battlefield_analytics",
            "battlefield_sensor_fusion",
            "self_healing_tactical_networks",
            "memetic_security_protocols",
        ),
        (
            "mesh_command_networks",
            "field_radio_networks",
            "encryption_rebuild",
            "signal_intercept_arrays",
            "counterintelligence_filters",
            "memetic_security_protocols",
        ),
    ),
    "computing": (
        (
            "electromechanical_relays",
            "recovered_data_archives",
            "recovered_semiconductors",
            "hardened_computers",
            "error_correcting_field_computers",
            "strategic_digital_twins",
            "strategic_ai_coordination",
        ),
        (
            "electromechanical_relays",
            "recovered_data_archives",
            "recovered_semiconductors",
            "hardened_computers",
            "predictive_logistics",
            "operational_ai_assistants",
            "strategic_ai_coordination",
        ),
    ),
    "power": (
        (
            "local_grid_restoration",
            "substation_networks",
            "phase_synchronized_substations",
            "superconducting_power_busbars",
            "continental_load_balancing",
            "emergency_core_suppression",
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
            "autonomous_battery_network",
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
            "hypervelocity_at_networks",
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
            "directed_energy_air_defense",
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
}

PROGRAMME_SYNTHESIS = {
    "small_arms": ('networked_service_rifles',),
    "squad_weapons": ('swarm_fireteams',),
    "anti_tank_infantry": ('distributed_anti_armor_net',),
    "night_combat": ('nocturnal_combat_mesh',),
    "signals": ('memetic_security_protocols',),
    "computing": ('strategic_ai_coordination',),
    "artillery": ('autonomous_battery_network',),
    "anti_tank": ("hypervelocity_at_networks",),
    "anti_air": ("directed_energy_air_defense",),
    "recon_armor": ('autonomous_recon_screen',),
    "mechanized_mobility": ('networked_mechanized_cells',),
    "combat_armor": ('distributed_battlegroup',),
    "heavy_armor": ("siege_platform_networks",),
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
        raise ValueError(f"{branch.key}: technologies outside programme routes: {missing}")
    lanes = tuple(
        values[0] if len(values) == 1 else 1
        for values in membership.values()
    )
    synthesis = tuple(indices[key] for key in PROGRAMME_SYNTHESIS.get(branch.key, ()))
    return make_graph(lanes, edges, synthesis)


def graph_for_branch(branch: Branch) -> BranchGraph:
    count = len(branch.techs)
    if branch.key in PROGRAMME_ROUTES:
        graph = programme_graph(branch)
    elif branch.key == "production":
        # Either tooling specialization opens the shared maintenance programme.
        graph = make_graph(
            (1, 1, 1, 1, 1, 0, 2, 1, 1, 1),
            chain_edges((0, 1, 2, 3, 4)) + [(4, 5), (4, 6), (5, 7), (6, 7), (7, 8), (8, 9)],
        )
    elif branch.key == "industry_organization":
        graph = make_graph(
            (1, 0, 2, 0, 2, 0, 2, 0, 2),
            [(0, 1), (0, 2)] + chain_edges((1, 3, 5, 7)) + chain_edges((2, 4, 6, 8)),
        )
    elif branch.key == "advanced_materials":
        graph = make_graph((1, 0, 2, 0, 2, 1), [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 5)], (5,))
    elif branch.key == "bomber_maritime":
        graph = make_graph((1, 0, 2, 0, 2, 0, 2, 1), [(0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6), (5, 7), (6, 7)], (7,))
    else:
        graph = linear_graph(count)
    if len(graph.lanes) != count:
        raise ValueError(f"{branch.key}: graph and research rows differ in length")
    for start, targets in enumerate(graph.successors):
        for end in targets:
            if branch.years[start] >= branch.years[end]:
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
    "ADISCORD_tech_restored_truck_fleets": ("motorized_equipment_1",),
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
    "ADISCORD_tech_loyal_wingmen": ("ADISCORD_interceptor_airframe_2183",),
    "ADISCORD_tech_battlefield_attack_aircraft": ("ADISCORD_cas_airframe_2170",),
    "ADISCORD_tech_vtol_assault_frames": ("ADISCORD_vtol_airframe_2170",),
    "ADISCORD_tech_drone_air_wings": ("ADISCORD_drone_airframe_2183",),
    "ADISCORD_tech_orbital_tracking_relics": ("ADISCORD_rocket_strike_platform_2183",),
    "ADISCORD_tech_low_observable_cruise_missile_skins": ("ADISCORD_rocket_strike_platform_2183",),
    "ADISCORD_tech_suborbital_skip_glide_guidance": ("ADISCORD_deep_strike_airframe_2200",),
    "ADISCORD_tech_autonomous_strategic_strike_planning": ("ADISCORD_deep_strike_airframe_2200",),
    "ADISCORD_tech_suborbital_strike_systems": ("ADISCORD_orbital_tracking_platform_2200",),
}


# Production milestones identify the equipment families used by scripted armies.
NAVAL_AIR_UNLOCKS = {
    "coastal_patrols": ("ADISCORD_escort_ship_2155", "basic_destroyer"),
    "variable_depth_sonar": ("ADISCORD_escort_ship_2163", "improved_destroyer"),
    "autonomous_escorts": ("ADISCORD_escort_ship_2170", "advanced_destroyer"),
    "predictive_convoy_defense_network": ("ADISCORD_escort_ship_2175", "advanced_destroyer"),
    "modular_hull_standards": ("ADISCORD_cruiser_2155", "basic_heavy_cruiser"),
    "modular_vertical_launch_cells": ("ADISCORD_cruiser_2163", "improved_heavy_cruiser"),
    "railgun_batteries": ("ADISCORD_cruiser_2170", "advanced_heavy_cruiser"),
    "distributed_horizon_targeting": ("ADISCORD_cruiser_2175", "advanced_heavy_cruiser"),
    "quiet_propulsion": ("ADISCORD_submarine_2155", "basic_submarine"),
    "wake_homing_torpedo_seekers": ("ADISCORD_submarine_2163", "improved_submarine"),
    "autonomous_submarines": ("ADISCORD_submarine_2170", "advanced_submarine"),
    "self_repairing_pressure_hulls": ("ADISCORD_submarine_2175", "advanced_submarine"),
    "high_altitude_interceptors": ("ADISCORD_fighter_airframe_2161", "fighter2"),
    "thrust_vectoring": ("ADISCORD_fighter_airframe_2166", "jet_fighter1"),
    "loyal_wingmen": ("ADISCORD_fighter_airframe_2170", "jet_fighter2"),
    "distributed_interceptor_swarms": ("ADISCORD_fighter_airframe_2175", "jet_fighter2"),
    "precision_glide_bomb_kits": ("ADISCORD_attack_airframe_2163", "CAS2"),
    "autonomous_strike_wings": ("ADISCORD_attack_airframe_2170", "CAS3"),
    "persistent_sensor_strike_loops": ("ADISCORD_attack_airframe_2175", "CAS3"),
    "maritime_patrol_aircraft": ("ADISCORD_naval_aircraft_2164", "naval_bomber2"),
    "pressurized_bombers": ("ADISCORD_bomber_2164", "tactical_bomber2"),
    "long_range_maritime_aircraft": ("ADISCORD_naval_aircraft_2172", "naval_bomber3"),
    "jet_strike_bombers": ("ADISCORD_bomber_2172", "jet_tactical_bomber1"),
}
ENABLE_EQUIPMENT.update({f"ADISCORD_tech_{key}": (equipment,) for key, (equipment, _) in NAVAL_AIR_UNLOCKS.items()})
ENABLE_EQUIPMENT["ADISCORD_tech_twin_engine_aircraft"] = ("ADISCORD_bomber_2160", "ADISCORD_naval_aircraft_2160")
ENABLE_EQUIPMENT = {key: value for key, value in ENABLE_EQUIPMENT.items() if key in CURRENT_TECH_IDS}


# Cross-row integration is intentionally dependency-only: drawing paths
# between separate grid boxes is fragile in HOI4, while dependencies provide
# the required AND gate in the technology tooltip and research logic.
EXTRA_TECH_DEPENDENCIES = {
    "ADISCORD_tech_casualty_evacuation": ('ADISCORD_tech_combat_engineering_sections',),
    "ADISCORD_tech_battle_damage_survey_teams": ('ADISCORD_tech_standardized_field_tool_chests',),
    "ADISCORD_tech_spectrum_threat_libraries": ('ADISCORD_tech_frequency_hopping_field_sets',),
    "ADISCORD_tech_restored_airlift_planning": ('ADISCORD_tech_composite_wing_spars',),
    "ADISCORD_tech_shallow_water_navigation_tables": ('ADISCORD_tech_modular_escort_combat_systems',),
    "ADISCORD_tech_teleoperated_scout_carts": ('ADISCORD_tech_sealed_electric_scout_drives', 'ADISCORD_tech_hardened_computers'),
    "ADISCORD_tech_armored_carrier_program": ('ADISCORD_tech_sealed_electric_scout_drives', 'ADISCORD_tech_remote_weapon_stations'),
    "ADISCORD_tech_reconstituted_staff_academies": ('ADISCORD_tech_hardened_computers',),
    "ADISCORD_tech_railway_gun_reactivation": ('ADISCORD_tech_armored_rail_convoys',),
    "ADISCORD_tech_remote_weapon_tripods": ('ADISCORD_tech_modular_rifle_kits',),
    "ADISCORD_tech_autonomous_support_weapons": ('ADISCORD_tech_programmable_ammunition',),
    "ADISCORD_tech_swarm_fireteams": ('ADISCORD_tech_networked_service_rifles',),
    "ADISCORD_tech_autonomous_factory_cells": ('ADISCORD_tech_predictive_logistics',),
    "ADISCORD_tech_distributed_manufacturing": ('ADISCORD_tech_strategic_digital_twins',),
    "ADISCORD_tech_high_energy_laser_turrets": ('ADISCORD_tech_superconducting_power_busbars',),
    "ADISCORD_tech_autonomous_breakthrough_platforms": ('ADISCORD_tech_operational_ai_assistants',),
    "ADISCORD_tech_autonomous_strike_wings": ('ADISCORD_tech_operational_ai_assistants',),
    "ADISCORD_tech_autonomous_submarines": ('ADISCORD_tech_operational_ai_assistants',),
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
        # These programmes begin with research during the campaign. Making
        # their UI headings prominent must not grant their roots at startup.
        if branch_key not in {"officer_training", "bomber_maritime", "combat_medicine"}
    )
)

STARTING_TECH_PROFILE_SEEDS = {
    "common": COMMON_STARTING_ROOTS,
    "industrial": tuple(
        tech_id
        for branch_key in ("production", "reconstruction", "resources", "advanced_materials")
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
    "recon_platform": ("ADISCORD_tech_drone_recon_swarms",),
    "field_air_defense": ("ADISCORD_tech_point_defense_aa",),
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
    "NOD": ("industrial", "energy", "institutional", "land", "air", "naval", "armored_core"),
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
    "STP": (
        "industrial",
        "energy",
        "institutional",
        "land",
        "air",
        "naval",
        "recon_platform",
        "field_air_defense",
    ),
    "SVL": ("fragment_low_tech",),
    "TFF": ("fragment_low_tech", "land", "field_air_defense", "air"),
    "TMR": ("industrial",),
    "TRU": ("industrial", "institutional", "land"),
    "VAL": ("industrial", "energy", "institutional", "land", "air", "naval", "field_air_defense"),
    "VES": ("fragment_low_tech", "land"),
    "VLD": ("fragment_low_tech",),
    "VRA": ("fragment_low_tech",),
    "VLA": ("institutional", "land", "air"),
    "WEF": ("institutional", "land", "air"),
    "WIT": ("institutional", "land", "naval"),
    "WRK": ("industrial", "energy", "institutional", "land", "air", "naval", "armored_core"),
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
    "BCM": "Single-state Besjaysk fragment sustained by one civilian workshop base.",
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
    "TFF": "Frontier districts retain defensive land practice and a small standing army over a fragmentary workshop economy.",
    "TMR": "Utility chamber retains a modest industrial grid while limiting military specialization.",
    "TRU": "Organized Vorkerland successor with enough factories, infrastructure, and army continuity for core profiles.",
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
    "ADISCORD_tech_belt_fed_recovery": ("ADISCORD_regimental_fire_support",),
    "ADISCORD_tech_portable_at_cells": ("ADISCORD_regimental_anti_tank",),
    "ADISCORD_tech_radar_laying": ("ADISCORD_regimental_anti_air",),
    "ADISCORD_tech_urban_breaching": ("ADISCORD_regimental_pioneers",),
    "ADISCORD_tech_combat_recon_drones": ("ADISCORD_regimental_drone_observers",),
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
    "ADISCORD_tech_rare_components_industry": (("ADISCORD_rare_components_plant", 1),),
    "ADISCORD_tech_rare_alloy_metallurgy": (("ADISCORD_rare_alloy_foundry", 1),),
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
        ("synthetic_refinery", "rubber", 1),
    ),
    "ADISCORD_tech_strategic_element_reclamation": (
        ("ADISCORD_electrolysis_complex", "aluminium", 1),
        ("synthetic_refinery", "rubber", 2),
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
    "ADISCORD_tech_machine_vision_inspection": ("industry", 0.30, 1),
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
        raise ValueError(
            f"Research payoff on {_payoff_id} lands too late to be spent"
        )
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


def effects_for(branch: Branch, tier: int) -> tuple[str, ...]:
    return branch.techs[tier].effects


NAVAL_AIR_WEAPON_EFFECTS = {
    "air_independent_cells": ('submarine = { naval_range = 0.10 }',),
    "airborne_homing_torpedoes": ('nav_bomber = { naval_strike_attack = 0.10 naval_strike_targetting = 0.08 }',),
    "electronically_scanned_fighter_radar": ('fighter = { air_attack = 0.06 air_defence = 0.04 }',),
    "guided_munitions": ('cas = { air_ground_attack = 0.08 }',),
    "homing_torpedoes": ('submarine = { torpedo_attack = 0.08 }',),
    "integrated_strike_navigation": ('ADISCORD_tactical_bomber = { air_range = 0.08 strategic_attack = 0.06 }', 'nav_bomber = { air_range = 0.08 naval_strike_targetting = 0.06 }'),
    "jet_strike_bombers": ('ADISCORD_tactical_bomber = { strategic_attack = 0.06 }',),
    "long_range_maritime_aircraft": ('nav_bomber = { naval_strike_targetting = 0.06 }',),
    "maritime_patrol_aircraft": ('nav_bomber = { air_range = 0.04 }',),
    "missile_batteries": ('heavy_cruiser = { hg_attack = 0.08 }',),
    "pressurized_bombers": ('ADISCORD_tactical_bomber = { air_defence = 0.04 }',),
    "radar_gunnery": ('heavy_cruiser = { hg_attack = 0.06 }',),
    "stabilized_bomb_sights": ('ADISCORD_tactical_bomber = { strategic_attack = 0.08 air_ground_attack = 0.06 }',),
    "twin_engine_aircraft": ('ADISCORD_tactical_bomber = { reliability = 0.02 }',),
}


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


EQUIPMENT_UNLOCK_ICONS.update({f"ADISCORD_tech_{key}": icon for key, (_, icon) in NAVAL_AIR_UNLOCKS.items()})
EQUIPMENT_UNLOCK_ICONS["ADISCORD_tech_twin_engine_aircraft"] = "tactical_bomber1"


# Infantry effect-only cards show the equipment being improved. Their art
# must stay attached to the technology when the branch order changes.
REGIONAL_SERVICE_ICON_TAGS = ("STP", "VAL")

INFANTRY_COMPACT_ICONS = {
    key: icon
    for icon, keys in {
        "ADISCORD_equipment_ammunition": (
            "standardized_cartridges", "caseless_ammunition_trials",
            "hybrid_kinetic_energy_carbines", "programmable_grenade_fuzes",
            "deep_area_sustainment_pods",
        ),
        "ADISCORD_equipment_mechanism": (
            "electrothermal_ignition", "biometric_trigger_locks",
        ),
        "ADISCORD_equipment_armour": (
            "composite_protection_kits", "trauma_plates", "ceramic_trauma_inserts",
            "adaptive_radiation_shielding", "self_sealing_combat_skins",
        ),
        "ADISCORD_equipment_camouflage": (
            "thermal_signature_liners", "reactive_camouflage_textiles",
            "adaptive_camouflage", "low_observable_infiltration_suits",
            "multispectral_concealment_discipline",
        ),
        "ADISCORD_equipment_medical": (
            "smart_tourniquet_systems", "nanofiber_wound_dressings",
        ),
        "ADISCORD_equipment_respirator": (
            "sealed_combat_suits", "sealed_respirator_interfaces",
            "radiation_patrols",
        ),
        "ADISCORD_equipment_drone": (
            "drone_guided_support_fire",
            "combat_recon_drones", "autonomous_scout_microdrones",
            "robotic_breaching_companions",
        ),
        "ADISCORD_equipment_radio": (
            "networked_command_terminals", "cooperative_target_handoff",
            "swarm_coordinated_fire_support",
            "remote_beacon_extraction", "contested_zone_navigation",
            "augmented_mission_rehearsal",
        ),
        "ADISCORD_equipment_climbing": (
            "fieldcraft_manuals", "subterranean_route_reconnaissance",
            "urban_vertical_access_rigs", "vertical_assault_training",
        ),
        "ADISCORD_equipment_breaching": (
            "urban_breaching", "assault_sapper_kits",
        ),
        "ADISCORD_equipment_exoskeleton": (
            "powered_load_bearing_harnesses", "exoskeleton_load_frames",
            "exosuit_joint_actuators", "augmented_special_forces",
        ),
        "ADISCORD_equipment_ballistic_sight": (
            "networked_weapon_sights", "integrated_target_designation",
        ),
        "ADISCORD_night_04_squad_target_sharing": (
            "deep_recon_cells", "predictive_patrol_evasion",
        ),
        "ADISCORD_night_05_counter_illumination": (
            "man_portable_sensor_masts", "distributed_recon_sensor_caches",
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
        "ADISCORD_antitank_04_antitank_rifle": ("electromagnetic_anti_armor_launchers",),
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
WEAPON_CATEGORY_ICONS.update({
    "portable_at_cells": "ADISCORD_squad_02_heavy_machine_guns",
    "recoilless_squad_launchers": "ADISCORD_squad_02_heavy_machine_guns",
    "field_ew_units": "ADISCORD_squad_03_optical_fire_support",
    "remote_weapon_tripods": "ADISCORD_squad_03_optical_fire_support",
    "autonomous_support_weapons": "ADISCORD_squad_04_advanced_fire_support",
    "robotic_heavy_weapon_teams": "ADISCORD_squad_04_advanced_fire_support",
    "swarm_fireteams": "ADISCORD_squad_04_advanced_fire_support",
    "electrothermal_ignition": "ADISCORD_weapon_03_standardized_battle_rifle",
    "biometric_trigger_locks": "ADISCORD_weapon_03_standardized_battle_rifle",
})


def weapon_category_scale(tech: Tech) -> str:
    # Category art is 176x72; effect-only cards have a 72x72 viewport.
    if tech.key == "recovered_medium_chassis":
        return "\t\tscale = 0.35\n"
    if tech.id not in ENABLE_EQUIPMENT:
        branch, index = TECH_POSITION_BY_ID[tech.id]
        size = technology_icon_size(icon_for_technology(branch, index))
        if size and max(size) > 72:
            scale = min(64 / size[0], 64 / size[1])
            return f"\t\tscale = {scale:.6f}\n"
    return ""


def icon_for_technology(branch: Branch, index: int) -> str:
    tech = branch.techs[index]
    if tech.key in WEAPON_CATEGORY_ICONS:
        return WEAPON_CATEGORY_ICONS[tech.key]
    if branch.key == "small_arms" and tech.id in ENABLE_EQUIPMENT:
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
        return "night_vision" if tech.key in {
            "passive_intensifier_cells", "thermal_observation_channels",
        } else "night_vision2"
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
        if size and candidate.startswith("ADISCORD_") and size[0] <= 190 and size[1] <= 84:
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


TECHNICAL_TECH_DESCRIPTIONS = {
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
        "Защитное снаряжение и приборы контроля заражения позволяют готовить разведывательные выходы в опасную местность",
        "Protective equipment and contamination monitors support reconnaissance preparations for hazardous areas",
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
    "ADISCORD_rare_components_plant": ("завод редких компонентов", "Rare Components Plant"),
    "ADISCORD_rare_alloy_foundry": ("завод редких сплавов", "Rare Alloy Foundry"),
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


TECHNICAL_TECH_DESCRIPTIONS.update({
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
})


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
    if branch.key == "public_finance":
        entries.append("modifier = { factor = 1.40 ADISCORD_economy_ai_is_crisis = yes }")
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
    multiplier = (
        HORIZONTAL_YEAR_SLOT_MULTIPLIER if horizontal else VERTICAL_YEAR_SLOT_MULTIPLIER
    )
    return slot * multiplier


def horizontal_visual_slots(branch: Branch) -> tuple[int, ...]:
    """Keep every node under its actual research year, including fork arms."""

    slots = tuple(
        chronological_grid_slot(year, horizontal=True)
        for year in branch.years
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
    years = sorted(set(branch.years))
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
    doubled_slot = (
        2 * graph.lanes[index] - min(graph.lanes) - max(graph.lanes)
    ) * multiplier
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
    budget_effect = any(effect.startswith("ADISCORD_economy_") for effect in effects_for(branch, index))
    if not building_upgrades and payoff is None and not budget_effect:
        return []
    if LEADER_TRAINING.get(tech.key) is not None:
        raise ValueError(
            f"{tech.id} already spends its on_research_complete on leader training"
        )
    lines = ["\t\ton_research_complete = {"]
    if budget_effect:
        lines.append("\t\t\thidden_effect = { ADISCORD_economy_mark_dirty = yes }")
    for building, resource, amount in building_upgrades:
        lines.extend((
            "\t\t\tmodify_building_resources = {",
            f"\t\t\t\tbuilding = {building}",
            f"\t\t\t\tresource = {resource}",
            f"\t\t\t\tamount = {amount}",
            "\t\t\t}",
        ))
    if payoff is not None:
        category, bonus, uses = payoff
        branch, _ = TECH_POSITION_BY_ID[tech.id]
        declared = CATEGORY_BY_PROFILE[branch.profile].split()
        if category not in declared:
            raise ValueError(
                f"{tech.id} cannot grant {category} research; its branch declares "
                f"{declared}"
            )
        lines.extend((
            "\t\t\tadd_tech_bonus = {",
            f"\t\t\t\tbonus = {n(bonus)}",
            f"\t\t\t\tuses = {uses}",
            f"\t\t\t\tcategory = {category}",
            "\t\t\t}",
        ))
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
        elif position + 2 < len(tokens) and tokens[position + 1] in {"=", ">", "<", ">=", "<="}:
            value = tokens[position + 2]
            lines.append("\t" * indent + " ".join(tokens[position:position + 3]))
            if value == "{":
                indent += 1
            position += 3
        else:
            lines.append("\t" * indent + token)
            position += 1
    return lines


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
    for effect in effects_for(branch, index):
        lines.extend(render_payload(effect, 2))
    if tech.id == "ADISCORD_tech_restored_dockyards":
        # Native transport permission is separate from the invasion plan and
        # division caps, which retain their engine defaults.
        lines.append("\t\tnaval_invasion_capacity = 100")
    lines.extend(render_leader_training_effect(tech))
    for target in graph.successors[index]:
        lines.extend((
            "\t\tpath = {",
            f"\t\t\tleads_to_tech = {branch.techs[target].id}",
            "\t\t\tresearch_cost_coeff = 1",
            "\t\t}",
        ))
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
    lines.extend(render_research_completion_effects(tech))
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
    for entry in ai_will_do_for(branch, index):
        lines.extend(render_payload(entry, 3))
    lines.extend((
        "\t\t}",
        f"\t\tcategories = {{ {CATEGORY_BY_PROFILE[branch.profile]} }}",
        "\t}",
    ))
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
        ))
        # Startup calculates the first budget after granting profiles. Later
        # grants must invalidate it without reinitializing an existing country.
        if any(
            effect.startswith("ADISCORD_economy_")
            for tech_id in technology_ids
            for effect in effects_for(*TECH_POSITION_BY_ID[tech_id])
        ):
            lines.extend((
                "\thidden_effect = {",
                "\t\tif = {",
                "\t\t\tlimit = { has_variable = ADISCORD_economy_initialized }",
                "\t\t\tADISCORD_economy_mark_dirty = yes",
                "\t\t}",
                "\t}",
            ))
        lines.extend((
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
        history_paths = sorted((ROOT / "history" / "countries").glob(f"{tag} - *.txt"))
        history_text = history_paths[0].read_text(encoding="utf-8-sig") if history_paths else ""
        oob_match = re.search(r'(?m)^\s*oob\s*=\s*"([^"\n]+)"', history_text)
        oob_name = oob_match.group(1) if oob_match else tag
        oob_path = ROOT / "history" / "units" / f"{oob_name}.txt"
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


CUSTOM_TECH_TEXTURES = {
    "recovered_medium_chassis": "gfx/interface/technologies/armor/ADISCORD_restored_main_battle_tank.dds",
    "recovered_shaped_charge_cells": "gfx/interface/technologies/ADISCORD_antitank_01_incendiary_bottle.dds",
    "disposable_launcher_standards": "gfx/interface/technologies/ADISCORD_antitank_02_satchel_charge.dds",
    "tandem_penetrator_packages": "gfx/interface/technologies/ADISCORD_antitank_03_shaped_charge_grenade.dds",
    "wire_guided_hunter_teams": "gfx/interface/technologies/ADISCORD_antitank_04_antitank_rifle.dds",
    "top_attack_profiles": "gfx/interface/technologies/ADISCORD_antitank_08_rocket_launcher.dds",
    "loitering_armor_hunters": "gfx/interface/technologies/ADISCORD_antitank_09_top_attack_seeker.dds",
}


def write_gfx() -> None:
    entries = []
    for branch in BRANCHES:
        for index, tech in enumerate(branch.techs):
            icon = icon_for_technology(branch, index)
            custom_texture = CUSTOM_TECH_TEXTURES.get(tech.key)
            variants = [(f"GFX_{tech.id}_medium", custom_texture or icon)]
            if not custom_texture and icon.startswith("ADISCORD_weapon_") and tech.id in ENABLE_EQUIPMENT:
                variants.extend(
                    (f"GFX_{tag}_{tech.id}_medium", icon.replace("ADISCORD_", f"ADISCORD_{tag}_", 1))
                    for tag in REGIONAL_SERVICE_ICON_TAGS
                )
            for sprite, texture in variants:
                texture_file = (
                    texture
                    if texture.startswith("gfx/")
                    else f"gfx/interface/technologies/{texture}.dds"
                )
                entries.append(
                    "\tSpriteType = {\n"
                    f"\t\tname = \"{sprite}\"\n"
                    f"\t\ttextureFile = \"{texture_file}\"\n"
                    f"{weapon_category_scale(tech)}"
                    "\t}\n"
                )
    content = (
        "spriteTypes = {\n"
        + "\n".join(entries)
        + technology_tree_gfx_entries()
        + "}\n"
    )
    (ROOT / "interface" / "ADISCORD_technologies.gfx").write_text(content, encoding="utf-8")


def weapon_category_gfx_output() -> str:
    """Regenerate category sprites without rebuilding unrelated UI declarations."""
    path = ROOT / "interface" / "ADISCORD_technologies.gfx"
    text = path.read_text(encoding="utf-8")
    for branch in BRANCHES:
        for tech in branch.techs:
            if tech.key not in WEAPON_CATEGORY_ICONS:
                continue
            sprite = f"GFX_{tech.id}_medium"
            pattern = rf'\tSpriteType = \{{\s*name = "{re.escape(sprite)}"[^{{}}]*\}}'
            texture = f"gfx/interface/technologies/{WEAPON_CATEGORY_ICONS[tech.key]}.dds"
            replacement = (
                "\tSpriteType = {\n"
                f'\t\tname = "{sprite}"\n'
                f'\t\ttextureFile = "{texture}"\n'
                + weapon_category_scale(tech)
                + "\t}"
            )
            text, count = re.subn(pattern, lambda match: replacement, text)
            if count != 1:
                raise ValueError(f"Expected one category sprite {sprite}, found {count}")
    return text


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
    "motorized_equipment": (
        "Грузовые автомобили", "Cargo Trucks", "Грузовики", "Trucks",
        "Автомобили для доставки боеприпасов, продовольствия и топлива от узлов снабжения к войскам.",
        "Vehicles carrying ammunition, food and fuel from supply hubs to the troops.",
    ),
    "motorized_equipment_1": (
        "Восстановленные грузовики", "Rebuilt Cargo Trucks", "Грузовики I", "Trucks I",
        "Простые грузовики с восстановленными двигателями и ходовой частью. Обеспечивают моторизацию узлов снабжения.",
        "Simple trucks with rebuilt engines and running gear. Used to motorize supply hubs.",
    ),
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
        "Противотанковая установка расчёта с усиленным станком, оптикой и переносным боезапасом.",
        "A crew-operated anti-tank launcher with a reinforced mount, optics, and portable ammunition.",
    ),
    "ADISCORD_squad_weapons_equipment_2168": (
        "КОП-68 «Вал»", "FSC-68 “Shaft”", "КОП-68", "FSC-68",
        "Станковый гранатомёт со сменными узлами, общей оптикой и переносным боезапасом.",
        "A mounted grenade launcher with interchangeable assemblies, shared optics, and portable ammunition.",
    ),
    "ADISCORD_squad_weapons_equipment_2170": (
        "КОП-70 «Гул»", "FSC-70 “Rumble”", "КОП-70", "FSC-70",
        "Пулемётный комплект с дальномером и передачей целей на планшет расчёта.",
        "A machine-gun system with a rangefinder and target sharing through the crew tablet.",
    ),
    "ADISCORD_squad_weapons_equipment_2178": (
        "КОП-78 «Узел»", "FSC-78 “Knot”", "КОП-78", "FSC-78",
        "Станковый гранатомёт с программируемыми взрывателями и защищённой передачей целей.",
        "A mounted grenade launcher with programmable fuzes and protected target sharing.",
    ),
    "ADISCORD_squad_weapons_equipment_2183": (
        "КОП-83 «Маяк»", "FSC-83 “Beacon”", "КОП-83", "FSC-83",
        "Дистанционно управляемая огневая установка с многоканальными датчиками и планшетом расчёта.",
        "A remotely controlled fire-support mount with multichannel sensors and a crew tablet.",
    ),
    "ADISCORD_squad_weapons_equipment_2193": (
        "КОП-93 «Рой»", "FSC-93 “Swarm”", "КОП-93", "FSC-93",
        "Роботизированная опора тяжёлого оружия с автоматическим сопровождением целей и ручным управлением расчёта.",
        "A robotic heavy-weapon carrier with automatic target tracking and manual crew control.",
    ),
    "ADISCORD_squad_weapons_equipment_2200": (
        "КОП-00 «Хор»", "FSC-00 “Chorus”", "КОП-00", "FSC-00",
        "Согласованная сеть огневых роботов и разведывательных дронов под управлением расчёта.",
        "A coordinated network of armed robots and scout drones under crew control.",
    ),
}


INFANTRY_FAMILY_LOCALISATION = {
    "infantry_equipment": ("Личное стрелковое оружие", "Personal Small Arms"),
    "infantry_equipment_short": ("Личное оружие", "Personal Weapons"),
    "infantry_equipment_desc": (
        "Винтовки, карабины и автоматы, которыми вооружён каждый пехотинец.",
        "Rifles, carbines, and automatic weapons carried by individual infantry soldiers.",
    ),
    "ADISCORD_squad_weapons_equipment": ("Групповое оружие отделения", "Squad Crew-served Weapons"),
    "ADISCORD_squad_weapons_equipment_short": ("Групповое оружие", "Crew-served Weapons"),
    "ADISCORD_squad_weapons_equipment_desc": (
        "Пулемёты, станковые гранатомёты и тяжёлые огневые установки. Расчёты обслуживают оружие, переносят его и боезапас, обеспечивая огневую поддержку отделения.",
        "Machine guns, mounted grenade launchers, and heavy fire-support mounts. Crews operate the weapons and carry their ammunition to support the squad.",
    ),
}


NAVAL_AIR_UNIT_LOCALISATION = {
    "ADISCORD_tactical_bomber": ("Бомбардировщик", "Bomber"),
    "ADISCORD_tactical_bomber_desc": ("Бомбардировочная авиация для ударов по промышленности, снабжению и сухопутным войскам.", "Bomber aircraft for attacks on industry, supply and ground forces."),
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

REGIMENTAL_SUPPORT_LOCALISATION = {
    "ADISCORD_regimental_fire_support": (
        "Полковая огневая группа", "Regimental Fire-support Group",
    ),
    "ADISCORD_regimental_fire_support_desc": (
        "Расчёты пулемётов и станкового оружия для непосредственной поддержки полка. Используют групповое оружие, усиливая огонь по пехоте. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Machine-gun and crew-served weapon teams for close regimental support. Use crew-served weapons to reinforce anti-infantry fire. Occupy the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_anti_tank": (
        "Полковой противотанковый взвод", "Regimental Anti-tank Platoon",
    ),
    "ADISCORD_regimental_anti_tank_desc": (
        "Небольшой противотанковый резерв полка. Требует противотанкового вооружения и повышает бронепробитие; заметно слабее полной батареи. Занимает полковую ячейку под столбцом из не менее трёх батальонов.",
        "A small regimental anti-tank reserve. Requires anti-tank weapons and improves piercing; substantially weaker than a full battery. Occupies the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_anti_air": (
        "Полковой взвод ПВО", "Regimental Air-defense Platoon",
    ),
    "ADISCORD_regimental_anti_air_desc": (
        "Зенитные расчёты для прикрытия позиций полка и борьбы с низколетящими целями. Используют производимое зенитное вооружение. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Anti-aircraft teams covering regimental positions against low-flying targets. Use the country's produced anti-aircraft weapons. Occupy the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_pioneers": (
        "Полковой сапёрный взвод", "Regimental Pioneer Platoon",
    ),
    "ADISCORD_regimental_pioneers_desc": (
        "Сапёры с подрывным инструментом и полевыми комплектами. Улучшают укрепление позиций, штурм городской застройки и укреплений. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Pioneers with demolition tools and field kits. Improve entrenchment and assaults on urban positions and fortifications. Occupy the regimental slot below a column of at least three battalions.",
    ),
    "ADISCORD_regimental_drone_observers": (
        "Полковая группа воздушной разведки", "Regimental Drone Observation Team",
    ),
    "ADISCORD_regimental_drone_observers_desc": (
        "Наблюдатели с разведывательными дронами, средствами связи и запасными частями из полевых комплектов. Повышают разведку и инициативу, но почти не добавляют огневой мощи. Занимают полковую ячейку под столбцом из не менее трёх батальонов.",
        "Observers using reconnaissance drones, radios and spares supplied as field equipment. Improve reconnaissance and initiative with little added firepower. Occupy the regimental slot below a column of at least three battalions.",
    ),
}


def generated_localisation(language: str) -> list[str]:
    is_ru = language == "russian"
    lines = [
        f' {key}:0 "{names[0 if is_ru else 1]}"'
        for mapping in (
            ACCESS_REQUIREMENT_LOCALISATION, INFANTRY_FAMILY_LOCALISATION,
            NAVAL_AIR_UNIT_LOCALISATION, REGIMENTAL_SUPPORT_LOCALISATION,
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
        else:
            name = ("Личное оружие " if is_ru else "Personal weapon ") + name
            short = ("Личн. " if is_ru else "Personal ") + short
        lines.extend((
            f' {equipment_id}:0 "{name}"',
            f' {equipment_id}_short:0 "{short}"',
            f' {equipment_id}_desc:0 "{description}"',
        ))
    lines.append("")
    for equipment_id, (ru, en, description_ru, description_en) in NAVAL_AIR_EQUIPMENT_LOCALISATION.items():
        name, description = (ru, description_ru) if is_ru else (en, description_en)
        lines.extend((
            f' {equipment_id}:0 "{name}"',
            f' {equipment_id}_short:0 "{name}"',
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
        for equipment_id in (*LAND_EQUIPMENT_LOCALISATION, *NAVAL_AIR_EQUIPMENT_LOCALISATION)
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
                or key in NAVAL_AIR_UNIT_LOCALISATION
                or key in REGIMENTAL_SUPPORT_LOCALISATION
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
            grid_height = (
                (max(graph.lanes) - min(graph.lanes) + 1)
                * HORIZONTAL_LANE_SLOT_MULTIPLIER * GRID_SLOT
            )
            branch_layouts.append((branch, GRID_X, cursor_y, grid_width, grid_height))
            cursor_y += grid_height + BRANCH_GAP
        content_width = max(1180, GRID_X + grid_width + 80)
        height = max(700, cursor_y + 80)
    else:
        cursor_x = GRID_X
        for branch in branches:
            graph = BRANCH_GRAPHS[branch.key]
            grid_height = (max(technology_time_slot(branch, i) for i in range(len(branch.techs))) + 2) * GRID_SLOT
            grid_width = (
                (max(graph.lanes) - min(graph.lanes) + 1) * LANE_SLOT_MULTIPLIER
            ) * GRID_SLOT
            branch_layouts.append((branch, cursor_x, GRID_Y, grid_width, grid_height))
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
    # Vertical branches carry their own dated rows; a shared ruler would imply
    # that independent programmes on the same row have the same research year.
    if horizontal:
        year_labels = [
            (
                str(year), year,
                GRID_X + chronological_grid_slot(year, horizontal=True) * GRID_SLOT
                + (GRID_SLOT - YEAR_LABEL_WIDTH) // 2,
                84,
            )
            for year in YEARS
        ]
    else:
        year_labels = [
            (
                f"{branch.key}_{year}", year, grid_x - 62,
                grid_y + technology_time_slot(branch, branch.years.index(year)) * GRID_SLOT
                + (GRID_SLOT - YEAR_LABEL_HEIGHT) // 2,
            )
            for branch, grid_x, grid_y, _, _ in branch_layouts
            for year in sorted(set(branch.years))
        ]
    for label, year, year_x, year_y in year_labels:
        lines.extend((
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
        ))
    # Technology grid boxes must be direct children of the folder container.
    # The game does not discover grids nested inside the decorative
    # ``techtree_stripes`` container and reports every technology as having
    # no grid box even when the grid name itself is correct.
    lines.append("\t\t\t}")
    for branch, grid_x, grid_y, grid_width, grid_height in branch_layouts:
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
            f"\t\t\t\tslotsize = {{ width = {GRID_SLOT} height = {GRID_SLOT} }}",
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
            # Replace indentation with the generated block instead of adding
            # another prefix on every repository-GUI regeneration.
            line_start = text.rfind("\n", 0, start) + 1
            if text[line_start:start].strip():
                raise ValueError(f"Technology folder {name} must begin on its own line")
            replacements.append((line_start, end, render_folder(name)))
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
    text = apply_tree_skin(text)
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
    ensure_technology_state_gfx_current()
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
        f"{len(SIDE_PROGRAMME_KEYS)} branches are attached specialisations."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the A-Discord technology system.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate current generated outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write technology files, manifests, GUI and localisation")
    actions.add_argument("--apply-starting-profiles", action="store_true", help="write only starting technology effects and the country profile manifest")
    parser.add_argument("--technology-data-only", action="store_true", help="check or apply technology scripts without regenerating UI, localisation or country history")
    parser.add_argument("--weapon-icons-only", action="store_true", help="check or apply weapon category sprites without rebuilding other UI")
    args = parser.parse_args()
    if args.weapon_icons_only:
        if args.technology_data_only or args.apply_starting_profiles:
            parser.error("--weapon-icons-only cannot be combined with other partial output modes")
        path = ROOT / "interface" / "ADISCORD_technologies.gfx"
        content = weapon_category_gfx_output()
        changed = path.read_text(encoding="utf-8") != content
        if args.apply and changed:
            path.write_text(content, encoding="utf-8")
        print(f"Weapon category sprites {'updated' if args.apply else 'different'}: {int(changed)}")
        return int(changed and not args.apply)
    if args.technology_data_only:
        if args.apply_starting_profiles:
            parser.error("--technology-data-only cannot update starting profiles")
        changed = [path for path, content in technology_file_outputs().items()
                   if not path.exists() or path.read_text(encoding="utf-8-sig") != content]
        if args.apply:
            write_technology_files()
        print(f"Technology scripts {'updated' if args.apply else 'different'}: {len(changed)}")
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
