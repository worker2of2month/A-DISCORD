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

## Exclusive Shared-File Block Ownership

After core Tasks 1-6 commit, this plan may add or replace only these blocks in shared collapse files:

- decisions/missions: `ADISCORD_vorkerland_central_initiative`, `ADISCORD_vorkerland_recruit_local_volunteers`, `ADISCORD_vorkerland_establish_last_defensive_line`, `ADISCORD_vorkerland_frontline_propaganda`, `ADISCORD_vorkerland_collect_local_weapons`, `ADISCORD_vorkerland_prepare_regional_integration`;
- effects: `ADISCORD_vorkerland_initialize_initiative`, `ADISCORD_vorkerland_refresh_initiative_progress`, `ADISCORD_vorkerland_handle_initiative_expiry`, `ADISCORD_vorkerland_cancel_initiative`, `ADISCORD_vorkerland_select_militia_spawn_state`, `ADISCORD_vorkerland_recruit_local_volunteers_effect`, `ADISCORD_vorkerland_establish_last_defensive_line_effect`, `ADISCORD_vorkerland_apply_frontline_propaganda`, `ADISCORD_vorkerland_collect_local_weapons_effect`, `ADISCORD_vorkerland_prepare_regional_integration_effect`;
- triggers: `ADISCORD_vorkerland_meaningful_progress_detected`, `ADISCORD_vorkerland_has_exposed_supplied_front`, `ADISCORD_vorkerland_has_valid_militia_spawn_state`, `ADISCORD_vorkerland_can_recruit_local_volunteers`, `ADISCORD_vorkerland_can_spend_surplus_pp`;
- ideas/flags: `ADISCORD_vorkerland_initiative_recovery`, `ADISCORD_vorkerland_frontline_propaganda_modifier`, and prefixed use/cooldown/counter flags for the six decision IDs above.

For Task 6 stockpile recalculation and Task 7 one-time air setup, this plan additionally owns only equipment/manpower/`load_oob` statements and calls to `ADISCORD_vorkerland_initialize_claimant_air_setup` inside these existing setup effects: `ADISCORD_vorkerland_prepare_initial_combatants`, `ADISCORD_vorkerland_setup_tva`, `ADISCORD_vorkerland_setup_wtd`, `ADISCORD_vorkerland_setup_eyr`, `ADISCORD_vorkerland_setup_egc`, `ADISCORD_vorkerland_setup_riv`, `ADISCORD_vorkerland_setup_rev`, `ADISCORD_vorkerland_setup_yor`, `ADISCORD_vorkerland_setup_ndn`, `ADISCORD_vorkerland_setup_swb`, `ADISCORD_vorkerland_setup_vhv`, `ADISCORD_vorkerland_setup_osv`, `ADISCORD_vorkerland_setup_csl`, `ADISCORD_vorkerland_setup_wpa`, `ADISCORD_vorkerland_setup_wps`, `ADISCORD_vorkerland_setup_psd`, `ADISCORD_vorkerland_setup_eba`, `ADISCORD_vorkerland_setup_dva`, `ADISCORD_vorkerland_setup_sra`, `ADISCORD_vorkerland_setup_zta`, and `ADISCORD_vorkerland_setup_tgd`. The new `ADISCORD_vorkerland_initialize_claimant_air_setup` block itself is owned by this plan in `ADISCORD_vorkerland_force_design_effects.txt`. Ownership, control, cores, leaders, phase flags, diplomacy, war declarations, and outcome logic inside these setup effects remain read-only.

The only permitted `01_ADISCORD_vorkerland_collapse_on_actions.txt` edits are calls to initialize/refresh/cancel the named initiative effects from the existing war/state-control hooks. Any other shared-block need is a plan defect and stops the task.

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
- Generate: `history/states/331-*.txt` through `history/states/340-*.txt`
- Generate: affected source `history/states/*.txt`

