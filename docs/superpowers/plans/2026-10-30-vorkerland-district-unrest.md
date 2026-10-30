# Vorkerland district unrest implementation plan

> **For agentic workers:** Use superpowers:executing-plans in the existing shared checkout.

**Goal:** Make commandant rule carry a local, manageable revolt risk with paid intervention or withdrawal.

**Architecture:** State unrest belongs to the existing oath state array and monthly VAD callback. A third operation kind reuses the existing country receipt and state escrow. The current control-loss and peace paths settle it and remove local effects.

**Tech Stack:** Clausewitz scripts, BOM RU/EN localisation, Python source-executing tests.

**Spec:** `docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md`, VAD district mechanics.

## Global constraints

- Preserve unrelated dirty files; no commits or worktree replacement.
- New campaigns only. Ordinary save/load and living-country handoffs preserve state.
- Keep country content in existing files. No new country tags, world scans or periodic hooks.
- No Computer Use or game launch; native rendering and timing remain manual.
- Source focuses own generated output; check/apply/check and second-apply identity.
- Gameplay UTF-8 without BOM, RU/EN localisation with BOM; ASCII punctuation.

## Review focus

- A paid response must survive a monthly rise and still settle the same district.
- An old target callback must not settle another target's receipt.
- Control loss, subject status, capitulation and peace must close effects and refunds exactly once.
- Withdrawal must not refund installed administrations or erase another district's paid operation.
- Revolt must disable real local benefits and have visible material consequences, without restarting after cleanup.

## Task 1: State pressure and operation accounting

**Files:** Existing Vorkerland effects, triggers, dynamic modifiers, decisions and `tools/tests/test_vorkerland_preparation.py`.

**Interfaces:** `VAD_district_unrest` is state-scoped, starts at 20 and clamps 0-100. `VAD_monthly_district_unrest` iterates the oath array only while administration is active. `VAD_begin_district_order` / `VAD_finish_district_order` use `VAD_oath_kind = 3`, 25 PP and 500 manpower for 14 days. `VAD_withdraw_district_commandant` removes the local institution without a refund. Shared state cleanup serves withdrawal, control loss and retirement.

- [x] Add failing tests for monthly rates, threshold effects, paid prevention/suppression, boundaries, shared slots, duplicate callbacks, loss/handoff and withdrawal.
- [x] Implement unrest, existing receipt integration and complete cleanup.
- [x] Run the new district tests and existing VAD accounting tests; expect all green.

## Task 2: Focus, notification, UI and verification

**Files:** Existing VAD focus source, Vorkerland on_actions/events/scripted localisation/RU/EN text, event registry, focus contracts and guides.

**Interfaces:** Existing monthly VAD hook calls the bounded update. A new revolt reports through `ADISCORD_vorkerland_claimant.15`; the event only acknowledges and never reapplies the consequence. The commandant focus unlocks both responses. Decision visibility uses local institution context, shortages and busy slots remain visible as conditions.

- [x] Wire the monthly hook, one notification per pulse and native response unlocks.
- [x] Add narrative descriptions, exact local risk/result/cost text and native blocked costs.
- [x] Regenerate VAD with check/apply/check and prove idempotence; verify encoding and graph contracts.
- [x] Run `python -B -X utf8 -m unittest tools.tests.test_vorkerland_preparation tools.tests.test_adiscord_vorkerland_civil_war_focus tools.tests.test_vorkerland_campaign_state -q`, full `tools/validate_tc.py --limit 300`, and `git -c core.safecrlf=false diff --check`.
- [x] Review this scope with a fresh reviewer. Preserve unrelated concurrent map validation findings.

## Task 3: Paid district recruitment

**Interfaces:** Crown levy (kind 4): 35 PP, 60 support, 21 days, 3000 recruits and -10% district factories until administration retirement. Joint reserve (kind 5): 30 PP, 80 support, 21 days, 4500 recruits and +30 unrest. State `VAD_district_recruited` records actual delivered recruits and survives institution rebuilding. `VAD_oath_support` extends the same refundable receipt. Both programmes use the existing category and regional target list.

