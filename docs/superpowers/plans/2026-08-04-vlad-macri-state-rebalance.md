# Vlad Macri State Rebalance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebalance all five Republic of Ebern states to 3.55 million population, 7/2 factories, improved infrastructure and supply, and a distributed four-division collapse force.

**Architecture:** Extend the existing new-state validator with literal state-profile expectations and generator-output checks. Extend the Vorkerland unit and standalone validators with exact EBA reserve and deployment contracts, then update only the authoritative builder, five state outputs, EBA OOB, and EBA setup block.

**Tech Stack:** Python 3, `unittest`, HOI4 Clausewitz state/OOB/script files, existing A-Discord validators.

## Global Constraints

- Preserve unrelated dirty changes in every overlapping file.
- Do not run `tools/build_adiscord_new_states.py` over the working tree.
- Do not change resources, borders, ownership, cores, VP values, diplomacy, ideology, division count, templates, or equipment types.
- Accept the population/development increase for pre-collapse WRK state 311 and VLA states 197 and 312-314.
- Do not stage or commit overlapping implementation files.

---

### Task 1: State population and development profiles

**Files:**
- Modify: `tools/validate_adiscord_new_states.py`
- Modify: `tools/build_adiscord_new_states.py`
- Modify: `history/states/197-VLA-EAST.txt`
- Modify: `history/states/311-311.txt`
- Modify: `history/states/312-312.txt`
- Modify: `history/states/313-313.txt`
- Modify: `history/states/314-314.txt`

**Interfaces:**
- Consumes: `STATE_PROFILES`, `VORKERLAND_LEGACY_PROFILES`, `render_state(state_id: int, owner: str) -> str`, and `state_path(state_id: int) -> Path`.
- Produces: exact EBA state profiles in the builder and matching history files.

- [x] **Step 1: Add the failing EBA state-profile contract**

Import `STATE_PROFILES` and `VORKERLAND_LEGACY_PROFILES` into `tools/validate_adiscord_new_states.py`. Add this independent literal contract:

```python
EBA_EXPECTED_STATE_PROFILES = {
    197: {"population": 1_050_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 1, "air_base": 1, "supplies": 4.5},
    311: {"population": 750_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 0, "air_base": 0, "supplies": 2.5},
    312: {"population": 650_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 1, "air_base": 0, "supplies": 3.0},
    313: {"population": 550_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 0, "air_base": 0, "supplies": 3.0},
    314: {"population": 550_000, "category": "town", "infrastructure": 3, "civilian": 1, "military": 0, "air_base": 0, "supplies": 3.0},
}
```

Parse each real state file into the same seven fields and compare with the literal. For states 311-314, parse `render_state` output too. Check that `VORKERLAND_LEGACY_PROFILES[197]` and `STATE_PROFILES[311:314]` encode the same profile and that totals equal 3,550,000 population, seven civilian factories, two military factories, one air base, and 16.0 supplies.

Use a validator-only parser with this output boundary:

```python
def building_level(source: str, name: str) -> int:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*(\d+)", source)
    return int(match.group(1)) if match else 0


def state_profile(source: str) -> dict[str, int | float | str]:
    history = block(source, "history")
    buildings = block(history, "buildings")
    return {
        "population": int(re.search(r"(?m)^\s*manpower\s*=\s*(\d+)", source).group(1)),
        "category": re.search(r"(?m)^\s*state_category\s*=\s*(\w+)", source).group(1),
        "infrastructure": building_level(buildings, "infrastructure"),
        "civilian": building_level(buildings, "industrial_complex"),
        "military": building_level(buildings, "arms_factory"),
        "air_base": building_level(buildings, "air_base"),
        "supplies": float(re.search(r"(?m)^\s*local_supplies\s*=\s*([\d.]+)", source).group(1)),
    }
```

Normalize generated `industry` to the contract's `civilian` field before comparing builder constants.

- [x] **Step 2: Run the new-state validator and verify RED**

Run:

```powershell
python -B tools/validate_adiscord_new_states.py
```

Expected: exit 1 with EBA profile mismatches for states 197 and 311-314 and total mismatches. No import, syntax, or unrelated VP errors are acceptable.

- [x] **Step 3: Implement the authoritative profiles**

Set these exact builder values:

```python
STATE_PROFILES[311] = {"population": 750_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 2.5}
STATE_PROFILES[312] = {"population": 650_000, "category": "town", "infrastructure": 3, "industry": 1, "military": 1, "supplies": 3.0}
STATE_PROFILES[313] = {"population": 550_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 3.0}
STATE_PROFILES[314] = {"population": 550_000, "category": "town", "infrastructure": 3, "industry": 1, "supplies": 3.0}
VORKERLAND_LEGACY_PROFILES[197] = {"population": 1_050_000, "category": "large_town", "infrastructure": 4, "civilian": 3, "military": 1, "air_base": 1, "supplies": 4.5}
```

