# Task 2: Split the Five Regional State Bases

Plan: `docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`

Read the complete Task 2 section and Shared Manifest before editing.

## Scope

Modify only:

- `history/states/71-71.txt`
- `history/states/72-72.txt`
- `history/states/74-74.txt`
- `history/states/76-76.txt`
- `history/states/80-80.txt`
- `tools/test_validate_adiscord_vorkerland_collapse.py`

Create only:

- `history/states/194-PWR-EAST.txt`
- `history/states/195-ZAO-WEST.txt`
- `history/states/196-ZAO-CENTER.txt`
- `history/states/197-VLA-EAST.txt`
- `history/states/198-SOL-WEST.txt`
- `history/states/199-TRU-WEST.txt`
- `localisation/russian/ADISCORD_vorkerland_collapse_states_l_russian.yml`

Do not modify unrelated dirty files. Work on current `main` by explicit user
permission. Commit only files in scope with:

`feat: split vorkerland regional states`

## TDD workflow

1. Extend the focused test with `StatePartitionTests`.
2. Assert exact one-to-one conservation of every original province using
   `STATE_PARTITIONS`, existence of state IDs 194–199, and inclusion of the
   six capital provinces in their new states.
3. Run the named test and record RED because states 194–199 are absent.
4. Apply the exact province partitions from the manifest, with no omissions,
   duplication, or province reordering outside those lists.
5. Run the named test and record GREEN.
6. Run `python tools/validate_adiscord_vorkerland_collapse.py --section states`.
7. Run `python tools/validate_tc.py --limit 80`; compare findings to baseline
   and report any unrelated pre-existing noise.
8. Commit only scoped files.

## Exact content rules

- Populations:
  - state 71 and 194: 42500 each
  - state 72: 43334; states 195 and 196: 43333 each
  - state 74 and 197: 70000 each
  - state 76 and 198: 75000 each
  - state 80 and 199: 115000 each
- Keep existing VP/buildings in the retained states.
- Every new state uses the same original owner and core as its source state.
- Every new state gets `state_category = rural`,
  `buildings_max_level_factor = 1`, `local_supplies = 0`,
  and `infrastructure = 1`.
- New VPs:
  - 194/2339 = 3
  - 195/8032 = 3
  - 196/7129 = 3
  - 197/10016 = 3
  - 198/9104 = 3
  - 199/12930 = 3
- Transfer the state-71 arms factory to 194.
- Transfer the state-76 civilian factory to 198.
- Transfer the state-80 arms factory to 199; retain its civilian factory in
  state 80.
- Do not add factories to 195, 196, or 197.
- Use the exact state and VP localisation written in Task 2.
- Russian localisation must be UTF-8 with BOM.

Write the report to `.superpowers/sdd/task-2-implementer-report.md`, including
RED/GREEN evidence, validator output, commit hash, and any concerns.
