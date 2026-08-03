# A-Discord Startup Snow and Polar Cover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make polar ground snow visibly present in every fresh 1 January 2160 game while keeping snow outside the polar belt seasonal.

**Architecture:** Global weather settings provide enough pre-start update history and restore the vanilla thin-snow visibility floor. A focused Pillow generator owns permanent snow pixels in `map/terrain.bmp`, aligns them with the `y < 300` polar climate belt, and rejects invalid output before writing. Existing strategic-region climate weights and partitions remain untouched.

**Tech Stack:** HOI4 Clausewitz weather configuration, Python 3.11, `unittest`, Pillow, paletted BMP map assets.

## Global Constraints

- Set `init_run_passes = 720` and `snow_visual_min = 128` exactly.
- Set the permanent polar plain boundary to `y < 300` exactly.
- Preserve `snow_gain_on_snowing = 1.0`, `snow_gain_on_blizzard = 5.0`, runtime update rates, melt rates, combat thresholds, and all strategic-region climate weights.
- Do not run `tools/build_adiscord_strategic_regions.py` or rewrite `map/strategicregions/*.txt`.
- Preserve water pixels, non-snow terrain pixels, unrelated dirty files, and unrelated hunks in overlapping dirty files.
- For pre-existing dirty files, stage only the target hunks with `git add -p`, inspect `git diff --cached`, and never amend or reset a concurrent commit.
- Static checks do not prove Clausewitz rendering; final acceptance requires a fresh-game screenshot.

## File Map

- Modify `common/weather.txt`: global startup history and visual snow floor only.
- Modify `tools/validate_adiscord_strategic_regions.py`: lock the two approved global values.
- Modify `tools/build_adiscord_terrain_snow.py`: polar boundary, coverage contract, and write-before-validation guard.
- Modify `tools/test_build_adiscord_terrain_snow.py`: exact boundary and safe-write regression tests.
- Regenerate `map/terrain.bmp`: permanent polar and high-peak snow pixels only.
- Do not modify generated strategic-region files.

---

### Task 1: Restore visible startup snow accumulation

**Files:**
- Modify: `tools/validate_adiscord_strategic_regions.py:34,211-219`
- Modify: `common/weather.txt:90-110,134-143`

**Interfaces:**
- Consumes: `validate_global_weather_settings(errors: list[str]) -> None` and the existing scalar-key parser.
- Produces: an exact contract for `snow_visual_min = 128` and `init_run_passes = 720`.

- [ ] **Step 1: Change the validator first**

Change only these expected values:

```python
EXPECTED_INIT_RUN_PASSES = 720

# Inside validate_global_weather_settings:
expected_values = {
    "temperature_neighbor_smoothing": 0.5,
    "snow_gain_on_snowing": 1.0,
    "snow_gain_on_blizzard": 5.0,
    "snow_visual_min": 128.0,
    "init_run_passes": float(EXPECTED_INIT_RUN_PASSES),
}
```

- [ ] **Step 2: Run the validator and confirm the intended failure**

Run:

```powershell
python -B tools/validate_adiscord_strategic_regions.py
```

Expected: non-zero exit with errors reporting the current `snow_visual_min = 64` and `init_run_passes = 180`; no missing-region or climate-profile failures.

- [ ] **Step 3: Apply the minimal global weather change**

Change only these two assignments in `common/weather.txt`:

```txt
snow_visual_min = 128
init_run_passes = 720
```

Keep snow gain, snow melt, ground-snow thresholds, `provinces_per_update`, and `regions_per_update` unchanged.

- [ ] **Step 4: Run the validator and confirm it passes**

Run:

```powershell
python -B tools/validate_adiscord_strategic_regions.py
```

Expected: `Strategic-region validation passed: 227 regions, 689 states, 16653 provinces.`

- [ ] **Step 5: Commit only the approved hunks**

Run `git add -p -- common/weather.txt tools/validate_adiscord_strategic_regions.py`. Stage only the two global values and their validator expectations. Inspect `git diff --cached --check` and `git diff --cached` before committing:

```powershell
git commit -m "fix: accumulate visible startup snow"
```

### Task 2: Align permanent terrain snow with the polar climate belt

**Files:**
- Modify: `tools/test_build_adiscord_terrain_snow.py:6-35`
- Modify: `tools/build_adiscord_terrain_snow.py:23-125`

**Interfaces:**
- Consumes: `classify_terrain(terrain: int, y: int, height: int) -> int` and paletted terrain/heightmap BMPs.
- Produces: `definition_issues(definition: str) -> list[str]`, `coverage_issues(pixels: list[int]) -> list[str]`, and an `apply() -> None` that validates before opening the destination for writing.

- [ ] **Step 1: Add failing boundary and safe-write tests**

Import the module and test dependencies:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

