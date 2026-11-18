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
    gauges = Image.new("RGBA", (450, 65))
    draw = ImageDraw.Draw(gauges)
    for left in (0, 225):
        draw.rectangle((left, 0, left + 220, 64), fill=(29, 37, 34), outline=(78, 77, 63))
        draw.line((left + 1, 0, left + 219, 0), fill=(146, 123, 82))
    images = {"board": board, "tension_cards": gauges}
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


def caravan_assets():
    """A contract row keeps each quotation aligned even when the buyer wraps."""
    header = Image.new("RGB", (454, 51), (29, 38, 35))
    ink = ImageDraw.Draw(header)
    ink.rectangle((0, 0, 453, 24), fill=(43, 54, 45))
    ink.line((0, 0, 453, 0), fill=(170, 139, 87))
    ink.line((0, 50, 453, 50), fill=(117, 103, 74))
    row = Image.new("RGB", (454, 34), (31, 38, 35))
    rule = ImageDraw.Draw(row)
    rule.line((0, 33, 453, 33), fill=(64, 71, 60))
    for x in (205, 297, 376):
        ink.line((x, 29, x, 47), fill=(69, 77, 65))
        rule.line((x, 3, x, 29), fill=(51, 60, 52))

    paper, edge, wax = (236, 211, 155), (80, 56, 40), (182, 68, 50)
    letter = Image.new("RGBA", (18, 16))
    pen = ImageDraw.Draw(letter)
    pen.rectangle((0, 3, 17, 13), fill=paper, outline=edge)
    pen.line(((1, 4), (8, 9), (16, 4)), fill=edge)
    pen.ellipse((7, 7, 10, 10), fill=wax)

    contract = Image.new("RGBA", (18, 16))
    pen = ImageDraw.Draw(contract)
    pen.polygon(((3, 0), (12, 0), (15, 3), (15, 13), (3, 13)), fill=paper, outline=edge)
    pen.line((5, 4, 11, 4), fill=edge)
    pen.line((5, 7, 10, 7), fill=edge)
    pen.polygon(((9, 11), (14, 11), (14, 15), (12, 14), (10, 15)), fill=wax)
    pen.ellipse((9, 8, 15, 13), fill=(175, 123, 53), outline=edge)
    pen.point((12, 10), fill=paper)

    arrears = Image.new("RGBA", (18, 16))
    pen = ImageDraw.Draw(arrears)
    pen.polygon(((0, 3), (14, 3), (14, 11), (0, 11)), fill=paper, outline=edge)
    pen.line((3, 6, 9, 6), fill=edge)
    pen.rectangle((8, 8, 17, 14), fill=wax, outline=edge)
    pen.line((10, 11, 15, 11), fill=(255, 231, 192), width=2)
    return {
        "caravan_header": header,
        "caravan_row": row,
        "caravan_offer_texticon": letter,
        "caravan_contract_texticon": contract,
        "caravan_arrears_texticon": arrears,
    }


def survey_symbols():
    """Keep the map badges and the inline legend on the same pixel grid."""
    edge = (36, 30, 27)
    amber = (239, 184, 87)
    light = (248, 223, 173)
    brick = (183, 112, 70)
    iron = (159, 174, 171)
    symbols = {}
    for name in ("ballot", "stopped", "occupied", "shortage", "wear"):
        icon = Image.new("RGBA", (18, 16))
        pen = ImageDraw.Draw(icon)
        if name == "ballot":
            pen.polygon(((4, 2), (13, 2), (11, 5), (9, 7), (9, 8), (13, 12), (13, 14),
                         (4, 14), (4, 12), (8, 8), (8, 7), (4, 3)), fill=edge, outline=iron)
            pen.polygon(((6, 4), (11, 4), (8, 7)), fill=amber)
            pen.polygon(((5, 12), (8, 9), (12, 12)), fill=amber)
            for y in (1, 14):
                pen.rectangle((2, y, 15, y + 1), fill=light)
        elif name == "stopped":
            pen.rectangle((3, 6, 15, 14), fill=iron, outline=edge)
            pen.rectangle((11, 1, 14, 7), fill=iron, outline=edge)
            pen.polygon(((5, 13), (5, 10), (7, 8), (11, 8), (13, 10), (13, 13)), fill=edge)
            pen.line((2, 14, 15, 2), fill=edge, width=4)
            pen.line((2, 14, 15, 2), fill=(241, 125, 98), width=2)
        elif name == "occupied":
            pen.line((4, 1, 4, 15), fill=light, width=2)
            pen.polygon(((5, 2), (16, 2), (13, 5), (16, 8), (5, 8)), fill=(211, 89, 75), outline=edge)
            pen.line((6, 3, 13, 3), fill=(251, 169, 121))
        elif name == "shortage":
            pen.polygon(((1, 5), (16, 5), (13, 11), (5, 11)), fill=edge, outline=light)
            pen.line((4, 5, 13, 5), fill=iron)
            pen.line((6, 8, 12, 8), fill=amber, width=2)
            for x in (5, 12):
                pen.ellipse((x, 12, x + 2, 14), fill=iron)
        elif name == "wear":
            pen.rectangle((1, 2, 16, 13), fill=brick, outline=light)
            pen.line((2, 7, 15, 7), fill=edge)
            pen.line((5, 3, 5, 6), fill=edge)
            pen.line((12, 8, 12, 12), fill=edge)
            pen.line(((11, 1), (8, 6), (10, 8), (6, 14)), fill=edge, width=3)
            pen.line(((11, 1), (8, 6), (10, 8), (6, 14)), fill=light)
        symbols[f"{name}_texticon"] = icon
    # Delivery block 4 reserves the heat for an order and has no warning badge.
    strip = Image.new("RGBA", (72, 16))
    for index, name in enumerate(("stopped", "occupied", "shortage")):
        strip.paste(symbols[f"{name}_texticon"], (index * 18, 0))
    symbols["delivery_alerts"] = strip
    return symbols


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
        for layer, sprite, left, top in (("selected", "selected", x - 3, y - 3),
                                        ("wear", "wear_texticon", x - 7, y - 12),
                                        ("interruption", "delivery_alerts", x + 24, y - 12)):
            widgets.append(f'''		iconType = {{
			name = "{name}_{layer}"
			position = {{ x = {left} y = {top} }}
			quadTextureSprite = "GFX_SHL_{sprite}"
			alwaystransparent = yes
		}}''')
    return "\n".join(widgets)


def outputs():
    chart, districts, anchors = survey()
    result = {}
    images = {"survey": chart, "districts": districts, **controls(), **survey_symbols(), **caravan_assets()}
    icon_sources = {
        "furnace": OUT / "brazier.png",
        "crest": OUT / "signet.png",
        "ore": OUT / "ore_cart.png",
        "ledger": OUT / "manual.png",
        "house_loyalty": Path("gfx/interface/bop/SHL_bop_crests.png"),
    }
    for name, source in icon_sources.items():
        with Image.open(ROOT / source) as original:
            art = original.convert("RGBA")
        art = art.crop(art.getchannel("A").getbbox())
        art.thumbnail((18, 16), Image.Resampling.LANCZOS)
        icon = Image.new("RGBA", (18, 16))
        icon.paste(art, ((18 - art.width) // 2, (16 - art.height) // 2))
        images[f"{name}_texticon"] = icon
    for name, image in images.items():
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
