"""Export Stelander's political-route, island and dependent-government flags."""

from __future__ import annotations

import argparse
from io import BytesIO
from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}
SOURCE_FLAGS = ("SLI", "STS_hegemony")
ADMINISTRATION_FLAGS = ("NOD", "VAL", "YPR", "TFF")
STP_IDENTITIES = ("STP_revolution_capital",)
IMPORTED_FLAGS = (
    "STP_great_stelander",
    "BJK_STP_revolution",
    "VAL_STP_revolution",
    "NOD_STP_revolution",
    "SLI_mandate",
)
UNION_FLAG = "STS_stelander_union"
ALL_FLAGS = (
    *SOURCE_FLAGS,
    *STP_IDENTITIES,
    *IMPORTED_FLAGS,
    *(f"{tag}_STS_administration" for tag in ADMINISTRATION_FLAGS),
    "NKA_STS_administration",
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


def encode_flag(source, size):
    buffer = BytesIO()
    source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
        buffer, format="TGA"
    )
    return buffer.getvalue()


def outputs(tags=None, imports=None):
    selected = set(ALL_FLAGS if tags is None else tags)
    imports = imports or {}
    for tag in IMPORTED_FLAGS:
        if tag not in selected:
            continue
        base = ROOT / "gfx/flags" / f"{tag}.tga"
        if tag in imports:
            with Image.open(imports[tag]) as source:
                base_data = encode_flag(source, SIZES[""])
        else:
            base_data = base.read_bytes()
        yield base, base_data
        # The runtime master keeps rebuilds independent of user-owned originals.
        with Image.open(BytesIO(base_data)) as source:
            for folder, size in SIZES.items():
                if folder:
                    yield ROOT / "gfx/flags" / folder / f"{tag}.tga", encode_flag(source, size)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--flags-only", nargs="+", choices=ALL_FLAGS)
    parser.add_argument("--import-flag", nargs=2, action="append", default=[], metavar=("TAG", "PATH"))
    args = parser.parse_args()
    imports = dict(args.import_flag)
    if len(imports) != len(args.import_flag):
        parser.error("Each imported flag must be supplied once.")
    for tag, path in imports.items():
        if tag not in IMPORTED_FLAGS or not Path(path).is_file():
            parser.error(f"Invalid flag import: {tag} {path}")
        if args.flags_only and tag not in args.flags_only:
            parser.error(f"Imported flag is outside --flags-only: {tag}")
    changed = []
    texture_count = 0
    planned = list(outputs(args.flags_only, imports))
    for path, data in planned:
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
