# A-Discord Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved recovery design into a sequence of reviewable, test-first changes without losing the large existing working set or reintroducing hidden polling and generated-file drift.

**Architecture:** The work is split by ownership boundary: repository/tooling, economy, civil-war state machine and politics, map/forces/AI, and final integration/runtime acceptance. Each subsystem has its own plan and commits; shared files are assigned to one phase at a time. Generated outputs are changed only through their owning builder or manifest.

**Tech Stack:** HOI4 Clausewitz script, scripted GUIs/localisation, Python 3 `unittest` validators and generators, Git, full HOI4 restart/runtime inspection.

## Global Constraints

- The approved source of truth is `docs/superpowers/specs/2026-08-08-adiscord-recovery-design.md`.
- `WRK` is postwar/reunified Vorkerland. `WKR`, `VAD`, and `TVA` are the central wartime claimants.
- Preserve every unrelated or pre-existing dirty change. Never reset or bulk-format the working tree.
- Before each commit, inspect `git status --short`, `git diff --cached --name-status`, and `git diff --cached`.
- Do not hand-edit generated state, strategic-region, technology, building, or generated OOB output. Change the owner, run `--apply`, then run its check mode.
- Russian localisation remains UTF-8 with BOM. Technical IDs, template names, generator symbols, and `create_unit` references remain ASCII/English.
- Prefer events, decisions, flags, bounded delayed retries, and scoped `on_actions`. Do not add monthly world polling or recurring country-wide repair loops.
- Static green is not runtime proof. Map, ideas, AI, technology, GFX, GUI, or localisation changes require a full HOI4 restart before release claims.
- Do not push unless the user requests it.

---

## Plan Set and Exclusive Ownership

| Order | Plan | Primary ownership | Shared-file rule |
| --- | --- | --- | --- |
| 1 | `2026-08-08-adiscord-repository-tooling-and-ascii.md` | `tools/`, root docs/config, technical-name migration | Move/import foundation before other plans add tests; ASCII migration owns generators and OOB names only |
| 2 | `2026-08-08-adiscord-economy-recovery.md` | economy effects, ideas, GUI, scripted loc, economy AI | `common/on_actions/00_ADISCORD_on_actions.txt` is read-only for this recovery; cache invalidation stays inside existing economy entry effects or the minor-optimization hook file |
| 3 | `2026-08-08-adiscord-vorkerland-core.md` Tasks 1-6 | claimant tags, phase controller, war topology, claimant skeletons, regional matrix | Owns collapse events/effects/on_actions until the matrix commit; do not start postwar Tasks 7-12 yet |
| 4 | `2026-08-08-adiscord-map-forces-and-ai.md` Tasks 1-10 | map manifests/builders, templates, OOB, military/air AI, militia and initiative balance | May edit only the exact prefixed blocks and setup sub-blocks listed in that plan's exclusive-ownership section |
| 5 | `2026-08-08-adiscord-vorkerland-core.md` Tasks 7-12 | postwar WRK, shared/postwar focuses, coring packages, dirty-zone schedule, migration | Resumes only after all map/forces commits; consumes final maneuver-state IDs and must not rewrite military-owned setup sub-blocks |
| 6 | `2026-08-08-adiscord-integration-and-runtime-acceptance.md` | migrations, cross-subsystem validators, runtime evidence and final fixes | No feature expansion; fixes acceptance failures only |

## Task 1: Freeze and Record the Authoritative Starting Tree

**Files:** none; this is a read-only execution preflight whose evidence is written by repository/tooling Task 1.

- [ ] Capture `git rev-parse HEAD`, branch, staged paths, modified/deleted/untracked counts, active Git processes, generated owners, and the current 333-test plus `validate_tc.py --limit 300` baseline in the SDD ledger.
- [ ] Do not create or commit an audit or repository contract here. `docs/audits/2026-08-08-recovery-starting-tree.md` and `tools/tests/test_repository_contracts.py` are owned solely by repository/tooling Task 1.

