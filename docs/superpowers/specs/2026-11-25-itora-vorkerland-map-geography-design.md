# Itora and Vorkerland map geography

Status: design, not implemented. Nothing here has been checked in the running
game.

This record is the contract for the implementers. It extends the method of
`2026-11-22-mon-map-geography-design.md` (cited as "MON spec") to Itora and to
Vorkerland with its puppets. Where it disagrees with the builders after
implementation, the builders win and this record is corrected.

## 1. The author's orders

- "Займись теперь Иторой и Воркерландом: побольше городских провинций, хайт
  мапы, реки не должны пересикать и тд".
- "Под Воркерландом я имею в виду его и его марионетки".
- **Scope.** Itora (IVN, IIA) and WRK with its puppets except NAM and RIN.
  RIN belongs to MON stage 2. NAM gets only its off-border river fix.
- **Treatment.** The level of MON stage 2: split large provinces into round
  parts, carve a city per state and a town, recompute relief, rivers and
  terrain.
- **Declared terrain** is recomputed everywhere, including WRK and IVN.
- **Split rule.** Rural land provinces over 180 px split into parts of about
  100 px. This was chosen against the border budget (section 3).
- **WRK theatre VP package totals stay unchanged.** New cities and towns in
  those packages get their VPs by redistribution inside the package.
- **DAN (state 78) is postponed.**
- **Sequencing.** The spec and the tooling are prepared now. Map files are
  written only after the parallel MON stage 2 work is finished and committed.

## 2. Scope

| Group | Tag | States |
|---|---|---|
| Itora | IVN | 25, 92, 95-101, 127, 129-132, 164, 695-698, 713-717 |
| Itora | IIA | 128, 693, 694 |
| Vorkerland | WRK | 27, 32-40, 82, 200, 201, 320, 323-325 |
| Puppets | EYR | 75, 106 |
| Puppets | EGC | 81, 110, 124 |
| Puppets | RIV | 79, 306, 308, 309, 327 |
| Puppets | YOR | 102, 107-109, 111, 121-123 |
| Puppets | ZAO | 72, 195, 196, 322 |
| Puppets | PWR | 71, 90, 91, 93, 94, 194, 202, 328 |
| Puppets | VLA | 74, 105, 197, 311-314 |
| Puppets | ROM | 73, 144, 145, 319, 321 |
| Puppets | SOL | 76, 104, 198, 307, 310 |
| Puppets | TRU | 80, 146, 150, 199, 315-318 |
| Puppets | WCG | 151, 156-163, 223 |
| River fix only | NAM | the 11 off-border river pixels |

- The scope is fixed by state ids, not by current owners.
- Excluded:
  - DAN 78;
  - RIN 134, 147-149 (MON stage 2);
  - every province owned by the coastal geography builder (coastal-owned and
    `adiscord_river_bank_repairs.json` repair provinces);
  - all coastal provinces (for splitting only).

## 3. Current state and budget (measured 2026-11-25)

| Tag | Land provinces | Median px | Max px | Over 180 px | City-terrain provinces | Off-border river px |
|---|---|---|---|---|---|---|
| IVN | 320 | 133 | 301 | - | 24 | 85 |
| IIA | 81 | 151 | 284 | - | 3 | 20 |
| WRK | 136 | 92 | 279 | - | 77 (71 vorkernsberg) | 35 |
| EYR | 30 | 211 | 348 | - | 4 | 0 |
| EGC | 47 | 175 | 308 | - | 5 | 0 |
| RIV | 32 | 203 | 350 | - | 5 | 28 |
| YOR | 81 | 131 | 302 | - | 21 | 0 |
| ZAO | 71 | 132 | 204 | - | 2 | 7 |
| PWR | 134 | 144 | 375 | - | 1 | 42 |
| VLA | 60 | 202 | 452 | - | 9 | 33 |
| ROM | 89 | 126 | 203 | - | 9 | 21 |
| SOL | 54 | 240 | 583 | - | 8 | 0 |
| TRU | 134 | 144 | 333 | - | 8 | 43 |
| WCG | 101 | 140 | 287 | - | 0 | 51 |

New ids from splitting at 180/100, non-coastal only:

| Tag | New ids |
|---|---|
| IVN | 56 |
| IIA | 13 |
| WRK | 30 |
| EYR | 18 |
| EGC | 37 |
| RIV | 37 |
| YOR | 32 |
| ZAO | 5 |
| PWR | 18 |
| VLA | 71 |
| ROM | 9 |
| SOL | 51 |
| TRU | 29 |
| WCG | 21 |
| **Total** | **about 427** |

Cities and towns add about 220 more ids.

**Border budget.**
- HOI4 allows 65,536 adjacent province pairs. 60,470 were used on 2026-11-25
  with MON stage 2 on the map.
- A new province costs about 3.1 pairs.
- The plan (about 650 ids, about 2,000 pairs) must leave at least 2,000 spare
  pairs after MON stage 2 is final.
- Each planner reports its projected count and refuses a plan that breaks the
  margin. If stage 2 grows before its commit, raise the split threshold here,
  not the margin.

## 4. Architecture

Two builders own the work. No new data file is created except where noted.

### 4.1 Itora: a second plan in `build_adiscord_ivn_geography`

IVN and IIA geometry, relief, terrain, trees and rivers already belong to the
IVN builder (manifest `tools/data/adiscord_ivn_provinces.json`, raster
`tools/data/adiscord_ivn_province_geometry.png`). MON's builder deliberately
freezes an 8 px band around them. Itora therefore gets a stage-2 plan inside
the IVN builder.

**Manifest.**
- A `stage2` section with its own `origin`, `first_id`, `provinces` and
  `cities`. Entries are `{province, parent, state, kind: remainder|district|part|town, rgb}`.
- The raster gets a second layer under a `sheet_row`, as in MON.
- Stage 1 stays exactly as reviewed.

**Planner `--plan-stage2-provinces`.**
- Reads the current state lists, so stage-1 ids are valid parents.
- Splits non-coastal rural provinces over 180 px into parts of about 100 px.
  It uses MON's `partition_province`, imported rather than copied:
  roundness >= 0.35, at least 50 px, state pixel sets unchanged, river
  pixels and their neighbours locked.
- Carves cities and towns. In stage 2 a city keeps its parent id and the
  remainder gets a new id. Stage 1 did the opposite; that convention stays
  for stage-1 entries.
- Refuses to run when a stage-2 plan exists or the border margin breaks.

**Cities and towns.**
- Every IVN/IIA state without a city province gets one carved 40-50 px city.
- Every state gets one carved 30-40 px town.
- Port towns 18993/18994 and the Nordholm garrison stay as they are.

**Terrain.**
- The IVN classifiers stay (march relief and the northern landscape).
- Split parts and remainders take their terrain from the same per-pixel
  class. `RELIEF_EXCLUDED_PROVINCES` and `AUTHORED_RIVER_PROVINCES` are
  resolved through the root parent, not the direct parent.

**Rivers.**
- The 85 + 20 off-border pixels are re-routed onto borders.
- The rule of 6.3 holds.

**Pins to refresh** after the apply:
- `EXPECTED_IVN_GEOMETRY_SHA256`;
- `test_reviewed_states_are_never_replanned`, so that it guards stage 1 and
  stage 2 separately;
- `test_province_geometry_is_unchanged`;
- the coverage bands (forest 0.50-0.72, plains 0.02-0.07, hills 0.01-0.05),
  re-measured and justified;
- `ORIGINAL_PROVINCES` / `REPARTITIONED_STATES` / `EXPECTED_VPS` in
  `test_validate_adiscord_ivn_overhaul.py`;
- the Itoran rail and hub tests of the theatre.

### 4.2 Vorkerland: regions of the east geography builder

- The puppets and WRK become regions of the MON builder
  (`build_adiscord_mon_geography.py` and `adiscord_mon_geography.json`),
  after the generalisation that MON spec 13.6 already plans.
- **This work starts only after the parallel session has finished and
  committed MON stage 2**: it is editing those files now.

The generalisation needed:

1. **Stages.** Replace the hard-coded two layers with a list `stages[]`, each
   with `origin`, `sheet_row`, `first_id`, `provinces`, `cities`, `towns`.
   Update every consumer:
   - `geometry_layers`, `register_planned_rows`, `load_scope`;
   - the stage-2 refusal, `record_stage2_pixels`;
   - `mon_plan_stages` in `build_adiscord_northern_countries`;
   - `_east_planned_parents` in strategic regions;
   - `applied_mon_plan` in map buildings;
   - the trade-region validator.

   Vorkerland is stage 3.
