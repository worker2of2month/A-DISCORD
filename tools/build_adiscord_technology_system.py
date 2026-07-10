from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
# The legacy part of the tree is intentionally broad.  From the intended
# campaign baseline in 2160 onward, the cadence tightens to roughly one
# research generation every two to three years, following the dense-tree
# pattern used by large total conversions such as TFR and Darkest Hour.
YEARS = (
    2100, 2120, 2140, 2150,
    2160, 2162, 2164, 2166, 2168,
    2170, 2173, 2176, 2179,
    2182, 2185, 2188,
    2191, 2194, 2197, 2200,
)
MILESTONE_YEARS = (2100, 2120, 2140, 2160, 2170, 2182, 2200)
# Clausewitz technology grids use x for parallel lanes and y for progress
# along a LEFT-formatted tree.  The GUI turns every two y-slots into one
# horizontal 140-pixel era column.
YEAR_TO_Y = {year: index * 2 for index, year in enumerate(YEARS)}
GRID_X = 150
LANE_SLOT_MULTIPLIER = 2


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
        (2100, 2120, 2140, 2160, 2182, 2200),
    ),
    Branch(
        "forbidden_automation", "ADISCORD_forbidden.txt", ("electronics_folder",),
        "Запретная автоматизация", "Forbidden Automation", "forbidden_automation",
        techs("""
self_repairing_industrial_swarms|Самовосстанавливающиеся рои|Self-repairing Industrial Swarms|flexible_line
neural_command_cores|Нейронные командные ядра|Neural Command Cores|improved_mainframe
forbidden_automation_doctrine|Доктрина запретной автоматизации|Forbidden Automation Doctrine|advanced_mainframe
"""),
        (2170, 2182, 2200),
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
        "Основные боевые платформы", "Main Combat Platforms", "combat_armor",
        techs("""
recovered_medium_chassis|Восстановленное среднее шасси|Recovered Medium Chassis|basic_medium_tank
remote_weapon_stations|Дистанционные боевые модули|Remote Weapon Stations|improved_medium_tank
composite_armor_arrays|Массивы композитной брони|Composite Armor Arrays|advanced_medium_tank
semi_autonomous_combat_modules|Полуавтономные платформы|Semi-autonomous Combat Modules|basic_modern_tank
adaptive_fire_control|Адаптивное управление огнём|Adaptive Fire Control|improved_modern_tank
limited_battle_ai|Ограниченный боевой ИИ|Limited Battle AI|advanced_modern_tank
distributed_battlegroup|Распределённая бронегруппа|Distributed Battlegroup|generic_modern_tank
"""),
    ),
    Branch(
        "heavy_armor", "ADISCORD_armor.txt", ("armour_folder", "nsb_armour_folder"),
        "Тяжёлые и автономные платформы", "Heavy and Autonomous Platforms", "heavy_armor",
        techs("""
heavy_recovery_frames|Тяжёлые ремонтные рамы|Heavy Recovery Frames|basic_heavy_tank
reinforced_powertrains|Усиленные силовые установки|Reinforced Powertrains|improved_heavy_tank
heavy_composite_cores|Тяжёлые композитные ядра|Heavy Composite Cores|advanced_heavy_tank
remote_repair_sections|Дистанционные ремонтные машины|Remote Repair Sections|maintenance_company
heavy_platform_cores|Ядро тяжёлой платформы|Heavy Platform Cores|super_heavy_tank
autonomous_breakthrough_platforms|Автономные платформы прорыва|Autonomous Breakthrough Platforms|main_battle_tank
siege_platform_networks|Сеть осадных платформ|Siege Platform Networks|land_cruiser
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


try:
    from adiscord_technology_expansions_civil import EXPANSIONS as CIVIL_EXPANSIONS
    from adiscord_technology_expansions_combat import EXPANSIONS as COMBAT_EXPANSIONS
except ModuleNotFoundError:
    from tools.adiscord_technology_expansions_civil import EXPANSIONS as CIVIL_EXPANSIONS
    from tools.adiscord_technology_expansions_combat import EXPANSIONS as COMBAT_EXPANSIONS


EXPANSION_YEARS = set(YEARS) - set(MILESTONE_YEARS)
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
    if set(additions) != EXPANSION_YEARS:
        missing = sorted(EXPANSION_YEARS - set(additions))
        extra = sorted(set(additions) - EXPANSION_YEARS)
        raise ValueError(f"{branch.key}: bad expansion years; missing={missing}, extra={extra}")

    by_year = dict(zip(MILESTONE_YEARS, branch.techs, strict=True))
    by_year.update({year: Tech(*additions[year]) for year in EXPANSION_YEARS})
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
}


def apply_tech_text_overrides(branch: Branch) -> Branch:
    changed = []
    for tech in branch.techs:
        override = TECH_TEXT_OVERRIDES.get(tech.key)
        changed.append(replace(tech, ru=override[0], en=override[1]) if override else tech)
    return replace(branch, techs=tuple(changed))


BRANCHES = tuple(apply_tech_text_overrides(branch) for branch in BRANCHES)


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


def trident_graph() -> BranchGraph:
    left = (5, 8, 11, 14, 17)
    centre = (6, 9, 12, 15, 18)
    right = (7, 10, 13, 16, 19)
    edges = chain_edges((0, 1, 2, 3, 4))
    for lane in (left, centre, right):
        edges.append((4, lane[0]))
        edges += chain_edges(lane)
    lanes = [1] * 20
    for index in left:
        lanes[index] = 0
    for index in right:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges)


def trident_specialization_graph() -> BranchGraph:
    """Three mutually exclusive, long-lived programmes after a common trunk."""

    return trident_graph()


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


def infantry_integration_graph() -> BranchGraph:
    """Rifle mechanisms, ammunition, and optics form three real programmes."""

    ammunition = (2, 3, 6, 11, 13, 14, 16)
    rifles = (2, 5, 7, 9, 10, 15, 18)
    optics = (2, 4, 8, 12, 17)
    edges = chain_edges((0, 1, 2))
    edges += chain_edges(ammunition) + chain_edges(rifles) + chain_edges(optics)
    edges += [(16, 19), (17, 19), (18, 19)]
    lanes = [1] * 20
    for index in rifles[1:]:
        lanes[index] = 0
    for index in ammunition[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (19,))


def squad_integration_graph() -> BranchGraph:
    """Integrate automatic weapons, guided launchers, and squad C2."""

    explosive = (0, 1, 2, 3, 5, 11, 16)
    command = (0, 4, 6, 8, 9, 12, 15)
    automatic = (0, 7, 10)
    edges = chain_edges(explosive) + chain_edges(command) + chain_edges(automatic)
    edges += [(10, 13), (12, 13), (13, 14), (14, 17)]
    edges += [(16, 18), (15, 18), (17, 18), (18, 19)]
    lanes = [1] * 20
    for index in automatic[1:] + (13, 14, 17):
        lanes[index] = 0
    for index in explosive[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (13, 18))


def protection_programmes_graph() -> BranchGraph:
    """Body systems, combat medicine, and environmental protection."""

    body = (0, 1, 3, 6, 8, 9, 14)
    medicine = (0, 4, 10, 11, 15)
    environment = (0, 2, 5, 7, 12, 13, 16)
    edges = chain_edges(body) + chain_edges(medicine) + chain_edges(environment)
    edges += [(15, 17), (16, 17), (14, 18), (17, 18), (18, 19)]
    lanes = [1] * 20
    for index in body[1:]:
        lanes[index] = 0
    for index in environment[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (17, 18))


def special_forces_programmes_graph() -> BranchGraph:
    """Urban assault, deep reconnaissance, and airborne insertion."""

    urban = (0, 1, 3, 5, 16)
    reconnaissance = (0, 2, 4, 6, 7, 8, 11, 13, 14, 15)
    airborne = (0, 9, 10, 12, 17)
    edges = chain_edges(urban) + chain_edges(reconnaissance) + chain_edges(airborne)
    edges += [(16, 18), (15, 18), (17, 18), (18, 19)]
    lanes = [1] * 20
    for index in urban[1:]:
        lanes[index] = 0
    for index in airborne[1:]:
        lanes[index] = 2
    return make_graph(tuple(lanes), edges, (18,))


GRAPH_PATTERN_BY_BRANCH = {
    # Persistent strategic schools share a late OR-gated capstone.
    "reconstruction": "dual_choice",
    "finance": "dual_choice",
    "combat_armor": "dual_choice",
    "strategic_air": "dual_choice",
    "surface_fleet": "dual_choice",
    # These branches intentionally require both programmes for synthesis.
    "power": "dual_synthesis",
    # Three long-lived specializations after the common 2160 baseline.
    "production": "trident_specialization",
    "resources": "trident_specialization",
    "artillery": "trident_specialization",
    "fighter": "trident_specialization",
    # Three independent programmes can all be pursued if research permits.
    "administration": "trident",
    "small_arms": "infantry_integration",
    # Repeated paired research programmes converge into integrated systems.
    "civil_resilience": "double_diamond",
    "signals": "double_diamond",
    "computing": "double_diamond",
    "squad_weapons": "squad_integration",
    "protection": "protection_programmes",
    "special_forces": "special_forces_programmes",
    # Two successive attack/defence or manned/autonomous decisions.
    "anti_tank": "double_choice",
    "recon_armor": "double_choice",
    "subsurface": "double_choice",
    # A stable main line absorbs one of two field projects at each stage.
    "field_support": "alternating_choices",
    "logistics": "alternating_choices",
    "rail": "alternating_choices",
    "anti_air": "alternating_choices",
    "heavy_armor": "alternating_choices",
    "air_support": "alternating_choices",
    "naval_support": "alternating_choices",
}


DUAL_PROGRAMME_YEARS = (
    2100, 2120, 2140, 2150, 2160,
    2162, 2162, 2168, 2168, 2173, 2173, 2179, 2179,
    2185, 2185, 2191, 2191, 2197, 2197, 2200,
)
TRIDENT_PROGRAMME_YEARS = (
    2100, 2120, 2140, 2150, 2160,
    2162, 2162, 2162, 2170, 2170, 2170, 2182, 2182, 2182,
    2191, 2191, 2191, 2200, 2200, 2200,
)
DOUBLE_PROGRAMME_YEARS = (
    2100, 2120, 2140, 2150, 2160,
    2162, 2162, 2164, 2164, 2166, 2166, 2168,
    2173, 2173, 2179, 2179, 2185, 2185, 2194, 2200,
)
ALTERNATING_PROGRAMME_YEARS = (
    2100, 2120, 2140, 2150, 2160,
    2162, 2162, 2164, 2166,
    2168, 2168, 2170, 2173,
    2176, 2176, 2179, 2182,
    2188, 2188, 2200,
)


def align_programme_years(branch: Branch) -> Branch:
    pattern = GRAPH_PATTERN_BY_BRANCH.get(branch.key)
    years_by_pattern = {
        "dual_choice": DUAL_PROGRAMME_YEARS,
        "dual_synthesis": DUAL_PROGRAMME_YEARS,
        "trident": TRIDENT_PROGRAMME_YEARS,
        "trident_specialization": TRIDENT_PROGRAMME_YEARS,
        "double_diamond": DOUBLE_PROGRAMME_YEARS,
        "double_choice": DOUBLE_PROGRAMME_YEARS,
        "alternating_diamonds": ALTERNATING_PROGRAMME_YEARS,
        "alternating_choices": ALTERNATING_PROGRAMME_YEARS,
    }
    years = years_by_pattern.get(pattern)
    return replace(branch, years=years) if years else branch


BRANCHES = tuple(align_programme_years(branch) for branch in BRANCHES)


GRAPH_BUILDERS = {
    "dual_synthesis": dual_synthesis_graph,
    "dual_choice": dual_choice_graph,
    "trident": trident_graph,
    "trident_specialization": trident_specialization_graph,
    "double_diamond": double_diamond_graph,
    "double_choice": double_choice_graph,
    "alternating_diamonds": alternating_diamonds_graph,
    "alternating_choices": alternating_choices_graph,
    "infantry_integration": infantry_integration_graph,
    "squad_integration": squad_integration_graph,
    "protection_programmes": protection_programmes_graph,
    "special_forces_programmes": special_forces_programmes_graph,
}


def graph_for_branch(branch: Branch) -> BranchGraph:
    if branch.key == "forbidden_energy":
        return make_graph(
            (1, 1, 1, 0, 2, 1),
            [(0, 1), (1, 2), (2, 3), (2, 4), (3, 5), (4, 5)],
            (5,),
        )
    if branch.key == "forbidden_automation":
        return make_graph((1, 0, 2), [(0, 1), (0, 2)])
    pattern = GRAPH_PATTERN_BY_BRANCH.get(branch.key)
    if pattern is None:
        raise ValueError(f"{branch.key}: missing technology graph pattern")
    graph = GRAPH_BUILDERS[pattern]()
    if len(graph.lanes) != len(branch.techs):
        raise ValueError(f"{branch.key}: graph has {len(graph.lanes)} nodes for {len(branch.techs)} techs")
    for source, targets in enumerate(graph.successors):
        for target in targets:
            if branch.years[target] <= branch.years[source]:
                raise ValueError(f"{branch.key}: non-chronological edge {source}->{target}")
    return graph


BRANCH_GRAPHS = {branch.key: graph_for_branch(branch) for branch in BRANCHES}


XOR_INDEX_GROUPS_BY_BRANCH = {}
for branch in BRANCHES:
    pattern = GRAPH_PATTERN_BY_BRANCH.get(branch.key)
    if pattern == "dual_choice":
        XOR_INDEX_GROUPS_BY_BRANCH[branch.key] = ((5, 6),)
    elif pattern == "trident_specialization":
        # Clausewitz only renders two outgoing XOR paths reliably.  The first
        # two lanes are rival schools; the third is an independent programme
        # that either school may fund, mirroring large-mod industry layouts.
        XOR_INDEX_GROUPS_BY_BRANCH[branch.key] = ((5, 6),)
    elif pattern == "double_choice":
        XOR_INDEX_GROUPS_BY_BRANCH[branch.key] = ((5, 6), (12, 13))
    elif pattern == "alternating_choices":
        XOR_INDEX_GROUPS_BY_BRANCH[branch.key] = (
            (5, 6), (9, 10), (13, 14), (17, 18),
        )


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
    "ADISCORD_tech_modular_rifle_kits": ("ADISCORD_infantry_equipment_2170",),
    "ADISCORD_tech_programmable_ammunition": ("ADISCORD_infantry_equipment_2183",),
    "ADISCORD_tech_networked_service_rifles": ("ADISCORD_infantry_equipment_2200",),
    "ADISCORD_tech_belt_fed_recovery": ("ADISCORD_squad_weapons_equipment_0",),
    "ADISCORD_tech_remote_weapon_tripods": ("ADISCORD_squad_weapons_equipment_2170",),
    "ADISCORD_tech_autonomous_support_weapons": ("ADISCORD_squad_weapons_equipment_2183",),
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
    "ADISCORD_tech_remote_weapon_tripods": ("ADISCORD_tech_modular_rifle_kits",),
    "ADISCORD_tech_autonomous_support_weapons": ("ADISCORD_tech_programmable_ammunition",),
    "ADISCORD_tech_swarm_fireteams": ("ADISCORD_tech_networked_service_rifles",),
}


ENABLE_SUBUNITS = {
    "ADISCORD_tech_remote_weapon_tripods": ("ADISCORD_assault_infantry",),
    "ADISCORD_tech_standardized_field_tool_chests": ("maintenance_company",),
    "ADISCORD_tech_frequency_hopping_field_sets": ("signal_company",),
    "ADISCORD_tech_casualty_evacuation": ("field_hospital",),
    "ADISCORD_tech_forward_supply_hubs": ("logistics_company",),
    "ADISCORD_tech_drone_recon_swarms": ("ADISCORD_recon_platform",),
    "ADISCORD_tech_semi_autonomous_combat_modules": ("ADISCORD_combat_platform",),
    "ADISCORD_tech_remote_repair_sections": ("ADISCORD_recovery_platform",),
    "ADISCORD_tech_heavy_platform_cores": ("ADISCORD_heavy_platform",),
    "ADISCORD_tech_active_mass_balancing_suspension": ("ADISCORD_heavy_platform",),
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


def effects_for(branch: Branch, tier: int) -> tuple[str, ...]:
    """Return an effect package that reflects the actual programme selected.

    Filler-sized 0.4% effects made the old dense tree feel cosmetic.  A narrow
    technology is now normally worth about 1.2-1.8%, while a role-specific
    technology is worth 2-3%.  XOR branches replace, rather than stack, one
    another, keeping their cumulative strength under control.
    """

    profile = branch.profile
    tier_count = len(branch.techs)
    progress = 0 if tier_count <= 1 else tier * 6 / (tier_count - 1)
    capstone_scale = 1.45 if tier == tier_count - 1 else 1.0
    small = (0.012 + progress * 0.001) * capstone_scale
    medium = (0.020 + progress * 0.002) * capstone_scale
    organisation = (0.75 + progress * 0.12) * capstone_scale

    pattern = GRAPH_PATTERN_BY_BRANCH.get(branch.key)
    lane = BRANCH_GRAPHS[branch.key].lanes[tier]
    xor_group = next(
        (group for group in XOR_INDEX_GROUPS_BY_BRANCH.get(branch.key, ()) if tier in group),
        (),
    )
    xor_option = xor_group.index(tier) if xor_group else None

    # Persistent strategic schools.
    if pattern == "dual_choice" and tier >= 5 and tier != 19:
        dual = {
            "reconstruction": {
                0: (f"production_speed_buildings_factor = {n(medium)}", f"production_speed_industrial_complex_factor = {n(small)}"),
                2: (f"industry_repair_factor = {n(medium)}", f"production_speed_infrastructure_factor = {n(small)}"),
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

    # Long-lived three-way industrial and equipment specializations.
    if pattern == "trident_specialization" and tier >= 5:
        trident = {
            "production": {
                0: (f"line_change_production_efficiency_factor = {n(medium * 2)}", f"production_factory_efficiency_gain_factor = {n(small)}"),
                1: (f"industrial_capacity_factory = {n(medium)}", f"production_factory_start_efficiency_factor = {n(small)}"),
                2: (f"production_factory_max_efficiency_factor = {n(medium)}", f"production_lack_of_resource_penalty_factor = -{n(small)}"),
            },
            "resources": {
                0: (f"local_resources_factor = {n(medium)}", f"production_lack_of_resource_penalty_factor = -{n(small)}"),
                1: (f"fuel_gain_factor = {n(medium)}", f"local_resources_factor = {n(small)}"),
                2: (f"local_resources_factor = {n(medium * 1.25)}", f"industry_repair_factor = {n(small)}"),
            },
            "artillery": {
                0: (f"artillery = {{ soft_attack = {n(medium)} reliability = {n(small)} }}",),
                1: (f"artillery = {{ hard_attack = {n(medium)} ap_attack = {n(medium)} }}",),
                2: (f"artillery = {{ soft_attack = {n(medium)} breakthrough = {n(small)} }}",),
            },
            "fighter": {
                0: (f"air_mission_efficiency = {n(medium)}", f"air_accidents_factor = -{n(small)}"),
                1: (f"air_intercept_efficiency = {n(medium)}", f"air_mission_efficiency = {n(small)}"),
                2: (f"air_mission_efficiency = {n(medium)}", f"air_accidents_factor = -{n(medium)}"),
            },
        }
        return trident[branch.key][lane]

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
    "nuclear_bomb": "nuclear_missile_equipment_1",
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
    "special_project_air_nuclear_missile": "nuclear_missile_equipment_1",
    "special_project_land_railgun": "generic_super_heavy_railway_gun",
    "special_project_nuclear_reactor": "nuclear_reactor",
    "special_project_thermonuclear_bomb": "sp_nuclear_isotope_separation",
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
    "civil": ("basic_construction", "engineers", "radio"),
    "power": ("electronic_mechanical_engineering", "atomic_research", "radio"),
    "signals": ("radio", "basic_encryption", "basic_decryption"),
    "computing": ("mechanical_computing", "computing_machine", "improved_computing_machine"),
    "forbidden_energy": ("atomic_research", "nuclear_reactor"),
    "forbidden_automation": ("flexible_line", "advanced_computing_machine"),
    "infantry": ("infantry_weapons", "infantry_weapons2", "night_vision"),
    "squad": ("support_weapons", "support_weapons2", "infantry_at"),
    "protection": ("engineers", "tech_field_hospital", "recon"),
    "special_forces": ("recon", "tech_special_forces", "paratroopers"),
    "support": ("engineers", "tech_maintenance_company", "tech_field_hospital"),
    "logistics": ("tech_logistics_company", "radio", "engineers"),
    "rail": ("engineers", "radio", "tech_maintenance_company"),
    "artillery": ("artillery1", "artillery2", "artillery3"),
    "anti_tank": ("antitank1", "antitank2", "antitank3"),
    "anti_air": ("antiair1", "antiair2", "antiair3"),
    "recon_armor": ("nsb_engine_tech_1", "nsb_armor_tech_1", "armored_operations"),
    "combat_armor": ("nsb_armor_tech_1", "nsb_engine_tech_1", "armored_operations"),
    "heavy_armor": ("nsb_armor_tech_1", "engineers", "armored_operations"),
    "fighter": ("bba_tech_aircraft_construction", "bba_tech_engines_1", "centimetric_radar"),
    "air_support": ("bba_tech_armor_piercing_bombs", "bba_tech_engines_1", "radio"),
    "strategic_air": ("rocket_engines", "advanced_rocket_engines", "centimetric_radar"),
    "naval_support": ("sonar", "advanced_sonar", "advanced_centimetric_radar"),
    "surface_fleet": ("basic_cruiser_armor_scheme", "advanced_centimetric_radar", "naval_air_operations"),
    "subsurface": ("sonar", "basic_naval_mines", "advanced_sonar"),
}


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
    size = technology_icon_size(icon)
    if tech.id not in ENABLE_EQUIPMENT and size and (size[0] > 72 or size[1] > 72):
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
    "protection": "улучшает защиту, выживаемость и медицинское обеспечение бойцов",
    "special_forces": "повышает мобильность и эффективность разведки и специальных сил",
    "support": "усиливает инженерные, ремонтные и медицинские подразделения",
    "logistics": "снижает расход снабжения и ускоряет переброску резервов",
    "rail": "повышает устойчивость железнодорожного снабжения и ремонта путей",
    "artillery": "повышает точность, надёжность и огневую мощь артиллерии",
    "anti_tank": "увеличивает бронепробитие и эффективность против тяжёлых целей",
    "anti_air": "усиливает обнаружение и поражение воздушных целей",
    "recon_armor": "повышает скорость и надёжность разведывательной бронетехники",
    "combat_armor": "усиливает огневую мощь и прорыв основных боевых платформ",
    "heavy_armor": "повышает защиту и живучесть тяжёлых автономных платформ",
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
        "protection": "improves soldier protection, survival, and battlefield medicine",
        "special_forces": "improves the mobility and effectiveness of recon and special forces",
        "support": "strengthens engineering, repair, and medical units",
        "logistics": "reduces supply use and accelerates movement of reserves",
        "rail": "improves the resilience of railway supply and track repair",
        "artillery": "improves artillery accuracy, reliability, and firepower",
        "anti_tank": "increases armor penetration and performance against heavy targets",
        "anti_air": "improves detection and destruction of aerial targets",
        "recon_armor": "improves the speed and reliability of reconnaissance armor",
        "combat_armor": "improves the firepower and breakthrough of main combat platforms",
        "heavy_armor": "improves protection and survivability of heavy autonomous platforms",
        "fighter": "improves interception efficiency and reduces aviation accidents",
        "air_support": "improves close support for ground forces",
        "strategic_air": "develops long-range missile strikes and strategic guidance",
        "naval_support": "improves convoy protection and detection of maritime threats",
        "surface_fleet": "improves accuracy and coordination of surface task forces",
        "subsurface": "develops underwater detection, stealth, and maritime denial",
    }[key]
    for key in BRANCH_DESCRIPTION_RU
}


BUILDING_DISPLAY_NAMES = {
    "ADISCORD_metallurgical_complex": ("металлургический комплекс", "Metallurgical Complex"),
    "ADISCORD_electrolysis_complex": ("электролизный комплекс", "Electrolysis Complex"),
    "ADISCORD_strategic_mining_complex": ("комплекс стратегической добычи", "Strategic Mining Complex"),
    "ADISCORD_thermal_power_complex": ("теплоэнергетический комплекс", "Thermal Power Complex"),
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
        pattern = GRAPH_PATTERN_BY_BRANCH[branch.key]
        if pattern == "trident_specialization":
            notes.append(
                f"Долгосрочная специализация; закрывает программы: {alternatives}."
                if is_ru else
                f"Long-term specialization; locks out: {alternatives}."
            )
        else:
            notes.append(
                f"Взаимоисключающий проект с вариантом: {alternatives}; общая линия продолжится после любого выбора."
                if is_ru else
                f"Mutually exclusive with: {alternatives}; the common line continues after either choice."
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
    year_index = YEARS.index(year)
    research_progress = year_index * 6 / (len(YEARS) - 1)
    if year <= 2140:
        research_cost = 0.55
    elif year <= 2150:
        research_cost = 0.70
    elif year <= 2160:
        research_cost = 0.90
    else:
        research_cost = 1.05 + min(0.30, (year - 2160) * 0.0075)
    if xor:
        research_cost = max(research_cost, 1.50)
    if tech.id in ENABLE_EQUIPMENT or tech.id in ENABLE_SUBUNITS or tech.id in ENABLE_BUILDINGS:
        research_cost = max(research_cost, 1.75)
    if tech.id in BUILDING_RESOURCE_UPGRADES:
        research_cost = max(research_cost, 1.35)
    if len(dependencies) >= 2:
        research_cost = max(research_cost, 2.35)
    if index == len(branch.techs) - 1 and year >= 2200:
        research_cost = max(research_cost, 2.20)
    if branch.profile.startswith("forbidden_"):
        research_cost += 1.25
    lines.extend((
        f"\t\tresearch_cost = {n(research_cost)}",
        f"\t\tstart_year = {year}",
    ))
    for folder in branch.folders:
        lines.extend((
            "\t\tfolder = {",
            f"\t\t\tname = {folder}",
            f"\t\t\tposition = {{ x = {graph.lanes[index] * LANE_SLOT_MULTIPLIER} y = {YEAR_TO_Y[year]} }}",
            "\t\t}",
        ))
    ai_factor = (
        1
        if branch.profile.startswith("forbidden_")
        else max(8, round(36 - research_progress * 4))
    )
    lines.extend((
        f"\t\tai_will_do = {{ factor = {ai_factor} }}",
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
    """Grant the recovered pre-campaign baseline to every existing country."""

    baseline = [
        tech.id
        for branch in BRANCHES
        if not branch.profile.startswith("forbidden_")
        for tech, year in zip(branch.techs, branch.years, strict=True)
        if year <= 2150
    ]
    lines = [
        "# Generated by tools/build_adiscord_technology_system.py.",
        "# The campaign begins in 2160; recovered 2100-2150 knowledge is baseline,",
        "# while the dense 2160+ programmes remain player and AI decisions.",
        "ADISCORD_grant_2150_technology_baseline = {",
        "\tset_technology = {",
    ]
    lines.extend(f"\t\t{tech_id} = 1" for tech_id in baseline)
    lines.extend((
        "\t\tpopup = no",
        "\t}",
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
    ))
    path = ROOT / "common" / "scripted_effects" / "ADISCORD_technology_baseline_effects.txt"
    path.write_text("\n".join(lines), encoding="utf-8")


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


def generated_localisation(language: str) -> list[str]:
    is_ru = language == "russian"
    lines: list[str] = []
    for branch in BRANCHES:
        key = f"ADISCORD_TECH_BRANCH_{branch.key.upper()}"
        lines.append(f" {key}:0 \"{branch.ru if is_ru else branch.en}\"")
    lines.append("")
    for branch in BRANCHES:
        description = BRANCH_DESCRIPTION_RU[branch.profile] if is_ru else BRANCH_DESCRIPTION_EN[branch.profile]
        for index, tech in enumerate(branch.techs):
            name = tech.ru if is_ru else tech.en
            year = branch.years[index]
            if is_ru:
                desc = f"{name}: {description}. Технологический уровень {year} года."
            else:
                desc = f"{name}: {description}. Technology level: {year}."
            notes = technology_description_notes(branch, index, is_ru)
            if notes:
                desc += " " + " ".join(notes)
            lines.append(f" {tech.id}:0 \"{name}\"")
            lines.append(f" {tech.id}_desc:0 \"{desc}\"")
    return lines


def write_localisation() -> None:
    targets = {
        "russian": ROOT / "localisation" / "russian" / "ADISCORD_technology_doctrine_l_russian.yml",
        "english": ROOT / "localisation" / "english" / "ADISCORD_technology_doctrine_l_english.yml",
    }
    generated_key = re.compile(r"^\s+(?:ADISCORD_tech_|ADISCORD_TECH_BRANCH_)")
    for language, path in targets.items():
        if path.exists():
            original = path.read_text(encoding="utf-8-sig").splitlines()
        else:
            original = [f"l_{language}:"]
        preserved = [line for line in original if not generated_key.match(line)]
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
    branch_layouts: list[tuple[Branch, int, int, int]] = []
    cursor_y = 0
    for branch in branches:
        graph = BRANCH_GRAPHS[branch.key]
        grid_height = (max(graph.lanes) * LANE_SLOT_MULTIPLIER + 1) * 70
        title_y = 105 + cursor_y
        grid_y = 147 + cursor_y
        branch_layouts.append((branch, title_y, grid_y, grid_height))
        cursor_y += grid_height + 80
    height = max(700, 150 + cursor_y)
    grid_width = (max(YEAR_TO_Y.values()) + 1) * 70
    # The year labels and wide equipment cards extend beyond the nominal
    # 70-pixel grid slot.  Keep enough room for the final 2200 card instead
    # of clipping it against the scrollable content edge.
    content_width = max(1180, GRID_X + grid_width + 120)
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
        lines.extend((
            "\t\t\t\tinstantTextBoxType = {",
            f"\t\t\t\t\tname = \"ADISCORD_{folder}_year_{year}\"",
            f"\t\t\t\t\tposition = {{ x = {135 + index * 140} y = 42 }}",
            "\t\t\t\t\tfont = \"hoi_24header\"",
            f"\t\t\t\t\ttext = \"{year}\"",
            "\t\t\t\t\tmaxWidth = 100",
            "\t\t\t\t\tmaxHeight = 28",
            "\t\t\t\t\tformat = center",
            "\t\t\t\t\tOrientation = \"UPPER_LEFT\"",
            "\t\t\t\t}",
        ))
    # Technology grid boxes must be direct children of the folder container.
    # The game does not discover grids nested inside the decorative
    # ``techtree_stripes`` container and reports every technology as having
    # no grid box even when the grid name itself is correct.
    lines.append("\t\t\t}")
    for branch, title_y, grid_y, grid_height in branch_layouts:
        lines.extend((
            "\t\t\tinstantTextBoxType = {",
            f"\t\t\t\tname = \"ADISCORD_branch_{branch.key}\"",
            f"\t\t\t\tposition = {{ x = 36 y = {title_y} }}",
            "\t\t\t\tfont = \"hoi_18b\"",
            f"\t\t\t\ttext = \"ADISCORD_TECH_BRANCH_{branch.key.upper()}\"",
            f"\t\t\t\tmaxWidth = {content_width - 72}",
            "\t\t\t\tmaxHeight = 24",
            "\t\t\t\tformat = left",
            "\t\t\t\tOrientation = \"UPPER_LEFT\"",
            "\t\t\t}",
            "\t\t\tgridboxtype = {",
            f"\t\t\t\tname = \"{branch.techs[0].id}_tree\"",
            f"\t\t\t\tposition = {{ x = {GRID_X} y = {grid_y} }}",
            f"\t\t\t\tsize = {{ width = {grid_width} height = {grid_height} }}",
            "\t\t\t\tslotsize = { width = 70 height = 70 }",
            "\t\t\t\tformat = \"LEFT\"",
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

    # Vanilla gives the industry/electronics default item a 204x72 container,
    # even when it displays an ordinary effect-only technology.  With a dense
    # 140px year cadence that creates overlapping click targets and protruding
    # frames.  Reuse the complete, engine-compatible 72x72 infantry small-item
    # template instead of trying to hand-maintain its many required children.
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


def main() -> None:
    all_ids = [tech.id for branch in BRANCHES for tech in branch.techs]
    duplicates = sorted({tech_id for tech_id in all_ids if all_ids.count(tech_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate technology IDs: {duplicates}")
    write_technology_files()
    write_starting_technology_effect()
    write_gfx()
    write_localisation()
    write_gui()
    print(f"Generated {len(all_ids)} technologies in {len(BRANCHES)} independent branches.")


if __name__ == "__main__":
    main()
