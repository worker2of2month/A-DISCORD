# IVN Northern Landscape Implementation Plan

> **2026-08-16 amendment:** Task 3's automated province split was reverted.
> Do not execute it or write `provinces.bmp`, `unitstacks.txt`, or
> `buildings.txt`. The user will provide editor-authored province geometry in a
> later handoff. Continue landscape work on the current unsplit map and retain
> the generated urban terrain footprints.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic island relief, split all nine northern VP settlements into compact city provinces, synchronize normal/terrain/tree maps across the approved IVN north, and add distinct geographic names while preserving unrelated map content.

**Architecture:** Add a deterministic narrow province-split owner for the nine approved source provinces before the existing layered `build_adiscord_ivn_geography` pass. Retain each old ID as the compact city core, append deterministic IDs/colours for same-state rural remainders, then generate terrain, trees, map buildings, snow, and minimap from the new geometry. Keep naming in its current owning builders.

**Tech Stack:** Python 3 standard library, Pillow, `unittest`, HOI4 paletted/RGB BMP maps, existing A-Discord builder and validator conventions.

## Global Constraints

- Work in the authoritative dirty checkout and preserve every unrelated hunk.
- Change `map/provinces.bmp` only inside source provinces `{595, 579, 1971, 3447, 2262, 423, 4217, 6905, 11841}` and replace the old SHA-256 contract with the deterministic post-split hash.
- Sculpt height only in states 128, 693, and 694.
- Repaint forest, hills, mountains, and trees only in states 127-132, 164,
  693, and 694, excluding BOR state 89 and including state 128 explicitly.
- The only terrain changes permitted outside that northern mask are the
  user-requested organic reshaping of existing urban footprints for the exact
  `SETTLEMENT_PROVINCES` already owned by the IVN geography builder.
- The exact northern landscape state set is `{127, 128, 129, 130, 131, 132, 164, 693, 694}`.
- Do not change mainland height, water, coastlines, adjacency, rivers, railways, supply nodes, or victory-point values. Only the nine owning state province lists gain generated IDs; buildings are resynchronized without moving their old-ID anchors.
- Keep generated island height below 180 and therefore below the permanent-snow threshold 205.
- Preserve BMP dimensions, modes, and palettes.
- Preserve Russian localisation as UTF-8 with BOM; use ASCII/English technical names.
- Keep `Старая марка` only for state 25 and VP 16568.
- Urban terrain footprints must remain compact and connected but use organic,
  irregular boundaries without obvious rectangular shapes or long straight
  horizontal/vertical edges.
- Old IDs remain the nine city cores. Each core and each generated remainder is
  four-neighbour connected; province 6905's core must avoid mountain terrain and
  its ridge may be a separate mountain-dominant province.
- Run owning builders in check mode before apply and prove second-apply hash idempotence.
- Do not stage or commit implementation paths in the shared dirty tree unless the user explicitly authorizes implementation commits; use scoped diffs as checkpoints.
- Static checks do not prove Clausewitz rendering. Runtime acceptance requires a full restart and fresh campaign, not an old save.

## File responsibility map

- `tools/builders/build_adiscord_ivn_city_provinces.py`: deterministic nine-city province splitting, definition rows, state membership, atomic writes, and drift validation.
- `tools/builders/build_adiscord_ivn_geography.py`: full-resolution masks, island height, half-resolution normals, northern terrain, low-resolution trees, declared-terrain synchronization, atomic writes, and drift validation.
- `tools/tests/test_build_adiscord_ivn_city_provinces.py`: pure split/connectivity tests plus real-map scope, reference, and idempotence contracts.
- `tools/tests/test_build_adiscord_ivn_geography.py`: pure-function tests, real-map scope contracts, coverage contracts, BMP format contracts, and province hash.
- `tools/validators/validate_adiscord_ivn_overhaul.py`: player-visible IVN/IIA aggregate contract, including names and landscape builder drift.
- `tools/tests/test_validate_adiscord_ivn_overhaul.py`: exact state, VP, region-name, and aggregate landscape expectations.
- `tools/builders/build_adiscord_new_states.py`: generated state names and filenames 695-698 plus exact retirement of their four former filenames.
- `tools/builders/build_adiscord_strategic_regions.py`: strategic region 6 player-facing name.
- `tools/data/generated_output_owners.json`: layered ownership and apply order for height, normals, terrain, definition, and trees.
- `map/heightmap.bmp`: generated island height pixels.
- `map/world_normal.bmp`: generated half-resolution island normal cells.
- `map/terrain.bmp`: generated terrain inside the approved northern mask plus outputs from the existing snow layer.
- `map/trees.bmp`: generated tree cells inside the approved downsampled mask.
- `map/definition.csv`: generated terrain column 6 for the existing IVN/IIA declared-terrain scope.
- `map/provinces.bmp`: generated split geometry inside the nine approved source provinces only.
- `localisation/russian/state_names_l_russian.yml`: generated state names.
- `localisation/russian/victory_points_l_russian.yml`: generated VP 595 name.
- `localisation/replace/strategic_region_names_l_russian.yml`: generated strategic-region name.
- `history/states/695-Verkhnemarye.txt`, `696-Longar-Plain.txt`, `697-Rinval-Coast.txt`, `698-Salemar-Basin.txt`: renamed generated state files.

