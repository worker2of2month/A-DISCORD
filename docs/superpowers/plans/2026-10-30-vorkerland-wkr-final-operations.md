# WKR final operations implementation plan

Use superpowers:executing-plans inline. Preserve the authoritative shared checkout; no commits, worktree replacement or Computer Use.

**Goal:** Replace the late-war free bonuses with a timed offensive preparation and a local defensive programme tied to railway councils.

**Spec:** docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md. Exact prices below are implementation choices under its paid-programme and distinct-route requirements.

**Architecture:** Extend the existing railway receipt with kinds 4/5. Existing loss, annexation and handoff callbacks settle every paid currency; local defences use the existing council registry. No new polling, global scan, currency or queue.

## Contract

- Retire WKR_the_last_levy and its sole consumers. Retain the exclusive WKR_throw_the_reserves_forward / WKR_dig_in_along_the_interchange pair, directly after WKR_republic_fights_as_one at (21,13)/(23,13), 21 days each. Allow central preparation and showdown for both mandates, requiring a real council site. They are optional after readiness.
- WKR_breakthrough_programme: national order, kind 4, 40 PP, 150 support equipment and 600 manpower, 14 days. Requires the offensive focus, a fully held council hub and actual war against another central claimant. Completion grants the existing reserves_forward idea for 35 days (+8% attack, +10% breakthrough, -6% defence, +5% attrition). No repeated order while it is active. Ending that campaign cancels the idea; an unrelated external war does not preserve it. No state pointer or flag for this national operation.
- WKR_interchange_defence_programme: targeted order, kind 5, 35 PP, 100 support equipment and 800 manpower, 21 days. Requires the defensive focus and a fully held council hub without completed defences. Adds WKR_prepared_interchange: +25% local supplies, -10% enemy speed, +10% enemy attrition, -10% local factories. It persists with the council, disabled if full control is lost and removed on council ownership/control loss or campaign cleanup. Rebuilding requires full payment. Native modifier preview equals delivery; invalidate the economy cache on add/remove.
- Both use WKR_railway_order_pp/manpower/support/trains/state/kind. Trains receipt is 0. Existing kinds 1/2/3 and new kinds 4/5 block each other. All finish/cancel callbacks check kind; local callbacks also require exact state and paid marker. Loss of context refunds each currency once through existing paths. Government change preserves pending work.
- Replace both free activation decisions; retire the old interchange_line idea and sole focus flags. Preserve reserves_forward as the paid operation result, with updated narrative and actual-war cancellation. No additional reward padding.
- GetWKRRailwayOrder reports the actual kind and target only for local work. Focus unlock summaries, custom costs and blocked/tooltip variants use RU/EN BOM localisation. Inspect and bind actual action-specific native icons, including shines. No generated output edits.

## Tasks

- [x] RED then GREEN source tests: reachable timing and both mandates; exact fractional prices; all five queue kinds, wrong target/kind callbacks; paid delivery and matching previews; actual claimant war and external-war rejection; state loss/rebuild; native cancellation and handoff; order summaries.
- [x] Implement existing country sources, remove retired consumers and update explicit validation manifests and AI. Extend the existing guide and regenerate the WKR tree through check/apply/check with a repeated idempotent apply.
- [x] Inspect source layout and textures, delete owned previews, run the full Vorkerland source suite, TC, encoding and diff checks.
- [x] One fresh read-only final review; one author fix pass for material findings with RED/GREEN. Keep the broad goal active.

## Review focus

Verify that the focus can prepare for the central war without starting its temporary bonus early. An unrelated war must neither complete an offensive preparation nor retain its bonus. Old railway callbacks must not consume new receipts, and new callbacks must not consume kinds 1/2/3. Local defences must have a genuine state consequence and no stale occupation benefit. Peace, annexation and reunification must refund the current receipt once, with no double delivery. Check both political mandates and native modifier scopes; runtime AI timing, local attrition and UI remain manual.
