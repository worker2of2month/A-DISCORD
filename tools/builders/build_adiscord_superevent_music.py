"""Build presentation audio and silent radio carriers.

The Legion victory layers fire and Sophia's March of Strength (0-56 s),
a panicking crowd (4-8 s), a rifle volley (8-10 s), the commander's radio
address (10-18 s), then passing tanks and distant gunfire. Source metadata is
in tools/assets/source/superevents/IVN/audio_sources.json.
The Committee victory layers marching, cheering and celebratory fireworks
over The Ever Green Tree, with a continuous music level.
The Stalk portal uses the visual timeline for low mask impacts and portal hum.
RUS successor proclamations use separate 56-second music excerpts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]

RUS_EMPIRE_TRACKS = {
    "superevent_rus_restoration_sound": ("lustmord_black_star_excerpt.flac", 0.80),
    "superevent_rus_black_banner_sound": ("in_slaughter_natives_sacred_worms_excerpt.flac", 0.55),
}


def build(root: Path, output: Path, *, silence_only: bool = False, track: str | None = None) -> list[Path]:
    known_tracks = {
        "ADISCORD_rus_world_ends", "one_minute_of_silence", "two_minutes_of_silence",
        "superevent_itora_legion_victory_sound",
        "superevent_itora_committee_victory_sound",
        "superevent_itora_stalk_portal_sound",
        *RUS_EMPIRE_TRACKS,
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

    if not silence_only and track in (None, "ADISCORD_rus_world_ends"):
        source = root / "tools/assets/source/rus_crisis_audio/world_ends_excerpt.ogg"
        encode("ADISCORD_rus_world_ends", ["-i", str(source)], [], wav=True)

    if not silence_only and track in (None, "superevent_itora_legion_victory_sound"):
        source = root / "tools/assets/source/superevents/IVN"
        inputs = ["-stream_loop", "-1", "-i", str(source / "campfire.mp3")]
        for name in (
            "panic_crowd.mp3", "rifle.ogg", "march_of_strength_excerpt.ogg",
            "commander_radio.flac", "tank_medium.ogg", "tank_light.ogg",
            "distant_rifle.ogg", "distant_cannon.ogg",
        ):
            if name in ("tank_medium.ogg", "tank_light.ogg"):
                inputs.extend(["-stream_loop", "-1"])
            inputs.extend(["-i", str(source / name)])
        filters = (
            "[0:a]aresample=44100,aformat=channel_layouts=stereo,"
            "atrim=duration=56,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.08,afade=t=out:st=54:d=2,volume=1.15[fire];"
            "[1:a]atrim=start=1:duration=4,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.15,afade=t=out:st=3.7:d=0.3,"
            "volume=1.1,adelay=4000:all=1[crowd];"
            "[2:a]atrim=duration=1.2,asetpts=PTS-STARTPTS,"
            "aecho=0.8:0.7:140|310|510:0.6|0.45|0.3,apad,atrim=duration=2,"
            "afade=t=out:st=1.5:d=0.5,volume=0.85,adelay=8000:all=1[volley];"
            "[3:a]atrim=duration=56,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.05,afade=t=out:st=52:d=4,volume=0.75[music];"
            "[4:a]asetpts=PTS-STARTPTS,afade=t=in:d=0.02,"
            "afade=t=out:st=7.85:d=0.1,volume=0.9,adelay=10000:all=1[radio];"
            "[5:a]atrim=duration=8,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=2,afade=t=out:st=5:d=3,"
            "apulsator=hz=0.07:amount=0.65,volume=0.28,adelay=21000:all=1[tank1];"
            "[6:a]atrim=duration=8,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=2,afade=t=out:st=5:d=3,"
            "apulsator=hz=0.09:amount=0.65,volume=0.28,adelay=40000:all=1[tank2];"
            "[7:a]atrim=duration=1.2,asetpts=PTS-STARTPTS,lowpass=f=2200,"
            "aecho=0.8:0.7:170|390:0.4|0.2,apad,atrim=duration=2,"
            "afade=t=out:st=1.4:d=0.6,volume=0.25,asplit=3[s1][s2][s3];"
            "[s1]adelay=25000:all=1[shot1];"
            "[s2]adelay=34000:all=1[shot2];"
            "[s3]adelay=49000:all=1[shot3];"
            "[8:a]atrim=duration=3,asetpts=PTS-STARTPTS,lowpass=f=1800,"
            "afade=t=out:st=1.5:d=1.5,volume=0.22,adelay=31000:all=1[cannon];"
            "[fire][crowd][volley][music][radio][tank1][tank2]"
            "[shot1][shot2][shot3][cannon]"
            "amix=inputs=11:duration=longest:normalize=0,"
            "alimiter=limit=0.95:level=false:latency=true,aresample=44100,"
            "asetpts=N/SR/TB,apad=whole_len=2469600,atrim=end_sample=2469600[out]"
        )
        encode(
            "superevent_itora_legion_victory_sound", inputs,
            ["-filter_complex", filters, "-map", "[out]", "-t", "56"], wav=True,
        )

    if not silence_only and track in (None, "superevent_itora_committee_victory_sound"):
        source = root / "tools/assets/source/superevents/IVN"
        inputs = ["-i", str(source / "the_ever_green_tree_excerpt.flac")]
        inputs.extend(["-stream_loop", "-1", "-i", str(source / "committee_marching.mp3")])
        for name in ("committee_cheers.mp3", "committee_fireworks.mp3"):
            inputs.extend(["-i", str(source / name)])
        filters = (
            "[0:a]aresample=44100,aformat=channel_layouts=stereo,"
            "atrim=duration=56,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=1.5,afade=t=out:st=51:d=5,volume=0.55[music];"
            "[1:a]aresample=44100,asplit=2[m1][m2];"
            "[m1]atrim=duration=22,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=3,afade=t=out:st=18:d=4,volume=1.25,adelay=2000:all=1[march1];"
            "[m2]atrim=start=2:duration=17,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=3,afade=t=out:st=13:d=4,volume=1.0,adelay=35000:all=1[march2];"
            "[2:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[c1][c2];"
            "[c1]atrim=start=1:duration=10,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.7,afade=t=out:st=8:d=2,volume=2.0,adelay=7000:all=1[cheers1];"
            "[c2]atrim=start=9:duration=8,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.7,afade=t=out:st=6:d=2,volume=1.8,adelay=34000:all=1[cheers2];"
            "[3:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[f1][f2];"
            "[f1]atrim=start=10:duration=13,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.2,afade=t=out:st=11:d=2,volume=0.65,adelay=18000:all=1[fireworks1];"
            "[f2]atrim=start=40:duration=11,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.2,afade=t=out:st=8:d=3,volume=0.65,adelay=43000:all=1[fireworks2];"
            "[music][march1][march2][cheers1][cheers2][fireworks1][fireworks2]"
            "amix=inputs=7:duration=longest:normalize=0,"
            "alimiter=limit=0.95:level=false:latency=true,"
            "asetpts=N/SR/TB,apad=whole_len=2469600,atrim=end_sample=2469600[out]"
        )
        encode(
            "superevent_itora_committee_victory_sound", inputs,
            ["-filter_complex", filters, "-map", "[out]", "-t", "56"],
            wav=True,
        )

    if not silence_only and track in (None, "superevent_itora_stalk_portal_sound"):
        from tools.builders.build_adiscord_superevent_animation import FRAME_COUNT, FPS, MASK_SECONDS, PORTAL_SECONDS

        source = root / "tools/assets/source/superevents/IVN/light_in_realitys_shadow_excerpt.flac"
        duration = FRAME_COUNT / FPS
        inputs = [
            "-i", str(source),
            "-f", "lavfi", "-i",
            "aevalsrc=0.19*sin(2*PI*(62*t-12*t*t))*exp(-7*t)"
            "+0.055*sin(2*PI*93*t)*exp(-9*t):s=44100:d=1",
            "-f", "lavfi", "-i",
            "aevalsrc=0.085*sin(2*PI*52*t+0.5*sin(2*PI*3*t))"
            "+0.045*sin(2*PI*104*t)+0.025*sin(2*PI*157*t):s=44100:d=1",
        ]
        filters = [
            "[0:a]afade=t=in:d=2,afade=t=out:st=50:d=6,volume=0.85[music]",
            "[1:a]afade=t=in:d=0.012,afade=t=out:st=0.65:d=0.35,"
            "aformat=channel_layouts=stereo,"
            f"asplit={len(MASK_SECONDS)}" + "".join(f"[n{i}]" for i in range(len(MASK_SECONDS))),
            "[2:a]afade=t=in:d=0.04,afade=t=out:st=0.76:d=0.24,"
            "aformat=channel_layouts=stereo,"
            f"asplit={len(PORTAL_SECONDS)}" + "".join(f"[h{i}]" for i in range(len(PORTAL_SECONDS))),
        ]
        layers = ["[music]"]
        for prefix, seconds in (("n", MASK_SECONDS), ("h", PORTAL_SECONDS)):
            for index, second in enumerate(seconds):
                label = f"{prefix}{index}_delayed"
                filters.append(f"[{prefix}{index}]adelay={second * 1000}:all=1[{label}]")
                layers.append(f"[{label}]")
        # Additive mixing keeps the music gain unchanged, including during flashes.
        filters.append(
            "".join(layers)
            + f"amix=inputs={len(layers)}:duration=first:normalize=0,"
            + f"atrim=duration={duration},asetpts=N/SR/TB[out]"
        )
        encode(
            "superevent_itora_stalk_portal_sound", inputs,
            ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", str(duration)],
            wav=True,
        )

    if not silence_only:
        for name, (source_name, gain) in RUS_EMPIRE_TRACKS.items():
            if track is not None and track != name:
                continue
            source = root / "tools/assets/source/superevents/RUS" / source_name
            encode(
                name,
                ["-i", str(source)],
                ["-af", f"afade=t=in:d=2,afade=t=out:st=50:d=6,volume={gain}", "-t", "56"],
                wav=True,
            )

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
            if generated.name in {
                "superevent_itora_legion_victory_sound.wav",
                "superevent_itora_committee_victory_sound.wav",
                "superevent_itora_stalk_portal_sound.wav",
                "superevent_rus_restoration_sound.wav",
                "superevent_rus_black_banner_sound.wav",
            }:
                target_directory = "sound/superevents"
            else:
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
    return int(bool(not args.apply and changed))


if __name__ == "__main__":
    raise SystemExit(main())
