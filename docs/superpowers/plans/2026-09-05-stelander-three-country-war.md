# Stelander Three-Country War - integration plan and status

**Goal:** deliver a playable STP preparation loop followed by an actual three-country war between STP, STS and SRP, with separate NOD and VAL interventions.

**Acceptance basis:** new campaign in the installed mod checkout, focused static validation, full HOI4 restart, fresh logs and live progression through the timed branches. Preserve unrelated dirty work; do not stage or commit unless requested.

**Design reference:** `docs/superpowers/specs/2026-09-05-stelander-civil-war-loop-design.md`.

## Implemented scope

- [x] Add fixed STS and SRP tags, dormant histories, provisional flags and the template-only six-militia OOB. The brigade costs 6000 manpower and 480 infantry equipment; histories add no units, manpower or equipment.
- [x] Add a 28-focus STP preparation tree and automatic Shabrat opening. No other main human route is currently selectable.
- [x] Implement five illness stages as four 70-day missions with three one-day rearm callbacks (nominal `70 × 4 + 3`; engine mission ticks determine actual dates).
- [x] Make Ivanov's death start one 100-day election mission. Death does not automatically split the country.
- [x] Require a prepared uprising and a real NOD war with YPR or COF while elections remain active before the player can manually start the uprising.
- [x] Add two northern strategies: evidence/provocation for the NOD ultimatum and a paid 21-day shipment of 1200 rifles to YPR or COF.
- [x] Connect 14-day regional networks, paid 480-rifle caches, local assets, suspicion and the shared operation slot to the split outcome.
- [x] Create STP, STS and SRP through one guarded split; allocate 28 to STP, 1 to STS, 43/44/88 to SRP and settle 45 plus optional regions through shared outcome triggers.
- [x] Preserve Capital Guard, disband only regular/police formations with refunds, divide actual free manpower and transferable domestic stockpile 40/20/40, retain foreign stock with STP, and create only paid territorial brigades.
- [x] Start all three pairwise wars and perform the human handoff after setup.
- [x] Load the 12-focus `STP_cw_focus` tree for all three tags. Each tag sees six shared plus two tag-specific focuses, eight visible focuses total.
- [x] Add normal war controls and paid mobilisation for all three countries.
- [x] Add the 21-day NOD warning and limited join on STP's side against STS after the northern war ends.
- [x] Add VAL's accept/refuse offer, shared-operation reservation, SRP's 21-day ultimatum and real VAL–SRP declaration.
- [x] Add feature-specific capitulation routing with `skip_default_capitulation`, including exact VAL settlement of SRP-owned 43/44/88 and exclusion of state 45.
- [x] Add Russian localisation with UTF-8 BOM and reuse existing focus/decision icons. STS/SRP flags remain provisional and the final portrait is unknown.

## Verification status

- [x] Focused suites passed: 39 tests total (5 preparation, 18 core, 16 regions).
- [x] Independent static review found no remaining confirmed P1/P2 integration defect after fixes to external mission activation, singular `delete_unit` use and focus-tree loading for all three tags.
- [x] Live run started at 18:28 and exposed defects in `exists = TAG`, manpower handling, a parameterized helper and `receive 100`. These defects were repaired.
- [x] Live P2/P3 confirmed normal death, the 100-day election mission and an actual northern war.
- [x] Verify preparation resource lifecycle with focused tests and P2's real 480-rifle cache materialization. The final shared payment helper is separately runtime-proven by all twelve P4 brigade payments; individual cancel permutations are statically covered.
- [x] Live P4 confirmed 12 actual paid brigades (5 STP, 4 STS, 3 SRP), exact 6000 manpower/480-rifle cost for each, 221156 initial manpower conserved and 11184.30 rifles conserved. Domestic stock split 40/40/20; 2000 foreign-produced rifles remained with STP.
- [x] Live P4 confirmed VAL's 21-day path to an actual war and NOD's 21-day party-side join.
- [x] Live P4 confirmed the party-defeat result: STS annexed STP and NOD made white peace.
- [x] P6 confirmed VAL settlement: immediate occupier code 5; only 43/44/88 transferred and SRP retained 45. The subsequent STP defeat correctly chose STS (code 2) despite reported FROM=SRP.
- [x] Final clean campaign naturally reached death and election expiry without QA: opening 2160.10.12.02, expiry 2161.01.21.02; no split, preparation operations closed. These are actual engine dates for the configured 100-day mission, including its zero-day processing.
- [x] Live map, human handoff, preparation-tree layout and resistance forces checked; shared focus loading and per-tag visibility contracts pass static tests. Exhaustive playthroughs of every focus combination are not claimed.
- [x] Removed all three temporary loaded QA files; completed a full restart, fresh campaign and end-of-run log inspection without scoped STP/STS/SRP errors. Full validator and diff check passed. Final balance/art remain a later content pass.

## Stable rulings

- Fixed tags and three ordinary pairwise wars are the required model; no dynamic fourth country is created.
- The automatic opening selects Shabrat. Additional playable political routes and long postwar trees are later content.
- Death only opens the 100-day election window; it never triggers the split.
- Existing units are reorganised conservatively; the design does not promise deterministic transfer of a named live division.
- VAL can receive only 43, 44 and 88 from SRP. NOD restores STS to STP and receives no Stelander territory.
- Generic capitulation handling must not pre-empt these settlements or terminate unrelated wars.
