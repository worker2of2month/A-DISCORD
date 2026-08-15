# IVN Northern Landscape Design

**Date:** 2026-08-16
**Status:** Approved direction; implementation plan pending user review
**Selected approach:** Deterministic, scoped landscape generation

## Goal

Give the IIA island a readable three-dimensional landform, expand northern
forest coverage, synchronize the low-resolution tree map with painted terrain,
and replace repeated `March` state names while preserving the existing province
geometry and unrelated map content.

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
- Do not change `map/provinces.bmp`, province adjacency, coastlines, state
  province membership, railways, supply nodes, or buildings.

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
- Existing compact urban footprints remain unchanged.
- Water terrain is never modified.

Coverage targets are measured after excluding water and urban footprints:

- island forest terrain: 25-30 percent;
- selected mainland northern IVN forest terrain: 20-25 percent overall;
- each affected non-marsh state retains meaningful non-forest open land;
- mountain and hill terrain remains visually continuous with the new island
  height field.

After painting, the existing IVN geography plurality logic updates column 6 of
`map/definition.csv` for affected provinces. Settlement provinces remain
declared `urban`; other declarations must match their dominant painted combat
terrain.

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

Extend `tools.builders.build_adiscord_ivn_geography` into the single scoped
landscape owner rather than adding an unrelated hand-painted pass. It owns:

- island pixels in `map/heightmap.bmp`;
- corresponding cells in `map/world_normal.bmp`;
- terrain pixels inside the approved northern IVN/IIA mask;
- tree cells inside the downsampled approved mask;
- terrain column 6 for affected rows of `map/definition.csv`;
- existing compact urban footprints for IVN/IIA settlements.

Ownership remains layered because terrain snow also writes `terrain.bmp` and
other builders write different `definition.csv` fields. Apply order is:

1. state history and naming builders;
2. IVN northern landscape;
3. permanent-snow terrain pass;
4. minimap generation.

The landscape height ceiling intentionally prevents new permanent-snow pixels,
but the snow pass is still rerun and checked because it consumes height and
terrain.

## Safety and verification contracts

- Preserve the existing SHA-256 contract for `map/provinces.bmp`.
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

- New province cuts or coastline edits.
- Mainland heightmap changes.
- New rivers, railways, supply hubs, buildings, or victory points.
- Changes to BOR state 89.
- Permanent snow on the island.
- A new leader portrait or changes to the island-administration autonomy icon.
