# A-Discord Law Localisation Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace artificial player-facing law terminology with the approved restrained historical register in Russian and English without changing law mechanics.

**Architecture:** Keep Clausewitz idea definitions and technical IDs untouched. Treat Russian localisation as the editorial source, add a complete English counterpart for the custom-law file, and protect both languages with a focused Python `unittest` contract that checks BOMs, key parity, approved names, duplicate keys, and retired wording.

**Tech Stack:** Hearts of Iron IV Clausewitz localisation YAML, Python 3 standard-library `unittest`, repository validators, PowerShell, Git.

## Global Constraints

- Preserve every law category ID, law ID, category membership, modifier, cost, availability rule, AI weight, and starting country law package.
- Preserve the names already approved for retention; only names listed in the design mapping may change.
- Revised names use restrained historical realism and normally contain two to four words.
- Revised descriptions explain the institution and its practical trade-off without quoting modifier values.
- Remove developer-facing terms such as `vanilla-модификаторы` and literary phrasing such as `страна хуже дышит`.
- Shared global keys must not contain country-specific lore.
- Russian defines the editorial tone; English must be idiomatic rather than a word-for-word calque.
- Russian and English localisation files must use UTF-8 with a BOM.
- Use `apply_patch` for text edits. Do not rewrite localisation through PowerShell or Python.
- Preserve unrelated dirty work. Before every commit, stage only the exact files named by that task and inspect `git diff --cached --name-only`.
- Do not launch Hearts of Iron IV without explicit user authorisation. Runtime acceptance requires a full launcher/Steam restart and a fresh campaign.

## File Structure

- Create `tools/tests/test_adiscord_law_localisation.py`: focused bilingual contract for custom laws and economic-system law text.
- Modify `localisation/russian/ADISCORD_laws_l_russian.yml`: authoritative Russian custom-law category, name, and description copy.
- Create `localisation/english/ADISCORD_laws_l_english.yml`: complete English counterpart with the same key set as the Russian custom-law file.
- Modify `localisation/russian/ADISCORD_economy_l_russian.yml`: approved Russian economic-system names, descriptions, category copy, and synchronized dashboard model labels.
- Modify `localisation/english/ADISCORD_economy_l_english.yml`: English economic-system law keys and synchronized dashboard model labels.
- Read only `common/ideas/ADISCORD_laws.txt` and `common/ideas/_economic.txt`: source of truth for modifiers and availability used to verify description claims.
- Read only `docs/superpowers/specs/2026-08-16-adiscord-law-localisation-design.md`: approved terminology and editorial rules.

No listed localisation output is owned by `tools/data/generated_output_owners.json`. Do not add a builder.

---

### Task 1: Russian Civilian-Law Contract and Copy

**Files:**
- Create: `tools/tests/test_adiscord_law_localisation.py`
- Modify: `localisation/russian/ADISCORD_laws_l_russian.yml:1-198`
- Read: `common/ideas/ADISCORD_laws.txt:1-1423`
- Read: `docs/superpowers/specs/2026-08-16-adiscord-law-localisation-design.md:24-98`

**Interfaces:**
- Consumes: existing `ADISCORD_*` category and law IDs from `ADISCORD_laws.txt`.
- Produces: `parse_localisation(path: Path) -> tuple[str, dict[str, str], dict[str, int]]` and the authoritative `APPROVED_RU_CIVILIAN_NAMES` mapping used by later tasks.

- [ ] **Step 1: Add the focused parser and failing civilian-name contract**

Create `tools/tests/test_adiscord_law_localisation.py` with this initial structure:

`@python
import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RU_LAWS = ROOT / "localisation/russian/ADISCORD_laws_l_russian.yml"
LAW_DEFINITIONS = ROOT / "common/ideas/ADISCORD_laws.txt"

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
)


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


if __name__ == "__main__":
    unittest.main()
`@

- [ ] **Step 2: Run the civilian contract and verify RED**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation.LawLocalisationContractTests.test_approved_russian_civilian_names
`@

Expected: FAIL on `ADISCORD_society_type_laws` because the current value is `Тип общества`.

- [ ] **Step 3: Apply the approved Russian civilian names and rewrite affected descriptions**

Use `APPROVED_RU_CIVILIAN_NAMES` as the exact name mapping. Do not rename any custom-law key absent from that dictionary.

For descriptions, inspect the corresponding modifiers and availability in `common/ideas/ADISCORD_laws.txt`, then rewrite the category and law descriptions under these prefixes:

`@python
CIVILIAN_PREFIXES = (
    "ADISCORD_society_type_",
    "ADISCORD_information_",
    "ADISCORD_taxation_",
    "ADISCORD_welfare_",
    "ADISCORD_education_",
    "ADISCORD_healthcare_",
    "ADISCORD_cultural_policy_",
    "ADISCORD_industrial_policy_",
    "ADISCORD_labor_policy_",
    "ADISCORD_infrastructure_",
)
`@

Retain an existing description only when it already states the institution and trade-off plainly. Every description containing a fragment from `RETIRED_RU_CIVILIAN_FRAGMENTS` must be replaced. Use the two-sentence pattern approved in the design; do not mention numeric modifiers or technical implementation.

- [ ] **Step 4: Run the complete focused contract**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation
`@

