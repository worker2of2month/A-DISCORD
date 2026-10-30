# Vorkerland collegial general staff implementation plan

> For agentic workers: use superpowers:executing-plans in the authoritative shared checkout.

**Goal:** Make the approved Petrichev-led collegial staff a complete alternative when Worker was not rescued, with distinct wartime programmes, preserved succession and a non-imperial final settlement.

**Spec:** `docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md`, VAD first-month fork.

## Constraints

- No commits, worktree replacement, Computer Use or game launch. Preserve unrelated dirty work.
- New campaigns only; preserve paid operations and actual government across current-campaign handoffs and ordinary save/load.
- Use existing Vorkerland files per engine type and the existing VAD and joint/restoration postwar source trees. Regenerate owned focus outputs with check/apply/check and prove second-apply identity.
- Keep the actual joint cabinet and its news/programmes exclusive to the rescued-Worker course. Worker does not join the collegial staff, including when he survived elsewhere.
- No copied political branch. Common army, logistics, reconstruction and integrations remain shared; the new course has its own mandate, paid programmes and final state.

## Contract

### Government and routes

- `VAD_convene_collegial_staff`,14 days after the seven-day charter, is available only without the rescue outcome. It excludes the imperial and joint entries. Petrichev chairs the staff under a pragmatic military mandate; it neither sets the joint-government flag nor appoints Worker.
- One canonical global government fact records the actually formed collegial staff. Country predicates also require the correct tag/route, living independent government and Petrichev as leader. Do not infer the course merely from the absence of rescue.
- Expose a real choice between collective directives and delegated front commands,14 days each, then `VAD_codify_staff_mandate`,14 days. The mandate rejoins the existing central readiness route as a third alternative. Solar policy accepts the new entrance.
- Hide joint-only and imperial-only political descendants when inappropriate. Use disjoint visibility gates where geometry is shared, and verify them; keep common focus cells and all native card widths valid.
- Historical AI without rescue may retain the imperial default. A player-selected staff mandate must switch AI takeover to one coherent collective-directive plan, never back to the empire or the joint cabinet.

### Paid local programmes

- Collective directives unlock garrison rotation:25PP,500 manpower,60 support equipment,21 days. A held commandant district loses30 unrest and receives+15% local supplies for70 days. Any uprising below100 ends. A lost local institution cancels/refunds a pending rotation; completion does not refund consumed personnel.
- Delegated commands unlock field depot preparation:25PP,100 support equipment,21 days. A held commandant district receives+25% local supplies and+5% controller movement for70 days, with+20 unrest and immediate uprising checks.
- Both use the existing regional target set, country chancery receipt and state in-progress flag, new kinds8/9, existing PP/manpower/support refund and successor transfer. No concurrent order may overwrite a receipt. Recheck exact affordability, target identity, current ownership, institution and route at settlement. Timed local benefits cannot be purchased again while active and are removed on institution loss or administration retirement.

### Mandate and final settlement

- The final wartime staff statute grants one aggregate national spirit with exact dummy previews. Collective direction:+10% planning speed,+3% organisation recovery,-0.05 political power gain. Delegated commands:+3% reinforcement rate,+5% army speed,+3% supply consumption. Variables are initialized in the normal lifecycle and explicitly transferred before VAD is annexed.
- `route_joint` remains the existing shared VAD successor route identifier, not proof of the rescued joint cabinet. The collegial marker, Petrichev's role, programme accounting and aggregate must survive the two-phase VAD-to-WRK handoff and bounded leader reconciliation.
- Block automatic imperial reclamation/coronation and the joint-cabinet coup offer for this course. Continue through shared reconstruction. Add a distinct staff-constitution finale after the Unity Tower: military republic cosmetic identity,+5% stability and+10% command-power gain to the same aggregate, with a real focus delta and a news announcement.
- Audit all callers that currently equate not-joint with imperial, especially settlement, mandate offers, regional war entry, party identity, leader repair and western presentation. Common military reconquest is not renamed to an imperial course for the staff republic.
- Add formation/final news in the existing event file and registry, with dispatch guards and complete RU/EN narrative text. Preserve existing imperial and joint-government story prose.

## Task 1: Lifecycle and government course

- [x] Write source-executing red tests for actual course selection, rescued/dead/escaped Worker, exclusivity, leader reconciliation and two-phase handoff.
- [x] Add the guarded government formation/appointment, mode predicates and explicit transfer of mandate variables; close false imperial/coup routes.
- [x] Verify existing political, recovery and succession tests alongside new course tests.

## Task 2: Focus route and regional programmes

- [x] Add paid-order tests for fractional boundaries, receipt/target isolation, delivered unrest/modifiers, cancellation, rebuilding and handoff.
- [x] Author the distinct focus route, local decisions and shared receipt integration; wire AI takeover and real common-route merges.
- [x] Integrate inspected existing textures, exact previews, localisation and geometry contracts; regenerate and verify.

## Task 3: Postwar finale and complete verification

- [x] Author the separate military-republic finale and source-driven tests proving that tower restoration does not crown Petrichev in this course.
- [x] Add truthful news, party/country identity, settlement presentation and all lifecycle cleanup.
- [x] Run focused suites, full TC validation, encoding checks, idempotence and diff check; inspect source geometry and remove only this task's previews.
- [x] Obtain one fresh read-only final review. Fix important findings with RED/GREEN coverage and rerun affected suites. Record native checks as unverified.

## Review focus

The no-rescue course must remain an actual third mandate after every handoff and delayed callback. It must reach central readiness and a distinct postwar finale without Worker, imperial war unlocks or forced coronation. Paid local programmes must preserve exact resources and target identity through loss, cancellation, annexation and delayed results. Shared reconstruction must not erase the staff aggregate or substitute joint-cabinet narrative. Geometry exceptions require disjoint native gates, not validator-only assumptions.

## Verification status

The six focused suites pass 429 tests. Full TC validation reports zero structural and content findings; its informational vanilla-token inventory remains separate. Both generated trees pass source checks and repeated application preserves SHA-256. Localisation BOM, single-line values and new news description lengths are verified. The source layout was inspected and its temporary preview removed.

One independent read-only review identified a successor aggregate dependency on departed ordinary-focus history. The regression test reproduces the missing modifier and passes for both policies after reapplication was tied to transferred numeric values. No remaining review findings are deferred.

The staff core reaches central readiness in 168 focus days. Native rendering, leader activation and timed callback order remain manual checks. This contract targets new campaigns; unrelated concurrent changes and earlier-version save compatibility are outside its scope.
