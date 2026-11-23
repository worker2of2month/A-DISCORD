# Montar Empire map geography

Status: implemented and applied on 2026-11-22 by
`tools/builders/build_adiscord_mon_geography.py`. The new provinces are
19285-19305, and 18 rail segments pass through remainders. The game starts with
the new map; the map itself has not yet been inspected in game.

This record is the contract for the implementers of the Montar Empire (MON) map
rework. Where it disagrees with the builders after implementation, the builders
win and this record is corrected.

## 1. The author's orders

- "Нужно проработать карту монтарской империи (города), реки, сёла, хайт мапа и тд".
- Cities are carved as compact new city provinces, as on the Itoran island,
  not marked on whole existing provinces.
- Density: one city per state plus villages, about 45 named places.
- Declared province terrain is recalculated from the new relief.
- A specification is written first; Opus agents implement it in packages and
  the lead reviews the combined diff.

## 2. Current state (measured 2026-11-22)

- MON owns 20 inland states: 425, 438, 439, 444, 445, 448, 453, 456, 459, 460,
  462, 464, 466, 467, 468, 469, 470, 471, 472, 473 (`history/states/<id>-outer-right.txt`).
- 488 land provinces, 67,714 px, sizes 53-287 px (median 135). No province is
  coastal. Two lakes lie inside the region: 16231 (borders 439/445/453) and
  16285 (borders 439/453). Lake 16263 lies south of it.
- Bounding box x 3025-3452, image rows 824-1164 on the 5632x2048 map. All
  coordinates in this record are `(x, row)` with row 0 at the top of the image,
  as in the arrays PIL returns. unitstacks and buildings use `z = 2047 - row`.
- Heightmap: blurred noise, heights 97-158, median 120. Median height by
  declared terrain is plains 120, hills 125, forest 115, marsh 103,
  mountain 143. Relief does not express the terrain.
- Declared terrain: plains 201, hills 129, forest 124, mountain 21, marsh 13,
  scattered as a patchwork. Terrain palettes 0, 1, 2, 4, 5, 9, 11, 17, 20.
- `cities.bmp` is index 1 on every MON pixel and terrain palette 13 is absent,
  so MON has no city meshes and no night lights.
- 727 river pixels, 118 of them off province borders. Existing components: the
  northern river along 425/439 into lake 16231; the eastern river from the EXZ
  side through 460/459 into lake 16285 (tributary joins at (3372, 994) and
  (3386, 1001)); the western river along 464/470/471 south into lake 16263; a
  21 px stub into lake 16231; a source at (3332, 1161) on the southern tip.
- 4 victory points, sum 23: Монтера 2845 (10, state 469), Аркен 9899 (5, 459),
  Вальд 6028 (5, 460), Валтор 6748 (3, 471). Comparable powers hold 28-57 VPs
  with sums of 150-270 (NAM 57/232, SHL 46/267, EFL 34/211, KDR 28/158).
- 13 supply hubs: 212, 418, 2090, 2845, 3859, 6028, 6748, 7404, 8729, 8865,
  9322, 9899, 10095. 19 railway lines touch MON; 13 chains and the hubs are
  managed by `build_adiscord_vorkerland_theatre.py`.
- Lore anchors: the throne of fifteen crowns (subjugated dynasties kept their
  titles), the arsenal belt of southern cities joined by rail and military
  orders, the core of the empire against the conquered lands, the Arken dynasty.

Before pictures: `docs/development/previews/MON_map/before_relief_rivers.png`
and `before_terrain.png` (delete with the other previews when the work ends).

## 3. Ownership (who writes what)

