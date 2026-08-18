# STP Core Mechanics Cleanup Design

## Goal

Reduce StepanLand's bespoke political scripting to three connected systems while preserving its authored starting-army restriction:

1. Party suspicion controls political-power gain.
2. Ivanov's health is a discrete five-stage state that controls stability.
3. The focus-tree inlay visualizes that same health state and shows its tooltip on hover.

Temporary DEBUG decisions provide deterministic test controls. Legacy rate variables, duplicate localisation APIs, mirrored health state, stale migration code, and disposable test content are removed.

## Canonical state

### Party suspicion

Use exactly one persistent gameplay variable:

- `STP_party_suspicion`: clamped to `0..100`.
- default value: `5`.

Use exactly one derived modifier variable:

- `STP_sus_political_power_factor`.

Formula:

`STP_sus_political_power_factor = 0.35 - 0.007 * STP_party_suspicion`

Thus:

- suspicion 0 -> +35% political-power gain;
- suspicion 50 -> 0%;
- suspicion 100 -> -35% political-power gain.

`STP_change_party_suspicion` consumes temporary `STP_party_suspicion_change`, clamps the persistent value, recalculates the PP factor, then clears the temporary input.

The suspicion dynamic modifier is permanent for STP and reads `STP_sus_political_power_factor`.

`STP_sus_political_power_factor` is never stored as authored country-history state. It is always recalculated from suspicion by `STP_refresh_party_suspicion`, preventing a stale cached value after balance changes.

### Ivanov health

Use exactly one persistent gameplay variable:

- `STP_leader_health_stage`: integer-like state `1..5`.

Stages:

1. Stable condition.
2. Growing exhaustion.
3. Severe weakness.
4. Critical condition.
5. Death.

There is no separate health percentage, `*_rate`, or mirrored portrait-stage variable.

`STP_set_leader_health_stage` consumes temporary `STP_requested_health_stage`, updates `STP_leader_health_stage`, refreshes and clamps the result to `1..5`, then clears the temporary input.

Health penalties are deliberately simple:

- stage 1 -> 0 stability factor;
- stage 2 -> -5% stability factor;
- stage 3 -> -10%;
- stage 4 -> -20%;
- stage 5 -> -30%.

`STP_fading_father_stability_factor` is derived state and is not authored in country history.

Ivanov health does not directly modify political-power gain. Low stability already applies the game's global low-stability PP penalty, so the causal chain remains readable: Ivanov deteriorates -> stability falls -> political work becomes harder.

Existing focus content uses `STP_ivanov_dead`, so the flag is retained only as a derived compatibility/output state: stage 5 sets it and stages 1-4 clear it. The flag never drives the health stage and therefore is not a second source of truth.

### Focus-tree inlay

The inlay reads `STP_leader_health_stage` directly. No mirror variable such as `STP_state_face_stage` exists.

The portrait and hover tooltip use the same five-stage state. The inlay is metaphorical presentation, not a third gameplay subsystem.

Keep only the scripted-localisation API required by the inlay:

- `STPGetStateFaceStageName`
- `STPGetStateFaceTooltip`

The decisions category keeps suspicion text helpers because it is the player-facing status panel.

## Initialization

Fresh STP country history owns only canonical persistent state:

- `STP_party_suspicion = 5`
- `STP_leader_health_stage = 1`

`STP_initialize_core_mechanics` is the single startup entry point for this subsystem. It:

1. initializes either persistent value if missing;
2. recalculates both derived modifier values;
3. synchronizes the starting army restriction with `STP_hedonism_with_no_bondaries`;
4. attaches the suspicion and fading-father dynamic modifiers if missing.

No separate STP on-action file is added and country history does not duplicate derived values.

## Starting army restriction

The starting division lock is authored gameplay and remains separate from suspicion/health state.

At scenario start:

- `Police division` is locked and cannot be recruited;
- `Regular army` is locked and cannot be recruited;
- `Capital Guard` is locked, cannot be recruited, and remains capped at one division.

The OOB declares those starting restrictions directly. `STP_initialize_core_mechanics` reasserts them through `ADISCORD_STP_lock_regular_army_templates` while `STP_hedonism_with_no_bondaries` is active, so startup state is deterministic.

The minimal army-restriction API contains only:

- `ADISCORD_STP_lock_regular_army_templates`
- `ADISCORD_STP_unlock_regular_army_templates`

The old save-migration wrapper is removed.

When `STP_hedonism_with_no_bondaries` is removed, its `on_remove` calls the unlock effect. That unlocks only Police and Regular Army; Capital Guard remains permanently unique and locked.

## DEBUG decisions

Delete `STP_test`.

Add clearly marked zero-cost DEBUG decisions under the existing `STP_elections_in_the_party` category:

- DEBUG: Increase party suspicion (+10)
- DEBUG: Decrease party suspicion (-10)
- DEBUG: Improve Ivanov's condition (-1 stage)
- DEBUG: Worsen Ivanov's condition (+1 stage)

Their visible names begin with red `DEBUG:` text. They are test controls, not intended gameplay.

## Suspicion gameplay direction

Suspicion is a heat/operational-exposure system, not a passive timer.

Future Shabrata and Party content should create a repeated risk-tempo choice:

- covert recruitment, infiltration, propaganda, patronage capture, blackmail, and preparations raise suspicion;
- higher suspicion reduces PP gain, reducing the player's ability to keep acting at the same tempo;
- reducing suspicion requires active concessions such as lying low, burning assets, sacrificing contacts, disinformation, or spending political/economic resources;
- suspicion should not automatically decay every week, because passive decay turns the mechanic into waiting rather than strategy.

The two succession paths use the same scale but interact with it differently:

- Shabrata: smaller clandestine network, sharper high-risk actions, stronger tools for deception and compartmentalization.
- Party: larger institutional footprint, slower actions, more capacity to redirect investigations through bureaucracy, appointments, and scapegoats.

Thresholds should primarily unlock consequences and decision variants rather than pile on extra arbitrary modifiers. Suggested bands remain 0-24 / 25-49 / 50-69 / 70-89 / 90-100.

## Cleanup scope

Remove or rewrite STP-specific artifacts that support the abandoned dual-rate/mirrored-health architecture or obsolete army-lock migration logic. Preserve the authored starting division restriction, its player-facing tooltip, the minimal lock/unlock API, and the one-copy Capital Guard rule. Do not refactor unrelated StepanLand focus content.
