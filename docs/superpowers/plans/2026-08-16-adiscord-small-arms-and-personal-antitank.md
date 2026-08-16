# A-DISCORD Small Arms and Personal Anti-Tank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace vague infantry weapon research with real small-arms and personal anti-tank engineering, align equipment tiers with existing 3D weapon entities, and add twelve original compact anti-tank icons.

**Architecture:** Keep stable technology and equipment IDs. Author names, descriptions, effects, unlocks, and generated localisation in the technology builder; keep equipment stats in the equipment database; use vanilla/regional `infantry`, `infantry_2`, and `infantry_3` entity families; extend the deterministic icon manifest and builder for generated anti-tank art.

**Tech Stack:** Python 3 generators and `unittest`, Pillow RGBA/DDS rendering, HOI4 Clausewitz technology/equipment/entity syntax, UTF-8 BOM localisation.

## Global Constraints

- Russian branch title: exactly `Индивидуальные противотанковые средства`.
- Preserve all 16 small-arms technology IDs, 12 personal anti-tank technology IDs, and 9 infantry equipment IDs.
- Change owning builders and regenerate; do not hand-edit generated technology, GFX, GUI, or generated localisation.
- Russian localisation remains UTF-8 with BOM.
- Reference only entities, meshes, textures, and attachments proven to exist.
- First automatic equipment generation uses visual level 2; late automatic generations use level 3.
- Anti-tank icons are centered 72x72 DDS files with no text, logo, border, or clipped object.
- Preserve unrelated dirty work. Do not stage or commit in this shared checkout.
- Static validation does not replace a full HOI4 restart and fresh-campaign visual test.

---

### Task 1: Lock the real-engineering technology contract

**Files:**
- Modify: `tools/tests/test_build_adiscord_technology_system.py`
- Modify: `tools/builders/build_adiscord_technology_system.py`

**Interfaces:**
- Consumes: `Branch`, `Tech`, `BRANCH_BY_KEY`, `effects_for()`, and `generated_localisation()`.
- Produces: `TECHNICAL_TECH_DESCRIPTIONS: dict[str, tuple[str, str]]`, updated branch text, causal effects, and stable RU/EN localisation keys.

- [ ] **Step 1: Write the failing name contract**

Add a test asserting these exact RU lists:

```python
small_arms_names = [
    "Прецизионная нарезка каналов стволов",
    "Обтюрация казённой части",
    "Унитарный металлический патрон",
    "Нитроцеллюлозные метательные составы",
    "Лазерное измерение дальности",
    "Промежуточные патроны",
    "Высокопрочные ствольные стали",
    "Самозарядная автоматика",
    "Вычислительное определение баллистической поправки",
    "Газоотводная автоматика",
    "Запирание поворотным затвором",
    "Интегрированные электронно-оптические прицелы",
    "Хромирование и износостойкие покрытия ствола",
    "Оптимизация импульса отдачи",
    "Полимерные и гибридные гильзы",
    "Программируемые боеприпасы",
]
anti_tank_names = [
    "Бутылочные зажигательные смеси",
    "Динамитные и ранцевые подрывные заряды",
    "Ручные кумулятивные противотанковые гранаты",
    "Крупнокалиберные противотанковые ружья",
    "Командное наведение по проводной линии",
    "Безоткатные противотанковые системы",
    "Полуавтоматическое наведение по линии визирования",
    "Реактивные гранатомёты с кумулятивной боевой частью",
    "Инфракрасное самонаведение верхней атаки",
    "Тандемные кумулятивные боевые части",
    "Барражирующие противотанковые боеприпасы",
    "Кооперативное мультиспектральное целеуказание",
]
self.assertEqual([tech.ru for tech in generator.BRANCH_BY_KEY["small_arms"].techs], small_arms_names)
anti_tank = generator.BRANCH_BY_KEY["anti_tank_infantry"]
self.assertEqual(anti_tank.ru, "Индивидуальные противотанковые средства")
self.assertEqual([tech.ru for tech in anti_tank.techs], anti_tank_names)
```

- [ ] **Step 2: Write the failing authored-description contract**

