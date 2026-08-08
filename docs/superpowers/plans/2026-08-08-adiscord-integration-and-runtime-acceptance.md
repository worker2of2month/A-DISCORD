# A-Discord Recovery Integration and Runtime Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the repository, economy, civil-war, map, force, and AI work; prove migrations and static contracts; then obtain fresh HOI4 runtime, UI, route, air-use, dirty-zone, and observer-campaign evidence before the final commit.

**Architecture:** Integration begins from a frozen working tree and a generated ownership audit. A cross-subsystem validator detects stale tags, IDs, policies, templates, polling, and localisation conflicts. Runtime evidence is collected into a structured manifest linked to fresh logs, screenshots, saves, and observer results. Acceptance failures become focused regression tests and scoped fixes; this phase adds no new feature design.

**Tech Stack:** Python validators/evidence collector, Git, HOI4 full restart with A-Discord, Clausewitz logs/saves, screenshots, CSV observer results.

## Global Constraints

- Begin only after every subsystem plan is committed and all agents are idle.
- Freeze the tree before integration: no parallel editor, generator, or agent may change shared files during final gates.
- Preserve the starting-tree inventory and account for every move, deletion, generated output, and untracked asset.
- Runtime acceptance uses a fully restarted HOI4 process. Hot reload and pre-existing logs do not count.
- Do not suppress errors by deleting logs, weakening validators, or adding compatibility polling.
- A runtime failure is fixed by first adding or strengthening a focused static/runtime contract where feasible.
- Observer results are evidence, not a deterministic unit test; record all runs, including bad outcomes.
- Do not push unless the user separately requests it.

---

## Task 1: Freeze the Integrated Tree and Audit Commit Coverage

**Files:**
- Update: `docs/audits/2026-08-08-recovery-starting-tree.md`
- Create: `docs/audits/2026-08-08-recovery-integration-inventory.md`

- [ ] Record branch, HEAD, all thematic commits, `git status --short`, staged paths, untracked paths, and active Git/Python/HOI4 processes.
- [ ] Compare current paths against the starting inventory and classify every change as pre-existing user work, recovery implementation, generated output, intentional deletion, move, or transient artifact.
- [ ] Verify each generated path matches `tools/data/generated_output_owners.json` and no generated output was hand-edited after its last apply/check run.
- [ ] Verify no agent remains running or owns a shared file.
- [ ] Leave the index empty until each integration fix has an explicit commit scope.

## Task 2: Add the Cross-Subsystem Recovery Validator

**Files:**
- Create: `tools/validators/validate_adiscord_recovery_integration.py`
- Create: `tools/tests/test_validate_adiscord_recovery_integration.py`
- Update: `tools/validators/validate_tc.py`

- [ ] Add failing tests that reject wartime WRK claimant references, missing WKR tag/assets, retired construction-policy controls, debt-capacity public/runtime references, Cyrillic technical template names, blanket coring, generic regional subject fallbacks, and weekly/monthly repair polling.
- [ ] Require exactly one definition for every recovery event ID and localisation key.
- [ ] Require every regional outcome/integration package state to exist, every maneuver split to remain in its source package, and every OOB template/reference to resolve.
- [ ] Require economy/civil-war schema migrations to be versioned, idempotent, and reachable on startup for the intended countries.
- [ ] Require dirty events on exact dates and prohibit alternate random opening schedules.
- [ ] Require claimant air chains to reference WKR/VAD/TVA and postwar content to reference WRK.
- [ ] Run the focused validator RED, implement only integration checks, then run it GREEN against the completed subsystems.
- [ ] Commit as `test: validate recovery subsystem integration`.

## Task 3: Run Generator and Static Gates from a Clean Index

**Files:**
- Update: `docs/audits/2026-08-08-recovery-integration-inventory.md`

