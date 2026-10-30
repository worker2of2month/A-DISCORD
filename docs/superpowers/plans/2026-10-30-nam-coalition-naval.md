# NAM Coalition and Naval Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver the approved coalition map, supply network, 40/25/15 starting fleets, viable invasions and expanded NAM naval branch.

**Architecture:** Extend the existing country files and map generators. Keep province geometry, country borders and treaty border belts unchanged. Supply and mobilization support actual formations and fleets rather than adding unused counters.

**Tech Stack:** Clausewitz scripts, UTF-8 localisation, Python builders and unittest, native map data.

**Spec:** `docs/superpowers/specs/2026-10-30-nam-coalition-naval-design.md`

## Global Constraints

- New campaigns only; no save migrations or periodic repair for old versions.
- Preserve unrelated changes in the shared dirty checkout; no commits or staging.
- NAM 40 ships, AZH 25, EFL 15 at campaign start; convoys are separate.
- EFL 10 states, AZH 6; no province bitmap changes or altered national borders.
- Native declarations and landings remain the route into hostilities; no diplomatic UI unlocks or teleporting invasions.
- Country content stays in its existing files; generated content changes through its owner, with check/apply/check.
- ASCII quotation marks and hyphens; RU/EN localisation keeps its BOM; gameplay scripts have none.
- No Computer Use or game launch/restart. Record manual verification as unverified until supplied.

## Review Focus

- A fleet loaded before its technology silently loses ships: task 1 verifies order and equipment unlocks.
- New states can leave claims, capital models or treaty outcomes pointing at only part of a former region: task 2 audits consumers and conserved territory.
- Mobilization can count units without enough recruits, crew, weapons or trains: task 3 computes full templates and replenishment.
- A land-front policy can consume every invasion unit: task 3 tests conditional naval reserves and peace cleanup.
- War-tree replacement can orphan paid naval orders: task 4 tests payment, delivery, cancellation and stale callbacks across tree changes.

## Task 1: Starting fleets

Files: `history/units/{NAM,AZH,EFL}.txt`, their `history/countries/*.txt`, `tools/tests/test_adiscord_naval_programmes.py`.

- [x] Extend `test_starting_fleet_composition_and_technology_before_oob` with NAM `(4,6,22,8)`, AZH `(3,4,13,5)`, EFL `(1,2,9,3)`; observe failure.
- [x] Grant the existing naval and naval-taskforce technology profiles before each OOB.
- [x] Replace the small starting flotillas with those exact existing-model compositions, separate submarines and adequate screens.
- [x] Run the focused fleet tests and verify unique ship names, valid owned coastal bases and no second fleet grant at independence/war.

## Task 2: Connected states and supply

Files: `tools/builders/build_adiscord_new_states.py`, `tools/builders/build_adiscord_vorkerland_theatre.py`, `tools/builders/build_adiscord_strategic_regions.py`, `tools/data/generated_output_owners.json`; generated state/map/localisation outputs and their explicit consumers. Tests: `tools/tests/test_vorkerland_nam_state_balance.py`, `tools/tests/test_build_adiscord_vorkerland_theatre.py`.

- [x] Inventory state references, original totals, existing buildings/VP and all affected generated owners. Reserve currently free IDs 723-729 after checking again at apply time.
- [x] Add conservation and physical-connectivity tests for the approved seven groups, unchanged country borders and states 701/720/721/722.
- [x] Put the reviewed province sets and balanced profiles into the existing state builder. Add bounded `--check-coalition-regions` and `--apply-coalition-regions` entry points; include the same pass in full generation.
- [x] Set EFL/AZH to 12m population each; preserve resources/existing factories; retain central AZH state 69 and give province 16893 unambiguous capital VP priority. Update region references, claims and native model bindings where partition requires it.
- [x] Add EFL hub 10422 and AZH hub 6577, connect AZH 16893-16886-7737, and define connected level-2 capital/front/port routes in the theatre builder. Preserve unmanaged Nudge records.
- [x] Raise working ports 6495/493 to support the approved fleet roles, update building ownership and generated localisation through their owners.
- [x] Run dry checks before each apply, then prove idempotence and run state/theatre/strategic-region validation.

