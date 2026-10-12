"""Build presentation OGG mirrors, the Khan finale WAV and silent carriers."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def build(root: Path, output: Path, *, silence_only: bool = False, track: str | None = None) -> list[Path]:
    source = (root / "sound/superevents_sound.asset").read_text(encoding="utf-8")
    tracks = re.findall(r'name = "(\w+)_sound"\s+file = "([^"]+)"', source)
    known_tracks = {name for name, _ in tracks} | {
        "ADISCORD_rus_world_ends", "one_minute_of_silence", "two_minutes_of_silence"
    }
    if track is not None and track not in known_tracks:
        raise ValueError(f"Unknown presentation track: {track}")
    results = []

    def encode(name: str, inputs: list[str], filters: list[str], *, wav: bool = False) -> None:
        if track is not None and name != track:
            return
        target = output / f"{name}.{'wav' if wav else 'ogg'}"
        codec = ["-c:a", "pcm_s16le", "-ac", "2"] if wav else ["-c:a", "libvorbis", "-q:a", "6"]
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                *inputs,
                *filters,
                "-map_metadata",
                "-1",
                "-fflags",
                "+bitexact",
                "-flags:a",
                "+bitexact",
                "-ar",
                "44100",
                *codec,
                str(target),
            ],
            check=True,
        )
        results.append(target)

    if not silence_only:
        for name, relative in tracks:
            encode(name, ["-i", str(root / "sound" / relative)], [])

        # Preserve the mastered excerpt byte-for-byte; GUI playback uses PCM.
        if track is None or track == "ADISCORD_rus_world_ends":
            source = root / "tools/assets/source/rus_crisis_audio/world_ends_excerpt.ogg"
            mirror = output / "ADISCORD_rus_world_ends.ogg"
            mirror.write_bytes(source.read_bytes())
            results.append(mirror)
            encode("ADISCORD_rus_world_ends", ["-i", str(source)], [], wav=True)

    for name, seconds in (("one_minute_of_silence", 60), ("two_minutes_of_silence", 120)):
        encode(
            name,
            ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"],
            ["-t", str(seconds)],
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--silence-only", action="store_true", help="Build only the 60/120-second silent carriers")
    selection.add_argument("--track", help="Build only one named presentation track")
    args = parser.parse_args()
    changed = []
    with tempfile.TemporaryDirectory(prefix="adiscord-superevent-") as directory:
        for generated in build(ROOT, Path(directory), silence_only=args.silence_only, track=args.track):
            target_directory = "sound/RUS" if generated.suffix == ".wav" else "music"
            target = ROOT / target_directory / generated.name
            content = generated.read_bytes()
            if not target.exists() or target.read_bytes() != content:
                changed.append(target.name)
                if args.apply:
                    target.write_bytes(content)
    # Postwar songs play from focuses; presentation audio must not embed them.
    obsolete = ROOT / "music/ADISCORD_stp_civil_war_end_after_superevent.ogg"
    if not args.silence_only and args.track is None and obsolete.exists():
        changed.append(f"remove {obsolete.name}")
        if args.apply:
            assert obsolete.resolve().parent == (ROOT / "music").resolve()
            obsolete.unlink()
    print(f"{'Updated' if args.apply else 'Different'}: {len(changed)} tracks")
    for name in changed:
        print(name)
    return int(bool(args.check and changed))


if __name__ == "__main__":
    raise SystemExit(main())