```python
def test_weapon_technologies_have_authored_technical_descriptions(self) -> None:
    keys = {
        tech.key
        for branch_key in ("small_arms", "anti_tank_infantry")
        for tech in generator.BRANCH_BY_KEY[branch_key].techs
    }
    self.assertEqual(keys, keys & set(generator.TECHNICAL_TECH_DESCRIPTIONS))
    for language in ("russian", "english"):
        rendered = "\n".join(generator.generated_localisation(language))
        language_index = 0 if language == "russian" else 1
        for key in keys:
            self.assertIn(generator.TECHNICAL_TECH_DESCRIPTIONS[key][language_index], rendered)
```

- [ ] **Step 3: Run the two tests and verify RED**

Run the two named `CompactTechnologyTreeContractTests` methods with `python -B -m unittest`. Expected: old names/title and missing description table fail.

- [ ] **Step 4: Author the two branches without changing IDs**

Update the small-arms branch and `INFANTRY_ANTI_TANK_BRANCH` with the exact RU names above, faithful English equivalents, current stable keys, and existing graph-compatible ordering. Use custom icon stems for all 12 anti-tank nodes.

- [ ] **Step 5: Add exact technical descriptions**

Create `TECHNICAL_TECH_DESCRIPTIONS` entries for all 28 keys. Each RU/EN entry explains the physical mechanism and restored manufacturing capability in one or two sentences. Avoid corporate, network, platform, and generic upgrade prose.

- [ ] **Step 6: Route localisation through authored descriptions**

In `generated_localisation()` select `TECHNICAL_TECH_DESCRIPTIONS[tech.key]` when present; otherwise retain `BRANCH_DESCRIPTION_RU/EN`. Do not repeat the technology name at the start of `_desc`.

- [ ] **Step 7: Make effect packages causal**

Add explicit small-arms packages: barrel/ammunition nodes improve soft attack; actions/recoil improve breakthrough and soft attack; sights improve coordination or night capability; materials use bounded reliability-adjacent combat modifiers supported by HOI4. Keep anti-tank direct-fire indices `(3, 5, 7, 9)` focused on `hard_attack`/`breakthrough`, guided indices `(4, 6, 8, 10)` on `ap_attack`/`coordination_bonus`, and node 11 as bounded synthesis.

- [ ] **Step 8: Run the technology-system test module**

Run `python -B -m unittest tools.tests.test_build_adiscord_technology_system`. Expected: green before regeneration.

---

### Task 2: Align equipment unlocks and visual levels

**Files:**
- Modify: `tools/tests/test_build_adiscord_technology_system.py`
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Modify: `common/units/equipment/ADISCORD_infantry_equipment.txt`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py`

**Interfaces:**
- Consumes: stable equipment IDs, `ENABLE_EQUIPMENT`, `EQUIPMENT_UNLOCK_ICONS`, and validator equipment block extraction.
- Produces: exact unlock mapping and visual levels `(0, 1, 2, 2, 2, 3, 3, 3, 3)`.

- [ ] **Step 1: Change the milestone test to the approved unlock keys**

```python
milestone_keys = (
    "postwar_weapon_standardization",
    "refurbished_receivers",
    "sealed_receiver_assemblies",
    "smart_recoil_compensators",
    "smart_optics",
    "modular_rifle_kits",
    "programmable_ammunition",
    "coil_assisted_service_rifles",
    "networked_service_rifles",
)
```

Keep the current nine equipment IDs and nine wide icon IDs in their present order.

- [ ] **Step 2: Add the failing visual-level test**

```python
expected_levels = [0, 1, 2, 2, 2, 3, 3, 3, 3]
blocks = validator.collect_equipment_blocks()
actual_levels = [
    int(re.search(r"\bvisual_level\s*=\s*(\d+)", blocks[equipment]).group(1))
    for equipment in equipment_ids
]
self.assertEqual(actual_levels, expected_levels)
```

- [ ] **Step 3: Run milestone and visual tests and verify RED**

Expected: current unlock keys and current visual tuple fail.

- [ ] **Step 4: Update unlock maps and equipment visuals**

Remap `ENABLE_EQUIPMENT` and `EQUIPMENT_UNLOCK_ICONS` to the milestone keys from Step 1. Change only the nine equipment `visual_level` values to `0,1,2,2,2,3,3,3,3`; keep IDs, parent chain, and stats intact unless a technical description exposes an obvious contradiction.

- [ ] **Step 5: Rewrite equipment descriptions technically**

Keep terse in-world series names, but change `LAND_EQUIPMENT_LOCALISATION` descriptions to identify cartridge, action, barrel, sight, case, recoil, or programmable-ammunition changes. Remove unsupported claims about distributed networks.

- [ ] **Step 6: Update validator expectations and run focused checks**

Change `validate_infantry_equipment_visuals()` to the approved tuple. Run the technology tests and `python -B tools/validate_adiscord_tech_doctrine.py`; expect green.

---

### Task 3: Complete the custom 3D entity progression

**Files:**
- Modify: `tools/tests/test_build_adiscord_technology_system.py`
- Modify: `gfx/entities/zz_ADISCORD_country_infantry.asset`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py`

