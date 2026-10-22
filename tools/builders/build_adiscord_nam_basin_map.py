"""Render Svetlogorye's basin from native geography and bind its map markers."""

from __future__ import annotations

import argparse
import csv
import io
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from tools.lib.paths import repository_root


ROOT = repository_root()
OUT = Path("gfx/interface/NAM_basin")
WIDTH, HEIGHT = 436, 246
STATES = (67, 688, 689, 690, 719, 700)
GUI = Path("interface/ADISCORD_NAM_basin.gui")
GFX = Path("interface/ADISCORD_NAM_basin.gfx")
BEGIN = "# BEGIN GENERATED NAM BASIN MAP"
END = "# END GENERATED NAM BASIN MAP"
COLOURS = ((60, 150, 143, 68), (190, 78, 65, 115), (110, 116, 121, 110))


def pack_rgb(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.int32)
    return values[..., 0] * 65536 + values[..., 1] * 256 + values[..., 2]


def read_geography() -> tuple[np.ndarray, dict[int, set[int]], set[int]]:
    province_colours = {}
    land_colours = set()
    with (ROOT / "map/definition.csv").open(encoding="utf-8-sig") as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) < 5 or not row[0].isdigit():
                continue
            colour = int(row[1]) * 65536 + int(row[2]) * 256 + int(row[3])
            province_colours[int(row[0])] = colour
            if row[4] == "land":
                land_colours.add(colour)
    state_colours = {}
    for state in STATES:
        paths = sorted((ROOT / "history/states").glob(f"{state}-*.txt"))
        if len(paths) != 1:
            raise ValueError(f"Expected one state history for {state}")
        source = paths[0].read_text(encoding="utf-8-sig")
        match = re.search(r"provinces\s*=\s*\{([^}]+)\}", source)
        if not match:
            raise ValueError(f"Missing provinces in state {state}")
        state_colours[state] = {province_colours[int(p)] for p in re.findall(r"\d+", match[1])}
    with Image.open(ROOT / "map/provinces.bmp") as source:
        provinces = pack_rgb(np.asarray(source.convert("RGB")))
    return provinces, state_colours, land_colours


def interior_anchor(mask: Image.Image) -> tuple[int, int]:
    """Anchor tiny coastal states inside their actual outline, never at a sea centroid."""
    inner = mask
    while True:
        eroded = inner.filter(ImageFilter.MinFilter(3))
        if not eroded.getbbox():
            break
        inner = eroded
    y, x = np.where(np.asarray(inner) > 0)
    distance = (x - x.mean()) ** 2 + (y - y.mean()) ** 2
    index = int(np.argmin(distance))
    return int(x[index]), int(y[index])


