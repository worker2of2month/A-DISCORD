# Vorkerland Collapse and Dirty Zone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать фоновый каскадный распад конфедерации Воркерланда, настоящую многостороннюю войну ИИ, волновое появление стран Грязной зоны и четыре итоговые политические карты.

**Architecture:** Все стороны являются постоянными заранее объявленными тегами без стартовой территории. One-shot orchestrator освобождает субъектов, передаёт штаты, назначает столицы, загружает OOB и через сутки объявляет обычные войны; отдельный месячный pulse меняет фазы ИИ и проверяет победу. Грязные штаты получают постоянный state-scoped dynamic modifier, который в этой реализации никогда не снимается.

**Tech Stack:** Hearts of Iron IV Clausewitz script, state history, country/character/OOB databases, AI strategies, scripted GUI/superevents, Python 3 read-only validators.

## Global Constraints

- Работать прямо на `main` по явному разрешению пользователя.
- Не включать в коммиты чужие незавершённые изменения.
- Не изменять уже dirty-файлы `common/on_actions/00_ADISCORD_on_actions.txt`, `common/ai_strategy/default.txt`, `common/ai_strategy/VAL.txt` и `tools/validate_tc.py`; использовать отдельные файлы и отдельный валидатор.
- Не использовать `start_civil_war` и dynamic tags `D01`–`D50`.
- Использовать fixed tags: `TVA EYR EGC WPA WPS PSD EBA DVA SRA ZTA SLA RZA MLR ERT IRT SCA`.
- Каноническая Башня Единства: state `32`, province `6713`; state `40` остаётся вместе с метрополией.
- Взрыв запускается через 120–180 дней от старта кампании; Грязная зона открывается ещё через 60–90 дней.
- State `23` получает загрязнённый modifier, но никогда не передаётся новой стране.
- States `24/57` остаются VAL, states `59/60` остаются CIN.
- `ADISCORD_vorkerland_dirty_state` не получает `remove_trigger`, а код не вызывает `remove_dynamic_modifier`.
- Не менять `map/provinces.bmp`, `map/definition.csv`, `map/terrain.bmp`, `map/strategicregions`, `map/railways.txt` или `map/supply_nodes.txt`.
- Все видимые русские localisation-файлы сохранять UTF-8 BOM.
- Новые публичные названия — географические или административные, без пафосных самоназваний.
- Игрок не получает дерево решений или обязательные выборы; результат создают войны и ИИ.

---

## Shared Manifest

Создать `tools/vorkerland_collapse_manifest.py` и использовать эти значения в валидаторе:

```python
TAGS = (
    "TVA", "EYR", "EGC", "WPA", "WPS", "PSD", "EBA", "DVA",
    "SRA", "ZTA", "SLA", "RZA", "MLR", "ERT", "IRT", "SCA",
)

CONTAMINATED_STATES = {
    23, 24, 49, 51, 57, 59, 60, 125, 152, 153, 154, 155, 160,
    165, 166, 167, 168, 169, 171, 172, 173, 176, 177, 178, 180,
    181, 182, 183, 184, 185, 187, 188, 189, 190, 191, 192, 193,
}

DIRTY_GROUPS = {
    "SLA": (49, 51, 155, 176, 187, 191),
    "RZA": (125, 177, 188, 192),
    "MLR": (152, 153, 154, 160, 189, 190),
    "ERT": (167, 168, 169, 171, 184, 185),
    "IRT": (178, 180, 181, 182, 183, 193),
    "SCA": (165, 166, 172, 173),
}

CAPITALS = {
    "TVA": (36, 12227), "EYR": (102, 16594), "EGC": (81, 16587),
    "WPA": (195, 8032), "WPS": (196, 7129), "PSD": (194, 2339),
    "EBA": (197, 10016), "DVA": (145, 6729), "SRA": (198, 9104),
    "ZTA": (199, 12930), "SLA": (49, 16639), "RZA": (177, 2952),
    "MLR": (152, 9806), "ERT": (169, 10693), "IRT": (181, 2226),
    "SCA": (173, 6015),
}

STATE_PARTITIONS = {
    71: {
        71: (258,339,623,672,1129,1156,1514,1980,2713,3743,3925,4212,4771,5154,5225,5508,5691,5859,5893,6038,6295,6592,7360,7381,8101,8409,8468,8620,8901,8949,8988,9363,9988,10324,10388,10734,11454,11690,11971,12030,12241,12444,12473,12520,12733,12801,12877,16559,16561,16591),
        194: (773,1128,1375,1611,1685,1888,1906,1968,2192,2202,2339,2363,2571,2740,3757,3972,4381,4415,5080,5170,5469,5689,6461,6631,6921,7869,7989,8238,8300,8679,8869,8881,8926,9269,9453,9492,9509,9698,9725,9908,9935,10250,10345,11082,11505,12023,12103,12302,12441),
    },
    72: {
        72: (2565,3738,4178,4262,5136,5844,6181,6636,6730,7664,7685,7959,8631,8987,9022,10896,11703,11945,12093,12433,16622,16625),
        195: (647,806,1100,1111,2896,3534,4528,4634,7090,7230,8032,9075,9149,9158,9727,10606,11635,11717,12025,12995),
        196: (236,1569,1711,3069,3151,3928,4224,4331,5207,5409,6253,6799,7129,7341,7443,7827,7934,8051,10171,10864),
    },
    74: {
        74: (2197,2402,2516,2583,3492,5408,5666,5799,6543,8497,8704,12316,12541,12947,16585),
        197: (1386,2131,2474,6341,6560,6839,7406,9688,10016,10251,12923,16605,16608,16623,16626),
    },
    76: {
        76: (336,2552,2866,2988,3905,5721,5741,6443,9452,9833,10964,11090,16582),
        198: (513,741,3183,4185,6510,6764,8323,8570,9104,9193,9466,11282,11411,11659,12232,12564,12584),
    },
    80: {
        80: (265,449,686,860,868,1423,1426,1581,1672,1969,2914,3083,3567,3997,4133,4278,5153,5358,5376,5676,6399,7434,7770,7819,8849,9464,9845,10034,10609,10624,10746,11472,16619,16633,16634),
        199: (531,976,1280,1889,3345,3518,4501,5314,5524,5679,5888,6456,6465,6759,6820,7267,7942,9448,9811,10990,11379,11563,11592,12508,12930),
    },
}
```

---

### Task 1: Specialized Validator and Manifest

**Files:**
- Create: `tools/vorkerland_collapse_manifest.py`
- Create: `tools/validate_adiscord_vorkerland_collapse.py`
- Create: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Produces: `validate(root: Path) -> list[str]`, CLI `--section`, shared constants above.
- Consumes: only repository files; validator is read-only.

- [ ] **Step 1: Write the failing unit test**

```python
from tools.vorkerland_collapse_manifest import (
    CAPITALS, CONTAMINATED_STATES, DIRTY_GROUPS, STATE_PARTITIONS, TAGS,
)

def test_manifest_is_unique_and_complete():
    assert len(TAGS) == len(set(TAGS)) == 16
    assert len(CONTAMINATED_STATES) == 37
    assert set().union(*map(set, DIRTY_GROUPS.values())) == CONTAMINATED_STATES - {23, 24, 57, 59, 60}
    assert set(STATE_PARTITIONS) == {71, 72, 74, 76, 80}
    assert set(CAPITALS) == set(TAGS)
```

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v`

Expected: FAIL because `tools.vorkerland_collapse_manifest` does not exist.

- [ ] **Step 3: Implement manifest and validator**

The validator must expose sections `manifest`, `states`, `countries`,
`dirty`, `events`, `ai`, `outcomes`, and `superevents`. It parses text
without modifying it and exits `1` when the selected section has issues.

- [ ] **Step 4: Run GREEN and real preflight**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v`

Expected: PASS.

Run: `python tools/validate_adiscord_vorkerland_collapse.py --section countries`

Expected: FAIL with missing fixed tags, proving the feature gate detects absent content.

