"""Draw the Conclave's survey map and place its furnace seals in the decision panel."""

import argparse
import io
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from tools.builders.build_adiscord_nam_basin_map import interior_anchor, read_geography
from tools.lib.paths import repository_root


ROOT = repository_root()
OUT = Path("gfx/interface/SHL_conclave")
GUI = Path("interface/ADISCORD_SHL.gui")
SIZE = (262, 284)
MAP_X, MAP_Y = 8, 84
SEAL = (34, 22)
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
SITES = tuple(range(287, 296))
DISTRICTS = (*SITES, 296, 699, 707, 730, 731, 732, 733)


def survey():
    provinces, colours, land = read_geography(DISTRICTS)
    y, x = np.where(np.isin(provinces, list(set.union(*colours.values()))))
    scale = max((x.max() - x.min() + 20) / SIZE[0], (y.max() - y.min() + 20) / SIZE[1])
    w, h = (round(length * scale) for length in SIZE)
    left, top = (int(x.min() + x.max() - w) // 2, int(y.min() + y.max() - h) // 2)
    crop = provinces[top:top + h, left:left + w]
    with Image.open(ROOT / "map/heightmap.bmp") as heights:
        height = heights.convert("L").crop((left, top, left + w, top + h))
        elevation = np.asarray(height.resize(SIZE, Image.Resampling.BILINEAR)).astype(float)
    dy, dx = np.gradient(elevation)
    relief = np.clip((elevation - 100) * .23 - 1.4 * dx - dy, -21, 30)
    palette = np.full((*crop.shape, 3), (22, 43, 45), dtype=np.uint8)
    palette[np.isin(crop, list(land))] = (48, 50, 44)
    masks = {}
    for state in DISTRICTS:
        inside = np.isin(crop, list(colours[state]))
        palette[inside] = (105, 83, 54) if state in SITES else (75, 70, 52)
        masks[state] = Image.fromarray(inside.astype(np.uint8) * 255).resize(SIZE, Image.Resampling.NEAREST)
    base = np.asarray(Image.fromarray(palette).resize(SIZE, Image.Resampling.NEAREST))
    chart = Image.fromarray(np.clip(base + relief[..., None], 0, 255).astype(np.uint8))
    for mask in masks.values():
        border = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
        chart.paste((158, 139, 95), mask=border)
    draw = ImageDraw.Draw(chart, "RGBA")
    for x in range(10, SIZE[0], 24):
        draw.line((x, 0, x, SIZE[1]), fill=(209, 194, 142, 25))
    for y in range(10, SIZE[1], 24):
        draw.line((0, y, SIZE[0], y), fill=(209, 194, 142, 25))
    draw.rectangle((0, 0, SIZE[0] - 1, SIZE[1] - 1), outline=(151, 129, 86))
    draw.polygon(((17, 9), (12, 24), (17, 20), (22, 24)), fill=(226, 203, 152))
    anchors = [interior_anchor(masks[state]) for state in SITES]
    # Devyatipechye is a single small district with two separate works.
    x, y = anchors[7]
    anchors[7] = (x - 5, y + 30)
    anchors.append((x + 16, y))
    for index, (cx, cy) in enumerate(anchors):
        if not (20 <= cx <= SIZE[0] - 21 and 16 <= cy <= SIZE[1] - 14):
            raise ValueError(f"Furnace {ROMAN[index]} extends beyond the survey")
        for px, py in anchors[:index]:
            if abs(px - cx) < 42 and abs(py - cy) < 30:
                raise ValueError(f"Furnace {ROMAN[index]} overlaps another seal")
    draw.line((*anchors[7], x, y), fill=(238, 210, 154))
    draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(246, 219, 162))
    districts = Image.new("RGBA", (SIZE[0] * len(anchors), SIZE[1]))
    for index, state in enumerate((*SITES, 294)):
        mask = masks[state]
        region = Image.new("RGBA", SIZE)
        region.paste((246, 173, 82, 75), mask=mask)
        edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask)
        region.paste((250, 205, 128, 230), mask=edge)
        districts.paste(region, (index * SIZE[0], 0))
    return chart, districts, anchors