2. **Per-region parameters.** `split_threshold` / `split_part` (180 / 100
   here), height range (`heights` per region; Vorkerland keeps peaks up to
   238), and the terrain classes allowed.
3. **Terrain classes.**
   - Add `desert` to the rural classes: EYR, EGC, SOL, YOR and VLA are
     largely desert. Desert zones are authored in the region data.
   - Province terrains in `CITY_TERRAINS` (`vorkernsberg`, national city
     terrains) are kept, never recomputed.
   - The 13 conurbation provinces pinned by `test_vorkerland_nam_state_balance`
     stay `vorkernsberg`; 10016 stays `mountain`.
   - Snow masses at height >= 205 keep the `terrain_snow` total in
     320k-400k.
4. **An `adopt` settlement kind.** A state that already has a city province
   (an urban VP province, the carved cities 16560-16643 of
   `vorkerland_cities.TARGET_PROVINCES`, the WRK capital quarter) adopts it
   instead of carving a new one. Adopted cities keep their geometry and their
   `cities.bmp` pixels; `vorkerland_cities` keeps owning those masks.
5. **Exclusions.**
   - The WRK capital states 32-40 are not split: median 72 px, dense
     landmarks.
   - Only towns may be carved there, and only outside `LANDMARK_CLEARANCES`,
     the hand-placed skyline in `ambient_object.txt` and the Isaiah tower
     footprint (6192).
   - The Unity Tower province 16428 is never a parent of new geometry.
6. **Landmarks.**
   - Relief under the Isaiah tower footprint and the capital skyline keeps
     the heights those objects were placed at. Model the plinth as a keep
     zone.
   - The Isaiah tower report needs a Blender rebuild after the apply.

## 5. Owners of state files, VPs and rails

### 5.1 `build_adiscord_new_states` (most scope states)

Add one narrow mode `--apply-east-geography` (and its `--check` drift entry).

**Province lists.**
- Append the planned provinces of the applied stages to each state with
  `with_appended_provinces(source, planned, 16)`, as
  `archipelago_island_plan` does.
- Check that every parent is in the state, every row is land and no other
  state lists the province.
- Feed the same provinces into `render_state`, `ivanland_state_provinces` and
  `validate_ivanland_split_inputs`, so the whole-file renderers keep them.
- Gate each stage on all its ids being present in `definition.csv`, as
  `mon_planned_entries` does.

**VPs.**

