#!/usr/bin/env python3
"""Paint deterministic 3D-city masks for selected Vorkerland urban provinces."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import struct

from PIL import Image

from tools.lib.paths import repository_root


ROOT = repository_root()
CITIES_PATH = ROOT / "map" / "cities.bmp"
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"

CITY_PALETTE_INDEX = 15
TARGET_PROVINCES = frozenset(
    {
        8059,   # Revel
        8803,   # Verkhovye
        11795,  # Langar
        16587,  # Zshatsk
        16614,  # Norden
        16616,  # Old Zshat
        16635,  # Lower Orvin
        16641,  # Kern Ford
        16642,  # Ostvin
        16643,  # Riven
    }
)


@dataclass(frozen=True)
class BitmapLayout:
    width: int
    height: int
    pixel_offset: int
    row_stride: int
    bottom_up: bool

    def pixel_position(self, x: int, y: int) -> int:
        row = self.height - 1 - y if self.bottom_up else y
        return self.pixel_offset + row * self.row_stride + x


def bitmap_layout(source: bytes) -> BitmapLayout:
    """Return the layout of an uncompressed 8-bit indexed BMP."""
    if len(source) < 54 or source[:2] != b"BM":
        raise RuntimeError("map/cities.bmp must be a Windows BMP")
    pixel_offset = struct.unpack_from("<I", source, 10)[0]
    dib_size = struct.unpack_from("<I", source, 14)[0]
    if dib_size < 40:
        raise RuntimeError(f"map/cities.bmp uses unsupported DIB header size {dib_size}")
    width, signed_height = struct.unpack_from("<ii", source, 18)
    planes, bits_per_pixel = struct.unpack_from("<HH", source, 26)
    compression = struct.unpack_from("<I", source, 30)[0]
    if width <= 0 or signed_height == 0:
        raise RuntimeError(f"map/cities.bmp has invalid dimensions {width}x{signed_height}")
    if planes != 1 or bits_per_pixel != 8 or compression != 0:
        raise RuntimeError(
            "map/cities.bmp must be an uncompressed 8-bit paletted BMP "
            f"(planes={planes}, bpp={bits_per_pixel}, compression={compression})"
        )
    height = abs(signed_height)
    row_stride = ((width * bits_per_pixel + 31) // 32) * 4
    required_size = pixel_offset + row_stride * height
    if required_size > len(source):
        raise RuntimeError(
            f"map/cities.bmp pixel data is truncated: need {required_size}, found {len(source)}"
        )
    return BitmapLayout(width, height, pixel_offset, row_stride, signed_height > 0)


def target_colours(definition_path: Path | None = None) -> tuple[dict[int, int], list[str]]:
    """Return RGB keys for target land provinces and definition contract issues."""
    definition_path = DEFINITION_PATH if definition_path is None else definition_path
    issues: list[str] = []
    found: dict[int, int] = {}
    seen_colours: dict[int, int] = {}
    with definition_path.open(encoding="utf-8-sig", newline="") as handle:
        for line_number, fields in enumerate(csv.reader(handle, delimiter=";"), 1):
            if len(fields) < 7 or not fields[0].isdigit():
                continue
            province = int(fields[0])
            if province not in TARGET_PROVINCES:
                continue
            try:
                red, green, blue = map(int, fields[1:4])
            except ValueError:
                issues.append(
                    f"map/definition.csv:{line_number}: province {province} has invalid RGB"
                )
                continue
            colour = (red << 16) | (green << 8) | blue
            if colour in seen_colours:
                issues.append(
                    f"map/definition.csv:{line_number}: target provinces {seen_colours[colour]} "
                    f"and {province} share RGB {red},{green},{blue}"
                )
            seen_colours[colour] = province
            if fields[4] != "land":
                issues.append(
                    f"map/definition.csv:{line_number}: target province {province} is not land"
                )
            if fields[6] != "urban":
                issues.append(
                    f"map/definition.csv:{line_number}: target province {province} is not urban"
                )
            found[colour] = province
    missing = sorted(TARGET_PROVINCES - set(found.values()))
    if missing:
        issues.append(f"map/definition.csv: missing target provinces {missing}")
    return found, issues


def province_bytes(provinces: Image.Image, expected_size: tuple[int, int]) -> bytes:
    if provinces.mode != "RGB":
        raise RuntimeError(f"map/provinces.bmp must be RGB, found {provinces.mode}")
    if provinces.size != expected_size:
        raise RuntimeError(
            f"cities/provinces size mismatch: {expected_size} != {provinces.size}"
        )
    return provinces.tobytes()


def render_bytes(
    source: bytes,
    provinces: Image.Image,
    colours: dict[int, int],
) -> tuple[bytes, dict[int, int], frozenset[int]]:
    """Overlay target masks while preserving every byte outside their pixels."""
    layout = bitmap_layout(source)
    rgb = province_bytes(provinces, (layout.width, layout.height))
    output = bytearray(source)
    counts = {province: 0 for province in TARGET_PROVINCES}
    target_positions: set[int] = set()
    for index in range(layout.width * layout.height):
        colour_index = index * 3
        colour = (
            (rgb[colour_index] << 16)
            | (rgb[colour_index + 1] << 8)
            | rgb[colour_index + 2]
        )
        province = colours.get(colour)
        if province is None:
            continue
        x = index % layout.width
        y = index // layout.width
        position = layout.pixel_position(x, y)
        output[position] = CITY_PALETTE_INDEX
        counts[province] += 1
        target_positions.add(position)
    return bytes(output), counts, frozenset(target_positions)


def unmanaged_difference_count(
    original: bytes, generated: bytes, target_positions: frozenset[int]
) -> int:
    if len(original) != len(generated):
        return max(len(original), len(generated))
    return sum(
        first != second and index not in target_positions
        for index, (first, second) in enumerate(zip(original, generated))
    )


def generated_issues(
    source: bytes,
    provinces: Image.Image,
    colours: dict[int, int],
) -> list[str]:
    issues: list[str] = []
    generated, counts, target_positions = render_bytes(source, provinces, colours)
    for province, count in sorted(counts.items()):
        if count == 0:
            issues.append(f"map/provinces.bmp: target province {province} has an empty mask")
    outside = unmanaged_difference_count(source, generated, target_positions)
    if outside:
        issues.append(f"map/cities.bmp: generation would alter {outside} unmanaged bytes")
    missing_city_pixels = sum(source[position] != CITY_PALETTE_INDEX for position in target_positions)
    if missing_city_pixels:
        issues.append(
            f"map/cities.bmp: {missing_city_pixels} target pixels are not palette index "
            f"{CITY_PALETTE_INDEX}"
        )
    return issues


def validate() -> list[str]:
    issues: list[str] = []
    for path in (CITIES_PATH, PROVINCES_PATH, DEFINITION_PATH):
        if not path.is_file():
            issues.append(f"{path.relative_to(ROOT).as_posix()} is missing")
    if issues:
        return issues
    colours, definition_issues = target_colours()
    issues.extend(definition_issues)
    if definition_issues:
        return issues
    source = CITIES_PATH.read_bytes()
    try:
        with Image.open(BytesIO(source)) as cities, Image.open(PROVINCES_PATH) as provinces:
            if cities.mode != "P":
                issues.append(f"map/cities.bmp must be paletted, found {cities.mode}")
            layout = bitmap_layout(source)
            if cities.size != (layout.width, layout.height):
                issues.append(
                    f"map/cities.bmp header/Pillow size mismatch: "
                    f"{(layout.width, layout.height)} != {cities.size}"
                )
            issues.extend(generated_issues(source, provinces, colours))
    except (OSError, RuntimeError) as error:
        issues.append(str(error))
    return issues


def apply() -> None:
    colours, issues = target_colours()
    if issues:
        raise RuntimeError("\n".join(issues))
    source = CITIES_PATH.read_bytes()
    with Image.open(BytesIO(source)) as cities, Image.open(PROVINCES_PATH) as provinces:
        if cities.mode != "P":
            raise RuntimeError(f"map/cities.bmp must be paletted, found {cities.mode}")
        original_palette = cities.getpalette()
        generated, counts, target_positions = render_bytes(source, provinces, colours)
        empty = sorted(province for province, count in counts.items() if count == 0)
        if empty:
            raise RuntimeError(f"map/provinces.bmp: empty target masks {empty}")
        outside = unmanaged_difference_count(source, generated, target_positions)
        if outside:
            raise RuntimeError(f"generation would alter {outside} unmanaged bytes")
        with Image.open(BytesIO(generated)) as verification:
            if verification.mode != "P" or verification.size != cities.size:
                raise RuntimeError("generated cities.bmp changed mode or dimensions")
            if verification.getpalette() != original_palette:
                raise RuntimeError("generated cities.bmp changed its palette")

    temporary = CITIES_PATH.with_suffix(".bmp.tmp")
    try:
        with temporary.open("wb") as output:
            output.write(generated)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, CITIES_PATH)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        f"Generated Vorkerland city models for {len(TARGET_PROVINCES)} provinces "
        f"({sum(counts.values())} pixels)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate current output (default)")
    actions.add_argument("--apply", action="store_true", help="write map/cities.bmp")
    args = parser.parse_args()
    if args.apply:
        apply()
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Vorkerland city-model validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