Expected: 3 tests, all PASS.

- [ ] **Step 5: Verify encoding and inspect only the task diff**

Run:

`@powershell
$lawRu = Resolve-Path 'localisation\russian\ADISCORD_laws_l_russian.yml'
$bytes = [System.IO.File]::ReadAllBytes($lawRu)
if (-not ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)) { throw 'Russian laws localisation lost its UTF-8 BOM' }
git diff --check -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_laws_l_russian.yml
git diff -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_laws_l_russian.yml
`@

Expected: BOM check succeeds, `diff --check` prints nothing, and no gameplay definition appears in the diff.

- [ ] **Step 6: Commit the civilian localisation slice**

`@powershell
git add -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_laws_l_russian.yml
git diff --cached --name-only
git diff --cached --check
git commit -m "loc: rewrite civilian law terminology"
`@

Expected staged paths: exactly the two files listed above.

---

### Task 2: Russian Military and Security Copy

**Files:**
- Modify: `tools/tests/test_adiscord_law_localisation.py`
- Modify: `localisation/russian/ADISCORD_laws_l_russian.yml:29-198`
- Read: `common/ideas/ADISCORD_laws.txt:441-1910`
- Read: `docs/superpowers/specs/2026-08-16-adiscord-law-localisation-design.md:96-121`

**Interfaces:**
- Consumes: `parse_localisation` and `RU_LAWS` from Task 1.
- Produces: `APPROVED_RU_MILITARY_NAMES` and the completed restrained Russian custom-law copy.

- [ ] **Step 1: Add the failing military-name and retired-wording contract**

Add:

`@python
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
)

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
`@

Place both methods inside `LawLocalisationContractTests`.

- [ ] **Step 2: Run the military-name test and verify RED**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation.LawLocalisationContractTests.test_approved_russian_military_names
`@

Expected: FAIL on `ADISCORD_military_organization_militia_autonomy` because the current value is `Автономные ополчения`.

- [ ] **Step 3: Apply the approved military names and rewrite affected descriptions**

Use `APPROVED_RU_MILITARY_NAMES` exactly. Inspect modifiers and availability before rewriting descriptions under:

`@python
MILITARY_PREFIXES = (
    "ADISCORD_military_organization_",
    "ADISCORD_officer_corps_",
    "ADISCORD_logistics_",
    "ADISCORD_training_",
    "ADISCORD_internal_security_",
)
`@

Keep `Политическая полиция` direct and institutionally descriptive. Do not soften it back to a generic investigative service. Retain names absent from the approved mapping, including `Кадровая армия`, `Политические комиссары`, `Академия Генштаба`, `Моторизованное снабжение`, `Чрезвычайные реквизиции`, `Базовая муштра`, and `Чрезвычайные патрули`.

- [ ] **Step 4: Run the complete focused contract**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation
`@

Expected: 5 tests, all PASS.

- [ ] **Step 5: Inspect and commit only the Russian military slice**

`@powershell
git diff --check -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_laws_l_russian.yml
git diff -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_laws_l_russian.yml
git add -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_laws_l_russian.yml
git diff --cached --name-only
git diff --cached --check
git commit -m "loc: rewrite military law terminology"
`@

Expected staged paths: exactly the two files listed above.

---

### Task 3: Complete English Custom-Law Localisation

**Files:**
- Modify: `tools/tests/test_adiscord_law_localisation.py`
- Create: `localisation/english/ADISCORD_laws_l_english.yml`
- Read: `localisation/russian/ADISCORD_laws_l_russian.yml:1-198`
- Read: `common/ideas/ADISCORD_laws.txt:1-1910`

**Interfaces:**
- Consumes: the final Russian key set and descriptions from Tasks 1-2.
- Produces: an English file with a one-to-one key mapping and `APPROVED_ENGLISH_CUSTOM_NAMES`.

- [ ] **Step 1: Add the failing English completeness contract**

Add `EN_LAWS`, approved English names, and these tests:

`@python
EN_LAWS = ROOT / "localisation/english/ADISCORD_laws_l_english.yml"

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
`@

