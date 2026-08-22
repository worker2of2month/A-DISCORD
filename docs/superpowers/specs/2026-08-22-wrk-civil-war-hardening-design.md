# WRK Fresh-Campaign Civil-War Hardening Design

## Goal

Make the Vorkerland civil war reliable in a fresh campaign, remove confirmed
runtime and interface failures, and reduce recurring script work without
rewriting the authored campaign. The reference is The Fire Rises' use of staged
events, explicit wars, territorial decisions, and bounded follow-up checks.
The implementation must not copy TFR's monolithic files or introduce a second
source of truth for campaign state.

The work covers WKR, VAD, TVA, their regional wars, the central showdown,
reunification, late formations, focus presentation, and the interface files
that currently shadow newer vanilla definitions.

## Constraints

- Support fresh campaigns only. Do not add save migration, startup repair for
  serialized old state, or polling intended to revive old saves.
- Preserve the current claimants, focus rewards, map split, regional war graph,
  central-war outcomes, diplomacy, and reunification results unless this design
  explicitly changes their routing.
- Use events, decisions, and relevant on-actions for campaign progression.
  Recurring work is allowed only for a value that genuinely changes without a
  useful transition event.
- Preserve unrelated dirty work. Generated files remain owned by their
  builders, Russian localisation retains UTF-8 BOM, and commits stage only
  explicitly verified paths.
- Static validation is not runtime acceptance. Final completion requires a
  fully restarted game, a new campaign, and fresh logs.

## Confirmed failures and debt

The latest available runtime log and repository audit established these
concrete problems:

- Four civil-war focuses use a focus anchor before its definition:
  `WKR_authorize_retreat_levies`, `VAD_standardize_district_logistics`,
  `TVA_raise_technical_battalions`, and `TVA_seal_the_approaches`.
- Late `create_unit` calls can fail after AI template lifecycle changes. The
  confirmed failures include `TVA Collapse Militia` and
  `Armi Security Detachment`; the contract is systemic rather than limited to
  those names.
- The mod's old `nationalfocusview.gui` shadows the current vanilla interface
  and produces `Undefined GUI_TYPE: continuous_national_focus_item`.
- The mod's `goals_shine.gfx` shadows thousands of current vanilla shine
  definitions and causes missing continuous-focus shines.
- `unit_ADISCORD_mechanized_infantry_icon_small` is referenced but undefined.
- Legitimacy-leader comments promise a stable incumbent on a tie, while the
  implementation clears the incumbent and applies fixed tag priority.
- The WRK global monthly hook performs campaign progression, repeated state
  recounts, legitimacy refreshes, theatre/coalition refreshes, and dynamic
  modifier work that can be driven by transitions instead.
- `global.ADISCORD_vorkerland_live_claimants` is written but never read.
- `ADISCORD_vorkerland_is_main_claimant` and
  `ADISCORD_vorkerland_is_central_claimant` currently identify the same tags.
- Three release on-actions duplicate the same premature-WRK interception body.

## TFR reference model

TFR's China collapse stages its initial war declarations through triggered-only
events separated by short, explicit delays. Regional consolidation and final
reunification then proceed through decisions whose availability depends on
owned territory and surviving neighbours. China does not use a global monthly
war clock to unlock those phases. Its tag-specific weekly hook serves a
separate Taiwan-war surrender mission rather than collapse progression.

WRK will follow that structural model:

1. A verified event materializes the collapse.
2. Bounded events declare and verify the regional war graph.
3. Decisions, control changes, and capitulations advance consolidation.
4. A verified phase transition opens the central showdown.
5. Territorial and claimant-survival contracts resolve reunification.

## Canonical campaign progression

The existing phase flags remain the source of truth. Remove the parallel time
source of truth:

- remove `global.ADISCORD_vorkerland_war_month`;
- remove the war-clock-owner trigger and
  `ADISCORD_vorkerland_advance_war_clock`;
- remove the WRK global `on_monthly` progression block;
- remove the unused live-claimant counter;
- replace every `war_month > 18` focus gate with the central-showdown phase
  contract.

No replacement 6-, 18-, or 30-month milestone events are added. Gameplay
state, not elapsed calendar time, advances the scenario.

At verified war outbreak, the setup path immediately applies the one-shot
central attrition modifier and initializes all living claimants. At entry into
the central-showdown phase, late-war focus branches become available and the
AI theatre-priority state is refreshed. This avoids the current delay of up to
one month and makes the result independent of monthly pulse order.

## Transition-driven campaign state

### Legitimacy and leader

