import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RU_LAWS = ROOT / "localisation/russian/ADISCORD_laws_l_russian.yml"
EN_LAWS = ROOT / "localisation/english/ADISCORD_laws_l_english.yml"
RU_ECONOMY = ROOT / "localisation/russian/ADISCORD_economy_l_russian.yml"
EN_ECONOMY = ROOT / "localisation/english/ADISCORD_economy_l_english.yml"

ENTRY_RE = re.compile(
    r'(?m)^\s*([A-Za-z0-9_.-]+):\s*"((?:[^"\\]|\\.)*)"\s*$'
)


def parse_localisation(path: Path) -> tuple[str, dict[str, str], dict[str, int]]:
    text = path.read_text(encoding="utf-8-sig", errors="strict")
    pairs = ENTRY_RE.findall(text)
    counts = Counter(key for key, _ in pairs)
    return text, dict(pairs), dict(counts)


APPROVED_RU_CIVILIAN_NAMES = {
    "ADISCORD_society_type_laws": "Общественный уклад",
    "ADISCORD_information_open_press": "Свободная пресса",
    "ADISCORD_information_licensed_press": "Регулируемая пресса",
    "ADISCORD_information_state_bulletins": "Государственная пресса",
    "ADISCORD_information_sealed_networks": "Государственный контроль информации",
    "ADISCORD_taxation_light_dues": "Местное налогообложение",
    "ADISCORD_taxation_balanced_register": "Единая налоговая система",
    "ADISCORD_taxation_industrial_tariffs": "Протекционистские тарифы",
    "ADISCORD_taxation_extraction_quotas": "Чрезвычайные сборы",
    "ADISCORD_welfare_basic_services": "Базовая социальная помощь",
    "ADISCORD_welfare_universal_provision": "Всеобщие социальные гарантии",
    "ADISCORD_welfare_rationed_support": "Военное нормирование",
    "ADISCORD_education_informal_instruction": "Местное образование",
    "ADISCORD_education_civic_curriculum": "Гражданское образование",
    "ADISCORD_healthcare_basic_clinics": "Первичная медицинская помощь",
    "ADISCORD_cultural_policy_tolerated_subcultures": "Культурный плюрализм",
    "ADISCORD_cultural_policy_public_entertainment": "Массовая культура",
    "ADISCORD_cultural_policy_civic_festivals": "Общественные праздники",
    "ADISCORD_cultural_policy_avant_garde_patronage": "Поддержка современного искусства",
    "ADISCORD_cultural_policy_national_mythmaking": "Патриотическая культурная политика",
    "ADISCORD_industrial_policy_artisan_markets": "Ремесленное производство",
    "ADISCORD_industrial_policy_balanced_workshops": "Поддержка частного производства",
    "ADISCORD_industrial_policy_civilian_expansion": "Приоритет гражданской промышленности",
    "ADISCORD_industrial_policy_military_prioritization": "Приоритет военной промышленности",
    "ADISCORD_industrial_policy_state_planning_boards": "Промышленное планирование",
    "ADISCORD_labor_policy_loose_contracts": "Гибкая занятость",
    "ADISCORD_labor_policy_guild_protections": "Профессиональные объединения",
    "ADISCORD_labor_policy_regulated_shifts": "Трудовое регулирование",
    "ADISCORD_labor_policy_technocratic_work_norms": "Научная организация труда",
    "ADISCORD_labor_policy_mobilized_labor": "Трудовая мобилизация",
    "ADISCORD_infrastructure_patchwork_roads": "Местное дорожное хозяйство",
    "ADISCORD_infrastructure_regional_roadworks": "Региональные инфраструктурные программы",
}

APPROVED_RU_ECONOMIC_SYSTEM_NAMES = {
    "ADISCORD_economic_system_laws": "Экономическая система",
    "ADISCORD_economic_system_agrarian": "Аграрная экономика",
    "ADISCORD_economic_system_industrializing": "Экономика индустриализации",
    "ADISCORD_economic_system_free_market": "Свободный рынок",
    "ADISCORD_economic_system_mixed": "Смешанная экономика",
    "ADISCORD_economic_system_state_coordinated": "Государственно регулируемая экономика",
    "ADISCORD_economic_system_planned_bureaucratic": "Административно-плановая экономика",
    "ADISCORD_economic_system_syndicalist": "Синдикалистская экономика",
    "ADISCORD_economic_system_oligarchic_clan": "Клановая экономика",
    "ADISCORD_economic_system_technocratic": "Технократическая экономика",
}

