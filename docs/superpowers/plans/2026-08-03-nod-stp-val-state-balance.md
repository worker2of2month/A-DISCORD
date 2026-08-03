# NOD, STP and VAL State Balance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved population, VP, industry, custom-building, infrastructure, and resource balance for the starting states of NOD, STP, and VAL.

**Architecture:** Keep game data in the existing hand-authored state files and Russian VP localisation. Add a small Python manifest as the single source for exact balance expectations and a focused validator that parses the live files; teach the existing global state validator about the nine explicitly approved non-urban settlement VPs.

**Tech Stack:** Hearts of Iron IV Clausewitz state history and localisation, Python 3 standard library validators, existing `tools/validate_tc.py` gate.

## Global Constraints

- Preserve the final population order `STP > VAL > NOD` with exact totals NOD 11,010,000, STP 16,380,000, and VAL 11,290,000.
- Add exactly one `ADISCORD_industrial_cluster` and one `ADISCORD_business_center` to states 30, 28, and 48; add no other custom building types.
- Add only the nine approved non-urban 1-VP settlements and raise the eight approved urban VPs below 5 to exactly 5; do not lower existing VPs.
- Preserve STP resources and concentrate 56 of VAL's 68 resource units in states 42 and 55.
- Preserve owners, cores, claims, forts, dams, ports, naval bases, and resources not explicitly changed by the approved design.
- Keep `localisation/russian/victory_points_l_russian.yml` as UTF-8 with BOM and one key per VP id.
- Do not modify or stage the user's existing `map/railways.txt` and `map/supply_nodes.txt` changes.

---

### Task 1: Add an executable balance contract

**Files:**
- Create: `tools/adiscord_core_state_balance_manifest.py`
- Create: `tools/validate_adiscord_core_state_balance.py`
- Modify: `tools/validate_adiscord_new_states.py`

**Interfaces:**
- Produces: exact dictionaries for target population/category, VP placement/value, capital custom buildings, industry totals, and VAL/STP resources.
- Produces: `python tools/validate_adiscord_core_state_balance.py`, returning 0 only when the approved state contract is satisfied.
- Updates: global VP validation to allow only `{14, 22, 34, 45, 70, 110, 125, 9126, 9617}` as non-urban settlement VPs.

- [ ] **Step 1: Create the exact manifest**

Define the approved state-path map, all 26 population values and four category changes, the nine `NON_URBAN_SETTLEMENT_VPS`, eight urban VP floors, expected factory totals, capital custom-building states, resource dictionaries for VAL states 24/42/54/55, and unchanged STP resource totals.

- [ ] **Step 2: Create the focused validator**

Implement balanced-brace block extraction and checks for owners/cores/claims, exact population/category values, one state-level `buildings` block, building and resource counts, province membership/terrain, VP values, UTF-8 BOM/localisation uniqueness, and national totals.

- [ ] **Step 3: Run the validator and confirm RED**

Run: `python tools/validate_adiscord_core_state_balance.py`

Expected: non-zero exit with mismatches for current population, missing settlement VPs, missing custom buildings, industry totals, and resource placement.

- [ ] **Step 4: Permit only the approved non-urban VPs in the global validator**

Import `NON_URBAN_SETTLEMENT_VPS` into `tools/validate_adiscord_new_states.py` and change the global terrain assertion to accept a VP when the province terrain is `urban` or the province id is in the approved set. Retain rejection for every other non-urban VP.

- [ ] **Step 5: Syntax-check validator code**

Run: `python -m py_compile tools/adiscord_core_state_balance_manifest.py tools/validate_adiscord_core_state_balance.py tools/validate_adiscord_new_states.py`

Expected: exit 0.

- [ ] **Step 6: Commit the contract**

```powershell
git add -- tools/adiscord_core_state_balance_manifest.py tools/validate_adiscord_core_state_balance.py tools/validate_adiscord_new_states.py
git commit -m "test: define core state balance contract"
```

### Task 2: Apply approved population and category values

**Files:**
- Modify: the 26 state files listed in `docs/superpowers/specs/2026-08-03-nod-stp-val-state-balance-design.md` under “Население и категории штатов”.

**Interfaces:**
- Consumes: `TARGET_STATES` from `tools/adiscord_core_state_balance_manifest.py`.
- Produces: exact national totals NOD 11,010,000, STP 16,380,000, VAL 11,290,000.

- [ ] **Step 1: Patch all `manpower` values**

Apply the exact per-state target values from the approved spec; do not touch province lists, owners, cores, claims, resources, or buildings in this step.

- [ ] **Step 2: Patch four state categories**

Set state 11 to `city`, state 2 to `city`, state 46 to `town`, and state 168 to `town`; retain every other current category.

- [ ] **Step 3: Run the focused validator**

Run: `python tools/validate_adiscord_core_state_balance.py`

Expected: population/category errors are absent; VP, industry, custom-building, and resource errors remain.

- [ ] **Step 4: Inspect the scoped diff**

Run: `git diff -- history/states`

Expected: this task changes only `manpower` and the four approved `state_category` values.

- [ ] **Step 5: Commit demographics**

Stage exactly the 26 target state files and commit with `balance: revise NOD STP VAL population`.

### Task 3: Implement the VP hierarchy and Russian names

