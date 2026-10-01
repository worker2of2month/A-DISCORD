"""Convert the supplied reservation illustration and build native terminal atlases."""

from __future__ import annotations

import argparse
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "gfx/interface/ADISCORD_western_continent"
ART_SOURCE = ROOT / "tools/assets/source/ADISCORD_reservation_reference.png"
# Whole DXT blocks keep stationary text identical across adjacent atlas frames.
FRAME_SIZE = (240, 512)
FRAME_COUNT = 17
TERMINAL_BACKGROUND = (8, 16, 24)
FONT_SOURCE = ROOT / "gfx/fonts/vt323_22.fnt"
FONT_TEXTURE = ROOT / "gfx/fonts/vt323_22.tga"
TERMINAL_MESSAGES = (
    ((8, 8), "> Receiving signal...", (119, 222, 113)),
    ((8, 70), "> Observation post: N-7.\n> Movement at forest edge.", (119, 222, 113)),
    ((8, 266), "! They can see us.\n! No response to our call.", (221, 84, 65)),
    ((8, 336), "! Keep your distance.\n! Do not cross the perimeter.", (221, 84, 65)),
)


def terminal_font() -> tuple[dict, int]:
    source = FONT_SOURCE.read_text(encoding="utf-8-sig")
    line_height = int(re.search(r"\blineHeight=(\d+)", source)[1])
    with Image.open(FONT_TEXTURE) as texture:
        alpha = texture.convert("RGBA").getchannel("A")
    glyphs = {}
    for line in source.splitlines():
        if not line.startswith("char id="):
            continue
        row = {key: int(value) for key, value in re.findall(r"(\w+)=(-?\d+)", line)}
        mask = alpha.crop(
            (row["x"], row["y"], row["x"] + row["width"], row["y"] + row["height"])
        )
        glyphs[chr(row["id"])] = (row, mask)
    return glyphs, line_height


def draw_terminal_text(frame, text, position, color, glyphs, line_height):
    left, top = position
    x, y = left, top
    for character in text:
        if character == "\n":
            x, y = left, y + line_height
            continue
        row, mask = glyphs[character]
        ink = Image.new("RGBA", mask.size, (*color, 255))
        ink.putalpha(mask)
        if x + row["xadvance"] > FRAME_SIZE[0] - 8 or y + line_height > FRAME_SIZE[1]:
            raise ValueError("terminal message exceeds its frame")
        frame.alpha_composite(ink, (x + row["xoffset"], y + row["yoffset"]))
        x += row["xadvance"]
    return x, y


def terminal_frames() -> list[Image.Image]:
    # Opaque frames carry the complete English display, including its backing.
    # No hidden text or reveal masks depend on the surrounding GUI texture.
    glyphs, line_height = terminal_font()
    frames = []
    for index in range(FRAME_COUNT):
        frame = Image.new("RGBA", FRAME_SIZE, (*TERMINAL_BACKGROUND, 255))
        cursor = (8, 8)
        for row, (position, text, color) in enumerate(TERMINAL_MESSAGES):
            step = index - row * 2
            if step >= 2:
                visible = text
            elif step == 1:
                visible = text[: (len(text) + 1) // 2]
            else:
                visible = ""
            if visible:
                cursor = draw_terminal_text(
                    frame, visible, position, color, glyphs, line_height
                )
        if index % 2 == 0:
            x, y = cursor
            ImageDraw.Draw(frame).rectangle(
                (x + 1, y + 7, x + 6, y + 19), fill=(119, 222, 113, 255)
            )
        frames.append(frame)
    return frames


def dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS", pixel_format="DXT5")
    return stream.getvalue()


def terminal_outputs() -> dict[Path, bytes]:
    atlas = Image.new(
        "RGBA",
        (FRAME_SIZE[0] * FRAME_COUNT, FRAME_SIZE[1]),
        (*TERMINAL_BACKGROUND, 255),
    )
    for index, frame in enumerate(terminal_frames()):
        atlas.paste(frame, (index * FRAME_SIZE[0], 0))
    return {OUTPUT / "reservation_terminal.dds": dds_bytes(atlas)}


def expected_outputs() -> dict[Path, bytes]:
    # Keep the complete supplied composition inside the native picture frame.
    artwork = Image.open(ART_SOURCE).convert("RGBA")
    artwork.thumbnail((520, 270), Image.Resampling.LANCZOS)
    wallpaper = Image.new("RGBA", (528, 278), (10, 15, 17, 255))
    wallpaper.alpha_composite(artwork, ((528 - artwork.width) // 2, (278 - artwork.height) // 2))
    ImageDraw.Draw(wallpaper).rectangle((2, 2, 525, 275), outline=(91, 101, 102, 255))
    outputs = {OUTPUT / "reservation_wallpaper.dds": dds_bytes(wallpaper)}
    outputs.update(terminal_outputs())
    for size in ("", "medium", "small"):
        folder = ROOT / "gfx/flags" / size
        outputs[folder / "RSV.tga"] = (folder / "EXZ.tga").read_bytes()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--terminal-only",
        action="store_true",
        help="check or rebuild only the English terminal animation",
    )
    args = parser.parse_args()
    outputs = terminal_outputs() if args.terminal_only else expected_outputs()
    stale = [path for path, data in outputs.items() if not path.exists() or path.read_bytes() != data]
    if args.apply:
        for path in stale:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(outputs[path])
        print(f"Western diplomacy assets: wrote {len(stale)} files.")
        return 0
    for path in stale:
        print(f"STALE: {path.relative_to(ROOT)}")
    return int(bool(stale))


if __name__ == "__main__":
    raise SystemExit(main())
