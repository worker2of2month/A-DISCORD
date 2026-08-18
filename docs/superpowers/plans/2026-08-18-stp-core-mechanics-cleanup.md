# STP Core Mechanics Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the conflicting STP suspicion/health scripts with one 0..100 suspicion scale, one five-stage Ivanov-health state, synchronized inlay presentation, deterministic DEBUG decisions, and the preserved starting division restriction.

**Architecture:** `common/scripted_effects/ADISCORD_STP_scripted_effects.txt` owns STP political state transitions and derived modifiers. Decisions and focus inlay consume those canonical variables; dynamic modifiers only expose their mechanical effects. Country history owns only persistent starting state. `ADISCORD_STP_army_restriction_effects.txt` remains a small independent lock/unlock API invoked by the single STP core initializer and by the starting hedonism idea when removed.

**Tech Stack:** Hearts of Iron IV Clausewitz script, scripted localisation, decision localisation, Python contract tests.

**Spec:** `docs/superpowers/specs/2026-08-18-stp-core-mechanics-cleanup-design.md`

## Global Constraints

- Suspicion has exactly one persistent variable: `STP_party_suspicion` in `0..100`.
- Suspicion PP mapping is exactly `0.35 - 0.007 * suspicion`.
- `STP_sus_political_power_factor` is derived and must not be authored in country history.
- Ivanov health has exactly one persistent state variable: `STP_leader_health_stage` in `1..5`.
- `STP_fading_father_stability_factor` is derived and must not be authored in country history.
- Health stages modify stability only; they do not directly modify PP.
- Focus inlay reads `STP_leader_health_stage` directly.
- Police and Regular Army start locked and are unlocked when `STP_hedonism_with_no_bondaries` is removed.
- Capital Guard remains permanently locked and capped at one.
- Existing STP focus content outside the inlay declaration remains untouched.
- DEBUG decisions are explicitly red-labelled and have no gameplay costs.

---

### Task 1: Replace stale STP contract tests

**Files:**
- Modify: `tools/tests/test_adiscord_stp_startup.py`
- Modify: `tools/tests/test_adiscord_army_hq_contracts.py`

**Interfaces:**
- Consumes: current STP script paths.
- Produces: contract checks for canonical suspicion, health, inlay, decisions, initialization, and starting division locks.

- [ ] Assert the effects file contains `STP_party_suspicion`, `STP_party_suspicion_change`, `STP_sus_political_power_factor`, and the constants `0.35` and `-0.007`.
- [ ] Assert country history contains `STP_party_suspicion = 5` but not authored `STP_sus_political_power_factor`.
- [ ] Assert the effects file contains `STP_leader_health_stage`, `STP_requested_health_stage`, and stage-specific stability values `0`, `-0.05`, `-0.10`, `-0.20`, `-0.30`.
- [ ] Assert country history contains `STP_leader_health_stage = 1` but not authored `STP_fading_father_stability_factor`.
- [ ] Assert the STP effects/localisation/inlay/decisions do not use `STP_party_suspicion_rate`, `STP_leader_health_rate`, or `STP_state_face_stage` as state variables.
- [ ] Assert the inlay selects all portraits from `STP_leader_health_stage`.
- [ ] Assert `STP_test` is absent and four `STP_debug_*` decisions exist.
- [ ] Assert Police, Regular Army, and Capital Guard start locked; only Police and Regular Army are present in the unlock effect.

### Task 2: Implement canonical STP state effects

**Files:**
- Modify: `common/scripted_effects/ADISCORD_STP_scripted_effects.txt`

**Interfaces:**
- Consumes: temp variables `STP_party_suspicion_change`, `STP_requested_health_stage`.
- Produces: effects `STP_initialize_core_mechanics`, `STP_refresh_party_suspicion`, `STP_change_party_suspicion`, `STP_refresh_leader_health`, `STP_set_leader_health_stage`.

- [ ] `STP_refresh_party_suspicion` clamps `STP_party_suspicion` to `0..100`, computes `STP_sus_political_power_factor = 0.35 - 0.007 * suspicion`, and clamps the factor to `-0.35..0.35`.
- [ ] `STP_change_party_suspicion` adds `STP_party_suspicion_change`, refreshes, then clears the temp input.
- [ ] `STP_refresh_leader_health` clamps stage `1..5`, assigns stability factor by exact stage, and derives `STP_ivanov_dead` from stage 5.
- [ ] `STP_set_leader_health_stage` copies the requested stage, refreshes, then clears the temp input.
- [ ] `STP_initialize_core_mechanics` initializes missing persistent variables to `5` and `1`, refreshes both derived values, synchronizes the starting army restriction with the hedonism idea, and attaches both dynamic modifiers only if missing.

### Task 3: Keep only canonical initial state

**Files:**
- Modify: `common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt`
- Modify: `common/on_actions/00_ADISCORD_on_actions.txt`
- Modify: `history/countries/STP - StepanLand.txt`

