# Review Task 1: Validator and Manifest

Review range: `3191c8b76ef772db3c0d542e1efeed3e94227949..7cc0205b24cba0fdd1886c627c16702848612f23`

## Verdict: CHANGES REQUIRED

The three committed files and the full Git diff were inspected directly. The
manifest data matches the Task 1 shared manifest, the requested API and all
eight section names are present, and the countries gate fails as required
while the feature is not yet implemented. Two validator defects must be
fixed before this gate can be trusted for subsequent tasks.

## Pass 1: Spec compliance

- `TAGS`, `CONTAMINATED_STATES`, `DIRTY_GROUPS`, `CAPITALS`, and
  `STATE_PARTITIONS` in `tools/vorkerland_collapse_manifest.py` match the
  shared-manifest values.
- `validate(root: Path) -> list[str]`, CLI `--section`, and sections
  `manifest`, `states`, `countries`, `dirty`, `events`, `ai`, `outcomes`,
  and `superevents` are present in
  `tools/validate_adiscord_vorkerland_collapse.py:28-29, 194-224`.
- The implementation only reads repository data (`read_text`, `glob`, and
  `rglob`); no production-file write operation was found.
- Future-content gate behavior was verified: `--section countries` exits 1
  and lists the missing fixed-tag registry and country artifacts.

## Pass 2: Code quality findings

### Important — duplicate dirty-state assignment is silently accepted

`tools/validate_adiscord_vorkerland_collapse.py:60-68`

`set().union(...)` discards duplicate state IDs, but line 64 reports that
the groups are covered “exactly once.” A duplicate state placed in two dirty
groups therefore passes validation. The accompanying unit test repeats the
same set-union-only assertion at
`tools/test_validate_adiscord_vorkerland_collapse.py:15-18`.

Reproduced in memory by appending state `49` to `RZA` while retaining the
otherwise valid manifest: `validate_manifest()` returned `[]`. During the
spawn-wave tasks, this can allow one contaminated state to be assigned to
two countries. Count each transferable state across the group tuples and add
a regression test which fails on a cross-group duplicate.

### Important — state province parser treats comments as province IDs

`tools/validate_adiscord_vorkerland_collapse.py:43-45`

`provinces()` extracts every digit from the raw block and does not remove
Clausewitz `#` comments. The normal formatted input
`provinces = { 1 # 999\n 2 }` produces `{1, 2, 999}`. A comment containing a
number therefore creates a false partition mismatch; a commented-out
`provinces` block before the real one can also be selected by `re.search`.
Strip comments before locating and tokenising the provinces block (or use a
small Clausewitz-aware scanner) and add tests for both comment positions.

## Verification evidence

- `python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v`:
  passed, 1 test.
- `python tools/validate_adiscord_vorkerland_collapse.py --section manifest`:
  passed, exit 0.
- `python tools/validate_adiscord_vorkerland_collapse.py --section countries`:
  failed as expected for missing future country content, exit 1.
- `git diff --check 3191c8b76ef772db3c0d542e1efeed3e94227949..7cc0205b24cba0fdd1886c627c16702848612f23`:
  no whitespace errors.
