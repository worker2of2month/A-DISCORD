"""Export the furnace administrations' heraldic flags and autonomy seal."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}
COLOURS = {
    "SFD": (53, 79, 67),
    "SCD": (124, 74, 37),
    "SMD": (32, 74, 99),
    "SOD": (70, 51, 81),
    "SDA": (126, 52, 46),
}
IVORY = (237, 227, 196)
GOLD = (216, 152, 55)
INK = (24, 31, 34)


def furnace(draw, x, y, scale):
    """An open furnace door, chimney and flame remain legible at flag size."""
    def box(coords, fill):
        draw.rectangle(tuple(int((x if i % 2 == 0 else y) + v * scale)
                             for i, v in enumerate(coords)), fill=fill)

    box((10, 0, 18, 11), IVORY)
    box((4, 9, 24, 31), IVORY)
    box((8, 14, 20, 31), INK)
    draw.polygon([(x + 14 * scale, y + 15 * scale),
                  (x + 19 * scale, y + 26 * scale),
                  (x + 14 * scale, y + 30 * scale),
                  (x + 10 * scale, y + 26 * scale)], fill=GOLD)
    box((0, 31, 28, 34), GOLD)


def flag(tag):
    image = Image.new("RGB", (820, 520), COLOURS[tag])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 819, 54), fill=IVORY)
    draw.rectangle((0, 465, 819, 519), fill=IVORY)
    draw.rectangle((0, 55, 279, 464), fill=INK)
    draw.rectangle((275, 55, 294, 464), fill=GOLD)
    furnace(draw, 40, 125, 7)
    if tag == "SFD":
        # A qanat arch over a water channel.
        draw.arc((425, 135, 690, 405), 180, 360, fill=IVORY, width=36)
        draw.rectangle((425, 268, 460, 355), fill=IVORY)
        draw.rectangle((655, 268, 690, 355), fill=IVORY)
        draw.line((400, 380, 715, 380), fill=GOLD, width=25)
        draw.line((470, 325, 645, 325), fill=GOLD, width=19)
    elif tag == "SCD":
        # Parallel rails and sleepers, extending beyond the old customs borders.
        for y in (160, 215, 270, 325, 380):
            draw.rectangle((440, y, 680, y + 17), fill=GOLD)
        draw.rectangle((475, 120, 501, 410), fill=IVORY)
        draw.rectangle((619, 120, 645, 410), fill=IVORY)
    elif tag == "SMD":
        draw.ellipse((540, 113, 580, 153), outline=IVORY, width=12)
        draw.line((560, 150, 560, 345), fill=IVORY, width=24)
        draw.line((490, 197, 630, 197), fill=IVORY, width=22)
        draw.arc((440, 160, 680, 375), 0, 180, fill=IVORY, width=24)
        draw.polygon(((431, 256), (469, 292), (431, 302)), fill=IVORY)
        draw.polygon(((689, 256), (651, 292), (689, 302)), fill=IVORY)
        draw.line((420, 411, 700, 411), fill=GOLD, width=19)
    elif tag == "SOD":
        draw.polygon(((560, 105), (655, 258), (465, 258)), fill=GOLD)
        draw.ellipse((461, 190, 659, 390), fill=GOLD)
        draw.polygon(((560, 144), (610, 260), (510, 260)), fill=INK)
        draw.ellipse((510, 227, 610, 337), fill=INK)
    else:
        # A causeway ties the inland dry river to the coastal cistern towns.
        draw.rectangle((420, 165, 700, 200), fill=IVORY)
        for x in (445, 545, 645):
            draw.rectangle((x, 190, x + 30, 320), fill=IVORY)
        draw.line(((410, 365), (455, 345), (505, 365), (555, 345),
                   (605, 365), (655, 345), (705, 365)), fill=GOLD, width=22)
    return image


def autonomy_icon():
    image = Image.new("RGBA", (280, 288))
    draw = ImageDraw.Draw(image)
    draw.polygon(((28, 18), (252, 18), (245, 200), (140, 275), (35, 200)),
                 fill=(20, 25, 27), outline=GOLD, width=12)
    draw.polygon(((43, 34), (237, 34), (231, 192), (140, 255), (49, 192)),
                 outline=(114, 91, 51), width=5)
    furnace(draw, 56, 50, 6)
    return image.resize((35, 36), Image.Resampling.LANCZOS)


def outputs():
    result = {}
    for tag in COLOURS:
        source = flag(tag)
        for folder, size in SIZES.items():
            buffer = BytesIO()
            source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(buffer, format="TGA")
            result[Path("gfx/flags") / folder / f"{tag}.tga"] = buffer.getvalue()
    buffer = BytesIO()
    autonomy_icon().save(buffer, format="PNG")
    result[Path("gfx/interface/autonomy/autonomy_SHL_furnace_administration_icon.png")] = buffer.getvalue()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = []
    for relative, data in outputs().items():
        path = ROOT / relative
        if not path.exists() or path.read_bytes() != data:
            changed.append(relative.as_posix())
            if args.apply:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    print(f"Furnace administration assets: {len(changed)} {'written' if args.apply else 'pending'}")
    for path in changed:
        print(path)
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
