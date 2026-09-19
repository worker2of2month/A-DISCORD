"""Export Kefreyt administration flags from their approved source artwork."""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FLAGS = ("OCA", "OSF_VAL_commissariat")
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}


def outputs():
    for tag in FLAGS:
        with Image.open(ROOT / "tools/assets/source" / f"{tag}_flag.png") as source:
            for folder, size in SIZES.items():
                buffer = BytesIO()
                source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(buffer, format="TGA")
                yield ROOT / "gfx/flags" / folder / f"{tag}.tga", buffer.getvalue()


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
        print("Kefreyt administration flags are current (6 textures).")
    return 1 if changed and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
