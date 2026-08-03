# Vlad Macri Victory Points Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Vlad Macri's Republic of Ebern a 10 VP capital, two 3 VP cities, and two distributed 1 VP railway settlements.

**Architecture:** Keep `tools/build_adiscord_new_states.py` authoritative for both generated and legacy state output. Extend the existing new-state validator with hand-derived EBA expectations, then update only the generator constants, narrow non-urban exception path, five state outputs, and BOM-safe Russian localisation.

**Tech Stack:** Python 3, HOI4 Clausewitz state files, YAML localisation with UTF-8 BOM, existing project validators.

## Global Constraints

- Preserve every unrelated dirty change in the checkout.
- Do not run the broad state generator over the working tree; patch only its intended outputs.
- Do not change population, buildings, resources, borders, ownership, or collapse logic.
- Keep Russian localisation encoded as UTF-8 with BOM.
- Static checks do not prove visual in-game placement.

---

### Task 1: Add and validate the Republic of Ebern VP network

**Files:**
- Modify: `tools/validate_adiscord_new_states.py`
- Modify: `tools/build_adiscord_new_states.py`
- Modify: `history/states/197-VLA-EAST.txt`
- Modify: `history/states/311-311.txt`
- Modify: `history/states/312-312.txt`
- Modify: `history/states/313-313.txt`
- Modify: `history/states/314-314.txt`
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_states_l_russian.yml`
- Modify: `localisation/russian/victory_points_l_russian.yml`

**Interfaces:**
- Consumes: `state_path(state_id: int) -> Path`, `VORKERLAND_CENTRES`, `VORKERLAND_LEGACY_VICTORY_POINTS`, `GENERATED_VICTORY_POINT_NAMES`, and `render_state(state_id: int, owner: str) -> str` from the existing builder.
- Produces: `VORKERLAND_MINOR_VPS: dict[int, tuple[int, int]]`, containing `{311: (5905, 1), 314: (5405, 1)}`; generated and legacy state files containing the approved VP layout.

- [x] **Step 1: Add the failing EBA output contract**

Add independent literal expectations near the validator constants:

```python
EBA_EXPECTED_VPS = {
    197: {16623: 10},
    311: {5905: 1},
    312: {16637: 3},
    313: {16617: 3},
    314: {5405: 1},
}
EBA_EXPECTED_VP_NAMES = {
    16623: "Эберн",
    5905: "Фельден",
    16637: "Нойен",
    16617: "Эстервик",
    5405: "Линден",
}
```

Inside `validate_states()`, parse each target state's real `victory_points` entries and assert every literal province/value pair. For generated states 311-314, also call `render_state` and assert that its output contains the same literal VP. Assert that each expected localisation key occurs exactly once with the expected Russian value.

- [x] **Step 2: Run the validator and verify the RED state**

Run:

```powershell
python -B tools/validate_adiscord_new_states.py
```

Expected: exit 1 with missing or wrong VP reports for province 16623 and states 311-314, plus missing localisation reports for 5905 and 5405. The failure must come from the new contract rather than an import or syntax error.

- [x] **Step 3: Add the authoritative generator data**

Update the builder with these exact data changes:

```python
VORKERLAND_CENTRES = {
    # existing entries remain
    312: (16637, 3),
    313: (16617, 3),
}

VORKERLAND_MINOR_VPS = {
    311: (5905, 1),
    314: (5405, 1),
}
```

Change state 197 in `VORKERLAND_LEGACY_VICTORY_POINTS` to `((16623, 10),)`. Set province 16623 to `Эберн`, keep 10016 as `Дальний пост`, and add names 5905 `Фельден`, 5405 `Линден`, 16617 `Эстервик`, and 16637 `Нойен` to `VORKERLAND_VICTORY_POINT_NAMES`.

In `render_state`, combine `VORKERLAND_MINOR_VPS` into `centres` and emit a VP when its province is urban or its state/value pair is the exact entry in `VORKERLAND_MINOR_VPS`. Continue raising when the configured province is outside its state.

- [x] **Step 4: Teach the validator the narrow non-urban exception**

Import `VORKERLAND_MINOR_VPS`. Add its province IDs to `APPROVED_NON_URBAN_SETTLEMENT_VPS`, include it in the combined `centres`, and treat an approved non-urban centre like an urban centre for presence and localisation checks. Continue rejecting every non-urban VP not in the approved set.

- [x] **Step 5: Update only the five state outputs and two new localisation keys**

Apply these exact output changes without running the broad builder:

```text
state 197: victory_points = { 16623 10 }
state 311: victory_points = { 5905 1 }
state 312: victory_points = { 16637 3 }
state 313: victory_points = { 16617 3 }
state 314: victory_points = { 5405 1 }
```

Ensure the localisation file has one exact entry for every expected VP name, including:

```yaml
 VICTORY_POINTS_5905: "Фельден"
 VICTORY_POINTS_5405: "Линден"
```

Remove the stale duplicate `VICTORY_POINTS_10016: "Дальний пост"` from `ADISCORD_vorkerland_collapse_states_l_russian.yml`; keep the authoritative keys `VICTORY_POINTS_10016: "Дальний пост"` and `VICTORY_POINTS_16623: "Эберн"` in the VP localisation file.

- [x] **Step 6: Run focused GREEN verification**

Run:

```powershell
python -B tools/validate_adiscord_new_states.py
python -B tools/validate_adiscord_vorkerland_collapse.py
```

Expected: both exit 0. If the broader Vorkerland validator reports a pre-existing unrelated failure, record the exact message and verify that none references states 197 or 311-314, the five VP provinces, or EBA.

An initial baseline run reported `TGD/VLA/EBA peripheral rivalry triangle is missing`; it checked the scripted regional-rival trigger rather than state VP data. A fresh final run passed after unrelated concurrent working-tree changes; this VP task did not edit that trigger.

- [x] **Step 7: Run repository map checks**

Run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check -- tools/build_adiscord_new_states.py tools/validate_adiscord_new_states.py history/states/197-VLA-EAST.txt history/states/311-311.txt history/states/312-312.txt history/states/313-313.txt history/states/314-314.txt localisation/russian/victory_points_l_russian.yml
```

Expected: the validator exits 0 or reports only separately identified baseline errors outside the EBA VP scope; `git diff --check` exits 0. Verify `victory_points_l_russian.yml` still starts with bytes `EF BB BF`.

- [x] **Step 8: Review scope without committing overlapping dirty files**

Inspect the exact targeted hunks with `git diff --` for all files above. Do not stage or commit the implementation because these files already contain unrelated uncommitted work; report the modified files and verification evidence instead.