import build_adiscord_terrain_snow as snow
```

Add these tests to `TerrainSnowTests`:

```python
def test_polar_cap_matches_generated_climate_boundary(self) -> None:
    self.assertEqual(snow.POLAR_CAP_Y, 300)
    self.assertEqual(snow.classify_terrain(4, 299, 100), snow.SNOW_PLAIN)
    self.assertEqual(snow.classify_terrain(4, 300, 100), 4)

def test_coverage_contract_accepts_generated_target(self) -> None:
    pixels = [snow.SNOW_MOUNTAIN] * 10_205 + [snow.SNOW_PLAIN] * 339_720
    self.assertEqual(snow.coverage_issues(pixels), [])

def test_apply_stops_before_writing_rejected_coverage(self) -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        terrain_path = root / "terrain.bmp"
        heightmap_path = root / "heightmap.bmp"
        definition_path = root / "00_terrain.txt"
        Image.new("P", (2, 2), color=4).save(terrain_path, format="BMP")
        Image.new("L", (2, 2), color=100).save(heightmap_path, format="BMP")
        definition_path.write_text(
            "snow_16 = { type = mountain color = { 16 } texture = 11 perm_snow = yes }\n"
            "plains_17 = { type = plains color = { 19 } texture = 0 perm_snow = yes }\n",
            encoding="utf-8",
        )
        original = terrain_path.read_bytes()
        with (
            patch.object(snow, "TERRAIN_PATH", terrain_path),
            patch.object(snow, "HEIGHTMAP_PATH", heightmap_path),
            patch.object(snow, "TERRAIN_DEFINITION_PATH", definition_path),
            patch.object(snow, "coverage_issues", return_value=["coverage rejected"]),
        ):
            with self.assertRaisesRegex(RuntimeError, "coverage rejected"):
                snow.apply()
        self.assertEqual(terrain_path.read_bytes(), original)
```

- [ ] **Step 2: Run the tests and confirm they fail for the missing contract**

Run:

```powershell
python -B tools/test_build_adiscord_terrain_snow.py
```

Expected: failures because `POLAR_CAP_Y` is 120 and `coverage_issues` does not exist. The four pre-existing classification tests must remain green.

- [ ] **Step 3: Implement the exact polar and coverage constants**

Replace and add these module constants:

```python
POLAR_CAP_Y = 300
POLAR_MOUNTAIN_Y = 300
PERMANENT_PEAK_HEIGHT = 205

MIN_PERMANENT_SNOW_PIXELS = 320_000
MAX_PERMANENT_SNOW_PIXELS = 380_000
MIN_PERMANENT_MOUNTAIN_PIXELS = 5_000
```

Extract the terrain-definition validation into a pure helper:

```python
def definition_issues(definition: str) -> list[str]:
    issues: list[str] = []
    for snow_index in (SNOW_MOUNTAIN, SNOW_PLAIN):
        matching_entries = [
            block
            for block in re.findall(
                r"^\s*\w+\s*=\s*\{([^\n}]*(?:\}[^\n}]*)*)\}\s*$",
                definition,
                re.M,
            )
            if re.search(rf"\bcolor\s*=\s*\{{\s*{snow_index}\s*\}}", block)
        ]
        if len(matching_entries) != 1 or not re.search(
            r"\bperm_snow\s*=\s*yes\b", matching_entries[0]
        ):
            issues.append(
                f"common/terrain/00_terrain.txt: palette index {snow_index} "
                "must have exactly one perm_snow=yes terrain entry"
            )
    return issues
```

Add the pure coverage helper:

```python
def coverage_issues(pixels: list[int]) -> list[str]:
    issues: list[str] = []
    mountain_snow, plain_snow = snow_counts(pixels)
    total_snow = mountain_snow + plain_snow
    if not MIN_PERMANENT_SNOW_PIXELS <= total_snow <= MAX_PERMANENT_SNOW_PIXELS:
        issues.append(
            "map/terrain.bmp: permanent-snow coverage "
            f"{total_snow} is outside "
            f"{MIN_PERMANENT_SNOW_PIXELS}..{MAX_PERMANENT_SNOW_PIXELS}"
        )
    if mountain_snow < MIN_PERMANENT_MOUNTAIN_PIXELS:
        issues.append(
            f"map/terrain.bmp: only {mountain_snow} permanent mountain pixels"
        )
    return issues