---

### Task 1: Define pure landscape masks and deterministic scalar fields

**Files:**
- Modify: `tools/builders/build_adiscord_ivn_geography.py`
- Modify: `tools/tests/test_build_adiscord_ivn_geography.py`

**Interfaces:**
- Consumes: province RGB bitmap, `map/definition.csv`, and exact state province manifests.
- Produces: `ISLAND_HEIGHT_STATE_IDS`, `NORTHERN_LANDSCAPE_STATE_IDS`, `LandscapeMasks`, `distance_from_edge()`, `island_height_value()`, `moisture_value()`, and `stable_unit_hash()`.

- [ ] **Step 1: Add failing mask and scalar-field tests**

Add imports for `dataclass` and construct tiny RGB/grayscale fixtures. Require the exact state sets and these pure contracts:

```python
def test_landscape_scope_is_exact(self) -> None:
    self.assertEqual(builder.ISLAND_HEIGHT_STATE_IDS, frozenset({128, 693, 694}))
    self.assertEqual(
        builder.NORTHERN_LANDSCAPE_STATE_IDS,
        frozenset({127, 128, 129, 130, 131, 132, 164, 693, 694}),
    )

def test_distance_from_edge_increases_inward(self) -> None:
    mask = bytearray([
        0, 0, 0, 0, 0,
        0, 1, 1, 1, 0,
        0, 1, 1, 1, 0,
        0, 1, 1, 1, 0,
        0, 0, 0, 0, 0,
    ])
    distances = builder.distance_from_edge(mask, 5, 5)
    self.assertEqual(distances[2 * 5 + 2], 1)
    self.assertEqual(distances[1 * 5 + 1], 0)

def test_scalar_fields_are_bounded_and_repeatable(self) -> None:
    first = builder.island_height_value(0.52, 0.45, 8)
    self.assertEqual(first, builder.island_height_value(0.52, 0.45, 8))
    self.assertGreaterEqual(first, 97)
    self.assertLess(first, 180)
    self.assertEqual(builder.stable_unit_hash(41, 73, 19), builder.stable_unit_hash(41, 73, 19))
```

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_ivn_geography -v
```

Expected: failures naming the missing scope constants and pure functions, while the pre-existing province-hash test still passes.

- [ ] **Step 3: Implement state/province masks**

Add:

```python
from dataclasses import dataclass
from math import cos, exp, pi, sin

ISLAND_HEIGHT_STATE_IDS = frozenset({128, 693, 694})
NORTHERN_LANDSCAPE_STATE_IDS = frozenset({127, 128, 129, 130, 131, 132, 164, 693, 694})

@dataclass(frozen=True)
class LandscapeMasks:
    island: bytearray
    north: bytearray
    island_bbox: tuple[int, int, int, int]