| States | Rule |
|---|---|
| Non-theatre | Extend `REGIONAL_SETTLEMENTS` from the geography data, as the southern `regional_town` loop does |
| Theatre | Merge into `VORKERLAND_THEATRE_VICTORY_POINTS` with the package totals of `VORKERLAND_THEATRE_PACKAGE_TOTALS` unchanged (author's order). A new city or town takes points from the other VPs of its package; no package total moves |
| IVN/IIA | Extend `IVANLAND_SETTLEMENT_VICTORY_POINTS` or the rural table |

- Carved cities and towns are declared `urban`. Their VPs are listed in
  approved tables, so `validate_adiscord_new_states` passes.
- An urban town under 10 points needs the explicit exception in
  `regional_settlement_plan`, like `svetlogorye_town`.

**Names.**
- Russian names come from the geography data.
- Each name needs a reviewed `{russian, english}` pair in
  `adiscord_world_names_english.json` under the `new_states` block, then
  `--english-localisation --apply`.
- Names follow each country's toponyms (its state and VP names) and are
  checked against all localisation for collisions.

**Never run** the full `new_states --apply`, or `--apply-state-metadata` /
`--apply-legacy-state` on these states: they reformat files and rewrite
buildings.

### 5.2 `build_adiscord_inner_frontier_countries` (TRU 146/150, WCG)

- It already appends planned provinces for states in the geography scope.
  Extend its scope intersection to the new regions.
- `check_mon_settlements` needs exactly one city per scope state.
- `exclusion_zone_boundaries` must keep the children of 156, 160 and 223
  through `snapshot_children`; otherwise its `--apply` drops them.

### 5.3 Vorkerland collapse manifest (`tools/lib/vorkerland_collapse_manifest.py`)

- `STATE_PARTITIONS` pins the province sets of 71/194, 72/195/196, 74/197,
  76/198 and 80/199.
- New ids join the partition of their root parent, derived from the
  geography data rather than listed by hand.
- `CAPITALS` keep their ids (parent keeps id).
- Update `validate_adiscord_vorkerland_collapse.py`.

### 5.4 Rails and hubs

- The geography builders never write `railways.txt`.
- **Theatre-managed lines** (`MON_SUPPLY_RAILS`-style constants,
  `ITORA_SUPPLY_RAILS`, `WEST_TRUNK_RAIL_UPGRADES`, `WEST_CORRIDOR_RAILS`,
  `STARTING_SUPPLY_RAILS`, `OSV_CAPITAL_RAIL`) are rerouted in
  `build_adiscord_vorkerland_theatre.py` through the part or remainder the
  planner names.
- **Unmanaged lines** have no owner; MON stage 2 hit the same gap. Add a
  repair step that inserts the named part or remainder into such lines,
  owned by the east geography builder as a layered output of
  `railways.txt`. No hand edits.
- **Line format.** A line never visits a province twice; split a spur
  instead. The count field equals the province count.
- **Hubs** stay on their ids: the part holding a hub keeps the parent id.

## 6. Geography design rules

### 6.1 Splitting

- Rural, non-coastal land provinces over 180 px split into
  `ceil(area / 100)` parts of about 100 px.
- **Locks:**
  - naval-base and port anchors, lakes;
  - coastal-builder provinces;
  - provinces of another builder;
  - WRK states 32-40.
- **The part that keeps the parent id** holds, in order: any literal used
  by script (section 7), the VP, a supply hub, the most rail contacts, the
  slot-0 anchor, the most pixels.
- **Parts:**
  - roundness >= 0.35, at least 50 px, inside their state;
  - no part may cut a rail chain: each chain neighbour keeps contact with
    the part on the chain, or the reroute is listed.

### 6.2 Settlements

- **Cities.** Every state has one city, carved 40-50 px or adopted.
  - The capital of each country gets a carved district of 45 px when it is
    carved.
  - Existing VP provinces become the cities of their states.
- **Towns.** Every state gets one carved town of 30-40 px, VP 1-2, at least
  10 px from the city, preferring a river bank or a rail province. A town
  replaces nothing in WRK 32-40.
- **VP values outside theatre packages.**
  - Capitals: unchanged.
  - New cities: 3-5.
  - Towns: 1-2.
- **Visuals.**
  - City and town pixels get `cities.bmp` 15 and terrain 13 over the whole
    province, up to its border and never past it; only the shoreline band
    stays clear. The east builder covers 78-90 % of each urban province
    off the shore with a frayed edge and no houses outside it (MON spec
    13.5a).
  - Frozen strips keep their heights, not stale textures: their pixels take
    the declared palette of their province. The detached IVN islands keep
    their authored relief and are painted in their declared terrain.
  - Forest provinces of both builders are wooded throughout: every tree
    cell wholly on forest carries trees, and only cells where the forest
    meets other ground keep the ordinary 62 % share (MON spec 13.5a).
  - Night lights come from the coastal builder's whole-map pass. No scope
    state is EXZ-owned; WCG states beside EXZ stay lit only where they own
    the pixels.

### 6.3 Rivers

- Every river pixel lies on a province border with different provinces on
  its two sides.
- No course cuts a province or hops through its interior.
- No river palette 5 or 8: native rivers use 3, 4, 6, 7, 9, 10 and 11.
- Tributary ends are palette 1, 4-adjacent to the receiving river.
- Components that leave the scope keep their entry and exit pixels; 186 river
  pairs cross the scope edge today.
- Off-border pixels are re-routed or the course is moved, never the land of a
  pinned frontage.
- NAM's 11 off-border pixels are fixed as `river_courses` entries in
  `adiscord_river_bank_repairs.json` (coastal builder owner).

### 6.4 Relief

- Per-country relief comes from state names (uplands, hills, forest, plain,
  desert, lakes), authored as levels, uplands, ridges, basins and zones.
- Each region has its own height range. Peaks above 205 stay where they
  already are, so permanent snow does not move.
- Relief blends to outside heights at the scope edge (8 px). Valleys are
  carved under rivers from the in-memory routes. Towns and cities are
  levelled with their surroundings.
- The landmark keep zones of 4.2.6 apply.

### 6.5 Declared terrain

- Rural provinces are recomputed from the per-pixel classes with the
  province rule of MON spec 5.4.
- City terrains are kept.
- Acceptance bands per country are re-measured from the plan and recorded in
  the data; each state's named landform holds the majority.
- `contaminated` and `reactor_zone` never appear.

## 7. Literals that must stay on their parent ids

The split rule of 6.1 must keep every id below on the piece that keeps the
parent id. Naval-base provinces must also keep sea contact.

- **Bunkers:** 12227, 16400, 16397, 6192, 6713, 3248.
- **Unity Tower:** 16428.
- **Naval bases:** 16568, 4443, 8243, 11944, 10730, 11841, 2553, 5986, 18994.
- **ZAO bunker:** 16622.
- **OOB locations** of WRK, VAD, TVA_collapse, IVN, IIA, PWR, ROM, TRU, VLA,
  ZAO, SOL, WCG/KRM/LMN and the collapse successors. See
  `test_validate_adiscord_vorkerland_collapse.py` and
  `test_vorkerland_worx_supporters.py`.
- **Ports and hubs:**
  - the starting-navy ports in `tools/lib/adiscord_starting_navies.py`;
  - the export ports 5986 and 16568;
  - every supply hub of the theatre and of `ITORA_SUPPLY_RAILS`.

A test lists these ids and asserts that each keeps its id, stays land and
keeps sea contact where it has a naval base.

## 8. Apply chain (lead only, after MON stage 2 is committed)

Snapshot the map, the scope state files, the units, the VP localisation and
the English names JSON first. Check `definition.csv`'s last id before
planning.

1. IVN `--plan-stage2-provinces`, then the east builder's stage-3 plan, then
   both previews. **Author checkpoint**: the user reviews cities, towns,
   splits, rivers and relief.
2. IVN `--apply` and the east builder `--apply`, each twice. The second
   run must change nothing.
3. `new_states --apply-east-geography`, `inner_frontier_countries --apply`,
   `exclusion_zone_boundaries --apply`, `northern_countries --apply` if
   the stage list changed its inputs, then `--english-localisation --apply`
   for each owner.
4. `vorkerland_theatre --apply` after the constant reroutes.
5. `coastal_geography --apply` (night lights and NAM river fix),
   `map_buildings --apply`, `strategic_regions --apply`,
   `trade_regions --apply`, `ambient_audio --apply`, `minimap --apply`.
6. Map renderers: `vorkerland_capital_map`, `west_influence_map`,
   `val_operations_map`, `--check` of the others.
7. Blender reports: `isaiah_tower`, `nam_oilfields`.
8. Refresh the IVN outside-scope hashes. First prove that every changed byte
   lies inside the two scopes plus the normal feather.
9. Focused tests, `python -B tools/validate_tc.py --limit 300`,
   `git diff --check`.

## 9. Tests

- Each builder: `--check` clean, second apply idempotent, scope-only diffs,
  state pixel sets unchanged, border margin kept.
- Splits: part sizes, roundness, rail contacts, the literal list of
  section 7.
- Settlements: one city per state, one town per state, VP values, package
  totals unchanged, names unique with English pairs.
- Rivers: the rules of 6.3 over the whole scope; no palette 5 or 8; no
  province split by a river.
- Terrain: bands, named landforms, kept city terrains, snow total.
- Owners: state lists include every planned id exactly once; collapse
  partitions; EXZ snapshot children.

## 10. Gameplay consequences

Flag these to the author:

- **Recalculated declared terrain** changes combat in the Vorkerland and
  Itora civil wars, which were balanced on the old terrain. Check the
  civil-war outcomes in text saves after the change.
- **Package totals stay fixed**, so the Vorkerland capitulation pace does
  not move. Puppet and Itora VPs grow.
- **More provinces** mean longer fronts in the affected states and slightly
  more AI and pathfinding work.

## 11. Implementation packages

The file sets are disjoint. Agents never run `--apply`, commit or reset.

| Package | Files | When |
|---|---|---|
| A - Itora stage 2 | `build_adiscord_ivn_geography.py`, the IVN manifest and raster, its tests and the IVN overhaul validator tests | Now, code and tests only. Plan after the stage 2 commit |
| B - state owners | `build_adiscord_new_states.py` (the new mode), `validate_adiscord_new_states.py`, `tools/lib/vorkerland_collapse_manifest.py` and its validator, the theatre VP manifest, the English names JSON `new_states` block, and their tests | Now, against the data schema |
| C - east builder generalisation and Vorkerland regions | `build_adiscord_mon_geography.py`, `adiscord_mon_geography.json`, its tests, the stage-list consumers in northern countries, strategic regions, map buildings and trade regions, and the rail repair step | After the parallel session commits MON stage 2 |
| D - theatre reroutes and the NAM river fix | `build_adiscord_vorkerland_theatre.py` constants, `adiscord_river_bank_repairs.json` | After the plans exist |

The lead runs the plans, the author checkpoint, the apply chain, the pins and
the full gate, and reviews the combined diff with `rules-reviewer`.

## 12. Runtime verification (the author, after a full restart)

- `error.log` clean of map, province, river and unitstack errors.
- City meshes and lights in the new cities and towns. No floating buildings.
  The Isaiah tower and the capital skyline sit on the ground.
- Rivers on borders with no gaps at confluences.
- VP names in both languages. Units and fleets in their provinces.
- A short Vorkerland civil war and an Itora civil war for balance.

## 13. State borders and new states (second order of 2026-11-25)

### 13.1 Orders

- "Так границы штатов красивее сделай".
- "Мб ещё штаты где-то поделай".
- "Лучше, чтобы штаты тож не пересекали границы рек (в идеале)".
- Answers: smooth every land border between two scope states, including
  country borders inside the scope; the Itora-Vorkerland seam stays as it is.
  Split the six largest states in two: PWR 71 and 194, ROM 73, TRU 80 and 199,
  IIA 693.

### 13.2 Measured before the change (map after stage 3)

- Map median land state: 2,896 px. The six states: 693 7,426 px (56 provinces,
  a main island and one 177 px islet), 71 7,176 px (53), 73 5,985 px (54),
  194 5,344 px (47), 199 5,241 px (45), 80 4,843 px (42).
- Scope river pixels: 3,117; 2,422 on a state border, 695 inside one state.
  Most of the interior river is Itoran: 693 150, 717 121, 101 49, 716 47,
  698 46, 715 45. Vorkerland: 32 51 (frozen capital), 195 36, 223 33, 199 17.
- Prototype smoothing (5x5 majority, radius 4, eight passes, 55 % share,
  protected pixels as in 13.3) moves 2,640 pixels and shortens the state
  edge from 26,255 to 25,568 pixels. Previews:
  `docs/development/previews/vorkerland_states/`.

### 13.3 Smoothing rule

- A land pixel on the border of two scope states joins the state that holds
  at least 55 % of its land neighbours within radius 4. It joins the
  neighbouring province of that state it touches most. Passes repeat, at
  most eight, until none changes.
- The east call runs up to sixteen passes. Its longer lines, with the split
  states among them, still move a few pixels up to the thirteenth pass, and a
  plan is written only once a further pass would move nothing, so a second
  run moves no pixel. The east
  layer marks the moved pixels with alpha 254; the map pass stamps them like
  any planned pixel, and its state-area check lets exactly those pixels
  change state.
- Never moved: river pixels and the pixels beside them, so a border along a
  river keeps its course; pixels of city, town and district provinces and
  one pixel around them; one pixel along every coast; frozen states 32-40;
  the 8 px seam between the IVN and east geographies; pixels whose move would
  disconnect their province, drop it under 25 px or create a four-province
  2x2 square.
- Kept contracts: every railway segment stays between adjacent provinces;
  every province keeps a slot 0 anchor inside it; the border-pair margin
  stays at or above 2,000; state province lists do not change, only the
  pixels of provinces move.
- Implemented once, in `build_adiscord_ivn_geography.py` next to the shared
  geometry helpers, and called by the IVN stage 2 plan and by the east
  builder's stage 3 plan. The result is stored in each plan raster, so the
  map pass only stamps it.

### 13.4 Rivers prefer state borders (best effort)

- New and rerouted courses of both builders prefer a province border that is
  also a state border when the other river rules allow it.
- A split line of 13.5 follows a river wherever it can.
- Report interior river pixels per state before and after. No river is cut,
  merged or moved off a province border to meet this goal.

### 13.5 Six new states

- New ids 734-739, in this order: 734 from 71, 735 from 194, 736 from 73,
  737 from 80, 738 from 199, 739 from 693.
- **Cut.** Each half is connected, holds 38-62 % of the state's area (30-70 %
  for 693) and at least one VP. The cut cost of a shared border is its length,
  at 1 % where it carries a river. For 693 the cut follows the main river
  across the island: the two banks of its main stem seed the halves and a
  minimum cut closes the gap to the coast. The islet stays with the half that
  holds the capital VP 18994.
