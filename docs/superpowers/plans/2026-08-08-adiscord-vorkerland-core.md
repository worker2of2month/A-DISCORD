# A-Discord Vorkerland Civil-War Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken WRK-centered collapse with an explicit WKR/VAD/TVA war state machine, real postwar WRK formation, shared focus skeletons, a complete regional outcome matrix, explicit coring packages, and the three-stage January 2163 dirty-zone opening.

**Architecture:** WKR is a temporary technical claimant created from prewar WRK at collapse. Seven mutually exclusive phase flags drive events, decisions, focuses, and AI. Bounded launch/formation effects set success only after postconditions. Regional outcomes and integration packages are generated from documented data, with no generic subject fallback. Postwar winners change into WRK and receive a route-specific political branch plus shared recovery branches.

**Tech Stack:** HOI4 tags/countries/events/focuses/decisions/scripted effects/triggers/on_actions/localisation/GFX, Python data generator and validators.

## Global Constraints

- `WRK` is never a wartime claimant. Wartime central claimant sets are exactly `WKR`, `VAD`, and `TVA`.
- Prewar WRK becomes WKR before collapse ownership/OOB setup. WKR home states are 32, 33, 200, and 201; state 34 belongs to WTD after setup.
- A victory flag is set only after war, tag change, ownership, or migration postconditions succeed.
- Every retry is bounded to one explicit retry unless an existing compatibility event already has a stricter finite contract; every terminal failure sets a diagnostic flag and logs `[ADISCORD][VORKERLAND][RECOVERY] ...`.
- VAD or TVA victory forms WRK; it does not annex a pre-existing WRK country. Joint government promotes the joint council leader/cabinet.
- Regional winners are sovereign by default. The only initial subject route is ZAO accepting a voluntary confederal offer.
- Temporary claimants receive home cores only. No `every_owned_state = { add_core_of = ROOT }` is allowed.
- Dirty-zone stage completion flags are set only after ownership/country postconditions and are reconstructed from date plus actual ownership without monthly polling.
- Military balance, militia, initiative, and phase AI implementation belong to the map/forces plan after this core is committed.

---

## Task 1: Replace Stale WRK-as-Claimant Tests