- [ ] Reserve IDs 331-340 only for the following ten maneuver splits; do not collide with outer-state generation beginning at 341. Add failing graph tests requiring both listed province sets to be connected, their union to equal the current source, every capital to belong to its state, every retained VP to belong to its state, at least two physical state adjacencies per residual, and the named front to contain at least three residual border provinces.
- [ ] Generate the exact central partitions:
  - `27 -> 331`: residual `331 = (524,904,4568,4878,6435,11842,16598,16601)`, remaining `27 = (2643,5090,6451,6850,7564,9525,10215,12618,16614)`, capital `4878`, borders `27:6,35:1,199:4,317:1,318:2`, four-province front against 199. All current rail and the `16614` junction remain in 27; no rail or supply-file edit is required.
  - `35 -> 332`: residual `332 = (566,7885,9321,10805,16422)`, remaining `35 = (1378,4880,16388,16410,16412)`, capital `7885`, borders `32:2,34:1,35:3,36:4,320:2`, four-province front against 36. Keep VP/hub `16388` in 35; the state border crosses rail edge `7885-16388`, while branch `7885-12227` remains available to 332.
- [ ] Generate the exact northern partitions:
  - `72 -> 333`: residual `333 = (4262,5136,5844,6636,6730,7664,7685,7959,11945,12433,16625)`, remaining `72 = (2565,3738,4178,6181,8631,8987,9022,10896,11703,12093,16622)`, capital/existing VP `16625`, borders `72:9,133:1,196:8,322:2`, eight-province front against 196. Keep VP/hub `16622` in 72; retain rail `16625-7959-5844` in 333 and allow border crossings `2565-6730` and `16625-12093`.
  - `195 -> 334`: residual `334 = (647,1111,7230,9158,9727,10606,11635,11717,12025,12995)`, remaining `195 = (806,1100,2896,3534,4528,4634,7090,8032,9075,9149)`, capital `1111`, borders `137:1,194:2,195:8,196:9`, nine-province front against 196. Keep hub `8032` in 195; rail crosses at `1111-8032` and `8032-647`, with the branch from `7230` retained in 334.
  - `196 -> 335`: residual `335 = (1569,3069,3928,4224,7341,7443,8051,10171,10864)`, remaining `196 = (236,1711,3151,4331,5207,5409,6253,6799,7129,7827,7934)`, capital `10864`, borders `72:5,194:1,195:2,196:5,322:2`, five-province front against 72. Keep hub `7129` and its rail in 196; retain segment `3928-10864` in 335.
- [ ] Generate the exact regional partitions:
  - `73 -> 336`: residual `336 = (404,2346,2767,3573,4139,4423,4924,5695,6927,9537,9962,10323,10696,11072,11904,12126,12450,12692,12940,12984,13011,16618)`, remaining `73 = (930,1374,2916,4795,4798,4859,4931,5076,5762,5878,6742,7615,7954,7974,8019,8912,9266,9323,10555,10747,12850,12946,13007,16557,16571)`, capital/existing VP `16618`, borders `72:6,73:7,319:3,321:4,322:1`, six-province front against 72. Keep VP/hub `16571` in 73; rail crosses at `9323-12984` and `4798-404`, while the `404-4924-4423-16618-6927` segment remains in 336.
  - `74 -> 337`: residual `337 = (3492,5408,5666,6543,8704,12541)`, remaining `74 = (2197,2402,2516,2583,5799,8497,12316,12947,16585)`, capital `6543`, borders `74:5,105:1,197:2,311:1,312:3,326:1`, three-province front against 312. Keep VP/hub `16585` in 74; rail crosses at `2516-8704`, with `8704-6543-5408` and `5666-6543` retained in 337.
  - `76 -> 338`: residual `338 = (336,2552,2866,3905,5741,9833,10964)`, remaining `76 = (2988,5721,6443,9452,11090,16582)`, capital `2866`, borders `76:3,104:2,198:4,307:1,310:1`, four-province front against 198. Keep VP/hub `16582` in 76; rail crosses only at `16582-9833`, with `9833-2866-3905` retained in 338.
  - `80 -> 339`: residual `339 = (1423,1672,1969,2914,4133,4278,5676,6399,7434,7770,8849,10034,10609,10746,16633,16634)`, remaining `80 = (265,449,686,860,868,1426,1581,3083,3567,3997,5153,5358,5376,7819,9464,9845,10624,11472,16619)`, capital `10034`, borders `80:8,146:2,150:1,151:2,157:1,159:2,161:5,162:4,199:2,315:1`, five-province front against 161. Keep VP `16619` and hub `3083` in 80; rail crosses at `10624-10034`.
  - `199 -> 340`: residual `340 = (531,976,1889,4501,6456,6465,6759,9448,9811,10990,12508)`, remaining `199 = (1280,3345,3518,5314,5524,5679,5888,6820,7267,7942,11379,11563,11592,12930)`, capital `10990`, borders `27:3,80:3,199:5,317:3,318:1`, three-province fronts against 27, 80, and 317. Keep hub `12930` in 199; rail crosses at `10990-5314` and `12930-4501`, while `6456-976` remains in 340.