APPROVED_EN_ECONOMIC_SYSTEM_NAMES = {
    "ADISCORD_economic_system_laws": "Economic System",
    "ADISCORD_economic_system_agrarian": "Agrarian Economy",
    "ADISCORD_economic_system_industrializing": "Industrializing Economy",
    "ADISCORD_economic_system_free_market": "Free Market",
    "ADISCORD_economic_system_mixed": "Mixed Economy",
    "ADISCORD_economic_system_state_coordinated": "State-Regulated Economy",
    "ADISCORD_economic_system_planned_bureaucratic": "Administrative Command Economy",
    "ADISCORD_economic_system_syndicalist": "Syndicalist Economy",
    "ADISCORD_economic_system_oligarchic_clan": "Clan Economy",
    "ADISCORD_economic_system_technocratic": "Technocratic Economy",
}

APPROVED_RU_MODEL_LABELS = {
    "ADISCORD_economy_model_3": "Государственно регулируемая экономика",
    "ADISCORD_economy_model_4": "Административно-плановая экономика",
    "ADISCORD_economy_model_5": "Синдикалистская экономика",
    "ADISCORD_economy_model_6": "Клановая экономика",
}

APPROVED_EN_MODEL_LABELS = {
    "ADISCORD_economy_model_3": "State-regulated economy",
    "ADISCORD_economy_model_4": "Administrative command economy",
    "ADISCORD_economy_model_5": "Syndicalist economy",
    "ADISCORD_economy_model_6": "Clan economy",
}

RETIRED_RU_CIVILIAN_FRAGMENTS = (
    "страна меньше спорит, но и хуже дышит",
    "пока помнят границы дозволенного",
    "независимая мысль постепенно беднеет",
    "цена молчания",
    "настоящая страховка от бедности",
    "казна и чиновники начинают работать на пределе",
    "мирное общество быстро устает от талонов",
    "верхних этажей системы",
    "кошелька и удачи",
    "страна меньше теряет людей впустую",
    "повод не спорить хотя бы один день",
    "хочет простых ответов",
    "хорошо держит строй",
    "гражданский сектор терпит",
    "строка в производственном плане",
    "общество быстро запоминает цену принуждения",
    "фронт благодарит",
    "такая машина",
    "случайные школы",
    "неровный кадровый фундамент",
)

APPROVED_RU_MILITARY_NAMES = {
    "ADISCORD_military_organization_militia_autonomy": "Территориальное ополчение",
    "ADISCORD_military_organization_contract_brigades": "Контрактная служба",
    "ADISCORD_military_organization_general_staff": "Централизованное командование",
    "ADISCORD_military_organization_total_defense_grid": "Система территориальной обороны",
    "ADISCORD_officer_corps_local_seniority": "Продвижение по выслуге",
    "ADISCORD_officer_corps_merit_commissions": "Отбор по профессиональным качествам",
    "ADISCORD_officer_corps_emergency_promotions": "Повышения военного времени",
    "ADISCORD_logistics_local_foraging": "Снабжение за счёт местных ресурсов",
    "ADISCORD_logistics_civilian_contracts": "Гражданские поставщики",
    "ADISCORD_logistics_centralized_depots": "Централизованная система снабжения",
    "ADISCORD_training_irregular_exercises": "Периодические военные сборы",
    "ADISCORD_training_standardized_program": "Единая программа подготовки",
    "ADISCORD_training_officer_led_wargames": "Командно-штабные учения",
    "ADISCORD_training_accelerated_bootcamps": "Ускоренная военная подготовка",
    "ADISCORD_internal_security_neighborhood_watch": "Добровольные патрули",
    "ADISCORD_internal_security_local_garrisons": "Территориальные гарнизоны",
    "ADISCORD_internal_security_investigative_bureaus": "Политическая полиция",
    "ADISCORD_internal_security_internal_directorate": "Государственная служба безопасности",
}

RETIRED_RU_MILITARY_FRAGMENTS = (
    "меньше романтики",
    "решения становятся тяжелее, но точнее",
    "страна заранее размечена",
    "старые круги теряют комфорт",
    "смелых, жестких и просто выживших",
    "государство берет нужное там, где оно есть",
    "новую причину ненавидеть списки",
    "подготовка идет рывками",
    "прогоняют через жесткие короткие курсы",
    "личные счеты не начинают выдавать за безопасность",
    "порядок крепнет",
    "государство видит больше, общество дышит меньше",
    "решения требуют больше времени",
    "металлом и топливом",
)

