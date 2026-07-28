"""Generate the A-Discord mastery doctrine system.

The structure borrows the useful part of TDA's doctrine redesign: a country
chooses a bounded operational school, unlocks it through relevant technology,
and earns five modest rewards by actually using the associated forces.  Legacy
IDs are retained for the original eleven schools and their existing rewards.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Track:
    key: str
    ru: str
    en: str
    background: str
    icon: str
    frame: str
    multiplier: float
    mastery_kind: str
    mastery_values: tuple[str, ...]


@dataclass(frozen=True)
class School:
    key: str
    domain: str
    track: str
    ru: str
    en: str
    desc_ru: str
    desc_en: str
    icon: str
    gate: str
    root_effects: tuple[str, ...]
    profile: str
    ai: tuple[str, ...] = ()
    legacy_rewards: tuple[str, ...] = ()


TRACKS = (
    Track("ADISCORD_land_mass_restoration", "Восстановление массовой армии", "Mass Army Restoration", "GFX_grand_battleplan_bg", "GFX_doctrine_milestone_infantry_land", "GFX_doctrine_decor_land", 1.0, "categories", ("category_all_infantry",)),
    Track("ADISCORD_land_platform_centric", "Танковые войска", "Armored Forces", "GFX_mob_warfare_bg", "GFX_doctrine_milestone_armored_land", "GFX_doctrine_decor_land", 6.0, "categories", ("category_tanks", "category_all_armor")),
    Track("ADISCORD_land_networked_operations", "Оперативное управление", "Operational Command", "GFX_tac_operation_bg", "GFX_doctrine_milestone_operations_land", "GFX_doctrine_decor_land", 0.8, "categories", ("category_all_infantry", "category_support_battalions", "category_tanks", "category_all_armor")),
    Track("ADISCORD_land_fortress_state", "Огневая поддержка и устойчивость", "Fire Support and Resilience", "GFX_sup_firepower_bg", "GFX_doctrine_milestone_artillery_land", "GFX_doctrine_decor_land", 0.8, "categories", ("category_all_infantry", "category_support_battalions", "category_line_artillery")),
    Track("ADISCORD_air_drone_swarm", "Беспилотная авиация", "Unmanned Aviation", "GFX_air_superiority_bg", "GFX_doctrine_milestone_fighter_air", "GFX_doctrine_decor_air", 7.0, "equipment", ("fighter", "cas", "naval_bomber")),
    Track("ADISCORD_air_vtol_deep_strike", "Поддержка наземных войск", "Ground-force Aviation", "GFX_battlefield_destruction_bg", "GFX_doctrine_milestone_striker_air", "GFX_doctrine_decor_air", 7.0, "equipment", ("cas", "tactical_bomber", "heavy_fighter")),
    Track("ADISCORD_air_strategic_denial", "Контроль воздушного пространства", "Airspace Control", "GFX_strategic_destruction_bg", "GFX_doctrine_milestone_heavy_air", "GFX_doctrine_decor_air", 7.0, "equipment", ("fighter", "interceptor", "strategic_bomber")),
    Track("ADISCORD_naval_littoral_security", "Прибрежная безопасность", "Littoral Security", "GFX_screens_bg", "GFX_doctrine_milestone_screens_naval", "GFX_doctrine_decor_naval", 2.0, "equipment", ("screen_ship",)),
    Track("ADISCORD_naval_surface_control", "Надводные соединения", "Surface Action Groups", "GFX_fleet_in_being_bg", "GFX_doctrine_milestone_ships_naval", "GFX_doctrine_decor_naval", 2.5, "equipment", ("capital_ship", "carrier", "screen_ship")),
    Track("ADISCORD_naval_subsurface_warfare", "Подводная война", "Subsurface Warfare", "GFX_trade_interdiction_bg", "GFX_doctrine_milestone_submarine_naval", "GFX_doctrine_decor_naval", 3.0, "equipment", ("submarine",)),
    Track("ADISCORD_special_forces_adaptation", "Адаптация специальных сил", "Special-force Adaptation", "GFX_paratroopers_bg", "GFX_doctrine_milestone_special_forces", "GFX_doctrine_decor_special_forces", 4.0, "categories", ("category_special_forces",)),
    Track("ADISCORD_special_forces_insertion", "Ввод и автономность специальных сил", "Special-force Insertion", "GFX_marine_bg", "GFX_doctrine_milestone_special_forces", "GFX_doctrine_decor_special_forces", 4.0, "categories", ("category_special_forces",)),
)


def reward(slug: str, ru: str, en: str, *effects: str) -> tuple[str, str, str, tuple[str, ...]]:
    return slug, ru, en, effects


REWARD_PROFILES = {
    "mass": (
        reward("line_rotation", "Ротация линейных частей", "Line-unit Rotation", "category_all_infantry = { default_morale = 0.03 }"),
        reward("salvage_issue", "Снабжение восстановленным оружием", "Salvaged Arms Issue", "category_all_infantry = { soft_attack = 0.03 }"),
        reward("replacement_drafts", "Подготовленные маршевые пополнения", "Prepared Replacement Drafts", "land_reinforce_rate = 0.01"),
        reward("distributed_training", "Распределённая подготовка", "Distributed Training", "category_all_infantry = { max_organisation = 2 }"),
        reward("restoration_front", "Единый фронт восстановления", "Restoration Front", "category_all_infantry = { defense = 0.05 max_organisation = 3 }", "planning_speed = 0.03"),
    ),
    "assault": (
        reward("assault_recon", "Разведка штурмовых маршрутов", "Assault-route Reconnaissance", "category_recon = { recon = 0.5 }"),
        reward("breach_groups", "Группы развития прорыва", "Breach Exploitation Groups", "category_all_infantry = { breakthrough = 0.04 }"),
        reward("short_fireplans", "Короткие огневые планы", "Short Fireplans", "planning_speed = 0.04"),
        reward("shock_reserves", "Ударные резервы", "land_reinforce_rate = 0.01", "category_all_infantry = { soft_attack = 0.03 }"),
        reward("continuous_assault", "Непрерывный штурм", "category_all_infantry = { breakthrough = 0.06 soft_attack = 0.04 }"),
    ),
    "mobile": (
        reward("march_discipline", "Дисциплина марша", "March Discipline", "org_loss_when_moving = -0.015"),
        reward("mobile_reserves", "Мобильные резервы", "Mobile Reserves", "land_reinforce_rate = 0.01"),
        reward("route_control", "Контроль маршрутов", "Route Control", "supply_consumption_factor = -0.01"),
        reward("rolling_front", "Подвижный фронт", "Rolling Front", "category_all_infantry = { maximum_speed = 0.03 }"),
        reward("operational_mobility", "Оперативная мобильность", "Operational Mobility", "category_all_infantry = { maximum_speed = 0.04 max_organisation = 3 }", "org_loss_when_moving = -0.02"),
    ),
    "militia": (
        reward("local_guides", "Местные проводники", "Local Guides", "category_all_infantry = { defense = 0.03 }"),
        reward("hidden_stores", "Скрытые склады", "Hidden Stores", "supply_consumption_factor = -0.01"),
        reward("district_reserves", "Окружные резервы", "District Reserves", "land_reinforce_rate = 0.01"),
        reward("ruin_positions", "Позиции в руинах", "Ruins as Positions", "dig_in_speed_factor = 0.04"),
        reward("defense_in_depth", "Распределённая оборона", "Distributed Defense", "category_all_infantry = { defense = 0.07 max_organisation = 2 }", "dig_in_speed_factor = 0.05"),
    ),
    "armor_breakthrough": (
        reward("remote_weapons", "Координация дистанционного оружия", "Remote Weapon Coordination", "category_all_armor = { soft_attack = 0.04 }"),
        reward("heavy_columns", "Тяжёлые колонны прорыва", "Heavy Breakthrough Columns", "category_tanks = { breakthrough = 0.06 }"),
        reward("drone_screen", "Дроновое прикрытие наступления", "Drone-screened Advance", "category_all_armor = { defense = 0.04 }", "coordination_bonus = 0.01"),
        reward("repair_cycles", "Автономные ремонтные циклы", "Autonomous Repair Cycles", "category_all_armor = { reliability = 0.04 default_morale = 0.03 }"),
        reward("armored_decision", "Танковая война решений", "Armored Decision Warfare", "category_all_armor = { breakthrough = 0.08 max_organisation = 2 }"),
    ),
    "armor_integration": (
        reward("infantry_liaisons", "Связные мотопехоты", "Motor-infantry Liaisons", "coordination_bonus = 0.01"),
        reward("protected_approach", "Прикрытый подход", "Protected Approach", "category_all_infantry = { breakthrough = 0.03 }"),
        reward("mutual_support", "Взаимная поддержка", "Mutual Support", "category_all_armor = { defense = 0.04 }", "category_all_infantry = { defense = 0.02 }"),
        reward("combined_reserves", "Общевойсковые резервы", "Combined-arms Reserves", "land_reinforce_rate = 0.01"),
        reward("integrated_battlegroup", "Интегрированная боевая группа", "Integrated Battlegroup", "category_all_armor = { max_organisation = 3 breakthrough = 0.05 }", "category_all_infantry = { breakthrough = 0.03 }"),
    ),
    "armor_recon": (
        reward("scout_vehicles", "Разведывательные машины", "Scout Vehicles", "category_recon = { recon = 0.75 }"),
        reward("screened_flanks", "Прикрытые фланги", "Screened Flanks", "category_all_armor = { defense = 0.04 }"),
        reward("route_prediction", "Предиктивный выбор маршрута", "Predictive Route Selection", "category_all_armor = { maximum_speed = 0.03 }"),
        reward("target_handoff", "Передача целей", "Target Handoff", "coordination_bonus = 0.015"),
        reward("reconnaissance_strike", "Разведывательно-ударный контур", "Reconnaissance-strike Loop", "category_all_armor = { soft_attack = 0.05 breakthrough = 0.05 }", "category_recon = { recon = 1 }"),
    ),
    "armor_autonomy": (
        reward("crewless_scouts", "Безэкипажная разведка", "Crewless Scouts", "category_recon = { recon = 0.75 }"),
        reward("machine_pickets", "Машинное охранение", "Machine Pickets", "category_all_armor = { defense = 0.04 }"),
        reward("swarm_fire", "Распределённый огонь роя", "Distributed Swarm Fire", "category_all_armor = { soft_attack = 0.05 }"),
        reward("self_recovery", "Самоэвакуация машин", "Vehicle Self-recovery", "category_all_armor = { reliability = 0.05 default_morale = 0.03 }"),
        reward("autonomous_battlefield", "Автономный боевой контур", "Autonomous Battlespace", "category_all_armor = { breakthrough = 0.06 reliability = 0.04 }", "coordination_bonus = 0.02"),
    ),
    "network": (
        reward("recon_saturation", "Насыщение разведкой", "Reconnaissance Saturation", "category_recon = { recon = 1 }"),
        reward("predictive_planning", "Предиктивное планирование", "Predictive Planning", "planning_speed = 0.05", "max_planning = 0.02"),
        reward("integrated_fire", "Интегрированное управление огнём", "Integrated Fire Control", "coordination_bonus = 0.015", "category_support_battalions = { soft_attack = 0.03 }"),
        reward("command_cells", "Распределённые командные ячейки", "Distributed Command Cells", "land_reinforce_rate = 0.01"),
        reward("algorithmic_campaign", "Алгоритмическая кампания", "Algorithmic Campaigning", "coordination_bonus = 0.025", "planning_speed = 0.05"),
    ),
    "mission": (
        reward("intent_orders", "Приказы по замыслу", "Intent-based Orders", "planning_speed = 0.03"),
        reward("local_initiative", "Локальная инициатива", "Local Initiative", "land_reinforce_rate = 0.01"),
        reward("reserve_authority", "Делегирование резервов", "Delegated Reserves", "category_all_infantry = { default_morale = 0.03 }"),
        reward("fault_tolerant_staff", "Отказоустойчивые штабы", "Fault-tolerant Staffs", "coordination_bonus = 0.015"),
        reward("adaptive_command", "Адаптивное командование", "Adaptive Command", "planning_speed = 0.05", "land_reinforce_rate = 0.015", "coordination_bonus = 0.02"),
    ),
    "deep": (
        reward("operational_axes", "Операционные направления", "Operational Axes", "max_planning = 0.02"),
        reward("follow_on_echelons", "Эшелоны развития успеха", "Follow-on Echelons", "land_reinforce_rate = 0.01"),
        reward("rear_disruption", "Нарушение тыла", "Rear-area Disruption", "category_all_infantry = { breakthrough = 0.03 }"),
        reward("tempo_control", "Управление темпом", "Tempo Control", "org_loss_when_moving = -0.02"),
        reward("deep_campaign", "Глубокая кампания", "Deep Campaign", "planning_speed = 0.05", "max_planning = 0.03", "category_all_armor = { breakthrough = 0.05 }"),
    ),
    "fire_control": (
        reward("target_registry", "Единый реестр целей", "Common Target Registry", "coordination_bonus = 0.01"),
        reward("counterbattery", "Контрбатарейный цикл", "Counter-battery Cycle", "category_line_artillery = { soft_attack = 0.04 }"),
        reward("munition_timing", "Синхронизация боеприпасов", "Munition Timing", "category_support_battalions = { soft_attack = 0.03 }"),
        reward("fire_shift", "Быстрый перенос огня", "Rapid Fire Shift", "planning_speed = 0.03"),
        reward("theater_fire_network", "Театральная огневая сеть", "Theater Fire Network", "coordination_bonus = 0.025", "category_line_artillery = { soft_attack = 0.06 breakthrough = 0.03 }"),
    ),
    "fortress": (
        reward("urban_grids", "Городские узлы обороны", "Urban Defense Grids", "category_all_infantry = { entrenchment = 0.05 }"),
        reward("hardened_supply", "Защищённое снабжение", "Hardened Supply", "supply_consumption_factor = -0.015"),
        reward("contaminated_zones", "Действия в заражённых зонах", "Contaminated-zone Operations", "attrition = -0.02"),
        reward("counterattack_reserve", "Резерв контратаки", "Counterattack Reserve", "land_reinforce_rate = 0.01", "category_all_infantry = { breakthrough = 0.03 }"),
        reward("national_redoubt", "Национальный редут", "National Redoubt", "category_all_infantry = { defense = 0.07 max_organisation = 3 }", "dig_in_speed_factor = 0.06"),
    ),
    "artillery": (
        reward("forward_observers", "Передовые наблюдатели", "Forward Observers", "category_recon = { recon = 0.5 }"),
        reward("distributed_batteries", "Распределённые батареи", "Distributed Batteries", "category_line_artillery = { defense = 0.03 }"),
        reward("rapid_fireplans", "Быстрые огневые планы", "Rapid Fireplans", "planning_speed = 0.03"),
        reward("precision_barrages", "Точные огневые налёты", "Precision Barrages", "category_line_artillery = { soft_attack = 0.05 }"),
        reward("artillery_web", "Сеть артиллерийской поддержки", "Artillery Support Web", "category_line_artillery = { soft_attack = 0.06 breakthrough = 0.04 }", "coordination_bonus = 0.015"),
    ),
    "engineer": (
        reward("damage_surveys", "Оценка боевых повреждений", "Battle-damage Surveys", "industry_repair_factor = 0.02"),
        reward("breaching_teams", "Штурмовые группы разграждения", "Assault Breaching Teams", "engineer = { breakthrough = 0.04 }"),
        reward("mobile_bridges", "Мобильные переправы", "Mobile Bridging", "planning_speed = 0.02"),
        reward("robotic_clearance", "Роботизированное разминирование", "Robotic Clearance", "engineer = { defense = 0.04 breakthrough = 0.04 }"),
        reward("engineer_command", "Единое инженерное командование", "Engineer Command", "engineer = { defense = 0.06 breakthrough = 0.06 }", "category_support_battalions = { max_organisation = 2 }"),
    ),
    "logistics": (
        reward("route_audits", "Аудит маршрутов", "Route Audits", "supply_consumption_factor = -0.01"),
        reward("forward_pools", "Передовые фонды снабжения", "Forward Supply Pools", "org_loss_when_moving = -0.01"),
        reward("repair_columns", "Ремонтные колонны", "Repair Columns", "industry_repair_factor = 0.02"),
        reward("depot_dispersion", "Рассредоточение складов", "Depot Dispersion", "category_support_battalions = { defense = 0.03 }"),
        reward("resilient_theater", "Устойчивый тыл театра", "Resilient Theater Logistics", "supply_consumption_factor = -0.025", "land_reinforce_rate = 0.01", "category_support_battalions = { default_morale = 0.03 }"),
    ),
}


REWARD_PROFILES.update({
    "air_swarm": (
        reward("cheap_airframes", "Расходуемые планеры", "Expendable Airframes", "air_accidents_factor = -0.03"),
        reward("layered_screen", "Многоярусный рой", "Layered Swarm Screen", "air_superiority_efficiency = 0.03", "category_fighter = { air_defence = 0.03 }"),
        reward("target_marking", "Автономная маркировка целей", "Autonomous Target Marking", "air_cas_efficiency = 0.03", "category_cas = { air_ground_attack = 0.03 }"),
        reward("swarm_relay", "Ретрансляторы роя", "Swarm Relays", "air_mission_efficiency = 0.03"),
        reward("persistent_swarm", "Постоянное присутствие роя", "Persistent Swarm Presence", "air_mission_efficiency = 0.04", "air_superiority_efficiency = 0.04", "air_cas_efficiency = 0.04"),
    ),
    "air_attrition": (
        reward("modular_drones", "Модульные дроны", "Modular Drones", "air_accidents_factor = -0.03"),
        reward("replacement_waves", "Волны замены", "Replacement Waves", "air_mission_xp_gain_factor = 0.03"),
        reward("risk_tolerance", "Допустимый риск", "Acceptable Losses", "air_cas_efficiency = 0.03"),
        reward("mass_sorties", "Массовые вылеты", "Mass Sorties", "air_mission_efficiency = 0.04"),
        reward("attritional_saturation", "Истощающее насыщение", "Attritional Saturation", "air_superiority_efficiency = 0.05", "category_fighter = { air_attack = 0.04 }"),
    ),
    "air_autonomous": (
        reward("passive_sensors", "Пассивные сенсоры", "Passive Sensors", "air_interception_detect_factor = 0.03"),
        reward("machine_wingmen", "Машинные ведомые", "Machine Wingmen", "category_fighter = { air_agility = 0.03 }"),
        reward("distributed_control", "Распределённое управление", "Distributed Control", "air_mission_efficiency = 0.03"),
        reward("adaptive_intercepts", "Адаптивный перехват", "Adaptive Intercepts", "air_intercept_efficiency = 0.04"),
        reward("autonomous_air_screen", "Автономный воздушный экран", "Autonomous Air Screen", "category_fighter = { air_attack = 0.04 air_defence = 0.04 }", "air_superiority_efficiency = 0.04"),
    ),
    "air_vertical": (
        reward("precision_cas", "Точная непосредственная поддержка", "Precision Close Support", "air_cas_efficiency = 0.03", "category_cas = { air_ground_attack = 0.03 }"),
        reward("forward_liaisons", "Передовые авианаводчики", "Forward Air Liaisons", "army_bonus_air_superiority_factor = 0.03"),
        reward("strike_windows", "Окна глубокого удара", "Deep-strike Windows", "category_tac_bomber = { air_ground_attack = 0.03 }", "air_mission_xp_gain_factor = 0.03"),
        reward("landing_control", "Управление зонами высадки", "Landing-zone Control", "planning_speed = 0.025"),
        reward("vertical_battlegroup", "Вертикальная боевая группа", "Vertical Battlegroup", "air_cas_present_factor = 0.04", "air_cas_efficiency = 0.04", "land_reinforce_rate = 0.005"),
    ),
    "air_persistent": (
        reward("loiter_patterns", "Схемы длительного барражирования", "Persistent Loiter Patterns", "air_cas_present_factor = 0.03"),
        reward("rapid_retasking", "Быстрая смена задач", "Rapid Retasking", "air_mission_efficiency = 0.03"),
        reward("ground_relays", "Наземные ретрансляторы", "Ground Relays", "army_bonus_air_superiority_factor = 0.025"),
        reward("armed_overwatch", "Вооружённое патрулирование", "Armed Overwatch", "category_cas = { air_ground_attack = 0.04 }"),
        reward("continuous_support", "Непрерывная поддержка", "Continuous Support", "air_cas_efficiency = 0.05", "air_cas_present_factor = 0.04"),
    ),
    "air_airlift": (
        reward("airlift_tables", "Таблицы воздушных перевозок", "Airlift Tables", "air_mission_efficiency = 0.02"),
        reward("forward_basing", "Передовое базирование", "Forward Basing", "air_power_projection_factor = 0.03"),
        reward("aerial_resupply", "Точное воздушное снабжение", "Precision Aerial Resupply", "supply_consumption_factor = -0.01"),
        reward("airbridge", "Постоянный воздушный мост", "Persistent Airbridge", "air_mission_efficiency = 0.04"),
        reward("theater_mobility", "Мобильность театра", "Theater Mobility", "air_power_projection_factor = 0.04", "air_mission_efficiency = 0.04", "land_reinforce_rate = 0.005"),
    ),
    "air_intercept": (
        reward("hardened_airfields", "Защищённые аэродромы", "Hardened Airfields", "air_accidents_factor = -0.03", "air_home_defence_factor = 0.03"),
        reward("denial_zones", "Зоны воздушного запрета", "Air-denial Zones", "air_interception_detect_factor = 0.03", "category_fighter = { air_attack = 0.03 }"),
        reward("warning_network", "Сеть раннего предупреждения", "Early-warning Network", "air_intercept_efficiency = 0.03", "air_power_projection_factor = 0.03"),
        reward("interceptor_rotation", "Ротация перехватчиков", "Interceptor Rotation", "category_fighter = { air_defence = 0.03 }"),
        reward("closed_airspace", "Закрытое воздушное пространство", "Closed Airspace", "air_intercept_efficiency = 0.05", "air_home_defence_factor = 0.04"),
    ),
    "air_missile": (
        reward("launch_detection", "Обнаружение пусков", "Launch Detection", "air_interception_detect_factor = 0.04"),
        reward("dispersed_batteries", "Рассредоточенные батареи", "Dispersed Batteries", "air_home_defence_factor = 0.03"),
        reward("defense_cues", "Передача целеуказания ПВО", "Air-defense Cueing", "air_intercept_efficiency = 0.03"),
        reward("hardened_nodes", "Защищённые узлы управления", "Hardened Control Nodes", "air_accidents_factor = -0.02"),
        reward("layered_defense", "Эшелонированная противовоздушная оборона", "Layered Air Defense", "air_home_defence_factor = 0.05", "air_interception_detect_factor = 0.05"),
    ),
    "air_ewar": (
        reward("threat_libraries", "Библиотеки излучателей", "Emitter Libraries", "decryption_factor = 0.02"),
        reward("spoofed_corridors", "Ложные воздушные коридоры", "Spoofed Air Corridors", "air_mission_efficiency = 0.025"),
        reward("hardened_waveforms", "Защищённые сигналы", "Hardened Waveforms", "encryption_factor = 0.03"),
        reward("jamming_swarms", "Рои подавления", "Jamming Swarms", "enemy_army_bonus_air_superiority_factor = -0.02"),
        reward("spectrum_control", "Контроль спектра", "Spectrum Control", "encryption_factor = 0.04", "decryption_factor = 0.04", "air_intercept_efficiency = 0.03"),
    ),
    "naval_littoral": (
        reward("coastal_watch", "Береговые посты наблюдения", "Coastal Watch Posts", "navy_intel_factor = 0.03"),
        reward("mine_drills", "Минно-тральные учения", "Mine-countermeasure Drills", "mines_sweeping_by_fleets_factor = 0.06"),
        reward("screen_coordination", "Координация охранения", "Screen Coordination", "screening_efficiency = 0.03"),
        reward("shallow_patrols", "Мелководные патрули", "Shallow-water Patrols", "naval_detection = 0.03"),
        reward("littoral_network", "Единая прибрежная сеть", "Integrated Littoral Network", "screening_efficiency = 0.04", "naval_detection = 0.04", "mines_sweeping_by_fleets_factor = 0.06"),
    ),
    "naval_escort": (
        reward("escort_routing", "Маршрутизация эскортов", "Escort Routing", "convoy_escort_efficiency = 0.03"),
        reward("sailing_orders", "Аварийные приказы конвоям", "Emergency Sailing Orders", "convoy_retreat_speed = 0.03"),
        reward("repair_crews", "Ремонтные команды", "Repair Crews", "navy_max_range_factor = 0.03"),
        reward("hunter_groups", "Поисковые группы", "Hunter Groups", "naval_detection = 0.03"),
        reward("protected_sealane", "Защищённые морские коммуникации", "Protected Sea Lanes", "convoy_escort_efficiency = 0.05", "screening_efficiency = 0.03"),
    ),
    "naval_mines": (
        reward("surveyed_channels", "Промеренные фарватеры", "Surveyed Channels", "naval_mines_effect_reduction = 0.04"),
        reward("rapid_laying", "Быстрая постановка заграждений", "Rapid Mine Laying", "naval_mine_hit_chance = 0.03"),
        reward("remote_minefields", "Дистанционные минные поля", "Remote Minefields", "naval_coordination = 0.01"),
        reward("sweeper_escorts", "Охранение тральщиков", "Minesweeper Escorts", "mines_sweeping_by_fleets_factor = 0.05"),
        reward("controlled_waters", "Контролируемые воды", "Controlled Waters", "naval_mine_hit_chance = 0.05", "naval_mines_effect_reduction = 0.05"),
    ),
    "naval_carrier": (
        reward("deck_drones", "Дроны палубного управления", "Deck-control Drones", "navy_carrier_air_agility_factor = 0.03"),
        reward("strike_coordination", "Координация удара", "Strike Coordination", "naval_strike_attack_factor = 0.03"),
        reward("drone_maintenance", "Обслуживание палубных дронов", "Drone Maintenance", "air_accidents_factor = -0.02"),
        reward("distributed_decks", "Распределённые палубные группы", "Distributed Deck Groups", "naval_coordination = 0.015"),
        reward("carrier_mesh", "Сетевая авианосная группа", "Networked Carrier Group", "naval_strike_attack_factor = 0.05", "navy_carrier_air_agility_factor = 0.04"),
    ),
    "naval_missile": (
        reward("over_horizon", "Загоризонтное целеуказание", "Over-the-horizon Targeting", "naval_detection = 0.03"),
        reward("salvo_timing", "Синхронизация залпа", "Salvo Timing", "naval_hit_chance = 0.025"),
        reward("screened_launchers", "Прикрытые носители ракет", "Screened Missile Ships", "screening_efficiency = 0.03"),
        reward("cooperative_fire", "Кооперативное поражение", "Cooperative Engagement", "naval_coordination = 0.02"),
        reward("saturation_salvo", "Насыщающий залп", "Saturation Salvo", "naval_hit_chance = 0.04", "naval_coordination = 0.025"),
    ),
    "naval_support": (
        reward("landing_tables", "Таблицы десантной операции", "Landing Tables", "naval_invasion_prep_speed = 0.04"),
        reward("shore_observers", "Береговые наблюдатели", "Shore Observers", "shore_bombardment_bonus = 0.03"),
        reward("fire_corridors", "Коридоры корабельного огня", "Naval Fire Corridors", "naval_coordination = 0.015"),
        reward("floating_depots", "Плавучие склады", "Floating Depots", "supply_consumption_factor = -0.01"),
        reward("coastal_fire_command", "Командование береговой поддержки", "Coastal Fire Command", "shore_bombardment_bonus = 0.06", "naval_invasion_penalty = -0.03"),
    ),
    "naval_sub": (
        reward("quiet_approach", "Скрытный подход", "Quiet Approaches", "convoy_raiding_efficiency_factor = 0.03"),
        reward("ambush_grids", "Сетки засад", "Ambush Grids", "navy_submarine_attack_factor = 0.03"),
        reward("torpedo_cells", "Распределённые торпедные ячейки", "Distributed Torpedo Cells", "naval_hit_chance = 0.02"),
        reward("silent_withdrawal", "Скрытый отход", "Silent Withdrawal", "navy_submarine_defence_factor = 0.03"),
        reward("subsurface_denial", "Подводное воспрещение", "Subsurface Denial", "convoy_raiding_efficiency_factor = 0.05", "navy_submarine_attack_factor = 0.05"),
    ),
    "naval_silent": (
        reward("passive_sonar", "Пассивное наблюдение", "Passive Sonar", "naval_detection = 0.025"),
        reward("thermal_layers", "Использование термоклина", "Thermal-layer Tactics", "navy_submarine_defence_factor = 0.03"),
        reward("patient_hunters", "Терпеливые охотники", "Patient Hunters", "convoy_raiding_efficiency_factor = 0.03"),
        reward("coordinated_ambush", "Координированная засада", "Coordinated Ambush", "naval_coordination = 0.015"),
        reward("silent_sea", "Безмолвное море", "Silent Sea", "navy_submarine_attack_factor = 0.04", "navy_submarine_defence_factor = 0.04", "naval_detection = 0.03"),
    ),
    "naval_seabed": (
        reward("bottom_arrays", "Донные сенсорные поля", "Seabed Sensor Arrays", "naval_detection = 0.03"),
        reward("autonomous_hunters", "Автономные подводные охотники", "Autonomous Subsea Hunters", "navy_submarine_attack_factor = 0.03"),
        reward("data_fusion", "Слияние гидроакустических данных", "Sonar Data Fusion", "naval_coordination = 0.015"),
        reward("closing_routes", "Перекрытие подводных маршрутов", "Closing Subsea Routes", "convoy_raiding_efficiency_factor = 0.03"),
        reward("seabed_control", "Контроль подводной среды", "Seabed Control", "naval_detection = 0.05", "navy_submarine_attack_factor = 0.04"),
    ),
    "sf_mountain": (
        reward("cold_acclimation", "Холодовая акклиматизация", "Cold Acclimatization", "acclimatization_cold_climate_gain_factor = 0.08"),
        reward("light_columns", "Облегчённые колонны", "Light Columns", "category_special_forces = { supply_consumption = -0.02 }"),
        reward("ridge_positions", "Позиции на гребнях", "Ridge Positions", "category_special_forces = { defense = 0.04 }"),
        reward("vertical_routes", "Вертикальные маршруты", "Vertical Routes", "category_special_forces = { maximum_speed = 0.03 }"),
        reward("highland_mastery", "Господство в высокогорье", "Highland Mastery", "category_special_forces = { defense = 0.06 soft_attack = 0.04 max_organisation = 3 }"),
    ),
    "sf_contaminated": (
        reward("sealed_patrols", "Герметичные патрули", "Sealed Patrols", "attrition = -0.015"),
        reward("dose_rotation", "Ротация по дозовой нагрузке", "Exposure Rotation", "category_special_forces = { default_morale = 0.03 }"),
        reward("ruin_navigation", "Навигация в мёртвых зонах", "Dead-zone Navigation", "category_special_forces = { maximum_speed = 0.02 }"),
        reward("protected_supply", "Защищённое снабжение", "Protected Supply", "category_special_forces = { supply_consumption = -0.02 }"),
        reward("dead_zone_raiders", "Рейдеры мёртвых зон", "Dead-zone Raiders", "attrition = -0.025", "category_special_forces = { breakthrough = 0.05 defense = 0.05 }"),
    ),
    "sf_urban": (
        reward("building_recon", "Разведка зданий", "Building Reconnaissance", "category_recon = { recon = 0.5 }"),
        reward("breach_cells", "Ячейки пролома", "Breach Cells", "category_special_forces = { breakthrough = 0.04 }"),
        reward("vertical_clearance", "Вертикальная зачистка", "Vertical Clearance", "category_special_forces = { soft_attack = 0.04 }"),
        reward("isolated_strongpoints", "Изоляция опорных пунктов", "Isolated Strongpoints", "planning_speed = 0.025"),
        reward("urban_assault", "Городская штурмовая группа", "Urban Assault Group", "category_special_forces = { breakthrough = 0.06 soft_attack = 0.06 max_organisation = 2 }"),
    ),
    "sf_recon": (
        reward("deep_observation", "Глубокое наблюдение", "Deep Observation", "category_recon = { recon = 0.75 }"),
        reward("hidden_relays", "Скрытые ретрансляторы", "Hidden Relays", "coordination_bonus = 0.01"),
        reward("target_handover", "Передача целей", "Target Handover", "category_support_battalions = { soft_attack = 0.025 }"),
        reward("stay_behind", "Оставленные группы", "Stay-behind Teams", "category_special_forces = { supply_consumption = -0.02 }"),
        reward("theater_recon", "Разведка театра", "Theater Reconnaissance", "category_recon = { recon = 1 }", "planning_speed = 0.04", "coordination_bonus = 0.015"),
    ),
    "sf_vertical": (
        reward("landing_beacons", "Маяки высадки", "Landing Beacons", "planning_speed = 0.02"),
        reward("airmobile_supply", "Аэромобильное снабжение", "Airmobile Supply", "category_special_forces = { supply_consumption = -0.02 }"),
        reward("rapid_concentration", "Быстрое сосредоточение", "Rapid Concentration", "land_reinforce_rate = 0.005"),
        reward("assault_landing", "Штурмовая высадка", "Assault Landing", "category_special_forces = { breakthrough = 0.05 }"),
        reward("vertical_envelopment", "Вертикальный охват", "Vertical Envelopment", "category_special_forces = { breakthrough = 0.06 maximum_speed = 0.03 }", "planning_speed = 0.03"),
    ),
    "sf_autonomous": (
        reward("machine_scouts", "Машинные разведчики", "Machine Scouts", "category_recon = { recon = 0.75 }"),
        reward("distributed_cells", "Распределённые ячейки", "Distributed Cells", "category_special_forces = { defense = 0.03 }"),
        reward("remote_fire", "Дистанционная огневая поддержка", "Remote Fire Support", "category_special_forces = { soft_attack = 0.04 }"),
        reward("self_sustaining_teams", "Автономные группы", "Self-sustaining Teams", "category_special_forces = { supply_consumption = -0.025 }"),
        reward("autonomous_raiders", "Автономные рейдеры", "Autonomous Raiders", "category_special_forces = { soft_attack = 0.05 breakthrough = 0.05 max_organisation = 3 }", "coordination_bonus = 0.015"),
    ),
})


SCHOOLS = (
    # Land: four competing schools for every operational track.
    School("ADISCORD_doctrine_mass_recruitment_bureaus", "land", "ADISCORD_land_mass_restoration", "Бюро массового развёртывания", "Mass Mobilization Bureaus", "Стандартизированные кадры превращают многочисленные пополнения в устойчивые линейные части.", "Standardized cadres turn large replacement pools into durable line formations.", "GFX_doctrine_mass_assault_medium", "ADISCORD_has_military_standardization_tech = yes", ("category_all_infantry = { max_organisation = 2 }", "land_reinforce_rate = 0.005"), "mass", ("modifier = { factor = 1.6 has_manpower > 50000 }",), ("ADISCORD_doctrine_salvage_line_infantry", "ADISCORD_doctrine_distributed_militias", "ADISCORD_doctrine_emergency_replacement_system", "ADISCORD_doctrine_total_restoration_front", "ADISCORD_doctrine_people_and_scrap")),
    School("ADISCORD_doctrine_assault_detachments", "land", "ADISCORD_land_mass_restoration", "Штурмовые отряды", "Assault Detachments", "Специализированные штурмовые группы вскрывают укреплённый участок и передают прорыв линейным частям.", "Specialized assault groups open fortified sectors for exploitation by line formations.", "GFX_doctrine_assault_infantry_medium", "has_tech = ADISCORD_tech_assault_breaching_packages", ("category_all_infantry = { breakthrough = 0.03 }", "planning_speed = 0.02"), "assault", ("modifier = { factor = 1.8 has_war = yes }",)),
    School("ADISCORD_doctrine_mobile_line_groups", "land", "ADISCORD_land_mass_restoration", "Мобильные линейные группы", "Mobile Line Groups", "Моторизованные резервы закрывают прорывы и поддерживают темп наступления без перехода к тяжёлой броне.", "Motorized reserves close breaches and sustain operational tempo without relying on heavy armor.", "GFX_doctrine_mobile_infantry_medium", "has_tech = ADISCORD_tech_standardized_transport_columns", ("category_all_infantry = { maximum_speed = 0.02 }", "org_loss_when_moving = -0.01"), "mobile", ("modifier = { factor = 1.5 has_tech = ADISCORD_tech_forward_supply_hubs }",)),
    School("ADISCORD_doctrine_dispersed_militia_system", "land", "ADISCORD_land_mass_restoration", "Рассредоточенная система ополчения", "Dispersed Militia System", "Местные кадры, скрытые склады и простые планы обороны позволяют слабой промышленности удерживать пространство.", "Local cadres, hidden stocks, and simple defense plans let a weak industry hold territory.", "GFX_doctrine_defensive_postures_medium", "has_tech = ADISCORD_tech_fieldcraft_manuals", ("category_all_infantry = { defense = 0.04 }", "dig_in_speed_factor = 0.02"), "militia", ("modifier = { factor = 1.5 num_of_military_factories < 8 }",)),

    School("ADISCORD_doctrine_platform_battlegroups", "land", "ADISCORD_land_platform_centric", "Танковые боевые группы", "Armored Battlegroups", "Танковые части концентрируются для короткого решающего прорыва под прикрытием разведки и ремонта.", "Armored formations concentrate for a short decisive breakthrough under reconnaissance and recovery cover.", "GFX_doctrine_armored_spearhead_medium", "has_tech = ADISCORD_tech_restored_armored_chassis", ("category_all_armor = { max_organisation = 2 breakthrough = 0.03 }",), "armor_breakthrough", ("modifier = { factor = 2 has_tech = ADISCORD_tech_remote_weapon_stations }",), ("ADISCORD_doctrine_remote_weapon_coordination", "ADISCORD_doctrine_heavy_breakthrough_columns", "ADISCORD_doctrine_drone_screened_advance", "ADISCORD_doctrine_autonomous_repair_cycles", "ADISCORD_doctrine_armored_decision_warfare")),
    School("ADISCORD_doctrine_armored_spearhead_command", "land", "ADISCORD_land_platform_centric", "Командование танкового клина", "Armored Spearhead Command", "Небольшое число лучших танковых соединений пробивает фронт и удерживает инициативу до ввода резервов.", "A small number of elite armored formations rupture the front and retain initiative until reserves arrive.", "GFX_doctrine_armored_cavalry_medium", "has_tech = ADISCORD_tech_composite_armor_arrays", ("category_tanks = { breakthrough = 0.05 }", "max_planning = 0.01"), "armor_breakthrough", ("modifier = { factor = 1.5 num_of_military_factories > 12 }",)),
    School("ADISCORD_doctrine_infantry_tank_integration", "land", "ADISCORD_land_platform_centric", "Интеграция пехоты и танков", "Infantry-tank Integration", "Танки не действуют отдельно: пехота, сапёры и машины образуют устойчивую общевойсковую группу.", "Armor no longer fights alone: infantry, engineers, and vehicles form a durable combined-arms group.", "GFX_doctrine_armored_infantry_support_medium", "has_tech = ADISCORD_tech_armored_platoon_target_handoff", ("category_all_armor = { defense = 0.03 }", "category_all_infantry = { breakthrough = 0.02 }"), "armor_integration", ("modifier = { factor = 1.5 has_tech = ADISCORD_tech_combat_engineering_sections }",)),
    School("ADISCORD_doctrine_autonomous_armored_screen", "land", "ADISCORD_land_platform_centric", "Автономный танковый экран", "Autonomous Armored Screen", "Безэкипажные машины принимают на себя разведку, охранение и часть огневых задач танковой группы.", "Crewless vehicles assume reconnaissance, screening, and part of an armored group's fire mission.", "GFX_mechanised_offensive_medium", "has_tech = ADISCORD_tech_armed_recon_drones", ("category_all_armor = { reliability = 0.03 }", "category_recon = { recon = 0.5 }"), "armor_autonomy", ("modifier = { factor = 2 has_tech = ADISCORD_tech_distributed_ground_swarm_control }",)),

    School("ADISCORD_doctrine_mesh_battlefield_command", "land", "ADISCORD_land_networked_operations", "Сетевое управление полем боя", "Mesh Battlefield Command", "Датчики, штабы и огневые средства сводятся в один устойчивый контур управления.", "Sensors, staffs, and fire assets share a single resilient command mesh.", "GFX_doctrine_mission_type_tactics_medium", "ADISCORD_has_cyber_command_tech = yes", ("coordination_bonus = 0.015", "planning_speed = 0.02"), "network", ("modifier = { factor = 2 has_tech = ADISCORD_tech_mesh_command_networks }",), ("ADISCORD_doctrine_reconnaissance_saturation", "ADISCORD_doctrine_predictive_operational_planning", "ADISCORD_doctrine_integrated_fire_control", "ADISCORD_doctrine_distributed_command_cells", "ADISCORD_doctrine_algorithmic_campaigning")),
    School("ADISCORD_doctrine_mission_command", "land", "ADISCORD_land_networked_operations", "Командование по замыслу", "Mission Command", "Младшие командиры получают свободу исполнения общего замысла и быстрее реагируют на разрушение связи.", "Junior commanders execute the common intent independently and react faster when communications fail.", "GFX_doctrine_mission_type_tactics_medium", "has_tech = ADISCORD_tech_reconstituted_staff_academies", ("land_reinforce_rate = 0.005", "category_all_infantry = { default_morale = 0.02 }"), "mission", ("modifier = { factor = 1.5 has_war = yes }",)),
    School("ADISCORD_doctrine_deep_operations", "land", "ADISCORD_land_networked_operations", "Глубокие операции", "Deep Operations", "Последовательные эшелоны разрушают не только передний край, но и снабжение, резервы и управление противника.", "Successive echelons attack not only the front line but also enemy supply, reserves, and command.", "GFX_doctrine_deep_battle_medium", "has_tech = ADISCORD_tech_operational_planning_exercises", ("max_planning = 0.02", "category_all_armor = { breakthrough = 0.03 }"), "deep", ("modifier = { factor = 1.5 num_of_military_factories > 10 }",)),
    School("ADISCORD_doctrine_centralized_fire_control", "land", "ADISCORD_land_networked_operations", "Централизованное управление огнём", "Centralized Fire Control", "Единый реестр целей позволяет быстро собирать артиллерию и поддержку на решающем участке.", "A shared target registry rapidly concentrates artillery and support assets on the decisive sector.", "GFX_doctrine_fire_concentration_medium", "has_tech = ADISCORD_tech_smart_fire_control", ("category_line_artillery = { soft_attack = 0.03 }", "coordination_bonus = 0.01"), "fire_control", ("modifier = { factor = 1.5 has_tech = ADISCORD_tech_counterbattery_radar_links }",)),

    School("ADISCORD_doctrine_fortress_state_command", "land", "ADISCORD_land_fortress_state", "Командование государства-крепости", "Fortress-state Command", "Инфраструктура, населённые пункты и резервы заранее превращаются в глубоко эшелонированную оборону.", "Infrastructure, settlements, and reserves are prepared as a defense in depth before the battle begins.", "GFX_doctrine_defensive_postures_medium", "ADISCORD_has_civil_resilience_tech = yes", ("dig_in_speed_factor = 0.04", "category_all_infantry = { defense = 0.04 }"), "fortress", ("modifier = { factor = 1.8 has_war = yes }",), ("ADISCORD_doctrine_urban_defense_grids", "ADISCORD_doctrine_hardened_logistics", "ADISCORD_doctrine_radiation_zone_operations", "ADISCORD_doctrine_counteroffensive_reserves", "ADISCORD_doctrine_national_redoubt_protocols")),
    School("ADISCORD_doctrine_artillery_support_network", "land", "ADISCORD_land_fortress_state", "Сеть артиллерийской поддержки", "Artillery Support Network", "Распределённые батареи получают общие данные и могут поддерживать соседние участки без длительной подготовки.", "Distributed batteries share targeting data and support adjacent sectors without lengthy preparation.", "GFX_doctrine_fire_concentration_medium", "has_tech = ADISCORD_tech_restored_field_artillery", ("category_line_artillery = { soft_attack = 0.04 }", "planning_speed = 0.015"), "artillery", ("modifier = { factor = 1.8 has_tech = ADISCORD_tech_drone_spotted_batteries }",)),
    School("ADISCORD_doctrine_combat_engineer_groups", "land", "ADISCORD_land_fortress_state", "Боевые инженерные группы", "Combat Engineer Groups", "Сапёры одновременно ускоряют наступление, восстанавливают пути и готовят позиции для удержания плацдарма.", "Engineers accelerate the advance, restore routes, and prepare positions to hold the bridgehead.", "GFX_doctrine_field_engineering_medium", "has_tech = ADISCORD_tech_battle_damage_survey_teams", ("engineer = { breakthrough = 0.04 defense = 0.03 }", "industry_repair_factor = 0.02"), "engineer", ("modifier = { factor = 2 has_tech = ADISCORD_tech_robotic_obstacle_clearance }",)),
    School("ADISCORD_doctrine_resilient_logistics_command", "land", "ADISCORD_land_fortress_state", "Командование устойчивого тыла", "Resilient Logistics Command", "Рассредоточенные склады, ремонтные колонны и запасные маршруты поддерживают армию после ударов по тылу.", "Dispersed depots, repair columns, and alternate routes sustain the army after attacks on its rear.", "GFX_tech_logistics_company_medium", "has_tech = ADISCORD_tech_theater_logistics_wargames", ("supply_consumption_factor = -0.015", "category_support_battalions = { defense = 0.02 }"), "logistics", ("modifier = { factor = 1.7 has_tech = ADISCORD_tech_hardened_logistics_nodes }",)),

    # Air: three choices for each mastery track.
    School("ADISCORD_air_doctrine_swarm_recon", "air", "ADISCORD_air_drone_swarm", "Роевая разведка", "Swarm Reconnaissance", "Дешёвые беспилотники непрерывно обновляют обстановку и передают цели ударной авиации.", "Cheap drones continuously update the battlespace and hand targets to strike aviation.", "GFX_doctrine_forward_interception_medium", "has_tech = ADISCORD_tech_drone_air_wings", ("air_mission_efficiency = 0.025", "air_interception_detect_factor = 0.02"), "air_swarm", ("modifier = { factor = 2 has_tech = ADISCORD_tech_drone_air_wings }",), ("ADISCORD_air_doctrine_disposable_airframes", "ADISCORD_air_doctrine_layered_drone_screen", "ADISCORD_air_doctrine_autonomous_target_marking")),
    School("ADISCORD_air_doctrine_attritional_drone_swarms", "air", "ADISCORD_air_drone_swarm", "Истощающие дроновые рои", "Attritional Drone Swarms", "Массовые дешёвые аппараты вынуждают противника расходовать дорогие перехватчики и боеприпасы.", "Mass-produced cheap aircraft force the enemy to expend costly interceptors and munitions.", "GFX_doctrine_air_skirmish_medium", "has_tech = ADISCORD_tech_loitering_strike_drones", ("air_superiority_efficiency = 0.03", "air_mission_xp_gain_factor = 0.02"), "air_attrition", ("modifier = { factor = 1.7 num_of_military_factories > 8 }",)),
    School("ADISCORD_air_doctrine_autonomous_air_screen", "air", "ADISCORD_air_drone_swarm", "Автономный воздушный экран", "Autonomous Air Screen", "Машинные ведомые и распределённые сенсоры прикрывают пилотируемые самолёты и воздушные узлы.", "Machine wingmen and distributed sensors shield crewed aircraft and key air nodes.", "GFX_fighter_sweeps_medium", "has_tech = ADISCORD_tech_loyal_wingmen", ("category_fighter = { air_defence = 0.03 air_agility = 0.02 }",), "air_autonomous", ("modifier = { factor = 2 has_tech = ADISCORD_tech_autonomous_dogfight_controller }",)),

    School("ADISCORD_air_doctrine_vtol_assault_groups", "air", "ADISCORD_air_vtol_deep_strike", "Штурмовые группы VTOL", "VTOL Assault Groups", "Вертикальный манёвр связывает непосредственную поддержку, переброску и быстрый захват ключевых точек.", "Vertical maneuver combines close support, movement, and rapid seizure of key terrain.", "GFX_doctrine_low_echelon_support_medium", "has_tech = ADISCORD_tech_vtol_assault_frames", ("air_cas_present_factor = 0.04", "planning_speed = 0.02"), "air_vertical", ("modifier = { factor = 2 has_tech = ADISCORD_tech_vtol_assault_frames }",), ("ADISCORD_air_doctrine_precision_cas", "ADISCORD_air_doctrine_forward_air_liaisons", "ADISCORD_air_doctrine_deep_strike_windows")),
    School("ADISCORD_air_doctrine_persistent_close_support", "air", "ADISCORD_air_vtol_deep_strike", "Постоянная непосредственная поддержка", "Persistent Close Support", "Авиация постоянно дежурит над фронтом и меняет задачу по запросу наземных частей.", "Aircraft remain on station over the front and retask on demand from ground formations.", "GFX_doctrine_direct_ground_support_medium", "has_tech = ADISCORD_tech_cooperative_close_air_control_links", ("air_cas_efficiency = 0.035", "air_cas_present_factor = 0.025"), "air_persistent", ("modifier = { factor = 1.7 has_war = yes }",)),
    School("ADISCORD_air_doctrine_theater_air_mobility", "air", "ADISCORD_air_vtol_deep_strike", "Воздушная мобильность театра", "Theater Air Mobility", "Воздушные мосты и передовые площадки позволяют быстро менять направление главного усилия.", "Airbridges and forward landing sites rapidly shift the theater's main effort.", "GFX_bomber_ace_initiative_medium", "has_tech = ADISCORD_tech_restored_airlift_planning", ("air_mission_efficiency = 0.025", "supply_consumption_factor = -0.005"), "air_airlift", ("modifier = { factor = 2 has_tech = ADISCORD_tech_vertical_envelopment_control }",)),

    School("ADISCORD_air_doctrine_interceptor_grids", "air", "ADISCORD_air_strategic_denial", "Сети перехвата", "Interceptor Grids", "Распределённые радары и дежурные звенья закрывают воздушное пространство над важнейшими районами.", "Distributed radars and alert flights close the airspace over critical regions.", "GFX_doctrine_forward_interception_medium", "has_tech = ADISCORD_tech_high_altitude_interceptors", ("air_intercept_efficiency = 0.04", "air_home_defence_factor = 0.025"), "air_intercept", ("modifier = { factor = 2 has_tech = ADISCORD_tech_high_altitude_interceptors }",), ("ADISCORD_air_doctrine_hardened_airfields", "ADISCORD_air_doctrine_strategic_denial_zones", "ADISCORD_air_doctrine_rocket_warning_network")),
    School("ADISCORD_air_doctrine_layered_missile_defense", "air", "ADISCORD_air_strategic_denial", "Эшелонированная ракетная оборона", "Layered Missile Defense", "Пассивное обнаружение и рассредоточенные батареи защищают промышленность от ракет и высотных ударов.", "Passive detection and dispersed batteries protect industry from missiles and high-altitude strikes.", "GFX_doctrine_home_defence_medium", "has_tech = ADISCORD_tech_integrated_short_range_missile_cells", ("air_interception_detect_factor = 0.03", "air_home_defence_factor = 0.03"), "air_missile", ("modifier = { factor = 1.8 has_tech = ADISCORD_tech_predictive_airspace_denial_grid }",)),
    School("ADISCORD_air_doctrine_electronic_suppression", "air", "ADISCORD_air_strategic_denial", "Радиоэлектронное подавление", "Electronic Suppression", "Наступательное подавление ослабляет управление вражеской авиацией, а защищённые сигналы сохраняют своё.", "Offensive jamming disrupts enemy aviation while hardened waveforms preserve friendly control.", "GFX_doctrine_formation_flying_medium", "has_tech = ADISCORD_tech_offensive_jamming_cells", ("decryption_factor = 0.025", "enemy_army_bonus_air_superiority_factor = -0.01"), "air_ewar", ("modifier = { factor = 2 has_tech = ADISCORD_tech_adaptive_spectrum_dominance }",)),

    # Naval: capability-gated littoral, surface, and subsurface schools.
    School("ADISCORD_naval_doctrine_littoral_security_network", "sea", "ADISCORD_naval_littoral_security", "Сеть прибрежной безопасности", "Littoral Security Network", "Наблюдательные посты, тральщики и малые корабли создают устойчивый контур защиты побережья.", "Watch posts, minesweepers, and small combatants form a resilient coastal security network.", "GFX_doctrine_escort_patrols_medium", "has_tech = ADISCORD_tech_coastal_patrols", ("screening_efficiency = 0.04", "mines_sweeping_by_fleets_factor = 0.05"), "naval_littoral", ("modifier = { factor = 1.6 has_war = yes }",), ("coastal_watch_posts", "minefield_drills", "screen_coordination")),
    School("ADISCORD_naval_doctrine_convoy_shield_doctrine", "sea", "ADISCORD_naval_littoral_security", "Доктрина защиты конвоев", "Convoy Shield Doctrine", "Эскорты, маршрутизация и поисковые группы сохраняют морские коммуникации под постоянной угрозой.", "Escorts, routing, and hunter groups preserve sea lanes under persistent threat.", "GFX_doctrine_convoy_sailing_medium", "has_tech = ADISCORD_tech_convoy_routing", ("convoy_escort_efficiency = 0.06", "convoy_retreat_speed = 0.03"), "naval_escort", ("modifier = { factor = 1.8 has_war = yes }",), ("escort_routing", "emergency_sailing_orders", "repair_crews")),
    School("ADISCORD_naval_doctrine_mine_warfare_command", "sea", "ADISCORD_naval_littoral_security", "Командование минной войны", "Mine Warfare Command", "Управляемые заграждения закрывают подходы, а специализированные силы сохраняют собственные фарватеры.", "Controlled minefields close enemy approaches while specialist forces preserve friendly channels.", "GFX_basic_naval_mines_medium", "has_tech = ADISCORD_tech_unmanned_mine_countermeasure_boats", ("naval_mine_hit_chance = 0.03", "naval_mines_effect_reduction = 0.03"), "naval_mines", ("modifier = { factor = 1.7 has_war = yes }",)),

    School("ADISCORD_naval_doctrine_drone_carrier_groups", "sea", "ADISCORD_naval_surface_control", "Дроновые авианосные группы", "Drone Carrier Groups", "Палубные беспилотники дают флоту разведку, удар и противовоздушное прикрытие без крупного авиакрыла.", "Carrier drones provide fleet reconnaissance, strike, and air cover without a large crewed air wing.", "GFX_doctrine_carrier_battlegroups_medium", "has_tech = ADISCORD_tech_drone_carrier_deck_systems", ("navy_carrier_air_agility_factor = 0.04", "naval_strike_attack_factor = 0.03"), "naval_carrier", ("modifier = { factor = 2 has_tech = ADISCORD_tech_drone_carrier_deck_systems }",), ("deck_control_drones", "strike_coordination", "drone_maintenance")),
    School("ADISCORD_naval_doctrine_missile_surface_groups", "sea", "ADISCORD_naval_surface_control", "Ракетные надводные группы", "Missile Surface Groups", "Распределённые пусковые установки проводят согласованный залп по данным внешнего целеуказания.", "Distributed launchers execute coordinated salvos using off-board targeting data.", "GFX_doctrine_floating_fortress_medium", "has_tech = ADISCORD_tech_missile_batteries", ("naval_hit_chance = 0.025", "naval_coordination = 0.01"), "naval_missile", ("modifier = { factor = 1.8 has_tech = ADISCORD_tech_networked_task_groups }",)),
    School("ADISCORD_naval_doctrine_coastal_fire_support", "sea", "ADISCORD_naval_surface_control", "Корабельная поддержка побережья", "Coastal Fire Support", "Флот связывает высадку, корабельный огонь и плавучие склады в единую операцию на побережье.", "The fleet unifies landing forces, naval gunfire, and floating depots in one coastal operation.", "GFX_doctrine_base_strike_medium", "has_tech = ADISCORD_tech_modular_landing_causeways", ("shore_bombardment_bonus = 0.04", "naval_invasion_prep_speed = 0.03"), "naval_support", ("modifier = { factor = 2 has_tech = ADISCORD_tech_autonomous_littoral_fire_control }",)),

    School("ADISCORD_naval_doctrine_subsurface_denial", "sea", "ADISCORD_naval_subsurface_warfare", "Подводное воспрещение", "Subsurface Denial", "Подводные лодки атакуют снабжение и вынуждают противника постоянно держать силы охранения.", "Submarines attack supply and force the enemy to maintain continuous escort coverage.", "GFX_doctrine_wolfpacks_medium", "has_tech = ADISCORD_tech_homing_torpedoes", ("convoy_raiding_efficiency_factor = 0.06", "navy_submarine_attack_factor = 0.03"), "naval_sub", ("modifier = { factor = 1.8 has_war = yes }",), ("quiet_approaches", "ambush_grids", "salvage_torpedo_cells")),
    School("ADISCORD_naval_doctrine_silent_ambush_groups", "sea", "ADISCORD_naval_subsurface_warfare", "Группы скрытной засады", "Silent Ambush Groups", "Тихие лодки выбирают узкие маршруты, долго ждут цель и отходят до развёртывания охотников.", "Quiet boats exploit constrained routes, wait patiently, and withdraw before hunters can deploy.", "GFX_doctrine_convoy_interdiction_medium", "has_tech = ADISCORD_tech_quiet_propulsion", ("navy_submarine_defence_factor = 0.03", "convoy_raiding_efficiency_factor = 0.04"), "naval_silent", ("modifier = { factor = 2 has_tech = ADISCORD_tech_magnetohydrodynamic_silent_drive }",)),
    School("ADISCORD_naval_doctrine_seabed_hunter_network", "sea", "ADISCORD_naval_subsurface_warfare", "Донная поисковая сеть", "Seabed Hunter Network", "Донные датчики и автономные аппараты превращают подводную среду в наблюдаемое поле боя.", "Seabed sensors and autonomous vehicles turn the subsurface domain into an observed battlespace.", "GFX_doctrine_submarine_operations_medium", "has_tech = ADISCORD_tech_seabed_sensor_webs", ("naval_detection = 0.035", "navy_submarine_attack_factor = 0.025"), "naval_seabed", ("modifier = { factor = 2 has_tech = ADISCORD_tech_autonomous_submarines }",)),

    # Special forces: two mastery tracks, three operational schools each.
    School("ADISCORD_special_forces_mountain_companies", "special_forces", "ADISCORD_special_forces_adaptation", "Горные роты", "Mountain Companies", "Лёгкие автономные роты удерживают высоты и действуют там, где обычные соединения теряют темп.", "Light autonomous companies hold high ground and operate where regular formations lose tempo.", "GFX_special_forces_mountaineers_medium", "has_tech = ADISCORD_tech_fieldcraft_manuals", ("category_special_forces = { defense = 0.04 supply_consumption = -0.01 }",), "sf_mountain", ("modifier = { factor = 1.5 has_war = yes }",)),
    School("ADISCORD_special_forces_contaminated_zone_teams", "special_forces", "ADISCORD_special_forces_adaptation", "Группы заражённых зон", "Contaminated-zone Teams", "Герметичное снаряжение и дозовая ротация позволяют выполнять задачи в химически и радиационно опасной местности.", "Sealed equipment and exposure rotation sustain missions in chemically and radiologically hazardous terrain.", "GFX_doctrine_special_forces_1_medium", "has_tech = ADISCORD_tech_radiation_patrols", ("attrition = -0.015", "category_special_forces = { default_morale = 0.02 }"), "sf_contaminated", ("modifier = { factor = 1.8 has_tech = ADISCORD_tech_adaptive_radiation_shielding }",)),
    School("ADISCORD_special_forces_urban_assault_groups", "special_forces", "ADISCORD_special_forces_adaptation", "Группы городского штурма", "Urban Assault Groups", "Малые штурмовые группы последовательно изолируют и зачищают вертикально организованную застройку.", "Small assault groups isolate and clear vertically organized urban terrain in sequence.", "GFX_marines_commandoes_medium", "has_tech = ADISCORD_tech_urban_breaching", ("category_special_forces = { breakthrough = 0.04 soft_attack = 0.03 }",), "sf_urban", ("modifier = { factor = 1.7 has_war = yes }",)),

    School("ADISCORD_special_forces_deep_recon_cells", "special_forces", "ADISCORD_special_forces_insertion", "Ячейки глубокой разведки", "Deep Reconnaissance Cells", "Небольшие группы остаются в глубине, ведут наблюдение и передают цели общевойсковым средствам поражения.", "Small teams remain in depth, observe, and hand targets to theater strike assets.", "GFX_special_forces_rangers_medium", "has_tech = ADISCORD_tech_deep_recon_cells", ("category_recon = { recon = 0.75 }", "planning_speed = 0.015"), "sf_recon", ("modifier = { factor = 2 has_tech = ADISCORD_tech_distributed_recon_sensor_caches }",)),
    School("ADISCORD_special_forces_vertical_insertion", "special_forces", "ADISCORD_special_forces_insertion", "Вертикальное введение", "Vertical Insertion", "Воздушная мобильность доставляет штурмовые группы сразу к узлам снабжения и управления.", "Air mobility delivers assault teams directly onto supply and command nodes.", "GFX_special_forces_paratroopers_medium", "has_tech = ADISCORD_tech_vertical_assault_training", ("category_special_forces = { breakthrough = 0.04 }", "planning_speed = 0.02"), "sf_vertical", ("modifier = { factor = 2 has_tech = ADISCORD_tech_vertical_envelopment_control }",)),
    School("ADISCORD_special_forces_autonomous_raiders", "special_forces", "ADISCORD_special_forces_insertion", "Автономные рейдеры", "Autonomous Raiders", "Безэкипажные разведчики и удалённая огневая поддержка позволяют малым группам долго действовать без связи с фронтом.", "Crewless scouts and remote fires let small teams operate for long periods beyond the front.", "GFX_doctrine_special_forces_2_medium", "has_tech = ADISCORD_tech_autonomous_scout_microdrones", ("category_special_forces = { supply_consumption = -0.015 soft_attack = 0.03 }",), "sf_autonomous", ("modifier = { factor = 2 has_tech = ADISCORD_tech_augmented_special_forces }",)),
)


DOMAIN_PATHS = {
    "land": ROOT / "common/doctrines/subdoctrines/land/ADISCORD_land_subdoctrines.txt",
    "air": ROOT / "common/doctrines/subdoctrines/air/ADISCORD_air_subdoctrines.txt",
    "sea": ROOT / "common/doctrines/subdoctrines/sea/ADISCORD_naval_subdoctrines.txt",
    "special_forces": ROOT / "common/doctrines/subdoctrines/special_forces/ADISCORD_special_forces_subdoctrines.txt",
}


GRANDS = (
    {
        "key": "ADISCORD_doctrine_restoration_general_staff",
        "folder": "land",
        "ru": "Генеральный штаб восстановления",
        "en": "Restoration General Staff",
        "desc_ru": "Единый штаб координирует массовую армию, танковые войска, оперативное управление и устойчивый тыл.",
        "desc_en": "A unified staff coordinates the mass army, armored forces, operational command, and resilient rear areas.",
        "icon": "GFX_doctrine_grand_battleplan_medium",
        "xp": 75,
        "type": "army",
        "tracks": tuple(track.key for track in TRACKS[:4]),
        "effects": ("planning_speed = 0.04", "land_reinforce_rate = 0.008"),
        "ai": ("modifier = { factor = 1.5 has_war = yes }",),
        "milestones": (
            ("category_all_infantry = { max_organisation = 3 }", "land_reinforce_rate = 0.005"),
            ("category_all_armor = { breakthrough = 0.04 }", "coordination_bonus = 0.008"),
            ("coordination_bonus = 0.015", "planning_speed = 0.03"),
            ("category_support_battalions = { defense = 0.04 }", "dig_in_speed_factor = 0.03"),
        ),
    },
    {
        "key": "ADISCORD_air_doctrine_restored_air_command",
        "folder": "air",
        "ru": "Восстановленное воздушное командование",
        "en": "Restored Air Command",
        "desc_ru": "Командование объединяет беспилотную авиацию, поддержку сухопутных войск и контроль воздушного пространства.",
        "desc_en": "The command integrates unmanned aviation, ground-force support, and control of the airspace.",
        "icon": "GFX_doctrine_direct_ground_support_medium",
        "xp": 70,
        "type": "air",
        "tracks": tuple(track.key for track in TRACKS[4:7]),
        "effects": ("air_mission_efficiency = 0.025", "air_accidents_factor = -0.03"),
        "ai": ("modifier = { factor = 1.5 has_tech = ADISCORD_tech_reclaimed_jet_platforms }",),
        "milestones": (
            ("category_fighter = { air_agility = 0.03 }", "air_superiority_efficiency = 0.03"),
            ("category_cas = { air_ground_attack = 0.03 }", "air_cas_efficiency = 0.03"),
            ("air_intercept_efficiency = 0.03", "air_interception_detect_factor = 0.03"),
        ),
    },
    {
        "key": "ADISCORD_naval_doctrine_littoral_command",
        "folder": "naval",
        "ru": "Морское командование восстановления",
        "en": "Restoration Naval Command",
        "desc_ru": "Единое морское командование распределяет ограниченный флот между защитой побережья, надводным контролем и подводной войной.",
        "desc_en": "A unified naval command allocates a limited fleet between coastal defense, surface control, and subsurface warfare.",
        "icon": "GFX_doctrine_trade_interdiction_medium",
        "xp": 50,
        "type": "navy",
        "tracks": tuple(track.key for track in TRACKS[7:10]),
        "effects": ("convoy_escort_efficiency = 0.04", "naval_coordination = 0.01"),
        "ai": ("modifier = { factor = 1.5 has_war = yes }",),
        "milestones": (
            ("screening_efficiency = 0.03", "naval_detection = 0.02"),
            ("naval_hit_chance = 0.02", "shore_bombardment_bonus = 0.03"),
            ("convoy_raiding_efficiency_factor = 0.03", "navy_submarine_attack_factor = 0.03"),
        ),
    },
    {
        "key": "ADISCORD_special_forces_mass_formations",
        "folder": "special_forces",
        "ru": "Массовые специальные формирования",
        "en": "Mass Special Formations",
        "desc_ru": "Расширенная система подготовки создаёт больше специальных частей с умеренными требованиями к отбору.",
        "desc_en": "An expanded training system fields more special formations with practical selection standards.",
        "icon": "GFX_doctrine_special_forces_1_medium",
        "xp": 70,
        "type": "army",
        "tracks": tuple(track.key for track in TRACKS[10:12]),
        "effects": ("special_forces_cap = 0.02", "special_forces_training_time_factor = -0.08"),
        "ai": ("modifier = { factor = 1.5 has_manpower > 40000 }",),
        "milestones": (
            ("special_forces_cap = 0.01", "category_special_forces = { soft_attack = 0.03 }"),
            ("special_forces_cap = 0.01", "category_special_forces = { max_organisation = 2 }"),
        ),
    },
    {
        "key": "ADISCORD_special_forces_precision_cadres",
        "folder": "special_forces",
        "ru": "Отборные специальные кадры",
        "en": "Precision Special Cadres",
        "desc_ru": "Меньшее число тщательно отобранных групп получает лучшую автономность и качество командования.",
        "desc_en": "A smaller number of carefully selected teams gains superior autonomy and command quality.",
        "icon": "GFX_doctrine_special_forces_2_medium",
        "xp": 70,
        "type": "army",
        "tracks": tuple(track.key for track in TRACKS[10:12]),
        "effects": ("category_special_forces = { max_organisation = 4 }", "special_forces_no_supply_grace = 12"),
        "ai": ("modifier = { factor = 1.7 has_tech = ADISCORD_tech_reconstituted_staff_academies }",),
        "milestones": (
            ("category_special_forces = { breakthrough = 0.04 }", "special_forces_no_supply_grace = 8"),
            ("category_special_forces = { defense = 0.04 soft_attack = 0.03 }", "special_forces_no_supply_grace = 8"),
        ),
    },
)


def indent(lines: tuple[str, ...] | list[str], tabs: int) -> list[str]:
    prefix = "\t" * tabs
    return [prefix + line for line in lines]


def render_folders() -> str:
    return """land = {
\tallowed = { always = yes }
\tname = \"land_doctrine_folder\"
\tledger = army
\tledger_gfx = GFX_land_doctrine_folder_icon
\ttab_gfx = GFX_landdoctrine_tab_large
\tcolor_frame = 1
\tsound = ui_doctrine_tab_land
}