- [ ] Run every registered builder `--check` command.
- [ ] Snapshot generated output hashes, run only required `--apply` commands, rerun `--check`, and prove a second apply makes no byte changes.
- [ ] Run all focused repository, localisation, economy, recovery, collapse, map, template, force, AI, air, ROM/TRU, VAL, IVN, dirty-zone, and migration suites.
- [ ] Run `python -B -m unittest discover -s tools/tests -p "test_*.py"`.
- [ ] Run `python -B tools/validate_tc.py --limit 300` through the compatibility facade and the package entry point.
- [ ] Run `git diff --check` and the recovery integration validator.
- [ ] Record command, timestamp, exit code, test count, and failure text; distinguish focused green from full-suite green.
- [ ] Commit only generator drift or integration fixes, with a regression test in the same commit.

## Task 4: Build the Runtime Evidence Collector and Fresh-Log Guard

**Files:**
- Create: `tools/validators/collect_adiscord_runtime_evidence.py`
- Create: `tools/tests/test_collect_adiscord_runtime_evidence.py`
- Create: `docs/audits/runtime/README.md`

- [ ] Write failing tests requiring an evidence manifest to reject logs older than the recorded HOI4 launch time, missing `error.log`/`game.log`/`system.log`, empty screenshots, missing save metadata, and observer CSV rows with incomplete fields.
- [ ] Implement a read-only collector that copies or hashes selected evidence into `docs/audits/runtime/<run-id>/` and writes source path, timestamp, size, SHA-256, campaign type, route, and notes.
- [ ] Point the collector at `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/logs` and explicitly supplied screenshot/save paths; never delete or truncate the live log directory.
- [ ] Add pattern summaries for unknown effect/trigger/modifier, missing localisation/GFX, invalid event target, map/state errors, OOB/template errors, and scripted GUI errors without treating an empty pattern list as proof of gameplay success.
- [ ] Run collector unit tests and commit as `test: collect fresh HOI4 runtime evidence`.

## Task 5: Fresh New-Campaign and Migration Startup Smoke Tests

**Files:**
- Create: `docs/audits/runtime/new-campaign/manifest.json` via collector
- Create: `docs/audits/runtime/legacy-migration/manifest.json` via collector

- [ ] Confirm no HOI4 process is running, record the launch timestamp, and start the game from the installed executable with A-Discord enabled.
- [ ] Start a fresh 2160 campaign and verify initial economy schema, prewar phase, preference event, generated countries/tags, focus trees, templates, OOBs, map, and GUI load without script errors.
- [ ] Exit fully, preserve fresh logs, and collect them as the new-campaign run.
- [ ] Restart fully and load a pre-recovery save; verify schema 12 economy migration, WKR/phase reconstruction, regional flags, explicit cores, renamed templates, and dirty-stage reconstruction.
- [ ] Exit fully and collect the migration logs/save metadata separately.
- [ ] Add regression tests and scoped fixes for every reproducible error, rerun the relevant static gates, and repeat the full restart until both smoke runs are clean enough for deeper testing.

## Task 6: Economy UI and Tooltip Visual Acceptance

**Files:**
- Create: `docs/audits/runtime/economy-ui-1366x768/manifest.json`
- Create: `docs/audits/runtime/economy-ui-1920x1080/manifest.json`
- Update: `docs/audits/2026-08-08-recovery-acceptance.md`

- [ ] At 1366x768, capture the complete economy panel, each policy row hover, one enabled and disabled arrow, short inflation/debt/treasury tooltips, delayed versions, and the debt notification.
- [ ] Repeat at 1920x1080.
- [ ] Verify no clipping/overlap, useful row hover areas, practical arrow hitboxes, visible current levels/effects, exact cooldown/boundary reasons, readable next-level weekly deltas, and no diagnostic slogan.
- [ ] Change each policy once and verify tax/army/research/social effects, targeted refresh, three-month cooldown, and weekly balance settlement within seven days.
- [ ] Verify research level 5 gives +5% research and +2% construction speed while levels 1-4 give no positive construction bonus.
- [ ] Trigger first automatic loan and every debt tier; verify one transition notification, cause/current/next-risk text, 4/13 settlement behavior, and immediate repayment downgrade.
- [ ] Collect screenshots/logs for both resolutions and record pass/fail per visual contract.

## Task 7: Civil-War Route, Regional, Coring, Dirty-Zone, and Air Scenarios

