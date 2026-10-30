"""Build Itora's political flags, the Marches Legion flag and the island-administration assets."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/assets/source/autonomy_island_administration_source.png"
ICON = ROOT / "gfx/interface/autonomy/autonomy_island_administration_icon.png"
FLAG_SOURCE = ROOT / "tools/assets/source/country_flags"
FLAG_IDS = ("IVN", "IVN_etatism")
IMPORTED_FLAGS = ("IIA", "IVC", "IVN_chauvinism")
FLAG_SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}


def render_icon() -> bytes:
    with Image.open(SOURCE) as source:
        rgba = source.convert("RGBA")
        bbox = rgba.getbbox()
        if bbox is None:
            raise RuntimeError("island-administration source is fully transparent")
        cropped = rgba.crop(bbox)
        cropped.thumbnail((33, 34), Image.Resampling.LANCZOS)
        cropped = cropped.filter(
            ImageFilter.UnsharpMask(radius=0.7, percent=125, threshold=2)
        )
        canvas = Image.new("RGBA", (35, 36), (0, 0, 0, 0))
        canvas.alpha_composite(
            cropped,
            ((35 - cropped.width) // 2, (36 - cropped.height) // 2),
        )
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=False, compress_level=9)
        return output.getvalue()


def encode_flag(source: Image.Image, size: tuple[int, int]) -> bytes:
    buffer = io.BytesIO()
    source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
        buffer, format="TGA"
    )
    return buffer.getvalue()


def render_flags(imports: dict[str, Path] | None = None) -> dict[Path, bytes]:
    imports = imports or {}
    outputs = {}
    for flag_id in FLAG_IDS:
        with Image.open(FLAG_SOURCE / f"{flag_id}.png") as source:
            for folder, size in FLAG_SIZES.items():
                buffer = io.BytesIO()
                source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
                    buffer, format="TGA"
                )
                outputs[ROOT / "gfx/flags" / folder / f"{flag_id}.tga"] = buffer.getvalue()
    for flag_id in IMPORTED_FLAGS:
        base = ROOT / "gfx/flags" / f"{flag_id}.tga"
        if flag_id in imports:
            with Image.open(imports[flag_id]) as source:
                base_data = encode_flag(source, FLAG_SIZES[""])
        else:
            base_data = base.read_bytes()
        outputs[base] = base_data
        # The runtime master keeps rebuilds independent of user-owned originals.
        with Image.open(io.BytesIO(base_data)) as source:
            for folder, size in FLAG_SIZES.items():
                if folder:
                    outputs[ROOT / "gfx/flags" / folder / f"{flag_id}.tga"] = encode_flag(source, size)
    return outputs


def drift(imports: dict[str, Path] | None = None) -> list[str]:
    expected_icon = render_icon()
    problems = []
    if not ICON.is_file() or ICON.read_bytes() != expected_icon:
        problems.append(str(ICON.relative_to(ROOT)))
    flags = render_flags(imports)
    for target, expected in flags.items():
        if not target.is_file() or target.read_bytes() != expected:
            problems.append(str(target.relative_to(ROOT)))
    return problems


def apply(imports: dict[str, Path] | None = None) -> None:
    flags = render_flags(imports)
    ICON.parent.mkdir(parents=True, exist_ok=True)
    ICON.write_bytes(render_icon())
    for path, data in flags.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="validate generated runtime assets (default)",
    )
    actions.add_argument(
        "--apply", action="store_true", help="write the generated runtime assets"
    )
    parser.add_argument("--import-flag", nargs=2, action="append", default=[], metavar=("TAG", "PATH"))
    args = parser.parse_args()
    imports = {tag: Path(path) for tag, path in args.import_flag}
    if len(imports) != len(args.import_flag):
        parser.error("Each imported flag must be supplied once.")
    for tag, path in imports.items():
        if tag not in IMPORTED_FLAGS or not path.is_file():
            parser.error(f"Invalid flag import: {tag} {path}")
    if args.apply:
        apply(imports)
        print("Built Itora's political flags, island-administration icon and IIA flags.")
        return 0
    problems = drift(imports)
    if problems:
        print("Island-administration asset drift: " + ", ".join(problems))
        return 1
    print("Itora's political flags and island-administration assets are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
