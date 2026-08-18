# Province-layer alignment audit — 2026-08-19

## Scope

- 72 raster targets: 53 new provinces (`16654–16706`) plus 19 existing provinces whose terrain declaration changed.
- `definition.csv` and `provinces.bmp` are source inputs and remain unchanged.
- `terrain.bmp`, `trees.bmp`, `heightmap.bmp`, and dependent `world_normal.bmp` are regenerated only inside the explicit alignment footprint.

## Verified change totals

- `terrain.bmp`: **4,728** province-alignment pixels.
- `trees.bmp`: **260** cells.
- `heightmap.bmp`: **1,132** pixels.
- `world_normal.bmp`: **478** cells.

## Existing definition terrain changes

`579, 5245, 5636, 5772, 6905, 6928, 7678, 8877, 9664, 11209, 11392, 11443, 12189, 12250, 12296, 12955, 16563, 16611, 16612`

Coastal-only change `10479` is intentionally not a raster-terrain target.

## Northern texture seam follow-up

- The hard permanent-snow cutoff at `y=300` was replaced with a deterministic multi-scale boundary driven by longitude and local relief.
- The follow-up changes **22,793** `terrain.bmp` pixels across rows `276–341`.
- The largest one-row change in the permanent-snow mask fell from **2,092 / 5,632 columns (37.1%)** to **203 / 5,632 columns (3.6%)**.
- `trees.bmp`, `heightmap.bmp`, and `world_normal.bmp` are unchanged by this follow-up.
- The permanent-snow builder now rejects any future map-wide horizontal cutoff and has focused regression coverage.

## Output SHA-256

- `map/terrain.bmp`: `ec246c7a18be8176f427f5c44562335cc0527d7e5f261d3478c7a530fa068256`
- `map/trees.bmp`: `6e02986c2b61ba7a481902e0b303f62e9dfa3154fa9054e787fcdda5a50550f2`
- `map/heightmap.bmp`: `425cfaf0b1a5952f3f6b206662efdb4ac9c22b547ec32d2aac444de5068b8d16`
- `map/world_normal.bmp`: `7305224af090baa61fe0e19a0daaf634622d390debcc7e1318b12fe88173c759`
- `map/provinces.bmp`: `397d5ceaad8a24e8919203e17dadb8e6c617eef1feafe4771408611e818eaa7d`
- `map/definition.csv`: `f25d80dc47ac18c9fcdd33ac1029b683218ee3daedfa5a6009fd7ec70090ee86`

The adjacent CSV lists all 72 province-alignment IDs and their declared terrain.
