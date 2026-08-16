# IVN Island Administration and Geography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create IVN's permanent same-colour island subject, unique `autonomy_island_administration` icon, exact island/Old March state splits, denser named victory points, and painted/defined terrain agreement without changing province geometry.

**Architecture:** Keep state ownership and metadata in the existing state-history builder, isolate IIA/autonomy contracts in focused country files, generate the autonomy icon from one high-resolution source through a deterministic builder, and add a scoped layered geography builder for `definition.csv` terrain fields plus visible urban footprints. Focused validators enforce exact province unions, balance totals, GFX resolution, subject setup, OOB counts, and terrain agreement before the global release gate.

**Tech Stack:** HOI4 Clausewitz data, Python 3 standard library, Pillow, unittest, existing A-Discord builders/validators, image generation for one source PNG.

## Global Constraints

- Fresh campaigns only; no save migration, startup repair, or old-save acceptance evidence.
- `map/provinces.bmp` must remain byte-for-byte unchanged.
- Existing province adjacency, coastlines, railways, supply nodes, and strategic-region membership remain unchanged.
- Russian localisation remains UTF-8 with BOM; technical IDs remain ASCII/English.
- Preserve all unrelated dirty technology, AI, Vorkerland, UI, and unit work.
- State, terrain, definition, map-building, localisation, and icon outputs must be regenerated through their owning builders and prove idempotent.
- Static success is not runtime proof; final acceptance requires a full HOI4 restart and fresh campaign.

---

### Task 1: Add exact RED contracts for the state partitions and balance

**Files:**
- Create: `tools/tests/test_validate_adiscord_ivn_overhaul.py`
- Create: `tools/validators/validate_adiscord_ivn_overhaul.py`
- Create: `tools/validate_adiscord_ivn_overhaul.py`

**Interfaces:**
- Consumes: state files under `history/states`, `tools.builders.build_adiscord_new_states`, Russian state/VP localisation.
- Produces: `validate_states() -> None`, `main() -> int`, and `IVNOverhaulTests` covering exact state and VP contracts.

- [ ] **Step 1: Write the failing partition tests**

Define literal `ISLAND_SPLIT` and `OLD_MARCH_SPLIT` dictionaries copied from the approved design. Parse state province blocks and assert:

```python
self.assertEqual(set().union(*ISLAND_SPLIT.values()), ORIGINAL_STATE_128_PROVINCES)
self.assertEqual(sum(map(len, ISLAND_SPLIT.values())), len(ORIGINAL_STATE_128_PROVINCES))
self.assertEqual(set().union(*OLD_MARCH_SPLIT.values()), ORIGINAL_STATE_25_PROVINCES)
self.assertEqual(sum(map(len, OLD_MARCH_SPLIT.values())), len(ORIGINAL_STATE_25_PROVINCES))
```

Read the post-generation state files and require IDs `25, 128, 693, 694, 695, 696, 697, 698` to contain their exact literal sets. Assert the profiles and exact aggregate totals from the spec: Old March population 4,000,000, civilian 6, military 4, air base 3, local supplies 8.0, steel 24; island population 360,000 and civilian 1.

- [ ] **Step 2: Write failing VP/localisation tests**

Use the exact map from the spec:

```python
EXPECTED_VPS = {
    128: (579, 1, "Нордхольм"), 693: (6905, 5, "Рейдаль"),
    694: (11841, 3, "Кайрхольм"), 695: (1763, 3, "Верхнемарск"),
    696: (5573, 3, "Лонгар"), 697: (9160, 3, "Ринваль"),
    25: (16568, 10, "Старая марка"), 698: (12076, 3, "Салемар"),
    92: (3462, 1, "Серенга"), 95: (3318, 3, "Ведрина"),
    96: (888, 3, "Талара"), 97: (838, 3, "Кантория"),
    98: (2448, 5, "Моресса"), 99: (882, 7, "Лакора"),
    100: (702, 5, "Ильван"), 101: (9327, 3, "Ольсия"),
    127: (595, 3, "Северная Марка"), 129: (1971, 1, "Старый Кордон"),
    130: (3447, 2, "Дальняя Застава"), 131: (2262, 2, "Пыльный Тракт"),
    132: (423, 2, "Западная Серенга"), 164: (4217, 1, "Восточная Итора"),
}
```