| Output | Owner after this work | Notes |
|---|---|---|
| `map/provinces.bmp` MON pixels, new `definition.csv` rows | new `mon_geography` | City carving only; no other province changes |
| `definition.csv` field 6 (terrain) for MON provinces | `mon_geography` | Recomputed from relief |
| `heightmap.bmp`, `world_normal.bmp`, `terrain.bmp`, `trees.bmp`, `rivers.bmp` inside MON | `mon_geography` | Layered; pixels outside the MON scope stay byte-identical |
| `cities.bmp` index 15 inside MON | `mon_geography` | Layered, like `vorkerland_cities` |
| `unitstacks.txt` rows of carved, remainder and touched provinces | `mon_geography` | Native slot order, see 6.4 |
| MON state files: province lists, VPs, principal provinces | `northern_countries` | Extended, see 7.1 |
| VP names (Russian block, English pairs) | `northern_countries` | Names come from the geography data |
| MON rails and supply hubs | `vorkerland_theatre` | Unchanged unless a chain loses adjacency |
| Night-light alpha in the colormap | `coastal_geography` | Whole-map rebuild already lights palette 13 and index 15 minus EXZ |
| Per-province rows in `buildings.txt`, building heights | `map_buildings` | Extended, see 7.3 |
| Strategic-region membership, weather positions | `strategic_regions` | Re-applied |

The outer-state builder reads the frozen northern shell membership, climate
markers and Russian names from `tools/data/adiscord_northern_state_shells.json`.
MON's carved provinces join their specified shells once present on the map.
The relief follows the existing state names.

## 4. Builder architecture

New builder `tools/builders/build_adiscord_mon_geography.py` with one authored
data file `tools/data/adiscord_mon_geography.json` and one planned geometry
raster `tools/data/adiscord_mon_province_geometry.png`. No other new files
except its test module `tools/tests/test_build_adiscord_mon_geography.py`.

Reuse, do not copy. Import the generic primitives the way
`build_adiscord_coastal_geography.py` already does:

- from `build_adiscord_ivn_geography`: `packed_rgb`, `province_mask`,
  `province_borders`, `province_adjacency`, `neighbours_of`, `masked_slopes`,
  `stable_unit_hash`, `lattice_noise`, `polyline_distance`, `province_colour`,
  `carve_junction_city`, `_assign_to_neighbours`, `remove_four_province_corners`,
  `normal_from_height`, `level_towns_with_surroundings`, `province_terrain_type`,
  `paint_provinces`, `palette_types`, `_route_river`, `_prune_river_loops`,
  `_snap_river_point`, `river_width_palette`, `native_river_bmp`,
  `atomic_save_bmp`, the tree samplers if their scope can be passed in;
- from `build_adiscord_coastal_geography`: `carve_river_valleys`,
  `complete_native_anchors`, `moving_anchors_native`, `border_contacts`,
  `province_interior`, `native_slots`.

Do not refactor or reformat the IVN or coastal builders. If a primitive
depends on IVN module globals, write the MON orchestration in the MON builder
with explicit parameters instead of editing the IVN function. Prove after the
work that `build_adiscord_ivn_geography --check` and
`build_adiscord_coastal_geography --check` report exactly what they reported
before.

### 4.1 CLI

| Mode | Writes |
|---|---|
| default / `--check` | nothing; lists differences against the expected outputs |
| `--plan-provinces` | only the `planned` section of the JSON and the PNG |
| `--preview` | review images in `docs/development/previews/MON_map/` |
| `--apply` | the map outputs of section 3 |

`--plan-provinces` refuses to replan while a `planned` section exists; replanning
means restoring the pre-apply map first, as for IVN. `--apply` refuses if
`definition.csv` no longer ends at the id the plan started from (another builder
or Codex appended provinces): planned ids must be exactly `max + 1` onwards.

The builder must be deterministic and idempotent: a second `--apply` changes no
byte, and `--check` after `--apply` is clean.

### 4.2 Data file schema

`tools/data/adiscord_mon_geography.json`, UTF-8 without BOM, indent 2,
`ensure_ascii=False`, LF:

```json
{
  "schema": 1,
  "states": [425, 438, "..."],
  "heights": {"min": 97, "max": 190, "feather": 8},
  "uplands": [{"name": "North Kelvor", "centre": [3385, 870], "radii": [30, 20], "angle": 20, "peak": 168}],
  "ridges": [{"name": "West Kelvor", "points": [[3170, 1068], [3195, 1045]], "crest": 182, "sigma": 9}],
  "basins": [{"name": "Taller lakes", "centre": [3297, 955], "radii": [32, 26], "angle": 0, "floor": 101}],
  "levels": [{"name": "Southern plain", "states": [468, 469, 471, 472, 473], "range": [112, 122]}],
  "forest_zones": [{"name": "Rendar wood", "centre": [3250, 925], "radii": [38, 20], "angle": 0}],
  "marsh_zones": [{"name": "Taller fen", "centre": [3297, 958], "radii": [24, 20], "angle": 0}],
  "rivers": [{"name": "Fallen", "points": [[3228, 1035], [3322, 1066], [3310, 966]], "mouth": {"lake": 16285}}],
  "settlements": [
    {"state": 469, "kind": "city", "parent": 2845, "hint": [3322, 1066], "value": 20, "name": "Монтера"},
    {"state": 469, "kind": "district", "parent": 2845, "hint": [3328, 1072]},
    {"state": 425, "kind": "village", "province": null, "value": 1, "name": "Верхний Келвор"}
  ],
  "planned": {"origin": [0, 0], "first_id": 0, "provinces": [], "cities": {}, "villages": {}}
}
```

`levels` give each state's base height range. The builder smooths the base
field (Gaussian, about 12 px) so no step appears on a state border. A village
`province` stays `null` until `--plan-provinces` picks it and records it in
`planned.villages` (state -> list of provinces in table order) and in the entry
itself. `planned.provinces` lists `{province, rgb, state, parent, kind:
remainder|district}`; `planned.cities` maps each parent to itself, because the
city keeps the parent id.

`mouth` is `{"lake": <province>}` or `{"river": "existing"}` (confluence with the
nearest existing river pixel) or `{"river": "<name>"}` (confluence with another
MON river routed earlier in the list). `planned` is written only by
`--plan-provinces`; everything else is authored.

## 5. Geography design

### 5.1 Concept

The empire is a basin ringed by uplands. Three Kelvor uplands stand at the
edges: the North Kelvor upland (425) with hills around it (438), the West
Kelvor ridge (466, falling into 471 and the hills of 462/464/456/448), and the
Kelvor heights east of the capital (467, with the hills of 460). Inside lie the
lake district of Taller (453 and the south of 439), the central Kelvor plain
(459), and the southern plain of the arsenal belt (469, 468, 473, 472, and the
south of 471). Forests cover the northern belt (445, 439, 444), the lake shores
(453) and the Draven woods in the south-west (470).

This matches the frozen state names: every "нагорье" state is upland, every
"холмы" state is hills, every "леса" state is forest, every "равнина" state is
plain.

### 5.2 Relief

Starting values; the implementer may tune them inside the limits, then records
the final values in the JSON.

| Feature | Where | Heights |
|---|---|---|
| North Kelvor upland | dome centre (3385, 870), radii 30x20 | crest 160-172, apron to 438 at 135-145 |
| West Kelvor ridge | polyline (3170, 1068) - (3195, 1045) - (3215, 1025) - (3240, 1015), sigma 9 | crest 172-188 |
| Kelvor heights | dome centre (3350, 1045), radii 18x14 | crest 158-170 |
| Western hills | 448, 456, 462, 464 | rolling 126-146 |
| Hills of 438 and 460 | | 128-145 |
| Taller lake basin | around lakes 16231/16285 | 100-108, marsh rim |
| Central plain | 459 | 108-118, sloping north to the lakes |
| Southern plain | 469, 468, 473, 472, south of 471 | 112-122, very gentle |
| Draven woods | 470 | 110-124 |

Rules:

- Heights stay in [97, 190]. Nothing reaches 205, so `terrain_snow` adds no
  permanent snow to MON.
- Only MON pixels change. Each MON pixel blends its target with the height of
  the nearest non-MON pixel by weight `min(1, d / 8)`, as IVN does, so there is
  no cliff at the border and the neighbours keep their bytes.
