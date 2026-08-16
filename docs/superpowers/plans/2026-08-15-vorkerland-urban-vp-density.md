# Vorkerland Urban VP Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one VP to each disconnected Vorkerland urban settlement that currently has no VP, while preserving every existing VP.

**Architecture:** Keep the exact data in the existing Vorkerland theatre manifest. The existing targeted builder writes the manifest to state history and preserves BOM-safe Russian localisation.

**Tech Stack:** Python 3, `unittest`, HOI4 state history and YAML localisation.

## Global Constraints

- Never remove, move, rename, or revalue an existing VP.
- Do not add VP markers to extra provinces in a city cluster that already has a central VP.
- Generated state history must be changed only through its builder.
- Russian localisation must retain UTF-8 BOM.
- Do not commit without explicit user approval.

---

### Task 1: Add the two missing urban-settlement VPs

**Files:**
- Modify: `tools/tests/test_validate_adiscord_new_states.py`
- Modify: `tools/lib/adiscord_vorkerland_theatre_manifest.py`
- Generated: `history/states/310-310.txt`
- Generated: `history/states/318-318.txt`

**Interfaces:**
- Consumes: `VORKERLAND_THEATRE_VICTORY_POINTS`, `VORKERLAND_THEATRE_PACKAGES`, and `VORKERLAND_THEATRE_PACKAGE_TOTALS`.
- Produces: exact state 310 VP tuple `((16588, 1),)` and exact state 318 VP tuple `((16642, 3), (16624, 1))`.

- [ ] **Step 1: Write the failing outcome test**

Add a test asserting the two exact tuples, while also asserting the retained
pre-existing state 318 centre `(16642, 3)`.

- [ ] **Step 2: Run the focused test and verify RED**

Run `python -B -m unittest tools.tests.test_validate_adiscord_new_states.VorkerlandNewStateOutcomeContractTests.test_disconnected_urban_settlements_receive_victory_points` and confirm it fails because state 310 is absent and state 318 lacks province 16624.

- [ ] **Step 3: Update the exact manifest**

Add state 310 with `((16588, 1),)`, append `(16624, 1)` to state 318, add the
SOL package, and update OSV and SOL totals to 7 and 1 respectively.

- [ ] **Step 4: Regenerate targeted outputs**

Run `python -B tools/builders/build_adiscord_new_states.py --apply-vorkerland-vps`.

- [ ] **Step 5: Verify GREEN and idempotence**

Run the focused test, run the targeted builder a second time, and confirm the
second run creates no additional diff.

- [ ] **Step 6: Run repository gates**

Run the full focused test module, both relevant validators, builder `--check`,
`python -B tools/validate_tc.py --limit 300`, BOM verification, and
`git diff --check`. Inspect the final diff to confirm it contains additions
only for the requested VP behavior and the required manifest/test/docs.
