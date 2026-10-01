"""Pack supplied infantry badges into native counter and text-icon DDS strips."""

import argparse
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
BASE_GAME = Path("Z:/SteamLibrary/steamapps/common/Hearts of Iron IV")
UNITS = {
    "territorial": "irregular_infantry",
    "assault_infantry": "assault_engineer",
    "marine_infantry": "marine",
    "hazard_infantry": "infantry",
}
SIZES = (
    ("gfx/interface/counters/divisions_large", "unit_", "_icon"),
    ("gfx/interface/counters/divisions_small", "onmap_unit_", "_icon"),
    ("gfx/texticons", "unit_", "_icon_small"),
)


def outputs():
    result = {}
    for unit, native in UNITS.items():
        with Image.open(SOURCE / f"ADISCORD_{unit}.png") as source:
            badge = source.convert("RGBA")
        # Ignore near-transparent extraction fringe only when measuring margins.
        # The original alpha is retained in the exported badge.
        bounds = badge.getchannel("A").point(lambda value: 255 if value > 32 else 0).getbbox()
        assert bounds is not None
        badge = badge.crop(bounds)
        for directory, prefix, suffix in SIZES:
            native_prefix = "" if directory == "gfx/texticons" and native == "assault_engineer" else prefix
            with Image.open(BASE_GAME / directory / f"{native_prefix}{native}{suffix}.dds") as source:
                strip = source.convert("RGBA")
            assert strip.width % 2 == 0
            width, height = strip.width // 2, strip.height
            icon = badge.copy()
            icon.thumbnail((width - 2, height - 2), Image.Resampling.LANCZOS)
            frame = Image.new("RGBA", (width, height))
            frame.paste(icon, ((width - icon.width) // 2, (height - icon.height) // 2))
            # Preserve the native NATO frame for the player's symbol preference.
            strip.paste(frame, (0, 0))
            buffer = io.BytesIO()
            strip.save(buffer, format="DDS")
            result[ROOT / directory / f"ADISCORD_{unit}{suffix}.dds"] = buffer.getvalue()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    generated = outputs()
    changed = [
        path for path, data in generated.items()
        if not path.exists() or path.read_bytes() != data
    ]
    if args.apply:
        for path in changed:
            path.write_bytes(generated[path])
    print(f"Infantry icon files {'updated' if args.apply else 'different'}: {len(changed)}")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
