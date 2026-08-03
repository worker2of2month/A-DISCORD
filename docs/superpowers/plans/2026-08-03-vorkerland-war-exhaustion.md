# Vorkerland Civil-War Exhaustion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independent casualty- and duration-driven war exhaustion for WRK and VAD with monthly targeted updates and peaceful recovery.

**Architecture:** The existing Vorkerland monthly on-action invokes country-scoped scripted effects for only WRK/VAD. One local score per country is converted into variables consumed by one dynamic modifier; debug controls reuse the existing scenario category.

**Tech Stack:** HOI4 Clausewitz script, dynamic modifiers, Russian YAML localisation with UTF-8 BOM, Python `unittest` validation.

## Global Constraints

- Do not add a daily pulse, `every_country`, or `every_state` exhaustion loop.
- Do not penalise attack or organisation; the mechanic must not refreeze fronts.
- Preserve all concurrent civil-war, NAM, state, flag, and portrait changes.
- Do not commit from this shared multi-agent worktree; the root agent owns integration.

---

### Task 1: Executable exhaustion contract

**Files:**
- Create: `tools/test_vorkerland_war_exhaustion.py`
- Modify: `tools/validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Consumes: `named_block(source: str, name: str) -> str` and `validate(root: Path, section: str | None) -> list[str]`.
- Produces: `validate_exhaustion(root: Path, issues: list[str]) -> None` and the new `exhaustion` validator section.

- [ ] **Step 1: Write failing tests for the approved observable contract**

Test monthly routing for only WRK/VAD, separate country-scope variables, casualty snapshots and literal 5/25/100 thresholds, +2 duration, -8 peace recovery, clamps, one modifier without attack/org penalties, two AI-disabled debug decisions, and BOM localisation.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `python -B -m unittest tools.test_vorkerland_war_exhaustion -v`

Expected: failures because the exhaustion section/effects/modifier/debug keys do not exist.

- [ ] **Step 3: Add the minimal validator section**

Add `exhaustion` to `SECTIONS` and `CHECKS`, then validate the production files and all approved invariants without changing other validator sections.

### Task 2: Country-scoped monthly model

**Files:**
- Modify: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Modify: `common/dynamic_modifiers/ADISCORD_vorkerland_collapse_dynamic_modifiers.txt`

**Interfaces:**
- Produces: `ADISCORD_vorkerland_update_civil_war_exhaustion`, `ADISCORD_vorkerland_refresh_civil_war_exhaustion`, and `ADISCORD_vorkerland_reset_civil_war_exhaustion` scripted effects.
- Produces: `ADISCORD_vorkerland_civil_war_exhaustion` dynamic modifier.

- [ ] **Step 1: Add one targeted branch to the existing monthly pulse**

Route only country scopes with `tag = WRK` or `tag = VAD`; call the update effect after collapse start or while the score variable exists.

- [ ] **Step 2: Implement snapshot, delta, gain, decay, and clamps**

Initialize the snapshot before computing delta; while WRK and VAD directly fight, add 2 plus 1/3/6 at 5/25/100 casualty delta; otherwise subtract 8. Clamp score 0–100 and delta 0–10000.

- [ ] **Step 3: Derive modifier values and manage its lifecycle**

Set war support to score × -0.002, stability/factory output/surrender limit to score × -0.001, and army morale to score × -0.0005. Add and refresh the modifier above zero; remove it at zero.

- [ ] **Step 4: Run focused tests and confirm remaining failures are only debug/localisation**

Run: `python -B -m unittest tools.test_vorkerland_war_exhaustion -v`

### Task 3: Player and debug surface

**Files:**
- Modify: `common/decisions/ADISCORD_scenario_debug_decisions.txt`
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Modify: `localisation/russian/ADISCORD_scenario_debug_l_russian.yml`
- Modify: `docs/testing/vorkerland_and_nam_debug.md`

**Interfaces:**
- Consumes: the refresh and reset effects from Task 2.
- Produces: `ADISCORD_debug_add_vorkerland_war_exhaustion` and `ADISCORD_debug_reset_vorkerland_war_exhaustion`.

- [ ] **Step 1: Add Russian modifier localisation with current score**

Add the modifier name, description, and tooltip containing `[?ADISCORD_vorkerland_civil_war_exhaustion|0]/100` while retaining UTF-8 BOM.

- [ ] **Step 2: Add two debug-only decisions**

Allow only WRK/VAD, add 25 with clamp/refresh or call reset, use zero cost, and set `ai_will_do = { factor = 0 }`.

- [ ] **Step 3: Localise and document the debug controls**

Use the existing red `§RDEBUG:§!` naming style and add a short WRK/VAD test instruction.

### Task 4: Verification

**Files:**
- Verify all files from Tasks 1–3.

- [ ] **Step 1: Run focused red/green suite and validator**

Run: `python -B -m unittest tools.test_vorkerland_war_exhaustion -v`

Run: `python -B tools/validate_adiscord_vorkerland_collapse.py --section exhaustion`

- [ ] **Step 2: Run broader regression gates**

Run: `python -B -m unittest tools.test_validate_adiscord_vorkerland_collapse -q`

Run: `python -B tools/validate_adiscord_vorkerland_collapse.py`

Run: `python -B tools/validate_tc.py --limit 300`

- [ ] **Step 3: Check patch cleanliness and shared-file scope**

Run `git diff --check` only for the implementation files, inspect their diffs, and verify no state, PIV, NAM, flag, or portrait file was modified by this task.
