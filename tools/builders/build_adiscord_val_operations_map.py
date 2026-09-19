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
WIDTH, HEIGHT = 420, 340
STATE_IDS = (43, 44, 45, 88, 58, 59, 60, 61, 62, 63, 64, 65, 168)
VAL_STATES = (24, 42, 48, 54, 55, 56, 57)
STP_STATES = (1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88)
NOD_STATES = (10, 11, 12, 13, 17, 18, 30)
STATE_IDS = tuple(dict.fromkeys((*STATE_IDS, *VAL_STATES, *STP_STATES, *NOD_STATES)))
EXZ_STATES = (167, 169, 171, 180, 182, 185)

# Countries participating in the northern and Stelander campaigns; the last frame
# represents a controller from outside this theatre.
MAP_TAGS = ("VAL", "STP", "STS", "SRP", "NOD", "CIN", "OSF", "APH", "ERT", "NKA", "OCA", "YPR", "COF", "TFF")
FRAME_COUNT = len(MAP_TAGS) + 1


def country_colors() -> list[tuple[int, int, int]]:
    registry = "\n".join(p.read_text(encoding="utf-8-sig") for p in sorted((ROOT / "common/country_tags").glob("*.txt")))
    result = []
    for tag in MAP_TAGS:
        relative = re.search(rf'(?m)^\s*{tag}\s*=\s*"([^"]+)"', registry).group(1)
        source = (ROOT / "common" / relative).read_text(encoding="utf-8-sig")
        color = re.search(r"\bcolor\s*=\s*(?:rgb\s*)?\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}", source)
        if color is None:
            raise ValueError(f"No RGB map color for {tag}")
        result.append(tuple(map(int, color.groups())))
    return [*result, (103, 103, 107)]


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


def render_outputs() -> tuple[dict[str, Image.Image], tuple[int, int, int, int], tuple[int, int], tuple[int, int]]:
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
    for y in range(0, HEIGHT, 32):
        draw.line((0, y, WIDTH, y), fill=(34, 37, 38, 255), width=1)
    for x in range(0, WIDTH, 32):
        draw.line((x, 0, x, HEIGHT), fill=(34, 37, 38, 255), width=1)

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
    outputs = {"VAL_ops_map_background.png": background}

    palette = country_colors()
    for state in STATE_IDS:
        frames = Image.new("RGBA", (WIDTH * FRAME_COUNT, HEIGHT), (0, 0, 0, 0))
        mask = state_masks[state]
        expanded = mask.filter(ImageFilter.MaxFilter(3))
        rim = Image.frombytes("L", mask.size, bytes(max(a - b, 0) for a, b in zip(expanded.getdata(), mask.getdata())))
        for index, color in enumerate(palette):
            frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            frame.alpha_composite(Image.composite(Image.new("RGBA", frame.size, (*color, 255)), Image.new("RGBA", frame.size), mask))
            if index == MAP_TAGS.index("VAL"):
                frame.alpha_composite(Image.composite(Image.new("RGBA", frame.size, (235, 215, 160, 235)), Image.new("RGBA", frame.size), rim))
            frames.paste(frame, (WIDTH * index, 0))
        outputs[f"VAL_ops_state_{state}.png"] = frames
        # Mark divided control independently of the state's majority controller.
        stripes = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        stripe_draw = ImageDraw.Draw(stripes)
        for x in range(-HEIGHT, WIDTH, 8):
            stripe_draw.line((x, 0, x + HEIGHT, HEIGHT), fill=(255, 205, 90, 210), width=2)
        outputs[f"VAL_ops_contested_{state}.png"] = Image.composite(stripes, Image.new("RGBA", stripes.size), mask)


    return outputs, box, size, offset


def validate_outputs(outputs: dict[str, Image.Image]) -> list[str]:
    issues: list[str] = []
    expected_filenames = set(outputs)
    for path in sorted(OUT.glob("VAL_ops_*.png")):
        if path.is_file() and path.name not in expected_filenames:
            issues.append(f"unexpected generated operations-map image: {path.name}")
    for filename, expected in outputs.items():
        path = OUT / filename
        if not path.is_file():
            issues.append(f"missing generated operations-map image: {path.relative_to(ROOT)}")
            continue
        try:
            with Image.open(path) as source:
                actual = source.convert("RGBA")
        except OSError as exc:
            issues.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
            continue
        if actual.size != expected.size:
            issues.append(
                f"{path.relative_to(ROOT)} has size {actual.size}, expected {expected.size}"
            )
            continue
        if any(channel.getbbox() is not None for channel in ImageChops.difference(actual, expected.convert("RGBA")).split()):
            issues.append(f"{path.relative_to(ROOT)} pixels differ from deterministic render")
    return issues


