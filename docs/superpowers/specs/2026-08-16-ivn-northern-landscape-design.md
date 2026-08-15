# IVN Northern Landscape Design

**Date:** 2026-08-16
**Status:** Approved direction; implementation plan pending user review
**Selected approach:** Deterministic, scoped landscape generation

## Province-editor handoff amendment

The automated nine-city province split was withdrawn at the user's request.
`map/provinces.bmp`, `map/unitstacks.txt`, and `map/buildings.txt` remain at the
pre-split repository geometry. The user will author the province cuts in the
map editor and provide that result for a later synchronization pass.

Until that handoff, the active landscape pass must not write province geometry,
unitstack positions, building positions, reserved province IDs, state
membership, or strategic-region membership. The current generated urban
terrain footprints may remain in `map/terrain.bmp`; height, normals, terrain,
and trees may still be refined against the unsplit province map.

## Goal

Give the IIA island a readable three-dimensional landform, expand northern
forest coverage, synchronize the low-resolution tree map with painted terrain,
replace repeated `March` state names, and enforce the mod's approximate
one-province/one-dominant-texture rule around all nine northern VP settlements.

## Approved scope

- Sculpt `map/heightmap.bmp` only inside the province union of island states
  128, 693, and 694.
- Repaint forest and related terrain only inside island states 128, 693, and
  694 plus mainland IVN states 127, 129, 130, 131, 132, and 164.
- Synchronize `map/trees.bmp` for the same island and mainland IVN scope.
- Regenerate the corresponding island area of `map/world_normal.bmp` from the
  new height field.
- Recalculate declared province terrain for affected IVN and IIA provinces
  after the graphical terrain pass.
- Rename state 127, states 695-698, victory point 595, and strategic region 6.
- Leave state 25 and victory point 16568 named `Старая марка`.
- Do not change BOR state 89 even though it shares strategic region 6.
- Split the nine northern settlement provinces `595`, `579`, `1971`, `3447`,
  `2262`, `423`, `4217`, `6905`, and `11841`. The existing ID remains the
  compact city core; deterministic new IDs are assigned to the surrounding
  land and added to the same state.
- Preserve coastlines, VP/OOB/rail/supply references, and ports. Coastal city
  cores that host naval infrastructure remain coastal.

## Baseline evidence

- The island occupies 12,396 full-resolution land pixels within bounding box
  `(2649, 791)-(2792, 1000)`.
- Its current height range is only 97-123 with 15 distinct values.
- All 1,066 sampled island cells in the 1650x600 tree map use palette index 0,
  so the island currently has no painted trees.
- The island graphical terrain contains only 745 palette-4 forest pixels,
  approximately six percent of its land mask.
- Mainland state 129 already has dense trees and should be blended into the
  new regional pattern rather than blindly overwritten. States 130, 131, 132,
  and 164 currently have no sampled tree cells.
- `map/heightmap.bmp` is 5632x2048 grayscale; `map/world_normal.bmp` is
  2816x1024 RGB; `map/terrain.bmp` is 5632x2048 paletted; and `map/trees.bmp`
  is 1650x600 paletted.

## Landscape generation

### Island height field

The island height field is deterministic and analytic. It combines distance
from the coastline, a broad curved north-south ridge, two subordinate upland
lobes, shallow valleys, and low-amplitude smooth noise. No uncontrolled random
state or manual bitmap paint is accepted as the source of truth.

Target bands:

- coastal shelf and immediate lowland: 97-105;
- rolling lowland: 106-129;
- hills and shoulders: 130-149;
- principal ridge and summits: 150-175;
- hard maximum below 180.

The maximum remains safely below the existing permanent-peak snow threshold
of 205. The generator must feather heights near the coast, avoid one-pixel
spikes and pits, and create enough distinct values and local gradient variation
to remove the current stepped, nearly flat appearance.

Only island land pixels may change in `heightmap.bmp`. Water and all mainland
height pixels remain byte-for-byte unchanged.

### World normals