- Gentle lattice noise breaks up the shapes; no blob may read as a round pimple.
- River valleys are carved after routing, from the routes held in memory and
  the uncarved relief, depth growing with river width (1.5-4 height units).
- City and village cores are levelled with their surroundings
  (`level_towns_with_surroundings`, sigma 4); a town never sits in a pit or on
  a spike.
- `world_normal.bmp` is regenerated only under the MON mask plus the one-cell
  feather of `normal_from_height`.

### 5.2a Rina canyon

Author's order: "На границе с Риной пусть будет каньон (углубление сильное)"
and "А внизу течёт большая река".

- A deep gorge follows the whole MON-RIN state border (251 MON border pixels,
  x 3092-3275, rows 1075-1123; MON states 470, 464, 471, 468, 473 against
  RIN 134, 147, 148, 149).
- Floor at 98-102, never below 97. Walls rise to the local relief within 4-6
  px, with a slight rim lift on the MON side. Gentle noise runs along the axis.
- The axis is the border itself. For this feature only, the heightmap scope
  extends at most 6 px into RIN to form the far wall; normals follow with
  their feather. RIN terrain, trees, provinces, definition rows and rivers are
  untouched. Along this border the blend to outside heights happens at the
  outer edge of the RIN band.
- The feature is authored in the JSON (`canyons`), not hardcoded.
- A big river, the Rina gorge, runs on the canyon floor along the border
  pixels on the MON side. It uses the widest palettes over most of its length
  and joins the existing western river.
- Cities and village cores stay at least 8 px from the border. The steep rim
  may turn MON rim provinces into hills or mountain.

### 5.3 Rivers

Rivers run on province borders, never through a province (user rule,
repeated on 2026-11-22: "реки не должны пересекать границы провинций"). Every
river pixel is a genuine border pixel whose two sides belong to different
provinces. No course hops through a province interior, and no province is
split by a river. They are
routed with the IVN A* on the pixels that are MON, on a province border, at
least 2 px from a foreign river and more than 3 px from water except at the
mouth. Waypoints below are hints; the router snaps them.

| River | Course | Mouth |
|---|---|---|
| Fallen (main) | West Kelvor ridge (3228, 1035) - east through 468 - past Montera (3322, 1066) - north through 459 past Arken (3332, 999) | lake 16285; if the eastern river blocks it, a confluence with that river |
| Feyva | 472 (3365, 1125) - north-west | joins the Fallen at Montera |
| Kelva | North Kelvor upland (3395, 880) - south through 444 (3415, 925) - past Vald (3391, 990) | joins the existing eastern river near (3386, 1001) |
| Tallerka | 448 hills (3176, 947) - east past Rendar (3245, 930) | lake 16231 |
| Ulva | 462 (3205, 1000) - south-west past Ulvar (3139, 1040) | joins the existing western river |
| Valta | ridge foot (3195, 1060) - south-west past Valtor (3182, 1077) | joins the existing western river |
| Solda (optional) | 473 (3295, 1150) - north past Solden (3308, 1099) | joins the Fallen |

Existing rivers:

- Components that leave MON keep their entry and exit pixels so the network of
  the neighbours stays connected.
- Inside MON they are re-routed onto province borders; the 118 off-border
  pixels disappear.
- The 21 px stub into lake 16231 may be absorbed by the Tallerka or dropped.

Palettes: 0 marks each source, widths follow `river_width_palette` and grow
downstream; the last pixel of a tributary is palette 1 (flow-in) and is
4-adjacent to the receiving river. The MON river validator extends
`river_issues`: one source per river, no branching except the flow-in pixel,
4-connected courses, every pixel on a province border, every mouth touching
its lake or receiving river, no river pixel inside a carved city.

### 5.4 Declared terrain

The per-pixel class comes from the relief, slope and zones:

- mountain: height >= 160 or slope >= 12;
- hills: height >= 132 or slope >= 6, and the shoulders of mountains;
- marsh: inside a marsh zone and below 106;
- forest: inside a forest zone;
- plains otherwise.