`ADISCORD_vorkerland_add_legitimacy` remains the only writer for gameplay
legitimacy changes. After clamping and refreshing derived values it must:

1. refresh the claimant's doctrine variables;
2. recalculate the legitimacy leader;
3. refresh anti-leader coalition state.

An existing living leader remains leader while tied for the highest
legitimacy. A deterministic WKR, VAD, TVA priority is used only when no valid
incumbent exists. A dead, capitulated, or otherwise invalid incumbent is
cleared before selection.

### Territory and organized defence

`on_state_control_changed` refreshes the affected claimant scopes instead of
waiting for a monthly pulse. It continues to resolve iconic objectives and
also recounts central control and organized defence for claimant scopes
involved in the transfer. After any of the 17 central states changes control,
one bounded three-claimant pass refreshes coalition ideas for every living main
claimant; this prevents an uninvolved third claimant from retaining an obsolete
anti-leader idea.

A full three-claimant reconciliation runs only at verified war outbreak,
central-showdown entry, and terminal settlement. These bounded calls provide a
phase-boundary consistency check without becoming a recurring repair loop.

### Anti-leader coalition

The coalition is based on actual dominance rather than elapsed time. It is
active only when all of the following are true:

- the central showdown is active and unfinished;
- a valid legitimacy leader exists;
- that leader controls at least 9 of the 17 central states;
- the recipient is another living AI main claimant currently at war.

Each eligible recipient gets only the idea aimed at the current leader. All
other anti-leader ideas are removed. Losing the territorial majority, changing
leader, leaving the war, becoming player-controlled, or ending the central war
removes obsolete coalition ideas on the same relevant transition.

### Theatre priority

AI theatre priority is refreshed when the central showdown starts and on
subsequent war/peace transitions. It is removed when the claimant leaves the
war, becomes player-controlled, or the central war ends. It has no calendar
gate.

### War economy and doctrine

War economy is the only remaining monthly WRK subsystem in this scope because
factory count can change through construction, damage, and repair without a
Vorkerland state-control transition. Use tag-specific `on_monthly_WKR`,
`on_monthly_VAD`, and `on_monthly_TVA` hooks. Each hook refreshes only its own
active claimant and performs no country or state scan.

Doctrine does not run monthly. Its variables depend on legitimacy and authored
focus choices, so refresh them from the legitimacy writer, doctrine-focus
completion rewards, and bounded claimant initialization.

## Recovery and error handling

The existing regional-war declaration and verification retries remain bounded.
If final verification still fails:

1. clear transient launch-pending flags;
2. set a permanent degraded diagnostic flag;
3. write one precise recovery log entry;
4. queue one next-day event that rechecks the phase and then begins central
   preparation if the scenario is still active.

This path deliberately preserves forward campaign progress rather than
waiting six months for a clock or looping forever. It does not pretend that the
regional graph succeeded, and it cannot execute after collapse completion.

All new transition effects must be idempotent and guarded by phase or ownership
state. Retries are finite and scheduled only from the failing transition.

## Emergency division-template contract

Every late WRK civil-war `create_unit` call must have a same-scope template
guarantee immediately before it. The guarantee:

- checks `has_template` for the exact literal template name;
- recreates the authored template only when absent;
- preserves the original battalion layout, lock state, and recruiting rules;
- creates no divisions itself;
- is safe to call repeatedly.

Initial OOB files continue to own initial templates and units. Emergency
effects cover later event, decision, focus, retreat-levy, reinforcement, and
collapse-militia spawns, including templates that an AI may have deleted after
their initial divisions disappeared. There is no monthly template repair.

Static validation must reject an in-scope late `create_unit` whose template is
neither defined in the executing block nor guaranteed by the corresponding
same-scope ensure effect.

## Focus-tree corrections

Reorder the four confirmed focus definitions so every anchor is defined before
its consumer. Preserve focus IDs, coordinates, `relative_position_id` values,
prerequisites, rewards, and layout.

Late-war focuses remain visible in their authored branches but become available
when the central-showdown phase is active. Delete all focus-validator
expectations for `global.ADISCORD_vorkerland_war_month` and add an ordering
contract that rejects both missing and forward focus references.

## File boundaries and consolidation

Use responsibility-based boundaries while preserving existing public scripted
IDs wherever possible:

- `ADISCORD_vorkerland_phase_effects.txt` retains phase transitions, war-graph
  launch/verification, and terminal settlement routing.
- New `ADISCORD_vorkerland_campaign_state_effects.txt` owns legitimacy leader,
  central-control reconciliation, organized-defence routing, theatre priority,
  and anti-leader coalition state.
