# A-DISCORD: Individual Small Arms and Personal Anti-Tank Technologies

Date: 2026-08-16

## Objective

Rework the infantry small-arms and personal anti-tank programmes so that their
player-facing names, descriptions, effects, equipment unlocks, icons, and 3D
weapon progression are based on concrete weapon engineering rather than vague
futuristic terminology.

The setting does not rediscover firearms from first principles. Early research
represents rebuilding machine tools, material quality, gauges, interchangeable
parts, and repeatable mass production for already known mechanisms.

## Scope and ownership

The technology generator remains the source of truth for generated
technologies, layout, GFX declarations, equipment definitions, localisation,
and validators. Generated outputs must not be edited by hand.

Primary owned sources:

- `tools/builders/build_adiscord_technology_system.py`
- `tools/builders/build_adiscord_technology_icons.py`
- `tools/data/adiscord_technology_weapon_icons.json`
- focused tests and technology validators

Expected generated or directly maintained outputs include:

- `common/technologies/ADISCORD_infantry.txt`
- `common/units/equipment/ADISCORD_infantry_equipment.txt`
- `interface/ADISCORD_technologies.gfx`
- Russian and English technology/equipment localisation
- generated technology icon DDS files
- `gfx/entities/zz_ADISCORD_country_infantry.asset` for the narrowly scoped
  missing country-specific visual levels

The squad-weapons branch is out of scope except for reference validation. No
country, focus, economy, doctrine, or unrelated AI content is to be rewritten.

## Compatibility policy

The existing sixteen small-arms technology IDs, twelve personal anti-tank
technology IDs, and nine infantry equipment IDs remain stable. Their
player-facing meaning, descriptions, effects, unlock placement, and visual
levels may change. Legacy internal IDs are compatibility identifiers and are
not shown to players.

All references to retained IDs must continue to resolve. No save migration is
required because this work targets fresh campaigns, but starting technology
profiles and AI research weights must remain internally consistent.

## Small-arms research programme

The branch keeps its existing sixteen-node graph: a common industrial trunk,
three technical routes, and a final synthesis.

### Common industrial trunk

| Node | Player-facing technology | Engineering meaning |
| --- | --- | --- |
| 0 | Прецизионная нарезка каналов стволов | Restored tooling and gauges for repeatable bore geometry, twist rate, and concentricity. |
| 1 | Обтюрация казённой части | Controlled chamber dimensions, headspace, and sealing of propellant gases. |
| 2 | Унитарный металлический патрон | Interchangeable case, primer, propellant, and projectile manufactured to one standard. |

### Propellants and materials route

| Node | Player-facing technology | Engineering meaning |
| --- | --- | --- |
| 3 | Нитроцеллюлозные метательные составы | Stable smokeless propellant geometry, burn rate, and batch control. |
| 6 | Высокопрочные ствольные стали | Heat treatment and alloy control for higher chamber pressure and barrel life. |
| 12 | Хромирование и износостойкие покрытия ствола | Protection against erosion and corrosion during sustained fire. |
| 14 | Полимерные и гибридные гильзы | Reduced cartridge mass without sacrificing chamber sealing or extraction strength. |

### Mechanisms and recoil route

| Node | Player-facing technology | Engineering meaning |
| --- | --- | --- |
| 5 | Промежуточные патроны | Cartridge impulse suited to controllable individual automatic fire. |
| 7 | Самозарядная автоматика | Use of firing energy to extract, feed, lock, and cock the weapon. |
| 9 | Газоотводная автоматика | Metered propellant gas drives a repeatable automatic cycle. |
| 10 | Запирание поворотным затвором | Multiple locking lugs contain pressure while preserving reliable extraction. |
| 13 | Оптимизация импульса отдачи | Moving mass, gas timing, buffers, and weapon geometry reduce dispersion in automatic fire. |

### Fire-control route

| Node | Player-facing technology | Engineering meaning |
| --- | --- | --- |
| 4 | Лазерное измерение дальности | Direct range measurement for the individual weapon sight. |
| 8 | Вычислительное определение баллистической поправки | Range, projectile data, atmosphere, and sight angle produce an aiming correction. |
| 11 | Интегрированные электронно-оптические прицелы | Day, low-light, and thermal channels share one aligned sight and ballistic solution. |

### Final synthesis

Node 15 becomes **Программируемые боеприпасы**. The fire-control unit transfers
range or burst data to a compatible fuze while the ammunition, action, and
barrel are manufactured to tolerances that make the programmed effect useful.

Russian descriptions use one or two technical sentences. English fallback
localisation conveys the same mechanism without fictional corporate language.

## Infantry equipment generations

Nine existing equipment IDs remain because they already have authored icons,
production-chain references, and useful intermediate stat steps. Research
nodes outnumber equipment generations, so effect-only research remains common.

| Equipment generation | Unlocking capability | Visual level | 3D presentation |
| --- | --- | --- | --- |
| `infantry_equipment_0` | node 0: restored rifling and inspection | 0 | recovered rifle set |
| `ADISCORD_infantry_equipment_2156` | node 1: controlled breech obturation | 1 | newly manufactured rifle/self-loader |
| `ADISCORD_infantry_equipment_2163` | node 5: standardized intermediate cartridge | 2 | automatic weapon via `infantry_2` family |
| `ADISCORD_infantry_equipment_2168` | node 7: repeatable self-loading action | 2 | automatic weapon |
| `ADISCORD_infantry_equipment_2170` | node 4: laser-assisted sighting | 2 | automatic weapon with new equipment icon, no arbitrary model swap |
| `ADISCORD_infantry_equipment_2178` | node 9: mature gas-operated action | 3 | late automatic weapon via `infantry_3` family |
| `ADISCORD_infantry_equipment_2183` | node 12: durable high-pressure barrel system | 3 | late automatic weapon |
| `ADISCORD_infantry_equipment_2193` | node 13: optimized recoil impulse | 3 | late automatic weapon |
| `ADISCORD_infantry_equipment_2200` | node 15: programmable ammunition and integrated fire control | 3 | late automatic weapon |

