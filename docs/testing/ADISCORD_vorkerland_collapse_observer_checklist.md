# Vorkerland collapse observer checklist

## Normal campaign flow

1. Start the campaign and remain in observer mode.
2. Wait for the Unity Tower explosion and the collapse event.
3. Confirm that VAD and ZAO break apart through ordinary country releases and wars.
4. Confirm that the conflict remains AI-driven and advances through consolidation, regional, and endgame phases.
5. Confirm that one ending fires only after a contender has held its required states continuously for 98 days.
6. If nobody wins, confirm that the fragmentation ending fires after 1080 days.

## Dirty Zone

1. After the collapse begins, confirm that the Dirty Zone remains closed for exactly 1095 days.
2. Confirm that the opening superevent fires once, then SLA, MLR, RZA, SCA, ERT, and IRT appear one at a time over the following 11 days.
3. Confirm that every contaminated state keeps the permanent contaminated modifier.
4. Confirm that state 23 remains untouched and that no Dirty Zone country enters the Vorkerland war automatically.

## Outcome maps

- Worker victory: WRK controls the central territory; the regional republics survive as autonomies.
- Vlad victory: VAD restores the central military order; regional tags become military districts.
- Dorian victory: TVA controls the metropolitan core; EYR and the technical republics form the new dependency map.
- Fragmentation: all scripted internal wars end without redrawing the current front lines.

## Debug shortcuts

Use the console command `event ADISCORD_vorkerland_collapse.<id>` with:

- `1` - start the collapse sequence.
- `85` - open the Dirty Zone sequence after its three-year scheduling flag has been set.
- `20` - Worker victory.
- `21` - Vlad victory.
- `22` - Dorian victory.
- `23` - fragmentation.

After each run, inspect `error.log`, `game.log`, and `executed_commands.log` for new errors tied to `ADISCORD_vorkerland_collapse`.

## Worx's postwar directorate

The authoring source is `focus_trees/Vorkerland/technical_directorate/focuses.txt`.
Its 120 focuses include 13 exclusive pairs. The original 32-focus foundation
continues into 12 political, 16 scientific, 14 industrial, 14 military,
16 social and 16 foreign-policy focuses. The additional branches are optional
for entry into the western war. The existing 180-day reconstruction gate remains.
These are alternatives across several campaigns, not 120 sequential completions.
Scientific, industrial, military and social choices retain separate descendants
for several stages. Their conclusions may require both parallel programmes
within the chosen course. Descendants inherit their route's exclusion without
repeating it at each tier. AI plans must include a reachable prerequisite for every listed focus.

New programmes use the existing laboratory slot and receipt. Operation IDs
12-19 cover archive review, clinical trials, tooling, rehabilitation, assault
conditioning, clinics, population records and corridor depots respectively.
Personal-rule programmes consume their paid manpower and equipment at completion.
Cancellation refunds exactly the original payment and cannot refund another order.
Non-experimental programmes remain usable under council oversight.

The political course sets `WRK_worx_growth`; institutional choices accumulate
`WRK_worx_growth_bonus`. The daily pulse consumes both, while the existing gauge
shows their sum through `WRK_worx_growth_total`. Changing the political course
must preserve earlier institutional pressure. Council oversight stops both.

Story events `ADISCORD_vorkerland_postwar.31` through `.50` add personal scenes
and institutional consequences. The existing country pulse advances the three
one-time madness stages at 25, 50 and 75 before settling a crisis. Deliveries
recording a scientific result increment `WRK_worx_total_results`; counts 1, 3 and 6
dispatch distinct scenes, independently of the resetting demand counter.
Payment, cancellation, archive reviews and civilian work do not increment it.
Clinics, rehabilitation and assault conditioning deliver their rewards before
dispatching optional scenes. Open event windows cannot suspend the clock.
Each scene has an unconditional close option; personal-rule choices recheck
authority when selected. Narrative variants describe council supervision,
laboratory access, current subject terms and the final madness level.

For a later native check, record the loaded source hashes and start a new campaign:

1. Open the directorate tree and inspect all seven regions, names, icons and links.
   Check the two-factory choice with and without a controlled state with a free slot.
2. Select a pressure-increasing research focus before the political choice.
   Check the gauge immediately after each completion and after the next daily pulse.
3. Start each new programme at exact affordability, then repeat with a fractional
   manpower or equipment shortage. Compare payment, full-duration delivery and refund.
4. Save and load an active programme. Cancel through subjugation, capitulation,
   government change and the emergency ultimatum; verify all deposits and the slot.
5. Complete oversight during an experimental series. Verify cancellation, then
   complete clinics or rehabilitation without restarting madness.
6. Complete tooling, clinic and corridor upgrades during paid work. Check the
   final stockpile delta, then verify that no delayed callback delivers twice.
7. Follow both constitutional endings and both western settlements. Check that
   the AI selects only one alternative in each exclusive pair and that war entry
   still uses the existing scripted campaign.
8. Cross each madness threshold, reduce madness and cross it again. Each stage
   must appear only once. Leave a scene open across a crisis and across oversight:
   the clock must continue and a stale choice must not restore personal powers.
9. Compare one cancelled series with six delivered series. Only completed
   experiments count toward the three result scenes. Save/load must preserve
   the counter, stage and queued events.
10. Read both laboratory and settlement variants and all three final descriptions.
    Check the last visible line, every option and the event picture in a fresh
    screenshot. Static character and UTF-8 byte ceilings do not prove rendering.

Static contracts:

```powershell
python -B -m unittest tools.tests.test_vorkerland_worx_madness tools.tests.test_adiscord_vorkerland_vad_postwar.RouteTreeTests
```

These model tests do not prove native loading, layout, campaign balance or AI behaviour.
