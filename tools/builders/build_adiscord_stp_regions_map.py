"""Build the Battle for Stelander decision map from actual HOI4 state geometry."""

from __future__ import annotations

import argparse
import csv
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from tools.lib.paths import repository_root


ROOT = repository_root()
OUT = ROOT / "gfx" / "interface" / "STP_regions"
WIDTH, HEIGHT = 420, 260
STATE_IDS = (1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88)

# Frames match the status order in ADISCORD_STP_regions.gfx/gui:
# contested, Shabrat leaning/entrenched, Party leaning/entrenched,
# local forces leaning/dominant.
FRAME_COLORS = (
    (94, 99, 105),
    (43, 91, 153),
    (49, 154, 225),
    (91, 42, 114),
    (164, 56, 194),
    (162, 133, 34),
    (232, 193, 46),
)
INITIAL_STATUS_FRAME = {
    1: 2,
    2: 3,
    3: 0,
    28: 4,
    29: 3,
    43: 6,
    44: 6,
    45: 0,
    46: 0,
    53: 5,
    88: 6,
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


def state_overlay(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    contracted = mask.filter(ImageFilter.MinFilter(3))
    rim = Image.frombytes(
        "L",
        mask.size,
        bytes(max(inner - core, 0) for inner, core in zip(mask.tobytes(), contracted.tobytes())),
    )
    frame.alpha_composite(
        Image.composite(
            Image.new("RGBA", frame.size, (*color, 214)),
            Image.new("RGBA", frame.size),
            mask,
        )
    )
    frame.alpha_composite(
        Image.composite(
            Image.new("RGBA", frame.size, (232, 218, 176, 235)),
            Image.new("RGBA", frame.size),
            rim,
        )
    )
    return frame


def contact_sheet(background: Image.Image, masks: dict[int, Image.Image]) -> Image.Image:
    sheet = Image.new("RGBA", (920, 650), (10, 11, 13, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((34, 24), "BATTLE FOR STELANDER - INITIAL REGIONAL MAP", fill=(224, 215, 184, 255))

    preview = background.copy()
    for state_id in STATE_IDS:
        preview.alpha_composite(state_overlay(masks[state_id], FRAME_COLORS[INITIAL_STATUS_FRAME[state_id]]))
    preview = preview.resize((840, 520), Image.Resampling.NEAREST)
    sheet.alpha_composite(preview, (40, 62))

    legend = (
        ("contested", FRAME_COLORS[0]),
        ("Shabrat", FRAME_COLORS[2]),
        ("Party", FRAME_COLORS[4]),
        ("local forces", FRAME_COLORS[6]),
    )
    x = 46
    for label, color in legend:
        draw.rectangle((x, 600, x + 18, 618), fill=(*color, 255), outline=(232, 218, 176, 255))
        draw.text((x + 27, 603), label, fill=(213, 207, 188, 255))
        x += 205
    return sheet


def render_outputs() -> tuple[dict[str, Image.Image], tuple[int, int, int, int]]:
    province_to_color, land_colors = province_colors()
    state_sets = {state_id: state_provinces(state_id) for state_id in STATE_IDS}
    target_colors = {
        province_to_color[province]
        for provinces in state_sets.values()
        for province in provinces
        if province in province_to_color
    }

    provinces = Image.open(ROOT / "map" / "provinces.bmp").convert("RGB")
    min_x, min_y = provinces.width, provinces.height
    max_x = max_y = -1
    pixels = provinces.load()
    for y in range(provinces.height):
        for x in range(provinces.width):
            if pixels[x, y] in target_colors:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0:
        raise RuntimeError("STP states were not found in provinces.bmp")
    pad = 28
    box = (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(provinces.width, max_x + pad + 1),
        min(provinces.height, max_y + pad + 1),
    )

    cropped = provinces.crop(box)
    masks: dict[int, Image.Image] = {}
    cropped_pixels = list(cropped.get_flattened_data())
    for state_id, state_province_ids in state_sets.items():
        colors = {province_to_color[p] for p in state_province_ids if p in province_to_color}
        raw = Image.new("L", cropped.size, 0)
        raw.putdata([255 if pixel in colors else 0 for pixel in cropped_pixels])
        masks[state_id] = transform(raw, (0, 0, cropped.width, cropped.height))

    land_raw = Image.new("L", cropped.size, 0)
    land_raw.putdata([255 if pixel in land_colors else 0 for pixel in cropped_pixels])
    land_mask = transform(land_raw, (0, 0, cropped.width, cropped.height))
    background = Image.new("RGBA", (WIDTH, HEIGHT), (10, 11, 13, 255))
    background.alpha_composite(
        Image.composite(
            Image.new("RGBA", background.size, (40, 43, 44, 255)),
            Image.new("RGBA", background.size),
            land_mask,
        )
    )

    draw = ImageDraw.Draw(background)
    for y in range(0, HEIGHT, 8):
        draw.line((0, y, WIDTH, y), fill=(46, 49, 49, 255), width=1)
    for state_id in STATE_IDS:
        background.alpha_composite(
            Image.composite(
                Image.new("RGBA", background.size, (61, 63, 62, 255)),
                Image.new("RGBA", background.size),
                masks[state_id],
            )
        )

    all_mask = Image.new("L", background.size, 0)
    for mask in masks.values():
        all_mask = ImageChops.lighter(all_mask, mask)
    outer = all_mask.filter(ImageFilter.MaxFilter(5))
    border = Image.frombytes(
        "L",
        all_mask.size,
        bytes(max(a - b, 0) for a, b in zip(outer.tobytes(), all_mask.tobytes())),
    )
    background.alpha_composite(
        Image.composite(
            Image.new("RGBA", background.size, (193, 180, 145, 150)),
            Image.new("RGBA", background.size),
            border,
        )
    )

    outputs: dict[str, Image.Image] = {"STP_regions_map_background.png": background}
    for state_id in STATE_IDS:
        strip = Image.new("RGBA", (WIDTH * len(FRAME_COLORS), HEIGHT), (0, 0, 0, 0))
        for index, color in enumerate(FRAME_COLORS):
            strip.paste(state_overlay(masks[state_id], color), (WIDTH * index, 0))
        outputs[f"STP_regions_state_{state_id}.png"] = strip
    outputs["STP_regions_contact_sheet.png"] = contact_sheet(background, masks)
    return outputs, box


def validate_outputs(outputs: dict[str, Image.Image]) -> list[str]:
    issues: list[str] = []
    expected_filenames = set(outputs)
    for path in sorted(OUT.glob("STP_regions_*.png")):
        if path.is_file() and path.name not in expected_filenames:
            issues.append(f"unexpected generated STP regions-map image: {path.name}")
    for filename, expected in outputs.items():
        path = OUT / filename
        if not path.is_file():
            issues.append(f"missing generated STP regions-map image: {path.relative_to(ROOT)}")
            continue
        try:
            with Image.open(path) as source:
                actual = source.convert("RGBA")
        except OSError as exc:
            issues.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
            continue
        if actual.size != expected.size:
            issues.append(f"{path.relative_to(ROOT)} has size {actual.size}, expected {expected.size}")
            continue
        if ImageChops.difference(actual, expected.convert("RGBA")).getbbox() is not None:
            issues.append(f"{path.relative_to(ROOT)} pixels differ from deterministic render")
    return issues


def apply(outputs: dict[str, Image.Image]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    expected_filenames = set(outputs)
    for path in sorted(OUT.glob("STP_regions_*.png")):
        if path.is_file() and path.name not in expected_filenames:
            path.unlink()
    for filename, image in outputs.items():
        image.save(OUT / filename, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Battle for Stelander regional decision map.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="compare current PNGs with a deterministic render (default)")
    actions.add_argument("--apply", action="store_true", help="write deterministic regional-map PNGs")
    args = parser.parse_args()

    outputs, box = render_outputs()
    if args.apply:
        apply(outputs)
        print(f"Wrote STP regions map to {OUT.relative_to(ROOT)}; source crop={box}")
    issues = validate_outputs(outputs)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("STP regions-map validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