**Files:**
- Create: `tools/tests/test_adiscord_vorkerland_recovery.py`
- Create: `tools/validators/validate_adiscord_vorkerland_recovery.py`
- Update: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`
- Update: `tools/tests/test_vorkerland_claimant_spirit_progression.py`
- Update: `tools/tests/test_vorkerland_war_exhaustion.py`
- Update: `tools/tests/test_vorkerland_worx_supporters.py`
- Update: `tools/validators/validate_adiscord_new_states.py`
- Update: `tools/validators/validate_tc.py`

- [ ] Add `WkrTagSemanticTests`, `PhaseControllerTests`, `BoundedRetryTests`, `ClaimantFocusTests`, `RegionalOutcomeMatrixTests`, `PostwarWrkTests`, `CoringIntegrationTests`, `DirtyZoneTimelineTests`, and `RecoveryMigrationTests`.
- [ ] Replace `test_wrk_remains_a_main_civil_war_claimant` and all equivalent expected-target tables with contracts requiring WKR/VAD/TVA and prohibiting WRK before postwar.
- [ ] Replace tests that require blanket owned-state cores, generic claimant puppeting, WRK-only winner maps, Worker-Doctor special war scheduling, and the two-principal-claimant launcher.
- [ ] Preserve ROM/TRU, IVN, VAL, air/OOB, exhaustion, map-connectivity, and regional-war coverage; update only their claimant/tag assumptions.
- [ ] Run each new class and confirm RED because WKR, phase effects, generated matrix, explicit integration, and dirty timeline are missing.
- [ ] Commit RED tests as `test: define WKR and WRK semantic contracts`.

## Task 2: Add the Temporary WKR Tag and Migrate Wartime References

**Files:**
- Create: `common/countries/WKR.txt`
- Update: `common/country_tags/01_ADISCORD_vorkerland_collapse_tags.txt`
- Create: `gfx/flags/WKR.tga`
- Create: `gfx/flags/medium/WKR.tga`
- Create: `gfx/flags/small/WKR.tga`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Update: `common/decisions/ADISCORD_vorkerland_collapse_decisions.txt`
- Update: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Update: `events/ADISCORD_vorkerland_collapse_events.txt`
- Update: `common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt` only for mechanical tag semantics; phase tuning is deferred
- Update: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`
- Create: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Create: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`

- [ ] Add WKR to the existing Vorkerland regional tag file rather than creating a one-tag file.
- [ ] Copy the three existing `WRK_vorkerland_emergency.tga` sizes to WKR; do not use a vanilla placeholder or alter WRK postwar route flags.
- [ ] At collapse, execute `WKR = { change_tag_from = WRK }` before initial-map, OOB, idea, and war setup. Add a postcondition requiring `country_exists = WKR` and WKR control of home states 32, 33, 200, 201 before continuing.
- [ ] Change setup, launch, exhaustion, cosmetics, relocation, support contracts, outcome detection, and wartime AI scopes from WRK to WKR.
- [ ] Exclude WRK from every temporary-claimant trigger and wartime focus/decision availability.
- [ ] Remove/reassign historical WRK cores during collapse so dormant WRK is not releasable and postwar integration is not free.
- [ ] Add WKR country/party/cosmetic names to Russian and English recovery localisation.
- [ ] Run WKR semantic, country-tag/path, flag-dimension, collapse, exhaustion, and localisation tests.
- [ ] Commit as `feat: add temporary WKR civil war claimant`.

## Task 3: Introduce the Seven-Phase Controller

**Files:**
- Create: `common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt`
- Create: `common/scripted_triggers/ADISCORD_vorkerland_phase_triggers.txt`
- Create: `events/ADISCORD_vorkerland_phase_events.txt`
- Update: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Update: `events/ADISCORD_vorkerland_collapse_events.txt`
- Update: `tools/data/adiscord_event_ids.json`
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Define exactly one of: `phase_prewar`, `phase_collapse`, `phase_regional_consolidation`, `phase_central_preparation`, `phase_central_showdown`, `phase_reunification`, `phase_postwar_integration`, all prefixed `ADISCORD_vorkerland_`.
- [ ] Implement one `ADISCORD_vorkerland_clear_phase_flags` and seven setter effects; prohibit direct phase flag mutation outside this file and migration.
- [ ] Implement triggers `is_temporary_claimant`, `collapse_materialized`, `regional_consolidation_complete`, `central_showdown_required`, `central_showdown_edges_verified`, `has_single_surviving_claimant`, and `reunification_verified`.
- [ ] Implement effects `begin_collapse`, `verify_collapse_materialized`, `verify_regional_consolidation`, `begin_central_preparation`, `initialize_showdown_edge_queue`, `attempt_next_showdown_edge`, `verify_showdown_edge_wkr_vad`, `verify_showdown_edge_wkr_tva`, `verify_showdown_edge_vad_tva`, `verify_central_showdown`, `begin_reunification`, and `verify_reunified_wrk`.
- [ ] Use `add_namespace = ADISCORD_vorkerland_phase` and the inventoried full IDs: `.1` prewar preference, `.2` one-day collapse verification, `.3` regional completion, `.4` 45-day preparation expiry/queue initialization, `.5` one-edge attempt/postcondition dispatcher, `.6` winner dispatcher, `.7` WRK formation postcondition and one retry. Switch these registry entries from `reserved` to `active` with this owning file.
- [ ] At `.4`, set a `required` flag for each pair whose two tags still exist: `showdown_edge_wkr_vad_required`, `showdown_edge_wkr_tva_required`, and `showdown_edge_vad_tva_required`. Clear all previous attempted/retry/verified/failed edge flags before initialization.
- [ ] Event `.5` processes exactly one next required-unverified edge in fixed order WKR-VAD, WKR-TVA, VAD-TVA. It detaches the pair from conflicting factions, attempts one declaration, and schedules itself one day later for postcondition verification; a missing `has_war_with` gets exactly one retry flag and one second attempt.
- [ ] After an edge verifies, set its `..._verified` flag and schedule `.5` for the next edge. After its second failure, set its `..._failed` flag plus `ADISCORD_vorkerland_central_showdown_launch_failed`, log the exact pair, and stop without setting showdown success.
- [ ] Set `ADISCORD_vorkerland_central_showdown_started` and enter the showdown phase only when every required edge has its verified flag. A non-required edge is skipped, never treated as implicitly successful.
- [ ] Add terminal flags for collapse materialization, regional war launch, central border launch, the three named showdown edges, central showdown launch, and reunification failures, each with an explicit diagnostic log.
- [ ] Run phase exclusivity, transition, bounded retry, event namespace, and no-polling tests.
- [ ] Commit as `feat: add Vorkerland phase controller`.

## Task 4: Route Existing Launchers Through the Phase Controller

**Files:**
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt`
- Update: `common/decisions/ADISCORD_vorkerland_collapse_decisions.txt`
- Update: `events/ADISCORD_vorkerland_collapse_events.txt`
- Update: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`

- [ ] Keep existing `.48/.49`, `.63/.64`, and `.71/.72` IDs as compatibility shims; do not reuse or delete queued event IDs.
- [ ] Change their wartime WRK scopes to WKR and route obsolete Worker-Doctor scheduling into phase events `.4/.5`.
- [ ] Preserve faction-detachment/cache barriers, but set success only after `has_war_with` postconditions and route exhausted retries into named terminal flags.
- [ ] Ensure regional consolidation opens assigned wars before central preparation and never launches two central opponents in one unverified step.
- [ ] Remove the special two-principal claimant assumption; all three surviving claimants are eligible for the showdown.
- [ ] Run compatibility-shim, live-border, faction-detach, bounded retry, and phase tests.
- [ ] Commit as `fix: route collapse launchers through phase state`.

## Task 5: Add the Player Preference Event and Claimant Focus Skeleton

**Files:**
- Create: `common/national_focus/ADISCORD_vorkerland_claimant_focus.txt`
- Update: `events/ADISCORD_vorkerland_phase_events.txt`
- Update: `common/ideas/ADISCORD_vorkerland_collapse_ideas.txt`
- Update: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Make phase event `.1` a visible choice between Worker, joint-government, and utilitarian support; choices set support/AI-weight flags and never select a route with unseeded naked randomness.
- [ ] If the human begins as WRK, the player follows the WRK->WKR change; VAD/TVA remain independently playable tags and consume the same preference/support flags for AI weighting.
- [ ] Create one non-default focus tree whose country weight covers exactly WKR, VAD, and TVA while phase flags control availability.
- [ ] Add focus IDs: stabilize regime, repair field army, secure proxy network, consolidate home region, prepare central front, conduct central showdown, authorize emergency defence, and form reunified Vorkerland.
- [ ] Use shared focus content with tag-scoped completion effects for WKR Worker networks, VAD Solyarino loyalists, and TVA technocratic proxies.
- [ ] Gate each focus to its correct phase and actual preconditions; no focus may set a phase success flag directly before the controller verifies it.
- [ ] Add Russian and English names/descriptions/tooltips with identical new key sets and Russian BOM.
- [ ] Run focus graph, claimant coverage, route-weight, phase availability, localisation, and BOM tests.
- [ ] Commit as `feat: add Vorkerland claimant focus skeleton`.

## Task 6: Generate the Complete Regional Outcome Matrix

**Files:**
- Create: `tools/data/adiscord_vorkerland_regional_outcomes.json`
- Create: `tools/builders/build_adiscord_vorkerland_recovery.py`
- Generate: `common/scripted_effects/ADISCORD_vorkerland_regional_outcome_effects.txt`
- Create: `events/ADISCORD_vorkerland_postwar_events.txt`
- Update: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Update: `tools/data/adiscord_event_ids.json`
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Encode all 30 winner/partner x route cells exactly:
  - ZAO: voluntary confederal / voluntary confederal / economic association.
  - WPA: guarantee+NAP / alliance / economic association.
  - WPS: economic association / guarantee+NAP / alliance.
  - PSD: sovereignty+NAP / guarantee / economic association.
  - PWR: sovereignty+NAP / guarantee / alliance+association.
  - ROM: guarantee / alliance / NAP.
  - DVA: NAP / guarantee / economic association.
  - TRU: guarantee / alliance / NAP.
  - ZTA: NAP / guarantee / economic association.
  - VAL: sovereign guarantee partner / sovereign ally / sovereign economic partner.
- [ ] Make the builder default to `--check` and require `--apply` for the generated effect file.
- [ ] Generate recording effects for northern, ROM/DVA, and TRU/ZTA winners; generate one named outcome effect for every cell and an `apply_pending_regional_outcomes` dispatcher.
- [ ] Call winner recording from relevant capitulation/peace hooks and apply pending outcomes both when a row becomes terminal and after WRK formation.
- [ ] Prohibit generic `puppet`, generic `set_autonomy`, generic subject fallback, and unhandled cells in data, generator, and output.
- [ ] Use `add_namespace = ADISCORD_vorkerland_postwar`; switch inventoried `.1-.3` from reserved to active. `.1` is the ZAO accept/refuse event, `.2` the WRK acceptance notice, and `.3` the refusal notice. Refusal leaves ZAO sovereign and applies the route fallback.
- [ ] Treat VAL wartime support-recipient flags as historical inputs only; never map them to subjection.
- [ ] Run matrix completeness/prohibition tests and generator check/apply/idempotence.
- [ ] Commit as `feat: generate Vorkerland regional outcomes`.

## Task 7: Form Actual Postwar WRK for Every Central Winner

**Files:**
- Update: `common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_map_effects.txt`
- Update: `events/ADISCORD_vorkerland_phase_events.txt`
- Update: `common/characters/ADISCORD_vorkerland_collapse_characters.txt`
- Update: `history/countries/WRK - WorkerLand.txt`
- Update: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Implement `form_wrk_from_wkr`, `form_wrk_from_vad`, `form_wrk_from_tva`, `verify_reunified_wrk`, and `finalize_reunified_wrk`.
- [ ] Map WKR victory to `route_worker`, VAD victory to `route_joint`, and TVA victory to `route_utilitarian`.
- [ ] For VAD/TVA victory, move any defeated country still occupying the WRK tag to WKR before changing the winner into WRK; never annex WRK as the formation mechanism.
- [ ] For WKR victory, change WKR into WRK and retain player control, armies, air wings, subjects, and relevant event targets.
- [ ] Promote `WRK_VAD_Joint_Council` and its compromise cabinet on the joint route; repair the leader exactly once.
- [ ] Before retiring losers, detach WKR/VAD/TVA from internal-war factions. For each losing claimant, release every surviving subject to `autonomy_free`, remove that subject from the claimant's faction, and verify it is no longer subject; regional/proxy subjects never transfer automatically to WRK.
- [ ] After the winner has changed into WRK and its route/leader/capital postconditions pass, annex each existing losing temporary claimant from WRK scope with troop transfer enabled. This postwar cleanup transfers the loser's armies, navy, air wings, owned states, and occupations; it is not the prohibited VAD-annexes-pre-existing-WRK formation mechanism.
- [ ] A human player on the winning claimant follows `change_tag_from` into WRK. A human player on a losing claimant is defeated normally and is not silently switched to the winner.
- [ ] Verify each losing claimant no longer exists, owns/controls no state, has no subject, and leaves no active internal war before setting `reunification_verified`. On failure, preserve the tag for diagnosis, set `ADISCORD_vorkerland_reunification_failed`, and do not enter postwar integration.
- [ ] Apply pending regional outcomes and enter postwar integration only after WRK formation verifies.
- [ ] Run tag-formation tests and targeted save migration/runtime scenarios for all three winners.
- [ ] Commit as `feat: form postwar WRK from every claimant`.

## Task 8: Add the Reunified WRK Shared and Political Focus Tree

**Files:**
- Create: `common/national_focus/ADISCORD_vorkerland_reunified_focus.txt`
- Update: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Create a WRK-only non-default focus tree gated to `phase_postwar_integration`.
- [ ] Add `WRK_convene_recovery_council` followed by mutually exclusive Worker mandate, joint charter, and utilitarian directorate focuses, each requiring its exact route flag.
- [ ] Add shared focuses for unified army, air/naval commands, economy/science, ending the war emergency, transport reconstruction, and regional integration.
- [ ] Keep political route effects distinct in leader/government/ideas; shared branches may not erase the route.
- [ ] Make integration focus completion unlock decisions rather than adding blanket cores.
- [ ] Add Russian/English localisation and run focus graph, exclusivity, route, and localisation tests.
- [ ] Commit as `feat: add reunified Vorkerland focus tree`.

## Task 9: Replace Blanket Cores with Explicit Integration Packages

**Files:**
- Create: `tools/data/adiscord_vorkerland_integration_packages.json`
- Generate: `common/scripted_effects/ADISCORD_vorkerland_integration_effects.txt`
- Create: `common/scripted_triggers/ADISCORD_vorkerland_integration_triggers.txt`
- Create: `common/decisions/ADISCORD_vorkerland_recovery_decisions.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Update: `tools/builders/build_adiscord_vorkerland_recovery.py`
- Update: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Delete `every_owned_state = { add_core_of = ROOT }` from claimant preparation.
- [ ] Give temporary home cores only: WKR `32,33,200,201`; VAD `75,106,107,121`; TVA `36,37,38,39,324`.
- [ ] Encode explicit integration packages:
  - central `27,34,35,40,79,81,82,102,108,109,110,111,122,123,124,306,308,309,315,316,317,318,320,323,325,327,331,332`;
  - northern `71,72,90,91,93,94,194,195,196,202,322,328,333,334,335`;
  - Volnograd `74,105,197,311,312,313,314,337`;
  - Frealor `73,144,145,319,321,336`;
  - Solyarino `76,104,198,307,310,338`;
  - Zlatorech `80,199,339,340`.
