# Vorkerland collapse observer checklist

## Normal campaign flow

1. Start the campaign and remain in observer mode.
2. Wait for the Unity Tower explosion and the collapse event.
3. Confirm that VAD and ZAO break apart through ordinary country releases and wars.
4. Confirm that the conflict remains AI-driven and advances through consolidation, regional, and endgame phases.
5. Confirm that one ending fires only after a contender has held its required states continuously for 98 days.
6. If nobody wins, confirm that the fragmentation ending fires after 1080 days.

## Dirty Zone

1. After the collapse begins, wait 60–90 days for the Dirty Zone opening superevent.
2. Confirm that SLA and MLR appear first, RZA and SCA after 45 days, and ERT and IRT after another 45 days.
3. Confirm that every contaminated state keeps the permanent contaminated modifier.
4. Confirm that state 23 remains untouched and that no Dirty Zone country enters the Vorkerland war automatically.

## Outcome maps

- Worker victory: WRK controls the central territory; the regional republics survive as autonomies.
- Vlad victory: VAD restores the central military order; regional tags become military districts.
- Dorian victory: TVA controls the metropolitan core; EYR and the technical republics form the new dependency map.
- Fragmentation: all scripted internal wars end without redrawing the current front lines.

## Debug shortcuts

Use the console command `event ADISCORD_vorkerland_collapse.<id>` with:

- `1` — start the collapse sequence.
- `10` — open the Dirty Zone sequence.
- `20` — Worker victory.
- `21` — Vlad victory.
- `22` — Dorian victory.
- `23` — fragmentation.

After each run, inspect `error.log`, `game.log`, and `executed_commands.log` for new errors tied to `ADISCORD_vorkerland_collapse`.