- [x] Add source-executing tests for exact costs, shared slots, delivery, quotas, unrest, refunds and handoffs.
- [x] Implement programmes, shared settlement and local effect cleanup; replace two focus gifts with unlocks.
- [x] Update both localisation sections, inspect and bind suitable existing focus textures, regenerate and verify idempotence.
- [x] Run focused tests, full validator, encoding/diff checks and fresh final review.

## Task 4: One coherent prewar tree

**Scope:** Merge the two WRK preparation roots into `WRK_measure_confederation_fault_lines` (21 days, combined 75 PP and both sets of unlocks). Connect budget, production, camps, military readiness, political continuity and tower protection in one layout. Keep existing exclusive choices, deliveries and country handoff. Industry and army camp programmes follow their respective preparation choices. Remove the redundant root from AI plans and source contracts; no old-save migration.

- [x] Add a failing single-entry/reachability test.
- [x] Consolidate the source graph, AI plans, manifests and timeline expectations.
- [x] Regenerate prewar output, inspect layout and verify all affected checks.

## Task 5: VAD and TVA focus layout

**Scope:** Use the native 96-pixel horizontal pitch and 165-pixel card width. Keep at least two cells between same-row cards. Group political courses, field programmes and supporting branches; place common operations beneath their convergences. Preserve costs, rewards, prerequisite logic and AI chronology. Use source-rendered previews for geometry; native UI remains manual.

- [x] Add a failing card-clearance test and arrange both source trees.
- [x] Update explicit geometry contracts without relaxing overlap checks; inspect source previews.
- [x] Regenerate, prove idempotence and run focused/full checks.

## Task 6: Joint-government news and distinctive focuses

**Scope:** The joint Worker-Petrichev government only. Attach news to actual formation, survival or the authored coup/execution outcome. Add political-course-specific focus content with real programmes and choices in the existing files. Preserve optional narrative reading and the surviving joint-government route.

- [x] Audit the joint-government story, focus routes and existing programme consumers.
- [x] Implement source-driven outcome tests, news and distinctive focus rewards.
- [x] Verify localisation, native picture dimensions, lifecycle cleanup, generation and full checks.

**Joint programme contract:** Two exclusive 14-day focuses after the dual chamber. Congress: 35 PP and 500 personnel, 14 days, -20 unrest in every held commandant district and ends uprisings that fall below 100. Operations: 30 PP and 100 support, 14 days, 35 days of +5% planning speed/+5% organisation recovery and +10 district unrest. Both reserve the existing chancery receipt (kinds 6/7), recheck the joint cabinet, and refund through the existing handoff. Operations additionally require an ongoing campaign war. Only the congress enters the default AI programme plan. Formation, programme choice and postwar confirmation receive news; the existing execution news stays tied to the actual imperial transition.

## Verification status

- Four-module scenario suite: 380 tests pass, including programme accounting, joint news/default succession and native-width card spacing.
- Additional story, decision, builder and interface suite: 54 pass; one interface registry check is blocked by absent existing STP portrait-source PNGs. The registry pattern is unchanged from HEAD.
- Full TC validation: all Vorkerland and shared syntax/localisation/event sections pass. One unrelated lore trade-region geography discrepancy remains in ongoing map work.
- Focus generation is idempotent; gameplay scripts have no BOM, RU/EN localisation retains BOM, and `git diff --check` passes.
- Fresh read-only review completed. The player-visible technical-flag finding was fixed with a failing-then-passing source regression; the full 380-test suite remains green.
- Native UI rendering, loader acceptance, unattended timing, news fanout and campaign balance require manual game verification. Temporary geometry previews are removed after inspection. No commits or worktree replacement.
