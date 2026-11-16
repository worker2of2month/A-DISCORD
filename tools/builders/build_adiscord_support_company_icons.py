"""Build the support companies' division-designer, map and inline sprites."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageOps

from tools.lib.adiscord_ui_surfaces import dds_bytes


ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "tools/assets/source/support_companies"
REGISTRY = ROOT / "interface/ADISCORD_subuniticons.gfx"
BEGIN = "\t# BEGIN generated support company icons"
END = "\t# END generated support company icons"
LARGE = Path("gfx/interface/counters/divisions_large")
MAP = Path("gfx/interface/counters/divisions_small")
TEXT = Path("gfx/texticons")


def nato_badge(role, field, ink):
    badge = Image.new("RGBA", (42, 26), field)
    draw = ImageDraw.Draw(badge)
    draw.rectangle((0, 0, 41, 25), outline=ink, width=2)
    if role in ("assault_sapper", "armored_engineer"):
        if role == "armored_engineer":
            draw.rounded_rectangle((5, 4, 36, 21), radius=8, outline=ink, width=2)
        draw.line((12, 9, 29, 9), fill=ink, width=3)
        for x in (12, 20, 28):
            draw.line((x, 9, x, 17), fill=ink, width=2)
    elif role == "drone_recon":
        draw.line((2, 23, 39, 2), fill=ink, width=3)
    elif role == "ew":
        draw.line([(5, 5), (21, 16), (19, 8), (36, 20)], fill=ink, width=3)
    elif role == "decontamination":
        for x, y in ((17, 5), (11, 13), (23, 13)):
            draw.ellipse((x, y, x + 7, y + 7), outline=ink, width=2)
    elif role == "desert_support":
        draw.line((3, 17, 38, 17), fill=ink, width=2)
        draw.polygon([(20, 4), (25, 11), (24, 14), (17, 14), (16, 11)], fill=ink)
    elif role == "loitering_munition":
        draw.ellipse((11, 13, 19, 21), fill=ink)
        draw.line([(21, 9), (32, 5), (29, 15)], fill=ink, width=3)
    else:
        raise ValueError(f"No NATO symbol for {role}")
    return badge


def centered(image, size, limit):
    icon = ImageOps.contain(image, limit, Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", size)
    frame.paste(icon, ((size[0] - icon.width) // 2, (size[1] - icon.height) // 2))
    return frame


def draw_support_cross(frame):
    pen = ImageDraw.Draw(frame)
    for line in ((10, 10, 20, 10), (15, 5, 15, 15)):
        pen.line(line, fill="#203d79", width=4)
    for line in ((10, 9, 19, 9), (14, 5, 14, 14)):
        pen.line(line, fill="#8dafff", width=2)


def strip(first, second):
    if first.size != second.size:
        raise ValueError("Both frames must have the same dimensions")
    atlas = Image.new("RGBA", (first.width * 2, first.height))
    atlas.paste(first, (0, 0))
    atlas.paste(second, (first.width, 0))
    return atlas


def sprite(name, path, frames, inline=False):
    lines = ["\tspriteType = {", f'\t\tname = "{name}"', f'\t\ttexturefile = "{path.as_posix()}"']
    if inline:
        lines.append("\t\tlegacy_lazy_load = no")
    if frames > 1:
        lines.append(f"\t\tnoOfFrames = {frames}")
    return "\n".join([*lines, "\t}"])


def outputs():
    catalog = json.loads((SOURCES / "company_icon_prompts.json").read_text(encoding="utf-8"))
    generated = {}
    sprites = []
    for item in catalog["icons"]:
        unit = item["unit"]
        role = unit.removeprefix("ADISCORD_").removesuffix("_company")
        colour = item["colour"].split()[-1]
        with Image.open(SOURCES / item["file"]) as source:
            # Match the approved slot preview: faint alpha fringes do not set the scale.
            bounds = source.getchannel("A").point(lambda a: 255 if a >= 128 else 0).getbbox()
            if not bounds:
                raise ValueError(f"Empty silhouette: {unit}")
            art = source.crop(bounds)

        ink = "white" if ImageColor.getcolor(colour, "L") < 130 else "#171a17"
        badge = nato_badge(role, colour, ink)
        mono_badge = nato_badge(role, "white", "#151515")
        medium = Image.new("RGBA", (76, 42))
        # Reserve the left edge for the cross so it cannot cover a rotor or a tool.
        medium.paste(centered(art, (54, 42), (50, 34)), (21, 0))
        draw_support_cross(medium)
        small = centered(art, (30, 12), (28, 12))
        # White relief keeps interior details legible in a 12-pixel map counter.
        relief = ImageOps.autocontrast(ImageOps.grayscale(small), cutoff=2, mask=small.getchannel("A"))
        white = relief.point(lambda v: 140 + v * 115 // 255).convert("RGBA")
        white.putalpha(small.getchannel("A"))
        small_nato = centered(badge, (30, 12), (23, 12))
        variants = (
            (f"GFX_unit_{unit}_icon_medium", LARGE / f"{unit}_icon.dds",
             strip(medium, centered(badge, (76, 42), badge.size)), 2, False),
            (f"GFX_unit_{unit}_icon_medium_white", MAP / f"{unit}_icon.dds",
             strip(white, centered(mono_badge, (30, 12), (23, 12))), 2, False),
            (f"GFX_unit_{unit}_icon_small", TEXT / f"{unit}_icon_small.dds",
             strip(small, small_nato), 2, True),
            (f"GFX_nato_unit_{unit}_icon_small", TEXT / f"nato_{unit}_icon_small.dds",
             centered(badge, (25, 12), (23, 12)), 1, True),
        )
        for name, path, image, frames, inline in variants:
            generated[ROOT / path] = dds_bytes(image)
            sprites.append(sprite(name, path, frames, inline))

    original = REGISTRY.read_bytes()
    text = original.decode("utf-8").replace("\r\n", "\n")
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError(f"Expected a single support-company section in {REGISTRY.name}")
    before, rest = text.split(BEGIN)
    _, after = rest.split(END)
    content = before + BEGIN + "\n" + "\n\n".join(sprites) + "\n" + END + after
    if b"\r\n" in original:
        content = content.replace("\n", "\r\n")
    generated[REGISTRY] = content.encode("utf-8")
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check assets (default)")
    mode.add_argument("--apply", action="store_true", help="write changed assets")
    args = parser.parse_args()
    changed = 0
    for path, data in outputs().items():
        if path.is_file() and path.read_bytes() == data:
            continue
        changed += 1
        print(path.relative_to(ROOT))
        if args.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"Support company icon files {'updated' if args.apply else 'different'}: {changed}")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
