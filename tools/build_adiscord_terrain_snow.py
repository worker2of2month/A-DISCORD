#!/usr/bin/env python3
"""Generate permanent polar and high-altitude snow in ``map/terrain.bmp``.

HOI4's accumulated weather snow always melts when temperatures rise.  Vanilla
keeps ice caps and glaciers visible through graphical terrain entries carrying
``perm_snow = yes``.  A-Discord defines those entries as palette indices 16
(mountain) and 19 (plain), but its bitmap previously contained effectively no
such pixels.

The pass is deliberately conservative: it preserves seasonal snow as weather,
while reserving permanent snow for the extreme polar cap, northern mountains,
and the highest mountain pixels worldwide.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
TERRAIN_DEFINITION_PATH = ROOT / "common" / "terrain" / "00_terrain.txt"

POLAR_CAP_Y = 300
POLAR_MOUNTAIN_Y = 300
PERMANENT_PEAK_HEIGHT = 205

MIN_PERMANENT_SNOW_PIXELS = 320_000
MAX_PERMANENT_SNOW_PIXELS = 380_000
MIN_PERMANENT_MOUNTAIN_PIXELS = 5_000

WATER_TERRAIN = frozenset({14, 15})
MOUNTAIN_TERRAIN = frozenset({6, 10, 11, 16, 31})
SNOW_MOUNTAIN = 16
SNOW_PLAIN = 19
RESTORE_SNOW = {SNOW_MOUNTAIN: 11, SNOW_PLAIN: 0}


def classify_terrain(terrain: int, y: int, height: int) -> int:
    """Return the generated terrain palette index for one map pixel."""
    base = RESTORE_SNOW.get(terrain, terrain)
    if base in WATER_TERRAIN:
        return base
    mountain = base in MOUNTAIN_TERRAIN
    if y < POLAR_CAP_Y:
        return SNOW_MOUNTAIN if mountain else SNOW_PLAIN
    if mountain and (y < POLAR_MOUNTAIN_Y or height >= PERMANENT_PEAK_HEIGHT):
        return SNOW_MOUNTAIN
    return base


def generated_pixels(terrain: Image.Image, heightmap: Image.Image) -> list[int]:
    if terrain.mode != "P":
        raise RuntimeError(f"terrain.bmp must be paletted, found {terrain.mode}")
    if terrain.size != heightmap.size:
        raise RuntimeError(
            f"terrain/heightmap size mismatch: {terrain.size} != {heightmap.size}"
        )
    width, _height = terrain.size
    terrain_pixels = list(terrain.get_flattened_data())
    height_pixels = list(heightmap.convert("L").get_flattened_data())
    return [
        classify_terrain(value, index // width, height_pixels[index])
        for index, value in enumerate(terrain_pixels)
    ]


def snow_counts(pixels: list[int]) -> tuple[int, int]:
    return pixels.count(SNOW_MOUNTAIN), pixels.count(SNOW_PLAIN)


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


def validate() -> list[str]:
    issues: list[str] = []
    if not TERRAIN_DEFINITION_PATH.exists():
        issues.append("common/terrain/00_terrain.txt is missing")
    else:
        definition = TERRAIN_DEFINITION_PATH.read_text(
            encoding="utf-8-sig", errors="strict"
        )
        issues.extend(definition_issues(definition))
    if not TERRAIN_PATH.exists() or not HEIGHTMAP_PATH.exists():
        return ["map/terrain.bmp or map/heightmap.bmp is missing"]
    with Image.open(TERRAIN_PATH) as terrain, Image.open(HEIGHTMAP_PATH) as heightmap:
        current = list(terrain.get_flattened_data())
        expected = generated_pixels(terrain, heightmap)
    differences = sum(first != second for first, second in zip(current, expected))
    if differences:
        issues.append(
            f"map/terrain.bmp: {differences} pixels differ from permanent-snow generation"
        )
    issues.extend(coverage_issues(current))
    return issues


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
    # os.replace() is unreliable for BMPs watched by the Windows shell/HOI4.
    # Copying the already complete temporary file keeps the destination valid
    # even when metadata watchers have an open handle to the old image.
    with temporary.open("rb") as generated, TERRAIN_PATH.open("r+b") as destination:
        shutil.copyfileobj(generated, destination)
        destination.truncate()
    temporary.unlink()
    mountain_snow, plain_snow = snow_counts(pixels)
    print(
        "Generated permanent snow: "
        f"{mountain_snow} mountain + {plain_snow} polar plain pixels."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write map/terrain.bmp")
    args = parser.parse_args()
    if args.apply:
        apply()
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Permanent-snow terrain validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
