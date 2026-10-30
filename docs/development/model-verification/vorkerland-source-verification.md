# Vorkerland source verification

Source snapshot: [vorkerland-source-manifest.json](vorkerland-source-manifest.json).
This report does not certify native loading, event rendering or campaign balance.

## Automated coverage

- All 32 Vorkerland test modules, focus builder tests, shared peace ownership
  tests and 32 difficulty behavior tests: 1007 passed.
- All seven Vorkerland focus authoring sources match their generated trees.
- Gameplay scripts are UTF-8 without BOM; country localisation retains UTF-8 BOM.
- `git -c core.safecrlf=false diff --check` passes.
- `tools/validate_tc.py --limit 300`: all 29 structural sections report zero
  issues; 11 existing informational vanilla-token matches remain.
- Independent review found no actionable issues; its 47 focused tests passed.
- Two additional difficulty tests concerning southern-war preparation fail on
  `ADISCORD_south_preparing_country`, unsupported by their test interpreter.
  They are outside this country verification; their implementation is unchanged.

The focus UI test validates its own builder, inputs and outputs. It does not
certify the entire generated-output registry: the unrelated STP portrait family
references original artwork absent from this checkout.

The institution-loss tests reject removal of absent array members. Pending
railway councils and district administrations must still refund their receipts
and release their slots when no completed registry entry exists.

## Manual acceptance in a new campaign

Fully restart the game with the recorded sources before testing. Existing logs
and saves predate this snapshot and cannot verify it. Do not use an older campaign.

1. Open preparation, VAD and TVA trees at several zoom levels. Check card spacing,
   labels, prerequisites and exclusive links. After the actual civil-war side
   choice, preparation must disappear and the selected wartime tree must load.
2. Complete a normal preparation route without forced focus completion. Verify
   that paid formations and equipment reach the chosen country at the split,
   and no delayed preparation callback pays twice after the handoff.
3. Rescue Worker and choose the joint-government focus. Rescue alone must not
   appoint the council. Check the joint portrait, formation news, exclusive
   congress/operations focuses and their paid programmes. Check unrest reduction
   for congress and the temporary wartime reward for operations.
4. In a separate run without rescue, choose Petrichev's collegial staff. Verify
   its leader, news and military-republic constitution. Imperial reclamation must
   remain unavailable to the joint and collegial courses.
5. Trigger district unrest: both paid suppression and withdrawal must resolve
   the local crisis. Check before/after resources, modifiers and renewed local
   availability. Lose a district while its institution is still being built;
   check one refund, released capacity and no invalid-array error.
6. Reach the joint postwar choice. Preserving the cabinet must publish the
   survival news. Worker's coup must report Petrichev's execution. Petrichev's
   own imperial route must not report his death. Check foreign-observer versions,
   repeat prevention and an event left unanswered until timeout.
7. Test foreign guarantees and observers with acceptance, refusal, timeout and
   loss of eligibility. Verify payment/refund once, the intended recipient and
   actual coalition membership in the same war.
8. Check full descriptions, final lines, pictures and every answer in short and
   long events. Inspect fresh error/game logs after loading and these transitions.
   Ordinary save/load during a paid operation must preserve its receipt and term.

Native force distribution, front behavior, event delivery and UI geometry remain
unverified until these manual checks are performed against the recorded sources.
