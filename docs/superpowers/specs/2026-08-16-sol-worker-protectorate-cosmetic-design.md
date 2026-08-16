# SOL Worker Protectorate Cosmetic Design

## Goal

Use `SOL_vorkerland_worker_protectorate` while SOL is the starting WRK autonomy or a subject of the worker claimant WKR/WRK, and restore base SOL presentation when it becomes independent.

## Design

- Seed `SOL_vorkerland_worker_protectorate` in SOL country history so it is visible from a fresh campaign's first frame.
- Preserve the authored worker-protectorate flag triplet as a deterministic runtime-master asset instead of aliasing the base SOL flag.
- Extend the existing event-driven independence cosmetic synchronizer to cover SOL.
- Keep the protectorate cosmetic only for `is_subject_of = WKR` or `is_subject_of = WRK`.
- Use `drop_cosmetic_tag = yes` for independent SOL and for subjects of other overlords, preserving VAD's distinct loyalist outcome.
- Invoke the synchronizer from the existing collapse cosmetic pass and the existing `on_puppet`, `on_release_as_puppet`, and `on_release_as_free` hooks. Do not add monthly polling or save migrations.

## Verification

- A focused regression test covers fresh-start history, WKR/WRK subject branches, independence fallback, VAD exclusion, event hooks, and the absence of monthly polling.
- Run the focused Vorkerland collapse and diplomacy tests and validators.
- Run `python -B tools/validate_tc.py --limit 300` and both unstaged and cached `git diff --check`.
- Runtime acceptance requires a fully restarted game and fresh campaign; static validation alone is not runtime proof.
