"""Build Kefreyt's local operations map from the actual HOI4 state geometry."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from tools.lib.paths import repository_root


ROOT = repository_root()
OUT = ROOT / "gfx" / "interface" / "VAL_operations"
WIDTH, HEIGHT = 420, 260
STATE_IDS = (43, 44, 45, 88, 59, 61)
VAL_STATES = (24, 42, 48, 54, 55, 56, 57, 168)
EXZ_STATES = (167, 169, 171, 180, 182, 185)

FRAME_COLORS = {
    43: ((15, 118, 124), (55, 105, 175), (185, 105, 40), (127, 15, 2), (100, 100, 105)),
    44: ((15, 118, 124), (55, 105, 175), (185, 105, 40), (127, 15, 2), (100, 100, 105)),
    45: ((15, 118, 124), (55, 105, 175), (185, 105, 40), (127, 15, 2), (100, 100, 105)),
    88: ((15, 118, 124), (55, 105, 175), (185, 105, 40), (127, 15, 2), (100, 100, 105)),
    59: ((74, 74, 66), (74, 74, 66), (74, 74, 66), (127, 15, 2), (100, 100, 105)),
    61: ((88, 78, 68), (88, 78, 68), (88, 78, 68), (127, 15, 2), (100, 100, 105)),
}


def state_provinces(state_id: int) -> set[int]:
    candidates = sorted((ROOT / "history" / "states").glob(f"{state_id}-*.txt"))
    if not candidates:
        raise FileNotFoundError(f"state {state_id}")
    text = candidates[0].read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"provinces\s*=\s*\{([^}]*)\}", text, re.S)
    if not match:
        raise ValueError(f"no provinces block in {candidates[0]}")
    return {int(value) for value in re.findall(r"\d+", match.group(1))}


def province_colors() -> tuple[dict[int, tuple[int, int, int]], set[tuple[int, int, int]]]:
    colors: dict[int, tuple[int, int, int]] = {}
    land: set[tuple[int, int, int]] = set()
    with (ROOT / "map" / "definition.csv").open(encoding="utf-8-sig", errors="replace") as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) < 5 or not row[0].isdigit():
                continue
            province = int(row[0])
            color = tuple(map(int, row[1:4]))
            colors[province] = color
            if row[4] == "land":
                land.add(color)
    return colors, land


def transform(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    cropped = mask.crop(box)
    scale = min(WIDTH / cropped.width, HEIGHT / cropped.height)
    size = (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale)))
    resized = cropped.resize(size, Image.Resampling.NEAREST)
    canvas = Image.new("L", (WIDTH, HEIGHT), 0)
    canvas.paste(resized, ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Kefreyt's local operations map.")
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    province_to_color, land_colors = province_colors()
    state_sets = {
        state: state_provinces(state)
        for state in (*STATE_IDS, *VAL_STATES, *EXZ_STATES)
    }
    color_to_state = {
        province_to_color[province]: state
        for state, provinces in state_sets.items()
        for province in provinces
        if province in province_to_color
    }

    provinces = Image.open(ROOT / "map" / "provinces.bmp").convert("RGB")
    focus_colors = set(color_to_state)
    min_x, min_y = provinces.width, provinces.height
    max_x = max_y = -1
    pixels = provinces.load()
    for y in range(provinces.height):
        for x in range(provinces.width):
            if pixels[x, y] in focus_colors:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0:
        raise RuntimeError("target states were not found in provinces.bmp")
    pad = 24
    box = (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(provinces.width, max_x + pad + 1),
        min(provinces.height, max_y + pad + 1),
    )

    cropped = provinces.crop(box)
    state_masks: dict[int, Image.Image] = {}
    for state in state_sets:
        colors = {province_to_color[p] for p in state_sets[state] if p in province_to_color}
        raw = Image.new("L", cropped.size, 0)
        raw.putdata([255 if pixel in colors else 0 for pixel in cropped.getdata()])
        state_masks[state] = transform(raw, (0, 0, cropped.width, cropped.height))

    scale = min(WIDTH / cropped.width, HEIGHT / cropped.height)
    size = (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale)))
    offset = ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2)
    land_raw = Image.new("L", cropped.size, 0)
    land_raw.putdata([255 if pixel in land_colors else 0 for pixel in cropped.getdata()])
    land_mask = transform(land_raw, (0, 0, cropped.width, cropped.height))

    background = Image.new("RGBA", (WIDTH, HEIGHT), (12, 13, 15, 255))
    terrain = Image.new("RGBA", (WIDTH, HEIGHT), (48, 49, 48, 255))
    background.alpha_composite(Image.composite(terrain, Image.new("RGBA", background.size), land_mask))
    draw = ImageDraw.Draw(background)
    for y in range(0, HEIGHT, 8):
        draw.line((0, y, WIDTH, y), fill=(52, 53, 51, 255), width=1)

    for state in VAL_STATES:
        fill = Image.new("RGBA", background.size, (82, 18, 17, 255))
        background.alpha_composite(Image.composite(fill, Image.new("RGBA", background.size), state_masks[state]))
    for state in EXZ_STATES:
        fill = Image.new("RGBA", background.size, (35, 37, 40, 255))
        background.alpha_composite(Image.composite(fill, Image.new("RGBA", background.size), state_masks[state]))

    all_mask = Image.new("L", background.size, 0)
    for mask in state_masks.values():
        all_mask = ImageChops.lighter(all_mask, mask)
    outer = all_mask.filter(ImageFilter.MaxFilter(5))
    border = Image.eval(outer, lambda p: p)
    border = Image.frombytes("L", border.size, bytes(max(a - b, 0) for a, b in zip(border.getdata(), all_mask.getdata())))
    background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (190, 178, 145, 150)), Image.new("RGBA", background.size), border))

    vignette = Image.new("RGBA", background.size, (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for i in range(18):
        vd.rectangle((i, i, WIDTH - i - 1, HEIGHT - i - 1), outline=(0, 0, 0, max(0, 9 - i // 2)))
    background.alpha_composite(vignette)
    background.save(OUT / "VAL_ops_map_background.png", optimize=True)

    for state in STATE_IDS:
        frames = Image.new("RGBA", (WIDTH * 5, HEIGHT), (0, 0, 0, 0))
        mask = state_masks[state]
        expanded = mask.filter(ImageFilter.MaxFilter(7))
        rim = Image.frombytes("L", mask.size, bytes(max(a - b, 0) for a, b in zip(expanded.getdata(), mask.getdata())))
        for index, color in enumerate(FRAME_COLORS[state]):
            frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            frame.alpha_composite(Image.composite(Image.new("RGBA", frame.size, (*color, 210)), Image.new("RGBA", frame.size), mask))
            frame.alpha_composite(Image.composite(Image.new("RGBA", frame.size, (235, 215, 160, 235)), Image.new("RGBA", frame.size), rim))
            frames.paste(frame, (WIDTH * index, 0))
        frames.save(OUT / f"VAL_ops_state_{state}.png", optimize=True)

    print(f"Wrote operations map to {OUT.relative_to(ROOT)}; source crop={box}, resized={size}, offset={offset}")


if __name__ == "__main__":
    main()
