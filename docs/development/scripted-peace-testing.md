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

A capitulated subject remains occupied while its living overlord is at war with
the credited victor, even outside a shared faction. A neutral overlord does not
block settlement. The overlord's final defeat includes its already defeated
subjects in the generic snapshot.

Kefreyt's war against YPR, COF and TFF reserves the campaign before declaring on
YPR. Two one-shot hourly callbacks let the declaration and then the invitations
reach native diplomacy before confirming entry. Daily reconciliation preserves
this pending entry. Failed entry ends the partial campaign without awards and
clears only major status added by this campaign. All three defenders must fall
before the common administration treaty, including when COF capitulates last.

Kefreyt's Nodrul, Stelander and northern-coalition administrations close each
participating VAL subject's war relation before the relation with VAL itself.
The victors execute the white peace so native callbacks retain the correct side.
Faction removal and autonomy changes follow this cleanup. Separate enemies stay
at war. Verify both pairwise peace and peace that ends a whole merged war;
assuming every white peace removes all client relations can hide a conference
left open for the clients.

`VAL_PEACE_TRACE diagnostics_loaded` confirms the diagnostic hooks were loaded.
The event-only trace records native immediate/late capitulation, loss of the
last war, campaign closure and the boundary before a VAL peace conference.
Each country snapshot prints true predicates only; omitted booleans are false.
Conference callbacks use winner ROOT and loser FROM, the reverse of capitulation.
Capture the trace before applying manual administration decisions: those use
the settlement effects directly and cannot prove the automatic route ran.
These records observe the failure; they do not suppress a native conference.

The Party's postwar victory over Kefreyt uses the same subject treaty whether
STP launched its own operation or defeated a Kefreyt invasion. The immediate
callback requires the live STP-VAL war and victory credit for STP or its subject.
Both STP and VAL must be independent, and STP must qualify for postwar
reconstruction before the callback reserves the result or alters the peace.
The delayed subject settlement rechecks these conditions.
Its receipt protects VAL from generic annexation through the late callback;
subject creation follows the technical peace after the faction cache advances.
Test both initiators and an unrelated victor without granting STP that victory.

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

Shabrat's hegemony imposes provisional administrations after a repeated victory
over NOD or VAL, or victory in the campaign unlocked by a refused dependency
demand. The first limited peace leaves the defeated government independent.
Kefreyt's first peace returns the Stelander Islands (709) when owned by VAL or
its subject, alongside the existing mainland package. Its captured northern
subjects change overlord to STS. Annexed tribal land in 58-65 restores the original
tribes, or joins the existing transferred NKA, including the captured resource
belt. Independent tribes, foreign-owned land and third-party occupation are
excluded from this northern award. Snapshot occupation before technical peace.

The late final wars retain their provisional administrations. In the hegemony
route, the defeated Kefreyt council also survives its revanche as a subject.
The surviving country must be an STS subject; a defeat receipt alone is
insufficient. Full integration remains the existing paid 90-day decision.
Verify both first/second-war sequences, refused-demand campaigns, the islands,
separate tribes and NKA, unrelated wars, and the distinct liberation outcome.

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

NAM records a current resource-war enemy's capitulation from either native
recipient credit or occupation of that enemy's capital by NAM or its subject.
Both native capitulation callbacks use the same recorder, with the late one
running before generic annexation. Verify EFL-first and AZH-first defeats,
different native recipient credit, liberation of the first defeated ally, and
unrelated third-party victories. The treaty preserves EFL and AZH and their
faction, awards only 691/701 to NAM, and adds its existing claim to 69.

The final VAL capitulation receipt has an explicit nonzero value and remains
valid through the late callback's settlement attempt. The accepted defeat in
`VAL_final_defeat_pending` survives later reconciliation while that country
remains in the same war: native `has_capitulated` may still be false. Native
`on_uncapitulation` invalidates that defeat and any Ainholm occupation snapshot;
external peace, annexation and foreign subjugation also invalidate it. A committed
coalition settlement survives the technical peace and liberation callbacks it
causes itself. `[VAL_PEACE]` records native entry, accepted defeat, liberation and
administration installation in ordinary release logs.
An unfinished frontier offer does not
reserve a separate NOD defeat once VAL has no active war with the frontier targets.

After NOD's northern victory, VAL can negotiate with an independent TFF before
the final operation. NOD's settlement creates four contiguous administrations:
NOD (10/11/12/30), ECA (13/17/18, plus defeated-bloc 14), YPR (19/20/21/22), and
DCA (8/15/16). State ownership and control are captured before white peace.
Independent YPR and foreign-controlled land are excluded. Thus a NOD defeat
after its **loss** in the northern war does not authorize annexing free Yubora.
ECA and DCA receive 40% of their respective predecessor's surviving army,
air force and stockpile; fleets stay with NOD/YPR. A replay does not split again.

