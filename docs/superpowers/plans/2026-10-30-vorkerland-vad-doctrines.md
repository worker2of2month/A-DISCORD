# VAD doctrine implementation plan

Use superpowers:executing-plans inline in the authoritative dirty checkout.
No commits, worktree replacement, Computer Use or game launch. Spec:
docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md.

## Contract

- Keep the imperial and joint doctrine routes distinct; the collegial staff
  retains its own programmes. Preserve all four focus IDs and positions.
- First doctrines cost 21 days and apply their exact existing four deltas to
  the existing VAD doctrine aggregate, using authoritative country variables
  and dummy previews. Preserve legitimacy-scaled base doctrine values when
  recomputing; initialise new fields only in guarded administration setup.
  Remove extra experience, command power and manpower padding and sole-use flags.
- Second focuses cost 21 days and unlock real programmes instead of second
  permanent ideas. Remove obsolete ideas, localisation and settlement cleanup
  references through their owning sources. Narrative descriptions explain the
  institutions; prices and results remain in effects/tooltips.
- Imperial guards use an unspent chartered district cohort. A 35-day order
  costs 60 PP, 1300 reserve manpower, 3870 rifles, 32 squad weapons and 90 support
  equipment. The existing district cohort contributes 3000 recruits; it is
  marked spent only at successful delivery. Deliver one Imperial Guard Regiment
  in that held district: four infantry battalions and engineers, 4300 men,
  3870 rifles, 32 squad weapons, 30 support equipment, experience 0.35. The
  remaining 60 support equipment pays the same local recruitment administration
  as ordinary crown recruitment. Apply its existing factory disruption.
- Lock this stable template when the focus unlocks it and when ordering/delivering;
  ordinary native recruitment remains allowed. Refund paid orders before unlocking
  on campaign closure. The focus requires a usable cohort; AI reserves remaining
  crown cohorts once the officer doctrine is selected so it can reach the guards.
- Joint local militias cost 35 PP, 1000 people, 900 rifles and 60 support, take
  21 days and require a held, functioning commandant district without an uprising.
  They lower unrest by 20 on completion, give +10% local recruitable population
  and -5% local factories, and reduce the existing monthly unrest increment by 10
  (10/20/30 becomes 0/10/20). They do not create a field division. No new pulse.
  Existing active uprising responses remain necessary. One militia institution
  per district; loss or withdrawal removes it and permits full-price rebuilding.
- Reuse the country oath receipt, kinds 14 guards and 15 local militia. Add optional
  rifle and squad-weapon deposits to existing refund/handoff/release helpers.
  All fifteen orders share one slot; kind and target checks protect stale callbacks.
  Delivery rechecks the current mandate, campaign, district and unused cohort.
  Cancellation, lost control, subjugation, capitulation and handoff refund once.
  Existing district recruitment history survives loss and reconstruction.
- End doctrine and militia effects with the civil campaign; successors receive
  existing veteran/settlement accounting, not duplicate national doctrine ideas.
  Preserve proper scope, economy invalidation, RU/EN BOM and gameplay no-BOM.

## Tasks

- [x] RED: add focused source-executing tests to test_vorkerland_preparation.py:
  exact aggregate deltas before completion and across legitimacy recalculation;
  guard composition, cohort and fractional prices; both new orders and shared
  receipts; stale targets, delivery, cancellation, successor refunds, template
  locks; militia monthly rates, uprising, control loss, rebuilding and retirement.
- [x] GREEN: update existing country files, source trees, template audit,
  localisation, scripted summary, AI and source inventories.
- [x] Verify targeted/full suite, each changed builder check/apply/check and
  idempotent second apply, validate_tc.py, encoding and diff checks. Update the
  existing guide/spec/manual QA; inspect actual focus textures.
- [x] One fresh read-only final review; one author fix pass for material findings.

## Review focus

Trace every paid currency and the district cohort through delivery, cancellation,
loss, government/campaign changes and recipient handoff. Guards must not provide
unpaid manpower/equipment beyond the explicit existing 3000-person district cohort,
or repeat that cohort after rebuilding. Militia must change the real unrest pulse
and disappear with its administration. Recalculation must preserve both doctrine
deltas and legitimacy scaling; dummy ideas must never be installed. Native spawning,
local modifiers, recruitment, queue UI and campaign balance remain manual checks.
