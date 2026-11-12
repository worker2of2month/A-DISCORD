# Itora Five-Sided Civil War Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Five playable participants, negotiated reunification and symmetric military outcomes.

**Architecture:** Extend the existing IVN effects, triggers, events, decisions,
characters and localisation. The shared peace router delegates to IVN effects.
New country/history definitions are separate only where required by the engine.

**Tech Stack:** Clausewitz, UTF-8 localisation, Python unittest and repository validators.

**Spec:** docs/superpowers/specs/2026-11-12-itora-five-sides-design.md

## Global Constraints

New campaigns only. Preserve unrelated dirty files. Do not launch or control
the game. No new superevents. Generated focus output is rebuilt through its
owner with check, apply and a second check. Russian localisation retains BOM.

## Review Focus

- A delayed or unattended side-choice event starts exactly one conflict.
- A principal can fall while other participants remain independent.
- An offer cannot debit an absent or insolvent initiator or settle twice.
- Player and treaty obligations survive both absorption and final IVN handoff.
- Territory and industry remain sufficient and connected for both principals.

## Task 1: Participants and startup

Files: existing IVN country tags, characters, effects, triggers, events,
portrait GFX and localisation; IMD/IFC/IAM country definitions and histories;
tools/tests/test_adiscord_itora_civil_war.py.

- [x] Add and run failing source-backed scenarios for territory and war pairs.
- [x] Register participants, assign leaders, split territory and armies.
- [x] Separate country creation from player choice and war declaration.
- [x] Verify scenarios and cross-file registrations.

## Task 2: Agreements and settlement

Files: existing IVN decisions/categories, ideas, effects, triggers, events;
shared scripted-peace on_actions; the same scenario tests.

- [x] Add failing cases for partial defeat, every winner and stale offers.
- [x] Implement voluntary reunification with explicit acceptance and guarantees.
- [x] Implement individual absorption and final handoff without default victory.
- [x] Check all event callbacks and ordinary save/load state.

## Task 3: Content integration and validation

Files: IVN localisation, authored focus sources where leadership text changes,
event registry, affected existing tests and development guide.

- [x] Update narrative names and route references without shortening lore.
- [x] Run focused tests; regenerate owned outputs and prove idempotence.
- [x] Run python -B tools/validate_tc.py --limit 300 and git diff --check.
- [x] Review the complete change and report remaining manual runtime checks.