- [ ] Store these literal province tuples and state profiles in the builder; do not implement runtime ownership surgery. Province IDs and global rail/supply endpoints remain unchanged, so regenerate `map/buildings.txt` and strategic regions but do not edit `map/railways.txt` or `map/supply_nodes.txt`.
- [ ] Preserve each source's total manpower, resources, buildings, existing VPs, and provinces across source plus residual before Task 3 balance additions. Task 3 adds 1-point VPs at residual capitals `4878,7885,1111,10864,6543,2866,10034,10990`; existing residual VPs `16625` and `16618` remain unchanged.
- [ ] Record for later core Task 9 that the exact final packages are: central `(27,34,35,40,79,81,82,102,108,109,110,111,122,123,124,306,308,309,315,316,317,318,320,323,325,327,331,332)`; northern `(71,72,90,91,93,94,194,195,196,202,322,328,333,334,335)`; Volnograd `(74,105,197,311,312,313,314,337)`; Frealor `(73,144,145,319,321,336)`; Solyarino `(76,104,198,307,310,338)`; Zlatorech `(80,199,339,340)`. Do not create or update the not-yet-owned integration-package file during this map task; theater tests assert the source-to-package mapping so core Task 9 can consume it.
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
- [ ] Define `ADISCORD_vorkerland_meaningful_progress_detected` as capture of a listed state or VP from the current assigned enemy; use the existing state-control hook to call `ADISCORD_vorkerland_refresh_initiative_progress`.
- [ ] Use `ADISCORD_vorkerland_initialize_initiative` at war launch, `ADISCORD_vorkerland_handle_initiative_expiry` on mission timeout, and `ADISCORD_vorkerland_cancel_initiative` when the assigned war ends.
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

- [ ] Implement exactly `ADISCORD_vorkerland_recruit_local_volunteers` and `ADISCORD_vorkerland_establish_last_defensive_line`, calling `ADISCORD_vorkerland_recruit_local_volunteers_effect` and `ADISCORD_vorkerland_establish_last_defensive_line_effect` after `ADISCORD_vorkerland_select_militia_spawn_state` succeeds.
- [ ] Add failing tests that major defensive lines/last stands are `fire_only_once`, while local volunteer mobilization has a 90-day cooldown and per-region quota.
- [ ] Require a controlled, supplied, non-encircled spawn state adjacent to the threatened front; reject capitals surrounded by enemy-controlled provinces.
- [ ] Charge manpower, infantry equipment, and political power before unit creation; abort without setting success when payment or spawn selection fails.
- [ ] Spawn weak militia with 25-40% equipment and at most 0.10 experience; better reservists pay at least twice the equipment/PP cost and start above the weak-militia factors.
- [ ] Accumulate war exhaustion/economic strain per repeated mobilization and cap active emergency formations per theater.
- [ ] Allow AI only when retreat/front-density/initiative conditions show genuine need and political power remains above the story-action reserve.
- [ ] Add repeatable `ADISCORD_vorkerland_frontline_propaganda` at 25 PP/90 days, `ADISCORD_vorkerland_collect_local_weapons` at 30 PP/90 days, and `ADISCORD_vorkerland_prepare_regional_integration` at 35 PP/120 days. Each calls its exact prefixed effect and refreshes or advances one capped result rather than stacking an unbounded modifier or spawning free resources.
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