- Split the current focus dynamic effect into
  `ADISCORD_vorkerland_war_economy_effects.txt` and
  `ADISCORD_vorkerland_doctrine_effects.txt`.
- New `ADISCORD_vorkerland_emergency_template_effects.txt` owns all late-spawn
  template guarantees. The existing AI force-design file remains responsible
  only for AI technologies, equipment, and force-design bootstrap.
- Split `ADISCORD_vorkerland_focus_decisions.txt` at its existing category
  boundary into central operations and allied support files.
- Make `ADISCORD_vorkerland_is_main_claimant` canonical, replace consumers of
  the identical central-claimant trigger, and remove the duplicate trigger.
- Extract the common premature-WRK release interception path into one scripted
  effect called by `on_puppet`, `on_release_as_puppet`, and
  `on_release_as_free`. Hook-specific normal cosmetic and auxiliary behavior
  remains in each hook.

Do not split the remaining large collapse files merely to reduce line count.
Further extraction requires an ownership or testability benefit tied to this
design.

## Interface inheritance and assets

Delete `interface/nationalfocusview.gui` so the current vanilla focus interface,
including `continuous_national_focus_item`, loads normally. The file contains no
ADISCORD-specific GUI contract worth retaining.

Before removing `interface/goals_shine.gfx`, parse its current dirty contents
and preserve every custom-only sprite definition. Move those definitions into
`interface/ADISCORD_focus_shines.gfx`, discard definitions already provided by
current vanilla, and then remove the shadowing vanilla-named file. This
operation must preserve concurrent custom focus-shine work rather than
reconstructing it from `HEAD`.

Add `unit_ADISCORD_mechanized_infantry_icon_small` to
`interface/ADISCORD_subuniticons.gfx` using the current vanilla small
mechanized texticon texture. Do not introduce another vanilla-named interface
override.

GFX validation must aggregate custom `.gfx` files, verify custom focus icon and
shine coverage, reject duplicate sprite names in the extracted custom file,
and assert that the two obsolete vanilla-shadowing interface paths are absent.

## Verification

### Static regression coverage

Add or extend focused tests and validators to prove:

- no missing or forward focus references;
- no war-clock variable, owner trigger, effect, monthly routing, or focus gate;
- late focuses use the central-showdown availability contract;
- one-shot attrition runs from verified war outbreak;
- legitimacy writes refresh derived doctrine, stable-tie leadership, and
  coalition state;
- coalition activation requires a 9-of-17 leader majority and obsolete ideas
  are removed on relevant transitions;
- control refresh is routed through `on_state_control_changed` and bounded
  phase initialization;
- only tag-specific claimant war-economy refresh remains monthly;
- every in-scope late unit spawn has a same-scope emergency-template guarantee;
- all three release hooks call the shared interception effect without changing
  their hook-specific normal branches;
- custom focus shines and the mechanized small texticon resolve;
- `nationalfocusview.gui` and vanilla-named `goals_shine.gfx` are absent;
- Russian localisation files touched by implementation retain UTF-8 BOM.

Run the focused Vorkerland validators and tests, then the complete Vorkerland
test set. Final repository gates are:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Run the relevant generator `--check` and ownership tests for any generated
path reached during implementation. Do not report a gate as passed unless its
current invocation completed successfully.

### Fresh-campaign runtime acceptance

Fully restart Hearts of Iron IV and begin a new campaign. Exercise or observe:

1. scheduled collapse and verified claimant materialization;
2. regional war launch, bounded verification, and transition to central
   preparation;
3. central-showdown opening and immediate late-focus availability;
4. late reinforcement, retreat-levy, and collapse-militia spawns without
   missing-template errors;
5. legitimacy changes, stable ties, territorial-majority coalition activation,
   leader change, and coalition removal;
6. claimant capitulations, central settlement, and WRK reunification;
7. national-focus and continuous-focus UI rendering;
8. custom focus shines and the small mechanized texticon.

Inspect fresh `error.log`, `game.log`, and relevant UI output. Acceptance
requires no recurrence of the four focus-order errors, missing division
templates, missing continuous shines, undefined continuous-focus GUI types, or
the missing mechanized small texticon.

## Out of scope

- Old-save migration or repair.
- A wholesale rewrite of the authored WRK campaign into TFR source structure.
- New claimants, map borders, focus rewards, localisation prose, or victory
  outcomes unrelated to confirmed failures.
- General cleanup of unrelated interface, technology, map, or Vorkerland
  systems.
