"""Export party subideology textures and a political-window size comparison."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("tools/assets/source/stp_party_ideologies")
TEXTURES = Path("gfx/interface/ideologies")
PREVIEW = Path("docs/development/previews/stp-party-ideology-icons.png")
LABELS = {
    "aristocratic_hedonism": "High Houses",
    "radical_hedonism": "Hedersett",
    "commercial_hedonism": "Merchants",
    "patronal_hedonism": "Regency",
    "steland_military_etatism": "Military",
    "steland_security_etatism": "Security",
}


def png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def outputs(root: Path = ROOT, *, include_preview: bool = False):
    if include_preview:
        preview = Image.new("RGB", (960, 328), "#25242b")
        draw = ImageDraw.Draw(preview)
        font = ImageFont.load_default(size=17)
        draw.text((20, 12), "Party subideologies - 125 px / 70 px", font=font, fill="#e2d9c9")
    for index, (subtype, label) in enumerate(LABELS.items()):
        texture = TEXTURES / f"{subtype}_group.png"
        if subtype == "aristocratic_hedonism":
            with Image.open(root / texture) as source:
                icon = source.convert("RGBA")
        else:
            with Image.open(root / SOURCE / f"{subtype}.png") as source:
                if source.mode != "RGBA" or source.width != source.height:
                    raise ValueError(f"Expected a square RGBA master: {subtype}")
                if source.getchannel("A").getextrema() != (0, 255):
                    raise ValueError(f"Missing transparency or opaque emblem: {subtype}")
                icon = source.resize((256, 256), Image.Resampling.LANCZOS)
            yield texture, png_bytes(icon)
        if include_preview:
            for size, top in ((125, 49), (70, 190)):
                sample = icon.resize((size, size), Image.Resampling.LANCZOS)
                preview.paste(sample, (index * 160 + (160 - size) // 2, top), sample)
            draw.text((index * 160 + 80, 286), label, font=font, fill="#e2d9c9", anchor="mt")
    if include_preview:
        yield PREVIEW, png_bytes(preview)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--preview", action="store_true",
        help="Include the temporary political-window size comparison.",
    )
    args = parser.parse_args()
    changed = []
    for relative, data in outputs(root=ROOT, include_preview=args.preview):
        path = ROOT / relative
        if not path.exists() or path.read_bytes() != data:
            changed.append(relative)
            if args.apply:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    for path in changed:
        print(("Updated: " if args.apply else "Drift: ") + path.as_posix())
    if not changed:
        print("Party ideology outputs are current.")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