## Task 3: Coalition readiness and invasion AI

Files: existing NAM resource-war effects/triggers/events/AI, EFL/AZH OOB and histories, existing generic AI only where a shared production contract needs correction. Tests: `tools/tests/test_adiscord_nam_focus.py`, `tools/tests/test_adiscord_naval_programmes.py`, relevant AI lifecycle tests.

- [x] Calculate existing land/sea manpower and complete equipment needs. Test the fleet crews, frontline force, two invasion units and reserve against mobilization and stocks.
- [x] Stage mobilization before the earliest possible strike. Aim for 15 EFL and 10 AZH units, adding small 3-4-battalion formations only for the unmet requirement and preserving existing units.
- [x] Provide and sustain convoys, trains, trucks and fuel; all allocated factories together must fit each country's real capacity and leave infantry production.
- [x] Add native `invade NAM`, invasion-unit requests and subtraction of invasion units from land-front needs in country-scoped war policies. Enable only with a viable base, transport capacity and active war; clean up on every settlement.
- [x] Exercise early strike, ordinary start, cancelled threat, lost port, peace and already larger AI armies. Confirm native 1.19.4 field names from installed sources.

## Task 4: Twelve-node NAM naval branch

Files: `focus_trees/NAM/main/focuses.txt`, existing NAM decisions/effects/triggers/dynamic modifiers/dummy ideas, RU/EN localisation and AI plan; generated NAM tree. Tests: `tools/tests/test_adiscord_nam_focus.py`, `tools/tests/test_adiscord_naval_programmes.py`.

- [x] Retain nine current functions, combine coastal battalions/watch into one focus, add reconnaissance, active squadron, ship construction and marine arsenal: total 12 nodes.
- [x] Make escort school and active squadron the exclusive choice; landing school remains available to both. Preserve the direct independence prerequisite and compact positions.
- [x] Implement real paid reconnaissance/ship/marine programs with visible prices and durations, material delivery and cancellation accounting. Use existing aggregates and exact dummy deltas for permanent modifiers.
- [x] Test recipient ownership, fleet/model availability, exact affordability, duplicate callback, war-tree replacement and peace. Descriptions remain narrative; effects use native output and short unlock summaries.
- [x] Update the AI route and preparation timeline; dry-check, apply and recheck the focus builder.

## Task 5: Integrated review and handoff