**Interfaces:**
- Consumes: vanilla `infantry_2_entity`, existing `STP_infantry_2_entity`, `VAL_infantry_2_entity`, and country graphical-culture fallbacks.
- Produces: `STP_infantry_3_entity`, `NOD_infantry_3_entity`, and `VAL_infantry_3_entity` without new meshes/textures.

- [ ] **Step 1: Add a failing entity clone test**

Parse `gfx/entities/zz_ADISCORD_country_infantry.asset` with the validator's existing block extractor and require:

```python
expected_clones = {
    "STP_infantry_3_entity": "STP_infantry_2_entity",
    "NOD_infantry_3_entity": "STP_infantry_3_entity",
    "VAL_infantry_3_entity": "VAL_infantry_2_entity",
}
```

- [ ] **Step 2: Run the entity test and verify RED**

Expected: all three third-level entities are absent.

- [ ] **Step 3: Add only the missing clones**

```text
entity = {
    clone = "STP_infantry_2_entity"
    name = "STP_infantry_3_entity"
}
entity = {
    clone = "STP_infantry_3_entity"
    name = "NOD_infantry_3_entity"
}
entity = {
    clone = "VAL_infantry_2_entity"
    name = "VAL_infantry_3_entity"
}
```

Do not override vanilla `units_infantry.asset` and do not introduce mesh, DDS, or attachment paths.

- [ ] **Step 4: Validate entity references**

Extend the focused validator for the three clone relationships while preserving its checks against legacy/global overrides. Run the named test and technology validator; expect green.

---

### Task 4: Generate and register twelve anti-tank icons

**Files:**
- Create: `tools/assets/source/technology_weapons/personal_antitank_generated_sheet.png`
- Modify: `tools/data/adiscord_technology_weapon_icons.json`
- Modify: `tools/tests/test_build_adiscord_technology_icons.py`
- Modify: `tools/builders/build_adiscord_technology_icons.py`
- Generate: `gfx/interface/technologies/ADISCORD_antitank_*.dds`

**Interfaces:**
- Consumes: `IconSpec`, `load_manifest()`, `render_outputs()`, `COMPACT_SIZE`.
- Produces: family `personal_antitank`, tiers 1-12, exact 72x72 DDS outputs, updated contact sheet.

- [ ] **Step 1: Add failing manifest/output tests**

Require 12 entries where `family == "personal_antitank"`, tiers `1..12`, unique outputs, `kind == "compact"`, and rendered size `(72, 72)`. Narrow the night-sheet test to `family == "night"`. Change expected technology DDS count from 24 to 36.

- [ ] **Step 2: Run icon tests and verify RED**

Run `python -B -m unittest tools.tests.test_build_adiscord_technology_icons`. Expected: missing manifest family and outputs.

- [ ] **Step 3: Generate one auditable 4x3 source sheet**

Use image generation with no reference image. Require strict row-major cells, isolated centered objects, dark neutral background, consistent lighting, generous margins, no text/border/logo, in this order: incendiary bottle; dynamite/satchel charge; shaped-charge hand grenade; anti-tank rifle; wire-guidance launcher; recoilless launcher; SACLOS sight/launcher; shaped-charge rocket launcher; imaging-infrared top-attack launcher; tandem warhead cutaway; loitering anti-armor munition; multispectral designator and launcher.

