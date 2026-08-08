# Recovery starting tree audit — 2026-08-08

## Snapshot

- Branch: `main`
- HEAD: `078de95edc8710258c8ed4cd38165613839860b0`
- HEAD subject: `docs: close A-Discord recovery plan gaps`
- Index: no staged paths at capture.
- Dirty worktree before this repository-tooling task: 370 paths — 284
  modified, 10 deleted, and 76 untracked. This is protected user work and is
  outside the Task 1 commit.
- No active `git`, `python`, or `hoi4` process was observed at capture.

## Protected work and generated ownership

The existing dirty tree includes civil-war gameplay, country/OOB, state/map,
strategic-region, sound, localisation, and validator work. None of those paths
belongs to this task.

Generated output remains owned by its builders:

- `tools/build_adiscord_outer_states.py` owns outer state files.
- `tools/build_adiscord_remainder_states.py` owns remainder state files.
- `tools/build_adiscord_new_states.py` owns its generated states and related
  state/victory-point localisation.
- `tools/build_adiscord_map_buildings.py` owns `map/buildings.txt`.
- `tools/build_adiscord_strategic_regions.py` owns marked strategic regions.
- `tools/build_adiscord_technology_system.py` owns marked technology output.

## Baseline checks

The recovery execution ledger records a 333-test tooling baseline before this
task. Task 1 adds one repository-contract test, so the corresponding discovery
run contains 334 tests while its RED condition exists.

- `python -B -m unittest discover -s tools -p 'test_*.py'` after adding the
  RED test: 334 tests, one expected failure from the 40 tracked
  `tools/__pycache__/*.pyc` files.
- `python -B tools/validate_tc.py --limit 300`: passed all reported sections
  (brace balance, countries, maps/states, map buildings, snow, localisation,
  GFX/entity, economy/AI, NCNS, and vanilla leftovers).

## Verified transient artifacts

- `tools/__pycache__/*.pyc`: 40 tracked files; these are Python bytecode
  caches and are the deliberate RED-test trigger.
- `console_history.txt`: untracked, 111 bytes, and contains only local
  Clausewitz console commands (`fow`, `spectator`, `observe`, and `annex`), not
  source data. It is safe to remove.

The Task 1 cleanup removes only these 40 tracked cache files and the verified
untracked console history. Source text, JSON, YAML, maps, audio, and image
assets are deliberately not ignored by the new repository rules.
