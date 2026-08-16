# SOL Worker Protectorate Cosmetic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SOL use the worker-protectorate cosmetic at campaign start and under WKR/WRK, while reverting to base SOL presentation on independence or non-worker subjection.

**Architecture:** Reuse the existing event-driven `ADISCORD_vorkerland_sync_independence_cosmetic` effect and autonomy on-actions. Seed the start-state cosmetic in country history, and keep VAD's loyalist puppet path separate by checking the actual worker overlord.

**Tech Stack:** Hearts of Iron IV Clausewitz script, Python `unittest`, repository validators.

## Global Constraints

- Fresh campaigns only; no save migrations.
- No monthly polling.
- Preserve unrelated dirty changes, including existing generated flag edits.
- Russian localisation remains UTF-8 with BOM; no localisation edit is required.

---

### Task 1: Specify the SOL cosmetic lifecycle

**Files:**
- Modify: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`
- Modify: `history/countries/SOL - Solarino.txt`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Modify: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`

**Interfaces:**
- Consumes: `ADISCORD_vorkerland_sync_independence_cosmetic`, autonomy on-actions, `SOL_vorkerland_worker_protectorate`.
- Produces: an event-driven SOL presentation contract for start, WKR/WRK dependency, independence, and non-worker dependency.

- [x] **Step 1: Write the failing regression test**

Add assertions that SOL history seeds the protectorate cosmetic; the synchronizer recognizes SOL, applies the cosmetic only for WKR/WRK subjects, and otherwise drops it; the collapse cosmetic pass and all three autonomy hooks invoke the synchronizer; monthly polling does not.

- [x] **Step 2: Run the focused test and verify RED**

Run: `python -B -m unittest tools.tests.test_validate_adiscord_vorkerland_collapse.InterventionAndVisualTests.test_sol_worker_protectorate_cosmetic_tracks_worker_dependency`

Expected: FAIL because SOL history and the synchronizer do not yet implement the lifecycle.

- [x] **Step 3: Implement the minimal Clausewitz changes**

Seed the cosmetic in SOL history, extend the synchronizer with explicit SOL worker-overlord and fallback branches, include SOL in the collapse cosmetic pass, and invoke it for SOL from existing autonomy hooks.

- [x] **Step 4: Verify GREEN and regression gates**

Run the focused test, Vorkerland collapse and diplomacy suites, their validators, `validate_tc.py`, BOM verification, and unstaged/cached `git diff --check`.

- [x] **Step 5: Review scoped diff**

Confirm only the planned SOL lifecycle, tests, and plan/spec documents changed; do not stage or commit.
