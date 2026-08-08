# A-Discord Vorkerland Map, Forces, and Military AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Vorkerland civil war enough maneuver space, manpower, supply, organization, equipment, and phase-aware AI to remain dynamic for two to three years without AFK fronts, deterministic WKR victory, unused aircraft, or infinite militia.

**Architecture:** A machine-readable theater and template audit becomes the balance source of truth. Map/state changes are made through existing builders and manifests, then regenerated. Force changes are calculated from audited template cost, stockpile, frontage, and supply. Military AI follows the civil-war phase flags created by the core plan and receives bounded initiative/militia interventions rather than polling or outcome-forcing cheats.

**Tech Stack:** HOI4 map/state/OOB/AI/decision scripting, Python map parsers/generators/validators, observer-campaign CSV evidence.

## Global Constraints

- This plan starts only after the repository/ASCII plan and civil-war phase-controller commit are complete.
- `WKR`, `VAD`, and `TVA` are wartime claimants; `WRK` appears only after reunification.
- Modify generated state, building, strategic-region, and OOB output only through registered owners.
- Preserve protected existing regional contracts: ROM/DVA, TRU/ZTA, VLA/EBA, ZAO/WPA/WPS/PSD/PWR, VAL, and Ivanland interventions remain independent systems.
- Line units must be able to move and fight. Intentionally weak militia alone may start at 25-40% equipment and low experience.
- A military intervention may improve planning, supply, organization recovery, or bounded defensive density; it may not assign a winner, annex territory, force white peace, or spawn unlimited units.
- Aircraft validation must prove active employment, not only equipment creation.
- Every map or AI acceptance claim requires a full HOI4 restart.

---

## Task 1: Create the Theater Balance Manifest and Baseline Report

**Files:**
- Create: `tools/data/vorkerland_theater_balance.json`
- Create: `tools/validators/validate_adiscord_vorkerland_theater_balance.py`
- Create: `tools/tests/test_validate_adiscord_vorkerland_theater_balance.py`
- Create: `docs/audits/2026-08-08-vorkerland-balance-baseline.md`
- Update: `tools/validators/validate_tc.py`

- [ ] Write failing tests requiring rows for WKR, VAD, TVA, every central minor, ZAO/WPA/WPS/PSD/PWR, VLA/EBA, ROM/DVA, SOL/SRA, TRU/ZTA, and VAL.
- [ ] Require each row to list home states, capital, population, VP total, front states, physical border-province count, supply hubs, rail access, air bases, starting divisions, full manpower/equipment cost, stockpile, and intended wars.
- [ ] Implement independent extraction from state history, map adjacency, supply nodes/railways, OOBs, and collapse setup effects; compare extracted facts to the manifest.
- [ ] Add objective warnings for a front with fewer than three land border provinces, a participant with fewer than 1.2 usable divisions per front state, missing rail-connected supply, or a stockpile below one full audited line-division replacement.
- [ ] Run `python -B -m unittest tools.tests.test_validate_adiscord_vorkerland_theater_balance -v` and preserve RED findings as the baseline report.
- [ ] Commit the audit/report before modifying balance as `test: inventory Vorkerland theater balance`.

## Task 2: Define Connected State Splits for Maneuver

**Files:**
- Update: `tools/builders/build_adiscord_new_states.py`
- Update: `tools/lib/vorkerland_collapse_manifest.py`
- Update: `tools/tests/test_vorkerland_nam_state_balance.py`
- Update: `tools/tests/test_validate_adiscord_vorkerland_theater_balance.py`
- Generate: `history/states/331-*.txt` through `history/states/340-*.txt` as applicable
- Generate: affected source `history/states/*.txt`

- [ ] Reserve IDs 331-340 only for maneuver splits, one residual connected state per selected source; do not collide with outer-state generation beginning at 341.
- [ ] Add failing graph tests requiring connected source/residual province sets, preserved union, valid capital/VP province, at least two physical state adjacencies per new state, and at least three usable border provinces on the affected war front.
- [ ] Apply the deterministic split set: central single-state bottlenecks 27 and 35; northern contestants 72, 195, and 196; regional single-state fronts 73, 74, 76, 80, and 199. A source may consume its reserved ID only if its connected residual satisfies every graph contract; otherwise record the rejected split and leave that ID unused rather than creating an island or one-province trap.
- [ ] Require at least six of the ten reserved splits to pass. If fewer pass, redesign explicit province partitions before proceeding; do not waive connectivity/frontage contracts merely to hit a file-count target.
- [ ] Store explicit province tuples and state profiles in the builder; do not implement runtime ownership surgery for these splits.
- [ ] Preserve each source's total manpower, resources, buildings, VPs, and provinces across source plus residual before the later balance adjustments.
- [ ] Add every accepted residual ID to the same package as its source in `tools/data/adiscord_vorkerland_integration_packages.json`, run the recovery builder, and verify postwar integration coverage.
- [ ] Run the builder with `--apply`, rerun with `--check`, then rerun to prove byte-idempotence.
- [ ] Run state connectivity, theater balance, strategic-region, building, and total-conversion validators.
- [ ] Commit generated state changes as `feat: add Vorkerland maneuver states`.

