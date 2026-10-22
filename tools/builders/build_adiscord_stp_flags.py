"""Export Stelander's political-route, island and dependent-government flags."""

from __future__ import annotations

import argparse
from io import BytesIO
from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}
SUBJECTS = ("NOD", "VAL", "BJK")
SOURCE_FLAGS = ("SLI", "SLI_mandate", "STS_hegemony")
ADMINISTRATION_FLAGS = ("NOD", "VAL", "YPR", "TFF")
# Great Stelander keeps the revolutionary banner until it receives its own source.
STP_IDENTITIES = ("STP_revolution_capital", "STP_great_stelander")
UNION_FLAG = "STS_stelander_union"
ALL_FLAGS = (
    *SOURCE_FLAGS,
    *STP_IDENTITIES,
    *(f"{tag}_STS_administration" for tag in ADMINISTRATION_FLAGS),
    "NKA_STS_administration",
    *(f"{tag}_STP_revolution" for tag in SUBJECTS),
    UNION_FLAG,
)


def stelander_union_flag():
    navy = (17, 38, 70, 255)
    ivory = (243, 237, 218, 255)
    gold = (216, 177, 84, 255)
    image = Image.new("RGBA", (820, 520), navy)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 160, 819, 359), fill=gold)
    draw.rectangle((0, 170, 819, 349), fill=ivory)
    draw.ellipse((280, 130, 540, 390), fill=navy, outline=gold, width=5)
    draw.polygon(
        [(410, 145), (436, 230), (518, 260), (436, 287),
         (410, 375), (384, 287), (302, 260), (384, 230)],
        fill=gold,
    )
    draw.line([(349, 295), (382, 260), (398, 275), (422, 242), (470, 296)],
              fill=navy, width=10)
    for side in (-1, 1):
        branch = []
        for angle in range(22, 153, 2):
            arc = radians(angle)
            branch.append((410 + side * 175 * sin(arc), 260 + 165 * cos(arc)))
        draw.line(branch, fill=gold, width=5)
        for angle in range(30, 150, 15):
            arc = radians(angle)
            x = 410 + side * 175 * sin(arc)
            y = 260 + 165 * cos(arc)
            for outward in (-1, 1):
                direction = radians(side * (angle - 90) + outward * 42)
                dx = 31 * sin(direction)
                dy = -31 * cos(direction)
                draw.polygon(
                    [(x, y), (x + dx * 0.45 - dy * 0.22, y + dy * 0.45 + dx * 0.22),
                     (x + dx, y + dy),
                     (x + dx * 0.45 + dy * 0.22, y + dy * 0.45 - dx * 0.22)],
                    fill=gold,
                )
    draw.line([(376, 410), (444, 410)], fill=gold, width=7)
    return image


def outputs(tags=None):
    selected = set(ALL_FLAGS if tags is None else tags)
    if UNION_FLAG in selected:
        source = stelander_union_flag()
        for folder, size in SIZES.items():
            buffer = BytesIO()
            source.resize(size, Image.Resampling.LANCZOS).save(buffer, format="TGA")
            yield ROOT / "gfx/flags" / folder / f"{UNION_FLAG}.tga", buffer.getvalue()
    for tag in ADMINISTRATION_FLAGS:
        cosmetic = f"{tag}_STS_administration"
        aliases = (cosmetic, "NKA_STS_administration") if tag == "NOD" else (cosmetic,)
        active = set(aliases) & selected
        if not active:
            continue
        source_path = ROOT / "tools/assets/source/stp_administration_flags" / f"{cosmetic}.png"
        with Image.open(source_path) as source:
            for folder, size in SIZES.items():
                buffer = BytesIO()
                source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
                    buffer, format="TGA"
                )
                for identity in aliases:
                    if identity in active:
                        yield ROOT / "gfx/flags" / folder / f"{identity}.tga", buffer.getvalue()
    for tag in SOURCE_FLAGS:
        if tag not in selected:
            continue
        with Image.open(ROOT / "tools/assets/source" / f"{tag}_flag.png") as source:
            for folder, size in SIZES.items():
                buffer = BytesIO()
                source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
                    buffer, format="TGA"
                )
                yield ROOT / "gfx/flags" / folder / f"{tag}.tga", buffer.getvalue()
    if selected.intersection(STP_IDENTITIES):
        source_path = ROOT / "tools/assets/source/STP_revolution_capital_flag.png"
        with Image.open(source_path) as source:
            for folder, size in SIZES.items():
                buffer = BytesIO()
                source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
                    buffer, format="TGA"
                )
                for cosmetic in STP_IDENTITIES:
                    if cosmetic in selected:
                        yield ROOT / "gfx/flags" / folder / f"{cosmetic}.tga", buffer.getvalue()
    for tag in SUBJECTS:
        if f"{tag}_STP_revolution" not in selected:
            continue
        for folder in SIZES:
            source = ROOT / "gfx/flags" / folder / "STP.tga"
            yield ROOT / "gfx/flags" / folder / f"{tag}_STP_revolution.tga", source.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--flags-only", nargs="+", choices=ALL_FLAGS)
    args = parser.parse_args()
    changed = []
    texture_count = 0
    for path, data in outputs(args.flags_only):
        texture_count += 1
        if not path.exists() or path.read_bytes() != data:
            changed.append(path)
            if args.apply:
                path.write_bytes(data)
    for path in changed:
        print(("Updated: " if args.apply else "Drift: ") + str(path.relative_to(ROOT)))
    if not changed:
        print(f"Stelander flags are current ({texture_count} textures).")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
