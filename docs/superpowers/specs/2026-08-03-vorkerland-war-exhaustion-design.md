# Vorkerland Civil-War Exhaustion Design

## Goal

Restore a separate, player-visible war-exhaustion system for WRK and VAD that responds to both the duration of their direct war and each side's own new casualties, without adding a daily global loop or penalties that freeze the front.

## Reference model

The local The Fire Rises 1.0.8.3 installation at Steam Workshop item `3350890356` uses recurring timed missions and one variable-backed dynamic modifier. Its SOV mission ticks every 150 days; its PRC mission ticks every 200 days. The PRC increment is `-0.015` war support/attack/defence, `-0.01` organisation, `-0.02` recovery, and `-0.005` surrender limit per timeout. TFR does not derive these increments from casualties.

A-Discord will retain the efficient TFR shape—an infrequent tick feeding one dynamic modifier—but use A-Discord's existing safe casualty-delta pattern (`casualties_k` minus a stored snapshot) rather than charging lifetime casualties repeatedly.

## Data flow

The existing Vorkerland `on_monthly` hook calls one update effect only for country scopes WRK and VAD after the collapse has begun or while a saved exhaustion value remains. No `on_daily`, `every_country`, or `every_state` loop is added.

Each country stores its own values under the same keys:

- `ADISCORD_vorkerland_civil_war_exhaustion`: score from 0 to 100.
- `ADISCORD_vorkerland_civil_war_casualties_snapshot_k`: previous cumulative `casualties_k`.
- `ADISCORD_vorkerland_civil_war_casualties_delta_k`: non-negative monthly delta.
- Derived modifier variables and a 0–4 display level.

During a direct WRK–VAD war, the score gains 2 per month plus 1/3/6 when that country's new monthly casualties reach 5/25/100 thousand. Outside that direct war, the score falls by 8 per month. The casualty snapshot is refreshed in both states so old losses cannot be charged in a later war. All score and delta values are clamped.

## Gameplay effect

One dynamic national modifier reads derived variables recalculated from the score. At score 100 it reaches:

- `war_support_factor = -0.20`
- `stability_factor = -0.10`
- `industrial_capacity_factory = -0.10`
- `army_morale_factor = -0.05`
- `surrender_limit = -0.10`

Attack and organisation are deliberately not reduced. The modifier is added above score zero, force-refreshed after updates, and removed when recovery reaches zero.

## Player and debug surface

Russian localisation names the modifier "Истощение гражданской войны" and displays the current country-scoped score out of 100. The existing debug-only scenario category gains two AI-disabled WRK/VAD decisions: add 25 exhaustion and reset the score/snapshot/modifier.

## Verification

The Vorkerland validator receives an `exhaustion` section. Focused tests must prove country-scoped monthly routing, casualty snapshots and thresholds, peace recovery, 0–100 clamps, absence of global/daily loops and attack/organisation penalties, debug isolation, and UTF-8 BOM localisation. The broader Vorkerland validator and total-conversion validator remain required final gates.
