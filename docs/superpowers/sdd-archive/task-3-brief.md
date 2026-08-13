# Task 3: Fixed Country Roster, Characters, Flags, and OOBs

Plan: `docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`

Read the complete Shared Manifest and Task 3 before editing.

## Scope

Create:

- `common/country_tags/01_ADISCORD_vorkerland_collapse_tags.txt`
- `common/countries/{TVA,EYR,EGC,WPA,WPS,PSD,EBA,DVA,SRA,ZTA,SLA,RZA,MLR,ERT,IRT,SCA}.txt`
- one `history/countries/<TAG> - <English slug>.txt` per tag
- `history/units/<TAG>_vorkerland_collapse.txt` per tag
- `common/characters/ADISCORD_vorkerland_collapse_characters.txt`
- `interface/ADISCORD_vorkerland_collapse_portraits.gfx`
- large/medium/small `.tga` flags for every tag
- `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`

Modify only:

- `tools/test_validate_adiscord_vorkerland_collapse.py`

Do not modify existing dirty files or existing leader/flag databases. Copy
binary flags with `Copy-Item`; all text edits use `apply_patch`. Work on main
by explicit user permission. Commit only scoped files:

`feat: add vorkerland collapse country roster`

## TDD workflow

1. Add `CountryRosterTests` checking every fixed tag has a tag entry, country
   definition, dormant country history, localisation, character, three flag
   sizes, and a loadable OOB whose locations match `CAPITALS`.
2. Run the named class and record RED.
3. Create the full fixed-tag database and assets.
4. Run GREEN.
5. Run:
   `python tools/validate_adiscord_vorkerland_collapse.py --section countries`
6. Run:
   `python tools/validate_tc.py --limit 80`
7. Check only scoped files, then commit.

## Roster

| Tag | Russian name | Leader | RGB | Flag source |
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
| ZTA | Златореченская временная администрация | Вера Холт | 150 55 58 | TRU |
| SLA | Администрация Старолесья | Старолесская окружная управа | 52 101 58 | PWR |
| RZA | Реакторная администрация | Реакторная техническая дирекция | 112 119 55 | PWR |
| MLR | Республика Малой низины | Низинная временная рада | 134 112 75 | PWR |
| ERT | Восточная восстановительная территория | Восточное восстановительное управление | 91 103 128 | PWR |
| IRT | Внутренняя восстановительная территория | Внутренний республиканский совет | 62 85 80 | PWR |
| SCA | Администрация Южного коридора | Управление Южного коридора | 118 97 82 | PWR |

## Content rules

- Tag entries reference exactly `countries/<TAG>.txt`.
- Every country definition:
  `western_european_gfx`, `western_european_2d`, and exact RGB.
- Dormant histories set future capital, politics, popularities, leader and
  research slots, but contain no `oob =`, owner transfer, core, faction, or
  subject setup.
- Use one unique character key per tag. Dorian uses
  `GFX_portrait_WRK_Dorian_Worx`; all other new keys use
  `GFX_portrait_PLACEHOLDER`.
- Use sober administrative leader descriptions; council/board leaders are
  intentionally collective characters.
- Regional OOBs (TVA through ZTA) have two divisions; dirty-zone OOBs
  (SLA through SCA) have one. All use a two-battalion
  `ADISCORD_militia` template, experience `0.10`, equipment `0.25` regional
  and `0.22` dirty.
- Every division location equals that tag's capital province in `CAPITALS`.
- Do not load OOBs from country history.
- Copy the source flag trio exactly for all three sizes. Verify that each
  source exists before copying.
- Localise `TAG`, `TAG_DEF`, `TAG_ADJ`, all party keys required by the
  ideologies used, every leader key and description.
- Russian YAML must be UTF-8 BOM.

Write the report to `.superpowers/sdd/task-3-implementer-report.md`, including
RED/GREEN evidence, validator output, copied flag sources, commit, and concerns.