```

Implement `province_ids_for_states(state_ids: frozenset[int]) -> frozenset[int]` by reusing `state_path()` and the existing province-block parser. Implement `landscape_masks(provinces: Image.Image, definition_colors: dict[int, tuple[int, int, int]]) -> LandscapeMasks` with one RGB scan. Reject missing state provinces, non-RGB conversion failure, and an empty island mask.

- [ ] **Step 4: Implement deterministic distance, height, moisture, and hash functions**

Use four-neighbour breadth-first distance initialized by every mask pixel touching a non-mask pixel. Add:

```python
def stable_unit_hash(x: int, y: int, salt: int) -> float:
    value = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    value = (value ^ (value >> 13)) * 1274126177
    return ((value ^ (value >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF

def island_height_value(u: float, v: float, coast_distance: int) -> int:
    coast = min(1.0, coast_distance / 11.0)
    ridge_x = 0.50 + 0.12 * sin((v - 0.12) * pi * 1.35)
    ridge = exp(-((u - ridge_x) / 0.17) ** 2)
    north_lobe = exp(-(((u - 0.43) / 0.25) ** 2 + ((v - 0.27) / 0.19) ** 2))
    south_lobe = exp(-(((u - 0.57) / 0.24) ** 2 + ((v - 0.73) / 0.22) ** 2))
    valley = exp(-(((u - 0.67) / 0.13) ** 2 + ((v - 0.52) / 0.26) ** 2))
    texture = 0.5 + 0.25 * sin(7.0 * u + 4.0 * v) + 0.25 * cos(5.0 * u - 6.0 * v)
    raw = 97.0 + coast * (12.0 + 43.0 * ridge + 13.0 * north_lobe + 10.0 * south_lobe - 8.0 * valley + 6.0 * texture)
    return max(97, min(175, round(raw)))

def moisture_value(u: float, v: float, x: int, y: int) -> float:
    broad = 0.50 + 0.22 * sin(5.0 * u + 3.0 * v) + 0.18 * cos(4.0 * u - 6.0 * v)
    return broad + 0.10 * (stable_unit_hash(x, y, 11) - 0.5)
```

- [ ] **Step 5: Run focused tests and inspect the scoped diff**

Run the focused unittest again and require PASS. Run:

```powershell
git diff --check -- tools/builders/build_adiscord_ivn_geography.py tools/tests/test_build_adiscord_ivn_geography.py
git diff -- tools/builders/build_adiscord_ivn_geography.py tools/tests/test_build_adiscord_ivn_geography.py
```

Confirm only Task 1 functions and tests were added. Do not stage them.

---

### Task 2: Generate island height and synchronized world normals

**Files:**
- Modify: `tools/builders/build_adiscord_ivn_geography.py`
- Modify: `tools/tests/test_build_adiscord_ivn_geography.py`
- Generate: `map/heightmap.bmp`
- Generate: `map/world_normal.bmp`

**Interfaces:**
- Consumes: `LandscapeMasks`, `island_height_value()`, source heightmap, source normal map.
- Produces: `render_heightmap() -> Image.Image`, `height_slope() -> int`, `normal_from_height() -> Image.Image`, and island/normal changed-cell masks.

- [ ] **Step 1: Add RED tests for height and normal direction**

Add in-memory tests:

```python
def test_render_heightmap_changes_only_island_mask(self) -> None:
    source = Image.new("L", (5, 5), 110)
    mask = bytearray(25)
    mask[2 * 5 + 2] = 1
    rendered = builder.render_heightmap(source, mask, (2, 2, 2, 2))
    changed = [i for i, (a, b) in enumerate(zip(source.getdata(), rendered.getdata())) if a != b]
    self.assertEqual(changed, [12])

def test_normal_channels_follow_existing_orientation(self) -> None:
    flat = Image.new("L", (6, 6), 120)
    normal = builder.normal_from_height(flat, Image.new("RGB", (3, 3), (127, 127, 253)), bytearray([1] * 36))
    self.assertEqual(normal.getpixel((1, 1)), (127, 127, 253))
```

Add rising-east and rising-south fixtures and require red to decrease for a positive x gradient and green to increase for a positive y gradient.

- [ ] **Step 2: Run RED**

Run the focused unittest. Expected: only the new `render_heightmap` and `normal_from_height` tests fail due to missing functions.

- [ ] **Step 3: Implement island height rendering and slope**

Add constants:

```python
HEIGHTMAP_PATH = ROOT / "map/heightmap.bmp"
WORLD_NORMAL_PATH = ROOT / "map/world_normal.bmp"
HEIGHT_MIN = 97
HEIGHT_MAX = 175
NORMAL_CENTER = 127
NORMAL_SCALE = 1.65
NORMAL_BLUE = 253
```

`render_heightmap(source, island_mask, bbox)` must require mode `L`, compute normalized coordinates over the real island bounding box, use `distance_from_edge`, and replace only set mask pixels. `height_slope(pixels, width, height, index)` returns the maximum absolute four-neighbour difference without wrapping rows.

- [ ] **Step 4: Implement half-resolution normal rendering**

For normal cell `(nx, ny)`, compute a 2x2 mean height `H(nx, ny)`, central differences `dx=(H(nx+1,ny)-H(nx-1,ny))/2` and `dy=(H(nx,ny+1)-H(nx,ny-1))/2`, then encode:

```python
r = clamp(round(NORMAL_CENTER - NORMAL_SCALE * dx), 0, 255)
g = clamp(round(NORMAL_CENTER + NORMAL_SCALE * dy), 0, 255)
b = NORMAL_BLUE
```

Modify a normal cell only if its 2x2 full-resolution footprint or a directly adjacent footprint contains island land. Preserve every other source RGB cell exactly. Require the normal image dimensions to equal half the heightmap dimensions.

- [ ] **Step 5: Add real-map scope and distribution assertions**

Require:

```python
self.assertGreaterEqual(min(island_values), 97)
self.assertLess(max(island_values), 180)
self.assertGreaterEqual(len(set(island_values)), 45)
self.assertGreaterEqual(sum(value >= 145 for value in island_values), 250)
self.assertEqual(changed_height_outside_island, 0)
self.assertEqual(changed_normal_outside_feathered_mask, 0)
```

Also assert image modes/sizes are exactly `L 5632x2048` and `RGB 2816x1024`.

- [ ] **Step 6: Wire check/apply with atomic BMP replacement**

Extend `expected()` to return a named dataclass rather than an expanding tuple:

```python
@dataclass
class GeographyOutputs:
    terrain: Image.Image
    definition: bytes
    heightmap: Image.Image
    world_normal: Image.Image
    trees: Image.Image | None
    desired: dict[int, str]
    counts: dict[int, Counter[str]]
    footprints: dict[int, set[int]]
```

At this task, preserve `trees=None`. Add `atomic_save_bmp(image, path)` and use it for terrain, height, and normal. `validate()` reports exact drift counts for both new maps.

- [ ] **Step 7: Run check, apply, and second-apply hash proof**

Run default check first and require it to report height/normal drift without writing. Record hashes for `map/provinces.bmp` and every BMP. Run:

```powershell
python -B tools/build_adiscord_ivn_geography.py --apply
python -B tools/build_adiscord_ivn_geography.py --check
python -B -m unittest tools.tests.test_build_adiscord_ivn_geography -v
```

Hash height and normal, apply again, and require identical hashes. Require the province hash to remain unchanged. Inspect the scoped diff; do not stage it.

---

### Task 3: Split all nine northern VP settlements into compact city provinces

**Files:**
- Create: `tools/builders/build_adiscord_ivn_city_provinces.py`
- Create: `tools/tests/test_build_adiscord_ivn_city_provinces.py`
- Modify: `tools/builders/build_adiscord_new_states.py`
- Modify: `tools/tests/test_validate_adiscord_new_states.py`
- Modify: `tools/data/generated_output_owners.json`
- Modify: `tools/tests/test_generated_output_ownership.py`
- Generate: `map/provinces.bmp`
- Generate: `map/definition.csv`
- Generate: `map/unitstacks.txt`
- Generate: `map/strategicregions/6-*.txt`
- Generate: the nine owning `history/states/*.txt` files

**Interfaces:**
- Consumes: the pre-split province bitmap, definition table, final island height, primary `unitstacks.txt` anchor for each retained old ID, and the nine state memberships.
- Produces: deterministic connected city cores, deterministic same-state rural remainder provinces, appended definition rows, updated state province lists, and exact scope/idempotence metrics.

Use this exact retained-ID/new-ID contract:

```python
CITY_SPLITS = {
    595:   (127, (16654,)),
    579:   (128, (16655,)),
    1971:  (129, (16656,)),
    3447:  (130, (16657,)),
    2262:  (131, (16658,)),
    423:   (132, (16659,)),
    4217:  (164, (16660,)),
    6905:  (693, (16661, 16662)),  # lowland remainder, mountain ridge
    11841: (694, (16663,)),
}
```

- [ ] **Step 1: Add RED pure and real-map split contracts**

Require deterministic four-neighbour region growth, old-ID preservation,
unique unused colours, connected outputs, exact pixel conservation, unchanged
pixels outside the nine old colours, and same-state membership for every new
ID. Require each primary unitstack anchor to remain inside its old city ID.
Require 579, 6905, and 11841 city cores to remain coastal; 6905's core must
have zero overlap with the final mountain mask.

- [ ] **Step 2: Implement a canonical-source, idempotent split builder**

The builder must recognize both the unsplit and already-split map. On the first
run it derives each complete source mask from the union of the retained ID and
its reserved new IDs; on later runs it reconstructs the same union and produces
byte-identical geometry. Refuse partial/foreign ownership, duplicate IDs or
colours, or a source mask that is not connected.

Choose the city core by connected priority-frontier growth from the primary
unitstack anchor, except for 6905: its former anchor is on the height-175 summit,
so select a deterministic low-slope coastal seed from the connected non-mountain
component and later reposition its unitstack rows inside the resulting core.
Use cost favouring low height, low slope, coast access where required, and short centroid distance. Use target size
`clamp(round(2.25 * sqrt(source_pixels)), 24, 96)`. Reject rectangular cores or
long straight boundary runs. For 6905, exclude mountain-eligible pixels and
smooth/flatten only the final core later in the landscape pass.

Assign the remaining connected component to the first reserved ID. For 6905,
assign a connected mountain-dominant ridge component to 16662 and the connected
non-city remainder to 16661. If any generated region is disconnected, fail
without writing rather than creating one-pixel enclaves.

- [ ] **Step 3: Append deterministic definition rows and update state ownership**

Reserve one collision-checked RGB colour per new ID and append rows in numeric
ID order. Derive `land`, `coastal`, continent, and default rural terrain from
the generated geometry while preserving all existing fields for the retained
old rows. Update only the nine owning state province lists through the existing
state-history owner; no VP, OOB, railway, supply, or building reference changes
ID.

Require each reserved ID to occur exactly once in its expected state and zero
times in every other state. The owner must reject or canonically remove foreign
or duplicate reserved memberships; an add-only union is insufficient.

Generate the standard unitstack position kinds for every new province from
interior pixels of its own geometry. Preserve existing rows whose coordinates
remain inside the retained core; deterministically reposition only out-of-core
rows while preserving province ID, kind, rotation, and scale fields. Reposition
all 6905 rows inside its lowland core. At minimum, require a valid interior
primary kind-0 anchor for every retained and new ID. After the
state owner applies, regenerate strategic region 6 through
`build_adiscord_strategic_regions` and require every new ID to appear exactly
once in that region and no other strategic region.

- [ ] **Step 4: Wire ownership and ordered apply**

Register the split builder as layered owner of the exact nine source-colour
regions in `map/provinces.bmp`, appended definition rows, generated unitstack
records, and state-list additions. Place it before `state_history`,
`strategic_regions`, `ivn_geography`, `map_buildings`, `terrain_snow`, and
`minimap` in the apply sequence.

- [ ] **Step 5: Check, apply, and prove idempotence**

Run the split builder in check mode first; apply it once, then rerun check and
focused tests. Record the resulting province SHA-256, apply a second time, and
require the same hash. Require definition/state outputs to be byte-identical on
the second apply and run `git diff --check` on scoped text paths. Replace the
old province hash expectation in both the geography test and aggregate IVN
validator with this exact post-split hash, and retain a canonical unsplit-union
fixture proving zero colour changes outside the nine approved sources.

---

### Task 4: Generate terrain forests and the low-resolution tree map

**Files:**
- Modify: `tools/builders/build_adiscord_ivn_geography.py`
- Modify: `tools/tests/test_build_adiscord_ivn_geography.py`
- Modify: `tools/validators/validate_adiscord_ivn_overhaul.py`
- Test: `tools/tests/test_validate_adiscord_ivn_overhaul.py`
- Modify: `docs/superpowers/specs/2026-08-16-ivn-northern-landscape-design.md`
- Generate: `map/terrain.bmp`
- Generate: `map/trees.bmp`
- Generate: `map/definition.csv`

**Interfaces:**
- Consumes: generated heightmap, `LandscapeMasks`, urban footprints, existing marsh pixels, and terrain palette categories.
- Produces: `render_northern_terrain()`, `tree_cell_sample()`, `tree_probability()`, `render_trees()`, forest/tree metrics, and synchronized `definition.csv` terrain declarations.

- [ ] **Step 1: Add RED terrain and tree probability tests**

Add pure tests requiring these exact palette and relative density contracts:

```python
def test_tree_probabilities_are_ordered(self) -> None:
    self.assertEqual(builder.tree_probability("mountain"), 0.0)
    self.assertEqual(builder.tree_probability("urban"), 0.0)
    self.assertEqual(builder.tree_probability("ocean"), 0.0)
    self.assertLess(builder.tree_probability("hills"), builder.tree_probability("plains"))
    self.assertLess(builder.tree_probability("plains"), builder.tree_probability("forest"))

def test_tree_probability_values(self) -> None:
    self.assertEqual(builder.tree_probability("forest"), 0.62)
    self.assertEqual(builder.tree_probability("plains"), 0.11)
    self.assertEqual(builder.tree_probability("hills"), 0.04)
    self.assertEqual(builder.tree_probability("marsh"), 0.08)
```

Add a 6x6 terrain fixture proving high/steep cells become palette 20, shoulders become 17, selected wet lowlands become 4, urban 13 remains 13, and state-164 marsh 9 remains 9.

Add a mountain-transition fixture requiring every non-coastal, non-urban land
cell directly adjacent to palette-20 mountain terrain to be palette 20 or 17.
Require a one-to-two-pixel connected hill shoulder around each generated
mountain component, so no mountain edge transitions directly into forest or
plains.

Add an urban-footprint fixture with at least 150 province pixels. Require the
generated footprint to be deterministic, four-neighbour connected, inside its
province, within the existing minimum/maximum area bounds, non-rectangular,
and free of any straight boundary run longer than half the footprint's rounded
square-root diameter.

- [ ] **Step 2: Add RED low-resolution sampling tests**

Create an 8x8 province/terrain fixture and a 2x2 tree image. Require `tree_cell_sample()` to use the entire corresponding full-resolution rectangle, choose a state only when a strict majority belongs to the approved mask, and choose terrain by plurality with the existing terrain priority. Require a cell sampling water or an urban plurality to remain index 0.

- [ ] **Step 3: Run RED**

Run the focused geography tests and the IVN aggregate tests. Expected: failures for missing tree functions, missing real `trees.bmp` drift checks, and missing forest/tree coverage metrics.

- [ ] **Step 4: Implement deterministic northern terrain**

First replace the current FIFO `compact_footprint()` growth with a
deterministic priority-frontier growth. Seed at the province centroid; add
four-neighbour frontier pixels ordered by squared centroid distance plus
`0.35 * stable_unit_hash(x, y, province_id)`. Keep a selected pixel only when
it touches the existing footprint, and reject a candidate that would extend a
horizontal or vertical boundary run beyond half the rounded square-root target
diameter when another valid frontier candidate exists. Preserve the existing
minimum 24 pixels, 12-percent target, 65-percent maximum, province containment,
and four-neighbour connectivity contracts. Update the committed design spec's
urban-footprint section to record this user-approved organic-edge requirement.

Define `FULL_URBAN_CITY_PROVINCES` as the exact nine retained IDs from Task 3.
For those IDs, use the entire generated city-core province as its footprint and
paint every pixel palette 13; do not run the 12-percent footprint reducer. Keep
the organic partial-footprint algorithm only for the remaining settlements.
Before terrain classification, lower only 6905 core pixels to a lowland plateau
with a feathered edge, regenerate affected normals, and assert the city has no
mountain-eligible pixel while the separated ridge retains the Task-2 slope and
height distribution gates.

Use palette indices `0=plains`, `4=forest`, `9=marsh`, `13=urban`, `17=hills`, and `20=mountain`. For each approved north pixel:

1. preserve urban footprint 13;
2. preserve existing state-164 marsh 9;
3. classify mountain when height is at least 158 or four-neighbour slope is at least 12;
4. dilate the mountain mask through approved land by one cell everywhere and
   by a second cell where height is at least 125 or slope is at least 4; mark
   those non-mountain shoulder cells as hills;
5. classify remaining hills when height is at least 132 or slope is at least 6;
6. exclude the first two coastline-distance bands and a six-pixel settlement buffer from forest eligibility;
7. rank remaining pixels per state by `moisture_value()` and select an exact deterministic forest quota;
8. use 27.5 percent forest for island eligible land and 22.5 percent for each mainland state eligible land;
9. leave all remaining eligible pixels plains.

Reject a state if exclusions make its requested forest quota impossible. Re-run the existing plurality/urban declaration pass from the generated terrain, not from the pre-generation source.

- [ ] **Step 5: Implement low-resolution tree generation**

Add `TREES_PATH = ROOT / "map/trees.bmp"`. Preserve its palette bytes. For each tree-map cell, compute the exact full-resolution rectangle using integer floor boundaries:

```python
x0 = tx * full_width // tree_width
x1 = (tx + 1) * full_width // tree_width
y0 = ty * full_height // tree_height
y1 = (ty + 1) * full_height // tree_height
```

If a strict majority of sampled pixels belongs to the approved north mask, obtain the plurality generated terrain type and compare `stable_unit_hash(tx, ty, 23)` with `tree_probability(type)`. Eligible cells use palette 6 when `stable_unit_hash(tx, ty, 29) < 0.65`, otherwise palette 5. Ineligible approved cells become 0. Cells outside the approved low-resolution mask retain their original value.

- [ ] **Step 6: Add real-map coverage and exclusion contracts**

Compute metrics from generated outputs and require:

- island forest share between 25 and 30 percent after water/urban exclusion;
- each selected non-marsh mainland state forest share between 20 and 25 percent;
- forest tree occupancy between 50 and 72 percent;
- plains tree occupancy between 6 and 16 percent;
- hills tree occupancy between 1 and 7 percent;
- hills occupancy lower than plains and at most one fifth of forest occupancy;
- zero nonzero generated tree cells sampling water, urban, or mountain plurality;
- zero forest/hills/mountain changes outside the approved full-resolution
  north mask before the snow layer; any other terrain diff must belong to the
  old-or-new organic footprint union of an exact non-split
  `SETTLEMENT_PROVINCES` entry; the nine retained northern city IDs must be
  entirely urban and may change only inside their new province geometry;
- zero tree changes outside the approved downsampled mask;
- `trees.bmp` remains mode `P`, size 1650x600, with an identical palette.

- [ ] **Step 7: Wire outputs, validate, apply, and prove idempotence**

Set `GeographyOutputs.trees` to the rendered paletted image. Add drift messages containing exact height, normal, terrain, tree, and definition difference counts. Run:

```powershell
python -B tools/build_adiscord_ivn_geography.py --check
python -B tools/build_adiscord_ivn_geography.py --apply
python -B tools/build_adiscord_terrain_snow.py --apply
python -B tools/build_adiscord_ivn_geography.py --check
python -B tools/build_adiscord_terrain_snow.py --check
python -B -m unittest tools.tests.test_build_adiscord_ivn_geography tools.tests.test_build_adiscord_terrain_snow tools.tests.test_validate_adiscord_ivn_overhaul -v
```

Hash height, normals, terrain, trees, definition, and provinces; repeat
geography then snow apply in the same order and require identical hashes. The
province hash must equal the new exact post-split regression value established
in Task 3. Inspect only scoped diffs; do not stage them.

---

### Task 5: Replace repeated March names through owning builders

**Files:**
- Modify: `tools/builders/build_adiscord_new_states.py`
- Modify: `tools/builders/build_adiscord_strategic_regions.py`
- Modify: `tools/tests/test_validate_adiscord_ivn_overhaul.py`
- Modify: `tools/validators/validate_adiscord_ivn_overhaul.py`
- Modify: `tools/data/generated_output_owners.json`
- Modify: `tools/tests/test_generated_output_ownership.py`
- Generate: `history/states/695-Verkhnemarye.txt`
- Generate: `history/states/696-Longar-Plain.txt`
- Generate: `history/states/697-Rinval-Coast.txt`
- Generate: `history/states/698-Salemar-Basin.txt`
- Remove after exact generated-content verification: `history/states/695-Upper-March.txt`
- Remove after exact generated-content verification: `history/states/696-Eastern-March.txt`
- Remove after exact generated-content verification: `history/states/697-Western-March.txt`
- Remove after exact generated-content verification: `history/states/698-Southern-March.txt`
- Generate: `localisation/russian/state_names_l_russian.yml`
- Generate: `localisation/russian/victory_points_l_russian.yml`
- Generate: `localisation/replace/strategic_region_names_l_russian.yml`

**Interfaces:**
- Consumes: existing IVN state manifests and strategic region 6 membership.
- Produces: exact approved Russian names and exactly one history file per state ID 695-698.

- [ ] **Step 1: Add exact RED naming tests**

Add:

```python
EXPECTED_NORTHERN_NAMES = {
    25: "Старая марка",
    127: "Иторский север",
    695: "Верхнемарье",
    696: "Лонгарская равнина",
    697: "Ринвальское побережье",
    698: "Салемарское междуречье",
}
```

Require VP 16568 to remain `Старая марка`, VP 595 to equal `Северный кордон`, and strategic region 6 to equal `Северная Итора`. Require exactly one `history/states/<id>-*.txt` match for 695-698 and reject any of the four former filenames.

Require the `state_history` ownership family to set `may_delete_outputs` to
`true`, with a test confirming that the only newly introduced deletion code is
the exact four-entry former-filename manifest.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_ivn_overhaul tools.tests.test_validate_adiscord_new_states -v
python -B tools/build_adiscord_strategic_regions.py --check
```

Expected: exact name and filename failures, without syntax or decoding failures.

- [ ] **Step 3: Update state and VP manifests**

Set:

```python
IVANLAND_OVERHAUL_FILENAMES.update({
    695: "695-Verkhnemarye.txt",
    696: "696-Longar-Plain.txt",
    697: "697-Rinval-Coast.txt",
    698: "698-Salemar-Basin.txt",
})

GENERATED_STATE_NAMES.update({
    127: "Иторский север",
    695: "Верхнемарье",
    696: "Лонгарская равнина",
    697: "Ринвальское побережье",
    698: "Салемарское междуречье",
})
```

Update the generated VP-name manifest entry for 595 to `Северный кордон`. Do not alter entries 25 or 16568.

- [ ] **Step 4: Add guarded retirement of the four former files**

Define an exact state-ID-to-former-path map. Before removal, require the file to start with `# Generated by tools/build_adiscord_new_states.py` and contain the matching `id=<state_id>` token. Refuse deletion if either guard fails. Write the new file first, then remove only its verified former counterpart.

Set `state_history.may_delete_outputs` to `true` in the ownership manifest so
the metadata reflects the builder's guarded deletion capability. Do not add a
wildcard deletion routine; the builder may unlink only the four literal former
paths after both content guards pass.

- [ ] **Step 5: Update strategic region 6 through its builder**

Change only the name field of region 6:

```python
Region(6, "northern-itora", "Северная Итора", "cool_maritime", (89, 127, 128, 129, 130, 131, 132, 164, 693, 694))
```

Keep membership and weather profile unchanged.

- [ ] **Step 6: Apply owning builders and verify BOM/idempotence**

Run:

```powershell
python -B tools/build_adiscord_new_states.py --check
python -B tools/build_adiscord_new_states.py --apply
python -B tools/build_adiscord_strategic_regions.py --apply
python -B tools/build_adiscord_new_states.py --check
python -B tools/build_adiscord_strategic_regions.py --check
python -B -m unittest tools.tests.test_validate_adiscord_ivn_overhaul tools.tests.test_validate_adiscord_new_states -v
```

Require BOM bytes `EF BB BF` on both changed Russian localisation files and the strategic-region localisation. Hash the four new state files and three localisation files, repeat both applies, and require identical hashes. Confirm exactly one state file exists for each ID 695-698. Do not stage the implementation paths.

---

### Task 6: Register layered ownership and run the complete release gate

**Files:**
- Modify: `tools/data/generated_output_owners.json`
- Modify: `tools/tests/test_generated_output_ownership.py`
- Modify: `tools/validators/validate_adiscord_ivn_overhaul.py`
- Modify: `tools/tests/test_validate_adiscord_ivn_overhaul.py`
- Generate: minimap outputs owned by `tools.builders.build_adiscord_minimap`

**Interfaces:**
- Consumes: completed state, landscape, snow, and minimap builders.
- Produces: ordered generated-output ownership, aggregate IVN validation, and final static evidence.

- [ ] **Step 1: Add RED ownership assertions**

Require the `ivn_geography` family to list:

```json
[
  "map/heightmap.bmp",
  "map/world_normal.bmp",
  "map/terrain.bmp",
  "map/trees.bmp",
  "map/definition.csv"
]
```

Require those map files in `source_inputs`, keep `ownership_mode` as `layered`, and require `ivn_geography` before `terrain_snow` and `minimap` in `apply_sequence`.

- [ ] **Step 2: Run RED ownership tests**

Run:

```powershell
python -B -m unittest tools.tests.test_generated_output_ownership -v
```

Expected: failure because height, normals, and trees are not registered as IVN geography outputs.

- [ ] **Step 3: Update ownership manifest and aggregate validator**

Expand `ivn_geography.output_globs` and `source_inputs` with the five exact files. Replace its overlap explanation with a statement that the pass owns island height/normal cells, approved northern terrain/tree cells, IVN/IIA terrain declarations, full urban coverage for the nine split city cores, and compact urban footprints for other settlements; `terrain_snow` owns only its snow conversion. Add aggregate validator messages for any landscape builder drift and exact approved names.

- [ ] **Step 4: Run the ordered builder chain**

Run check mode first:

```powershell
python -B tools/build_adiscord_new_states.py --check
python -B tools/build_adiscord_ivn_geography.py --check
python -B tools/build_adiscord_terrain_snow.py --check
python -B tools/build_adiscord_strategic_regions.py --check
python -B -m tools.builders.build_adiscord_minimap
```

Apply only builders reporting drift, in this exact order:

```powershell
python -B tools/build_adiscord_new_states.py --apply
python -B tools/build_adiscord_ivn_geography.py --apply
python -B tools/build_adiscord_terrain_snow.py --apply
python -B tools/build_adiscord_strategic_regions.py --apply
python -B -m tools.builders.build_adiscord_minimap --apply
```

Repeat all five checks and require success.

- [ ] **Step 5: Run focused tests and validators**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_ivn_geography tools.tests.test_build_adiscord_terrain_snow tools.tests.test_validate_adiscord_ivn_overhaul tools.tests.test_validate_adiscord_new_states tools.tests.test_generated_output_ownership -v
python -B tools/validate_adiscord_ivn_overhaul.py
python -B tools/validate_adiscord_new_states.py
python -B tools/build_adiscord_strategic_regions.py --check
python -B tools/build_adiscord_terrain_snow.py --check
python -B -m tools.builders.build_adiscord_minimap
```

Require every command to exit 0.

- [ ] **Step 6: Run global static gates**

Run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Require the global validator to pass and both diff checks to produce no errors. Verify BOM bytes on every changed Russian localisation file and verify the province bitmap hash one final time.

- [ ] **Step 7: Review the final scoped diff and report runtime boundary**

List every changed path and separate pre-existing unrelated dirty paths from this implementation. Report exact height range, forest shares, tree-density shares, changed-pixel counts, image modes/sizes, idempotence hashes, focused test count, and global validator result. Do not claim correct rendered terrain until HOI4 has been fully restarted and checked in a fresh campaign.