- The half that holds the parent's largest VP keeps the parent id; its main
  VP province stays the parent's capital.
- **State data.** Owner, cores and claims are copied. Manpower and
  population follow the land area share, rounded to 10,000. Factories are
  split with the larger share in the parent; at least one level stays in
  each half when the parent has two or more. Infrastructure and
  `local_supplies` are copied. Resources follow the area share, and their
  totals are conserved. The category comes from the new population.
  Buildings stay in the province that holds them. VPs follow their provinces.
  The largest settlement of the new half is its centre: its VP rises to 3
  where the half has no VP of 3 or more. Totals of the central-theatre
  packages are unaffected, because none of the six states is in a package.
- **Settlements.** The centre of a new half (258, 9269, 16618, 265, 16704,
  16695) counts as the city and the town of its state; nothing new is carved
  for a half. A parent's existing city, adopted city and town stay planned
  settlements of whichever half holds their province, and the two halves
  together keep the parent's one city and one town.
- **Geography data.** The history files are authoritative. In both geography
  data files a planned province and a settlement take the state of their
  province; in the east data the region `states` lists and `levels[].states`
  gain the child right after its parent, and `landforms` give the child the
  parent's landform. `capital_state` stays with the parent, which holds the
  capital, and the planner's `grouping_centres` stay as recorded. A half
  with its parent's landform shows it together with the parent half: the
  landform was authored for the whole land, and a half may hold only its
  hills or its marshes.
