import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RU_LAWS = ROOT / "localisation/russian/ADISCORD_laws_l_russian.yml"
EN_LAWS = ROOT / "localisation/english/ADISCORD_laws_l_english.yml"
RU_ECONOMY = ROOT / "localisation/russian/ADISCORD_economy_l_russian.yml"
EN_ECONOMY = ROOT / "localisation/english/ADISCORD_economy_l_english.yml"

ENTRY_RE = re.compile(r'(?m)^\s*([A-Za-z0-9_.-]+):\s*"((?:[^"\\]|\\.)*)"\s*$')


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
    "ADISCORD_labor_policy_technocratic_work_norms": "Научная и алгоритмическая организация труда",
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
    "ADISCORD_labor_policy_technocratic_work_norms": "Scientific and Algorithmic Management",
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


class SevenRowPoliticsContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )
        from tools.tests.test_adiscord_stp_party_route import one

        cls.one = staticmethod(one)
        cls.categories = one(
            parse_clausewitz(
                (ROOT / "common/idea_tags/00_idea.txt").read_text(encoding="utf-8")
            ),
            "idea_categories",
        )
        cls.groups = {}
        for name in (
            "ADISCORD_laws.txt",
            "ADISCORD_ministers_all_countries.txt",
            "ADISCORD_ideas_ZZZ_generic.txt",
        ):
            for group in one(
                parse_clausewitz(
                    (ROOT / "common/ideas" / name).read_text(encoding="utf-8")
                ),
                "ideas",
            ):
                cls.groups.setdefault(group.key, []).extend(group.value)

    def test_every_political_row_has_seven_positions_and_theorist_moves_once(self):
        rows = (
            "government",
            "social_laws",
            "economic_laws",
            "army_laws",
            "research_production",
            "military_staff",
        )
        all_slots = {}
        for row in rows:
            body = self.one(self.categories, row)
            slots = [e.value for e in body if e.key in ("slot", "character_slot")]
            self.assertEqual(len(slots), 7, row)
            all_slots[row] = slots
        self.assertEqual(
            sum(slots.count("theorist") for slots in all_slots.values()), 1
        )
        self.assertEqual(all_slots["military_staff"][-1], "theorist")
        self.assertNotIn("theorist", all_slots["research_production"])

    def test_new_categories_have_localized_choices_and_two_universal_drug_policies(
        self,
    ):
        slots = (
            "political_advisor_minister_of_foreign_affairs",
            "ADISCORD_electronics_designer",
            "ADISCORD_logistics_designer",
            "ADISCORD_military_justice_laws",
            "STP_drug_policy_laws",
        )
        locs = []
        for language in ("russian", "english"):
            values = {}
            for name in ("ADISCORD_laws", "ADISCORD_STP", "nsb_characters"):
                _, entries, _ = parse_localisation(
                    ROOT / f"localisation/{language}/{name}_l_{language}.yml"
                )
                values.update(entries)
            locs.append(values)
        for slot in slots:
            choices = [
                e
                for e in self.groups[slot]
                if isinstance(e.value, list) and not e.key.endswith("_vacant")
            ]
            self.assertGreaterEqual(len(choices), 2, slot)
            for loc in locs:
                self.assertIn(slot, loc)
                for choice in choices:
                    self.assertIn(choice.key, loc)
        drug = self.groups["STP_drug_policy_laws"]
        ban = self.one(drug, "STP_law_drug_prohibition")
        medical = self.one(drug, "ADISCORD_drugs_medical_distribution")
        self.assertEqual(self.one(ban, "default"), "yes")
        for idea in (ban, medical):
            self.assertEqual(self.one(self.one(idea, "allowed"), "always"), "yes")
            self.assertEqual(
                self.one(
                    self.one(self.one(idea, "available"), "custom_trigger_tooltip"),
                    "always",
                ),
                "no",
            )
        for key in ("STP_law_light_drugs", "STP_law_hard_drugs"):
            self.assertEqual(
                self.one(self.one(self.one(drug, key), "allowed"), "always"), "yes"
            )

    def test_drug_policies_are_visible_but_only_scripts_can_change_them(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        drug = self.groups["STP_drug_policy_laws"]
        for key in (
            "STP_law_drug_prohibition",
            "ADISCORD_drugs_medical_distribution",
            "STP_law_light_drugs",
            "STP_law_hard_drugs",
        ):
            idea = self.one(drug, key)
            self.assertFalse(any(e.key == "visible" for e in idea), key)
            for country in ("STP", "STS", "NOD", "VAL"):
                for hedonist in (False, True):
                    facts = {
                        ("STP", "original_tag", "STP"): country == "STP",
                        ("STP", "original_tag", "STS"): country == "STS",
                        ("STP", "has_government", "hedonism"): hedonist,
                    }
                    with self.subTest(key=key, country=country, hedonist=hedonist):
                        self.assertEqual(
                            matches_conditions(self.one(idea, "available"), facts),
                            False,
                        )
        history = (ROOT / "history/countries/STP - StepanLand.txt").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("STP_law_light_drugs", history)

    def test_electronics_and_logistics_have_universal_defaults_and_illustrated_choices(
        self,
    ):
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )
        from tools.tests.test_adiscord_stp_party_route import walk

        gfx = parse_clausewitz(
            (ROOT / "interface/ADISCORD_ideas.gfx").read_text(encoding="utf-8-sig")
        )
        sprites = {
            self.one(entry.value, "name").strip('"')
            for entry in walk(gfx)
            if entry.key == "spriteType"
        }
        for slot in ("ADISCORD_electronics_designer", "ADISCORD_logistics_designer"):
            choices = self.groups[slot]
            self.assertEqual(len(choices), 6, slot)
            defaults = [
                idea
                for idea in choices
                if any(
                    entry.key == "default" and entry.value == "yes"
                    for entry in idea.value
                )
            ]
            self.assertEqual(len(defaults), 1, slot)
            self.assertEqual(self.one(defaults[0].value, "cost"), "0")
            self.assertFalse(
                any(
                    entry.key in ("modifier", "research_bonus")
                    for entry in defaults[0].value
                )
            )
            for idea in choices:
                with self.subTest(slot=slot, idea=idea.key):
                    for gate in ("allowed", "available"):
                        self.assertEqual(
                            self.one(self.one(idea.value, gate), "always"), "yes"
                        )
                    self.assertIn(
                        "GFX_idea_" + self.one(idea.value, "picture"), sprites
                    )
                    for loc_path in (RU_LAWS, EN_LAWS):
                        _, loc, _ = parse_localisation(loc_path)
                        self.assertTrue(loc.get(idea.key + "_desc", "").strip())
                    modifiers = [
                        entry.value for entry in idea.value if entry.key == "modifier"
                    ]
                    if any(
                        entry.key.startswith("ADISCORD_economy_")
                        for modifier in modifiers
                        for entry in modifier
                    ):
                        for hook in ("on_add", "on_remove"):
                            effects = {
                                entry.key for entry in walk(self.one(idea.value, hook))
                            }
                            self.assertIn("ADISCORD_economy_mark_dirty", effects)
                            self.assertIn("ADISCORD_economy_queue_law_refresh", effects)

    def test_every_registered_country_has_candidates_for_each_political_slot(self):
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        rows = (
            "government",
            "social_laws",
            "economic_laws",
            "army_laws",
            "research_production",
            "military_staff",
        )
        slots = [
            e.value
            for row in rows
            for e in self.one(self.categories, row)
            if e.key in ("slot", "character_slot")
        ]
        required = Counter(slots)
        candidates = {slot: [] for slot in slots}
        for path in (ROOT / "common/ideas").glob("*.txt"):
            for scope in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if scope.key != "ideas":
                    continue
                for group in scope.value:
                    if group.key in candidates:
                        candidates[group.key].extend(
                            e
                            for e in group.value
                            if isinstance(e.value, list)
                            and not e.key.endswith("_vacant")
                        )
        tags = set()
        for path in (ROOT / "common/country_tags").glob("*.txt"):
            tags.update(
                re.findall(
                    r'(?m)^\s*([A-Z0-9]{3})\s*=\s*"',
                    path.read_text(encoding="utf-8-sig"),
                )
            )
        self.assertGreater(len(tags), 50)
        national_staff = self.one(
            parse_clausewitz(
                (
                    ROOT
                    / "common/scripted_triggers/ADISCORD_scripted_triggers_generic.txt"
                ).read_text(encoding="utf-8")
            ),
            "ADISCORD_has_national_military_staff",
        )
        for tag in tags:
            has_national_staff = matches_conditions(national_staff, {}, tag)
            facts = {
                (
                    tag,
                    "ADISCORD_has_national_military_staff",
                    "no",
                ): not has_national_staff
            }
            for slot in required:
                with self.subTest(tag=tag, slot=slot):
                    eligible = []
                    for candidate in candidates[slot]:
                        allowed = [
                            e.value for e in candidate.value if e.key == "allowed"
                        ]
                        if not allowed or matches_conditions(allowed[0], facts, tag):
                            eligible.append(candidate.key)
                    self.assertGreaterEqual(len(set(eligible)), required[slot])

    def test_new_economic_ministers_refresh_weekly_inputs_on_hire_and_removal(self):
        from tools.tests.test_adiscord_stp_party_route import walk

        for slot in (
            "political_advisor_minister_of_economy",
            "political_advisor_minister_of_health",
            "political_advisor_minister_of_foreign_affairs",
        ):
            for idea in self.groups[slot]:
                if not idea.key.startswith(
                    ("ADISCORD_general_", "ADISCORD_foreign_")
                ) and not (
                    slot == "political_advisor_minister_of_foreign_affairs"
                    and idea.key.startswith("minister_")
                ):
                    continue
                for hook in ("on_add", "on_remove"):
                    effects = {e.key for e in walk(self.one(idea.value, hook))}
                    self.assertIn(
                        "ADISCORD_economy_queue_law_refresh", effects, (idea.key, hook)
                    )

    def test_foreign_ministers_have_national_names_offices_and_cabinet_guards(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )

        tags = set()
        for path in (ROOT / "common/country_tags").glob("*.txt"):
            tags.update(
                re.findall(
                    r'(?m)^\s*([A-Z0-9]{3})\s*=\s*"',
                    path.read_text(encoding="utf-8-sig"),
                )
            )
        choices = [
            idea
            for idea in self.groups["political_advisor_minister_of_foreign_affairs"]
            if not idea.key.endswith("_vacant")
        ]
        traits = self.one(
            parse_clausewitz(
                (ROOT / "common/country_leader/ADISCORD_minister_traits.txt").read_text(
                    encoding="utf-8"
                )
            ),
            "leader_traits",
        )
        names = {}
        for language in ("russian", "english"):
            values = {}
            for stem in ("nsb_characters", "ADISCORD_traits", "ADISCORD_laws"):
                path = ROOT / f"localisation/{language}/{stem}_l_{language}.yml"
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                _, entries, _ = parse_localisation(path)
                values.update(entries)
            names[language] = values
        for tag in tags:
            eligible = [
                idea
                for idea in choices
                if matches_conditions(self.one(idea.value, "allowed"), {}, tag)
            ]
            dynamic = re.fullmatch(r"D\d\d", tag) is not None
            self.assertEqual(len(eligible), 2 if dynamic else 1, tag)
            if not dynamic:
                self.assertTrue(eligible[0].key.startswith(f"minister_{tag}_"), tag)
        for idea in choices:
            for gate in ("available", "allowed_to_remove"):
                self.assertEqual(
                    self.one(
                        self.one(idea.value, gate), "STP_party_minister_change_allowed"
                    ),
                    "yes",
                )
            office = self.one(idea.value, "traits")[0].value
            self.assertTrue(self.one(traits, office))
            for language, values in names.items():
                self.assertGreaterEqual(len(values[idea.key].split()), 2, idea.key)
                self.assertIn(
                    values[office], values[idea.key + "_desc"], (language, idea.key)
                )
        for language, values in names.items():
            self.assertEqual(
                len({values[idea.key] for idea in choices}), len(choices), language
            )


class MilitaryStaffContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.validators.validate_adiscord_division_templates import (
            parse_clausewitz,
        )
        from tools.tests.test_adiscord_stp_party_route import one, walk

        cls.one = staticmethod(one)
        cls.walk = staticmethod(walk)
        cls.parse = staticmethod(parse_clausewitz)
        cls.ideas = one(
            parse_clausewitz(
                (ROOT / "common/ideas/ADISCORD_ministers_all_countries.txt").read_text(
                    encoding="utf-8"
                )
            ),
            "ideas",
        )
        cls.slots = (
            "army_chief",
            "navy_chief",
            "air_chief",
            "high_command",
            "theorist",
        )
        cls.candidates = [
            (group.key, idea)
            for group in cls.ideas
            if group.key in cls.slots
            for idea in group.value
        ]
        cls.focuses = {}
        for filename in (
            "ADISCORD_national_focus_VAL.txt",
            "ADISCORD_STP_civil_war.txt",
        ):
            tree = one(
                parse_clausewitz(
                    (ROOT / "common/national_focus" / filename).read_text(
                        encoding="utf-8"
                    )
                ),
                "focus_tree",
            )
            cls.focuses.update(
                {
                    one(entry.value, "id"): entry.value
                    for entry in tree
                    if entry.key == "focus"
                }
            )

    def test_each_national_roster_can_fill_seven_seats_before_any_focus(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions

        trigger = self.one(
            self.parse(
                (
                    ROOT
                    / "common/scripted_triggers/ADISCORD_scripted_triggers_generic.txt"
                ).read_text(encoding="utf-8")
            ),
            "ADISCORD_has_national_military_staff",
        )
        tags = [entry.value for entry in self.walk(trigger) if entry.key == "tag"]
        self.assertEqual(len(set(tags)), 30)
        for tag in tags:
            counts = Counter()
            for slot, idea in self.candidates:
                if matches_conditions(
                    self.one(idea.value, "allowed"), {}, tag
                ) and matches_conditions(self.one(idea.value, "available"), {}, tag):
                    counts[slot] += 1
            for slot in self.slots:
                self.assertGreaterEqual(
                    counts[slot], 3 if slot == "high_command" else 1, (tag, slot)
                )
            if tag in ("VAL", "STP", "STS"):
                self.assertGreaterEqual(sum(counts.values()), 14, tag)

    def test_named_staff_have_valid_traits_ledgers_and_can_be_dismissed(self):
        trait_ids = set()
        for path in (ROOT / "common/country_leader").glob("*.txt"):
            for group in self.parse(path.read_text(encoding="utf-8-sig")):
                if group.key == "leader_traits":
                    trait_ids.update(entry.key for entry in group.value)
        for slot, idea in self.candidates:
            with self.subTest(idea=idea.key):
                self.assertEqual(self.one(idea.value, "removal_cost"), "0")
                for trait in self.one(idea.value, "traits"):
                    self.assertIn(trait.value, trait_ids)
                if slot == "high_command":
                    self.assertIn(
                        self.one(idea.value, "ledger"), ("army", "navy", "air")
                    )
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/nsb_characters_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            _, names, counts = parse_localisation(path)
            for _, idea in self.candidates:
                self.assertEqual(counts[idea.key], 1)
                self.assertGreaterEqual(len(names[idea.key].split()), 2)
                self.assertTrue(names[idea.key + "_desc"].strip())

    def test_elite_staff_are_gated_by_the_focus_that_actually_appoints_them(self):
        appointments = 0
        for slot, idea in self.candidates:
            gate = self.one(idea.value, "available")
            unlocks = [
                entry.value
                for entry in self.walk(gate)
                if entry.key == "has_completed_focus"
            ]
            if not unlocks:
                continue
            appointments += 1
            self.assertNotEqual(slot, "high_command")
            self.assertEqual(len(unlocks), 1)
            focus = self.focuses[unlocks[0]]
            reward = self.one(focus, "completion_reward")
            self.assertIn(
                idea.key, [entry.value for entry in reward if entry.key == "add_ideas"]
            )
            self.assertFalse(any(entry.key == "bypass" for entry in focus), unlocks[0])
            tag = self.one(self.one(idea.value, "allowed"), "tag")
            if tag in ("STP", "STS"):
                self.assertIn(
                    tag,
                    [
                        entry.value
                        for entry in self.walk(self.one(focus, "allow_branch"))
                        if entry.key == "tag"
                    ],
                )
        self.assertEqual(appointments, 13)

    def test_kefreyt_commanders_keep_single_character_identity_and_native_focus_appointments(
        self,
    ):
        chars = self.one(
            self.parse(
                (ROOT / "common/characters/VAL.txt").read_text(encoding="utf-8")
            ),
            "characters",
        )
        history = (ROOT / "history/countries/VAL - ValeraLand.txt").read_text(
            encoding="utf-8-sig"
        )
        for character in (
            "VAL_Kirill_Voron",
            "VAL_Erika_Stahl",
            "VAL_Boris_Gromov",
            "VAL_Renata_Morn",
        ):
            body = self.one(chars, character)
            self.assertIn("recruit_character = " + character, history)
            advisor = self.one(body, "advisor")
            self.assertIn(self.one(advisor, "slot"), ("army_chief", "theorist"))
            self.assertEqual(
                self.one(self.one(advisor, "allowed"), "original_tag"), "VAL"
            )
            unlock = self.one(self.one(advisor, "available"), "has_completed_focus")
            token = self.one(advisor, "idea_token")
            reward = self.one(self.focuses[unlock], "completion_reward")
            self.assertIn(
                token,
                [entry.value for entry in reward if entry.key == "activate_advisor"],
            )
            self.assertFalse(any(idea.key == token for _, idea in self.candidates))
            army = self.one(self.one(body, "portraits"), "army")
            self.assertTrue(self.one(army, "small"))

    def test_sotnikov_appointment_requires_a_free_high_command_seat(self):
        focus = self.focuses["STP_pc_lib_civil_army"]
        gate = next(
            entry.value
            for entry in self.walk(self.one(focus, "available"))
            if entry.key == "amount_taken_ideas"
        )
        comparison = [entry.value for entry in gate if not entry.key]
        self.assertEqual(comparison, ["amount", "<", "3"])
        self.assertEqual(
            [entry.value for entry in self.one(gate, "slots")], ["high_command"]
        )
        self.assertEqual(self.one(focus, "cancel_if_invalid"), "yes")
        alternatives = [
            entry
            for entry in self.walk(self.one(focus, "available"))
            if entry.key == "STP_cw_sotnikov_available"
        ]
        self.assertTrue(any(entry.value == "no" for entry in alternatives))

    def test_ai_sotnikov_appointment_releases_exactly_one_of_three_national_advisors(
        self,
    ):
        from itertools import combinations
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        focus = self.focuses["STP_pc_lib_civil_army"]
        ai_blocks = [
            entry.value
            for entry in self.walk(self.one(focus, "completion_reward"))
            if entry.key == "if"
            and any(
                child.key == "limit"
                and any(
                    condition.key == "is_ai" and condition.value == "yes"
                    for condition in child.value
                )
                for child in entry.value
            )
        ]
        self.assertEqual(len(ai_blocks), 1)
        branches = [entry for entry in ai_blocks[0] if entry.key != "limit"]
        candidates = [
            idea.key
            for slot, idea in self.candidates
            if slot == "high_command"
            and self.one(self.one(idea.value, "allowed"), "tag") == "STS"
        ]
        self.assertEqual(len(candidates), 6)
        for hired in combinations(candidates, 3):
            facts = {("STS", "has_idea", key): True for key in hired}
            removed = [
                entry.value
                for _, entry in selected_effects(branches, facts, "STS")
                if entry.key == "remove_ideas"
            ]
            self.assertEqual(len(removed), 1, hired)
            self.assertIn(removed[0], hired)


if __name__ == "__main__":
    unittest.main()
