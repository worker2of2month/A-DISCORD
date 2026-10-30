# WKR presidential doctrine implementation plan

Use superpowers:executing-plans inline. Preserve the authoritative dirty checkout;
no commits, worktree replacement, Computer Use or game launch.

**Goal:** Make the presidential doctrine support a paid militia army and stop
stacking two permanent national spirits.

**Spec:** docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md,
WKR councils and distinct political doctrines.

## Contract

- Preserve the first doctrine's exact five deltas in the existing council
  aggregate: conscription +0.02, training time -0.15, attack +0.05, organisation
  -0.05, army experience gain -0.10. Its idea becomes a dummy preview. Country
  variables are authoritative; council recalculation must preserve the doctrine.
  The existing civil-war aggregate lifetime applies, including its cleanup.
- The second focus becomes "Свести батальоны в ударные колонны", costs 21 days,
  and unlocks a paid formation instead of another permanent spirit and bonuses.
  It requires the active presidential course, factory battalions, two working
  councils and a free formation queue. Keep existing focus IDs and coordinates.
- WKR_assault_column_programme costs 60 PP, 6000 manpower and 5400 rifles, takes
  21 days, and reserves two working councils. It delivers one full-strength
  six-militia Worker Assault Column in WKR's owned and controlled capital,
  experience 0.30. This trades time and authority for one larger trained unit;
  existing one/two raw three-battalion orders remain available at their prices.
- Use the existing council receipt. Add WKR_council_order_kind: 1 ordinary,
  2 accelerated batch, 3 assault column. WKR_council_order_units continues to
  count reserved councils for refunds and postwar accounting, not spawned units.
  Every decision callback checks its kind; one receipt blocks all three orders.
- The paid composition survives a later leader change and regional peace.
  Start requires the presidential course; delivery requires the same active
  campaign and owned/controlled capital as other council orders. Invalid delivery
  refunds once. Successor handoff returns full payment before template unlock.
  New wars after campaign closure cannot reopen these orders.
- Create and lock the stable six-militia template when the focus unlocks it;
  ordinary recruitment remains allowed. Ensure/lock at payment too. End-of-campaign
  cleanup refunds first, then unlocks both council templates. No support companies,
  hidden equipment gifts, migrations, new periodic scans or extra state markers.
- The category summary distinguishes one assault column from two ordinary units.
  Native costs use amount-first icons and blocked/tooltip variants; narrative
  descriptions do not repeat mechanics. Keep RU/EN BOM and script no-BOM.
- Remove the second obsolete idea, localisation and cleanup references. Remove
  the two consumerless focus flags. Update owned focus sources and regenerate
  WKR, settlement and joint_postwar; do not edit generated trees directly.

## Tasks

- [x] RED: add WKRPresidentialDoctrineTests to the existing preparation suite.
  Cover focus/aggregate deltas, council recalculation, real template price and
  locks, fractional affordability, all three queue kinds, stale callbacks,
  delivery, refunds, leadership/peace, handoff, cleanup, summary and localisation.
- [x] GREEN: update existing effects, triggers, decisions, aggregate, ideas,
  scripted localisation and RU/EN localisation; update focus sources and tooling.
- [x] Verify focused tests; builder --check, --apply, --check and hash-idempotent
  second apply for all three outputs. Run full Vorkerland suite, validate_tc.py
  --limit 300, encoding checks and git -c core.safecrlf=false diff --check.
  Update existing guide, spec and manual QA instructions.
- [x] One fresh read-only review, then one author fix pass for material findings.

## Review focus

Check that kind 3 cannot be paid or settled by the old kind-2 batch despite both
reserving two councils. Check all currencies against the actual six-militia
template and delivery's count, equipment, manpower and experience. Check
ordinary recruitment, refunds before unlocking, own campaign versus later wars,
handoff recipient, postwar veteran counts, leader changes, aggregate preview and
immediate application before has_completed_focus can become true. Review source
and rendered-text constraints without claiming a native game verification.
