"""Build Ivanov's shared glitch animation from the supplied Stelander portraits.

The supplied portraits are integrated as runtime PNGs; their originals stay
with the author outside the repository, so the runtime copies are the inputs.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import random

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
FRAMES = 52
FPS = 12
PORTRAITS = {
    "STP": Path("gfx/leaders/STP/portrait_STP_Petr_Ivanov.png"),
    "NOD": Path("gfx/leaders/NOD/portrait_NOD_STS_administrator.png"),
    "VAL": Path("gfx/leaders/VAL/portrait_VAL_STS_administrator.png"),
    "NKA": Path("gfx/leaders/NKA/portrait_STP_northern_administrator.png"),
}
ATLAS = Path("gfx/leaders/STP/ivanov_glitch_animation.dds")
PREVIEW = Path("docs/development/previews/ivanov-glitch.gif")


def animation_frames(portrait: Image.Image) -> list[Image.Image]:
    """Keep quiet intervals and the loop seam intact; damage stays in brief bands."""
    base = portrait.convert("RGBA")
    if base.size != (156, 210):
        raise ValueError(f"Expected a 156x210 portrait, got {base.size}")
    bursts = {10: 2, 11: 5, 12: 3, 26: 3, 27: 7, 28: 4, 29: 2,
              41: 2, 42: 6, 43: 3}
    frames = []
    for index in range(FRAMES):
        frame = base.copy()
        strength = bursts.get(index, 0)
        rng = random.Random(7100 + index)
        for _ in range(strength):
            top = rng.randrange(10, base.height - 12)
            height = rng.randrange(2, 11)
            band = base.crop((0, top, base.width, top + height))
            shift = rng.choice((-1, 1)) * rng.randrange(2, strength + 3)
            band = ImageChops.offset(band, shift, 0)
            red, green, blue, alpha = band.split()
            band = Image.merge("RGBA", (
                ImageChops.offset(red, 2, 0), green,
                ImageChops.offset(blue, -2, 0), alpha,
            ))
            frame.paste(band, (0, top))
        # The supplied silhouette must not acquire displaced opaque edge pixels.
        frame.putalpha(base.getchannel("A"))
        frames.append(frame)
    return frames


def outputs(root: Path = ROOT, preview: bool = False):
    for portrait in PORTRAITS.values():
        with Image.open(root / portrait) as image:
            if image.size != (156, 210):
                raise ValueError(f"Invalid portrait dimensions: {portrait.as_posix()}")
    with Image.open(root / PORTRAITS["STP"]) as portrait:
        frames = animation_frames(portrait)
    atlas = Image.new("RGBA", (156 * FRAMES, 210))
    for index, frame in enumerate(frames):
        atlas.paste(frame, (156 * index, 0))
    buffer = BytesIO()
    atlas.save(buffer, format="DDS")
    yield ATLAS, buffer.getvalue()
    if not preview:
        return
    buffer = BytesIO()
    # GIF timing is quantised to 10 ms; the native atlas still runs at exactly 12 fps.
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:],
                   duration=80, loop=0, disposal=2)
    yield PREVIEW, buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--preview", action="store_true", help="also write the review GIF")
    args = parser.parse_args()
    changed = []
    for relative, data in outputs(preview=args.preview):
        path = ROOT / relative
        if not path.exists() or path.read_bytes() != data:
            changed.append(relative)
            if args.apply:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    for path in changed:
        print(("Updated: " if args.apply else "Drift: ") + path.as_posix())
    if not changed:
        print("Stelander portraits and animation are current.")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