Require one state VP record and one Russian localisation key per entry, no duplicate keys, and BOM on both changed localisation files.

- [ ] **Step 3: Write the validator facade and run RED**

The top-level facade mirrors other tools by inserting the repository root into `sys.path` and importing `main` from the validator. Run:

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_ivn_overhaul -v
python -B tools/validate_adiscord_ivn_overhaul.py
```

Expected: failures for missing states `693-698`, missing IVN VP contracts, and old unsplit state province sets. No import or syntax failure is acceptable.

- [ ] **Step 4: Commit the RED contract**

```powershell
git add -- tools/tests/test_validate_adiscord_ivn_overhaul.py tools/validators/validate_adiscord_ivn_overhaul.py tools/validate_adiscord_ivn_overhaul.py
git commit -m "test: define IVN geography overhaul contracts"
```

### Task 2: Generate the island and Old March state split

**Files:**
- Modify: `tools/builders/build_adiscord_new_states.py`
- Modify: `tools/validators/validate_adiscord_new_states.py`
- Modify: `tools/tests/test_validate_adiscord_new_states.py`
- Modify: `tools/data/generated_output_owners.json`
- Generate: `history/states/25-PLACEHOLDER.txt`
- Generate: `history/states/128-128.txt`
- Create/Generate: `history/states/693-693.txt` through `history/states/698-698.txt`
- Modify: `localisation/russian/state_names_l_russian.yml`
- Modify: `localisation/russian/victory_points_l_russian.yml`

**Interfaces:**
- Consumes: the exact split/profile/VP manifests in `build_adiscord_new_states.py`.
- Produces: `apply_ivanland_geography_split() -> None`; exact generated state histories and BOM-safe localisation.

- [ ] **Step 1: Add the approved manifests**

Add `IVANLAND_ISLAND_SPLIT`, `IVANLAND_OLD_MARCH_SPLIT`, `IVANLAND_SPLIT_PROFILES`, `IVANLAND_VICTORY_POINTS`, `IVANLAND_VICTORY_POINT_NAMES`, and `IVANLAND_STATE_NAMES` with the exact IDs, province sets, profiles, and strings from the design. Merge the VP/name maps into `GENERATED_LEGACY_VICTORY_POINTS`, `GENERATED_VICTORY_POINT_NAMES`, and `GENERATED_STATE_NAMES` without changing unrelated entries.

- [ ] **Step 2: Implement guarded state writing**

Add:

```python
def apply_ivanland_geography_split() -> None:
    """Repartition only reviewed IVN provinces and write exact state metadata."""