Place both methods inside `LawLocalisationContractTests`.

- [ ] **Step 2: Run the English parity test and verify RED**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation.LawLocalisationContractTests.test_english_custom_laws_have_bom_unique_keys_and_russian_parity
`@

Expected: FAIL with `English custom-law localisation is missing`.

- [ ] **Step 3: Create the complete English custom-law file**

Create `localisation/english/ADISCORD_laws_l_english.yml` with a UTF-8 BOM and `l_english:` header. Mirror every key from the Russian file exactly once, including `vacant`, the three broad law categories, all custom category names/descriptions, and all 75 law names/descriptions.

Use `APPROVED_ENGLISH_CUSTOM_NAMES` exactly for renamed entries. Translate retained names naturally. Each description must preserve the institution and trade-off of the final Russian text and must not introduce a mechanic absent from the matching idea definition.

- [ ] **Step 4: Run the complete focused contract**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation
`@

Expected: 7 tests, all PASS.

- [ ] **Step 5: Inspect and commit only the English-localisation slice**

`@powershell
git diff --check -- tools/tests/test_adiscord_law_localisation.py localisation/english/ADISCORD_laws_l_english.yml
git diff -- tools/tests/test_adiscord_law_localisation.py
git diff --no-index -- NUL localisation/english/ADISCORD_laws_l_english.yml
git add -- tools/tests/test_adiscord_law_localisation.py localisation/english/ADISCORD_laws_l_english.yml
git diff --cached --name-only
git diff --cached --check
git commit -m "loc: add English custom law localisation"
`@

Expected staged paths: exactly the two files listed above. A `git diff --no-index` exit code of 1 is expected because it is displaying a new file; content or encoding errors are not expected.

---

### Task 4: Bilingual Economic-System Terminology

**Files:**
- Modify: `tools/tests/test_adiscord_law_localisation.py`
- Modify: `localisation/russian/ADISCORD_economy_l_russian.yml:103-110,347-394`
- Modify: `localisation/english/ADISCORD_economy_l_english.yml:103-110`
- Read: `common/ideas/_economic.txt:442-784`
- Read: `docs/superpowers/specs/2026-08-16-adiscord-law-localisation-design.md:53-94`

**Interfaces:**
- Consumes: `parse_localisation` from Task 1.
- Produces: exact approved economic-system law names in both languages and synchronized dashboard model labels.

- [ ] **Step 1: Add the failing bilingual economic-system contract**

Add:

`@python
RU_ECONOMY = ROOT / "localisation/russian/ADISCORD_economy_l_russian.yml"
EN_ECONOMY = ROOT / "localisation/english/ADISCORD_economy_l_english.yml"

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
    "ADISCORD_economy_model_6": "Клановая экономика",
}

APPROVED_EN_MODEL_LABELS = {
    "ADISCORD_economy_model_3": "State-regulated economy",
    "ADISCORD_economy_model_4": "Administrative command economy",
    "ADISCORD_economy_model_6": "Clan economy",
}

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
`@

Place the methods inside `LawLocalisationContractTests`.

- [ ] **Step 2: Run the economic-system tests and verify RED**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation.LawLocalisationContractTests.test_approved_bilingual_economic_system_names
`@

Expected: FAIL because the Russian industrializing name is still `Индустриализирующаяся экономика` and the English economic-system law keys are absent.

- [ ] **Step 3: Update Russian economic-law names and descriptions**

Apply `APPROVED_RU_ECONOMIC_SYSTEM_NAMES` and `APPROVED_RU_MODEL_LABELS` exactly. Rewrite `economy_desc` and `ADISCORD_economic_system_laws_desc` without `vanilla` terminology. Review all nine economic-system descriptions against `common/ideas/_economic.txt` and rewrite any literary, evaluative, or mechanically inaccurate wording using the approved two-part register.

- [ ] **Step 4: Add English economic-system law keys and synchronize model labels**

Add exactly one name and one `_desc` key for the economic-system category and each of the nine economic-system law IDs. Use `APPROVED_EN_ECONOMIC_SYSTEM_NAMES` and `APPROVED_EN_MODEL_LABELS` exactly. Descriptions must be idiomatic semantic counterparts of the final Russian copy and must match the actual modifiers and availability.

- [ ] **Step 5: Run focused law and existing economy contracts**

Run:

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation
python -B -m unittest tools.tests.test_adiscord_economy_weekly_contracts
`@

Expected: 10 focused law-localisation tests PASS and 98 economy contract tests PASS.

- [ ] **Step 6: Verify all four localisation BOMs**

