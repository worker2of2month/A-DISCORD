# IVN Island Administration and Geography Design

## Goal

Turn IVN into a geographically readable country by creating a permanent island subject with a unique autonomy type, splitting its two oversized starting states without changing province geometry, adding settlement victory points, and making province terrain definitions agree with the painted terrain.

This is fresh-campaign work. No save migration, startup repair, or compatibility path for existing campaigns will be added.

## Safety and ownership

- `map/provinces.bmp` and province colours remain byte-for-byte unchanged.
- Existing province adjacency, coastlines, railway paths, and strategic-region membership remain unchanged.
- Generated state history is changed through `tools/builders/build_adiscord_new_states.py`, then regenerated with `--apply` and proved idempotent.
- The new states and layered terrain/definition outputs are registered in `tools/data/generated_output_owners.json`.
- Russian localisation remains UTF-8 with BOM.
- Existing dirty technology, AI, Vorkerland, UI, and unit work is out of scope.

## Island country

Create tag `IIA`, localised as `Иторское островное управление`, with adjective `островн.` and an identical temporary flag set copied from IVN. Its country colour may mirror IVN, but the required map-colour contract is supplied by the autonomy type.

IIA starts as IVN's subject in a fresh campaign and owns and cores states `128`, `693`, and `694`. Its capital is state `693`. It uses humanism, two research slots, western European graphical cultures, and a placeholder character:

- technical character ID: `IIA_Provisional_Commandant`;
- Russian display name: `Временный комендант`;
- description: a young, ambitious officer entrusted with the island administration;
- portrait: existing `GFX_Portrait_Europe_Generic_land_2`;
- no generated leader portrait in this scope.

IIA receives one weak garrison division in province `579`. IVN keeps its existing sixteen-division starting contract: the IVN division currently located in `579` moves to IVN-owned province `595`, and the new IIA garrison is additional rather than deducted from IVN's field army.

IIA has no focus tree, event chain, independent diplomacy, or autonomy progression in this scope.

## Unique autonomy

Create `common/autonomous_states/ADISCORD_island_administration.txt` with exact ID `autonomy_island_administration` and Russian localisation `Островное управление`.

The level is permanently locked to itself:

- `default = no`;
- `is_puppet = yes`;
- `min_freedom_level = 0.00`;
- `use_overlord_color = yes`;
- cannot declare war, decline an overlord call, or become spymaster;
- may deploy units to the overlord and allow overlord construction;
- 65% subject manpower share, 100% extra trade to the overlord, 50% reduced overlord trade cost, 25% civilian-industry transfer, and 35% military-industry transfer;
- both autonomy AI weights are zero and both level-change triggers are permanently false.

IVN creates the starting relationship in `history/countries/IVN - IvanLand.txt` using `set_autonomy` with `autonomy_state = autonomy_island_administration` and `freedom_level = 0.00`.

## Autonomy icon

Generate only the autonomy icon artwork. The leader portrait and country flag are not generated.

The high-resolution source depicts a compact silver coastal command tower rising above two dark teal waves, backed by the golden sun disc and crossed dark blades from IVN's flag. It uses a dark green, weathered gold, gunmetal, and silver palette, a transparent background, no text, no characters, and a strong centred silhouette readable at 35 pixels.

A deterministic icon builder crops, downsizes, sharpens, and writes `gfx/interface/autonomy/autonomy_island_administration_icon.png` as 35x36 RGBA. `interface/ADISCORD_autonomy_icons.gfx` exposes it as `GFX_autonomy_island_administration_icon`. Transparent corner pixels and a visible non-transparent centre are required.

## Island state split

State `128` is split into three states without modifying any province boundary:

| State | Russian name | Provinces | Population | Category | Infrastructure | Civilian | Military | Air | Supplies | VP |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---|
| 128 | Иванские нагорья | 579, 7125, 8423, 9072 | 90,000 | rural | 2 | 0 | 0 | 0 | 1.0 | 579 `Нордхольм`, 1 |
| 693 | Рейдаль | 1191, 1744, 2219, 2991, 4334, 6905, 6928, 7678, 8048, 10730 | 190,000 | town | 3 | 1 | 0 | 0 | 1.5 | 6905 `Рейдаль`, 5 |
| 694 | Кайрский берег | 2553, 5448, 11841, 12189 | 80,000 | rural | 2 | 0 | 0 | 0 | 1.5 | 11841 `Кайрхольм`, 3 |

State `694` receives a level-2 naval base in province `11841`. The split preserves the original total of 360,000 population and one civilian factory while raising total local supply from 2.0 to 4.0 so the three-state island and its port are functional.

## Old March split

State `25`, localised as `Старая марка`, is reduced to a capital/coastal state and four new states are created. Every listed group is connected through existing land adjacencies except the pre-existing detached single-province islands `4277`, `5729`, `6580`, `8885`, `9037`, `9778`, `10675`, and `11000`, which remain attached to their nearest coastal administration.

### State 695: Верхняя Марка

Provinces: `157, 217, 482, 1105, 1763, 2736, 3038, 3181, 3304, 3541, 3579, 4572, 5016, 6146, 6345, 8068, 8505, 8615, 9608, 10158, 10668, 10769, 10810, 10879, 11487, 12017, 12054`.

Profile: 750,000 population, town, infrastructure 3, one civilian factory, one military factory, local supplies 1.5, steel 4, and VP `1763` `Верхнемарск` worth 3.

### State 696: Восточная Марка

Provinces: `722, 1304, 2025, 2157, 2211, 3847, 4037, 5521, 5540, 5573, 5729, 6622, 7911, 8515, 9133, 9344, 11115, 11132, 12317, 12880, 12914`.

Profile: 700,000 population, town, infrastructure 3, one civilian factory, one military factory, local supplies 1.5, steel 4, and VP `5573` `Лонгар` worth 3.

### State 697: Западная Марка

Provinces: `401, 1385, 1429, 3273, 4277, 4646, 5055, 5273, 6350, 6827, 6979, 6991, 7263, 8885, 9037, 9132, 9150, 9160, 9418, 9778, 11000, 12383`.

Profile: 600,000 population, town, infrastructure 3, one civilian factory, no military factories, local supplies 1.5, steel 4, and VP `9160` `Ринваль` worth 3.

### State 25: Старая марка

Provinces: `694, 932, 1634, 1861, 1862, 3017, 3302, 3503, 3648, 3714, 4503, 4534, 4909, 5611, 6580, 7508, 7654, 8717, 9066, 9236, 9598, 9614, 10539, 10675, 10835, 10885, 11124, 11612, 11653, 12313, 12410, 12790, 12899, 16568`.

Profile: 1,300,000 population, large city, infrastructure 5, two civilian factories, two military factories, air base 2, local supplies 2.0, steel 8, the existing level-1 naval base in `16568`, and the existing VP `16568` `Старая марка` worth 10. It remains IVN's capital.

### State 698: Южная Марка

Provinces: `1768, 1890, 2380, 3828, 3919, 5798, 6971, 8328, 8371, 9611, 10313, 10357, 10403, 10548, 12076, 12122`.

Profile: 650,000 population, town, infrastructure 3, one civilian factory, no military factories, air base 1, local supplies 1.5, steel 4, and VP `12076` `Салемар` worth 3.

Across states `25` and `695-698`, the split preserves exactly 4,000,000 population, six civilian factories, four military factories, three air-base levels, 8.0 local supplies, and 24 steel. Existing railways and the supply node/rail spine through `16568` remain unchanged.

## Victory points for the rest of IVN

Add an ordinary named settlement to every other populated IVN state. Existing state names supply the settlement name unless otherwise stated:

| State | Province | Value | Name |
|---:|---:|---:|---|
| 92 | 3462 | 1 | Серенга |
| 95 | 3318 | 3 | Ведрина |
| 96 | 888 | 3 | Талара |
| 97 | 838 | 3 | Кантория |
| 98 | 2448 | 5 | Моресса |
| 99 | 882 | 7 | Лакора |
| 100 | 702 | 5 | Ильван |
| 101 | 9327 | 3 | Ольсия |
| 127 | 595 | 3 | Северная Марка |
| 129 | 1971 | 1 | Старый Кордон |
| 130 | 3447 | 2 | Дальняя Застава |
| 131 | 2262 | 2 | Пыльный Тракт |
| 132 | 423 | 2 | Западная Серенга |
| 164 | 4217 | 1 | Восточная Итора |

The new centres reuse existing valid deployment provinces and do not move supply hubs or railways.

## Terrain contract

Add a scoped IVN geography builder and validator. For every province in IVN or IIA starting states, the builder counts non-water graphical terrain pixels in `map/terrain.bmp`, maps palette indices to gameplay terrain categories using `common/terrain/00_terrain.txt`, and writes the plurality category to the terrain field in `map/definition.csv`.

Plurality ties use this fixed order: `urban`, `mountain`, `hills`, `marsh`, `forest`, `plains`, `jungle`, `desert`. Water indices `14` and `15` never participate in a land province classification.

Settlement provinces are explicit exceptions to pure plurality. The builder paints a deterministic compact urban footprint centred on land pixels near the province centroid, then assigns `urban` in `definition.csv`. Each settlement must contain at least 24 graphical urban pixels, remain entirely inside its province colour mask, and retain at least 35% of its previous non-urban biome so city textures do not erase the surrounding landscape.

The island's existing hills, plains, and mountain artwork is preserved rather than flattened. The current audit mismatch in which 16 of 18 state-128 provinces have a different definition from their painted plurality is reduced to zero, excluding the explicit visible-urban settlement rule. The same contract applies to the rest of IVN.

After the scoped urban and definition pass, `build_adiscord_terrain_snow` runs again so permanent snow remains deterministic. A second apply of both builders must leave `map/terrain.bmp` and `map/definition.csv` hashes unchanged.

## Generated files and localisation

The state builder owns the exact new state paths `history/states/693-693.txt` through `history/states/698-698.txt`, plus its existing layered ownership of states 25 and 128. It also owns the IVN state profiles and VP manifest entries. `build_adiscord_map_buildings` synchronises state IDs after regeneration.

Add the IIA tag, country/common history, character, OOB, flags, autonomy definition, autonomy sprite, Russian country/character/autonomy/state/VP localisation, icon source, deterministic icon builder, and focused validators/tests. Technical IDs and filenames remain ASCII; visible Russian text remains Cyrillic.

## Acceptance

Static acceptance requires:

- exact, disjoint province unions for the state-25 and state-128 splits;
- no province missing from or added to either original union;
- state IDs 693-698 unique and present in localisation;
- `map/provinces.bmp` SHA-256 unchanged;
- IIA owns and cores 128, 693, 694 and is IVN's locked `autonomy_island_administration` subject at game start;
- IIA and IVN share IVN's map colour through `use_overlord_color = yes`;
- IVN retains sixteen divisions and IIA has exactly one weak island garrison;
- all listed VP provinces, values, and Russian names are exact;
- non-settlement terrain definitions match painted plurality and settlement provinces have visible urban footprints;
- the autonomy icon is 35x36 RGBA, resolves through its sprite, and remains legible at native size;
- all changed Russian localisation files retain UTF-8 BOM;
- focused builders pass `--check`, both terrain builders are idempotent, and the relevant state, autonomy, GFX, terrain, map-building, and Vorkerland validators pass;
- `python -B tools/validate_tc.py --limit 300`, unstaged `git diff --check`, and cached `git diff --cached --check` pass.

Runtime acceptance requires a full HOI4 restart and fresh campaign. Verify the IIA subject relationship and matching map colour, autonomy icon, placeholder leader, three island states, five Old March states, ports, VPs, state names, terrain visuals/tooltips, unit deployment, railways, supply, and IVN's existing northern-intervention availability. Static checks alone do not prove these Clausewitz behaviours.