RETIRED_ENGLISH_MECHANICAL_FRAGMENTS = (
    "decision-making take more time",
    "metal and fuel",
)

APPROVED_ENGLISH_CUSTOM_NAMES = {
    "ADISCORD_society_type_laws": "Social Structure",
    "ADISCORD_information_open_press": "Free Press",
    "ADISCORD_information_licensed_press": "Regulated Press",
    "ADISCORD_information_state_bulletins": "State Media",
    "ADISCORD_information_sealed_networks": "State Information Control",
    "ADISCORD_taxation_light_dues": "Local Taxation",
    "ADISCORD_taxation_balanced_register": "Unified Tax System",
    "ADISCORD_taxation_industrial_tariffs": "Protectionist Tariffs",
    "ADISCORD_taxation_extraction_quotas": "Emergency Levies",
    "ADISCORD_welfare_basic_services": "Basic Social Assistance",
    "ADISCORD_welfare_universal_provision": "Universal Social Provision",
    "ADISCORD_welfare_rationed_support": "Wartime Rationing",
    "ADISCORD_education_informal_instruction": "Local Education",
    "ADISCORD_education_civic_curriculum": "Civic Education",
    "ADISCORD_healthcare_basic_clinics": "Primary Healthcare",
    "ADISCORD_cultural_policy_tolerated_subcultures": "Cultural Pluralism",
    "ADISCORD_cultural_policy_public_entertainment": "Mass Culture",
    "ADISCORD_cultural_policy_civic_festivals": "Civic Holidays",
    "ADISCORD_cultural_policy_avant_garde_patronage": "Support for Contemporary Art",
    "ADISCORD_cultural_policy_national_mythmaking": "Patriotic Cultural Policy",
    "ADISCORD_industrial_policy_artisan_markets": "Artisan Production",
    "ADISCORD_industrial_policy_balanced_workshops": "Support for Private Industry",
    "ADISCORD_industrial_policy_civilian_expansion": "Civilian Industry Priority",
    "ADISCORD_industrial_policy_military_prioritization": "Military Industry Priority",
    "ADISCORD_industrial_policy_state_planning_boards": "Industrial Planning",
    "ADISCORD_labor_policy_loose_contracts": "Flexible Employment",
    "ADISCORD_labor_policy_guild_protections": "Professional Associations",
    "ADISCORD_labor_policy_regulated_shifts": "Labor Regulation",
    "ADISCORD_labor_policy_technocratic_work_norms": "Scientific Management",
    "ADISCORD_labor_policy_mobilized_labor": "Labor Mobilization",
    "ADISCORD_infrastructure_patchwork_roads": "Local Road Administration",
    "ADISCORD_infrastructure_regional_roadworks": "Regional Infrastructure Programs",
    "ADISCORD_military_organization_militia_autonomy": "Territorial Militia",
    "ADISCORD_military_organization_contract_brigades": "Contract Service",
    "ADISCORD_military_organization_general_staff": "Centralized Command",
    "ADISCORD_military_organization_total_defense_grid": "Territorial Defense System",
    "ADISCORD_officer_corps_local_seniority": "Promotion by Seniority",
    "ADISCORD_officer_corps_merit_commissions": "Merit-Based Selection",
    "ADISCORD_officer_corps_emergency_promotions": "Wartime Promotions",
    "ADISCORD_logistics_local_foraging": "Local Supply Procurement",
    "ADISCORD_logistics_civilian_contracts": "Civilian Suppliers",
    "ADISCORD_logistics_centralized_depots": "Centralized Supply System",
    "ADISCORD_training_irregular_exercises": "Periodic Military Drills",
    "ADISCORD_training_standardized_program": "Unified Training Program",
    "ADISCORD_training_officer_led_wargames": "Command-Post Exercises",
    "ADISCORD_training_accelerated_bootcamps": "Accelerated Military Training",
    "ADISCORD_internal_security_neighborhood_watch": "Volunteer Patrols",
    "ADISCORD_internal_security_local_garrisons": "Territorial Garrisons",
    "ADISCORD_internal_security_investigative_bureaus": "Political Police",
    "ADISCORD_internal_security_internal_directorate": "State Security Service",
}


