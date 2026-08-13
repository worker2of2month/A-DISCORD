# Task 5: Collapse Scheduler, Tower Explosion, and Initial Wars

Plan: `docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`

Read Shared Manifest and complete Task 5 before editing.

## Scope

Create:

- `events/ADISCORD_vorkerland_collapse_events.txt`
- `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`

Modify:

- `events/ADISCORD_news.txt`
- `localisation/russian/ADISORD_news_l_russian.yml`
- `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- `tools/test_validate_adiscord_vorkerland_collapse.py`

Do not modify dirty `00_ADISCORD_on_actions.txt` or any AI/default file.
Work on main by explicit permission. Commit only scoped files:

`feat: launch vorkerland cascade wars`

## Runtime references already verified from local vanilla

- `set_capital = { state = 539 }`
- `load_oob = "name"`
- overlord scope: `end_puppet = SUBJECT`
- `country_event = { id = X days = 120 random_days = 60 }`
- `declare_war_on = { target = TAG type = annex_everything }`
- country scope after transfer: `set_state_controller = STATE_ID`
  or state scope: `set_state_controller_to = TAG`
- direct numeric state scopes such as `32 = { ... }`

Use these full/block forms. Do not invent shorthand.

## TDD workflow

Add `EventOrchestrationTests`, then run RED. Tests must verify:

1. new namespace and hidden one-shot events `.1`/`.2`;
2. startup applies dirty modifiers and schedules `.1` at
   `days = 120`, `random_days = 60`, behind a global one-shot guard;
3. `news.0` is presentation-only, `fire_only_once = yes`, and contains no
   `every_country`, `launch_nuke`, `damage_building`, or state transfer;
4. `.1` contains exactly one nuke at province 16428 and damage in state 32;
5. teardown frees `NAM DAN VAD ZAO PWR VLA ROM SOL TRU` before faction
   dismantling;
6. every new tag receives exact states, cores/controller, capital and OOB,
   with transfer/setup text occurring before `load_oob`;
7. `.2` alone contains all exact war edges and is scheduled one day after
   `.1`;
8. no `start_civil_war`;
9. states 32 and 40 remain together under WRK in the initial map.

After implementation run focused test, `--section events`,
`validate_tc --limit 80`, braces/BOM/diff checks.

## Scheduler

`on_startup` is global. Behind
`ADISCORD_vorkerland_collapse_scheduled`:

1. set the global guard;
2. call `ADISCORD_vorkerland_apply_dirty_modifiers = yes`;
3. if WRK exists, schedule WRK event `.1` with
   `days = 120 random_days = 60`.

Event `.1` also checks/sets
`ADISCORD_vorkerland_collapse_started`, so duplicate delayed events or old
saves cannot apply the collapse twice.

## Event `.1`

Hidden, triggered-only, one-shot, WRK-only:

1. set global started guard;
2. `goto_province = 16428`;
3. launch one nuke at province 16428 with `use_nuke = no`;
4. damage infrastructure, railway and anti-air once in direct state 32 scope;
5. random Worker fate:
   - 60: `ADISCORD_vorkerland_worker_rescued_by_vlad`
   - 30: `ADISCORD_vorkerland_worker_missing`
   - 10: `ADISCORD_vorkerland_worker_killed`
6. free all nine subjects, then dismantle WRK faction;
7. apply the exact state map below;
8. initialize each new tag with technology baseline/economy, then load OOB;
9. set `_wars_started` only in `.2`, not here;
10. schedule `.2` with `days = 1`;
11. fire presentation-only `news.0` after one hour.

Do not delete existing parent-tag OOBs. They become the loyalist/local
government forces. New split tags receive only their Task 3 OOBs.

## Exact setup map

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

For new tags, order:

1. target country `transfer_state` for all states;
2. each numeric state scope `add_core_of = TAG` and
   `set_state_controller_to = TAG`;
3. `set_capital = { state = CAPITAL }`;
4. technology/economy initializer;
5. `load_oob = "TAG_vorkerland_collapse"`.

Existing parent tags keep their retained states and existing cores. Add no
dirty-zone countries yet.

## Event `.2` wars

Behind `_wars_started`, and for every edge check target exists and attacker
is not already at war with it:

```text
WRK -> TVA
WRK -> VAD
TVA -> VAD
VAD -> EYR
VAD -> EGC
EYR -> EGC
ZAO -> WPA
WPA -> WPS
WPS -> ZAO
PWR -> PSD
VLA -> EBA
ROM -> DVA
SOL -> SRA
TRU -> ZTA
```

Use ordinary `declare_war_on` with `annex_everything`. No civil-war dynamic
tags or peace conference bypass.

## Presentation/localisation

Rewrite `news.0` description in sober Russian:

- title: `Взрыв в Башне Единства`
- description: the central complex is destroyed, contact with the
  confederation leadership is lost, district administrations declare
  emergency rule, and the common command system is breaking down;
- option: `Конфедерация распадается.`

Keep the existing superevent flag/sound/song option behavior for human
countries. Russian YAML remains UTF-8 BOM.

Add hidden-event debug localisation/flags descriptions only if required by
the engine; do not expose player choices.

Write report to `.superpowers/sdd/task-5-implementer-report.md` and keep it
untracked.
