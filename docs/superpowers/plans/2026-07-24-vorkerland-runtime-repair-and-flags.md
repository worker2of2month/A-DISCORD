# Vorkerland Runtime Repair and Flags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the logged Vorkerland runtime errors, replace weekly outcome polling, and provide the requested flag-tag handoff.

**Architecture:** Keep the existing collapse events and effects. Move outcome timing into one recursive hidden RUS event, repair data files in their current locations, and leave final flag artwork to the user.

**Tech Stack:** HOI4 1.19 Clausewitz script, YAML localisation, Python unittest validator, TGA flag assets.

## Global Constraints

- Work directly on `main`.
- Preserve unrelated dirty-tree changes.
- Keep the contaminated modifier permanent.
- Preserve the 98-day continuous-control rule.
- Do not use a weekly on-action.

---

### Task 1: Regression coverage

**Files:**
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Consumes: existing repository text and flag files.
- Produces: regression tests for localisation, OOBs, startup scope, monitoring, and flags.

- [ ] Add tests that reject single-quoted localisation values, scalar `division_name`, an unscoped startup effect, any `on_weekly`, duplicate flags, and invalid dimensions.
- [ ] Run `python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v`.
- [ ] Confirm the new tests fail on the logged defects.

### Task 2: Runtime data repair

**Files:**
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_states_l_russian.yml`
- Modify: `history/units/*_vorkerland_collapse.txt`
- Modify: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`

**Interfaces:**
- Consumes: HOI4 parser formats already used by working files.
- Produces: parser-safe localisation and OOBs plus a country-scoped startup effect.

- [ ] Convert localisation values to double quotes while preserving UTF-8 BOM.
- [ ] Replace every scalar division name with `{ is_name_ordered = yes name_order = N }`.
- [ ] Execute the dirty-state startup effect inside `RUS = { ... }`.
- [ ] Run the focused unittest suite and confirm these regressions pass.

### Task 3: Efficient outcome monitor

**Files:**
- Delete: `common/on_actions/02_ADISCORD_vorkerland_collapse_outcomes_on_actions.txt`
- Modify: `events/ADISCORD_vorkerland_collapse_events.txt`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`

**Interfaces:**
- Consumes: the three existing victory candidate scripted triggers.
- Produces: hidden event `ADISCORD_vorkerland_collapse.24`, scheduled every 14 days on RUS.

- [ ] Add a failing test requiring a recursive 14-day RUS monitor and exactly seven successful samples.
- [ ] Schedule event `.24` from the war-start event.
- [ ] Increment/reset the three stability variables by one sample and resolve at seven.
- [ ] Reschedule only while the collapse is active and unfinished.
- [ ] Run the focused unittest suite.

### Task 4: Country flag handoff

**Files:**
- No asset changes.

**Interfaces:**
- Consumes: the fixed collapse tag roster.
- Produces: a handoff list for the user.

- [ ] Report `TVA EYR EGC WPA WPS PSD EBA DVA SRA ZTA SLA RZA MLR ERT IRT SCA`.
- [ ] Note the required dimensions: 82x52, 41x26, and 10x7.

### Task 5: Verification and commit

**Files:**
- Modify: `tools/validate_adiscord_vorkerland_collapse.py` if needed for the new invariants.

**Interfaces:**
- Consumes: all repaired content.
- Produces: a verified scoped commit.

- [ ] Run `python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v`.
- [ ] Run `python tools/validate_adiscord_vorkerland_collapse.py`.
- [ ] Run `python tools/validate_tc.py --limit 80`.
- [ ] Check `git diff --check` and stage only Vorkerland repair files.
- [ ] Commit with `fix: repair vorkerland collapse runtime`.
