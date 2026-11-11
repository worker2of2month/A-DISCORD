# Intelligence Agencies Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give the main countries and their story successors native intelligence agencies with original emblems.

**Architecture:** One shared agency catalogue and country-scoped creation effect. Existing campaign startup and country creation effects dispatch initialization. Political profiles use native catalogue availability; existing agencies retain their state.

**Tech Stack:** Clausewitz scripts, UTF-8 localisation, Imagegen, DDS, Python/Pillow validation.

**Spec:** `docs/superpowers/specs/2026-11-11-intelligence-agencies-design.md`

## Global Constraints

- New campaigns only; preserve ordinary save/load and within-campaign state.
- No Computer Use or game process control.
- No automatic archive of generated image originals inside the mod.
- Russian localisation has BOM; gameplay scripts do not.
- Preserve all unrelated workspace changes; no automatic commits.
- One image generation per emblem; prompts grouped by asset family.

## Review Focus

- No DLC: creation must do nothing.
- Existing agency: initialization must not reset it.
- Unborn successors: creation must wait for actual country existence.
- Vorkerland winner: target routing must preserve the winning tag.
- Exclusive political courses: unavailable emblems must not leak to unrelated countries.

### Task 1: Native lifecycle and catalogue

**Files:** `common/intelligence_agencies/00_intelligence_agencies.txt`,
`common/scripted_effects/ADISCORD_intelligence_agencies.txt`,
`common/on_actions/00_ADISCORD_on_actions.txt`, existing STP/Vorkerland creation effects,
`localisation/{russian,english}/ADISCORD_intelligence_agencies_l_<language>.yml`,
existing STP localisation files, `tools/tests/test_adiscord_intelligence_agencies.py`.

- [x] Add failing lifecycle and catalogue tests for the five review conditions.
- [x] Read actual stable political course flags and country creation boundaries.
- [x] Implement the catalogue, guarded creation effect and lifecycle calls.
- [x] Add names and verify localization encoding and single-line values.
- [x] Run focused tests and review all changed callers.

### Task 2: Original emblems and runtime exports

**Files:** `tools/assets/source/intelligence_agencies/agency_art_prompts.json`,
`gfx/interface/intelligence/agencies/`, `interface/ADISCORD_intelligence_agencies.gfx`.

- [x] Inspect native agency texture dimensions and two-frame layout.
- [x] Generate each national, generic and political emblem through Imagegen.
- [x] Inspect generated results; retain only required runtime exports in the mod.
- [x] Verify every sprite resolves, frame layout, alpha and readability at native size.

### Task 3: Completion verification

- [x] Run focused agency tests and existing STP/Vorkerland lifecycle checks.
- [x] Run `python -B tools/validate_tc.py --limit 300` and `git diff --check`.
- [x] Obtain an independent review of final changes; fix material findings.
- [x] Record native limitations and the manual new-campaign/UI verification checklist.
- [x] Remove only temporary previews created for this task.
