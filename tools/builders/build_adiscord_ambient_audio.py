"""Place spatial ambience on sea coasts and settled victory points."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np
from PIL import Image

from tools.lib.paths import repository_root


ROOT = repository_root()
BEGIN = "# BEGIN ADISCORD ambient audio"
END = "# END ADISCORD ambient audio"
COAST_SPACING = 220
# The town sound uses falloff_infantry, with a maximum distance of 60.
CITY_SPACING = 60
MIN_CITY_VP = 5


def load_map(root: Path) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    lookup = np.zeros(1 << 24, dtype=np.uint16)
    kinds = {}
    with (root / "map/definition.csv").open(encoding="utf-8-sig") as source:
        for row in csv.reader(source, delimiter=";"):
            province, red, green, blue = map(int, row[:4])
            lookup[(red << 16) | (green << 8) | blue] = province
            kinds[province] = row[4]
    with Image.open(root / "map/provinces.bmp") as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint32)
    packed = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
    provinces = lookup[packed]
    with Image.open(root / "map/heightmap.bmp") as image:
        heights = np.asarray(image.convert("L"))
    if provinces.shape != heights.shape:
        raise ValueError("Province and height maps must have identical dimensions")
    return provinces, heights, kinds


def coast_mask(provinces: np.ndarray, kinds: dict[int, str]) -> np.ndarray:
    land = np.isin(provinces, [p for p, kind in kinds.items() if kind == "land" and p])
    sea = np.isin(provinces, [p for p, kind in kinds.items() if kind == "sea"])
    adjacent = np.roll(land, 1, axis=1) | np.roll(land, -1, axis=1)
    adjacent[1:] |= land[:-1]
    adjacent[:-1] |= land[1:]
    return sea & adjacent


def spaced_coast_pixels(mask: np.ndarray, spacing: int) -> list[tuple[int, int]]:
    """Cover the coastline with bounded emitters, including the horizontal seam."""
    width = mask.shape[1]
    cells = (width + spacing - 1) // spacing
    buckets: dict[tuple[int, int], list[tuple[int, int]]] = {}
    points = []
    for y_raw, x_raw in zip(*np.nonzero(mask)):
        x, y = int(x_raw), int(y_raw)
        cell_x, cell_y = x // spacing, y // spacing
        neighbours = (
            point
            for dx in range(-2, 3)
            for dy in range(-1, 2)
            for point in buckets.get(((cell_x + dx) % cells, cell_y + dy), ())
        )
        if any(
            min(abs(x - px), width - abs(x - px)) ** 2 + (y - py) ** 2 < spacing ** 2
            for px, py in neighbours
        ):
            continue
        points.append((x, y))
        buckets.setdefault((cell_x, cell_y), []).append((x, y))
    return points


def city_positions(
    root: Path, provinces: np.ndarray, heights: np.ndarray, kinds: dict[int, str]
) -> list[tuple[str, float, float, float]]:
    cities = {}
    for path in sorted((root / "history/states").glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="utf-8-sig"))
        if re.search(r"\bimpassable\s*=\s*yes\b", text):
            continue
        for province, score in re.findall(
            r"victory_points\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", text
        ):
            if int(score) >= MIN_CITY_VP and kinds.get(int(province)) == "land":
                province_id = int(province)
                cities[province_id] = max(int(score), cities.get(province_id, 0))
    anchors = {}
    for line in (root / "map/unitstacks.txt").read_text(encoding="utf-8").splitlines():
        fields = line.split(";")
        if len(fields) >= 5 and fields[1] == "0":
            anchors[int(fields[0])] = (float(fields[2]), float(fields[4]))
    height, width = provinces.shape
    result = {}
    # A dense city cluster shares its strongest victory point's ambience.
    for province in sorted(cities, key=lambda province: (-cities[province], province)):
        anchor = anchors.get(province)
        if anchor:
            x, z = anchor
            px, py = int(x), height - 1 - int(z)
        if not anchor or not (
            0 <= px < width and 0 <= py < height and provinces[py, px] == province
        ):
            ys, xs = np.nonzero(provinces == province)
            if not len(xs):
                raise ValueError(f"City province {province} is missing from the map")
            # A centroid may lie outside an irregular province; use its nearest real pixel.
            nearest = int(np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2))
            px, py = int(xs[nearest]), int(ys[nearest])
            x, z = float(px), float(height - 1 - py)
        if any(
            min(abs(x - kept_x), width - abs(x - kept_x)) ** 2 + (z - kept_z) ** 2
            < CITY_SPACING ** 2
            for _, kept_x, _, kept_z in result.values()
        ):
            continue
        result[province] = (f"ADISCORD_town_{province}", x, float(heights[py, px]) / 10, z)
    return [result[province] for province in sorted(result)]


def render_type(entity: str, positions: list[tuple[str, float, float, float]]) -> str:
    lines = ["type = {", f'\ttype = "{entity}"', "\tuse_animation = no"]
    for name, x, y, z in positions:
        lines.extend([
            "\tobject = {",
            f'\t\tname = "{name}"',
            f"\t\tposition = {{ {x:.2f} {y:.2f} {z:.2f} }}",
            "\t\trotation = { 0 0 0 }",
            "\t}",
        ])
    lines.append("}")
    return "\n".join(lines)


def replace_section(original: bytes, section: str) -> bytes:
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    payload = (BEGIN + "\n# Generated by tools/builders/build_adiscord_ambient_audio.py\n"
               + section + "\n" + END + "\n").replace("\n", newline.decode()).encode()
    pattern = re.escape(BEGIN.encode()) + rb".*?" + re.escape(END.encode()) + rb"\r?\n?"
    matches = list(re.finditer(pattern, original, re.S))
    if len(matches) > 1 or original.count(BEGIN.encode()) != len(matches):
        raise ValueError("Ambient audio ownership markers are duplicated or incomplete")
    if matches:
        match = matches[0]
        return original[:match.start()] + payload + original[match.end():]
    return original.rstrip(b"\r\n") + newline * 2 + payload


def build(root: Path = ROOT) -> tuple[bytes, int, int]:
    provinces, heights, kinds = load_map(root)
    coast = spaced_coast_pixels(coast_mask(provinces, kinds), COAST_SPACING)
    water = [
        (f"ADISCORD_coast_{x}_{y}", float(x), 0.0, float(provinces.shape[0] - 1 - y))
        for x, y in coast
    ]
    cities = city_positions(root, provinces, heights, kinds)
    section = render_type("ambient_water_entity", water) + "\n\n"
    section += render_type("ADISCORD_ambient_town_entity", cities)
    path = root / "map/ambient_object.txt"
    return replace_section(path.read_bytes(), section), len(water), len(cities)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload, coasts, cities = build()
    path = ROOT / "map/ambient_object.txt"
    changed = payload != path.read_bytes()
    print(f"Coastal sources: {coasts}; city sources: {cities}; changed: {changed}")
    if args.apply and changed:
        path.write_bytes(payload)
    return int(changed and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