**Interfaces:**
- Consumes: derived variables from Task 2.
- Produces: permanent STP PP/stability effects and deterministic fresh-game state.

- [ ] Keep only `STP_fading_father` with `stability_factor = STP_fading_father_stability_factor` and `STP_party_suspicion_dynamic_modifier` with `political_power_factor = STP_sus_political_power_factor`.
- [ ] In STP country history, author only `STP_party_suspicion = 5` and `STP_leader_health_stage = 1`.
- [ ] In the existing fresh-campaign `STP = {}` startup scope, call `STP_initialize_core_mechanics = yes` exactly once.
- [ ] Do not add a second direct army-lock call to `on_startup`; the core initializer owns synchronization.

### Task 4: Preserve the starting army restriction with a minimal API

**Files:**
- Create/restore: `common/scripted_effects/ADISCORD_STP_army_restriction_effects.txt`
- Modify: `history/units/STP.txt`
- Modify: `common/ideas/steland.txt`

**Interfaces:**
- Produces: `ADISCORD_STP_lock_regular_army_templates`, `ADISCORD_STP_unlock_regular_army_templates`.
- Consumed by: `STP_initialize_core_mechanics`, `STP_hedonism_with_no_bondaries.on_remove`.

- [ ] Restore `is_locked = yes` and `force_allow_recruiting = no` on Police division and Regular army in the STP OOB.
- [ ] Keep the same restrictions plus `division_cap = 1` on Capital Guard.
- [ ] Implement a lock effect that reasserts restrictions on all three authored templates.
- [ ] Implement an unlock effect that unlocks only Police and Regular Army.
- [ ] Do not restore the old `ADISCORD_STP_migrate_army_template_lock` wrapper.
- [ ] Restore `custom_modifier_tooltip = STP_hedonism_army_restriction_tt` and `on_remove = { ADISCORD_STP_unlock_regular_army_templates = yes }` on the hedonism idea.

### Task 5: Synchronize inlay and scripted localisation

**Files:**
- Modify: `common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt`
- Modify: `common/scripted_localisation/ADISCORD_STP_scripted_loc.txt`
- Modify: `localisation/russian/ADISCORD_STP_gui_l_russian.yml`
- Modify: `localisation/russian/ADISCORD_STP_decisions_l_russian.yml`

**Interfaces:**
- Consumes: `STP_leader_health_stage`, `STP_party_suspicion`, `STP_sus_political_power_factor`.
- Produces: portrait selection, hover tooltip, status-panel text.

- [ ] Keep portrait selection on `STP_leader_health_stage = 1..5`.
- [ ] Remove `PeterHealth`, `STPGetLeaderHealthStageName`, and `STPGetLeaderHealthTooltip` scripted-localisation blocks.
- [ ] Keep `STPGetStateFaceStageName` and `STPGetStateFaceTooltip`, testing `STP_leader_health_stage` directly.
- [ ] Keep suspicion helpers on thresholds 25/50/70/90 using `STP_party_suspicion`.
- [ ] Keep leader-health detail on the inlay hover rather than the decisions category.

### Task 6: Replace disposable test decision with DEBUG controls

**Files:**
- Modify: `common/decisions/ADISCORD_STP_decisions.txt`
- Modify: `localisation/russian/ADISCORD_STP_decisions_l_russian.yml`

**Interfaces:**
- Consumes: canonical effects from Task 2.
- Produces: four deterministic testing controls.

- [ ] Delete `STP_test`.
- [ ] Add `STP_debug_increase_suspicion`: +10 suspicion.
- [ ] Add `STP_debug_decrease_suspicion`: -10 suspicion.
- [ ] Add `STP_debug_worsen_ivanov`: current stage + 1.
- [ ] Add `STP_debug_improve_ivanov`: current stage - 1.
- [ ] Localize every title with `§RDEBUG:§!` followed by a normal Russian action name.

### Task 7: Verify the cleaned contract

**Files:**
- Test: `tools/tests/test_adiscord_stp_startup.py`
- Test: `tools/tests/test_adiscord_army_hq_contracts.py`
- Validate: `tools/validators/validate_adiscord_division_templates.py`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: evidence that no dual-state STP architecture remains and the starting-army restriction remains internally consistent.

- [ ] Run `python -m unittest tools.tests.test_adiscord_stp_startup -v`.
- [ ] Run the STP methods in `tools.tests.test_adiscord_army_hq_contracts -v`.
- [ ] Run the division-template validator; the restored minimal lock/unlock file must satisfy its existing audited technical-reference counts without weakening validation.
- [ ] Search runtime STP files for `STP_party_suspicion_rate`, `STP_leader_health_rate`, `STP_state_face_stage`, `STP_test`, and `ADISCORD_STP_migrate_army_template_lock`; expect no active-state/migration hits.
- [ ] Inspect the final diff for unrelated STP focus-tree changes; none are allowed.