The prewar agreement transfers both Yuboran administrations to TFF after victory.
Without agreement they remain VAL subjects; a surviving independent TFF sends a
21-day ultimatum. Acceptance, including timeout, transfers both subjects without
redrawing their borders. Refusal declares TFF's war against VAL and calls VAL's
subjects to that same war. Changed signatories or lost administrations invalidate
the offer safely. Debug country dumps include the receipt, active-ally blocker
and VAL frontier stage.

Test NOD-owned and NOD-subject Yubora, accepted/refused/no prewar offer, 14-day
offer timeout, 21-day ultimatum timeout, explicit refusal, TFF defeat/subjugation
before settlement, foreign occupation of 14/16, and a repeated administration
decision. Confirm owner, controller, overlord, focus tree and troop/stockpile
totals for all four administrations, and reload before the capitulation when
comparing outcomes. Source checks do not substitute for a cold-load campaign.

| Scenario | Expected result |
|---|---|
| CIN/OSF/APH in each capitulation order | No missing defeated member in a generic final annexation. |
| Same faction, NOD neutral | Neutral NOD keeps its territory and cannot veto that peace. |
| Same faction, an active tribe survives | No final peace until its campaign condition is satisfied. |
| Defeated ally regains control before final defeat | Liberation blocks settlement again. |
| Neutral state / unrelated war with another enemy | No ownership award or war termination from the generic snapshot. |
| Remote or impassable owned state | Included in the generic full-annex award. |
| Real VAL frontier coalition | All requested entrants appear on the selected target's war, not parallel wars. |
| VAL focus war against YPR/COF/TFF, every defeat order | All three join the same war and become contract administrations after the last defeat, without a native conference. |
| COF defeats a VAL subject outside VAL's faction | The subject remains occupied while VAL fights; no separate annexation or peace. |
| VAL claims 168 while RUS defeats ERT | Existing bounded claim and foreign occupation guards remain effective. |
| Explicit VAL abort / externally ended war | No victory reward; campaign memberships/temporary majors clean up. |

For an unexpected eastern transfer, capture snapshots immediately before and
after capitulation. Identify the state ID, pre/post owner and controller, active
VAL target/stage, and native callback ROOT/FROM. A colour change alone cannot
identify which treaty or map-reveal script transferred ownership.

## Automated verification

Transient native defeat receipts belong only to callback ROOT. They are reset at
the next immediate callback and consumed after the last country handler. Kefreyt's
accepted coalition defeats persist separately until settlement or a native
liberation/exit; a delayed native status must not erase them. A liberated ally
must block settlement again even when its transient receipt had not expired. Bezhaysk
participants and capital awards are captured before the first technical peace.
NAM and SHL reserve major status only when their campaign added it, and native
peace, annexation and subjugation clean up an externally interrupted campaign.
The southern final war also reserves major status for both champions only for
that campaign. A champion's capitulation settles every participant; other
defeated participants stay occupied until that settlement. Native peace,
annexation or subjugation outside it resolves the campaign by control of the
key districts, and the Restitution Alliance only repels it.
The western final war follows the same contract for reunified WRK and IVN. Its
`west_final` sections run after `south_final`; a champion's capitulation
settles every participant, and an external end resolves it by control of the
Old March, the Itoran frontier, the northern corridor and the WRK capital.

Also test both NOD/Stelander defeat orders, a surviving northern cobelligerent,
TFF joining NOD's northern war after YPR has capitulated, and failed TFF entry.
Deliberate frontier deferral must keep the northern campaign active. A foreign
puppet or independent participant leaving VAL's northern war cancels that
scripted campaign without territorial awards or ending the remaining wars.
Existing major status must survive every terminal path. RUS's six target wars,
NOD's Stelander victory and the exile return must accept the current native
defeat even before `has_capitulated` becomes visible.

`test_adiscord_peace_coalition_lifecycle` executes these production effects and
triggers with delayed capitulation and destructive peace side effects. Its
fixtures reject unknown instructions; presentation and economy effects are
explicit stubs. This is a script contract check, not native runtime acceptance.

```bash
python -B -m unittest tools.tests.test_scripted_peace_on_actions \
  tools.tests.test_adiscord_peace_coalition_lifecycle \
  tools.tests.test_validate_adiscord_val_rework.ValFrontierCampaignTests \
  tools.tests.test_adiscord_nod_capitulation_reservation \
  tools.tests.test_vorkerland_claimant_cleanup \
  tools.tests.test_adiscord_south_final_war \
  tools.tests.test_adiscord_west_final_war
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
