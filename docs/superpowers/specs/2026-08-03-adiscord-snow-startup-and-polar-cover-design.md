# A-Discord Startup Snow and Polar Cover Design

## Problem

A fresh game started on 1 January 2160 shows no visible ground snow, including in the northern polar regions. The current weather data loads without snow-related errors and the generated polar profiles contain sub-zero temperatures, snow, and blizzard weights. The failure is therefore in initial accumulation and presentation rather than in missing strategic-region weather blocks.

The current global settings perform 180 initialization passes. With 227 strategic regions and seven region updates per pass, this gives each region only about 5.6 initial weather updates. The map also lowers `snow_visual_min` from the vanilla value of 128 to 64, making thin accumulated snow substantially less visible. Permanent plain snow currently covers only the extreme strip above `y = 120`, while the generated polar climate belt extends to `y = 300`.

## Desired Result

- A new game on 1 January visibly shows continuous snow across polar land.
- Subarctic and cool climates receive seasonal snow from the weather system rather than permanent terrain paint.
- Temperate and southern climates do not gain a permanent white layer.
- Existing rain, mud, temperature, sandstorm, strategic-region partitioning, and unrelated dirty work remain unchanged.
- Static verification must establish correct generation and wiring. Final visual acceptance requires a fresh new-game screenshot because static checks cannot prove Clausewitz rendering.

## Design

### Startup Weather History

Set `init_run_passes` to 720. At the current map size this yields approximately 22 region updates per strategic region and 25 province updates per province during new-game construction. This is enough history for repeated polar snow and blizzard events to accumulate visible ground snow without increasing the normal runtime update rate.

Restore `snow_visual_min` to the vanilla value of 128. This preserves the vanilla presentation floor for a thin non-zero snow layer instead of rendering it at the currently reduced strength of 64. Snow gain, melt rates, combat thresholds, `regions_per_update`, and `provinces_per_update` remain unchanged.

### Permanent Polar Terrain

Keep the existing generated permanent-snow mechanism in `tools/build_adiscord_terrain_snow.py`, but align the permanent plain-snow cap with the authoritative polar climate boundary at `y < 300`. Water pixels remain untouched. Mountain pixels in the polar belt continue to use the permanent-snow mountain terrain, while permanent snow outside the polar belt remains limited to the highest peaks.

The terrain pass remains idempotent: old generated snow pixels outside the target are restored to their base terrain, non-snow terrain edits are preserved, and a second generation pass produces no further bitmap change.

### Contracts and Ownership

- `common/weather.txt` owns global startup accumulation and visual snow strength.
- `tools/build_adiscord_terrain_snow.py` owns the permanent-snow subset of `map/terrain.bmp`.
- `tools/test_build_adiscord_terrain_snow.py` covers the polar boundary, water preservation, high peaks, and removal of stale generated snow.
- `tools/validate_adiscord_strategic_regions.py` locks the expected global weather settings while continuing to validate all climate profiles and generated region weather.
- `map/strategicregions/*.txt` and the strategic-region climate weights are not regenerated or retuned for this fix.

## Failure Handling

The terrain generator must fail without writing when the terrain bitmap is not paletted, bitmap dimensions differ, required `perm_snow = yes` terrain entries are missing, or generated coverage is outside the updated expected range. Bitmap writing continues through a complete temporary BMP followed by bounded replacement of `map/terrain.bmp`.

The implementation must preserve all unrelated working-tree changes. Only the approved weather settings, snow generator and test/validator contracts, and the generated snow pixels in `map/terrain.bmp` belong to this change.

## Verification

1. Run the snow unit tests.
2. Generate the permanent-snow bitmap and run its validator twice, confirming idempotency.
3. Run the strategic-region validator without regenerating strategic regions.
4. Run `python -B tools/validate_tc.py --limit 300` and `git diff --check` on the scoped files.
5. Start a fresh 1 January 2160 game and inspect fresh logs for weather, snow, terrain, and strategic-region errors.
6. Obtain a screenshot showing the polar belt. Acceptance requires continuous visible polar snow with a smooth southern boundary and no permanent snow spill into temperate lowlands.