```

- [ ] **Step 4: Make validation and apply share the preflight helpers**

In `validate()`, replace the duplicated definition and coverage checks with `definition_issues(definition)` and `coverage_issues(current)`.

At the start of `apply()`, validate the definition and generated pixels before creating or opening any destination file for writing:

```python
def apply() -> None:
    if not TERRAIN_DEFINITION_PATH.exists():
        raise RuntimeError("common/terrain/00_terrain.txt is missing")
    problems = definition_issues(
        TERRAIN_DEFINITION_PATH.read_text(encoding="utf-8-sig", errors="strict")
    )
    if problems:
        raise RuntimeError("\n".join(problems))

    with Image.open(TERRAIN_PATH) as source, Image.open(HEIGHTMAP_PATH) as heightmap:
        terrain = source.copy()
        pixels = generated_pixels(source, heightmap)
    problems = coverage_issues(pixels)
    if problems:
        raise RuntimeError("\n".join(problems))

    terrain.putdata(pixels)
    temporary = TERRAIN_PATH.with_suffix(".bmp.tmp")
    terrain.save(temporary, format="BMP")
    with temporary.open("rb") as generated, TERRAIN_PATH.open("r+b") as destination:
        shutil.copyfileobj(generated, destination)
        destination.truncate()
    temporary.unlink()
    mountain_snow, plain_snow = snow_counts(pixels)
    print(
        "Generated permanent snow: "
        f"{mountain_snow} mountain + {plain_snow} polar plain pixels."
    )
```

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
python -B tools/test_build_adiscord_terrain_snow.py
```

Expected: seven tests pass, including the exact `y = 299`/`y = 300` boundary and the no-write rejection test.

- [ ] **Step 6: Commit the generator contract**

These two currently untracked files are entirely in scope. Stage them, verify the staged diff, and commit:

```powershell
git add -- tools/build_adiscord_terrain_snow.py tools/test_build_adiscord_terrain_snow.py
git diff --cached --check
git diff --cached -- tools/build_adiscord_terrain_snow.py tools/test_build_adiscord_terrain_snow.py
git commit -m "fix: generate permanent polar snow"
```

### Task 3: Regenerate the snow bitmap idempotently

**Files:**
- Modify: `map/terrain.bmp`

**Interfaces:**
- Consumes: the validated `apply() -> None` from Task 2.
- Produces: a paletted `map/terrain.bmp` whose permanent-snow pixels match the approved boundary.

- [ ] **Step 1: Generate and validate the bitmap**

Run:

```powershell
python -B tools/build_adiscord_terrain_snow.py --apply
python -B tools/build_adiscord_terrain_snow.py
```

Expected generation count for the current bitmap: `10205 mountain + 339720 polar plain pixels`; validation prints `Permanent-snow terrain validation passed.`

- [ ] **Step 2: Prove idempotency**

Run:

```powershell
$firstSnowHash = (Get-FileHash -Algorithm SHA256 -LiteralPath 'map\terrain.bmp').Hash
python -B tools/build_adiscord_terrain_snow.py --apply
$secondSnowHash = (Get-FileHash -Algorithm SHA256 -LiteralPath 'map\terrain.bmp').Hash
if ($firstSnowHash -ne $secondSnowHash) { throw 'terrain snow generation is not idempotent' }
```

Expected: the two hashes are equal.

- [ ] **Step 3: Commit only the generated bitmap**

Inspect the staged name and size before committing:

```powershell
git add -- map/terrain.bmp
git diff --cached --stat -- map/terrain.bmp
git commit -m "fix: add polar snow terrain cover"
```

### Task 4: Run the complete static and runtime verification gates

**Files:**
- Verify only; do not regenerate strategic regions.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: static evidence plus a clearly stated runtime/visual verification boundary.

- [ ] **Step 1: Run focused snow and strategic-region checks**

Run:

```powershell
python -B tools/test_build_adiscord_terrain_snow.py
python -B tools/build_adiscord_terrain_snow.py
python -B tools/validate_adiscord_strategic_regions.py
```

Expected: seven snow tests pass, permanent-snow validation passes, and strategic-region validation reports 227 regions, 689 states, and 16,653 provinces.

- [ ] **Step 2: Run the full mod validator**

Run:

```powershell
python -B tools/validate_tc.py --limit 300
```

Expected: exit code zero. If unrelated dirty-work errors appear, report them separately and do not attribute them to the snow fix.

- [ ] **Step 3: Check whitespace only in the scoped text files**

Run:

```powershell
git diff --check -- common/weather.txt tools/validate_adiscord_strategic_regions.py tools/build_adiscord_terrain_snow.py tools/test_build_adiscord_terrain_snow.py
```

Expected: no scoped whitespace errors.

- [ ] **Step 4: Verify a fresh game and logs**

Start a genuinely new 1 January 2160 game; do not reuse a save created before these changes. After the map loads, inspect fresh `error.log` entries for `weather`, `snow`, `terrain`, `strategic region`, `bitmap`, and `palette`.

Expected: no new snow/weather/terrain/strategic-region load errors. Obtain a screenshot of the north showing continuous visible polar snow, a smooth southern boundary, and no permanent white spill into temperate lowlands. If no screenshot is available, report static completion but leave visual acceptance explicitly unverified.