**Files:**
- Modify: states 10, 17, 18, 3, 53, 88, 24, 42, 55, 12, 13, 44, 54, 56, and 168 under `history/states/`.
- Modify: `localisation/russian/victory_points_l_russian.yml`

**Interfaces:**
- Consumes: `NON_URBAN_SETTLEMENT_VPS` and `URBAN_VP_MINIMUMS` from the manifest.
- Produces: new VPs `{22,34,14,45,70,110,9126,125,9617}` at value 1 and urban VP floor 5 for `{16448,16644,16647,16652,9395,16534,16653,16645}`.

- [ ] **Step 1: Add nine settlement VPs**

Add one `victory_points = { province 1 }` entry to the matching state history for each manifest mapping, without adding a second VP to those states.

- [ ] **Step 2: Raise eight urban VPs**

Change only the listed VP values from 1/3 to 5; preserve every existing VP at 5 or above.

- [ ] **Step 3: Update Russian localisation**

Add unique keys for provinces 14, 22, 34, 70, 125, 9126, and 9617; retain existing keys for 45 and 110; rename `VICTORY_POINTS_16356` to `Остриум`. Preserve UTF-8 BOM.

- [ ] **Step 4: Run focused and global VP validation**

Run:

```powershell
python tools/validate_adiscord_core_state_balance.py
python tools/validate_adiscord_new_states.py
```

Expected: no VP or localisation errors; focused validator still reports only industry/custom-building/resource mismatches.

- [ ] **Step 5: Commit VP data**

Stage only the listed state files, localisation, and any validator adjustment required by observed parser behavior; commit with `balance: add settlement victory points`.

### Task 4: Apply moderate industry, custom-building, infrastructure, and resource balance

**Files:**
- Modify: `history/states/10-Ashya.txt`
- Modify: `history/states/11-Ostrium.txt`
- Modify: `history/states/12-Kaclana.txt`
- Modify: `history/states/13-Treya.txt`
- Modify: `history/states/24-Irem.txt`
- Modify: `history/states/28-Fada.txt`
- Modify: `history/states/30-Cussington.txt`
- Modify: `history/states/42-Prigranichie.txt`
- Modify: `history/states/48-Depoitodron.txt`
- Modify: `history/states/54-Spastlant.txt`
- Modify: `history/states/55-Erstantpeo.txt`

**Interfaces:**
- Produces: factory totals NOD 8/6/1, STP 20/7/3, VAL 10/12/0 in civilian/military/dockyard order.
- Produces: one business center and one industrial cluster in each of states 30, 28, 48.
- Produces: VAL resources state 42 `{steel: 20, tungsten: 12}`, state 55 `{oil: 12, chromium: 12}`, state 24 `{oil: 7}`, state 54 `{steel: 5}`.

- [ ] **Step 1: Patch NOD industry**

Set state 11 to infrastructure 3 plus 2 civilian/1 military factories; add 2 civilian/1 military to state 10; add 1 civilian/1 military to states 12 and 13.

- [ ] **Step 2: Consolidate Cussington buildings**

Replace the two state-level `buildings` blocks with one block containing infrastructure 5, 2 civilian factories, 2 military factories, 1 dockyard, province 12434 naval base 5, and the two approved custom buildings.

- [ ] **Step 3: Add capital custom buildings**

Add one `ADISCORD_business_center` and one `ADISCORD_industrial_cluster` to the existing state-level building blocks in states 28 and 48. Add 2 civilian factories to state 48.

- [ ] **Step 4: Patch border infrastructure and VAL resources**

Set state 42 and 55 infrastructure to 2 and replace only resource values in states 24/42/54/55 with the exact manifest dictionaries.

- [ ] **Step 5: Run the focused validator and confirm GREEN**

Run: `python tools/validate_adiscord_core_state_balance.py`

Expected: `Core state balance validation passed` and exit 0.

- [ ] **Step 6: Commit gameplay balance**

Stage only the listed state files and commit with `balance: tune NOD STP VAL starting states`.

### Task 5: Full static and runtime verification

**Files:**
- Verify only; do not modify unrelated files unless a failing check proves an in-scope defect.

**Interfaces:**
- Consumes: all state/localisation/validator changes from Tasks 1-4.
- Produces: static validation evidence and, when the local game runtime is available, fresh game/log evidence.

- [ ] **Step 1: Run focused validation**

Run: `python tools/validate_adiscord_core_state_balance.py`

Expected: pass.

- [ ] **Step 2: Run global map/state validation**

Run:

```powershell
python tools/validate_tc.py --limit 300
python tools/validate_adiscord_new_states.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Inspect commit and dirty-work boundaries**

Run: `git status --short` and inspect each implementation commit with `git show --stat --oneline HEAD` plus the preceding implementation commits.

Expected: `map/railways.txt` and `map/supply_nodes.txt` remain modified but uncommitted; no unrelated path appears in balance commits.

- [ ] **Step 4: Launch a fresh game when available**

Start Hearts of Iron IV with A-Discord enabled, begin a new game, and inspect NOD/STP/VAL state population, categories, VP values, factory totals, and the six custom buildings. Close the game after the checks.

- [ ] **Step 5: Inspect fresh logs**

Check fresh `error.log` and `game.log` for state-history parse errors, unknown building ids, duplicate localisation, invalid VP placement, and missing localisation. Do not claim runtime completion if a fresh launch cannot be performed.