naval = {
\tallowed = { always = yes }
\tname = \"naval_doctrine_folder\"
\tledger = navy
\tledger_gfx = GFX_naval_doctrine_folder_icon
\ttab_gfx = GFX_navaldoctrine_tab_large
\tcolor_frame = 2
\tsound = ui_doctrine_tab_naval
}

air = {
\tallowed = { always = yes }
\tname = \"air_doctrine_folder\"
\tledger = air
\tledger_gfx = GFX_air_doctrine_folder_icon
\ttab_gfx = GFX_airdoctrine_tab_large
\tcolor_frame = 3
\tsound = ui_doctrine_tab_air
}

special_forces = {
\tallowed = { always = yes }
\tname = \"OFFICER_CORP_SPECIAL_FORCES_DOCTRINE\"
\tledger = army
\tledger_gfx = GFX_special_forces_doctrine_folder_icon
\ttab_gfx = GFX_specialforcesdoctrine_tab_large
\tcolor_frame = 4
\tsound = ui_doctrine_tab_special_forces
}
"""


def render_tracks() -> str:
    blocks: list[str] = []
    for track in TRACKS:
        lines = [
            f"{track.key} = {{",
            f"\tname = {track.key}",
            f"\tbackground = \"{track.background}\"",
            f"\ticon = \"{track.icon}\"",
            f"\ticon_frame = \"{track.frame}\"",
            "\tmastery = {",
            f"\t\tmultiplier = {track.multiplier:g}",
            f"\t\t{track.mastery_kind} = {{",
            *[f"\t\t\t{value}" for value in track.mastery_values],
            "\t\t}",
            "\t}",
            "}",
        ]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def render_grands() -> str:
    blocks: list[str] = []
    for grand in GRANDS:
        lines = [
            f"{grand['key']} = {{",
            f"\tfolder = {grand['folder']}",
            f"\tname = {grand['key']}",
            f"\tdescription = {grand['key']}_desc",
            f"\ticon = {grand['icon']}",
            "\tavailable = { always = yes }",
            f"\txp_cost = {grand['xp']}",
            f"\txp_type = {grand['type']}",
            "\tai_will_do = {",
            "\t\tbase = 1",
            *[f"\t\t{line}" for line in grand["ai"]],
            "\t}",
            "\ttracks = {",
            *[f"\t\t{track}" for track in grand["tracks"]],
            "\t}",
            *[f"\t{effect}" for effect in grand["effects"]],
            "\tmilestones = {",
        ]
        for milestone in grand["milestones"]:
            lines.append("\t\t{")
            lines.extend(f"\t\t\t{effect}" for effect in milestone)
            lines.append("\t\t}")
        lines.extend(("\t}", "}"))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def reward_id(school: School, index: int, slug: str) -> str:
    if index < len(school.legacy_rewards):
        return school.legacy_rewards[index]
    return f"{school.key}_{slug}"


def render_school(school: School, siblings: tuple[str, ...]) -> str:
    xp_cost = {"land": 70, "air": 55, "sea": 45, "special_forces": 60}[school.domain]
    xp_type = {"land": "army", "air": "air", "sea": "navy", "special_forces": "army"}[school.domain]
    stages = REWARD_PROFILES[school.profile]
    lines = [
        f"{school.key} = {{",
        f"\ttrack = {school.track}",
        f"\tname = {school.key}",
        f"\tdescription = {school.key}_desc",
        f"\ticon = {school.icon}",
        f"\txp_cost = {xp_cost}",
        f"\txp_type = {xp_type}",
        "\tavailable = {",
        f"\t\t{school.gate}",
        "\t}",
    ]
    if siblings:
        lines.extend(("\txor = {", *[f"\t\t{key}" for key in siblings], "\t}"))
    lines.extend(("\tai_will_do = {", "\t\tbase = 1"))
    lines.extend(f"\t\t{line}" for line in school.ai)
    lines.append("\t}")
    lines.extend(f"\t{effect}" for effect in school.root_effects)
    lines.append("\trewards = {")
    for index, (slug, _ru, _en, effects) in enumerate(stages):
        rid = reward_id(school, index, slug)
        lines.extend((f"\t\t{rid} = {{", "\t\t\tmastery = 50"))
        lines.extend(f"\t\t\t{effect}" for effect in effects)
        lines.append("\t\t}")
    lines.extend(("\t}", "}"))
    return "\n".join(lines)


def render_schools(domain: str) -> str:
    schools = [school for school in SCHOOLS if school.domain == domain]
    by_track: dict[str, list[str]] = {}
    for school in schools:
        by_track.setdefault(school.track, []).append(school.key)
    blocks = []
    for school in schools:
        siblings = tuple(key for key in by_track[school.track] if key != school.key)
        blocks.append(render_school(school, siblings))
    return "\n\n".join(blocks) + "\n"


def localisation(language: str) -> tuple[list[str], set[str]]:
    is_ru = language == "russian"
    lines: list[str] = []
    keys: set[str] = set()

    def add(key: str, value: str) -> None:
        keys.add(key)
        lines.append(f" {key}:0 \"{value}\"")

    for track in TRACKS:
        add(track.key, track.ru if is_ru else track.en)
    lines.append("")
    for grand in GRANDS:
        add(grand["key"], grand["ru"] if is_ru else grand["en"])
        add(f"{grand['key']}_desc", grand["desc_ru"] if is_ru else grand["desc_en"])
    lines.append("")
    for school in SCHOOLS:
        add(school.key, school.ru if is_ru else school.en)
        add(f"{school.key}_desc", school.desc_ru if is_ru else school.desc_en)
        for index, (slug, ru, en, _effects) in enumerate(REWARD_PROFILES[school.profile]):
            add(reward_id(school, index, slug), ru if is_ru else en)
    return lines, keys


def strip_migrated_localisation(keys: set[str]) -> None:
    for language in ("russian", "english"):
        path = ROOT / "localisation" / language / f"ADISCORD_technology_doctrine_l_{language}.yml"
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8-sig").splitlines()
        kept = []
        for line in original:
            match = re.match(r"^\s+([A-Za-z0-9_]+):", line)
            if match and match.group(1) in keys:
                continue
            kept.append(line)
        while kept and not kept[-1].strip():
            kept.pop()
        path.write_text("\n".join(kept) + "\n", encoding="utf-8-sig")


def write_localisation() -> None:
    all_keys: set[str] = set()
    for language in ("russian", "english"):
        lines, keys = localisation(language)
        all_keys.update(keys)
        path = ROOT / "localisation" / language / f"ADISCORD_mastery_doctrines_l_{language}.yml"
        path.write_text(f"l_{language}:\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8-sig")
    strip_migrated_localisation(all_keys)


def validate_manifest() -> None:
    school_ids = [school.key for school in SCHOOLS]
    if len(school_ids) != 40 or len(set(school_ids)) != 40:
        raise ValueError(f"Expected 40 unique schools, got {len(set(school_ids))}")
    track_ids = {track.key for track in TRACKS}
    missing_tracks = sorted({school.track for school in SCHOOLS} - track_ids)
    if missing_tracks:
        raise ValueError(f"Schools reference missing tracks: {missing_tracks}")
    reward_ids = [
        reward_id(school, index, stage[0])
        for school in SCHOOLS
        for index, stage in enumerate(REWARD_PROFILES[school.profile])
    ]
    duplicates = sorted({key for key in reward_ids if reward_ids.count(key) > 1})
    if duplicates:
        raise ValueError(f"Duplicate reward IDs: {duplicates}")


def main() -> None:
    validate_manifest()
    (ROOT / "common/doctrines/folders/ADISCORD_doctrine_folders.txt").write_text(render_folders(), encoding="utf-8")
    (ROOT / "common/doctrines/tracks/ADISCORD_doctrine_tracks.txt").write_text(render_tracks(), encoding="utf-8")
    (ROOT / "common/doctrines/grand_doctrines/ADISCORD_grand_doctrines.txt").write_text(render_grands(), encoding="utf-8")
    for domain, path in DOMAIN_PATHS.items():
        path.write_text(render_schools(domain), encoding="utf-8")
    write_localisation()
    print(f"Generated {len(GRANDS)} grand doctrines, {len(TRACKS)} tracks, {len(SCHOOLS)} schools and {len(SCHOOLS) * 5} mastery rewards.")


if __name__ == "__main__":
    main()