`province_terrain_type` chooses one terrain per province (marsh >= 35%,
mountain >= 40%, mountain + hills >= 40% gives hills, forest >= 40%, otherwise
the plurality). `paint_provinces` paints each rural province in one palette of
its type, as on IVN and the IIA island: the user wants province textures to
match their types. City cores are palette 13 and urban; the remainder keeps a
rural type computed without its urban pixels.

Acceptance bands over the 488 original provinces:

| Terrain | Band |
|---|---|
| plains | 185-215 |
| hills | 110-140 |
| forest | 110-140 |
| mountain | 16-30 |
| marsh | 8-16, only around the Taller lakes |

- Per state, the named type holds the majority of its rural provinces
  ("нагорье": hills + mountain >= 60% and at least 3 mountain).
- `contaminated` and `reactor_zone` never appear in MON: a state holding one
  must start as EXZ.

Trees: tree cells are regenerated in cells where MON holds the majority, dense
in forest provinces, sparse on hills and plains, none on mountain crests,
cleared around city and village cores and near water.

## 6. Cities and villages

### 6.1 Carving rule

- Every city is a compact province of 40-50 px, the capital two of them.
- The city keeps the parent's id; the leftover of the parent becomes a new
  "remainder" province with a new id. VP provinces 2845, 9899, 6028, 6748, all
  13 hub ids, the managed rail chains and the VP localisation keys therefore
  stay valid.
- The site is a junction within 14 px of the hint, reaching at least 3 land
  neighbours (`carve_junction_city`).
- Donors are only provinces of the same state; a donor loses at most 35% of its
  pixels. State pixel areas stay exactly the same, so the manpower split of
  `northern_countries` does not move.
- River pixels and their neighbours are locked; lakes are never donors.
- A city must keep contact with every rail-chain neighbour of its parent in
  `vorkerland_theatre`. The planner penalises sites that lose a contact. If no
  site keeps all contacts, the chain constant is edited to pass through the
  remainder, and the change is listed in the plan report.
- Remainders are at least 60 px. No province other than parents, donors and
  the new provinces changes a pixel.
- New ids start at 19285 (definition.csv ended at 19284 on 2026-11-22) and are
  contiguous. Recheck before planning: Codex works in this checkout.

### 6.2 Settlement table

City provinces are urban, `cities.bmp` index 15 (western houses), terrain
palette 13, and lit at night automatically. "Hub" means the parent is already
a supply hub.

| State | Parent | City (ru / en) | VP | Note |
|---|---|---|---|---|
| 469 | 2845 | Монтера / Montera | 20 | capital, hub; plus one urban district province (new id, no VP) |
| 459 | 9899 | Аркен / Arken | 10 | seat of the Arken dynasty, hub |
| 460 | 6028 | Вальд / Vald | 8 | steel, hub; VLD capital state |
| 468 | 4018 | Кронау / Kronau | 8 | arsenal belt, coal and steel, on the rail |
| 471 | 6748 | Валтор / Valtor | 6 | hub |
| 473 | 10815 | Зольден / Solden | 6 | arsenal belt, coal, oil, steel |
| 425 | 212 | Келвор / Kelvor | 5 | upland capital, hub |
| 448 | 8865 | Салвен / Salven | 5 | mines, hub |
| 456 | 3859 | Брейден / Breiden | 5 | mines, hub |
| 438 | 10541 | Гельмар / Gelmar | 4 | on the rail |
| 444 | 2090 | Ольдерн / Oldern | 4 | hub |
| 445 | 7404 | Рендар / Rendar | 4 | hub |
| 453 | 6835 | Таллер / Taller | 4 | lake shore town on lake 16285 |
| 464 | 10504 | Ульвар / Ulvar | 4 | on the rail |
| 467 | 418 | Эрдин / Erdin | 4 | hub |
| 470 | 8729 | Вирен / Viren | 4 | hub |
| 472 | 10095 | Фейвар / Feyvar | 4 | hub |
| 439 | 9322 | Лирен / Liren | 3 | hub |
| 462 | 11365 | Терлан / Terlan | 3 | on the rail |
| 466 | 8159 | Хальден / Halden | 3 | mountain town on the rail |