- [ ] Generate explicit state enumerations; prohibit `every_owned_state` and `every_state` coring. VAL is not coreable in this project.
- [ ] Add central integration at 75 PP/120 days and accepted voluntary northern confederation at 75 PP/120 days.
- [ ] Add forced northern, Volnograd, Frealor, Solyarino, and Zlatorech integration at 150 PP/360 days each.
- [ ] Require every listed state owned and controlled by WRK, resistance below 25, and compliance at least 40 for forced packages. Voluntary confederation uses the acceptance flag and its cheaper path.
- [ ] Independent allies remain uncoreable; decisions are unavailable until the relevant relationship/outcome permits annexed integration.
- [ ] Assert against the already-completed map theater manifest that every maneuver residual `331-340` is in exactly the same package as its source; this task is the sole creator of the integration-package file.
- [ ] Run home-core, package completeness, decision cost/time, prohibited blanket-core, generator, and migration tests.
- [ ] Commit as `feat: integrate Vorkerland through explicit coring packages`.

## Task 10: Open the Dirty Zone on 2163-01-01, 2163-01-12, and 2163-01-27

**Files:**
- Create: `events/ADISCORD_vorkerland_dirty_zone_events.txt`
- Update: `common/scripted_effects/ADISCORD_vorkerland_collapse_dirty_effects.txt`
- Update: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Update: `events/ADISCORD_vorkerland_collapse_events.txt`
- Update: `tools/data/adiscord_event_ids.json`
- Update: `localisation/english/ADISCORD_vorkerland_recovery_l_english.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_recovery_l_russian.yml`
- Update: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml` only for compatibility-event text retained from the old namespace
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Use `add_namespace = ADISCORD_vorkerland_dirty_zone` and switch inventoried `.1-.3` from reserved to active in this owning file.
- [ ] Add event `.1` exactly on 2163-01-01 for SLA+MLR fringe sectors; set `dirty_stage_1_complete` only after verification and schedule `.2` in 11 days.
- [ ] Add `.2` exactly on 2163-01-12 for RZA+SCA; set stage 2 only after verification and schedule `.3` in 15 days.
- [ ] Add `.3` exactly on 2163-01-27 for ERT+IRT plus conflict activation; set stage 3 only after verification.
- [ ] Seed `.1` from one country-scoped `on_yearly` route using RUS and the exact date; add no `on_monthly` or world scan.
- [ ] Convert old collapse events `.10-.19` into compatibility shims invoking reconstruction without duplicating ownership transfers.
- [ ] Implement `reconstruct_dirty_stage` and three stage verifiers. For old saves, date >= Jan 27 reconstructs all; >= Jan 12 stages 1-2; >= Jan 1 stage 1. Actual ownership overrides stale flags.
- [ ] Make each stage idempotent and leave a diagnostic failure flag/log when ownership/country postconditions cannot be materialized after one retry.
- [ ] Run exact-date, scheduling, group, ownership precedence, idempotence, event namespace, and no-monthly-poll tests.
- [ ] Commit as `feat: open the dirty zone through three dated stages`.

## Task 11: Add Recovery Schema Migration and Compatibility

**Files:**
- Update: `common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt`
- Update: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt`
- Update: `events/ADISCORD_vorkerland_phase_events.txt`
- Test: `tools/tests/test_adiscord_vorkerland_recovery.py`

