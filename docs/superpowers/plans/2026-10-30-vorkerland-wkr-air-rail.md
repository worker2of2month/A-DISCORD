# WKR aviation workshops and armoured trains implementation plan

Use superpowers:executing-plans inline. No commits, worktree replacement, Computer Use or game launch. Preserve unrelated shared work.

**Goal:** Give WKR an aviation and railway choice tied to its actual councils, replacing the duplicate air staff and free timed bonuses.

**Spec:** docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md. The following values are implementation choices under the accepted rework.

**Architecture:** Existing WKR railway receipt, council registry and callbacks. A local aviation workshop persists with its council; armoured trains are ordinary stockpile equipment. No extra queue, polling or country currency. Existing initial air command and production sustainment still support WKR's starting air force and southern campaign.

## Contract

- Retire WKR_form_the_republican_air_staff, both old air activation decisions and their two timed ideas/sole-use flags. Rewrite WKR_commit_shopfloor_squadrons and WKR_screen_the_interchange_sky as council aviation workshops versus armoured supply trains. Both cost 21 days and attach to WKR_put_railways_under_councils at (17,9)/(19,9), requiring a currently eligible council site. Available to both political mandates and between regional wars; optional for readiness.
- WKR_airfield_workshop_programme: targeted to existing railway council states. 40 PP, 80 support equipment, 400 manpower, 21 days. Needs an actual council, fully owned/controlled supply hub and airbase, with no workshop already present. Adds WKR_airfield_workshop: state_repair_speed_air_base_factor = 1.00 and local_factories = -0.05. Native modifier preview is in the decision. Recheck target on delivery; completed workshop is removed with its council or at campaign cleanup, and can be rebuilt at full price.
- WKR_armoured_train_programme: national procurement, 35 PP, 120 support equipment, 600 manpower, 35 days, produces 8 armored_train_equipment_1. Requires an actual railway council in a fully held hub with an arms factory, rechecked at delivery. No state-target UI for a stockpile-only result. Completed equipment remains after war/handoff.
- Both use WKR_railway_order_pp/manpower/support/trains/state and WKR_railway_in_progress; add only WKR_railway_order_kind: 1 existing council, 2 workshop, 3 national trains. Set kind on every new payment and clear on every settlement. No legacy inference. National orders have no state pointer/flag. Base council and new workshop callbacks must check their own kind and exact target, so neither can consume the other's receipt. National callbacks check kind 3 only. Every currency is charged once, and cancellation/refund/handoff preserve full payment through existing callbacks.
- The existing slot blocks every other railway programme, including council creation. Lost target, council, factory/airbase, independence, capitulation or campaign end refund unfinished work. Leadership change does not cancel work. Summary GetWKRRailwayOrder shows the actual kind, cost and target where relevant. Update its ordinary council summary/slot wording to include all programmes.
- Keep local modifier cleanup guarded; invalidate the economy cache after adding/removing the workshop. No changes to the initial air-force bootstrap or production minima.
- Inspect action-specific native artwork and bind both normal and shine sprites. RU/EN BOM, gameplay no BOM, ASCII punctuation and native tab-indented scripts.

## Tasks

- [x] RED then GREEN source tests: exact three-currency prices, mutually shared queue including existing council, wrong kind/target/stale callback, both mandates, local delivery and cleanup/rebuild, national delivery and equipment definition, all native loss/handoff callbacks, summaries and modifier previews.
- [x] Implement programmes and typed existing receipt; rewrite focuses, AI, localisation and art, removing verified retired consumers. Update explicit validator manifests and reward expansion without weakening existing checks.
- [x] Generator check/apply/check and repeated apply idempotence; inspect source geometry and textures, then remove owned previews. Run full source suite, TC and BOM/diff checks.
- [x] One fresh read-only final reviewer, one author fix pass for material findings with RED/GREEN. Keep broader goal active.

## Review focus

An old council callback must not finish or refund a workshop or national train order. A national receipt has no target flag, so a territorial callback must not accidentally consume it. Local workshop benefits require the actual council, airbase and complete control; cleanup and reconstruction must preserve exact accounting. A stockpile reward must not be presented as a local map consequence. Both political paths and the initial air-force programme must remain reachable and funded; native repaired-airbase effects and armoured-train roles need source-backed fields. Native UI, timing and balance remain manual.
