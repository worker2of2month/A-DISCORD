# A-Discord Repository, Tooling, and ASCII Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository understandable and safely verifiable, preserve existing command entry points, and replace Cyrillic technical division-template names at their sources without altering player-facing translations.

**Architecture:** Python tooling becomes importable packages under responsibility-based directories while root scripts temporarily remain thin facades. A generated-output registry defines ownership and check/apply commands. Technical-name migration starts from generator constants/manifests and is propagated atomically to generated OOB and scripted creation references.

**Tech Stack:** Python 3 packages and `unittest`, HOI4 text assets, Git rename detection, UTF-8/UTF-8-BOM localisation.

## Global Constraints

- Preserve the dirty main working tree; this plan reorganizes only verified tooling and technical-name paths.
- Use `git mv` for tracked moves only after confirming no active process owns the path. Do not move user-owned untracked files into the plan implicitly.
- Root compatibility scripts must keep the same arguments and exit codes until the final recovery release.
- Never move or merge HOI4 engine-loaded state history, map, strategic-region, technology-output, or OOB files merely to reduce file count.
- Every mutating builder must expose an idempotent `--check` and explicit `--apply` path.
- Technical names are ASCII/English. Russian displayed names remain localisation values, not `division_template` identifiers.
- Russian localisation files remain UTF-8 with BOM.

---

## Task 1: Add Repository Documentation and Transient-Artifact Contracts

**Files:**
- Create: `.gitignore`
- Create: `AGENTS.md`
- Create: `tools/README.md`
- Create: `tools/tests/test_repository_contracts.py`
- Delete: tracked `tools/__pycache__/*.pyc`
- Delete: `console_history.txt` after verifying it is transient and contains no source data

- [ ] Write a failing test that rejects tracked `__pycache__`, `.pyc`, `console_history.txt`, editor backups, and root-level reference binaries that are not registered assets.
- [ ] Run `python -B -m unittest tools.tests.test_repository_contracts.RepositoryHygieneTests -v` and confirm RED against the present tracked cache files.
- [ ] Add `.gitignore` entries for `__pycache__/`, `*.py[cod]`, `console_history.txt`, Clausewitz logs/dumps, editor backups, and local test caches; do not ignore source `.txt`, `.json`, `.yml`, map, audio, or image assets generically.
- [ ] Write `AGENTS.md` with generated-file ownership rules, BOM rules, required static gates, full-restart requirements, and dirty-worktree protection.
- [ ] Write `tools/README.md` with check/apply conventions and the single full static command.
- [ ] Remove only verified transient tracked artifacts, rerun the focused test, and confirm GREEN.
- [ ] Run `git diff --check` and stage only the four documentation/config paths plus verified transient deletions.
- [ ] Commit as `chore: document repository and ignore transient artifacts`.