- [ ] **Step 4: Inspect and register the accepted source**

Inspect at original detail. Reject clipping, duplicate objects, text, or merged cells. Copy the accepted image to the source path, record actual size and SHA-256, and add explicit non-overlapping row-major crops.

- [ ] **Step 5: Use exact output stems**

```text
ADISCORD_antitank_01_incendiary_bottle.dds
ADISCORD_antitank_02_satchel_charge.dds
ADISCORD_antitank_03_shaped_charge_grenade.dds
ADISCORD_antitank_04_antitank_rifle.dds
ADISCORD_antitank_05_wire_guidance.dds
ADISCORD_antitank_06_recoilless_launcher.dds
ADISCORD_antitank_07_saclos_guidance.dds
ADISCORD_antitank_08_rocket_launcher.dds
ADISCORD_antitank_09_top_attack_seeker.dds
ADISCORD_antitank_10_tandem_warhead.dds
ADISCORD_antitank_11_loitering_munition.dds
ADISCORD_antitank_12_multispectral_targeting.dds
```

- [ ] **Step 6: Update contact-sheet layout and technology bindings**

Label compact night icons with `N` and anti-tank icons with `A`. Wrap or extend the sheet so width stays at most 2000 pixels and no icon is outside bounds. Bind the 12 output stems to the 12 anti-tank technologies; ensure `icon_for_technology()` does not replace them through a branch palette.

- [ ] **Step 7: Apply and prove icon idempotence**

Run the icon builder with `--apply`, then `--check`, then the icon test module. Run a second `--apply` and compare hashes of all 12 DDS files and the contact sheet; expect identical bytes.

---

### Task 5: Regenerate and verify all outputs

**Files:**
- Generate: `common/technologies/ADISCORD_infantry.txt`
- Generate: `interface/ADISCORD_technologies.gfx`
- Generate: RU/EN `ADISCORD_technology_doctrine` localisation
- Verify: all files changed in Tasks 1-4

**Interfaces:**
- Consumes: completed builders, source art, stable IDs.
- Produces: byte-current generated outputs and static acceptance evidence.

- [ ] **Step 1: Run technology generator check, apply, and check**

Run `python -B tools/build_adiscord_technology_system.py --check`, then `--apply`, then `--check`. Capture SHA-256 hashes of generated outputs, run a second apply, and confirm identical hashes because these paths were already dirty before this task.

- [ ] **Step 2: Verify generated localisation**

Assert both RU and EN files contain all 28 names and `_desc` keys. Assert the exact Russian anti-tank title. Verify RU file begins with bytes `EF BB BF`. Search for superseded player-facing vague names and remove only occurrences owned by this programme.

- [ ] **Step 3: Run focused test set**

```powershell
python -B -m unittest tools.tests.test_build_adiscord_technology_system tools.tests.test_build_adiscord_technology_icons tools.tests.test_validate_adiscord_technology_contracts tools.tests.test_generated_output_ownership
```

Expected: all pass.

- [ ] **Step 4: Run focused and repository validators**

```powershell
python -B tools/validate_adiscord_tech_doctrine.py
python -B tools/validate_tc.py --limit 300
```

Expected: success. Report unrelated pre-existing errors without modifying their owners.

- [ ] **Step 5: Run whitespace gates**

Run scoped `git diff --check` for the plan's files, then repository `git diff --check`. Expected: no new errors. Verify BOM separately.

- [ ] **Step 6: Inspect the scoped diff without staging**

Confirm no technology/equipment ID was deleted, the squad-weapons programme was not rewritten, only STP/NOD/VAL received third-level entity clones, and all generated assets are owned and reproducible. Do not stage or commit.

- [ ] **Step 7: Record runtime acceptance still required**

After a full restart and fresh campaign, inspect branch spacing/connectors, icon clipping, RU tooltips, and researchability. Check representative western, middle-eastern, and custom-uniform infantry with early rifle, level-2 automatic, and level-3 late automatic equipment. Inspect fresh `logs/error.log` for missing entities, meshes, attachments, sprites, or localisation.
