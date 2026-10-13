"""Build Itora's political flags, the Marches Legion flag and the island-administration assets."""

from __future__ import annotations

import argparse
import io
import shutil
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/assets/source/autonomy_island_administration_source.png"
ICON = ROOT / "gfx/interface/autonomy/autonomy_island_administration_icon.png"
FLAG_SOURCE = ROOT / "tools/assets/source/country_flags"
FLAG_IDS = ("IVN", "IVN_etatism", "IVN_chauvinism", "IVC")
FLAG_SIZES = {"": (82, 52), "medium": (41, 26), "small": (10, 7)}
FLAG_PAIRS = tuple(
    (ROOT / directory / "IVN.tga", ROOT / directory / "IIA.tga")
    for directory in ("gfx/flags", "gfx/flags/medium", "gfx/flags/small")
)


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


def render_flags() -> dict[Path, bytes]:
    outputs = {}
    for flag_id in FLAG_IDS:
        with Image.open(FLAG_SOURCE / f"{flag_id}.png") as source:
            for folder, size in FLAG_SIZES.items():
                buffer = io.BytesIO()
                source.convert("RGBA").resize(size, Image.Resampling.LANCZOS).save(
                    buffer, format="TGA"
                )
                outputs[ROOT / "gfx/flags" / folder / f"{flag_id}.tga"] = buffer.getvalue()
    return outputs


def drift() -> list[str]:
    expected_icon = render_icon()
    problems = []
    if not ICON.is_file() or ICON.read_bytes() != expected_icon:
        problems.append(str(ICON.relative_to(ROOT)))
    flags = render_flags()
    for source, target in FLAG_PAIRS:
        flags[target] = flags[source]
    for target, expected in flags.items():
        if not target.is_file() or target.read_bytes() != expected:
            problems.append(str(target.relative_to(ROOT)))
    return problems


def apply() -> None:
    ICON.parent.mkdir(parents=True, exist_ok=True)
    ICON.write_bytes(render_icon())
    for path, data in render_flags().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for source, target in FLAG_PAIRS:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


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
    args = parser.parse_args()
    if args.apply:
        apply()
        print("Built Itora's political flags, island-administration icon and IIA flags.")
        return 0
    problems = drift()
    if problems:
        print("Island-administration asset drift: " + ", ".join(problems))
        return 1
    print("Itora's political flags and island-administration assets are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