## Task 3: Rebalance Population and Settlement Victory Points

**Files:**
- Update: `tools/builders/build_adiscord_new_states.py`
- Update: `tools/data/vorkerland_theater_balance.json`
- Update: `tools/tests/test_vorkerland_nam_state_balance.py`
- Generate: `localisation/russian/state_names_l_russian.yml`
- Generate: `localisation/russian/victory_points_l_russian.yml`
- Create: `localisation/english/ADISCORD_vorkerland_recovery_map_l_english.yml` through the builder
- Generate: affected `history/states/*.txt`

- [ ] Write failing tests requiring every active theater participant to have recruitable population sufficient for its starting OOB plus 50% reinforcement at its starting recruitable-population modifiers.
- [ ] Require central claimants to remain within 15% of one another in manpower-per-front-state after proxy/home-package differences are included; regional wars use their own paired ratios and must not be normalized globally.
- [ ] Require every state with at least 100,000 population to have an ordinary named settlement VP of at least 1 unless the state is explicitly contaminated/uninhabitable; every theater capital remains the highest local VP.
- [ ] Add VP value outside capitals so no theater places more than 55% of its surrender value in one state.
- [ ] Adjust population in explicit builder profiles, preserving believable regional totals and avoiding industrial changes in this task.
- [ ] Generate Russian and English VP/state names from the same mapping; keep Russian output BOM.
- [ ] Run builder apply/check/idempotence and focused graph/population/VP tests.
- [ ] Commit as `balance: improve Vorkerland population and victory points`.

## Task 4: Repair Supply, Rail, Infrastructure, Air Bases, and Strategic Regions

**Files:**
- Update: `tools/builders/build_adiscord_map_buildings.py`
- Update: `tools/builders/build_adiscord_strategic_regions.py`
- Update: `map/supply_nodes.txt`
- Update: `map/railways.txt`
- Generate: `map/buildings.txt`
- Generate: affected `map/strategicregions/*.txt`
- Update: `tools/tests/test_vorkerland_nam_state_balance.py`
- Update: `tools/tests/test_validate_adiscord_vorkerland_theater_balance.py`

- [ ] Write failing tests requiring each claimant capital and each independent regional theater to reach a supply hub through owned/controlled starting rail, with no route crossing an initial enemy state.
- [ ] Require each central claimant to have a usable air base and every intended air region to contain at least one reachable front state.
- [ ] Require rail endpoints, hub provinces, airports, and state IDs to survive the maneuver splits.
- [ ] Add only the minimum hubs/rails/infrastructure required by the failed contracts; prefer connecting existing hubs over creating one per minor.
- [ ] Rebuild buildings and strategic regions through their owners, then prove check-mode and idempotence.
- [ ] Run map, state, building, strategic-region, collapse, and total-conversion validators.
- [ ] Commit as `balance: repair Vorkerland front logistics`.

## Task 5: Enforce Template Organization and Equipment Contracts

**Files:**
- Update: `tools/data/division_template_audit.json`
- Update: central and regional `history/units/*.txt`
- Update: `common/ai_templates/ADISCORD_land_templates.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_force_design_effects.txt`
- Update: `tools/tests/test_validate_adiscord_force_designs.py`
- Update: `tools/tests/test_validate_adiscord_division_templates.py`

- [ ] Add failing role floors: line division organization at least 30; territorial/reservist organization at least 25; emergency militia organization at least 20 with no offensive-role assignment.
- [ ] Require line formations to start with at least 70% equipment, reservists at least 55%, and deliberate meat militia at 25-40%; require line experience at least 0.15 and emergency militia at most 0.10.
- [ ] Require every battalion/support equipment archetype to exist in starting technology/variant/stockpile paths.
- [ ] Repair composition and starting factors before increasing division counts. Keep template definitions and all OOB references atomic.
- [ ] Ensure the AI replacement path upgrades militia toward a valid line/territorial template rather than duplicating obsolete names.
- [ ] Run template, force-design, technology-contract, and collapse tests.
- [ ] Commit as `balance: make civil war templates combat capable`.