## Task 2: Create the Tool Package Skeleton and Compatibility Test

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/builders/__init__.py`
- Create: `tools/validators/__init__.py`
- Create: `tools/tests/__init__.py`
- Create: `tools/lib/__init__.py`
- Create: `tools/tests/test_tool_entrypoints.py`
- Update: `tools/validate_tc.py`

- [ ] Write a failing test that imports `tools.builders`, `tools.validators`, `tools.tests`, and `tools.lib`, and invokes representative old root CLIs with `--help` or check mode.
- [ ] Run `python -B -m unittest tools.tests.test_tool_entrypoints -v` and confirm RED because the packages do not yet exist.
- [ ] Add package markers and a shared `tools/lib/paths.py` only if required to keep root detection identical across moved modules.
- [ ] Change `validate_tc.py` imports to package-qualified imports with one documented compatibility fallback for direct execution.
- [ ] Rerun the focused test and `python -B tools/validate_tc.py --limit 300`.
- [ ] Commit as `refactor: establish importable tool packages`.

## Task 3: Move Builders Behind Stable Root Facades

**Files:**
- Move into `tools/builders/`: all fourteen current `tools/build_adiscord_*.py` files
- Create at old paths after each move: matching thin `tools/build_adiscord_*.py` facades
- Update: imports in `tools/validate_tc.py`, validators, and tests
- Test: `tools/tests/test_tool_entrypoints.py`

- [ ] Extend the entrypoint test to compare `--help`, exit code, and check-mode behavior between each root facade and its package module.
- [ ] Run the new test and confirm RED for missing package modules.
- [ ] Move one builder family at a time, starting with non-generated flag tooling and ending with state/map/technology builders.
- [ ] Make each root facade import `main` from `tools.builders.<name>` and call it under `if __name__ == '__main__'` without duplicating implementation.
- [ ] Replace sibling absolute imports with `tools.*` package imports; retain direct-script fallback only inside facades.
- [ ] After each family, run its focused tests and its check mode. Do not run `--apply` unless the task intentionally changes owned output.
- [ ] Run all builder tests, `python -B -m unittest tools.tests.test_tool_entrypoints -v`, and `python -B tools/validate_tc.py --limit 300`.
- [ ] Commit as `refactor: organize A-Discord builders`.

## Task 4: Move Validators, Tests, Libraries, and Manifests

**Files:**
- Move into `tools/validators/`: all `tools/validate_adiscord_*.py` plus the implementation of `validate_tc.py`
- Move into `tools/tests/`: all `tools/test_*.py`
- Move into `tools/lib/`: `adiscord_core_state_balance_manifest.py`, `adiscord_technology_applied_programmes.py`, `adiscord_technology_expansions_civil.py`, `adiscord_technology_expansions_combat.py`, `vorkerland_collapse_manifest.py`
- Preserve at old paths: validator and `validate_tc.py` compatibility facades
- Update: every internal import and documented command
- Test: `tools/tests/test_tool_entrypoints.py`

- [ ] Extend the failing compatibility test to discover tests from `tools/tests`, import all five library modules, and compare all validator root facades with package modules.
- [ ] Move libraries first and update consumers, then validators, then tests.
- [ ] Ensure `python -B -m unittest discover -s tools/tests -p "test_*.py"` is the canonical discovery command.
- [ ] Keep `python -B tools/validate_tc.py --limit 300` working through the root facade.
- [ ] Run both canonical and compatibility commands and require identical pass/fail semantics.
- [ ] Commit manifests/libraries separately from the large mechanical test move if staged review exceeds a practical size.
- [ ] Commit final package layout as `refactor: organize validators tests and manifests`.

## Task 5: Add Generated-Output Ownership and Check/Apply Contracts

**Files:**
- Create: `tools/data/generated_output_owners.json`
- Create: `tools/lib/generated_outputs.py`
- Create: `tools/tests/test_generated_output_ownership.py`
- Update: each mutating builder under `tools/builders/`
- Update: `tools/README.md`

- [ ] Write a failing test requiring registry entries for state history, buildings, strategic regions, technology, northern countries/OOB, inner-frontier countries/OOB, AIN mandate/OOB, flags, terrain/snow, and exclusion-zone boundaries.
- [ ] Define for every family: owner module, output globs, source manifests/data, check command, apply command, and whether output may be deleted during regeneration.
- [ ] Make builders default to non-mutating check behavior; require `--apply` for writes. Where backward compatibility makes default behavior unsafe to change immediately, the facade must print a deprecation warning and delegate explicitly.
- [ ] Add an idempotence test: snapshot owned output hashes, run `--apply`, run `--apply` again, and require identical hashes after the first run.
- [ ] Run registry tests and every registered check command.
- [ ] Commit as `feat: register generated output ownership`.

## Task 6: Relocate Vendor and Reference Assets Without Breaking Users

**Files:**
- Move: `tools/hoi4_flag_maker_gui/` to `third_party/hoi4_flag_maker/`
- Move verified reference PSD/DOCX/PNG assets from `tools/` to `tools/assets/reference/`
- Create: `third_party/hoi4_flag_maker/README.adiscord.md`
- Update: `tools/README.md`
- Test: `tools/tests/test_repository_contracts.py`

- [ ] Inventory exact vendor and reference paths, licenses/readmes, and any repo references before moving them.
- [ ] Write a failing test that rejects the vendor bundle under `tools/` and requires every moved binary to be documented.
- [ ] Move the vendor tree with history preserved; do not modify third-party code as part of the move.
- [ ] Document provenance, purpose, and update policy for the vendor and reference assets.
- [ ] Update only verified path references; do not invent a wrapper for an unused GUI.
- [ ] Run repository contracts and `git diff --check`.
- [ ] Commit as `chore: separate third party and reference assets`.

## Task 7: Define the Technical Division-Template Audit Schema

**Files:**
- Create: `tools/data/division_template_audit.json`
- Create: `tools/validators/validate_adiscord_division_templates.py`
- Create: `tools/tests/test_validate_adiscord_division_templates.py`
- Update: `tools/validators/validate_tc.py`

- [ ] Write failing tests for one-to-one coverage of all active OOB templates, ASCII technical/display names, battalions/supports, computed organization, manpower/equipment cost, equipment availability, starting factors, supply, AI role, replacement path, and every OOB/`create_unit` reference.
- [ ] Seed audit rows for central claimants, collapse minors, ROM/TRU/VAL/VLA/ZAO theaters, northern generated countries, inner frontier, and AIN mandate.
- [ ] Implement independent parsing of actual OOB/script references; do not trust the JSON row without comparing it to game files.
- [ ] Add explicit failures for missing equipment archetypes, organization below the approved role floor, and duplicate technical names with divergent compositions.
- [ ] Integrate the validator into `validate_tc.py` and run focused RED before any rename.
- [ ] Commit the audit framework as `test: define division template audit contract`.

## Task 8: Replace Cyrillic Technical Names at Generator Sources

**Files:**
- Update: `tools/builders/build_adiscord_ainholm_mandate.py`
- Update: `tools/builders/build_adiscord_inner_frontier_countries.py`
- Update: `tools/builders/build_adiscord_northern_countries.py`
- Update: relevant template-name rows in `tools/data/division_template_audit.json`
- Update: generator-focused tests and validators

- [ ] Add failing assertions that all generated `division_template` names and generator template constants match `^[\x20-\x7E]+$` and contain no Cyrillic.
- [ ] Define stable English names per role, such as `Licensed Security Battalion`, `Northern Line Brigade`, `Northern Militia`, `Frontier Brigade`, `Settler Militia`, and `Filtration Battalion`; record every exact old-to-new mapping in the audit JSON.
- [ ] Change generator sources first, then regenerate AIN, northern, and inner-frontier OOBs with explicit `--apply`.
- [ ] Run each generator check mode and require idempotence.
- [ ] Update validator expectations that currently require Cyrillic names.
- [ ] Run focused generator and division-template tests.
- [ ] Commit as `refactor: use ASCII names in generated division templates`.

## Task 9: Replace Remaining Handwritten Cyrillic Technical Names Atomically

**Files:**
- Update: affected `history/units/*.txt`, including collapse OOBs such as `YOR_vorkerland_collapse.txt`, `ZTA_vorkerland_collapse.txt`, `RIV_vorkerland_collapse.txt`, `REV_vorkerland_collapse.txt`, `NDN_vorkerland_collapse.txt`, `SWB_vorkerland_collapse.txt`, `VHV_vorkerland_collapse.txt`, and `OSV_vorkerland_collapse.txt`
- Update: matching `common/scripted_effects/*.txt` `create_unit` references
- Update: `tools/data/division_template_audit.json`
- Test: `tools/tests/test_validate_adiscord_division_templates.py`

- [ ] Make the validator fail on every remaining Cyrillic `name =` within an active `division_template` and every Cyrillic `division_template =` reference.
- [ ] Rename each definition and all references in one patch; do not leave compatibility duplicates with the same composition.
- [ ] Keep ordinary unit/regiment display text in localisation, not in technical identifiers.
- [ ] Run `rg -n "division_template\s*=.*[А-Яа-яЁё]|name\s*=.*[А-Яа-яЁё]" history/units common/scripted_effects` and require no active technical hits.
- [ ] Run the full division-template audit and collapse validators.
- [ ] Commit as `refactor: remove Cyrillic division template identifiers`.

## Task 10: Resolve Localisation Duplicates and Enforce the Internationalisation Boundary

**Files:**
- Create: `tools/validators/validate_adiscord_localisation.py`
- Create: `tools/tests/test_validate_adiscord_localisation.py`
- Update: conflicting localisation files identified by the validator
- Update: `tools/validators/validate_tc.py`

- [ ] Write a failing parser test that reports duplicate keys with file/line and distinguishes identical duplicates from conflicting values.
- [ ] Enforce BOM for `localisation/russian/*.yml`, ASCII technical IDs, and existence of both English and Russian keys for new/substantially rewritten recovery content.
- [ ] Resolve each conflicting duplicate by selecting one authoritative value and deleting only the duplicate definition, preserving intentionally different language files.
- [ ] Produce a documented debt report for untouched legacy keys rather than machine-translating them.
- [ ] Run the localisation validator, full unit discovery, `validate_tc.py`, and `git diff --check`.
- [ ] Commit as `fix: enforce localisation and technical id contracts`.

## Task 11: Safe File Consolidation Audit

**Files:**
- Create: `docs/audits/2026-08-08-file-consolidation.md`
- Update only if proven safe: `common/country_tags/*.txt`
- Test: `tools/tests/test_repository_contracts.py`

- [ ] Record file counts by engine directory and classify files as engine-sensitive, generated, subsystem-groupable, vendor, asset, or transient.
- [ ] Keep state history, map, strategic regions, generated technology output, and OOB files separate.
- [ ] Confirm existing regional country-tag files already provide useful consolidation; add `WKR` to the Vorkerland tag file rather than creating a one-tag file.
- [ ] Consolidate only exact semantic duplicates or truly orphaned one-tag files after validator proof; do not combine files solely to lower the count.
- [ ] Record every rejected consolidation candidate and reason.
- [ ] Run country-tag uniqueness, path-existence, and full static gates.
- [ ] Commit only if a real safe consolidation remains; otherwise commit the audit with the nearest related tooling commit.

## Task 12: Repository Plan Verification

- [ ] Run `python -B -m unittest discover -s tools/tests -p "test_*.py"`.
- [ ] Run every registered generated-output check command.
- [ ] Run `python -B tools/validate_tc.py --limit 300` through the compatibility facade.
- [ ] Run the package entry point for the same validator and compare exit codes.
- [ ] Run the Cyrillic technical-name search and localisation validator.
- [ ] Run `git diff --check`.
- [ ] Inspect staged paths and confirm no gameplay balance file entered the repository-only commits except the explicit ASCII rename outputs.
- [ ] Record static results in `docs/audits/2026-08-08-recovery-starting-tree.md`; do not claim runtime validation.
