# Scripted peace: ownership and runtime checks

## Contracts

Country-specific treaties run in `09_ADISCORD_scripted_peace_on_actions.txt`.
The generic full-annex fallback remains in the last `ZZ` on-action and honours
`skip_default_capitulation`. Do not replace bounded treaties with this fallback.

The fallback freezes defeated participants and their owned states before any
white peace or annexation. Neutral faction members do not block a war they never
joined. An active, undefeated faction cobelligerent does block final settlement,
including a liberated partner. An unrelated parallel enemy is not part of the
award. The final transfer includes impassable owned remnants, not neighbours'
cores or an unrestricted map scan. Arrays are temporary to the callback.

Kefreyt's frontier uses its real selected-target war for all invitations. Native
`on_war_relation_added` records entrants whose relation was not visible inside
the requesting effect. One hidden, target-bound event confirms entry after an
hour; it is not a repeating world poll. Failed declarations close the campaign.
A requested ally is not removed from the campaign by a second same-tick check.

The eastern ERT campaign still awards only state 168 to VAL when its existing
conditions authorize the award. RUS's separate victory can annex the rest of ERT.
This is an authored bounded treaty, not a reason to annex all ERT for VAL or to
repaint the exclusion zone. STP/STS versus VAL, the Occidian package (including
45), the northern 17/18 settlement and NAM's partition keep their existing rules.

## In-game controls

Launch with `-debug`. Decisions → **DEBUG: A-Discord Scenarios**. The added war
controls are free, human-only and have zero AI weight. Use a disposable save:
these are real diplomacy/occupation effects, not a rollback system.

1. Enable **Peace Trace** and create a manual **War and Territory State** snapshot.
   Find `[ADISCORD_PEACE]` in `logs/game.log`. Callback records distinguish native
   ROOT/FROM from capital occupation. State records name owner and controller.
2. **Raw War** isolates the default annexation path; it deliberately does not
   initialize a national story. **Join Alliance** is separate from **Join Wars**
   so a neutral faction member and a real cobelligerent can be tested separately.
3. **Test Major** can make each generic test participant mandatory before combat.
   The removal control only reverses a setting added by that debug button. Never
   remove it during a story campaign that now relies on the country being major.
4. **Occupy Capital** or **Occupy Owned States** changes control, not ownership.
   Advance simulation time for native capitulation. These buttons do not write
   defeat receipts or call victory effects.
5. **Restore Occupied States** releases only land occupied by the acting country
   or its subjects. Advance time and check that a living/restored partner again
   blocks final peace. It cannot resurrect an already annexed country.
6. **White Peace** is emergency cleanup, not a success test: native faction/subject
   war relations may also end. For VAL, **Abort Frontier Test** uses the campaign's
   cleanup. Reload the pre-war save to replay identical territorial conditions.

As VAL, **Start Frontier War** skips the ultimatum/refusal but calls the actual
campaign. It requires the real post-Stelander-war condition and valid territory;
it does not forge a civil-war outcome. **Recheck Frontier Treaty** runs the
existing checks without granting a victory or marking anyone defeated.

## Runtime matrix

| Scenario | Expected result |
|---|---|
| CIN/OSF/APH in each capitulation order | No missing defeated member in a generic final annexation. |
| Same faction, NOD neutral | Neutral NOD keeps its territory and cannot veto that peace. |
| Same faction, an active tribe survives | No final peace until its campaign condition is satisfied. |
| Defeated ally regains control before final defeat | Liberation blocks settlement again. |
| Neutral state / unrelated war with another enemy | No ownership award or war termination from the generic snapshot. |
| Remote or impassable owned state | Included in the generic full-annex award. |
| Real VAL frontier coalition | All requested entrants appear on the selected target's war, not parallel wars. |
| VAL claims 168 while RUS defeats ERT | Existing bounded claim and foreign occupation guards remain effective. |
| Explicit VAL abort / externally ended war | No victory reward; campaign memberships/temporary majors clean up. |

For an unexpected eastern transfer, capture snapshots immediately before and
after capitulation. Identify the state ID, pre/post owner and controller, active
VAL target/stage, and native callback ROOT/FROM. A colour change alone cannot
identify which treaty or map-reveal script transferred ownership.

## Automated verification

```bash
python -B -m unittest tools.tests.test_scripted_peace_on_actions \
  tools.tests.test_validate_adiscord_val_rework.ValFrontierCampaignTests \
  tools.tests.test_adiscord_nod_capitulation_reservation \
  tools.tests.test_vorkerland_claimant_cleanup
python -B -m unittest discover -s tools/tests
python -B tools/validate_tc.py --limit 300
git diff --check
```

The generic fixture deliberately allows a white peace to remove a whole faction's
relations, and annexation to leave an impassable remainder. It executes parsed
production code against those facts; it is not the HOI4 engine. Structural tests
cover queued entry, native registration, target-bound confirmation and debug
localisation. In-game callback timing, UI rendering and map colours still require
the runtime matrix above.