class LawLocalisationContractTests(unittest.TestCase):
    def test_russian_custom_law_file_has_bom_and_unique_keys(self) -> None:
        self.assertTrue(RU_LAWS.read_bytes().startswith(b"\xef\xbb\xbf"))
        text, _, counts = parse_localisation(RU_LAWS)
        self.assertTrue(text.startswith("l_russian:\n"))
        self.assertEqual(
            {key: count for key, count in counts.items() if count != 1},
            {},
        )

    def test_approved_russian_civilian_names(self) -> None:
        _, values, _ = parse_localisation(RU_LAWS)
        for key, expected in APPROVED_RU_CIVILIAN_NAMES.items():
            with self.subTest(key=key):
                self.assertEqual(values.get(key), expected)

    def test_retired_russian_civilian_phrasing_is_absent(self) -> None:
        text, _, _ = parse_localisation(RU_LAWS)
        lowered = text.lower()
        for fragment in RETIRED_RU_CIVILIAN_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment.lower(), lowered)

    def test_approved_russian_military_names(self) -> None:
        _, values, _ = parse_localisation(RU_LAWS)
        for key, expected in APPROVED_RU_MILITARY_NAMES.items():
            with self.subTest(key=key):
                self.assertEqual(values.get(key), expected)

    def test_retired_russian_military_phrasing_is_absent(self) -> None:
        text, _, _ = parse_localisation(RU_LAWS)
        lowered = text.lower()
        for fragment in RETIRED_RU_MILITARY_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment.lower(), lowered)

    def test_retired_english_mechanical_phrasing_is_absent(self) -> None:
        _, values, _ = parse_localisation(EN_LAWS)
        lowered_values = "\n".join(values.values()).lower()
        for fragment in RETIRED_ENGLISH_MECHANICAL_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment.lower(), lowered_values)

    def test_english_custom_laws_have_bom_unique_keys_and_russian_parity(self) -> None:
        self.assertTrue(EN_LAWS.is_file(), "English custom-law localisation is missing")
        self.assertTrue(EN_LAWS.read_bytes().startswith(b"\xef\xbb\xbf"))
        english_text, english_values, english_counts = parse_localisation(EN_LAWS)
        _, russian_values, _ = parse_localisation(RU_LAWS)
        self.assertTrue(english_text.startswith("l_english:\n"))
        self.assertEqual(
            {key: count for key, count in english_counts.items() if count != 1},
            {},
        )
        self.assertEqual(set(english_values), set(russian_values))
        for key, value in english_values.items():
            self.assertTrue(value.strip(), key)
            self.assertIsNone(re.search(r"[\u0400-\u04ff]", value), key)

    def test_approved_english_custom_names(self) -> None:
        _, values, _ = parse_localisation(EN_LAWS)
        for key, expected in APPROVED_ENGLISH_CUSTOM_NAMES.items():
            with self.subTest(key=key):
                self.assertEqual(values.get(key), expected)

    def test_approved_bilingual_economic_system_names(self) -> None:
        for path, expected_names in (
            (RU_ECONOMY, APPROVED_RU_ECONOMIC_SYSTEM_NAMES),
            (EN_ECONOMY, APPROVED_EN_ECONOMIC_SYSTEM_NAMES),
        ):
            _, values, counts = parse_localisation(path)
            self.assertEqual(
                {key: count for key, count in counts.items() if count != 1},
                {},
            )
            for key, expected in expected_names.items():
                with self.subTest(path=path.name, key=key):
                    self.assertEqual(values.get(key), expected)
                    self.assertTrue(values.get(f"{key}_desc", "").strip())

    def test_dashboard_model_labels_follow_approved_terminology(self) -> None:
        for path, expected_names in (
            (RU_ECONOMY, APPROVED_RU_MODEL_LABELS),
            (EN_ECONOMY, APPROVED_EN_MODEL_LABELS),
        ):
            _, values, _ = parse_localisation(path)
            for key, expected in expected_names.items():
                with self.subTest(path=path.name, key=key):
                    self.assertEqual(values.get(key), expected)

    def test_law_category_descriptions_have_no_developer_vocabulary(self) -> None:
        for path in (RU_ECONOMY, EN_ECONOMY):
            _, values, _ = parse_localisation(path)
            for key in ("economy_desc", "ADISCORD_economic_system_laws_desc"):
                value = values.get(key, "")
                self.assertTrue(value.strip(), (path.name, key))
                self.assertNotIn("vanilla", value.lower(), (path.name, key))


if __name__ == "__main__":
    unittest.main()
