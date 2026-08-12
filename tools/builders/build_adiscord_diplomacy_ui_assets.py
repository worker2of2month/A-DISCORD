#!/usr/bin/env python3
"""Build the custom diplomacy portrait, party and flag overlays.

The source PNGs are the approved ImageGen masters with their chroma-key
backgrounds removed.  This builder owns the three exact-size DDS sprites used
by ``countrydiplomacyview.gui``.  Use ``--check`` before ``--apply``.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "gfx/interface/diplomacy/source"
OUTPUT_DIR = ROOT / "gfx/interface/diplomacy"

LEADER_SOURCE = SOURCE_DIR / "ADISCORD_diplomacy_leader_overlay_master.png"
PARTIES_SOURCE = SOURCE_DIR / "ADISCORD_diplomacy_parties_overlay_master.png"
FLAG_SOURCE = SOURCE_DIR / "ADISCORD_diplomacy_flag_overlay_master.png"

LEADER_OVERLAY = OUTPUT_DIR / "ADISCORD_diplomacy_leader_overlay.dds"
PARTIES_OVERLAY = OUTPUT_DIR / "ADISCORD_diplomacy_parties_overlay.dds"
FLAG_OVERLAY = OUTPUT_DIR / "ADISCORD_diplomacy_flag_overlay.dds"


def _resample_source(
    source: Path,
    crop: tuple[int, int, int, int],
    size: tuple[int, int],
) -> Image.Image:
    with Image.open(source) as image:
        rgba = image.convert("RGBA").crop(crop)
    return rgba.resize(size, Image.Resampling.LANCZOS)


def _leader_overlay() -> Image.Image:
    # The crop keeps the complete outer shell while dropping stray keyed pixels.
    overlay = _resample_source(LEADER_SOURCE, (24, 24, 942, 1612), (128, 216))
    draw = ImageDraw.Draw(overlay)
    # Guarantee that the engine-owned portrait remains entirely unobstructed.
    draw.rounded_rectangle((9, 8, 119, 174), radius=2, fill=(0, 0, 0, 0))
    return overlay


def _parties_overlay() -> Image.Image:
    overlay = _resample_source(PARTIES_SOURCE, (115, 90, 1578, 835), (124, 68))
    draw = ImageDraw.Draw(overlay)
    # The native political chart has a 60-pixel diameter and must not be masked.
    draw.ellipse((31, 3, 93, 65), fill=(0, 0, 0, 0))
    return overlay


def _flag_overlay() -> Image.Image:
    overlay = _resample_source(FLAG_SOURCE, (108, 105, 1465, 895), (126, 80))
    draw = ImageDraw.Draw(overlay)
    # Preserve the whole native medium-flag viewport beneath the custom corners.
    draw.rounded_rectangle((20, 12, 106, 68), radius=4, fill=(0, 0, 0, 0))
    return overlay


def _dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS", pixel_format="DXT5")
    return stream.getvalue()


def expected_outputs() -> dict[Path, bytes]:
    return {
        LEADER_OVERLAY: _dds_bytes(_leader_overlay()),
        PARTIES_OVERLAY: _dds_bytes(_parties_overlay()),
        FLAG_OVERLAY: _dds_bytes(_flag_overlay()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    outputs = expected_outputs()
    stale = [path for path, data in outputs.items() if not path.is_file() or path.read_bytes() != data]
    if not args.apply:
        if stale:
            for path in stale:
                print(f"STALE: {path.relative_to(ROOT)}")
            return 1
        print("Diplomacy UI overlay assets are current.")
        return 0

    for path, data in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"WROTE: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