- [ ] Add idempotent `ADISCORD_vorkerland_recovery_schema_1` migration on startup/reload for relevant countries only.
- [ ] If an old active war uses wartime WRK, change old WRK to WKR first and reconstruct phase from actual wars, winner, and launch flags.
- [ ] If an old Worker victory is already postwar WRK, retain WRK and set Worker route/postwar phase without a tag change.
- [ ] If old VAD/TVA victory left defeated WRK in the WRK slot, move the defeated country to WKR before forming WRK from the winner.
- [ ] Preserve old joint-government council/cosmetic and set Joint route; repair the leader once.
- [ ] Preserve VAL support-recipient history without creating subject flags.
- [ ] Preserve queued `.48/.49/.63/.64/.71/.72` events through shims.
- [ ] Reconstruct dirty stages from ownership/date and regional winner/outcome flags from actual survivors/relationships.
- [ ] Test migration twice on each fixture and require byte/state-idempotent flags with no repeated event, core, or subject creation.
- [ ] Commit as `fix: migrate legacy Vorkerland collapse saves`.

## Task 12: Civil-War Core Verification

- [ ] Run the new recovery tests and validator.
- [ ] Run collapse, claimant spirit, exhaustion, Worx supporters, ROM/TRU, VAL, IVN/intervention, event ID, localisation, and map ownership focused suites.
- [ ] Run the recovery builder `--check`, generated idempotence, Russian BOM, localisation uniqueness, and prohibited polling/core/subject searches.
- [ ] Run full unit discovery, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`.
- [ ] Fully restart HOI4 and smoke test prewar choice, collapse into WKR/VAD/TVA, regional wars, 45-day preparation, all live showdown edges, each winner forming WRK, joint-government leader, regional outcomes, integration decisions, and all three dirty-zone dates.
- [ ] Load one legacy save for active wartime WRK, each winner, old joint government, and each dirty-zone stage.
- [ ] Inspect fresh `error.log`, `game.log`, and `system.log`; do not claim core completion from static validation alone.