```

Before writing, accept only the pre-split source union or the already-split reviewed union; reject any other province manifest as drift. Reuse a generalised form of `write_resource_war_state` to write all eight state files with exact owner/core, profile, resources, VP, and province-building records. State 694 receives `(11841, "naval_base", 2)` and state 25 retains `(16568, "naval_base", 1)`.

- [ ] **Step 3: Wire apply/check and generated ownership**

Call `apply_ivanland_geography_split()` before legacy profile patching. Add exact output globs `history/states/693-*.txt` through `698-*.txt` under `state_history`; add the new source inputs and explain the layered localisation/state ownership. Extend the new-state validator so `--check` compares real state files to the manifests rather than merely checking aggregate profiles.

- [ ] **Step 4: Run apply and GREEN tests**

```powershell
python -B tools/build_adiscord_new_states.py --apply
python -B tools/build_adiscord_new_states.py --check
python -B -m unittest tools.tests.test_validate_adiscord_ivn_overhaul tools.tests.test_validate_adiscord_new_states -v
```

Expected: all state/VP tests pass. Preserve UTF-8 BOM on Russian localisation.

- [ ] **Step 5: Prove state-builder idempotence**

Hash the eight state files plus both localisation files, run `--apply` again, and assert identical SHA-256 values.

- [ ] **Step 6: Commit the generated state work**

Stage only the builder, validators/tests, ownership manifest, eight state files, and two localisation files. Run cached diff check and commit:

```powershell
git commit -m "feat: split IVN island and Old March states"
```

### Task 3: Add IIA and the locked autonomy type

**Files:**
- Modify: `tools/tests/test_validate_adiscord_ivn_overhaul.py`
- Modify: `tools/validators/validate_adiscord_ivn_overhaul.py`
- Create: `common/autonomous_states/ADISCORD_island_administration.txt`
- Modify: `common/country_tags/00_countries.txt`
- Create: `common/countries/IIA.txt`
- Create: `common/characters/IIA.txt`
- Create: `history/countries/IIA - Itoran Island Administration.txt`
- Modify: `history/countries/IVN - IvanLand.txt`
- Create: `history/units/IIA.txt`
- Modify: `history/units/IVN.txt`
- Copy: `gfx/flags/IIA.tga`, `gfx/flags/medium/IIA.tga`, `gfx/flags/small/IIA.tga`
- Modify: `localisation/russian/countries_l_russian.yml`
- Modify: `localisation/russian/nsb_characters_l_russian.yml`
- Modify: `localisation/russian/autonomy_l_russian.yml`

**Interfaces:**
- Consumes: states 128/693/694 and existing Europe generic portrait sprite.
- Produces: tag `IIA`, character `IIA_Provisional_Commandant`, and autonomy `autonomy_island_administration`.

- [ ] **Step 1: Extend RED tests for country/autonomy/OOB**

Require the exact autonomy ID, `use_overlord_color = yes`, self-only `allowed_levels_filter`, locked level triggers, rules, and modifier values from the spec. Require IVN history to set IIA autonomy at 0.00, IIA capital 693, humanism, two research slots, placeholder character using `GFX_Portrait_Europe_Generic_land_2`, and exact owner/core states. Require sixteen IVN divisions, none located in 579, and one weak IIA garrison at 579.

Run the focused test and observe contract failures before adding files.

- [ ] **Step 2: Implement autonomy and country data**

Create the autonomy block exactly as specified. Add the IIA tag, colour/graphical culture, character, country history, subject relationship, and Russian localisation. Copy IVN's three existing flag sizes byte-for-byte to IIA; do not generate a new flag or leader portrait.

- [ ] **Step 3: Implement OOB movement and garrison**

Move the existing IVN division whose `location = 579` to `595` without changing its template, equipment, experience, or any other IVN division. Create one IIA garrison using the project's weakest ordinary infantry/garrison template and location 579; do not add aircraft or a navy.

- [ ] **Step 4: Run autonomy/OOB GREEN gates**

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_ivn_overhaul tools.tests.test_validate_adiscord_autonomy_chains tools.tests.test_validate_adiscord_vorkerland_collapse -v
python -B tools/validate_adiscord_ivn_overhaul.py
python -B tools/validate_adiscord_vorkerland_collapse.py
```

Expected: exact country/autonomy/OOB contracts pass without changing IVN intervention outcomes.

- [ ] **Step 5: Commit country/autonomy work**

Stage only the listed IIA/autonomy/OOB/localisation/test files, run cached diff check, and commit:

```powershell
git commit -m "feat: add IVN island administration subject"
```

### Task 4: Generate and connect the unique autonomy icon

**Files:**
- Modify: `tools/tests/test_validate_adiscord_ivn_overhaul.py`
- Modify: `tools/validators/validate_adiscord_ivn_overhaul.py`
- Create: `tools/assets/source/autonomy_island_administration_source.png`
- Create: `tools/builders/build_adiscord_island_administration_icon.py`
- Create: `tools/build_adiscord_island_administration_icon.py`
- Create: `tools/tests/test_build_adiscord_island_administration_icon.py`
- Generate: `gfx/interface/autonomy/autonomy_island_administration_icon.png`
- Modify: `interface/ADISCORD_autonomy_icons.gfx`
- Modify: `tools/data/generated_output_owners.json`

**Interfaces:**
- Consumes: one high-resolution transparent image source.
- Produces: `render_icon(source: Image.Image) -> Image.Image`, 35x36 RGBA output, and sprite `GFX_autonomy_island_administration_icon`.

- [ ] **Step 1: Add failing image-builder tests**

Require `render_icon` to return `(35, 36)` RGBA, transparent corner pixels, a non-transparent centre, and no output difference after a second apply. Require the GFX sprite to point to the exact PNG.

