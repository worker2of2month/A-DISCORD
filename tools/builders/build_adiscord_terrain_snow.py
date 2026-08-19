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

The cap edge is a *graded* band rather than a threshold.  An earlier pass gave
the boundary an organic wiggle but still flipped every column from snow to
vegetation in a single row, which read in-game as a hard painted edge where the
green forest bands stop dead against grey tundra.  Snow now wins a per-pixel
contest against fine noise inside a band whose width itself varies along the
coast, so the two biomes interleave in tongues and pockets.  The northern
mountain extension follows the same band instead of the old flat
``y = 300`` floor, which used to leave a visible map-wide straight line.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import os
import re
from pathlib import Path

from PIL import Image
from tools.lib.map_raster import value_noise
from tools.lib.paths import repository_root


ROOT = repository_root()
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
TERRAIN_DEFINITION_PATH = ROOT / "common" / "terrain" / "00_terrain.txt"

POLAR_CAP_Y = 300
POLAR_CAP_GENERATED_OFFSET = 12
POLAR_CAP_LONG_CELL = 700
POLAR_CAP_MEDIUM_CELL = 180
POLAR_CAP_DETAIL_CELL = 60
POLAR_CAP_LONG_AMPLITUDE = 18
POLAR_CAP_MEDIUM_AMPLITUDE = 16
POLAR_CAP_DETAIL_AMPLITUDE = 8
POLAR_CAP_RELIEF_SCALE = 0.08
POLAR_CAP_RELIEF_MIN = -7
POLAR_CAP_RELIEF_MAX = 16
POLAR_MOUNTAIN_MARGIN = 22
PERMANENT_PEAK_HEIGHT = 205

# The permanent-snow edge is a band, not a line.  ``HALF_WIDTH`` is the widest
# half-band in pixels, scaled per column so the transition narrows and widens
# along the coast; ``DETAIL_CELL`` sets how chunky the interlocking tongues are.
POLAR_TRANSITION_HALF_WIDTH = 15
POLAR_TRANSITION_MIN_SCALE = 0.35
POLAR_TRANSITION_WIDTH_CELL = 130
POLAR_TRANSITION_DETAIL_CELL = 13

MIN_PERMANENT_SNOW_PIXELS = 320_000
MAX_PERMANENT_SNOW_PIXELS = 380_000
MIN_PERMANENT_MOUNTAIN_PIXELS = 5_000
POLAR_SEAM_SCAN_MIN_Y = 220
POLAR_SEAM_SCAN_MAX_Y = 380
MAX_POLAR_ROW_TRANSITION_SHARE = 0.12
MAX_POLAR_INDEX_ROW_CHANGE_SHARE = 0.22
MIN_POLAR_SEAM_ROW_LAND = 400

WATER_TERRAIN = frozenset({14, 15})
MOUNTAIN_TERRAIN = frozenset({6, 10, 11, 16, 31})
SNOW_MOUNTAIN = 16
SNOW_PLAIN = 19
RESTORE_SNOW = {SNOW_MOUNTAIN: 11, SNOW_PLAIN: 0}
URBAN_TERRAIN = 13