**Files:**
- Create: route run manifests under `docs/audits/runtime/routes/`
- Update: `docs/audits/2026-08-08-recovery-acceptance.md`

- [ ] Create targeted saves immediately before WKR, VAD, and TVA victory. For each, fully restart, finish the war, and verify actual WRK formation, correct route/leader/government/focus tree, player control, armies, air wings, subjects, guarantees, and retired temporary tags.
- [ ] Verify VAD joint government promotes the joint council and never annexes a pre-existing WRK.
- [ ] Test at least one survivor from each regional row class and all three WRK routes; verify matrix outcome, ZAO consent/refusal, VAL sovereignty, and absence of generic puppeting.
- [ ] Test voluntary northern integration, forced northern integration, and every named regional coring package; verify costs/times/requirements and no independent ally cores.
- [ ] Run through 2163-01-01, Jan 12, and Jan 27; verify exact stage groups, visible events, idempotent ownership, conflict activation, and old-save reconstruction at each date.
- [ ] For WKR/VAD/TVA, verify valid aircraft stockpile/wings, air-base capacity, fuel, reachable strategic region, and active fighter/CAS missions without weekly forced spawning/redeployment.
- [ ] Collect separate fresh logs and save metadata for each route/scenario class.

## Task 8: Run 8-12 Observer Campaigns

**Files:**
- Update: `docs/audits/2026-08-08-vorkerland-observer-results.csv`
- Update: `docs/audits/2026-08-08-recovery-acceptance.md`

- [ ] Use 8-12 fresh campaigns with recorded seed/setup and no discarded unfavorable runs.
- [ ] Record civil-war start/end, central winner, regional winners, longest interval without meaningful state/VP movement, northern progress, aircraft mission use, initiative expiries, militia decisions/active cap, debt/default events, and script errors.
- [ ] Require normal central completion in two to three years and meaningful movement at least every 60-120 days.
- [ ] Require no claimant to win an overwhelming majority of the sample, no northern front unchanged for years, no unused claimant aircraft, and no runaway militia.
- [ ] Treat a failed distribution or timing target as a balance failure, add a focused contract for its mechanical cause, make the smallest balance change, rerun static gates, and start a new observer sample rather than editing old results.
- [ ] Keep failed-run rows in the CSV and link their evidence manifests.

## Task 9: Final Error, Migration, and Save-Compatibility Audit

**Files:**
- Update: `docs/audits/2026-08-08-recovery-acceptance.md`

- [ ] Search every collected `error.log`, `game.log`, and `system.log`; classify each relevant error as fixed, known legacy/out-of-scope, or blocking with evidence.
- [ ] Rerun migration twice on representative active-war, WKR win, VAD win, TVA win, joint government, regional survivor, economy schema 11, and dirty stage 0/1/2/3 saves; require no duplicate cores, ideas, events, tags, wars, wings, or notifications.
- [ ] Verify every bounded retry reaches success or a named terminal flag/log and no success flag precedes its postcondition.
- [ ] Verify no hidden construction policy, debt capacity, Cyrillic technical template name, blanket core, generic puppet fallback, or prohibited weekly/monthly repair remains.
- [ ] Rerun all static gates after the final runtime-derived fix.

## Task 10: Final Git Audit and Thematic Commit

**Files:**
- Update: `docs/audits/2026-08-08-recovery-integration-inventory.md`
- Update: `docs/audits/2026-08-08-recovery-acceptance.md`

- [ ] Stop HOI4 and all generators; confirm no lock or background writer is active.
- [ ] Compare final tree to the starting inventory and account for every deleted, moved, modified, and untracked path.
- [ ] Confirm all agreed user work is included across thematic commits and no unrelated dirty work was overwritten or silently excluded.
- [ ] Stage only the final integration fixes and acceptance documents; inspect `git diff --cached --name-status`, full staged diff, and `git diff --cached --check`.
- [ ] Create the final commit `chore: verify A-Discord recovery integration` only when static and runtime acceptance documents contain real evidence.
- [ ] Report commit IDs, static gate results, runtime/observer results, known non-blocking limitations, and leave the branch unpushed.
