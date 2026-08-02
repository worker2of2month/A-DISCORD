# Economy Dashboard Levels And Starting Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every budget level independently explainable, restore the missing increase arrows and manual borrowing actions, and give VAL/STP distinct one-shot starting macroeconomic profiles.

**Architecture:** Passive budget pips become hover targets with fixed level tooltips, while the moving active marker keeps the compact dynamic current-level tooltip. Country profiles run only inside first-time economy initialization after global defaults, then synchronize accounting snapshots and let existing calculations derive debt ratio, creditworthiness, overload, interest, and cycle status.

**Tech Stack:** Hearts of Iron IV Clausewitz GUI, scripted localisation, scripted effects, Python `unittest` contract tests.

## Global Constraints

- Do not add weekly/monthly country or state scans.
- Keep Russian localisation UTF-8 with BOM.
- Preserve existing save migration semantics; profiles apply only when `ADISCORD_economy_initialized` is absent.
- VAL starts with treasury 180, debt 260, inflation 9, deficit pressure 14, fiscal stress 22, and price shock 10.
- STP starts with treasury 240, debt 140, inflation 14, deficit pressure 8, fiscal stress 26, and price shock 16.
- Keep all four starting budget policies at level 3/5.

---

### Task 1: Budget Level Hover Targets And Paired Arrows

**Files:**
- Modify: `tools/test_validate_adiscord_gui_contracts.py`
- Modify: `interface/ADISCORD_economy.gui`
- Modify: `localisation/russian/ADISCORD_economy_l_russian.yml`

**Interfaces:**
- Consumes: existing `ADISCORD_economy_<policy>_effects_<level>` localisation keys.
- Produces: `ADISCORD_economy_<policy>_level_<level>_tt` for each of four policies and five levels.

- [ ] **Step 1: Write failing GUI contracts**

  Require each pip to accept hover and bind its own level tooltip. Require every increase button to use `button_right` without `orientation = upper_right`.

- [ ] **Step 2: Run the focused GUI contracts and verify RED**

  Run: `python -B -m unittest tools.test_validate_adiscord_gui_contracts.EconomyDashboardGuiContractTests -v`

  Expected: failures identify transparent pips, missing level tooltip keys, and right-arrow orientation.

- [ ] **Step 3: Implement the minimal GUI/localisation change**

  Remove pointer transparency from the twenty pips, attach fixed tooltip keys, remove the broken right-edge orientation from four increase buttons, and replace the oversized comparative current tooltip with a compact dynamic current-level tooltip.

- [ ] **Step 4: Run the focused GUI contracts and verify GREEN**

  Run: `python -B -m unittest tools.test_validate_adiscord_gui_contracts.EconomyDashboardGuiContractTests -v`

  Expected: all dashboard contracts pass.

### Task 2: VAL And STP Starting Macroeconomic Profiles

**Files:**
- Modify: `tools/test_adiscord_economy_weekly_contracts.py`
- Modify: `common/scripted_effects/ADISCORD_economy_effects.txt`

**Interfaces:**
- Produces: `ADISCORD_economy_apply_country_starting_profile` invoked once by `ADISCORD_economy_initialize_country`.
- Consumes: existing macro recalculation and accounting variables.

- [ ] **Step 1: Write a failing first-run profile contract**

  Assert the approved literal VAL/STP values, a first-initialization-only call site, accounting snapshot synchronization, and no invocation from weekly/monthly update effects.

- [ ] **Step 2: Run the focused economy contract and verify RED**

  Run: `python -B -m unittest tools.test_adiscord_economy_weekly_contracts.WeeklyEconomyContracts.test_val_and_stp_start_with_distinct_macroeconomic_profiles -v`

  Expected: failure because the starting-profile effect does not exist.

- [ ] **Step 3: Implement the one-shot profiles**

  Apply approved raw values after defaults, sync treasury/debt bookkeeping snapshots, then use existing macro and overload calculations to derive visible secondary values without a new recurring loop.

- [ ] **Step 4: Run focused and full validation**

  Run:

  ```text
  python -B -m unittest tools.test_validate_adiscord_gui_contracts -v
  python -B -m unittest tools.test_adiscord_economy_weekly_contracts -v
  python -B tools/validate_adiscord_economy_ai.py
  python -B tools/validate_tc.py --limit 300
  git diff --check
  ```

  Expected: zero failures and zero validation errors.

- [ ] **Step 5: Commit the coherent change**

  Stage only the GUI, localisation, scripted localisation/effects, tests, and this plan; commit directly to `main` with `fix: make economy levels and starts readable`.

### Task 3: Restore Manual Borrowing To The Compact Dashboard

**Files:**
- Modify: `tools/test_validate_adiscord_gui_contracts.py`
- Modify: `interface/ADISCORD_economy.gui`
- Modify: `common/scripted_guis/ADISCORD_economy_scripted_gui.txt`

**Interfaces:**
- Consumes: existing `ADISCORD_economy_gui_try_issue_internal_bonds`, `ADISCORD_economy_gui_try_take_external_loan`, and their eligibility triggers/tooltips.
- Produces: visible `ADISCORD_economy_action_internal_bonds` and `ADISCORD_economy_action_external_loan` dashboard buttons.

- [ ] **Step 1: Write a failing dashboard borrowing contract**

  Require both borrowing buttons, their click effects, and their enabled triggers to be wired into the compact dashboard.

- [ ] **Step 2: Run the focused GUI contract and verify RED**

  Run: `python -B -m unittest tools.test_validate_adiscord_gui_contracts.EconomyDashboardGuiContractTests.test_compact_dashboard_exposes_manual_borrowing_actions -v`

  Expected: failure because both button nodes are absent from `ADISCORD_economy.gui`.

- [ ] **Step 3: Add a three-row treasury action block**

  Place internal/external borrowing on row one, repayment/restructuring on row two, and stabilization/war taxes on row three. Reuse the existing effects, triggers, and explanatory tooltips so disabled buttons explain their requirements.

- [ ] **Step 4: Re-run the focused GUI contract**

  Expected: PASS with both actions visible and wired.
