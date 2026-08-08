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
| 2 | `2026-08-08-adiscord-economy-recovery.md` | economy effects, ideas, GUI, scripted loc, economy AI | Economy agent owns `common/on_actions/00_ADISCORD_on_actions.txt` only if a cache invalidation hook is proven necessary |
| 3 | `2026-08-08-adiscord-vorkerland-core.md` | tags, phase controller, focuses, decisions, regional matrix, coring, dirty-zone schedule | Owns collapse events/effects/on_actions before military tuning begins |
| 4 | `2026-08-08-adiscord-map-forces-and-ai.md` | map manifests/builders, templates, OOB, military/air AI, militia and initiative balance | May edit collapse decisions/effects only after the core plan is committed and only in named military blocks |
| 5 | `2026-08-08-adiscord-integration-and-runtime-acceptance.md` | migrations, cross-subsystem validators, runtime evidence and final fixes | No feature expansion; fixes acceptance failures only |

## Task 1: Freeze and Record the Authoritative Starting Tree

**Files:**
- Create: `docs/audits/2026-08-08-recovery-starting-tree.md`
- Test: `tools/tests/test_repository_contracts.py`

- [ ] Record `git rev-parse HEAD`, branch, staged paths, modified/deleted/untracked counts, and active Git processes.
- [ ] Record the existing generated owners for states, buildings, strategic regions, technology, northern countries, inner-frontier countries, and collapse manifests.
- [ ] Add a failing repository contract that requires every generated output family to appear in the ownership registry planned below.
- [ ] Run `python -B -m unittest tools.tests.test_repository_contracts -v` and preserve the expected RED output in the implementation notes.
- [ ] Implement only the inventory needed to make the contract GREEN; do not modify gameplay in this task.
- [ ] Run the focused test, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`.
- [ ] Commit the frozen-tree inventory and tooling foundation as `chore: establish recovery repository contracts`.

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

## Task 4: Execute the Civil-War Core

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-vorkerland-core.md`

- [ ] Replace stale WRK-as-claimant tests before adding `WKR`.
- [ ] Complete the phase controller and formation paths before tuning any front.
- [ ] Implement the explicit regional outcome matrix without a generic puppet fallback.
- [ ] Implement progressive January 2163 dirty-zone events and idempotent migration.
- [ ] Commit the state machine before focus/decision content, then commit coring/dirty-zone separately.

## Task 5: Execute Map, Force, and AI Balance

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-map-forces-and-ai.md`

- [ ] Build the machine-readable template/OOB audit before changing division counts.
- [ ] Change population, states, VP, supply, and OOB through authoritative builders/manifests.
- [ ] Remove weekly aircraft spawning/redeployment and prove the full aircraft data chain statically.
- [ ] Add bounded militia and initiative systems only after baseline organization, stockpiles, and supply are valid.
- [ ] Commit generated map output separately from military AI/decision logic.

## Task 6: Run Cross-Subsystem Integration and Runtime Acceptance

**Plan:** `docs/superpowers/plans/2026-08-08-adiscord-integration-and-runtime-acceptance.md`

- [ ] Run all focused validators and the complete Python unit suite.
- [ ] Run generator check modes and prove idempotence.
- [ ] Run `python -B tools/validate_tc.py --limit 300` and `git diff --check`.
- [ ] Fully restart HOI4 and collect fresh logs for a new campaign and old-save migration.
- [ ] Run the approved route, dirty-zone, air, economy UI, and 8-12 observer campaign matrix.
- [ ] Record failures as targeted tests before fixing them.
- [ ] Do not mark the release gate complete until runtime evidence meets every acceptance condition.

## Task 7: Final Git Audit and Delivery

**Files:**
- Update: `docs/audits/2026-08-08-recovery-starting-tree.md`
- Create: `docs/audits/2026-08-08-recovery-acceptance.md`

- [ ] Compare final tracked/untracked paths with the frozen-tree inventory and account for every deletion, move, and new file.
- [ ] Confirm `git diff --cached --name-status` matches the final thematic commit scope.
- [ ] Confirm no user-owned dirty path was silently omitted or overwritten.
- [ ] Record focused, full static, generator, localisation, runtime, and observer-campaign results separately.
- [ ] Create the final integration commit only after all required evidence is present.
- [ ] Leave the branch unpushed unless the user separately requests publication.