def map_images() -> tuple[dict[str, Image.Image], dict[int, dict]]:
    provinces, state_colours, land_colours = read_geography()
    selected = np.isin(provinces, list(set.union(*state_colours.values())))
    y, x = np.where(selected)
    box = (max(0, int(x.min()) - 15), max(0, int(y.min()) - 12),
           min(provinces.shape[1], int(x.max()) + 16), min(provinces.shape[0], int(y.max()) + 13))
    # Fill the viewport with geographic context instead of drawing a false
    # coastline at a letterboxed crop edge.
    crop_width = box[2] - box[0]
    crop_height = box[3] - box[1]
    extra_width = max(0, math.ceil(crop_height * WIDTH / HEIGHT) - crop_width)
    extra_height = max(0, math.ceil(crop_width * HEIGHT / WIDTH) - crop_height)
    box = (box[0] - extra_width // 2, box[1] - extra_height // 2,
           box[2] + extra_width - extra_width // 2, box[3] + extra_height - extra_height // 2)
    crop = provinces[box[1]:box[3], box[0]:box[2]]
    size = (WIDTH, HEIGHT)

    def fitted(array: np.ndarray, resample=Image.Resampling.NEAREST) -> Image.Image:
        image = Image.fromarray(array).resize(size, resample)
        return image

    land = fitted(np.isin(crop, list(land_colours)).astype(np.uint8) * 255)
    with Image.open(ROOT / "map/heightmap.bmp") as source:
        elevation = fitted(np.asarray(source.convert("L").crop(box)), Image.Resampling.BILINEAR)
    heights = np.asarray(elevation).astype(float)
    dy, dx = np.gradient(heights)
    shade = np.clip((heights - 100) * 0.21 - dx * 1.2 - dy * 0.8, -12, 38)
    pixels = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    land_pixels = np.asarray(land) > 0
    for channel, base in enumerate((48, 57, 55)):
        pixels[..., channel] = np.where(land_pixels, np.clip(base + shade, 0, 255), (18, 35, 43)[channel])
    pixels[..., 3] = 255
    background = Image.fromarray(pixels)
    contours = np.asarray(elevation) // 8
    contour = np.zeros((HEIGHT, WIDTH), dtype=bool)
    contour[1:] |= contours[1:] != contours[:-1]
    contour[:, 1:] |= contours[:, 1:] != contours[:, :-1]
    contour &= land_pixels
    contour_mask = Image.fromarray(contour.astype(np.uint8) * 34)
    background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (191, 180, 142)),
                                              Image.new("RGBA", background.size), contour_mask))
    coastline = ImageChops.subtract(land.filter(ImageFilter.MaxFilter(5)), land)
    background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (68, 106, 111, 180)),
                                              Image.new("RGBA", background.size), coastline))
    grid = Image.new("RGBA", background.size)
    drawing = ImageDraw.Draw(grid)
    for gx in range(20, WIDTH, 40):
        drawing.line((gx, 0, gx, HEIGHT), fill=(183, 185, 157, 22))
    for gy in range(8, HEIGHT, 40):
        drawing.line((0, gy, WIDTH, gy), fill=(183, 185, 157, 22))
    background.alpha_composite(grid)
    geometry = {}
    images = {"map.png": background}
    for state in STATES:
        mask = fitted(np.isin(crop, list(state_colours[state])).astype(np.uint8) * 255)
        anchor = interior_anchor(mask)
        geometry[state] = {"mask": mask, "anchor": anchor}
        edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
        background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (166, 156, 113, 210)),
                                                  Image.new("RGBA", background.size), edge))
        strip = Image.new("RGBA", (WIDTH * 4, HEIGHT))
        for frame, colour in enumerate(COLOURS):
            overlay = Image.composite(Image.new("RGBA", mask.size, colour), Image.new("RGBA", mask.size), mask)
            strip.paste(overlay, (frame * WIDTH, 0))
        selection = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask.filter(ImageFilter.MinFilter(3)))
        overlay = Image.composite(Image.new("RGBA", mask.size, (241, 204, 120, 255)), Image.new("RGBA", mask.size), selection)
        strip.paste(overlay, (WIDTH * 3, 0))
        images[f"state_{state}.png"] = strip
    drawing = ImageDraw.Draw(background)
    drawing.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=(128, 119, 90))
    drawing.rectangle((3, 3, WIDTH - 4, HEIGHT - 4), outline=(56, 72, 72))
    drawing.line((WIDTH - 25, 22, WIDTH - 25, 62), fill=(203, 186, 139), width=1)
    drawing.line((WIDTH - 36, 42, WIDTH - 14, 42), fill=(203, 186, 139), width=1)
    drawing.polygon(((WIDTH - 25, 22), (WIDTH - 29, 34), (WIDTH - 21, 34)), fill=(203, 186, 139))
    return images, geometry


def ui_images() -> dict[str, Image.Image]:
    images = {}
    for name, fill, edge in (("panel.png", (23, 30, 32), (100, 94, 73)),
                            ("row.png", (29, 38, 39), (64, 77, 75))):
        tile = Image.new("RGBA", (64, 64), (*fill, 255))
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, 0, 63, 63), outline=(*edge, 255))
        draw.line((2, 2, 61, 2), fill=(72, 81, 76))
        images[name] = tile
    marker = Image.new("RGBA", (32, 32))
    draw = ImageDraw.Draw(marker)
    draw.ellipse((1, 1, 30, 30), fill=(19, 30, 32), outline=(219, 187, 121), width=2)
    draw.ellipse((5, 5, 26, 26), outline=(70, 104, 101))
    images["marker.png"] = marker
    for group in ("nam", "oil", "dist", "garr", "trade"):
        icon = Image.new("RGBA", (28, 28))
        draw = ImageDraw.Draw(icon)
        colour = (202, 181, 128, 255)
        if group == "nam":
            draw.rectangle((6, 4, 21, 23), outline=colour, width=2)
            draw.line((10, 9, 18, 9), fill=colour, width=2)
            draw.ellipse((11, 13, 18, 20), outline=colour, width=2)
        elif group == "oil":
            draw.polygon(((14, 3), (6, 16), (7, 22), (14, 25), (21, 22), (22, 16)), fill=colour)
            draw.line((11, 15, 10, 19, 13, 21), fill=(38, 59, 58), width=2)
        elif group == "dist":
            for x, y in ((4, 4), (16, 4), (4, 16), (16, 16)):
                draw.rectangle((x, y, x + 8, y + 8), outline=colour, width=2)
        elif group == "garr":
            draw.polygon(((5, 4), (23, 4), (22, 17), (14, 25), (6, 17)), outline=colour, width=2)
            draw.line((14, 8, 14, 19), fill=colour, width=2)
            draw.line((9, 12, 19, 12), fill=colour, width=2)
        else:
            draw.line((14, 7, 14, 24), fill=colour, width=2)
            draw.ellipse((11, 2, 17, 8), outline=colour, width=2)
            draw.arc((4, 7, 24, 26), 0, 180, fill=colour, width=2)
            draw.line((4, 14, 4, 19), fill=colour, width=2)
            draw.line((24, 14, 24, 19), fill=colour, width=2)
        images[f"support_{group}.png"] = icon
        images[f"texticon_{group}.png"] = icon.resize((20, 20), Image.Resampling.LANCZOS)
    return images