- **Names.** `STATE_734` to `STATE_739` in Russian (`state_names_l_russian.yml`,
  BOM kept) and English (`localisation/replace/state_names_l_english.yml`),
  named after their land or main settlement in the country's naming style.
- **Collapse.** `vorkerland_collapse_manifest.AUTHORED_STATE_PARTITIONS`
  gives each new state the same successor as its parent half. 71 already
  splits into 71 and 194, and 80 into 80 and 199; each child now has its own
  child.
- **Scripts.** Review every reference to the six parent ids: the collapse
  transfers in `ADISCORD_vorkerland_effects.txt`, the PSD and ZTA capitals and
  cores (194, 199), `ADISCORD_RUS_scripted_effects.txt` transfers, the
  `controls_state = 199` decision condition, the west final war scripted GUI
  map entries, the IVN focus effects on 693 (`focus_trees/IVN/main`, then the
  focus builder), the NAM resource-war effect on 80, and the debug decisions.
  A transfer, core or ownership test that means the whole region covers both
  halves; a capital or a single site stays with the half that holds it.
- **Downstream.** Strategic regions, map buildings (every new state gets the
  full set of state building anchor rows in its own provinces), the
  inner-frontier and exclusion-zone checks, AI strategy references, the
  generated-output owner globs (`73[4-9]`), and the validators that pin
  state counts (trade regions: `EXPECTED_STATE_COUNTS`).

### 13.6 Packages and order

| Package | Files | When |
|---|---|---|
| E - smoothing and river preference | `build_adiscord_ivn_geography.py` and its tests; then the stage 3 call in `build_adiscord_mon_geography.py` | IVN part now; the east call after the MON session frees its builder |
| F - state splits | `build_adiscord_new_states.py` split table and renderer, its validator and tests, the collapse manifest, state-name localisation and the English names JSON, the owner globs | Now; data from the lead's cut proposal |
| G - scripts | the script files of 13.5 | After F fixes the ids |

Apply order: IVN plan with smoothing, east plan with smoothing, both applies
twice, `new_states` split apply, then the chain of section 8 and the
validators. Runtime checks remain the author's.

### 13.7 Gameplay consequences

- Six more states give the PWR, ROM, TRU and Itoran fronts more objectives
  and supply nodes; the civil-war successors gain or lose them with their
  parent halves.
- Smoothing moves land between neighbouring states by a few pixels; no
  province changes state.