Villages are VP markers on existing rural provinces. Each gets a compact core
of 6-9 px (`cities.bmp` 15 + terrain 13) inside the rural province. The
province keeps its rural declared terrain, which is the NAM archipelago
precedent.

The planner picks the village province by rule:

- in the named state;
- at least 10 px from the city;
- preferring a river bank or a rail province;
- never a donor or a remainder.

The pick is recorded in the JSON for review.

| State | Village (ru / en) | VP |
|---|---|---|
| 425 | Верхний Келвор / Upper Kelvor | 1 |
| 438 | Гельмарский рудник / Gelmar Mine | 1 |
| 439 | Лиренский брод / Liren Ford | 1 |
| 444 | Хорн / Horn | 1 |
| 445 | Таннвальд / Tannwald | 1 |
| 448 | Брайтгоф / Breithof | 1 |
| 453 | Тихая Гать / Tikhaya Gat | 1 |
| 456 | Ормен / Ormen | 1 |
| 459 | Старый Аркен / Old Arken | 2 |
| 460 | Корвель / Korvel | 1 |
| 462 | Стейнау / Steinau | 1 |
| 464 | Ульварский брод / Ulvar Ford | 1 |
| 466 | Хальденский перевал / Halden Pass | 2 |
| 467 | Гердау / Gerdau | 1 |
| 468 | Кронауские шахты / Kronau Pits | 1 |
| 469 | Фаллен / Fallen | 2 |
| 469 | Коронный тракт / Crown Road | 1 |
| 470 | Дравенская сторожка / Draven Lodge | 1 |
| 471 | Ланнау / Lannau | 1 |
| 472 | Фейварская мельница / Feyvar Mill | 1 |
| 473 | Зольденские промыслы / Solden Oilfields | 1 |

Totals: 20 cities with VP sum 114, 21 villages with VP sum 24; MON goes from
4 VPs / 23 to 41 VPs / 138. All names were checked against the localisation on
2026-11-22. Avoided collisions: Дравен (the DRV country), Морвен (another
republic), Кальтен (VP 3783 in the Kalten corridor).

### 6.3 City look

- City pixels get `cities.bmp` 15 and terrain 13. Trees are cleared in the
  city and one cell around it.
- Montera, Arken, Vald and Kronau also get an urban fringe: up to 20% of the
  remainder, on the side facing the city, painted 15/13. The remainder's
  declared terrain ignores these pixels.
- Night lights come from the whole-map pass of `coastal_geography`, which
  lights palette 13 and index 15 except EXZ-owned states. No MON city may sit
  in an EXZ-owned state.
- Combat terrain is plain `urban`. A national `montar_city` terrain would need
  terrain, GFX, localisation, unit, trait, doctrine and test entries; it is out
  of scope unless the author asks for it.

### 6.4 Unit stacks

- Carved cities, remainders, the capital district and every donor get native
  anchor rows, built with the coastal builder's
  `complete_native_anchors`: slot 0 centred, moving slots in the bottom-up scan
  order of neighbours, slots 9, 10, 21 and 38.
- Every MON row's height (`y`) follows the new heightmap.
- Afterwards `ambient_audio` and `strategic_regions` are re-applied, because
  they read slot 0.

## 7. Changes in other builders

### 7.1 `build_adiscord_northern_countries.py` (package B)

- MON province lists: each MON state renders its shell list plus the planned
  ids of that state from the geography JSON, in the existing 16-per-row
  layout.
- MON VPs come from the settlement table, several per state (cities and
  villages), instead of the single centroid VP. Other countries keep the
  centroid rule.
- The MON principal province is the state's city. OOB locations in
  `history/units/MON.txt` follow it.