def gui_block(geometry: dict[int, dict]) -> str:
    lines = []
    for state in STATES:
        for frame, status in enumerate(("held", "occupied", "lost", "selected"), 1):
            lines.extend(("\t\ticonType = {", f'\t\t\tname = "NAM_bw_map_{state}_{status}"',
                          "\t\t\tposition = { x = 12 y = 66 }",
                          f'\t\t\tquadTextureSprite = "GFX_NAM_bw_state_{state}"',
                          f"\t\t\tframe = {frame}", "\t\t}", ""))
    for number, state in enumerate(STATES, 1):
        x, y = geometry[state]["anchor"]
        lines.extend(("\t\tbuttonType = {", f'\t\t\tname = "NAM_bw_select_{state}"',
                      f"\t\t\tposition = {{ x = {x - 4} y = {y + 50} }}",
                      '\t\t\tquadTextureSprite = "GFX_NAM_bw_marker"',
                      f'\t\t\tbuttonText = "{number:02d}"', '\t\t\tbuttonFont = "hoi_16mbs"',
                      "\t\t\tclicksound = click_default", f'\t\t\tpdx_tooltip = "NAM_bw_map_{state}_tt"',
                      "\t\t}", ""))
    return "\n".join(lines).rstrip()


def gfx_block(images: dict[str, Image.Image]) -> str:
    lines = []
    for filename in images:
        name = Path(filename).stem
        if name in ("panel", "row"):
            lines.extend(("\tcorneredTileSpriteType = {", f'\t\tname = "GFX_NAM_bw_{name}"',
                          "\t\tsize = { x = 64 y = 64 }", f'\t\ttextureFile = "{(OUT / filename).as_posix()}"',
                          "\t\tborderSize = { x = 3 y = 3 }", "\t\ttilingCenter = yes", "\t}", ""))
        else:
            sprite_name = (f"GFX_NAM_support_{name.removeprefix('texticon_')}_texticon"
                           if name.startswith("texticon_") else f"GFX_NAM_bw_{name}")
            lines.extend(("\tspriteType = {", f'\t\tname = "{sprite_name}"',
                          f'\t\ttexturefile = "{(OUT / filename).as_posix()}"',
                          f'\t\tnoOfFrames = {4 if name.startswith("state_") else 1}'))
            if name == "marker":
                lines.append('\t\teffectFile = "gfx/FX/buttonstate.lua"')
            if name.startswith("texticon_"):
                lines.append("\t\tlegacy_lazy_load = no")
            lines.extend(("\t}", ""))
    return "\n".join(lines).rstrip()


def replace_generated(path: Path, content: str, indent: str) -> bytes:
    source = (ROOT / path).read_text(encoding="utf-8")
    pattern = rf"(?m)^[\t ]*{BEGIN}.*?^[\t ]*{END}"
    replacement = f"{indent}{BEGIN}\n{content}\n{indent}{END}"
    updated, count = re.subn(pattern, lambda _: replacement, source, flags=re.S)
    if count != 1:
        raise ValueError(f"Expected one generated map section in {path}")
    return updated.encode("utf-8")


def build_outputs() -> tuple[dict[Path, bytes], dict[int, dict]]:
    images, geometry = map_images()
    images.update(ui_images())
    outputs = {}
    for filename, image in images.items():
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        outputs[OUT / filename] = buffer.getvalue()
    outputs[GUI] = replace_generated(GUI, gui_block(geometry), "\t\t")
    outputs[GFX] = replace_generated(GFX, gfx_block(images), "\t")
    return outputs, geometry


def check_outputs(outputs: dict[Path, bytes]) -> list[str]:
    return [path.as_posix() for path, expected in outputs.items()
            if not (ROOT / path).is_file() or (ROOT / path).read_bytes() != expected]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check generated assets (default)")
    mode.add_argument("--apply", action="store_true", help="write changed assets and map bindings")
    args = parser.parse_args()
    outputs, _ = build_outputs()
    changed = check_outputs(outputs)
    if args.apply:
        for relative in changed:
            path = ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(outputs[Path(relative)])
        print(f"NAM basin assets written: {len(changed)}")
    else:
        for relative in changed:
            print(f"Different or missing: {relative}")
    print(f"NAM basin assets checked: {len(outputs)}; differences: {len(check_outputs(outputs))}")
    return int(bool(check_outputs(outputs)))


if __name__ == "__main__":
    raise SystemExit(main())