- [ ] **Step 2: Generate the high-resolution source**

Use the image-generation skill with this exact prompt:

```text
Square transparent-background strategy-game autonomy emblem, no text and no border outside the emblem. A compact silver coastal command tower rises above two dark teal ocean waves. Behind it sits a weathered golden sun disc and two crossed dark military blades, visually echoing the IVN flag without copying it literally. Dark forest-green, oxidized gold, gunmetal and cold silver palette; restrained late-industrial military administration mood; bold centered silhouette; crisp high contrast; simple large shapes that remain readable when reduced to 35 by 36 pixels; no people, no letters, no photorealistic scene, no drop shadow outside the transparent canvas.
```

Inspect the result before storing it as the source asset. Reject unreadable fine-detail or an opaque background and regenerate with the same art direction if necessary.

- [ ] **Step 3: Implement deterministic processing**

The builder trims transparent padding, centres the emblem on a square working canvas, applies `ImageOps.contain`, resizes with Lanczos, applies one mild unsharp mask, and writes the exact 35x36 RGBA output only under `--apply`. Default/`--check` compares encoded output bytes. Register the builder as the sole owner of the final autonomy PNG.

- [ ] **Step 4: Wire sprite and run GREEN/idempotence**

```powershell
python -B -m unittest tools.tests.test_build_adiscord_island_administration_icon -v
python -B tools/build_adiscord_island_administration_icon.py --apply
python -B tools/build_adiscord_island_administration_icon.py --check
python -B -m unittest tools.tests.test_validate_adiscord_ivn_overhaul -v
```

Open the 35x36 output at original size and at 4x nearest-neighbour preview; confirm the tower/waves silhouette remains distinct.

- [ ] **Step 5: Commit icon work**

Stage only the icon source/builder/output/test/GFX/ownership paths, run cached diff check, and commit:

```powershell
git commit -m "feat: add island administration autonomy icon"
```

### Task 5: Align IVN painted and defined terrain

**Files:**
- Modify: `tools/tests/test_validate_adiscord_ivn_overhaul.py`
- Modify: `tools/validators/validate_adiscord_ivn_overhaul.py`
- Create: `tools/builders/build_adiscord_ivn_geography.py`
- Create: `tools/build_adiscord_ivn_geography.py`
- Create: `tools/tests/test_build_adiscord_ivn_geography.py`
- Modify/Generate: `map/definition.csv`
- Modify/Generate: `map/terrain.bmp`
- Modify: `tools/data/generated_output_owners.json`

**Interfaces:**
- Consumes: exact IVN/IIA state province sets, terrain palette mapping from `common/terrain/00_terrain.txt`, province colour masks, and `EXPECTED_VPS`.
- Produces: `classify_province_terrain(province_id: int) -> str`, `render_definition() -> bytes`, `render_terrain() -> Image.Image`, and a mismatch report.

- [ ] **Step 1: Write RED terrain classification tests**

Use tiny in-memory paletted terrain/province fixtures to test water exclusion, plurality, the exact tie order `urban, mountain, hills, marsh, forest, plains, jungle, desert`, and deterministic urban-footprint clipping. Add real-map assertions that `map/provinces.bmp` hash matches the pre-task hash and the current 16/18 island mismatches are detected before apply.

- [ ] **Step 2: Implement read-only classification**

Parse palette-index-to-category mappings from `common/terrain/00_terrain.txt`; reject an unknown non-water index rather than silently mapping it. Count land pixels for every starting IVN/IIA province and choose the plurality category with the exact tie order.

- [ ] **Step 3: Implement deterministic urban footprints**

For every expected VP, select land pixels nearest the province centroid, grow a compact connected footprint inside that province only, preserve at least 35% of prior non-urban pixels, and ensure at least 24 urban pixels. Rerun classification after painting; write `urban` for settlement provinces and plurality for all others.

- [ ] **Step 4: Implement check/apply and layered ownership**

Default/`--check` reports exact differing province terrain fields and terrain pixels without writes. `--apply` writes only terrain column 6 for scoped province rows, preserves every other CSV field/order/line ending, and writes only scoped urban pixels in the paletted bitmap. Register layered ownership alongside trade-region definition output and terrain-snow output with an explicit overlap explanation.