- Russian names go into the NC block of `victory_points_l_russian.yml`;
  English pairs go into the NC block of `adiscord_world_names_english.json`;
  then `--english-localisation`.
- `validate_adiscord_northern_countries.py` and its test stay byte-equality
  checks of the extended render.
- Check `validate_adiscord_new_states.py:810-832` ("every VP urban or
  approved"). If it covers MON states, approve MON villages explicitly by
  province; do not weaken the rule globally.

### 7.2 `build_adiscord_exclusion_zone_boundaries.py` (package B)

- Its snapshot `adiscord_exclusion_zone_boundary_source.json` lists the
  provinces of 460 and 472. The builder adds the planned children of those
  states from the geography JSON instead of hand-editing the snapshot.
- Keep the order outer -> northern -> EXZ -> northern.

### 7.3 `build_adiscord_map_buildings.py` and `build_adiscord_strategic_regions.py` (package C)

- map_buildings: building model heights follow the relief in the MON scope too.
  Today they follow it only in the coastal and IVN scopes, so buildings would
  float or sink on the new heightmap.
- map_buildings: per-province rows (`supply_node`, `bunker`,
  `special_project_facility_spawn`) of every MON parent move into their own
  province at slot 0. Remainders and the capital district gain their own rows.
  A hub city keeps its supply-node model inside the city.
- strategic_regions: new MON provinces join the region of their parent; weather
  weighting treats children as their parent, like the IIA sectors. Re-apply so
  `weatherpositions.txt` and latitudes follow the new slot 0.

### 7.4 `build_adiscord_vorkerland_theatre.py`

- No change is expected, since cities keep their parent ids. The plan report
  from 6.1 lists any chain that must be rerouted through a remainder; only then
  edit `MON_SUPPLY_RAILS`.
- Never use `city_railways.passages` for MON lines: the coastal and theatre
  builders would undo each other.

### 7.5 Registration

- Add family `mon_geography` to `tools/data/generated_output_owners.json`:
  layered outputs of section 3, `source_inputs` with the JSON, the PNG, the
  builder and the map files it reads.
- In `apply_sequence` it runs after `outer_states` and before the first
  `northern_countries`: the northern builders need slot-0 rows and the planned
  ids, and `coastal_geography` must later rebuild the night lights over the new
  terrain.
- Update `test_generated_output_ownership.py` if it pins the order.

## 8. Apply chain (lead only)

Snapshot `map/`, the MON state files, `history/units/MON.txt`, the VP
localisation and the English names JSON first. Then:

1. `build_adiscord_mon_geography --plan-provinces`, then `--preview`.
   **Author checkpoint**: the user reviews cities, villages, rivers and relief
   in the previews before anything is applied.
2. `build_adiscord_mon_geography --apply`, then `--apply` again: no byte may
   change.
3. `build_adiscord_northern_countries --states-only --apply` and `--oobs-only --apply`.
4. `build_adiscord_exclusion_zone_boundaries --apply`.
5. `build_adiscord_northern_countries --states-only --apply` and
   `--english-localisation --apply`.
6. `build_adiscord_coastal_geography --apply`, which rebuilds the night lights.
7. `build_adiscord_map_buildings --apply`.
8. `build_adiscord_vorkerland_theatre --check`, and `--apply` only if a chain
   changed.
9. `build_adiscord_strategic_regions --apply`.
10. `build_adiscord_trade_regions --apply`, which covers the new rows' continent.
11. `build_adiscord_terrain_snow --check` and `build_adiscord_vorkerland_cities --check`.
12. `build_adiscord_ambient_audio --apply`.
13. `build_adiscord_minimap --apply`.
14. `build_adiscord_nam_oilfields --apply` (Blender 4.5, about 20 s): its
    report pins whole-map hashes.
15. `--check` of every remaining family whose `source_inputs` include
    provinces, definition, heightmap, rivers, terrain or state files: the map
    renderers `val_operations_map`, `stp_regions_map`,
    `vorkerland_capital_map`, `nam_basin_map`, `shl_furnace_map`,
    `south_influence_map`, `nam_piracy_map`, `west_influence_map`, plus
    `startup_ui_assets`, `intelligence_ui_assets`, `map_facility_models` and
    `factory_models`. Compare with the baseline: `val_operations_map` and the
    AZH palace, Isaiah tower and NAM export office model reports were already
    stale before this work.
16. Refresh `HEIGHT_OUTSIDE_ISLAND_SHA256` and `NORMAL_OUTSIDE_FEATHER_SHA256`
    in `test_build_adiscord_ivn_geography.py`. First prove that every changed
    heightmap and normal byte lies inside the MON scope plus the normal
    feather.
17. Full suite, `python -B tools/validate_tc.py --limit 300`, `git diff --check`.

Do not run the full `new_states --apply` or `outer_states --apply`.

## 9. Tests (`test_build_adiscord_mon_geography.py`)

- `--check` is clean and a second apply is idempotent.
- Scope: every changed pixel of heightmap, terrain, trees, rivers and cities
  lies inside MON; normals inside MON plus the feather; provinces.bmp changes
  only in parents, donors and new provinces.
- State pixel areas are unchanged; every planned province belongs to its
  parent's state.
- Cities: 40-50 px, at least 3 land neighbours, compact, no river pixel
  inside, contact kept with the rail-chain neighbours of the parent.
  Remainders: at least 60 px.
- Rivers: the validator of 5.3; mouths as authored.
- Terrain: the bands of 5.4; the named type of each state; no
  contaminated or reactor_zone; heights within [97, 190].
- Settlements: VP values and names exactly as in 6.2; villages keep rural
  declared terrain; every city is urban with cities.bmp 15 and palette 13.
- Lights: no lit pixel inside an EXZ-owned state, which the existing coastal
  test covers.

## 10. Gameplay consequences

Flag these to the author:

- Capitulation pacing changes. Montera now holds 20 of 138 VPs (14%) instead of
  10 of 23 (43%), so taking the capital alone no longer brings MON close to
  surrender. The Kefreyt eastern war and the Khan war against MON get longer.
  Check the eastern-war hold count in `ADISCORD_VAL_effects.txt:3536-3543`,
  which uses states and is not broken, and the AI war plans in a text save
  after the change.
- 21 city provinces gain urban defence. Recalculated terrain changes attack
  and attrition across MON.
- Supply hubs, rails, factories, resources and manpower stay as they are.

## 11. Implementation packages

The files of each package are disjoint. Agents never run `--apply`, commit or
reset; they run their own focused tests and report the checks they ran.

| Package | Files | Depends on |
|---|---|---|
| A - geography builder | `build_adiscord_mon_geography.py`, `adiscord_mon_geography.json`, `adiscord_mon_province_geometry.png` (via `--plan-provinces`), `test_build_adiscord_mon_geography.py`, the owners JSON entry | - |
| B - states, VPs, names | `build_adiscord_northern_countries.py` and its validator/test, `build_adiscord_exclusion_zone_boundaries.py` and its test, the NC block of `adiscord_world_names_english.json` | the JSON schema of 4.2; the planned ids after A's plan |
| C - buildings and regions | `build_adiscord_map_buildings.py`, `build_adiscord_strategic_regions.py` and their tests | the JSON schema |

The lead runs the plan and the author checkpoint, then the apply chain of
section 8, refreshes the pins, runs the full gate and reviews the combined diff
with the `rules-reviewer` agent.

## 12. Runtime verification (the author, after a full restart)

- `error.log`: no map, province, river or unitstack errors.
- The map in MON: city meshes and night lights on all 20 cities and village
  cores, no floating or sunken buildings, rivers on borders with no gaps at
  confluences, relief readable on the terrain and height map modes, terrain
  textures matching province types.
- VP names in both languages, MON divisions standing in their cities, supply
  hubs drawn inside the hub cities.
- A short Kefreyt-Montera war in a test campaign for the capitulation pace.