## Task 6: Recalculate OOB Counts and Starting Stockpiles

**Files:**
- Update: `tools/data/vorkerland_theater_balance.json`
- Update: all active Vorkerland `history/units/*.txt` listed by the manifest
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt` setup stockpiles only
- Update: `tools/tests/test_validate_adiscord_vorkerland_theater_balance.py`

- [ ] Write failing tests requiring 1.2-2.2 combat-capable starting divisions per initial front state, with a theater-specific ceiling based on supply and population.
- [ ] Require initial stockpile plus fielded equipment to cover audited OOB deployment and at least 15% replacement; deliberately weak militia equipment remains excluded from the line-unit reserve calculation.
- [ ] Recalculate WKR, VAD, TVA, proxy, central-minor, and regional OOBs from the audited costs rather than preserving current raw unit counts.
- [ ] Keep central claimant total deployed combat power within 20% after home proxies and starting industry are included; do not equalize their political or geographic advantages.
- [ ] Confirm every OOB location is an owned, controlled, supplied province at collapse.
- [ ] Run theater, template, force-design, and collapse validators.
- [ ] Commit as `balance: recalculate Vorkerland orders of battle`.

## Task 7: Replace Weekly Air Repair with Event-Driven Setup

**Files:**
- Delete if empty: `common/on_actions/02_ADISCORD_vorkerland_force_design_on_actions.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_force_design_effects.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Update: `common/ai_strategy/ADISCORD_vorkerland_force_design_ai.txt`
- Update: `common/units/ADISCORD_air_units.txt`
- Update: `common/units/equipment/ADISCORD_air_equipment.txt`
- Update: `tools/data/adiscord_starting_technology_profiles.json`
- Update: `tools/builders/build_adiscord_technology_system.py`
- Generate: `common/scripted_effects/ADISCORD_technology_baseline_effects.txt`
- Rename/Update: `history/units/WRK_vorkerland_collapse_air.txt` to `history/units/WKR_vorkerland_collapse_air.txt`
- Update: `history/units/VAD_vorkerland_collapse_air.txt`, `history/units/TVA_vorkerland_collapse_air.txt`
- Test: `tools/tests/test_validate_adiscord_force_designs.py`

- [ ] Replace existing tests that accept weekly deploy/redeploy calls with a failing prohibition on weekly air spawning, bootstrap, or forced redeployment.
- [ ] Test the full chain for each claimant: starting tech -> valid variant -> equipment stockpile -> owned air-base capacity -> fuel -> air wing -> reachable strategic region -> fighter/CAS mission strategy.
- [ ] Rename the wartime starting-technology profile from WRK to WKR and ensure WKR/VAD/TVA receive the exact aircraft technologies required by their generated variants; change the profile data/generator and regenerate instead of hand-editing the baseline effect.
- [ ] Change all force-design allowed blocks from WRK to WKR for wartime use; postwar WRK receives only normal peacetime strategy.
- [ ] Invoke one-time setup from collapse initialization, claimant formation, relevant reload migration, and explicit air-focus completion only.
- [ ] Keep a bounded idempotent flag so setup cannot duplicate wings.
- [ ] Remove the weekly on_action once no other contract uses it.
- [ ] Run force-design, technology, on_action-polling, and collapse validators.
- [ ] Commit as `fix: deploy and employ claimant aircraft without weekly repair`.

## Task 8: Implement Phase-Specific Military AI

**Files:**
- Update: `common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt`
- Update: `common/ai_strategy/ADISCORD_vorkerland_force_design_ai.txt`
- Update: regional AI files including `common/ai_strategy/ADISCORD_vorkerland_rom_tru_ai.txt`
- Update: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`
- Update: `tools/tests/test_validate_adiscord_force_designs.py`

- [ ] Add failing tests for mutually exclusive consolidation, preparation, offensive, recovery, and final-showdown strategy blocks keyed to authoritative phase flags.
- [ ] In consolidation, allow exactly one assigned target and prohibit parallel claimant wars.
- [ ] In preparation, request front coverage, avoid attacks at low organization/supply, stockpile equipment, and keep aircraft assigned.
- [ ] In offensive, prioritize an explicit enemy and meaningful VPs with `careful` execution by default; remove the hard-coded anti-VAD preference and any WRK-specific wartime block.
- [ ] In recovery, pause offensive priority after severe loss/organization conditions while retaining defensive coverage.
- [ ] In final showdown, activate only for surviving WKR/VAD/TVA claimants and one live-border opponent at a time.
- [ ] Add parallel phase blocks for northern and paired regional wars so they do not remain on generic peacetime AI.
- [ ] Run collapse/force-design validators and grep for stale `allowed = { ... tag = WRK ... }` wartime strategies.
- [ ] Commit as `feat: make Vorkerland military AI phase aware`.

## Task 9: Add the 90-Day Initiative Mission and Anti-Stall Escalation

**Files:**
- Update: `common/decisions/ADISCORD_vorkerland_collapse_decisions.txt`
- Update: `common/decisions/categories/ADISCORD_vorkerland_collapse_categories.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Update: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Update: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`
- Update: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`