`@powershell
$lawLocPaths = @(
    'localisation\russian\ADISCORD_laws_l_russian.yml',
    'localisation\english\ADISCORD_laws_l_english.yml',
    'localisation\russian\ADISCORD_economy_l_russian.yml',
    'localisation\english\ADISCORD_economy_l_english.yml'
)
foreach ($path in $lawLocPaths) {
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $path))
    if (-not ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)) {
        throw "$path lost its UTF-8 BOM"
    }
}
`@

Expected: no output and exit code 0.

- [ ] **Step 7: Inspect and commit only the economic terminology slice**

`@powershell
git diff --check -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_economy_l_russian.yml localisation/english/ADISCORD_economy_l_english.yml
git diff -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_economy_l_russian.yml localisation/english/ADISCORD_economy_l_english.yml
git add -- tools/tests/test_adiscord_law_localisation.py localisation/russian/ADISCORD_economy_l_russian.yml localisation/english/ADISCORD_economy_l_english.yml
git diff --cached --name-only
git diff --cached --check
git commit -m "loc: normalize economic system terminology"
`@

Expected staged paths: exactly the three files listed above.

---

### Task 5: Release Gates and Runtime Acceptance

**Files:**
- Verify: `tools/tests/test_adiscord_law_localisation.py`
- Verify: `localisation/russian/ADISCORD_laws_l_russian.yml`
- Verify: `localisation/english/ADISCORD_laws_l_english.yml`
- Verify: `localisation/russian/ADISCORD_economy_l_russian.yml`
- Verify: `localisation/english/ADISCORD_economy_l_english.yml`
- Read only: `common/ideas/ADISCORD_laws.txt`
- Read only: `common/ideas/_economic.txt`

**Interfaces:**
- Consumes: completed bilingual localisation and contract tests from Tasks 1-4.
- Produces: static release evidence plus a fresh-game law-screen acceptance result.

- [ ] **Step 1: Run the focused contracts**

`@powershell
python -B -m unittest tools.tests.test_adiscord_law_localisation
python -B -m unittest tools.tests.test_adiscord_economy_weekly_contracts
python -B tools\validate_adiscord_economy_ai.py
`@

Expected: all law-localisation and economy tests PASS; the economy/AI validator reports no issues.

- [ ] **Step 2: Run the total-conversion validator**

`@powershell
python -B tools\validate_tc.py --limit 300
`@

Expected: every reported section is `OK`.

- [ ] **Step 3: Verify retired text, raw keys, encoding, and diff hygiene**

`@powershell
rg -n -i "vanilla-модификаторы|страна меньше спорит|меньше романтики|фронт благодарит|общество дышит меньше" localisation\russian\ADISCORD_laws_l_russian.yml localisation\russian\ADISCORD_economy_l_russian.yml
git diff --check
git diff --cached --check
git status --short
`@

Expected: `rg` returns no matches; both diff checks report no whitespace errors. Review `git status` and attribute every remaining path before any further commit.

- [ ] **Step 4: Confirm the implementation commits contain localisation scope only**

Run `git show --stat --oneline` for each commit created by Tasks 1-4. Expected paths are limited to:

`@text
tools/tests/test_adiscord_law_localisation.py
localisation/russian/ADISCORD_laws_l_russian.yml
localisation/english/ADISCORD_laws_l_english.yml
localisation/russian/ADISCORD_economy_l_russian.yml
localisation/english/ADISCORD_economy_l_english.yml
`@

No `common/ideas`, history, interface, icon, technology, or unrelated documentation file may appear.

- [ ] **Step 5: Obtain explicit permission and perform fresh runtime acceptance**

Ask the user to authorise a Hearts of Iron IV launch or to run the check themselves. Start through Steam/Paradox Launcher, fully restart the game, and create a fresh campaign. Do not use an old save as acceptance evidence.

Inspect the Politics law screen in Russian and English for:

`@text
Общественный уклад / Social Structure
Государственный контроль информации / State Information Control
Чрезвычайные сборы / Emergency Levies
Система территориальной обороны / Territorial Defense System
Политическая полиция / Political Police
Экономика индустриализации / Industrializing Economy
Административно-плановая экономика / Administrative Command Economy
`@

Expected: no raw localisation keys, no clipped or overlapping labels, descriptions wrap cleanly, and each displayed modifier remains unchanged. Capture fresh screenshots or record the exact unchecked surfaces if runtime access is unavailable.

- [ ] **Step 6: Report acceptance honestly**

Report static commands and exact counts from their fresh output. State runtime acceptance separately. Do not describe the work as runtime-verified unless the full restart, fresh campaign, and bilingual law-screen inspection were actually completed.