- [ ] **Step 5: Commit**

Commit only the three new `tools/` files:

`test: add vorkerland collapse validation manifest`

---

### Task 2: Split the Five Regional State Bases

**Files:**
- Modify: `history/states/71-71.txt`
- Modify: `history/states/72-72.txt`
- Modify: `history/states/74-74.txt`
- Modify: `history/states/76-76.txt`
- Modify: `history/states/80-80.txt`
- Create: `history/states/194-PWR-EAST.txt`
- Create: `history/states/195-ZAO-WEST.txt`
- Create: `history/states/196-ZAO-CENTER.txt`
- Create: `history/states/197-VLA-EAST.txt`
- Create: `history/states/198-SOL-WEST.txt`
- Create: `history/states/199-TRU-WEST.txt`
- Create: `localisation/russian/ADISCORD_vorkerland_collapse_states_l_russian.yml`
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Consumes: `STATE_PARTITIONS`.
- Produces: connected states 194–199 and capital provinces used by OOB/events.

- [ ] **Step 1: Add a failing partition test**

The test parses state province lists and asserts that every original
province appears exactly once across the relevant partition, all new IDs
exist, and capitals `2339/8032/7129/10016/9104/12930` belong to their
new states.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.StatePartitionTests -v`

Expected: FAIL because states 194–199 do not exist.

- [ ] **Step 3: Apply the exact `STATE_PARTITIONS` lists**

Use populations:

- `71=42500`, `194=42500`;
- `72=43334`, `195=43333`, `196=43333`;
- `74=70000`, `197=70000`;
- `76=75000`, `198=75000`;
- `80=115000`, `199=115000`.

Keep old VP/buildings in retained states. Give each new state
`infrastructure = 1`, its new VP value `3`, the same original owner/core,
and no extra factory except `194` gets one `arms_factory` transferred from
state 71. State 198 gets the civilian factory from state 76; state 199 gets
the arms factory from state 80.

Localisation:

```yaml
l_russian:
 STATE_194: "Восточная ремонтная полоса"
 STATE_195: "Западный участок периметра"
 STATE_196: "Центральный участок периметра"
 STATE_197: "Дальний плацдарм"
 STATE_198: "Запад Солнечной равнины"
 STATE_199: "Западное Златоречье"
 VICTORY_POINTS_2339: "Восточная станция"
 VICTORY_POINTS_8032: "Западный узел"
 VICTORY_POINTS_7129: "Центральная станция"
 VICTORY_POINTS_10016: "Дальний пост"
 VICTORY_POINTS_9104: "Солнечный пост"
 VICTORY_POINTS_12930: "Западное Златоречье"
```

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.StatePartitionTests -v`

Expected: PASS.

Run: `python tools/validate_tc.py --limit 80`

Expected: no new duplicate/missing province or invalid owner/core findings.

- [ ] **Step 5: Commit**

`feat: split vorkerland regional states`

---

### Task 3: Fixed Country Roster, Characters, Flags, and OOBs

**Files:**
- Create: `common/country_tags/01_ADISCORD_vorkerland_collapse_tags.txt`
- Create: `common/countries/{TVA,EYR,EGC,WPA,WPS,PSD,EBA,DVA,SRA,ZTA,SLA,RZA,MLR,ERT,IRT,SCA}.txt`
- Create: `history/countries/<TAG> - <slug>.txt` for all 16 tags
- Create: `history/units/<TAG>_vorkerland_collapse.txt` for all 16 tags
- Create: `common/characters/ADISCORD_vorkerland_collapse_characters.txt`
- Create: `interface/ADISCORD_vorkerland_collapse_portraits.gfx`
- Create: 48 flag files under `gfx/flags`, `gfx/flags/medium`, `gfx/flags/small`
- Create: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Produces: dormant fixed tags with leaders and loadable OOB names `<TAG>_vorkerland_collapse`.
- Does not give any new tag states, cores, or startup OOB.

Roster:

| Tag | Name | Leader | RGB | Flag source |
|---|---|---|---|---|
| TVA | Техническая администрация Воркерланда | Дориан Воркс | 52 118 124 | WRK_technocracy |
| EYR | Эйрмийская окружная администрация | Ирина Коваль | 132 136 140 | VAD |
| EGC | Эйрмийское гарнизонное командование | Руслан Пайк | 55 62 70 | VAD |
| WPA | Администрация Западного периметра | Самира Кетт | 78 111 146 | ZAO |
| WPS | Управление снабжения Западного периметра | Карим Дол | 38 63 91 | ZAO |
| PSD | Дирекция Пепельного сектора | Марта Синдер | 112 97 122 | PWR |
| EBA | Администрация Восточного плацдарма | Вера Кранц | 126 92 54 | VLA |
| DVA | Долинская администрация | Карл Розен | 151 100 126 | ROM |
| SRA | Администрация Солнечной равнины | Гелио Марр | 184 137 34 | SOL |
| ZTA | Златореченская временная администрация | Виктор Холт | 150 55 58 | TRU |
| SLA | Администрация Старолесья | Старолесская окружная управа | 52 101 58 | PWR |
| RZA | Реакторная администрация | Реакторная техническая дирекция | 112 119 55 | PWR |
| MLR | Республика Малой низины | Низинная временная рада | 134 112 75 | PWR |
| ERT | Восточная восстановительная территория | Восточное восстановительное управление | 91 103 128 | PWR |
| IRT | Внутренняя восстановительная территория | Внутренний республиканский совет | 62 85 80 | PWR |
| SCA | Администрация Южного коридора | Управление Южного коридора | 118 97 82 | PWR |

- [ ] **Step 1: Add failing database tests**

Assert all tags have country/history files, `TAG/TAG_DEF/TAG_ADJ`, party
keys, a character, three flag sizes, and an OOB whose unit locations match
`CAPITALS`.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.CountryRosterTests -v`

Expected: FAIL on missing tag `TVA`.

- [ ] **Step 3: Create fixed tag database**

Every country definition uses:

```hoi4
graphical_culture = western_european_gfx
graphical_culture_2d = western_european_2d
color = rgb { R G B }
```

Every dormant history file sets the future capital, politics and character,
but contains no `oob =`, owner transfer, core, or faction membership.

Every OOB uses a two-battalion `ADISCORD_militia` template. Regional
splinters receive two divisions with experience `0.10` and equipment
`0.25`; dirty-zone tags receive one division with equipment `0.22`.

Dorian uses `GFX_portrait_WRK_Dorian_Worx`. Anton Bagley binds his existing
PNG. Every other new portrait key points to
`gfx/leaders/portrait_PLACEHOLDER.png`.

Copy all three flag sizes from the exact source column.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.CountryRosterTests -v`

Expected: PASS.

Run: `python tools/validate_adiscord_vorkerland_collapse.py --section countries`

Expected: PASS.

- [ ] **Step 5: Commit**

`feat: add vorkerland collapse country roster`

---

### Task 4: Dirty-State Bootstrap and Permanent Modifier

**Files:**
- Create: `common/dynamic_modifiers/ADISCORD_vorkerland_collapse_dynamic_modifiers.txt`
- Create: `common/scripted_effects/ADISCORD_vorkerland_collapse_dirty_effects.txt`
- Modify: the 32 ownerless dirty state files in `DIRTY_GROUPS`
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_states_l_russian.yml`
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Produces: `ADISCORD_vorkerland_apply_dirty_modifiers` and playable ownerless states.
- Modifier remains state-scoped across every owner transfer.

- [ ] **Step 1: Add failing dirty-state tests**

Assert all 37 states are enumerated once, modifier has no
`remove_trigger`, no file calls `remove_dynamic_modifier` for its key, all
32 spawn states have category/manpower/local supplies, and the six capitals
have VP/buildings.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.DirtyStateTests -v`

Expected: FAIL because the modifier is absent.

- [ ] **Step 3: Add the modifier**