- [ ] Write failing tests for one visible 90-day mission per active war participant, activated by war-launch events rather than monthly polling.
- [ ] Define meaningful progress as capture of a listed state or VP from the current assigned enemy; use state-control change hooks/events to refresh the mission.
- [ ] On first expiry, grant a bounded 30-day planning/supply/organization-recovery modifier and reset the mission.
- [ ] On a second consecutive expiry, unlock emergency mobilization or a prepared offensive and add war exhaustion; reset the consecutive counter on meaningful progress.
- [ ] Prohibit winner assignment, state transfer, arbitrary white peace, and direct attack bonuses above the approved modest-assistance bounds.
- [ ] Ensure completed/ended wars cancel missions and modifiers.
- [ ] Run collapse, war-exhaustion, polling, and localisation tests.
- [ ] Commit as `feat: add bounded anti-stall initiative missions`.

## Task 10: Implement Bounded Defensive Militia and Political-Power Sinks

**Files:**
- Update: `common/decisions/ADISCORD_vorkerland_collapse_decisions.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Update: `common/ideas/ADISCORD_vorkerland_collapse_ideas.txt`
- Update: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`
- Update: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`
- Update: `tools/tests/test_validate_adiscord_division_templates.py`

- [ ] Add failing tests that major defensive lines/last stands are `fire_only_once`, while local volunteer mobilization has a 90-day cooldown and per-region quota.
- [ ] Require a controlled, supplied, non-encircled spawn state adjacent to the threatened front; reject capitals surrounded by enemy-controlled provinces.
- [ ] Charge manpower, infantry equipment, and political power before unit creation; abort without setting success when payment or spawn selection fails.
- [ ] Spawn weak militia with 25-40% equipment and at most 0.10 experience; better reservists pay at least twice the equipment/PP cost and start above the weak-militia factors.
- [ ] Accumulate war exhaustion/economic strain per repeated mobilization and cap active emergency formations per theater.
- [ ] Allow AI only when retreat/front-density/initiative conditions show genuine need and political power remains above the story-action reserve.
- [ ] Add repeatable `frontline_propaganda` at 25 PP/90 days, `collect_local_weapons` at 30 PP/90 days, and `prepare_regional_integration` at 35 PP/120 days. Each refreshes or advances one capped result rather than stacking an unbounded modifier or spawning free resources.
- [ ] Let AI use these sinks only after mandatory story/military decisions and only above 100 PP; weapon collection additionally requires a verified equipment deficit, and integration preparation requires an eligible controlled package.
- [ ] Run decision, template, war-exhaustion, and collapse validators.
- [ ] Commit as `feat: add finite defensive mobilization and PP sinks`.

## Task 11: Static and Runtime Balance Verification

**Files:**
- Create: `docs/audits/2026-08-08-vorkerland-observer-results.csv`
- Update: `docs/audits/2026-08-08-vorkerland-balance-baseline.md`

- [ ] Run template, theater, force-design, collapse, war-exhaustion, state, building, strategic-region, technology, and localisation focused tests.
- [ ] Run full unit discovery, every generated-owner check, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`.
- [ ] Fully restart HOI4 and verify each claimant starts with organization, equipment, supply, valid air wings, fuel, and active missions.
- [ ] Run 8-12 observer campaigns and record seed, claimant route, start/end dates, winner, longest no-progress interval, northern/regional progress, aircraft mission use, and militia counts.
- [ ] Require normal central completion in two to three years, meaningful movement every 60-120 days, no overwhelming single-claimant win share, no multi-year northern stasis, and no militia growth beyond caps.
- [ ] Convert every runtime failure into a focused regression test before adjustment.
- [ ] Do not declare this plan complete until fresh runtime logs and observer data satisfy the acceptance targets.