The island footprint in `map/world_normal.bmp` is regenerated from the final
height field at the map's one-half resolution. The implementation must first
derive and test the channel orientation and scale against unchanged portions of
the existing height/normal pair. It then replaces only normal-map cells whose
full-resolution footprint intersects island land, with a one-cell feathered
edge to prevent seams. The blue channel and RGB encoding remain compatible
with the existing map format.

## Terrain and forest distribution

Terrain classification uses final height, local slope, coast distance, and a
deterministic broad-scale moisture field.

- Steep or high pixels remain hills or mountains.
- Forest is concentrated in lowland interiors, valleys, and sheltered hill
  shoulders.
- Plains remain around settlements, transport corridors, and open coastal
  lowlands.
- State 164's existing marsh is preserved except for small deterministic
  boundary blends where necessary.
- Each of the nine northern settlements is a compact urban province, not a
  partial urban texture painted across a much larger rural province. The old
  province ID is retained for the city core so existing VP, unit, railway,
  supply, and building references remain valid.
- City boundaries are deterministic, connected, organic, and never rectangular
  blocks or long straight horizontal/vertical cuts. The surrounding remainder
  is connected wherever possible; disconnected meaningful components receive
  separate new province IDs rather than producing invalid enclaves.
- Province `6905` is special-cased by terrain fitness: its urban core is selected
  on low-slope lowland and may not overlap the generated mountain mask. Its
  principal ridge is kept outside the city province and may receive a separate
  mountain-dominant province ID when required for the one-texture rule.
- Water terrain is never modified.

Coverage targets are measured after excluding water and urban footprints:

- island forest terrain: 25-30 percent;
- selected mainland northern IVN forest terrain: 20-25 percent overall;
- each affected non-marsh state retains meaningful non-forest open land;
- mountain and hill terrain remains visually continuous with the new island
  height field.

After painting, the existing IVN geography plurality logic updates column 6 of
`map/definition.csv` for affected provinces. Settlement cores are entirely
palette-13 and declared `urban`; every new rural province receives one dominant
painted combat terrain and a matching declaration. Small transition shoulders
may cross a province only where needed to avoid an abrupt mountain/plains edge.

## Province split contract

The province split is generated and reviewable rather than hand-painted. It
owns the exact pixel transfers from the nine source provinces and appends new
rows to `map/definition.csv` using unused IDs beginning at `16654` and unique
RGB colours. It also updates only the nine owning state province lists.

The splitter must prove all of the following before apply:

- every source pixel is assigned exactly once to its retained core or a new
  same-state province, with no changes outside the nine source colours;
- all resulting land provinces are four-neighbour connected;
- each retained old ID contains its intended VP location and every required
  building/port anchor; coastal flags match actual coastline contact;
- no VP value, OOB placement, railway, supply-node, or building definition is
  silently moved to a new ID;
- no province colour is duplicated and all new IDs/colours are deterministic;
- state membership is updated through the state-history owner and subsequent
  generated map-building output is resynchronized;
- each new land province receives deterministic valid entries in
  `map/unitstacks.txt`, with its primary anchor placed on an interior pixel;
- existing unitstack rows whose coordinates fall outside their retained city
  core are deterministically repositioned to interior core pixels while their
  province ID, position kind, rotation, and scale metadata remain unchanged;
- province `6905` receives a new low-slope coastal presentation anchor because
  its former anchor lies on the height-175 summit; this moves no VP, OOB,
  building, port, railway, or supply reference;
- the strategic-region owner regenerates region 6 so every new province ID is
  assigned to the same air region as its source state;
- the final province bitmap has a new exact SHA-256 regression contract and a
  second apply is byte-identical.

## Tree map synchronization

The tree pass computes a separate province and terrain mask at 1650x600 rather
than assuming full-resolution pixel coordinates. A low-resolution cell is
eligible only when its sampled footprint is land and belongs to an approved
IVN or IIA state.

The pass uses the northern tree palette entries already present in the map,
primarily indices 5 and 6. Placement is deterministic and dithered to avoid
rectangular or province-shaped edges.

Relative density contract:

- forest terrain: dense but non-solid coverage;
- plains: occasional groves;
- hills: sparse cover, several times less frequent than forest;
- mountains, urban terrain, water, and the immediate coastline: no trees;
- marsh: preserved or lightly wooded only where the existing palette and
  terrain contract support it.

Validation must compare densities by terrain class rather than rely only on a
global tree count. Hill density must remain below plains density and far below
forest density. No generated nonzero tree cell may sample water or an urban
footprint.

## Names

Russian player-facing names become:

- state 25 and VP 16568: `Старая марка` (unchanged);
- state 127: `Иторский север`;
- VP 595: `Северный кордон`;
- state 695: `Верхнемарье`;
- state 696: `Лонгарская равнина`;
- state 697: `Ринвальское побережье`;
- state 698: `Салемарское междуречье`;
- strategic region 6: `Северная Итора`.

Generated state filenames for 695-698 use ASCII geographic names rather than
`Upper-March`, `Eastern-March`, `Western-March`, and `Southern-March`. The
generator must explicitly retire only those four verified legacy filenames so
duplicate state IDs cannot remain.

Russian localisation stays UTF-8 with BOM. Technical IDs and filenames remain
ASCII/English.

## Ownership and build order

Add a narrow province-split pass before the landscape pass. It owns only the
nine approved source colours in `map/provinces.bmp`, their appended definition
rows, deterministic position records for the generated IDs, and the
corresponding generated state province-list additions. The
existing `tools.builders.build_adiscord_ivn_geography` then owns:

- island pixels in `map/heightmap.bmp`;
- corresponding cells in `map/world_normal.bmp`;
- terrain pixels inside the approved northern IVN/IIA mask;
- tree cells inside the downsampled approved mask;
- terrain column 6 for affected rows of `map/definition.csv`;
- full palette-13 coverage of the nine retained northern city-core provinces;
- deterministic organic urban footprints for other existing IVN/IIA
  settlements outside this nine-province split.

Ownership remains layered because terrain snow also writes `terrain.bmp` and
other builders write different `definition.csv` fields. Apply order is:

1. northern city province split and state-membership update;
2. state history and naming builders;
3. IVN northern landscape;
4. map-building synchronization;
5. permanent-snow terrain pass;
6. minimap generation.

The landscape height ceiling intentionally prevents new permanent-snow pixels,
but the snow pass is still rerun and checked because it consumes height and
terrain.

## Safety and verification contracts

- Replace the former province SHA-256 with the deterministic post-split hash and
  require zero changes outside the nine approved source provinces.
- Preserve image dimensions, modes, and palettes for every modified BMP.
- Require zero changed `heightmap.bmp` pixels outside island land.
- Require zero changed `terrain.bmp` pixels outside the approved north mask,
  apart from separately owned deterministic snow output.
- Require zero changed `trees.bmp` cells outside the approved downsampled mask.
- Require zero changed `world_normal.bmp` cells outside the island-derived
  normal mask and its one-cell seam feather.
- Check height range, distinct-value count, gradient continuity, forest
  coverage, terrain plurality, tree density ordering, and water/urban
  exclusion.
- Add small in-memory tests for height, terrain, normal, and tree generation.
- Run each owning builder in check mode before apply, apply it explicitly, then
  apply a second time and prove identical hashes.
- Regenerate and check the minimap after the final height/terrain output.
- Run focused IVN, state, terrain-snow, strategic-region, generated-ownership,
  and minimap tests before the global validator.
- Run `python -B tools/validate_tc.py --limit 300`, unstaged `git diff --check`,
  and cached `git diff --check` if any paths are staged.
- Static validation does not establish correct Clausewitz rendering. Final
  visual acceptance requires a full HOI4 restart and a fresh campaign; no old
  save is acceptance evidence.

## Out of scope

- Province cuts outside the nine approved northern settlement provinces or any
  coastline edit.
- Mainland heightmap changes.
- New rivers, railways, supply hubs, buildings, or victory points; existing
  generated building positions may only be resynchronized to retained city IDs.
- Changes to BOR state 89.
- Permanent snow on the island.
- A new leader portrait or changes to the island-administration autonomy icon.