```hoi4
ADISCORD_vorkerland_dirty_state = {
    enable = { always = yes }
    icon = GFX_modifiers_sabotaged_resource
    local_manpower = -0.75
    state_resources_factor = -0.60
    local_building_slots_factor = -0.40
    state_production_speed_buildings_factor = -0.50
    local_supply_impact_factor = 0.35
}
```

The apply effect enumerates exactly `CONTAMINATED_STATES`, checks
`has_dynamic_modifier`, and never removes it.

For states 165–193 without category/history use `rural`,
`local_supplies = 0.25`, and manpower `1500 × province count`. Preserve
existing non-zero manpower in states 152–160. Keep state 125 impassable.

Capital bootstrap:

| Tag | State/Province | VP | Buildings |
|---|---|---:|---|
| SLA | 49/16639 | 3 | infrastructure 1, industrial_complex 1 |
| RZA | 177/2952 | 3 | infrastructure 1, arms_factory 1 |
| MLR | 152/9806 | 3 | infrastructure 1, industrial_complex 1 |
| ERT | 169/10693 | 3 | infrastructure 1, arms_factory 1 |
| IRT | 181/2226 | 3 | infrastructure 1, industrial_complex 1 |
| SCA | 173/6015 | 3 | infrastructure 1, arms_factory 1 |

State 49 additionally becomes `town`, manpower `20000`, and
`local_supplies = 0.5`. Other new capital states use at least manpower
`18000`, category `town`, and `local_supplies = 0.5`.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.DirtyStateTests -v`

Expected: PASS.

Run: `python tools/validate_adiscord_vorkerland_collapse.py --section dirty`

Expected: PASS and exact 37-state match from `definition.csv`.

- [ ] **Step 5: Commit**

`feat: bootstrap contaminated territories`

---

### Task 5: Collapse Scheduler, Tower Explosion, and Initial Wars

**Files:**
- Create: `events/ADISCORD_vorkerland_collapse_events.txt`
- Create: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Create: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Create: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Modify: `events/ADISCORD_news.txt`
- Modify: `localisation/russian/ADISORD_news_l_russian.yml`
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Produces namespace `ADISCORD_vorkerland_collapse`, events `.1/.2`, flags
  `ADISCORD_vorkerland_collapse_scheduled`, `_started`, `_wars_started`.
- Consumes all fixed tags, capitals and OOB names.

Initial state map:

```text
WRK: 27 32 33 34 35 40 79 82 105
TVA: 36 37 38 39
VAD: 75 106 107 121 123
EYR: 102 108 109 111 122
EGC: 81 104 110 124
ZAO: 72
WPA: 195
WPS: 196
PWR: 71 90 91
PSD: 194 93 94
VLA: 74
EBA: 197
ROM: 73
DVA: 144 145
SOL: 76
SRA: 198
TRU: 80
ZTA: 199
```

- [ ] **Step 1: Add failing orchestration tests**

Assert: `news.0` is presentation-only and one-shot; nuke/damage occur once
in event `.1`; teardown frees `NAM DAN VAD ZAO PWR VLA ROM SOL TRU`; setup
precedes `load_oob`; wars occur only in delayed `.2`; TGD spawns in physical state 105 between VLA and EBA.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.EventOrchestrationTests -v`

Expected: FAIL because namespace/events do not exist.

- [ ] **Step 3: Implement scheduler and collapse**

`on_startup` sets the scheduled global flag once and applies dirty
modifiers. `on_monthly` begins the collapse with a monthly chance after 120
days and forces it after 180 days.

Event `.1`:

1. sets one-shot guard;
2. launches the nuke at `6713` and damages state 32 once;
3. resolves Worker fate with weights `60/30/10`;
4. ends subject status, then dismantles the faction;
5. deletes/distributes obsolete starting divisions;
6. performs the exact state setup map;
7. assigns capitals/cores/controllers and loads OOB;
8. schedules `.2` for one day later;
9. fires presentation-only `news.0` for human countries.

Event `.2` declares local wars:

```text
WRK↔TVA, WRK↔VAD, TVA↔VAD
VAD↔EYR, VAD↔EGC, EYR↔EGC
ZAO↔WPA, WPA↔WPS, WPS↔ZAO
PWR↔PSD, VLA↔EBA, ROM↔DVA, SOL↔SRA, TRU↔ZTA
```

Every edge checks both tags exist and are not already at war.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.EventOrchestrationTests -v`

Expected: PASS.

Run: `python tools/validate_adiscord_vorkerland_collapse.py --section events`

Expected: PASS.

- [ ] **Step 5: Commit**

`feat: launch vorkerland cascade wars`

---

### Task 6: Phase-Based Civil-War AI

**Files:**
- Create: `common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt`
- Extend: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Extend: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Extend: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Produces mutually exclusive country flags `_phase_consolidate`,
  `_phase_regional`, `_phase_endgame`, `_phase_finished`.
- Uses `abort_when_not_enabled = yes` for every strategy block.

- [ ] **Step 1: Add failing AI coverage tests**

Assert every active tag has consolidate/regional/endgame coverage, every
block aborts when disabled, non-active neighbors are ignored, state
objectives exist, and monthly code does not nest `every_country`.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.AIStrategyTests -v`

Expected: FAIL because the AI strategy file is absent.

- [ ] **Step 3: Implement phases**

- Days 0–60: `put_unit_buffers` around each capital and defensive
  `front_control`.
- Days 61–540: `consider_weak`, `conquer`, `prepare_for_war` and
  target-specific `front_control` only against neighbors/current enemies.
- After day 540: rush state objectives `32,36,39,75,102,195,196,71,194`.
- VAD gets stronger front ratio and production; TVA gets industrial
  priority; WRK gets defensive buffers; minors use militia production.
- Dirty-zone tags ignore the central war for their first 90 days and defend
  their capitals.

The monthly effect clears all old phase flags before setting exactly one.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.AIStrategyTests -v`

Expected: PASS.

Run: `python tools/validate_adiscord_vorkerland_collapse.py --section ai`

Expected: PASS.

- [ ] **Step 5: Commit**

`feat: add adaptive vorkerland war ai`

---

### Task 7: Dirty-Zone Opening, Spawn Waves, and Intervention

**Files:**
- Extend: `events/ADISCORD_vorkerland_collapse_events.txt`
- Extend: `common/scripted_effects/ADISCORD_vorkerland_collapse_dirty_effects.txt`
- Extend: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Extend: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Extend: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Produces events `.10/.11/.12/.13` and global flags `_dirty_opened`,
  `_dirty_wave_1`, `_dirty_wave_2`, `_dirty_wave_3`.

- [ ] **Step 1: Add failing spawn-wave tests**

Assert 60–90-day opening window, corrected connected state groups, no state
23 transfer, no modifier removal, setup-before-OOB, and one spawn per tag.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.DirtySpawnTests -v`

Expected: FAIL because dirty events are absent.

- [ ] **Step 3: Implement three waves**

- Opening after 60–90 days from collapse.
- Wave 1 immediately: `SLA`, `MLR`.
- Wave 2 after 45 days: `RZA`, `SCA`.
- Wave 3 after another 45 days: `ERT`, `IRT`.

Each setup transfers exactly `DIRTY_GROUPS[tag]`, adds cores/controllers,
sets `CAPITALS[tag]`, initializes economy/technology if the shared effects
exist, and loads one militia OOB. It never removes the dirty modifier.

External involvement is limited:

- RUS supplies and guarantees SLA after wave 1;
- VAL and CIN supply ERT/IRT after wave 3;
- EFL supplies and guarantees SCA after wave 2;
- no intervener receives annexation goals over the whole confederation.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.DirtySpawnTests -v`

Expected: PASS.

- [ ] **Step 5: Commit**

`feat: open and settle the dirty zone`

---

### Task 8: Winner Detection, Final Maps, and Superevents

**Files:**
- Create: `common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt`
- Extend: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Extend: `events/ADISCORD_vorkerland_collapse_events.txt`
- Modify: `interface/superevents.gfx`
- Modify: `common/scripted_guis/superevents.txt`
- Modify: `common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt`
- Modify: `localisation/russian/ADISCORD_superevents_l_russian.yml`
- Extend: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Produces `ADISCORD_vorkerland_apply_worker_map`,
  `_apply_vlad_map`, `_apply_dorian_map`.
- Produces super-event flags for dirty opening and three claimant outcomes.

- [ ] **Step 1: Add failing outcome tests**

Assert winner predicates are mutually exclusive, require state 32 for 90
days, do not trigger on first regional capitulation, each final map assigns
every civil-war state once, and all super-event flags have GUI/GFX/loc.

- [ ] **Step 2: Run RED**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.OutcomeTests -v`

Expected: FAIL because final-map effects are absent.

- [ ] **Step 3: Implement winner confirmation**

- Worker candidate: WRK controls 32 and main metropolitan states; TVA/VAD
  cannot contest the capital.
- Vlad candidate: VAD controls 32, 75 and 81; WRK/TVA cannot contest.
- Dorian candidate: TVA controls 32, 36, 37, 38 and 39; WRK/VAD cannot
  contest.
- Candidate must remain valid for 90 days.
- Elapsed time alone never chooses a winner or applies a fallback map.

Final maps:

- Worker: WRK directly receives all original WRK states; the factual
  surviving government in each regional pair receives its home region and
  becomes a broad WRK autonomy; dirty countries remain independent.
- Vlad: VAD directly receives all WRK/VAD states; regional survivors become
  military dependencies; SLA becomes a western protectorate.
- Dorian: TVA directly receives all WRK states; `EYR/WPA/PSD/EBA/DVA/SRA/ZTA`
  administer their regions as technical dependencies; RZA becomes TVA's
  associated administration.

Use the existing Dorian victory image. Other new sprite keys may point to
the existing civil-war image; no duplicate binary is needed.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest tools.test_validate_adiscord_vorkerland_collapse.OutcomeTests -v`

Expected: PASS.

Run: `python tools/validate_adiscord_vorkerland_collapse.py`

Expected: PASS.

- [ ] **Step 5: Commit**

`feat: add vorkerland victory maps and superevents`

---

### Task 9: Full Static and Runtime Verification

**Files:**
- Modify only files implicated by observed failures.
- Create: `docs/testing/ADISCORD_vorkerland_collapse_observer_checklist.md`

**Interfaces:**
- Consumes all prior tasks.
- Produces reproducible validation evidence and an observer checklist.

- [ ] **Step 1: Run focused unit/feature gates**

```powershell
python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v
python tools/validate_adiscord_vorkerland_collapse.py
python tools/validate_tc.py --limit 80
```

Expected: focused tests and validator PASS; `validate_tc.py` introduces no
new errors attributable to this feature.

- [ ] **Step 2: Run textual safety checks**

Verify:

- balanced braces in every touched `.txt/.gfx`;
- zero trailing whitespace;
- Russian YAML files have UTF-8 BOM;
- no `start_civil_war`;
- no `remove_dynamic_modifier` for the dirty key;
- no new tag owns a state at campaign start;
- no staged unrelated dirty file.

- [ ] **Step 3: Perform observer run**

Start a new campaign in debug/observer mode and run at least two game years.
Check:

1. one Tower explosion at province 6713;
2. three central claimants and all regional splits appear;
3. OOBs spawn inside owned capitals;
4. local wars start after the one-day settle window;
5. dirty opening occurs 60–90 days later;
6. six dirty countries spawn in three waves;
7. modifier remains on every transferred dirty state;
8. AI changes phase and does not open global wars;
9. one forced debug run for each final map;
10. fresh `error.log` has no new invalid tag/state/character/OOB/loc errors.

- [ ] **Step 4: Fix only evidence-backed regressions and rerun**

For every fix, add a regression assertion to the focused validator before
changing production content, observe RED, then GREEN.

- [ ] **Step 5: Commit**

`test: verify vorkerland collapse campaign`