Equipment names may retain terse in-world series designations, but their
descriptions must state the actual mechanism and ammunition standard.

## 3D infantry weapon mapping

The mod uses the vanilla `sprite = infantry` selection chain. The equipment
`visual_level` selects the matching infantry entity family:

- rifle levels use the vanilla or regional rifle entity;
- visual level 2 uses the `infantry_2` automatic/MG family;
- visual level 3 uses the `infantry_3` late automatic family.

Country graphical cultures provide regional fallbacks. Existing custom
uniforms are preserved. `CIN`, `OSF`, and `APH` already define third-level
entities. Missing `STP_infantry_3_entity`, `NOD_infantry_3_entity`, and
`VAL_infantry_3_entity` are added as validated clones of their automatic
second-level entities, with only existing vanilla weapon attachments. No new
mesh, texture, asset, or entity reference may be invented.

The automatic equipment generation must visibly switch away from the early
rifle model in a fresh campaign. Static checks can validate entity existence
and attachment names, but only a restarted game can prove the runtime model.

## Personal anti-tank programme

The Russian branch title is exactly **Индивидуальные противотанковые средства**.
The twelve-node graph remains a common trunk, two parallel routes, and a final
synthesis.

### Common trunk

| Node | Player-facing technology |
| --- | --- |
| 0 | Бутылочные зажигательные смеси |
| 1 | Динамитные и ранцевые подрывные заряды |
| 2 | Ручные кумулятивные противотанковые гранаты |

### Direct-fire route

| Node | Player-facing technology |
| --- | --- |
| 3 | Крупнокалиберные противотанковые ружья |
| 5 | Безоткатные противотанковые системы |
| 7 | Реактивные гранатомёты с кумулятивной боевой частью |
| 9 | Тандемные кумулятивные боевые части |

### Guided route

| Node | Player-facing technology |
| --- | --- |
| 4 | Командное наведение по проводной линии |
| 6 | Полуавтоматическое наведение по линии визирования |
| 8 | Инфракрасное самонаведение верхней атаки |
| 10 | Барражирующие противотанковые боеприпасы |

### Final synthesis

Node 11 becomes **Кооперативное мультиспектральное целеуказание**. Separate
observers, launchers, and loitering munitions exchange a target solution rather
than becoming a vague fictional network technology.

## Effects

Every modifier follows the physical capability:

- barrel geometry, cartridges, actions, and sights improve infantry attack,
  breakthrough, reliability-related capability, or coordination as supported
  by HOI4 modifiers;
- materials and coatings primarily improve reliability and sustained combat
  performance;
- lightweight cases may affect supply use or production cost only when the
  available modifier expresses the mechanism without disproportionate balance
  impact;
- direct-fire anti-tank research emphasizes hard attack and breakthrough;
- guided anti-tank research emphasizes piercing and coordination;
- early improvised anti-tank devices give smaller bonuses than mature launchers;
- the final anti-tank synthesis gives a bounded combined bonus.

No node receives a filler bonus unrelated to its mechanism. Existing balance
ceilings for a dense technology tree remain in force.

## Icons and UI

The existing horizontal branch layout and current wide small-arms equipment
icons remain. Effect-only small-arms nodes use appropriate compact technical
icons and must not create duplicate equipment generations.

The twelve personal anti-tank nodes receive twelve newly generated compact
icons. The source is an auditable generated sheet registered in the icon
manifest. Each crop is rendered to 72x72 DDS with:

- one centered, recognizable weapon or component;
- no text, labels, logos, or decorative border;
- sufficient internal margin to avoid clipping in the HOI4 frame;
- consistent lighting and the established dark military-technical style.

The icon builder owns resizing, crops, DDS conversion, GFX declarations, and
the contact sheet. Re-running it must be idempotent.

## Validation and acceptance

Focused automated checks must prove:

1. the exact Russian anti-tank branch title;
2. all sixteen small-arms and twelve anti-tank player-facing names;
3. complete RU/EN names and technical descriptions;
4. equipment unlock ordering and absence of duplicate unlocks;
5. visual levels change only at real weapon-generation boundaries;
6. the first automatic generation uses visual level 2;
7. all regional/custom entity parents and weapon attachments exist;
8. all twelve anti-tank sprites resolve to 72x72 DDS files;
9. generator and icon builder checks are idempotent;
10. no missing localisation, GFX, or retained-ID references.

Required static gates include focused unit tests, the technology doctrine
validator, `python -B tools/validate_tc.py --limit 300`, BOM verification for
Russian localisation, and both scoped and repository `git diff --check`.

Runtime acceptance requires a full HOI4 restart and a fresh campaign. Inspect
the infantry and anti-tank branches for spacing, connectors, icon clipping,
tooltips, and researchability; then verify that rifle, automatic, and late
automatic equipment generations change the weapon shown by representative
generic, regional, and custom-uniform countries.

## Completion report

The handoff reports the final research sequences, equipment unlock table,
visual-level/entity mapping, renamed player-facing technologies, changed files,
test and validator results, and any unavoidable limitation in available vanilla
weapon assets.
