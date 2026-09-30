#!/usr/bin/env python3
"""Generate permanent snow and the bounded Vorkerland urban overlay.

HOI4's accumulated weather snow always melts when temperatures rise.  Vanilla
keeps ice caps and glaciers visible through graphical terrain entries carrying
``perm_snow = yes``.  A-Discord defines those entries as palette indices 16
(mountain) and 19 (plain), but its bitmap previously contained effectively no
such pixels.

The pass is deliberately conservative: it preserves seasonal snow as weather,
while reserving permanent snow for the extreme polar cap, northern mountains,
and the highest mountain pixels worldwide.  It also repairs four provinces
which are already ``urban`` in ``map/definition.csv`` but whose graphical
terrain was still plains or desert.  No new combat terrain is introduced.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from math import sin
import os
import re
from pathlib import Path

import numpy as np
from PIL import Image
from tools.lib.coastal_clearance import (
    URBAN_FALLBACK_PALETTE,
    urban_blocked,
    water_colours,
    water_mask,
)
from tools.lib.paths import repository_root


ROOT = repository_root()
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
CITIES_PATH = ROOT / "map" / "cities.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
TERRAIN_DEFINITION_PATH = ROOT / "common" / "terrain" / "00_terrain.txt"

POLAR_CAP_Y = 300
POLAR_MOUNTAIN_Y = 300
PERMANENT_PEAK_HEIGHT = 205
# The cap edge is not a ruler line: per column it reaches up to this share of
# the cap latitude further south, with a few pixels of ragged dithering.
POLAR_EDGE_SOUTHWARD_SHARE = 0.10
POLAR_EDGE_DITHER_PIXELS = 3

MIN_PERMANENT_SNOW_PIXELS = 320_000
MAX_PERMANENT_SNOW_PIXELS = 400_000
MIN_PERMANENT_MOUNTAIN_PIXELS = 5_000

WATER_TERRAIN = frozenset({14, 15})
MOUNTAIN_TERRAIN = frozenset({6, 10, 11, 16, 31})
SNOW_MOUNTAIN = 16
SNOW_PLAIN = 19
RESTORE_SNOW = {SNOW_MOUNTAIN: 11, SNOW_PLAIN: 0}
URBAN_TERRAIN = 13
CITY_PALETTE_INDEX = 15
CITY_PALETTE_INDICES = frozenset({2, CITY_PALETTE_INDEX})

# These are existing combat-urban provinces whose complete graphical masks
# were missing or partial.  Keeping the set explicit prevents a global
# definition.csv-to-bitmap rewrite from swallowing intentional terrain blends.
VORKERLAND_GRAPHICAL_URBAN_PROVINCES = frozenset(
    {
        4443,  # Remmel
        6192,  # Isaiah
        8243,  # Old Isaiah
        8803,  # Verkhovye
        11944,  # Sutritsa
        12443,  # Kairholm
        16560,  # Severin
        16593,  # Zatern
        16616,  # Old Zshat
        16635,  # Lower Orvin
        16640,  # East Orvin
        16642,  # Ostvin
    }
)


def _unit_hash(x: int, y: int, salt: int) -> float:
    value = ((x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) & 0xFFFFFFFF
    value = ((value ^ (value >> 13)) * 1274126177) & 0xFFFFFFFF
    return (value ^ (value >> 16)) / 0xFFFFFFFF


def polar_edge_share(x: int) -> float:
    """Deterministic 0..1 southward reach of the polar edge in column ``x``."""
    wave = (
        0.50
        + 0.26 * sin(x / 41.0 + 1.3)
        + 0.14 * sin(x / 17.3 + 0.4)
        + 0.07 * sin(x / 6.1 + 2.2)
        + 0.03 * sin(x / 2.7)
    )
    return min(1.0, max(0.0, wave))


def polar_limit(limit: int, x: int | None, y: int) -> float:
    """Latitude limit for one pixel; ``x=None`` keeps the straight reference."""
    if x is None or limit <= 0:
        return limit
    reach = limit * POLAR_EDGE_SOUTHWARD_SHARE * polar_edge_share(x)
    return limit + reach - POLAR_EDGE_DITHER_PIXELS * _unit_hash(x, y, 71)


def classify_terrain(terrain: int, y: int, height: int, x: int | None = None) -> int:
    """Return the generated terrain palette index for one map pixel."""
    base = RESTORE_SNOW.get(terrain, terrain)
    if base in WATER_TERRAIN:
        return base
    mountain = base in MOUNTAIN_TERRAIN
    if y < polar_limit(POLAR_CAP_Y, x, y):
        return SNOW_MOUNTAIN if mountain else SNOW_PLAIN
    if mountain and (
        y < polar_limit(POLAR_MOUNTAIN_Y, x, y) or height >= PERMANENT_PEAK_HEIGHT
    ):
        return SNOW_MOUNTAIN
    return base


def province_color_contract() -> dict[tuple[int, int, int], int]:
    """Return RGB -> province ID for the exact urban-repair province set."""
    selected: dict[tuple[int, int, int], int] = {}
    definition_ids: set[int] = set()
    for line in DEFINITION_PATH.read_text(
        encoding="utf-8-sig", errors="strict"
    ).splitlines():
        fields = line.split(";")
        if len(fields) < 7 or not fields[0].isdigit():
            continue
        province_id = int(fields[0])
        if province_id not in VORKERLAND_GRAPHICAL_URBAN_PROVINCES:
            continue
        definition_ids.add(province_id)
        if fields[4] != "land":
            raise RuntimeError(
                f"province {province_id}: Vorkerland graphical urban target is not land"
            )
        if fields[6] != "urban":
            raise RuntimeError(
                f"province {province_id}: graphical urban repair requires definition terrain urban"
            )
        color = tuple(map(int, fields[1:4]))
        if color in selected:
            raise RuntimeError(
                f"definition.csv: duplicate RGB {color} for graphical urban targets"
            )
        selected[color] = province_id
    missing = sorted(VORKERLAND_GRAPHICAL_URBAN_PROVINCES - definition_ids)
    if missing:
        raise RuntimeError(
            f"definition.csv: missing graphical urban provinces {missing}"
        )
    return selected


def land_color_contract() -> set[tuple[int, int, int]]:
    """Return RGB province colours which are valid city-mask land targets."""
    colours: set[tuple[int, int, int]] = set()
    for line in DEFINITION_PATH.read_text(
        encoding="utf-8-sig", errors="strict"
    ).splitlines():
        fields = line.split(";")
        if len(fields) < 7 or not fields[0].isdigit() or fields[4] != "land":
            continue
        colours.add(tuple(map(int, fields[1:4])))
    return colours


def generated_pixels(
    terrain: Image.Image,
    heightmap: Image.Image,
    provinces: Image.Image,
    selected_colors: dict[tuple[int, int, int], int] | None = None,
    *,
    cities: Image.Image | None = None,
    land_colors: set[tuple[int, int, int]] | None = None,
) -> list[int]:
    if terrain.mode != "P":
        raise RuntimeError(f"terrain.bmp must be paletted, found {terrain.mode}")
    if terrain.size != heightmap.size or terrain.size != provinces.size:
        raise RuntimeError(
            "terrain/heightmap/provinces size mismatch: "
            f"{terrain.size} != {heightmap.size} != {provinces.size}"
        )
    if cities is not None:
        if cities.size != terrain.size:
            raise RuntimeError(
                f"terrain/cities size mismatch: {terrain.size} != {cities.size}"
            )
        if cities.mode != "P":
            raise RuntimeError(f"cities.bmp must be paletted, found {cities.mode}")
    selected_colors = selected_colors or province_color_contract()
    land_colors = land_colors or land_color_contract()
    selected_rgb = set(selected_colors)
    width, _height = terrain.size
    terrain_pixels = list(terrain.get_flattened_data())
    height_pixels = list(heightmap.convert("L").get_flattened_data())
    province_pixels = provinces.convert("RGB").tobytes()
    city_pixels = list(cities.get_flattened_data()) if cities is not None else None
    blocked = shoreline_band(provinces)
    result = [
        (
            URBAN_TERRAIN
            if (
                tuple(province_pixels[index * 3 : index * 3 + 3]) in selected_rgb
                or (
                    city_pixels is not None
                    and city_pixels[index] in CITY_PALETTE_INDICES
                    and tuple(province_pixels[index * 3 : index * 3 + 3]) in land_colors
                )
            )
            else classify_terrain(
                value, index // width, height_pixels[index], index % width
            )
        )
        for index, value in enumerate(terrain_pixels)
    ]
    # No city meshes on the waterline: the shared shore band falls back to plains.
    for index in np.flatnonzero(blocked):
        if result[index] == URBAN_TERRAIN:
            result[index] = URBAN_FALLBACK_PALETTE
    return result


def shoreline_band(provinces: Image.Image) -> np.ndarray:
    """Flat mask of dry pixels inside the shared urban shoreline clearance."""
    rgb = np.asarray(provinces.convert("RGB"))
    water = water_mask(rgb, water_colours(DEFINITION_PATH))
    if not water.any():
        return np.zeros(rgb.shape[0] * rgb.shape[1], dtype=bool)
    return (urban_blocked(water, rgb, DEFINITION_PATH) & ~water).reshape(-1)


def urban_coverage_issues(
    pixels: list[int],
    provinces: Image.Image,
    selected_colors: dict[tuple[int, int, int], int],
) -> list[str]:
    """Require every pixel of every explicit repair province to be urban.

    Pixels in the shared shoreline band are exempt: they stay plains.
    """
    issues: list[str] = []
    province_pixels = provinces.convert("RGB").tobytes()
    blocked = shoreline_band(provinces)
    counts = {province_id: [0, 0] for province_id in selected_colors.values()}
    id_by_color = selected_colors
    for index, terrain_value in enumerate(pixels):
        color = tuple(province_pixels[index * 3 : index * 3 + 3])
        province_id = id_by_color.get(color)
        if province_id is None or blocked[index]:
            continue
        counts[province_id][0] += 1
        if terrain_value == URBAN_TERRAIN:
            counts[province_id][1] += 1
    for province_id, (total, urban) in sorted(counts.items()):
        if not total:
            issues.append(f"map/provinces.bmp: province {province_id} has no pixels")
        elif urban != total:
            issues.append(
                f"map/terrain.bmp: province {province_id} has {urban}/{total} graphical urban pixels"
            )
    return issues


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
    if (
        not TERRAIN_PATH.exists()
        or not CITIES_PATH.exists()
        or not HEIGHTMAP_PATH.exists()
        or not PROVINCES_PATH.exists()
    ):
        return [
            "map/terrain.bmp, map/cities.bmp, map/heightmap.bmp, or map/provinces.bmp is missing"
        ]
    try:
        selected_colors = province_color_contract()
    except (OSError, RuntimeError, ValueError) as error:
        return [str(error)]
    with (
        Image.open(TERRAIN_PATH) as terrain,
        Image.open(CITIES_PATH) as cities,
        Image.open(HEIGHTMAP_PATH) as heightmap,
        Image.open(PROVINCES_PATH) as provinces,
    ):
        current = list(terrain.get_flattened_data())
        expected = generated_pixels(
            terrain, heightmap, provinces, selected_colors, cities=cities
        )
        issues.extend(urban_coverage_issues(current, provinces, selected_colors))
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

    selected_colors = province_color_contract()
    with (
        Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as source,
        Image.open(CITIES_PATH) as cities,
        Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as heightmap,
        Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces,
    ):
        terrain = source.copy()
        pixels = generated_pixels(
            source, heightmap, provinces, selected_colors, cities=cities
        )
        problems.extend(urban_coverage_issues(pixels, provinces, selected_colors))
    problems.extend(coverage_issues(pixels))
    if problems:
        raise RuntimeError("\n".join(problems))

    terrain.putdata(pixels)
    temporary = TERRAIN_PATH.with_suffix(".bmp.tmp")
    try:
        terrain.save(temporary, format="BMP")
        with temporary.open("r+b") as generated:
            generated.flush()
            os.fsync(generated.fileno())
        os.replace(temporary, TERRAIN_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    mountain_snow, plain_snow = snow_counts(pixels)
    print(
        "Generated permanent snow: "
        f"{mountain_snow} mountain + {plain_snow} polar plain pixels."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="validate current generated output (default)",
    )
    actions.add_argument("--apply", action="store_true", help="write map/terrain.bmp")
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
