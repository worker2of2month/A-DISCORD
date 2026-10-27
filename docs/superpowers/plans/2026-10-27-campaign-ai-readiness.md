# Campaign AI readiness implementation plan

> Use superpowers:executing-plans for implementation and a fresh review before completion.

**Goal:** Give the main campaign countries usable, sustainable military AI, beginning with Nodrul's marine recruitment and naval operations against Stelander.

**Architecture:** Reuse native AI roles, country strategy plans and existing country focus sources. Keep country war policies separate from shared recruitment and production. Do not add periodic world scans or artificial victories.

**Tech Stack:** Clausewitz scripts, Python unittest and repository validators, native Hearts of Iron IV campaign checks.

**Specification:** The user requests improvements for the main countries, starting with NOD invasions and marines; compact focus content is permitted. Scope includes NOD, STP/STS/SRP, VAL, RUS and the Vorkerland participants. Existing political routes and scripted war entry remain authoritative.

## Constraints

- Preserve unrelated changes in the shared checkout; no bulk regeneration or commits.
- New campaigns only; existing within-campaign settlement and resource accounting remain intact.
- Edit focus sources and regenerate only their declared output after a check.
- Keep one native template entry per role and registered, nonempty country filters.
- Production minima must leave room for basic weapons at the actual factory count.
- Russian localisation remains UTF-8 with BOM; gameplay scripts remain without BOM.
- Static tests establish source contracts, not successful native invasions.
- Do not launch the game. Native campaign verification is deferred by the user's instruction.

## Review focus

- Marine capacity while existing mountain troops already use the special-forces allowance.
- A marine school reachable before the intervention, including its training time.
- Loss of port, peace, capitulation and a simultaneous northern land war.
- Shared templates staying available when a country temporarily runs short of equipment.
- Additive AI production requests and scripted focus-plan competition.

## Implementation

- [x] Audit shared and country military policies against native documentation and record actionable defects.
- [x] Add failing tests to existing naval/army AI test modules for the confirmed defects.
- [x] Adjust NOD preparation in `focus_trees/NOD/main/focuses.txt`, its AI plan and existing technology where necessary; regenerate `common/national_focus/ADISCORD_NOD_focus.txt` with the focus builder and verify idempotence.
- [x] Correct shared marine role/recruitment and affected major-country production or army policy contracts in their existing engine files.
- [x] Run focused tests, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`; compare against the pre-change baseline.
- [ ] Deferred: record loaded source hashes, cold-start the game and inspect fresh loader logs, marine recruitment and naval orders in a new campaign.
- [x] Review final changes independently and document remaining runtime uncertainty without claiming unobserved success.

## Remaining major-country readiness

- [x] Trace VAL/STP/STS/SRP, RUS and WRK/NAM preparation against their actual war routes, army templates and paid programmes.
- [x] Separate mechanized recruitment demand from carrier stock accumulation in `ADISCORD_technology_doctrine_ai.txt`; verify that a filled reserve stops the factory minimum without removing the mobile role request.
- [x] Cover automatic VAL crisis preparation and preserve its prewar rifle reserve in the existing VAL strategies, triggers and decisions with lifecycle tests.
- [x] Add RUS border-campaign preparation and defer AI declarations during replacement shortages. Add NAM return-war preparation for actual targets, including human owners without AI scores.
- [x] Review source gates and cancellation paths; preserve existing WRK templates and unrelated shared-checkout changes. Native weight tuning and actual movement remain unverified.
- [x] Finish affected tests, shared validation and diff checks without launching the game. The 100 focused AI tests and total-conversion validator pass.
- [x] Resolve the six RUS/NAM regressions: leaf GUI localisation in both languages, science and advisor execution in the test model, LF checkout for generated NAM focuses, and complete terminal-news validation. The 271 RUS/NAM/development tests pass; focus generation is idempotent.

## Supply, aviation and fleet support

- [x] Separate rail replacement from truck technology and bound the train reserve with stock hysteresis and an industry floor; include its factory in simultaneous production-budget checks.
- [x] Add coastal maritime-air demand after its equipment technology, retain fiscal production penalties and verify the aircraft's actual sea missions.
- [x] Share NOD landing readiness between invasion requests and fleet support; prioritize the verified Eastern Antolla crossing only while both ports remain available to their respective sides.
- [x] Verify the physical sea adjacency and strategic region without regenerating map data. Keep native research weights and mission selection.
- [x] Pass 83 focused tests, the total-conversion validator and `git diff --check`; verify UTF-8 without BOM in the four affected gameplay files.
- [ ] Deferred: observe supply delivery, aircraft missions and fleet-supported landings in a fresh campaign when the user permits launching the game.

## Research, construction and factory allocation

- [x] Reuse current campaign preparation for construction, including STP before the civil-war opponent exists and NOD/NAM overseas routes. Separate healthy civilian growth, preparation and wartime construction without changing fiscal recovery.
- [x] Prioritize transport unlocks where supply trucks can be produced, production-efficiency prerequisites during preparation/war, and maritime aircraft for funded regional navies with a current port.
- [x] Stop the coastal dockyard request after port loss. Separate the medium-platform factory reserve from permanent force composition and replacement weights; retain the combined factory-budget check.
- [x] Pass 89 focused tests and the technology/doctrine validator. Verify syntax, definition uniqueness and UTF-8 without BOM in the four edited gameplay files.
- [x] Compare the expanded economy suite against an in-memory reconstruction without this phase's gameplay changes: both runs retain the same 13 assertion failures and one error. The checkout itself is not reverted for the comparison.
- [x] Pass total-conversion validation and the final diff check. Remove one whitespace-only GUI line reported by the shared-checkout diff check without changing its controls.
- [ ] Deferred: measure actual research order, construction completion and equipment delivery in a fresh campaign when launching the game is permitted.

## Economic regression resolution

- [x] Resolve the 13 assertion failures and one error in the economy rebalance suite. Check current law defaults and localisation owners, shared payment helpers, all VAL preview consumers and the live northern-route policy.
- [x] Restrict STP reconstruction settlement to current receipts; verify reward/refund exclusivity, replay, cancellation, port loss and ordinary pending payments. Initialize VAL payroll relief without inferring old results from completed focuses and preserve accumulated relief through repeated initialization.
- [x] Align adjacent reconstruction transaction tests with current prices and verify that an invalid liberation reply cannot consume the next country's offer. Keep focus dependency checks in the actual progression tooltip consumer.
- [x] Pass the 126-test economy/development/VAL group and seven additional reconstruction/staging tests, total-conversion validation and `git diff --check`. The game remains unlaunched.