- [ ] **Step 5: Apply, regenerate snow, and prove idempotence**

```powershell
python -B tools/build_adiscord_ivn_geography.py --apply
python -B tools/build_adiscord_terrain_snow.py --apply
python -B tools/build_adiscord_ivn_geography.py --check
python -B tools/build_adiscord_terrain_snow.py --check
python -B -m unittest tools.tests.test_build_adiscord_ivn_geography tools.tests.test_build_adiscord_terrain_snow tools.tests.test_validate_adiscord_ivn_overhaul -v
```

Hash `definition.csv` and `terrain.bmp`, repeat both applies in the same order, and require identical hashes. Confirm zero non-settlement mismatch for scoped provinces and visible urban footprints for every listed VP.

- [ ] **Step 6: Commit terrain work**

Stage only the geography builder/facade/tests/validator, ownership manifest, `definition.csv`, and `terrain.bmp`; run cached diff check and commit:

```powershell
git commit -m "feat: align IVN terrain and settlement geography"
```

### Task 6: Synchronise map buildings and run the release gate

**Files:**
- Generate: `map/buildings.txt`
- Modify: `tools/validators/validate_adiscord_map_buildings.py`
- Modify: `tools/validators/validate_adiscord_new_states.py`
- Modify: `tools/validators/validate_adiscord_autonomy_chains.py`
- Update: `docs/superpowers/plans/2026-08-15-ivn-island-administration-and-geography.md` checkboxes only after evidence exists.

**Interfaces:**
- Consumes: all implemented generated outputs.
- Produces: clean focused/static evidence and a bounded runtime checklist.

- [ ] **Step 1: Synchronise and check map builders**

```powershell
python -B tools/build_adiscord_map_buildings.py --apply
python -B tools/build_adiscord_map_buildings.py --check
python -B tools/build_adiscord_strategic_regions.py --check
```

The strategic-region builder must report no change because province membership is unchanged. A second map-building apply must be idempotent.

- [ ] **Step 2: Run focused validators/tests**

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_ivn_overhaul tools.tests.test_build_adiscord_island_administration_icon tools.tests.test_build_adiscord_ivn_geography tools.tests.test_validate_adiscord_new_states tools.tests.test_validate_adiscord_autonomy_chains tools.tests.test_validate_adiscord_vorkerland_collapse -v
python -B tools/validate_adiscord_ivn_overhaul.py
python -B tools/validate_adiscord_new_states.py
python -B tools/validate_adiscord_autonomy_chains.py
python -B tools/validate_adiscord_vorkerland_collapse.py
```

- [ ] **Step 3: Run all relevant generated-output checks**

Run these exact owner checks and report every failure:

```powershell
python -B tools/build_adiscord_new_states.py --check
python -B tools/build_adiscord_island_administration_icon.py --check
python -B tools/build_adiscord_ivn_geography.py --check
python -B tools/build_adiscord_terrain_snow.py --check
python -B tools/build_adiscord_map_buildings.py --check
python -B tools/build_adiscord_strategic_regions.py --check
python -B -m tools.builders.build_adiscord_trade_regions --check
```

The map-building validator must assert the state-694 naval-base record belongs to state 694. The new-state validator must assert the exact eight IVN state files and totals. The autonomy-chain validator must assert IIA cannot transition out of `autonomy_island_administration`.

- [ ] **Step 4: Run the global static gate**

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Also verify BOM bytes for every changed Russian localisation file and verify the current `map/provinces.bmp` SHA-256 equals the pre-implementation hash.

- [ ] **Step 5: Review the scoped diff and commit any final synchronisation**

Confirm staged paths contain no unrelated dirty work. If `map/buildings.txt` or validator-only corrections changed, stage only those exact paths, run cached checks, and commit:

```powershell
git commit -m "chore: validate IVN geography integration"
```

- [ ] **Step 6: Prepare runtime handoff**

Do not launch HOI4 without explicit user authorisation. Provide a fresh-campaign checklist for IIA subject colour/autonomy icon/placeholder leader, island and Old March borders/names/VPs/ports, terrain visuals and tooltips, OOB placement, supply/rail continuity, and IVN northern-intervention availability.