def controls():
    board = Image.new("RGB", (454, 588), (26, 33, 31))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, 453, 587), outline=(113, 97, 71))
    draw.rectangle((270, 81, 449, 366), fill=(33, 40, 37), outline=(100, 90, 69))
    for y in (137, 207, 253):
        draw.line((278, y, 441, y), fill=(76, 79, 65))
    for y in (430, 499, 530):
        draw.line((7, y, 446, y), fill=(102, 93, 70))
    images = {"board": board}
    for name, size, fill in (("seal", SEAL, (39, 49, 45)), ("allocation", (106, 26), (40, 54, 50)),
                             ("dispatch", (142, 28), (68, 54, 40))):
        image = Image.new("RGBA", size)
        draw = ImageDraw.Draw(image)
        w, h = size
        draw.polygon(((4, 0), (w - 5, 0), (w - 1, 4), (w - 1, h - 5), (w - 5, h - 1),
                      (4, h - 1), (0, h - 5), (0, 4)), fill=fill, outline=(179, 148, 94))
        draw.line((5, 2, w - 6, 2), fill=(107, 101, 75))
        images[name] = image
    selected = Image.new("RGBA", (40, 28))
    draw = ImageDraw.Draw(selected)
    for x, sx in ((0, 1), (39, -1)):
        for y, sy in ((0, 1), (27, -1)):
            draw.line((x + 7 * sx, y, x, y, x, y + 6 * sy), fill=(255, 221, 130), width=2)
    images["selected"] = selected
    alert = Image.new("RGBA", (12, 13))
    draw = ImageDraw.Draw(alert)
    draw.polygon(((6, 0), (11, 11), (11, 12), (0, 12), (0, 11)), fill=(250, 175, 76), outline=(54, 35, 25))
    draw.line((6, 4, 6, 7), fill=(47, 32, 24), width=2)
    draw.point((6, 9), fill=(47, 32, 24))
    images["alert"] = alert
    return images


def map_widgets(anchors):
    widgets = []
    for i, (cx, cy) in enumerate(anchors, 1):
        x, y = MAP_X + cx - SEAL[0] // 2, MAP_Y + cy - SEAL[1] // 2
        name = f"SHL_furnace_{i}"
        widgets.append(f'''		buttonType = {{
			name = "{name}_button"
			position = {{ x = {x} y = {y} }}
			quadTextureSprite = "GFX_SHL_seal"
			buttonText = "{ROMAN[i - 1]}"
			buttonFont = "hoi_16mbs"
			clicksound = click_default
			pdx_tooltip = "{name}_tip"
		}}''')
        for layer, left, top in (("selected", x - 3, y - 3), ("alert", x + 26, y - 5)):
            widgets.append(f'''		iconType = {{
			name = "{name}_{layer}"
			position = {{ x = {left} y = {top} }}
			quadTextureSprite = "GFX_SHL_{layer}"
			alwaystransparent = yes
		}}''')
    return "\n".join(widgets)


def outputs():
    chart, districts, anchors = survey()
    result = {}
    for name, image in {"survey": chart, "districts": districts, **controls()}.items():
        stream = io.BytesIO()
        image.save(stream, "PNG")
        result[OUT / f"{name}.png"] = stream.getvalue()
    original = (ROOT / GUI).read_bytes()
    source = original.decode("utf-8").replace("\r\n", "\n")
    begin, end = "# BEGIN GENERATED FURNACE SEALS", "# END GENERATED FURNACE SEALS"
    source, count = re.subn(rf"(?<={begin}\n).*?(?=\t\t{end})", lambda _: map_widgets(anchors) + "\n",
                            source, flags=re.S)
    if count != 1:
        raise ValueError("Expected one furnace map section")
    if b"\r\n" in original:
        source = source.replace("\n", "\r\n")
    result[GUI] = source.encode("utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = 0
    for path, data in outputs().items():
        dest = ROOT / path
        if dest.is_file() and dest.read_bytes() == data:
            continue
        changed += 1
        print(path)
        if args.apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
    print(f"{changed} changed")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