def apply(outputs: dict[str, Image.Image]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    expected_filenames = set(outputs)
    for path in sorted(OUT.glob("VAL_ops_*.png")):
        if path.is_file() and path.name not in expected_filenames:
            path.unlink()
    for filename, image in outputs.items():
        image.save(OUT / filename, optimize=True)


def compact_overlays(outputs: dict[str, Image.Image]) -> tuple[dict[str, Image.Image], dict[int, tuple[int, int, int, int]]]:
    # Store only the region's occupied rectangle, not fifteen full-map canvases.
    compact = {"VAL_ops_map_background.png": outputs["VAL_ops_map_background.png"]}
    boxes = {}
    for state in STATE_IDS:
        source = outputs[f"VAL_ops_state_{state}.png"]
        box = source.crop((0, 0, WIDTH, HEIGHT)).getbbox()
        if box is None:
            raise ValueError(f"Empty map region {state}")
        boxes[state] = box
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        strip = Image.new("RGBA", (width * FRAME_COUNT, height))
        for frame in range(FRAME_COUNT):
            strip.paste(source.crop((left + frame * WIDTH, top, right + frame * WIDTH, bottom)), (frame * width, 0))
        compact[f"VAL_ops_state_{state}.png"] = strip
        compact[f"VAL_ops_contested_{state}.png"] = outputs[f"VAL_ops_contested_{state}.png"].crop(box)
    return compact, boxes


def interface_outputs(boxes: dict[int, tuple[int, int, int, int]]) -> dict[str, str]:
    header = "# Generated by tools/builders/build_adiscord_val_operations_map.py; do not edit.\n"
    gui = [header, 'guiTypes = {\n containerWindowType = {\n  name = "ADISCORD_VAL_operations_panel_window"\n  position = { x = 0 y = 0 }\n  size = { width = 460 height = 398 }\n  clipping = no\n', '  iconType = { name = "VAL_operations_map" position = { x = 20 y = 38 } quadTextureSprite = "GFX_VAL_ops_map_background" pdx_tooltip = "VAL_operations_map_tt" }\n']
    gfx = [header, 'spriteTypes = {\n spriteType = { name = "GFX_VAL_ops_map_background" texturefile = "gfx/interface/VAL_operations/VAL_ops_map_background.png" }\n']
    script = [header, 'scripted_gui = {\n ADISCORD_VAL_operations_panel = {\n  context_type = decision_category\n  window_name = "ADISCORD_VAL_operations_panel_window"\n  visible = { always = yes }\n  triggers = {\n']
    for state in STATE_IDS:
        left, top, _, _ = boxes[state]
        gfx.append(f' spriteType = {{ name = "GFX_VAL_ops_state_{state}" texturefile = "gfx/interface/VAL_operations/VAL_ops_state_{state}.png" noOfFrames = {FRAME_COUNT} }}\n')
        for frame, tag in enumerate((*MAP_TAGS, "other"), 1):
            name = f"VAL_ops_{state}_{tag.lower()}"
            gui.append(f'  iconType = {{ name = "{name}" position = {{ x = {20 + left} y = {38 + top} }} quadTextureSprite = "GFX_VAL_ops_state_{state}" frame = {frame} }}\n')
            condition = f"tag = {tag}" if tag != "other" else "NOT = { OR = { " + " ".join(f"tag = {t}" for t in MAP_TAGS) + " } }"
            script.append(f'   {name}_visible = {{ {state} = {{ controller = {{ {condition} }} }} }}\n')
        gfx.append(f' spriteType = {{ name = "GFX_VAL_ops_contested_{state}" texturefile = "gfx/interface/VAL_operations/VAL_ops_contested_{state}.png" }}\n')
        gui.append(f'  iconType = {{ name = "VAL_ops_{state}_contested" position = {{ x = {20 + left} y = {38 + top} }} quadTextureSprite = "GFX_VAL_ops_contested_{state}" }}\n')
        provinces = " ".join(f"NOT = {{ controls_province = {p} }}" for p in sorted(state_provinces(state)))
        script.append(f'   VAL_ops_{state}_contested_visible = {{ {state} = {{ controller = {{ tag = VAL OR = {{ {provinces} }} }} }} }}\n')
    gui.append(" }\n}\n")
    gfx.append("}\n")
    script.append("  }\n }\n}\n")
    return {"interface/ADISCORD_VAL_operations.gui": "".join(gui), "interface/ADISCORD_VAL_operations.gfx": "".join(gfx), "common/scripted_guis/ADISCORD_VAL_operations_scripted_gui.txt": "".join(script)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Kefreyt's local operations map.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="compare current PNGs with a deterministic render (default)")
    actions.add_argument("--apply", action="store_true", help="write the deterministic operations-map PNGs")
    args = parser.parse_args()
    outputs, box, size, offset = render_outputs()
    outputs, boxes = compact_overlays(outputs)
    interfaces = interface_outputs(boxes)
    if args.apply:
        for name, source in interfaces.items():
            (ROOT / name).write_text(source, encoding="utf-8")
        apply(outputs)
        print(f"Wrote operations map to {OUT.relative_to(ROOT)}; source crop={box}, resized={size}, offset={offset}")
    issues = validate_outputs(outputs)
    for name, source in interfaces.items():
        if not (ROOT / name).exists() or (ROOT / name).read_text(encoding="utf-8") != source:
            issues.append(f"generated interface differs: {name}")
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("VAL operations-map validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
