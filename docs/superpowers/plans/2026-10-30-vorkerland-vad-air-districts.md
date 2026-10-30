# VAD district air infrastructure implementation plan

Use superpowers:executing-plans inline. Preserve the shared dirty checkout. No commits, worktree replacement, Computer Use or game launch.

**Goal:** Replace VAD's cloned air staff and temporary combat bonuses with a district choice between forward airfields and stationary air defence.

**Spec:** docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md, VAD's district administration and common focus design contract. Values below are implementation choices under the ongoing rework.

**Architecture:** Existing VAD district targets, paid chancery receipt and native buildings. No new currency, polling, resource receipt, state history edit or aircraft archetype. The completed infrastructure remains on the map after war settlement; only pending work is refundable.

## Contract

Retire VAD_restore_the_restoration_air_arm and its sole-use completion marker. Rewrite the exclusive pair VAD_task_the_guards_for_close_support / VAD_cover_the_district_capitals as forward airfields / district air defence, directly following VAD_standardize_district_logistics. Cost 21 days each; cells (57,10)/(59,10). Both require active independent VAD administration and an actual administered district, and are available under imperial, joint and collegial mandates. They remain optional to military readiness.

- VAD_forward_airfield_programme: shared state targets, 40 PP, 120 support equipment, 500 manpower; 28 days; receipt kind 12. Creates two airbase levels in a state currently without an airbase, with room for two levels.
- VAD_district_air_defence_programme: 45 PP, 100 support equipment, 800 manpower; 35 days; receipt kind 13. Creates two state AA levels where room remains for both; may be repeated only while that capacity remains.
- Both require current ownership/control, an actual charter or commandant administration, no district uprising, and a non-demilitarized state. Check native free_building_slots with size > 1 at payment and delivery. The airfield also rechecks air_base < 1. Payment, wrong-kind/target guards, cancellation, subjugation/capitulation and successor refund use VAD_oath_pp/manpower/support/kind/state and VAD_oath_in_progress. No new completion marker.
- Existing charter and commandant programmes share the same slot, so another district cannot overwrite the receipt. Conditions lost while paid work is running return every currency, build nothing and release the target. Native buildings already completed survive loss of the administration and ordinary war cleanup; they are not timed modifiers.
- Retire both free activation decisions and old air ideas, their sole-use localisation and other verified consumers. Focus rewards stay compact programme unlocks with a material result summary. Use action-specific inspected art and matching shine masks.
- Extend GetVADOathProject for kinds 10/11/12/13 and fix the two staff summaries that read nonexistent VAD_oath_target instead of authoritative VAD_oath_state. No new UI state or polling. Every occupied receipt must display an active programme, not the idle message.
- RU/EN BOM; scripts no BOM; ASCII punctuation; tab-indented authored Clausewitz blocks. Use native building/count documentation rather than invented parameters. Runtime verification remains manual.

## Tasks

- [x] Add failing source-executing payment, building-capacity, target/cancellation, native callback, completed-infrastructure and pending-summary tests. Extend the test interpreter only for documented demilitarization and exact free-slot comparisons.
- [x] Implement the district programmes, rewrite focuses/AI/localisation/art and remove retired consumers. Preserve current campaign state and existing handoff order.
- [x] Update explicit focus manifests and geometry; generator check/apply/check and idempotence, inspect source layout/art and remove owned previews.
- [x] Run source suites, full TC, BOM/diff checks and one fresh read-only review. Fix material findings with RED/GREEN; keep the full goal active until the wider design is complete.

## Review focus

A construction order must not pay into a lost, demilitarized, rebellious or full district. Native construction performed while the order runs must be observed again at delivery. Completed buildings must remain ordinary map assets through peace and country handoff. Pending paid work must return all resources exactly once and cannot be consumed by another target or programme. All three VAD mandates need actual eligible administration and an available focus route; the country summary must name every occupied receipt kind and the real state pointer.
