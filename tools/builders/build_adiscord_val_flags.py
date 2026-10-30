"""Export Kefreyt administration and Council flags from approved artwork."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FLAGS = ("OCA", "OSF_VAL_commissariat", "BJK_VAL_administration")
# Regional councils retain the heraldry of their parent administration.
FLAG_ALIASES = {
    "ECA": "NOD_VAL_administration",
    "DCA": "YPR",
}
IMPORTED_FLAGS = (
    "YPR_VAL_administration",
    "VAL_kefreyt_state",
    "VAL_valden_republic",
    "VAL_united_military_districts",
)
SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}


def encode_flag(source, size):
    buffer = BytesIO()
    source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
        buffer, format="TGA"
    )
    return buffer.getvalue()


def outputs(tags=None, imports=None):
    selected = set(tags or (*FLAGS, *FLAG_ALIASES, *IMPORTED_FLAGS))
    imports = imports or {}
    for tag in FLAGS:
        if tag not in selected:
            continue
        with Image.open(ROOT / "tools/assets/source" / f"{tag}_flag.png") as source:
            for folder, size in SIZES.items():
                yield ROOT / "gfx/flags" / folder / f"{tag}.tga", encode_flag(source, size)
    for tag, source_tag in FLAG_ALIASES.items():
        if tag not in selected:
            continue
        for folder in SIZES:
            source = ROOT / "gfx/flags" / folder / f"{source_tag}.tga"
            yield ROOT / "gfx/flags" / folder / f"{tag}.tga", source.read_bytes()
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
        # The runtime master makes later rebuilds independent of user-owned originals.
        with Image.open(BytesIO(base_data)) as source:
            for folder, size in SIZES.items():
                if folder:
                    yield ROOT / "gfx/flags" / folder / f"{tag}.tga", encode_flag(source, size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--flags-only", nargs="+", choices=(*FLAGS, *FLAG_ALIASES, *IMPORTED_FLAGS))
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
    planned = list(outputs(args.flags_only, imports))
    for path, data in planned:
        if not path.exists() or path.read_bytes() != data:
            changed.append(path)
            if args.apply:
                path.write_bytes(data)
    for path in changed:
        print(("Updated: " if args.apply else "Drift: ") + str(path.relative_to(ROOT)))
    if not changed:
        print(
            f"Kefreyt flags are current ({len(planned)} textures)."
        )
    return 1 if changed and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
