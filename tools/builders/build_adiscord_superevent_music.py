"""Build presentation OGG mirrors and silent music-channel carriers."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def build(root: Path, output: Path, *, silence_only: bool = False) -> list[Path]:
    source = (root / "sound/superevents_sound.asset").read_text(encoding="utf-8")
    tracks = re.findall(r'name = "(\w+)_sound"\s+file = "([^"]+)"', source)
    results = []

    def encode(name: str, inputs: list[str], filters: list[str]) -> None:
        target = output / f"{name}.ogg"
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
                "-c:a",
                "libvorbis",
                "-q:a",
                "6",
                str(target),
            ],
            check=True,
        )
        results.append(target)

    if not silence_only:
        for name, relative in tracks:
            encode(name, ["-i", str(root / "sound" / relative)], [])

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
    parser.add_argument("--silence-only", action="store_true", help="Build only the 60/120-second silent carriers")
    args = parser.parse_args()
    changed = []
    with tempfile.TemporaryDirectory(prefix="adiscord-superevent-") as directory:
        for generated in build(ROOT, Path(directory), silence_only=args.silence_only):
            target = ROOT / "music" / generated.name
            content = generated.read_bytes()
            if not target.exists() or target.read_bytes() != content:
                changed.append(target.name)
                if args.apply:
                    target.write_bytes(content)
    # Postwar songs play from focuses; presentation audio must not embed them.
    obsolete = ROOT / "music/ADISCORD_stp_civil_war_end_after_superevent.ogg"
    if not args.silence_only and obsolete.exists():
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