Extend `buildings()` to append `arms_factory` and `air_base` when optional `military` or `air_base` keys exist, while retaining the current `industry` behavior for every other generated profile.

Patch the five state files to mirror these values exactly. State 312 gains one `arms_factory`; state 197 gains one civilian factory, one infrastructure level, and one air base.

- [x] **Step 4: Run the new-state validator and verify GREEN**

Run `python -B tools/validate_adiscord_new_states.py`.

Expected: exit 0 with the existing new-state success message.

---

### Task 2: EBA reserve and deployment

**Files:**
- Modify: `tools/test_validate_adiscord_vorkerland_collapse.py`
- Modify: `tools/validate_adiscord_vorkerland_collapse.py`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt`
- Modify: `history/units/EBA_vorkerland_collapse.txt`

**Interfaces:**
- Consumes: `ADISCORD_vorkerland_setup_eba` and the existing four-division `EBA Collapse Militia` OOB.
- Produces: an exact 10,000 manpower/1,100 rifle reserve and locations `[16623, 16623, 16617, 16637]`.

- [x] **Step 1: Add failing military balance tests**

Add two methods to `FrontAndSupplyTests`:

```python
def test_eba_receives_the_approved_finite_reserve(self) -> None:
    effects = read("common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt")
    eba = named_block(effects, "ADISCORD_vorkerland_setup_eba")
    self.assertIn("add_manpower = 10000", eba)
    self.assertIn("amount = 1100", eba)

def test_eba_militia_cover_the_capital_and_two_secondary_cities(self) -> None:
    oob = read("history/units/EBA_vorkerland_collapse.txt")
    self.assertEqual(oob.count("division = {"), 4)
    locations = [int(value) for value in re.findall(r"location\s*=\s*(\d+)", oob)]
    self.assertCountEqual(locations, [16623, 16623, 16617, 16637])
```

Add equivalent exact checks to the standalone Vorkerland validator so its normal `all` section reports reserve or deployment drift:

```python
eba_setup = named_block(effects, "ADISCORD_vorkerland_setup_eba")
if "add_manpower = 10000" not in eba_setup or "amount = 1100" not in eba_setup:
    issues.append("EBA: approved collapse reserve is missing")
eba_oob = read(root, "history/units/EBA_vorkerland_collapse.txt", issues)
eba_locations = [int(value) for value in re.findall(r"location\s*=\s*(\d+)", eba_oob)]
if sorted(eba_locations) != sorted([16623, 16623, 16617, 16637]):
    issues.append("EBA: militia deployment is not distributed across the republic")
```

- [x] **Step 2: Run the two new tests and verify RED**

Run:

```powershell
python -B -m unittest tools.test_validate_adiscord_vorkerland_collapse.FrontAndSupplyTests.test_eba_receives_the_approved_finite_reserve tools.test_validate_adiscord_vorkerland_collapse.FrontAndSupplyTests.test_eba_militia_cover_the_capital_and_two_secondary_cities
```

Expected: two assertion failures showing 8,000/800 and four copies of location 10016.

- [x] **Step 3: Implement the approved reserve and deployment**

Change only the EBA setup values to `add_manpower = 10000` and `amount = 1100`. Keep the producer and equipment type unchanged.

Move the first two OOB divisions to Ebern's corrected bay-side province 16623. Change the third to province 16637 and the fourth to province 16617. Keep their templates, names, experience, and equipment factors unchanged.

- [x] **Step 4: Run the two tests and standalone validator GREEN**

Run the two-test command from Step 2, then `python -B tools/validate_adiscord_vorkerland_collapse.py`.

Expected: both commands exit 0.

---

### Task 3: Full verification and scope review

**Files:**
- Verify: every file listed in Tasks 1-2
- Verify: `docs/superpowers/plans/2026-08-04-vlad-macri-state-rebalance.md`

**Interfaces:**
- Consumes: completed state and military contracts.
- Produces: fresh evidence that the scoped rebalance is internally consistent.

- [x] **Step 1: Run the complete Vorkerland unit suite**

Run `python -B -m unittest tools.test_validate_adiscord_vorkerland_collapse`.

Expected: all tests pass with zero failures.

- [x] **Step 2: Run focused and general validators**

Run:

```powershell
python -B tools/validate_adiscord_new_states.py
python -B tools/validate_adiscord_vorkerland_collapse.py
python -B tools/validate_tc.py --limit 300
```

Expected: all three commands exit 0; `validate_tc.py` reports `Map and states: 0`.

- [x] **Step 3: Check formatting and dirty-scope preservation**

Run scoped `git diff --check` across all implementation files. Inspect exact EBA hunks and confirm no resources, borders, owners, cores, VP values, diplomacy, ideology, templates, division count, or equipment types changed. Leave implementation changes unstaged and uncommitted because the files overlap existing dirty work.
