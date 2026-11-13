"""Export the Stalk portal sequence from externally maintained artwork and video."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image

from tools.lib.adiscord_ui_surfaces import apply_or_check
from tools.lib.paths import repository_root
from tools.lib.superevent_art import ARTWORK_BOX, apply_template


ROOT = repository_root()
OUTPUT = Path("gfx/interface/superevents/IVN")
FRAME_COUNT = 56
FPS = 1
PORTAL_SECONDS = (16, 44)
MASK_SECONDS = (5, 12, 21, 31, 39, 50)
MASK_SOURCE_SECONDS = (0.5, 2.5, 4.5, 8.5, 10.5, 14.5)
# Narrow strips keep every native horizontal frame sheet below 4096 pixels.
STRIP_WIDTHS = (70,) * 12 + (68,)
VIEWPORT = (48, 82, 908, 510)


def timeline() -> tuple[str, ...]:
    frames = [f"painting_{min(second * 8 // FRAME_COUNT, 7)}" for second in range(FRAME_COUNT)]
    for second in PORTAL_SECONDS:
        frames[second] = "portal"
    for index, second in enumerate(MASK_SECONDS):
        frames[second] = f"mask_{index}"
    return tuple(frames)


def ffmpeg(*arguments: str) -> None:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg is required")
    subprocess.run(
        [executable, "-hide_banner", "-loglevel", "error", "-y", *arguments],
        check=True,
    )


def build_outputs(portal: Path, background: Path, masks: Path, preview: Path | None = None, paintings: list[Path] | None = None) -> dict[Path, bytes]:
    if paintings is None:
        manifest = json.loads((ROOT / "tools/assets/source/superevents/IVN/portal_art_sources.json").read_text(encoding="utf-8"))
        paintings = [Path.home() / ".codex/generated_images" / entry["generated_file"] for entry in manifest["paintings"]]
    if len(paintings) != 8:
        raise ValueError("Exactly eight expanded paintings are required")
    for source in (portal, background, masks):
        if not source.is_file():
            raise FileNotFoundError(source)
    with tempfile.TemporaryDirectory(prefix="adiscord-portal-") as folder:
        work = Path(folder)
        for index, painting in enumerate(paintings):
            ffmpeg(
                "-i", str(painting), "-vf", "scale=908:510:flags=lanczos,format=rgb24",
                "-frames:v", "1", str(work / f"painting_{index}.png"),
            )
        black = work / "black.png"
        ffmpeg("-i", str(background), "-vf", "crop=908:510:48:82,format=rgb24", "-frames:v", "1", str(black))
        portal_frame = work / "portal.png"
        ffmpeg(
            "-i", str(portal), "-f", "lavfi", "-i", "color=black:s=908x510",
            "-filter_complex", "[0:v]crop=908:510:48:82[p];[1:v][p]overlay=shortest=1:format=auto,format=rgb24[out]",
            "-map", "[out]", "-frames:v", "1", str(portal_frame),
        )
        for index, second in enumerate(MASK_SOURCE_SECONDS):
            ffmpeg(
                "-i", str(black), "-ss", str(second), "-i", str(masks),
                "-filter_complex",
                "[1:v]scale=514:490:flags=lanczos,setsar=1,format=rgba,colorkey=0x080808:0.045:0.07[m];"
                "[0:v][m]overlay=197:10:shortest=1:format=auto,format=rgb24[out]",
                "-map", "[out]", "-frames:v", "1", str(work / f"mask_{index}.png"),
            )
        # Grade each source frame once before it is reused in the native strips.
        template = ROOT / "tools/assets/source/Super_event_bg.psd"
        for name in [*(f"painting_{i}" for i in range(8)), "portal", *(f"mask_{i}" for i in range(6))]:
            path = work / f"{name}.png"
            with Image.open(path) as image:
                graded = apply_template(image, template).crop(ARTWORK_BOX).convert("RGB")
            graded.save(path)
        sequence = timeline()
        for index, name in enumerate(sequence):
            shutil.copyfile(work / f"{name}.png", work / f"frame_{index:02d}.png")
        outputs = {}
        offset = 0
        for index, width in enumerate(STRIP_WIDTHS):
            atlas = work / f"strip_{index}.png"
            ffmpeg(
                "-framerate", str(FPS), "-i", str(work / "frame_%02d.png"),
                "-vf", f"crop={width}:510:{offset}:0,tile={FRAME_COUNT}x1", "-frames:v", "1", str(atlas),
            )
            with Image.open(atlas) as pixels:
                encoded = BytesIO()
                pixels.convert("RGBA").save(encoded, format="DDS")
            outputs[ROOT / OUTPUT / f"superevent_itora_stalk_portal_strip_{index}.dds"] = encoded.getvalue()
            offset += width
        backdrop = work / "background.png"
        ffmpeg(
            "-i", str(work / "painting_0.png"), "-vf", "format=rgba,pad=1001:639:48:82:color=black@0",
            "-frames:v", "1", str(backdrop),
        )
        outputs[ROOT / OUTPUT / "superevent_itora_stalk_portal_background.png"] = backdrop.read_bytes()
        if preview is not None:
            preview.parent.mkdir(parents=True, exist_ok=True)
            ffmpeg(
                "-framerate", str(FPS), "-i", str(work / "frame_%02d.png"),
                "-filter_complex",
                "[0:v]format=rgba,pad=1001:639:48:82:color=black@0,split[a][b];"
                "[a]palettegen=reserve_transparent=1[p];[b][p]paletteuse=dither=none",
                "-loop", "0", str(preview),
            )
        return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    desktop = Path.home() / "Desktop"
    parser.add_argument("--portal", type=Path, default=desktop / "1.png")
    parser.add_argument("--background", type=Path, default=desktop / "2.png")
    parser.add_argument("--masks", type=Path, default=desktop / "iRVtBI1ebR3cyPGW.mp4")
    parser.add_argument("--paintings", type=Path, nargs=8, help="Eight expanded artworks in playback order")
    parser.add_argument("--preview", type=Path, help="Optional GIF outside the mod; never an automatic source copy")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.preview is not None and args.preview.resolve().is_relative_to(ROOT.resolve()):
        parser.error("the optional GIF preview must be outside the mod")
    outputs = build_outputs(args.portal, args.background, args.masks, args.preview, args.paintings)
    return apply_or_check(outputs, args.apply, "Stalk portal animation")


if __name__ == "__main__":
    raise SystemExit(main())
