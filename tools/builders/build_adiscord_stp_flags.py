"""Export Stelander's political-route, island and dependent-government flags."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}
SUBJECTS = ("NOD", "VAL", "BJK")
SOURCE_FLAGS = ("SLI", "SLI_mandate", "STS_hegemony")
# Great Stelander keeps the revolutionary banner until it receives its own source.
STP_IDENTITIES = ("STP_revolution_capital", "STP_great_stelander")


def outputs():
    for tag in SOURCE_FLAGS:
        with Image.open(ROOT / "tools/assets/source" / f"{tag}_flag.png") as source:
            for folder, size in SIZES.items():
                buffer = BytesIO()
                source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
                    buffer, format="TGA"
                )
                yield ROOT / "gfx/flags" / folder / f"{tag}.tga", buffer.getvalue()
    source_path = ROOT / "tools/assets/source/STP_revolution_capital_flag.png"
    with Image.open(source_path) as source:
        for folder, size in SIZES.items():
            buffer = BytesIO()
            source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
                buffer, format="TGA"
            )
            for cosmetic in STP_IDENTITIES:
                yield ROOT / "gfx/flags" / folder / f"{cosmetic}.tga", buffer.getvalue()
    for tag in SUBJECTS:
        for folder in SIZES:
            source = ROOT / "gfx/flags" / folder / "STP.tga"
            yield ROOT / "gfx/flags" / folder / f"{tag}_STP_revolution.tga", source.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = []
    for path, data in outputs():
        if not path.exists() or path.read_bytes() != data:
            changed.append(path)
            if args.apply:
                path.write_bytes(data)
    for path in changed:
        print(("Updated: " if args.apply else "Drift: ") + str(path.relative_to(ROOT)))
    if not changed:
        print("Stelander flags are current (24 textures).")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
