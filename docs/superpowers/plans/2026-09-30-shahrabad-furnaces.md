# Shahrabad Furnaces Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement the tasks in this chat. Do not commit, push or launch the shared game without user authorization.

**Goal:** Implement the approved SHL furnace campaign with native decisions, focus rewards and a cached country interface.

**Architecture:** A single SHL cycle event settles nine fixed industrial sites every 28 days. Site variables own wear, stocks, ownership and receipts; country variables own policy, project stages and cached aggregate/UI values. This local ownership refinement preserves paid operations when territory changes hands, without a new country or save migration.

**Tech Stack:** Native HOI4 Clausewitz scripts and GUI, existing Python focus builder and parser.

**Spec:** docs/superpowers/specs/2026-09-30-shahrabad-furnaces-design.md

## Global Constraints

- New campaigns only; preserve ordinary current-version save/load.
- One SHL file per engine data type; preserve unrelated shared code.
- Gameplay UTF-8 without BOM; Russian localisation UTF-8 BOM.
- Fixed SHL sites only, no daily or world-scanning simulation.
- Native custom costs debit all declared resources exactly once.
- Existing economy treasury; generated focuses owned by the focus builder.
- Work in the authorized checkout; retain edits uncommitted for review.

## Review Focus

- A second operation on one site cannot overwrite its receipt.
- A cancellation or duplicate delayed callback cannot create money or a factory.
- A lost region never delivers paid work to the occupying country.
- Building-slot exhaustion returns payment and leaves the stage retryable.
- GUI selection, context changes and external control changes remain readable.

## Task 1: Furnace lifecycle and accounting

**Files:** SHL scripted effects, triggers, decisions, categories, dynamic modifier, events, on_actions; existing startup, minor allowlist and development country list; tools/tests/test_adiscord_shl_furnaces.py.

**Interfaces:** SHL_initialize_furnaces, SHL_run_cycle, SHL_refresh_furnaces, SHL_finish_supply/repair/training/restart and SHL_cancel_operation use boolean calls. State operation receipts retain exact cost and currency source; furnace source values stay in states 287-295.

- [x] Write interpreter tests exercising real parsed script at stock and cost boundaries, duplicate settlement, interruption, ownership and furnace stop/restart.
- [x] Run them and verify failure because the SHL implementation is absent.
- [x] Implement one-shot startup, 28-day event and native targeted paid operations.
- [x] Remove SHL from suppression while retaining its research restoration entry; make SHL an active economy/development participant.
- [x] Run targeted tests and compare shared validator diagnostics with baseline.

## Task 2: Campaign and focus rewards

**Files:** focus_trees/SHL/main/focuses.txt, existing focus builder, SHL events/decisions/effects/localisation, event-ID registry.

**Interfaces:** Project stage and receipt values have one authoritative owner. Focus rewards unlock native decisions; first-pour settlement owns stage advancement. Political course is exclusive and terminal choices preserve the actual industrial result.

- [x] Add failing tests for four project stages, occupied-slot cancellation and all three political courses.
- [x] Implement 30 focuses, paid project stages, pressure events and a safe default response.
- [x] Register SHL events without modifying other event entries.
- [x] Run focus builder check, apply only its stale SHL output, then check again.
- [x] Verify native focus prerequisites, real rewards, prices and source BOM.

## Task 3: Conclave interface and final verification

**Files:** SHL scripted GUI, interface GUI/GFX, scripted localisation, Russian/English localisation, AI plan; existing performance/lore documentation.

**Interfaces:** SHL_gui_dirty invalidates cached furnace data. Native decisions remain the transaction owner; GUI selection never mutates a paid operation target.

- [x] Test selection and cached values, invalidation writers and fixed scope of recurring work.
- [x] Build the compact 3×3 furnace panel using existing industrial art; show ownership, wear, stocks and tenth-project stage.
- [x] Add bounded SHL AI behaviour and focus order; no extra world hooks.
- [x] Run focused tests, focus/event/minor validators, validate_tc with UTF-8 output and git diff --check.
- [x] Review the complete diff, fix confirmed regressions and record source hashes for a later cold-load check.
- [x] Report static evidence and runtime-unverified behaviour separately.

## Baseline

Before gameplay edits, event-ID validation already reports unregistered ADISCORD_STP_pc.50.
Minor validation already reports BBV/BCM/BGT/BHG/BJK/BLD participation outside their dormant contract.
The broad validator has additional unrelated source/map/localisation findings; its first shell run also hit cp1251 output encoding. Run with PYTHONIOENCODING=utf-8 to retain a complete comparable result.