# These are existing combat-urban provinces whose complete graphical masks
# were missing or partial.  Keeping the set explicit prevents a global
# definition.csv-to-bitmap rewrite from swallowing intentional terrain blends.
VORKERLAND_GRAPHICAL_URBAN_PROVINCES = frozenset(
    {
        4443,   # Remmel
        6192,   # Isaiah
        8243,   # Old Isaiah
        8803,   # Verkhovye
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


def stable_unit_hash(value: int, salt: int) -> float:
    """Return a deterministic unit interval value for one integer cell."""
    mixed = (value * 73856093) ^ (salt * 19349663)
    mixed = (mixed ^ (mixed >> 13)) * 1274126177
    return ((mixed ^ (mixed >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def smooth_value_noise(x: int, cell_size: int, salt: int) -> float:
    """Return continuous deterministic value noise along the map's x-axis."""
    left = x // cell_size
    fraction = (x % cell_size) / cell_size
    blend = fraction * fraction * (3.0 - 2.0 * fraction)
    first = stable_unit_hash(left, salt) * 2.0 - 1.0
    second = stable_unit_hash(left + 1, salt) * 2.0 - 1.0
    return first + (second - first) * blend


def polar_cap_longitude(x: int) -> float:
    """Return the column term of the permanent-snow edge, in pixels."""
    return (
        POLAR_CAP_LONG_AMPLITUDE
        * smooth_value_noise(x, POLAR_CAP_LONG_CELL, 17)
        + POLAR_CAP_MEDIUM_AMPLITUDE
        * smooth_value_noise(x, POLAR_CAP_MEDIUM_CELL, 31)
        + POLAR_CAP_DETAIL_AMPLITUDE
        * smooth_value_noise(x, POLAR_CAP_DETAIL_CELL, 47)
    )


def polar_cap_relief(height: int) -> float:
    """Return the elevation term of the permanent-snow edge, in pixels.

    High ground holds snow further from the pole and valley floors lose it
    earlier, so the cap edge reads as a snow *line* following the topography
    rather than as a painted region boundary.
    """
    return max(
        POLAR_CAP_RELIEF_MIN,
        min(POLAR_CAP_RELIEF_MAX, (height - 100) * POLAR_CAP_RELIEF_SCALE),
    )


def polar_cap_boundary(x: int, height: int) -> int:
    """Return an organic permanent-snow edge for one map column."""
    if POLAR_CAP_Y <= 0:
        return POLAR_CAP_Y
    return round(
        POLAR_CAP_Y
        + POLAR_CAP_GENERATED_OFFSET
        + polar_cap_longitude(x)
        + polar_cap_relief(height)
    )


def polar_transition_half_width(x: int, y: int) -> float:
    """Return the local half-width of the permanent-snow transition band."""
    scale = POLAR_TRANSITION_MIN_SCALE + (1.0 - POLAR_TRANSITION_MIN_SCALE) * (
        0.5 + 0.5 * value_noise(x, y, POLAR_TRANSITION_WIDTH_CELL, 61)
    )
    return max(1.0, POLAR_TRANSITION_HALF_WIDTH * scale)


def polar_snow_signal(x: int, y: int, height: int, offset: int = 0) -> float:
    """Return a positive value when a pixel falls inside the permanent cap.

    ``offset`` pushes the boundary further from the pole, which is how the
    northern mountain extension keeps snow a little south of the plains cap
    without reintroducing a straight horizontal cutoff.

    A non-positive :data:`POLAR_CAP_Y` switches the cap off entirely.  The band
    has to honour that explicitly: it reaches up to
    :data:`POLAR_TRANSITION_HALF_WIDTH` past the boundary in both directions, so
    a boundary at row zero would still have painted snow on the first row.
    """
    if POLAR_CAP_Y <= 0:
        return -1.0
    boundary = polar_cap_boundary(x, height) + offset
    half_width = polar_transition_half_width(x, y)
    mix = (boundary - y) / half_width
    return mix - value_noise(x, y, POLAR_TRANSITION_DETAIL_CELL, 73)


def classify_terrain(
    terrain: int,
    y: int,
    height: int,
    x: int | None = None,
) -> int:
    """Return the generated terrain palette index for one map pixel."""
    base = RESTORE_SNOW.get(terrain, terrain)
    if base in WATER_TERRAIN:
        return base
    mountain = base in MOUNTAIN_TERRAIN
    if x is None:
        if y < POLAR_CAP_Y:
            return SNOW_MOUNTAIN if mountain else SNOW_PLAIN
        if mountain and (y < POLAR_CAP_Y or height >= PERMANENT_PEAK_HEIGHT):
            return SNOW_MOUNTAIN
        return base
    if polar_snow_signal(x, y, height) > 0.0:
        return SNOW_MOUNTAIN if mountain else SNOW_PLAIN
    if mountain and (
        polar_snow_signal(x, y, height, POLAR_MOUNTAIN_MARGIN) > 0.0
        or height >= PERMANENT_PEAK_HEIGHT
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
        raise RuntimeError(f"definition.csv: missing graphical urban provinces {missing}")
    return selected


def generated_pixels(
    terrain: Image.Image,
    heightmap: Image.Image,
    provinces: Image.Image,
    selected_colors: dict[tuple[int, int, int], int] | None = None,
) -> list[int]:
    if terrain.mode != "P":
        raise RuntimeError(f"terrain.bmp must be paletted, found {terrain.mode}")
    if terrain.size != heightmap.size or terrain.size != provinces.size:
        raise RuntimeError(
            "terrain/heightmap/provinces size mismatch: "
            f"{terrain.size} != {heightmap.size} != {provinces.size}"
        )
    selected_colors = selected_colors or province_color_contract()
    selected_rgb = set(selected_colors)
    width, _height = terrain.size
    terrain_pixels = list(terrain.get_flattened_data())
    height_pixels = list(heightmap.convert("L").get_flattened_data())
    province_pixels = provinces.convert("RGB").tobytes()
    return [
        (
            URBAN_TERRAIN
            if tuple(province_pixels[index * 3:index * 3 + 3]) in selected_rgb
            else classify_terrain(
                value,
                index // width,
                height_pixels[index],
                index % width,
            )
        )
        for index, value in enumerate(terrain_pixels)
    ]


def urban_coverage_issues(
    pixels: list[int],
    provinces: Image.Image,
    selected_colors: dict[tuple[int, int, int], int],
) -> list[str]:
    """Require every pixel of every explicit repair province to be urban."""
    issues: list[str] = []
    province_pixels = provinces.convert("RGB").tobytes()
    counts = {province_id: [0, 0] for province_id in selected_colors.values()}
    id_by_color = selected_colors
    for index, terrain_value in enumerate(pixels):
        color = tuple(province_pixels[index * 3:index * 3 + 3])
        province_id = id_by_color.get(color)
        if province_id is None:
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


def polar_seam_issues(
    pixels: list[int],
    width: int,
    height: int,
) -> list[str]:
    """Reject a map-wide horizontal edge in the permanent-snow mask."""
    if len(pixels) != width * height:
        return ["map/terrain.bmp: pixel count does not match terrain dimensions"]
    start_y = max(1, min(height, POLAR_SEAM_SCAN_MIN_Y))
    end_y = max(start_y, min(height, POLAR_SEAM_SCAN_MAX_Y))
    snow_values = {SNOW_MOUNTAIN, SNOW_PLAIN}
    maximum = 0
    maximum_y = start_y
    for y in range(start_y, end_y):
        previous = (y - 1) * width
        current = y * width
        transitions = sum(
            (pixels[previous + x] in snow_values)
            != (pixels[current + x] in snow_values)
            for x in range(width)
        )
        if transitions > maximum:
            maximum = transitions
            maximum_y = y
    allowed = round(width * MAX_POLAR_ROW_TRANSITION_SHARE)
    if maximum > allowed:
        return [
            "map/terrain.bmp: horizontal permanent-snow seam at "
            f"y={maximum_y} changes {maximum}/{width} columns "
            f"(limit {allowed})"
        ]
    return []


def polar_index_seam_issues(
    pixels: list[int],
    width: int,
    height: int,
) -> list[str]:
    """Reject a straight horizontal edge in any northern terrain index.

    The snow-mask check above cannot see a seam that swaps one land index for
    another, which is exactly how the old ``y = 300`` mountain floor showed up:
    a single row where hundreds of grey mountain pixels became white snow
    mountain.  This compares the full palette index row by row over the land.
    """
    if len(pixels) != width * height:
        return ["map/terrain.bmp: pixel count does not match terrain dimensions"]
    start_y = max(1, min(height, POLAR_SEAM_SCAN_MIN_Y))
    end_y = max(start_y, min(height, POLAR_SEAM_SCAN_MAX_Y))
    worst_share = 0.0
    worst = (start_y, 0, 0)
    for y in range(start_y, end_y):
        previous = (y - 1) * width
        current = y * width
        land = 0
        changed = 0
        for x in range(width):
            above = pixels[previous + x]
            below = pixels[current + x]
            if above in WATER_TERRAIN and below in WATER_TERRAIN:
                continue
            land += 1
            if above != below:
                changed += 1
        if land < MIN_POLAR_SEAM_ROW_LAND:
            continue
        share = changed / land
        if share > worst_share:
            worst_share = share
            worst = (y, changed, land)
    if worst_share > MAX_POLAR_INDEX_ROW_CHANGE_SHARE:
        seam_y, changed, land = worst
        return [
            "map/terrain.bmp: horizontal terrain-index seam at "
            f"y={seam_y} changes {changed}/{land} land pixels "
            f"({worst_share:.0%}, limit {MAX_POLAR_INDEX_ROW_CHANGE_SHARE:.0%})"
        ]
    return []


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
        or not HEIGHTMAP_PATH.exists()
        or not PROVINCES_PATH.exists()
    ):
        return ["map/terrain.bmp, map/heightmap.bmp, or map/provinces.bmp is missing"]
    try:
        selected_colors = province_color_contract()
    except (OSError, RuntimeError, ValueError) as error:
        return [str(error)]
    with (
        Image.open(TERRAIN_PATH) as terrain,
        Image.open(HEIGHTMAP_PATH) as heightmap,
        Image.open(PROVINCES_PATH) as provinces,
    ):
        current = list(terrain.get_flattened_data())
        terrain_size = terrain.size
        expected = generated_pixels(terrain, heightmap, provinces, selected_colors)
        issues.extend(urban_coverage_issues(current, provinces, selected_colors))
    differences = sum(first != second for first, second in zip(current, expected))
    if differences:
        issues.append(
            f"map/terrain.bmp: {differences} pixels differ from permanent-snow generation"
        )
    issues.extend(coverage_issues(current))
    issues.extend(polar_seam_issues(current, *terrain_size))
    issues.extend(polar_index_seam_issues(current, *terrain_size))
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
        Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as heightmap,
        Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces,
    ):
        terrain = source.copy()
        pixels = generated_pixels(source, heightmap, provinces, selected_colors)
        problems.extend(urban_coverage_issues(pixels, provinces, selected_colors))
    problems.extend(coverage_issues(pixels))
    problems.extend(polar_seam_issues(pixels, *terrain.size))
    problems.extend(polar_index_seam_issues(pixels, *terrain.size))
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
    actions.add_argument("--check", action="store_true", help="validate current generated output (default)")
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
