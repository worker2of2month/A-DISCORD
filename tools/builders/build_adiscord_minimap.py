"""Generate the A-Discord minimap from the current world map inputs."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[2]
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
MINIMAP_PATH = ROOT / "gfx" / "minimap" / "minimap.dds"
MINIMAP_SIZE = (268, 97)
OCEAN_TERRAIN_INDEX = 15


def _land_mask() -> Image.Image:
    with Image.open(TERRAIN_PATH) as terrain:
        if terrain.mode != "P":
            raise RuntimeError(f"terrain.bmp must be paletted, found {terrain.mode}")
        lookup = [255] * 256
        lookup[OCEAN_TERRAIN_INDEX] = 0
        mask = terrain.point(lookup, mode="L")
    return mask.resize(MINIMAP_SIZE, Image.Resampling.LANCZOS)


def _minimap() -> Image.Image:
    land = _land_mask()
    with Image.open(HEIGHTMAP_PATH) as heightmap:
        height = heightmap.convert("L").resize(MINIMAP_SIZE, Image.Resampling.LANCZOS)

    # The minimap is deliberately subdued so army and navy markers remain legible,
    # while the coast silhouette still follows the current custom world exactly.
    relief = ImageOps.autocontrast(height, cutoff=1)
    relief = ImageEnhance.Contrast(relief).enhance(1.25)
    land_colour = ImageOps.colorize(
        relief,
        black=(57, 72, 69),
        white=(184, 171, 126),
    )

    water = Image.new("RGB", MINIMAP_SIZE, (8, 24, 47))
    water_glow = ImageOps.colorize(height, black=(4, 15, 34), white=(12, 34, 61))
    water = Image.blend(water, water_glow, 0.28)
    result = Image.composite(land_colour, water, land)

    # Add a thin, quiet coast line after compositing so small islands do not merge
    # into the sea at the 268x97 display size.
    land_binary = land.point(lambda value: 255 if value >= 96 else 0)
    eroded_land = land_binary.filter(ImageFilter.MinFilter(3))
    coast = ImageChops.subtract(land_binary, eroded_land)
    coast_colour = Image.new("RGB", MINIMAP_SIZE, (150, 174, 158))
    result = Image.composite(coast_colour, result, coast.point(lambda value: value // 2))

    return result.convert("RGBA")


def _dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS")
    return stream.getvalue()


def expected_bytes() -> bytes:
    return _dds_bytes(_minimap())


def validate(expected: bytes) -> list[str]:
    if not MINIMAP_PATH.is_file():
        return [f"missing generated minimap: {MINIMAP_PATH.relative_to(ROOT)}"]
    if MINIMAP_PATH.read_bytes() != expected:
        return [f"generated minimap differs: {MINIMAP_PATH.relative_to(ROOT)}"]
    with Image.open(MINIMAP_PATH) as image:
        if image.size != MINIMAP_SIZE:
            return [
                f"generated minimap has size {image.size}, expected {MINIMAP_SIZE}"
            ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="compare output (default)")
    actions.add_argument("--apply", action="store_true", help="write generated minimap")
    args = parser.parse_args()

    try:
        expected = expected_bytes()
        if args.apply:
            MINIMAP_PATH.parent.mkdir(parents=True, exist_ok=True)
            MINIMAP_PATH.write_bytes(expected)
        issues = validate(expected)
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("A-Discord minimap is current (custom terrain silhouette, 268x97 DDS).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
