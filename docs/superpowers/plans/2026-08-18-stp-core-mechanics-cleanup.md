# STP Core Mechanics Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the conflicting STP suspicion/health scripts with one 0..100 suspicion scale, one five-stage Ivanov-health state, synchronized inlay presentation, and deterministic DEBUG decisions.

**Architecture:** `common/scripted_effects/ADISCORD_STP_scripted_effects.txt` owns all STP state transitions and derived modifiers. Decisions and focus inlay consume those canonical variables; dynamic modifiers only expose their mechanical effects. Fresh-campaign startup attaches the two modifiers once, while country history owns initial scalar values.

**Tech Stack:** Hearts of Iron IV Clausewitz script, scripted localisation, decision localisation, Python contract tests.

**Spec:** `docs/superpowers/specs/2026-08-18-stp-core-mechanics-cleanup-design.md`

## Global Constraints

- Suspicion has exactly one persistent variable: `STP_party_suspicion` in `0..100`.
- Suspicion PP mapping is exactly `0.35 - 0.007 * suspicion`.
- Ivanov health has exactly one persistent state variable: `STP_leader_health_stage` in `1..5`.
- Health stages modify stability only; they do not directly modify PP.
- Focus inlay reads `STP_leader_health_stage` directly.
- Existing STP focus content outside the inlay declaration remains untouched.
- DEBUG decisions are explicitly red-labelled and have no gameplay costs.

---

### Task 1: Replace stale STP contract test

**Files:**
- Modify: `tools/tests/test_adiscord_stp_startup.py`

**Interfaces:**
- Consumes: current STP script paths.
- Produces: contract checks for canonical suspicion, health, inlay, decisions, startup references, and absence of abandoned variables.

- [ ] Rewrite the test to reference `common/scripted_effects/ADISCORD_STP_scripted_effects.txt`.
- [ ] Assert the effects file contains `STP_party_suspicion`, `STP_party_suspicion_change`, `STP_sus_political_power_factor`, and the constants `0.35` and `-0.007`.
- [ ] Assert the effects file contains `STP_leader_health_stage`, `STP_requested_health_stage`, and stage-specific stability values `0`, `-0.05`, `-0.10`, `-0.20`, `-0.30`.
- [ ] Assert the STP effects/localisation/inlay/decisions do not contain `STP_party_suspicion_rate`, `STP_leader_health_rate`, or `STP_state_face_stage`.
- [ ] Assert the inlay selects all portraits from `STP_leader_health_stage`.
- [ ] Assert `STP_test` is absent and four `STP_debug_*` decisions exist.
- [ ] Assert startup no longer references deleted `ADISCORD_STP_lock_regular_army_templates`.

### Task 2: Implement canonical STP state effects

**Files:**
- Modify: `common/scripted_effects/ADISCORD_STP_scripted_effects.txt`

**Interfaces:**
- Consumes: temp variables `STP_party_suspicion_change`, `STP_requested_health_stage`.
- Produces: effects `STP_initialize_core_mechanics`, `STP_refresh_party_suspicion`, `STP_change_party_suspicion`, `STP_refresh_leader_health`, `STP_set_leader_health_stage`.

- [ ] Replace the file with the minimal canonical API.
- [ ] `STP_refresh_party_suspicion` clamps `STP_party_suspicion` to `0..100`, computes `STP_sus_political_power_factor = 0.35 - 0.007 * suspicion`, and clamps the factor to `-0.35..0.35`.
- [ ] `STP_change_party_suspicion` adds `STP_party_suspicion_change`, refreshes, then clears the temp input.
- [ ] `STP_refresh_leader_health` clamps stage `1..5` and assigns stability factor by exact stage.
- [ ] `STP_set_leader_health_stage` copies the requested stage, refreshes, then clears the temp input.
- [ ] `STP_initialize_core_mechanics` initializes missing persistent variables to `5` and `1`, refreshes both derived values, and attaches both dynamic modifiers only if they are missing.

### Task 3: Simplify modifiers and initialization

**Files:**
- Modify: `common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt`
- Modify: `common/on_actions/00_ADISCORD_on_actions.txt`
- Modify: `history/countries/STP - StepanLand.txt`

**Interfaces:**
- Consumes: derived variables from Task 2.
- Produces: permanent STP PP/stability effects and deterministic fresh-game state.

- [ ] Keep only `STP_fading_father` with `stability_factor = STP_fading_father_stability_factor` and `STP_party_suspicion_dynamic_modifier` with `political_power_factor = STP_sus_political_power_factor`.
- [ ] In STP country history, set `STP_party_suspicion = 5`, `STP_sus_political_power_factor = 0.315`, `STP_leader_health_stage = 1`, and `STP_fading_father_stability_factor = 0`.
- [ ] In the existing fresh-campaign `STP = {}` startup scope, call `STP_initialize_core_mechanics = yes`.
- [ ] Remove the stale call to deleted `ADISCORD_STP_lock_regular_army_templates`.

### Task 4: Synchronize inlay and scripted localisation

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
- [ ] Keep `STPGetStateFaceStageName` and `STPGetStateFaceTooltip`, rewritten to test `STP_leader_health_stage`.
- [ ] Rewrite suspicion helpers to use thresholds 25/50/70/90 on `STP_party_suspicion`.
- [ ] Simplify decision description to suspicion status only; leader-health detail lives on inlay hover.
- [ ] Remove percentage-health and stale fading-factor text from decision localisation.

### Task 5: Replace disposable test decision with DEBUG controls

**Files:**
- Modify: `common/decisions/ADISCORD_STP_decisions.txt`
- Modify: `localisation/russian/ADISCORD_STP_decisions_l_russian.yml`

**Interfaces:**
- Consumes: canonical effects from Task 2.
- Produces: four deterministic testing controls.

- [ ] Delete `STP_test`.
- [ ] Add `STP_debug_increase_suspicion`: set temp change to `10`, call `STP_change_party_suspicion`.
- [ ] Add `STP_debug_decrease_suspicion`: set temp change to `-10`, call `STP_change_party_suspicion`.
- [ ] Add `STP_debug_worsen_ivanov`: derive requested stage as current stage + 1, call `STP_set_leader_health_stage`.
- [ ] Add `STP_debug_improve_ivanov`: derive requested stage as current stage - 1, call `STP_set_leader_health_stage`.
- [ ] Localize every title with `§RDEBUG:§!` followed by a normal Russian action name.
- [ ] Give each DEBUG decision a concise description stating the exact test change.

### Task 6: Verify the cleaned contract

**Files:**
- Test: `tools/tests/test_adiscord_stp_startup.py`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: evidence that no dual-state STP architecture remains.

- [ ] Run `python -m unittest tools.tests.test_adiscord_stp_startup -v`.
- [ ] Search the STP runtime files for `STP_party_suspicion_rate`, `STP_leader_health_rate`, `STP_state_face_stage`, `STP_test`, and `ADISCORD_STP_lock_regular_army_templates`; expect no runtime hits.
- [ ] Inspect the final main diff for unrelated STP focus-tree changes; none are allowed.