- [x] Run all four focused suites named in the spec, relevant map/AI validators, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`.
- [x] Request a fresh critic review of the whole package; fix proven findings and rerun the affected checks.
- [x] Update existing technical/playtest guides with actual delivered compositions, routes, prices and limits.
- [ ] Remove only this task's temporary previews after development. Record final source hashes for the user's manual new-campaign verification.

## Task6: Single resource-war deadline and finite diplomacy

Implement the approved 450-day mission and 300-day coalition muster. Replace
pressure-driven scheduling with once-only 45/75/45/60-day delays and the guarded
365-day territorial protocol. Preserve the phase and escrow through timeout,
entry retries and tree replacement; clean every terminal path. Update existing
localisation, synchronized tokens, story callers, AI and validators. Exercise
450-day timeout, repeated purchases, ordering of delays, expired dossier,
stale protocol answers and automatic mobilisation refunds.

## Task 7: Southern war after focus preparation

Use 2165.1.1 as the shared earliest calendar date, then require the actual
preparation milestones of SHL and the selected northern leader. Use reachable
alternatives for ordinary NAM, compromise, revenge and exile. EFL/AZH are
ready after the resource-war settlement because they have no authored trees.
Once both sides are ready, give a shared 56-day warning. Every declaration
uses the same gate, including NAM focuses. Offensive focuses can be completed
during the warning and store a current-campaign order. Without an order, the
automatic attack waits one further 28-day cycle. Keep existing 28-day SHL scheduling,
wake regional participants during preparation, and preserve story-war guards.
Verify 2165-2166 as the ordinary target window; unfinished focuses and long
exile routes may legitimately postpone it.

## Task 8: Postwar border-course design

The approved course is trade or armed deterrence before the southern war.
Two mutually exclusive 35-day focuses follow `NAM_recognition`, replacing
the eight-node branch. Neither route starts a separate northern war.

- `NAM_normalisation` combines the prisoner return (4000 manpower), one oil
  capacity unit and improved EFL/AZH relations. Existing oil-contract events
  already use those relations; preserve that consumer. Do not unlock the
  consortium's exclusive export programme from this unrelated branch.
- `NAM_border_revenge`, retitled "Armed Border", combines 80 artillery and
  20 army experience with access to paid permanent lines: 30 political power,
  100 treasury and 35 days per eligible district. Give this programme its own
  authorization predicate; `NAM_line_programme_open` also enables the temporary
  forward depot and must not grant that second programme implicitly.
- Both courses retain archive event `ADISCORD_nam_archive.6` and its full prose.
  Retire the commission, prisoner, trade-post, bunker, incident and closing
  focus nodes only after moving their selected material functions and updating
  AI plans, prerequisites, localisation consumers and source-count checks.

The route takes 35 days after recognition instead of 112. The common 2165
date and southern readiness gates remain authoritative. Verify paid lines work after victory and standoff, respect completed sites
and construction slots, refund on ownership loss, and retain a useful immediate
reward when all eligible lines were already built before the resource war.

## Task 9: Exile routes and preparation verification

- [x] Verify extended ground preparation against the daily 450-day mission,
  paid one-time diplomacy and actual colonial stocks. Preserve completed
  colonial focuses; do not pay their rewards twice. The eight routes finish
  focuses on days 574-609 and deliveries on days 595-630, before day 675.
- [x] Remove influence deltas and previews from corporate focuses after the
  takeover fixes influence at 100. Retain their material rewards and other scales.
  Company housing explicitly refreshes the economy cache. The mercenary supply
  focus takes 21 days for 3000 recruits, 2500 rifles and 40 support equipment.
- [x] Require an owned, controlled mining site for `NAM_rad_penal_mines`,
  recheck it at delivery, and preserve the route to `NAM_rad_fortress_capital`
  when both original sites are lost.
- [x] Give the corporate military and capital-development branches meaningful
  exclusive alternatives with reachable merges and coherent AI routes.
  Landing contracts remain shared; private navy and mercenaries are exclusive.
  Housing and docks are exclusive and both reach the airport. The AI chooses
  navy and docks. Preserve prior humanist preparation: bypass a fully redundant
  landing contract and preview only the remaining capacity/readiness gain.
- [x] Audit the descriptions of all 369 NAM focuses and 174 decisions in both
  languages. Keep them narrative; prices, delivery, cancellation and single-use
  restrictions belong in native output or the existing effect tooltips.
- [x] Classify propaganda by the actual decision action. Use the yellow prefix
  alone for all 34 paired Russian/English campaign titles, including the STP
  election campaign and official-history campaign.
- [x] Implement the approved trade/deterrence course in Task 8.

## Task 10: Postwar readiness and usable final rewards

- [x] Include the oil exchange and diplomatic prerequisites in the paid
  preparation route. Require the actual southern readiness predicate and every
  offensive prerequisite; the eight routes take 441 focus-days, followed by
  a 42-day order inside the 56-day warning.
- [x] Order both AI plans so diplomacy precedes their final readiness milestone
  and the offensive immediately follows it. Shipyards follow the order.
- [x] Give southern heritage a useful result when victory preserves allied and
  subject governments: open the missing housing or rearmament programme while
  retaining the earlier permanent tradeoffs, prices and settlement lifecycle.
- [x] Show the charter fuel-aid unlock only for an actual eligible ally.
  Without one, explain the future condition; show the unlock on the existing
  acceptance notification after rechecking the recipient.
- [x] Complete focused verification and critic review of this packet.

## Task 11: Exile orders and current reward recipients

- [x] Keep the marine template fixed while subsidised orders remain open,
  including after cancellation. Use the first delivery receipt to close the
  programme and prevent another free expedition on a renewed war. Preserve
  ordinary recruitment and deliver paid orders even to an already owned harbour.
- [x] Settle free-zone construction only against its own pending state receipt.
  Recheck ownership, control and country viability before delivery; preserve
  another island's pending slot and the nonrefundable political-power price.
- [x] Require current federal subject status for humanist district rewards and
  the recipient's ownership and control for construction in its capital.
- [x] Keep the new conditions in effect tooltips and document manual scenarios.
- [x] Complete the affected suites, source checks and critic review.

## Task 12: Compact compromise routes and usable trade

- [x] Merge joint fields into the oil union: two throughput units, the existing
  250 treasury settlement and 50 political power for a first contract. Replace
  its support-counter padding with conditional access to the existing fuel
  contract programme, independent of the optional prewar bureau. Preserve the
  combined narrative and update every permission consumer.
- [x] Merge underground return into officer cadres. Compromise already grants
  the lost-field claims; preserve the officers' material rewards and war support,
  remove the redundant claim focus and reconnect the actual war declaration.
  The defeated tree contains 22 focuses after these two merges.
- [x] Count accommodation readiness after road-south diplomacy,
  alongside the cabinet and harbour milestones. The AI selects the economic
  course after road-south diplomacy and retains defensive readiness.
- [x] Update dependent readiness text, source validators, counts and generated
  outputs. Exercise trade with and without the prewar bureau, the diplomatic
  milestone and the actual AI queue against the 56-day warning.
- [x] Implement the approved economic oil-peace course, exclusive with the
  southern offensive. Open paid exports and retain defence against SHL.

## Task 13: Requirement audit and radical preparation

- [x] Reconcile the older design's deadline, mobilisation cancellation, tree
  inventory and shared reward contract with the current source-backed guide.
- [x] Merge army-of-return preparation into cadet corps and the return plan
  into harbour pilots. Preserve their CP/XP/war support and complete narrative;
  remove the redundant readiness gains and both focus nodes. The declaration
  must still require cadets, landing craft, pilots, fortress, fuel dumps and
  corsair admiralty separately.
- [x] Enumerate every compatible prerequisite closure without optional drills.
  Verify the actual readiness gain reaches the landing threshold on every
  route and that the preparation takes 91 fewer focus-days.
- [x] Update AI, source consumers, localisation, counts and generated output;
  run affected checks and obtain critic review.
- [x] Record requirement-level source evidence and remaining manual/design
  gates in the existing verification manifest without claiming runtime proof.

## Task 14: Bound Svetlogorye in the southern campaign

- [x] Assign a surviving NAM subject to its champion before recording key
  states. Preserve existing leadership and exclude absent countries.
- [x] Reproduce missing side assignment for EFL/AZH/SHL subjection, with and
  without existing hostilities. Verify one war-entry request, objective-side
  accounting and loser-only settlement marking against both winning sides.
- [x] Reconcile the playtest deadline with the 450-day mission and record why
  existing hot-reload logs do not verify the current naval definitions.
- [x] Complete affected suites, total-conversion validation and critic review;
  refresh the verification manifest and retain the manual campaign checks.

## Colonial timing

The 17 compatible colonial focuses take 329 days. Independence follows the
WRK collapse event and its response, roughly on days 352-396. The approved
choice preserves this interval for colonial decisions; do not lengthen the
mandatory chains or add continuous focuses. Paid operations must settle
through the normal collapse lifecycle.

The ordering window ends at the actual WRK split, roughly days 350-394.
Fourteen-day orders fit after day 329; longer orders may be cancelled by an
early split. Concession settlement rechecks the same operating predicate as
payment and refunds its 200 treasury once if the metropole has disappeared.
