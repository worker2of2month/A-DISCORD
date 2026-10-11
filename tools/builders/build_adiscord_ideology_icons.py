"""Export shared subideology emblems and their political-window size preview."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("tools/assets/source/ideology_icons")
TEXTURES = Path("gfx/interface/ideologies")
PREVIEW = Path("docs/development/previews/additional-ideology-icons.png")
LABELS = {
    "steland_liberationism": "Liberationism",
    "steland_military_directory": "Military directory",
    "tff_emergency_war_coordinator": "Frontier coordinator",
    "dorian_technocracy": "Dorian Worx",
}


def png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def outputs(root: Path = ROOT, only: set[str] | None = None):
    preview = Image.new("RGB", (220 * len(LABELS), 328), "#25242b")
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default(size=17)
    draw.text((20, 12), "Subideology emblems - 125 px / 70 px", font=font, fill="#e2d9c9")
    for index, (subtype, label) in enumerate(LABELS.items()):
        texture = TEXTURES / f"{subtype}_group.png"
        if only is not None and subtype not in only:
            # Partial exports show the currently installed versions of other emblems.
            with Image.open(root / texture) as current:
                icon = current.convert("RGBA")
        else:
            with Image.open(root / SOURCE / f"{subtype}.png") as source:
                if source.mode != "RGBA" or source.width != source.height:
                    raise ValueError(f"Expected a square RGBA master: {subtype}")
                if source.getchannel("A").getextrema() != (0, 255):
                    raise ValueError(f"Missing transparency or opaque emblem: {subtype}")
                icon = source.resize((256, 256), Image.Resampling.LANCZOS)
            yield texture, png_bytes(icon)
        for size, top in ((125, 49), (70, 190)):
            sample = icon.resize((size, size), Image.Resampling.LANCZOS)
            preview.paste(sample, (index * 220 + (220 - size) // 2, top), sample)
        draw.text((index * 220 + 110, 286), label, font=font, fill="#e2d9c9", anchor="mt")
    yield PREVIEW, png_bytes(preview)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--only", nargs="+", choices=tuple(LABELS),
                        help="Export selected emblems and preview other installed textures.")
    args = parser.parse_args()
    changed = []
    for relative, data in outputs(only=set(args.only) if args.only else None):
        path = ROOT / relative
        if not path.exists() or path.read_bytes() != data:
            changed.append(relative)
            if args.apply:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    for path in changed:
        print(("Updated: " if args.apply else "Drift: ") + path.as_posix())
    if not changed:
        print("Shared ideology textures and preview are current.")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