## Task 2: Execute the Repository and ASCII Plan

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-repository-tooling-and-ascii.md`

- [ ] Complete every checkbox in the repository/tooling plan in order.
- [ ] Confirm old root tool entry points still work through compatibility facades.
- [ ] Confirm no Cyrillic remains in technical division-template definitions or references.
- [ ] Commit repository moves separately from generated ASCII/OOB changes so each diff remains reviewable.

## Task 3: Execute Economy Recovery

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-economy-recovery.md`

- [ ] Complete schema migration and cached accounting before GUI work.
- [ ] Verify exactly four policies: tax, military, research, social.
- [ ] Verify the debt tiers and notifications use the exact approved thresholds.
- [ ] Commit logic/migration before GUI/localisation when the staged diff is too large for one review.

## Task 4: Execute the Civil-War Core Foundation

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-vorkerland-core.md`

- [ ] Replace stale WRK-as-claimant tests before adding `WKR`.
- [ ] Complete core Tasks 1-6 only: claimant tags, phase controller, war topology, claimant focus skeletons, and the explicit regional outcome matrix.
- [ ] Implement the explicit regional outcome matrix without a generic puppet fallback.
- [ ] Commit the state machine before focus/decision content and stop after the Task 6 matrix commit; postwar formation, coring, dirty-zone, and migration wait for map/forces.

## Task 5: Execute Map, Force, and AI Balance

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-map-forces-and-ai.md`

- [ ] Build the machine-readable template/OOB audit before changing division counts.
- [ ] Change population, states, VP, supply, and OOB through authoritative builders/manifests.
- [ ] Remove weekly aircraft spawning/redeployment and prove the full aircraft data chain statically.
- [ ] Add bounded militia and initiative systems only after baseline organization, stockpiles, and supply are valid.
- [ ] Commit generated map output separately from military AI/decision logic.

## Task 6: Complete Postwar WRK, Coring, and Dirty-Zone Work

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-vorkerland-core.md`, Tasks 7-12

- [ ] Form postwar WRK and retire temporary tags only after the final map/OOB ownership graph exists.
- [ ] Generate the full integration packages with state IDs 331-340 already included in the exact package of their source.
- [ ] Implement postwar/shared focuses, the progressive January 2163 dirty-zone events, and idempotent migration.
- [ ] Do not rewrite the stockpile/air/initiative/militia setup sub-blocks owned by the completed map/forces phase.
- [ ] Run the core plan verification task and commit postwar formation, coring, and dirty-zone changes separately.

## Task 7: Run Cross-Subsystem Integration and Runtime Acceptance

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-integration-and-runtime-acceptance.md`

- [ ] Run all focused validators and the complete Python unit suite.
- [ ] Run generator check modes and prove idempotence.
- [ ] Run `python -B tools/validate_tc.py --limit 300` and `git diff --check`.
- [ ] Fully restart HOI4 and collect fresh logs for a new campaign and old-save migration.
- [ ] Run the approved route, dirty-zone, air, economy UI, and 8-12 observer campaign matrix.
- [ ] Record failures as targeted tests before fixing them.
- [ ] Do not mark the release gate complete until runtime evidence meets every acceptance condition.

## Task 8: Final Git Audit and Delivery

**Files:**
- Update: `docs/audits/2026-08-08-recovery-starting-tree.md`
- Create: `docs/audits/2026-08-08-recovery-acceptance.md`

- [ ] Compare final tracked/untracked paths with the frozen-tree inventory and account for every deletion, move, and new file.
- [ ] Confirm `git diff --cached --name-status` matches the final thematic commit scope.
- [ ] Confirm no user-owned dirty path was silently omitted or overwritten.
- [ ] Record focused, full static, generator, localisation, runtime, and observer-campaign results separately.
- [ ] Create the final integration commit only after all required evidence is present.
- [ ] Leave the branch unpushed unless the user separately requests publication.
