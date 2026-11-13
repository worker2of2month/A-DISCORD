"""Build presentation audio and silent radio carriers.

The Legion victory layers fire and Sophia's March of Strength (0-56 s),
a panicking crowd (4-8 s), a rifle volley (8-10 s), the commander's radio
address (10-18 s), then passing tanks and distant gunfire. Source metadata is
in tools/assets/source/superevents/IVN/audio_sources.json.
The Committee victory layers marching, cheering and celebratory fireworks
over The Ever Green Tree, with a continuous music level.
The Stalk portal uses the visual timeline for low mask impacts and portal hum.
RUS successor proclamations use separate 56-second music excerpts.
The Stelander Union proclamation layers a parade and celebrations over Svendsen.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]

RUS_EMPIRE_TRACKS = {
    "superevent_rus_restoration_sound": ("kloob_deep_introspection_excerpt.flac", 0.85),
    "superevent_rus_black_banner_sound": ("in_slaughter_natives_sacred_worms_excerpt.flac", 0.55),
}

STP_POLICY_TRACKS = {
    "superevent_stelander_sotnikov_directory_sound": "phragments_the_return_excerpt.flac",
    "superevent_stelander_sotnikov_charter_sound": "danny_norbury_light_in_august_excerpt.flac",
    "superevent_stelander_tikhoreva_sound": "m_ostermeier_rafters_excerpt.flac",
    "superevent_stelander_party_victory_staff_sound": "phragments_all_towers_must_fall_excerpt.flac",
    "superevent_stelander_party_victory_wallets_sound": "trigg_gusset_vanishing_gold_excerpt.flac",
    "superevent_stelander_party_victory_regent_sound": "peter_bjargo_to_replace_my_sadness_excerpt.flac",
}

STP_FESTIVAL_TRACK = "superevent_stelander_party_victory_festival_sound"
STP_HOUSES_TRACK = "superevent_stelander_party_victory_houses_sound"

WEST_POLICY_TRACKS = {
    "superevent_west_world_empire_sound": "arcana_opening_of_the_wound_excerpt.flac",
}

SOUTH_POLICY_TRACKS = {
    "superevent_south_houses_sound": "arcana_le_serpent_rouge_excerpt.flac",
    "superevent_south_free_islands_sound": "sophie_hutchings_by_night_excerpt.flac",
    "superevent_south_war_sound": "phragments_new_kings_excerpt.flac",
}

VAL_POLICY_TRACKS = {
    "superevent_val_council_proclamation_sound": "les_fragments_de_la_nuit_entre_ciel_et_fer_excerpt.flac",
}


@dataclass(frozen=True)
class PolicyCue:
    source: str
    start: float
    offset: float
    duration: float
    gain: float
    fade: float = 0.4
    peak_limit: float = 0.16


STP_POLICY_CUES = {
    "superevent_stelander_party_victory_regent_sound": (
        PolicyCue("STP/sfx_winter_wind.flac", 0, 0, 56, 0.1, 4.0),
        PolicyCue("STP/sfx_paper_slide.flac", 6, 0, 1.09, 0.35, 0.03),
        PolicyCue("STP/sfx_pen_writing.flac", 8, 10, 4, 4.0, 0.4),
        PolicyCue("STP/sfx_vintage_camera.flac", 14, 0, 1.15, 0.28, 0.02),
        PolicyCue("STP/renner_address.flac", 18, 0, 14.63, 1.0, 0.02, 0.75),
        PolicyCue("STP/sfx_paper_slide.flac", 34, 0, 1.09, 0.25, 0.03),
        PolicyCue("STP/sfx_vintage_camera.flac", 36, 0, 1.15, 0.24, 0.02),
        PolicyCue("STP/sfx_vintage_camera.flac", 38, 0, 1.15, 0.18, 0.02),
    ),
    "superevent_stelander_party_victory_wallets_sound": (
        PolicyCue("STP/sfx_ship_engine.flac", 2, 0, 17, 0.1, 2.0),
        PolicyCue("STP/sfx_distant_ship_horn.flac", 2, 1.5, 7, 0.4, 0.8),
        PolicyCue("STP/sfx_old_typewriter.flac", 10, 3, 5, 0.22, 0.25),
        PolicyCue("STP/sfx_paper_slide.flac", 16, 0, 1.09, 0.5, 0.03),
        PolicyCue("STP/sfx_vintage_camera.flac", 17.5, 0, 1.15, 0.4, 0.02),
        PolicyCue("STP/sfx_vintage_camera.flac", 19, 0, 1.15, 0.32, 0.02),
        PolicyCue("STP/lanskoy_address.flac", 21, 0, 9.58, 1.0, 0.02, 0.75),
        PolicyCue("STP/sfx_small_applause.flac", 32, 3, 6, 0.7, 0.8),
        PolicyCue("STP/sfx_cash_register.flac", 40, 0, 2.19, 0.35, 0.03),
        PolicyCue("STP/sfx_ship_engine.flac", 42, 0, 14, 0.08, 3.0),
        PolicyCue("STP/sfx_old_typewriter.flac", 44, 11, 4, 0.14, 0.3),
        PolicyCue("STP/sfx_distant_ship_horn.flac", 49, 10, 6, 0.22, 1.0),
    ),
    "superevent_stelander_party_victory_staff_sound": (
        PolicyCue("IVN/committee_marching.mp3", 1, 0, 14, 0.7, 0.2),
        PolicyCue("IVN/tank_medium.ogg", 5, 0, 14, 0.14, 3.0),
        PolicyCue("STP/sfx_radio_crackle.flac", 20, 2, 1, 0.15, 0.15),
        PolicyCue("STP/staff_broadcast.flac", 21, 0, 11.06, 1.0, 0.02, 0.75),
        PolicyCue("IVN/tank_light.ogg", 39, 0, 10, 0.07, 3.0),
        PolicyCue("STP/sfx_guard_steps.flac", 43, 1, 7, 0.45, 0.5),
        PolicyCue("STP/sfx_rifle_cocking.flac", 50.5, 2.45, 0.9, 0.65, 0.03),
    ),
    "superevent_stelander_sotnikov_directory_sound": (
        PolicyCue("IVN/committee_marching.mp3", 4, 0, 8, 0.5, 1.2),
        PolicyCue("STP/sfx_radio_crackle.flac", 15, 1, 2, 0.55, 0.15),
        PolicyCue("STP/sfx_pen_writing.flac", 21, 8, 5, 6.0),
        PolicyCue("STP/sfx_radio_crackle.flac", 29, 5, 2, 0.45, 0.15),
        PolicyCue("IVN/committee_marching.mp3", 37, 2, 9, 0.4, 1.5),
    ),
    "superevent_stelander_sotnikov_charter_sound": (
        PolicyCue("STP/sfx_pen_writing.flac", 5, 2, 5, 6.0),
        PolicyCue("STP/sfx_small_applause.flac", 12, 1, 9, 1.2, 1.0),
        PolicyCue("STP/sfx_pen_writing.flac", 30, 15, 4, 5.0),
        PolicyCue("STP/sfx_small_applause.flac", 39, 5, 9, 1.0, 1.5),
    ),
    "superevent_stelander_tikhoreva_sound": (
        PolicyCue("STP/sfx_courtyard.flac", 4, 8, 11, 4.0, 1.5),
        PolicyCue("STP/sfx_hand_saw.flac", 20, 0, 5, 0.45, 0.6),
        PolicyCue("STP/sfx_light_hammering.flac", 28, 0, 3, 1.0, 0.2),
        PolicyCue("STP/sfx_light_hammering.flac", 33, 0, 3, 0.85, 0.2),
        PolicyCue("STP/sfx_pen_writing.flac", 39, 10, 5, 5.0),
        PolicyCue("STP/sfx_courtyard.flac", 46, 25, 5, 3.0, 1.0),
    ),
}


WEST_POLICY_CUES = {
    "superevent_west_world_empire_sound": (
        PolicyCue("WRK/sfx_rail_lever.flac", 2, 0, 1.09, 0.4, 0.02),
        PolicyCue("WRK/sfx_steam_release.flac", 4, 0, 1.68, 0.18, 0.1),
        PolicyCue("WRK/sfx_distant_train_horn.flac", 7, 0, 5.09, 0.22, 0.5),
        PolicyCue("WRK/sfx_train_departure.flac", 11, 15, 26, 0.18, 3.0),
        PolicyCue("WRK/sfx_steam_train_passing.flac", 35, 0, 15.15, 0.12, 3.0),
        PolicyCue("WRK/sfx_distant_train_horn.flac", 47, 0, 5.09, 0.1, 1.0),
    ),
}


SOUTH_POLICY_CUES = {
    "superevent_south_houses_sound": (
        PolicyCue("STP/sfx_banquet_room.flac", 2, 4, 14, 0.12, 2.0),
        PolicyCue("STP/sfx_paper_slide.flac", 8, 0, 1.09, 0.35, 0.03),
        PolicyCue("STP/sfx_pen_writing.flac", 10, 8, 4, 4.0, 0.4),
        PolicyCue("South/sfx_contract_stamp.flac", 15, 0, 1.59, 0.6, 0.02),
        PolicyCue("STP/sfx_small_applause.flac", 18, 1, 7, 0.65, 1.0),
        PolicyCue("STP/sfx_courtyard.flac", 29, 8, 20, 0.8, 3.0),
        PolicyCue("South/sfx_horse_cart.flac", 30, 1, 16, 0.22, 2.0),
    ),
    "superevent_south_war_sound": (
        PolicyCue("STP/sfx_winter_wind.flac", 0, 0, 56, 0.07, 3.0),
        PolicyCue("STP/sfx_radio_crackle.flac", 2, 2, 1.5, 0.22, 0.15),
        PolicyCue("IVN/tank_medium.ogg", 5, 0, 18, 0.16, 3.0),
        PolicyCue("IVN/distant_cannon.ogg", 19, 0, 5, 0.35, 0.1),
        PolicyCue("IVN/distant_rifle.ogg", 27, 0, 10, 0.12, 1.0),
        PolicyCue("IVN/tank_light.ogg", 34, 0, 16, 0.1, 3.0),
        PolicyCue("IVN/distant_cannon.ogg", 44, 0, 5, 0.28, 0.1),
    ),
    "superevent_south_free_islands_sound": (
        PolicyCue("South/sfx_harbor_waves.flac", 2, 8, 52, 0.28, 3.0),
        PolicyCue("STP/sfx_ship_engine.flac", 4, 0, 14, 0.08, 3.0),
        PolicyCue("STP/sfx_distant_ship_horn.flac", 7, 1.5, 7, 0.35, 0.8),
        PolicyCue("STP/sfx_courtyard.flac", 18, 8, 27, 1.2, 4.0),
        PolicyCue("IVN/committee_cheers.mp3", 23, 0, 7, 1.1, 1.0),
        PolicyCue("STP/sfx_small_applause.flac", 24, 1, 13, 0.55, 2.0),
        PolicyCue("IVN/committee_cheers.mp3", 41, 3, 6, 0.8, 1.5),
    ),
}


VAL_POLICY_CUES = {
    "superevent_val_council_proclamation_sound": (
        PolicyCue("STP/sfx_radio_crackle.flac", 2, 2, 1.2, 0.18, 0.15),
        PolicyCue("STP/sfx_guard_steps.flac", 4, 1, 8, 0.5, 0.8),
        PolicyCue("STP/sfx_paper_slide.flac", 13, 0, 1.09, 0.3, 0.03),
        PolicyCue("STP/sfx_vintage_camera.flac", 15, 0, 1.15, 0.2, 0.02),
        PolicyCue("VAL/council_address.flac", 16.5, 0, 24.65, 1.0, 0.02, 0.75),
        PolicyCue("STP/sfx_small_applause.flac", 42, 1, 10, 0.75, 1.5),
    ),
}


def build(root: Path, output: Path, *, silence_only: bool = False, track: str | None = None) -> list[Path]:
    policy_tracks = {
        **{name: ("STP", source) for name, source in STP_POLICY_TRACKS.items()},
        **{name: ("WRK", source) for name, source in WEST_POLICY_TRACKS.items()},
        **{name: ("South", source) for name, source in SOUTH_POLICY_TRACKS.items()},
        **{name: ("VAL", source) for name, source in VAL_POLICY_TRACKS.items()},
    }
    policy_cues = {**STP_POLICY_CUES, **WEST_POLICY_CUES, **SOUTH_POLICY_CUES, **VAL_POLICY_CUES}
    known_tracks = {
        "ADISCORD_rus_world_ends", "one_minute_of_silence", "two_minutes_of_silence",
        "superevent_itora_legion_victory_sound",
        "superevent_itora_committee_victory_sound",
        "superevent_itora_stalk_portal_sound",
        "superevent_stelander_shabrat_republic_sound",
        *RUS_EMPIRE_TRACKS,
        *STP_POLICY_TRACKS,
        *WEST_POLICY_TRACKS,
        *SOUTH_POLICY_TRACKS,
        *VAL_POLICY_TRACKS,
        STP_FESTIVAL_TRACK,
        STP_HOUSES_TRACK,
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

    if not silence_only and track in (None, "superevent_stelander_shabrat_republic_sound"):
        source = root / "tools/assets/source/superevents"
        inputs = ["-i", str(source / "STP/svendsen_festival_polonaise_excerpt.flac")]
        for name in ("committee_marching.mp3", "committee_cheers.mp3", "committee_fireworks.mp3", "tank_medium.ogg"):
            inputs.extend(["-stream_loop", "-1", "-i", str(source / "IVN" / name)])
        filters = (
            "[0:a]aresample=44100,aformat=channel_layouts=stereo,"
            "atrim=duration=56,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=2,afade=t=out:st=50:d=6,volume=0.85[music];"
            "[1:a]aresample=44100,asplit=2[m1][m2];"
            "[m1]atrim=duration=18,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=2,afade=t=out:st=15:d=3,volume=0.4,adelay=4000:all=1[march1];"
            "[m2]atrim=start=3:duration=16,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=2,afade=t=out:st=13:d=3,volume=0.35,adelay=32000:all=1[march2];"
            "[2:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[c1][c2];"
            "[c1]atrim=start=1:duration=8,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.5,afade=t=out:st=6:d=2,volume=1.2,adelay=8000:all=1[cheers1];"
            "[c2]atrim=start=9:duration=9,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.5,afade=t=out:st=7:d=2,volume=1.2,adelay=35000:all=1[cheers2];"
            "[3:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[f1][f2];"
            "[f1]atrim=start=10:duration=7,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.15,afade=t=out:st=5:d=2,volume=0.22,adelay=18000:all=1[fireworks1];"
            "[f2]atrim=start=40:duration=8,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.15,afade=t=out:st=6:d=2,volume=0.22,adelay=46000:all=1[fireworks2];"
            "[4:a]aresample=44100,aformat=channel_layouts=stereo,"
            "atrim=duration=10,asetpts=PTS-STARTPTS,lowpass=f=1800,"
            "afade=t=in:d=3,afade=t=out:st=6:d=4,volume=0.08,adelay=26000:all=1[tank];"
            "[music][march1][march2][cheers1][cheers2][fireworks1][fireworks2][tank]"
            "amix=inputs=8:duration=first:normalize=0,"
            "asetpts=N/SR/TB,apad=whole_len=2469600,atrim=end_sample=2469600[out]"
        )
        encode(
            "superevent_stelander_shabrat_republic_sound", inputs,
            ["-filter_complex", filters, "-map", "[out]", "-t", "56"], wav=True,
        )

    if not silence_only and track in (None, STP_HOUSES_TRACK):
        source = root / "tools/assets/source/superevents/STP"
        inputs = []
        for filename in (
            "camerata_mediolanense_dolci_ire_excerpt.flac",
            "sfx_banquet_room.flac",
            "sfx_wine_glass.flac",
            "sfx_toast_glasses.flac",
            "sfx_small_applause.flac",
            "houses_banquet_toast.flac",
        ):
            inputs.extend(["-i", str(source / filename)])
        # Guests settle during the toast slot; the music has no speech-driven gain changes.
        filters = [
            "[0:a]aresample=44100,aformat=channel_layouts=stereo,"
            "loudnorm=I=-20:TP=-3:LRA=11,aresample=44100,"
            "afade=t=in:d=1.5,afade=t=out:st=51:d=5[music]",
            "[1:a]aresample=44100,aformat=channel_layouts=stereo,"
            "atrim=duration=56,asetpts=PTS-STARTPTS,highpass=f=160,lowpass=f=3800,"
            "loudnorm=I=-35:TP=-9:LRA=7,aresample=44100,"
            "volume='if(lt(t,17),1,if(lt(t,20),1-0.2*(t-17),"
            "if(lt(t,36),0.4,if(lt(t,39),0.4+0.2*(t-36),1))))':eval=frame,"
            "afade=t=in:d=2,afade=t=out:st=50:d=6[room]",
            "[2:a]aresample=44100,aformat=channel_layouts=stereo,"
            "volume=0.2,afade=t=in:d=0.01,asplit=2[g1][g2]",
            "[g1]adelay=8000:all=1[glass1]",
            "[g2]adelay=17000:all=1[glass2]",
            "[3:a]aresample=44100,aformat=channel_layouts=stereo,"
            "volume=0.25,afade=t=in:d=0.01,adelay=35800:all=1[toast]",
            "[4:a]aresample=44100,aformat=channel_layouts=stereo,"
            "atrim=start=2:duration=7,asetpts=PTS-STARTPTS,"
            "volume=0.75,afade=t=in:d=0.7,afade=t=out:st=4.5:d=2.5,"
            "adelay=37200:all=1[applause]",
            "[5:a]aresample=44100,aformat=channel_layouts=stereo,highpass=f=70,"
            "loudnorm=I=-18:TP=-3:LRA=7,aresample=44100,"
            "afade=t=in:d=0.02,afade=t=out:st=14.88:d=0.08,"
            "aecho=0.9:1:65|110:0.08|0.04,adelay=20000:all=1[speech]",
            "[music][room][glass1][glass2][toast][applause][speech]"
            "amix=inputs=7:duration=first:normalize=0,"
            "asetpts=N/SR/TB,apad=whole_len=2469600,atrim=end_sample=2469600[out]",
        ]
        encode(
            STP_HOUSES_TRACK, inputs,
            ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", "56"],
            wav=True,
        )

    if not silence_only and track in (None, STP_FESTIVAL_TRACK):
        source = root / "tools/assets/source/superevents"
        inputs = []
        for filename in (
            "STP/circus_contraption_raining_pianos_excerpt.flac",
            "STP/cities_last_broadcast_lights_out_excerpt.flac",
            "STP/sfx_radio_crackle.flac",
            "IVN/panic_crowd.mp3",
            "STP/sfx_small_applause.flac",
            "STP/festival_announcer.flac",
        ):
            inputs.extend(["-i", str(source / filename)])
        # The excerpt begins at 01:23; its final four seconds are 01:43-01:47.
        # Pitch shifts preserve the four-second loop length and its word boundaries.
        filters = [
            "[0:a]aresample=44100,aformat=channel_layouts=stereo,"
            "volume=0.52,asplit=4[intro0][loop1][loop2][loop3]",
            "[intro0]atrim=duration=24,asetpts=PTS-STARTPTS,"
            "afade=t=in:d=0.4,afade=t=out:st=23.99:d=0.01[intro]",
            "[loop1]atrim=start=20:duration=4,asetpts=PTS-STARTPTS,"
            "lowpass=f=7000,afade=t=in:d=0.01,afade=t=out:st=3.99:d=0.01[repeat1]",
            "[loop2]atrim=start=20:duration=4,asetpts=PTS-STARTPTS,"
            "asetrate=41454,aresample=44100,atempo=1.063829787234,"
            "flanger=delay=3:depth=2:width=55:speed=0.5,lowpass=f=4500,"
            "apad,atrim=duration=4,afade=t=in:d=0.01,"
            "afade=t=out:st=3.99:d=0.01[repeat2]",
            "[loop3]atrim=start=20:duration=4,asetpts=PTS-STARTPTS,"
            "asetrate=37926,aresample=44100,atempo=1.162790697674,"
            "flanger=delay=4:depth=3:width=70:speed=0.6,"
            "tremolo=f=8:d=0.55,lowpass=f=2800,apad,atrim=duration=4,"
            "afade=t=in:d=0.01,afade=t=out:st=3.88:d=0.12[repeat3]",
            "[intro][repeat1][repeat2][repeat3]concat=n=4:v=0:a=1,"
            "apad=whole_len=2469600,atrim=end_sample=2469600[carnival]",
            "[1:a]aresample=44100,aformat=channel_layouts=stereo,"
            "loudnorm=I=-20:TP=-4:LRA=11,aresample=44100,"
            "afade=t=in:d=0.25,afade=t=out:st=17:d=3,"
            "adelay=36000:all=1[horror]",
            "[2:a]aresample=44100,aformat=channel_layouts=stereo,asplit=3[n1][n2][n3]",
            "[n1]atrim=start=1:duration=2,asetpts=PTS-STARTPTS,volume=0.22,"
            "afade=t=in:d=0.4,afade=t=out:st=1.5:d=0.5,adelay=22000:all=1[noise1]",
            "[n2]atrim=start=2:duration=4,asetpts=PTS-STARTPTS,volume=0.4,"
            "afade=t=in:d=0.3,afade=t=out:st=3.7:d=0.3,adelay=28000:all=1[noise2]",
            "[n3]atrim=start=4:duration=4,asetpts=PTS-STARTPTS,volume=0.65,"
            "afade=t=in:d=0.2,afade=t=out:st=3.9:d=0.1,adelay=32000:all=1[noise3]",
            "[3:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[p1][p2]",
            "[p1]atrim=start=1:duration=4,asetpts=PTS-STARTPTS,volume=0.65,"
            "afade=t=in:d=0.15,afade=t=out:st=2.5:d=1.5,"
            "adelay=35000:all=1[panic1]",
            "[p2]atrim=start=1:duration=4,asetpts=PTS-STARTPTS,lowpass=f=1800,"
            "aecho=0.8:0.5:270|490:0.35|0.2,volume=0.3,"
            "afade=t=in:d=0.4,afade=t=out:st=2.5:d=2,adelay=41000:all=1[panic2]",
            "[4:a]aresample=44100,aformat=channel_layouts=stereo,"
            "atrim=start=1:duration=6,asetpts=PTS-STARTPTS,volume=0.55,"
            "afade=t=in:d=0.5,afade=t=out:st=4:d=2,adelay=2000:all=1[applause]",
            "[5:a]aresample=44100,aformat=channel_layouts=stereo,highpass=f=70,"
            "loudnorm=I=-18:TP=-3:LRA=7,aresample=44100,"
            "afade=t=in:d=0.02,afade=t=out:st=7.75:d=0.09,"
            "adelay=46000:all=1[announcer]",
            "[carnival][horror][noise1][noise2][noise3][panic1][panic2][applause][announcer]"
            "amix=inputs=9:duration=first:normalize=0,"
            "asetpts=N/SR/TB,apad=whole_len=2469600,atrim=end_sample=2469600[out]",
        ]
        encode(
            STP_FESTIVAL_TRACK, inputs,
            ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", "56"],
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

    if not silence_only:
        for name, (family, source_name) in policy_tracks.items():
            if track is not None and track != name:
                continue
            source = root / "tools/assets/source/superevents" / family / source_name
            inputs = ["-i", str(source)]
            music_gain = ""
            if name == "superevent_stelander_party_victory_regent_sound":
                # The song's vocals yield to Renner's address with a five-decibel dip.
                music_gain = (
                    "volume='if(lt(t,17.5),1,if(lt(t,18),"
                    "1-0.437659*(t-17.5)/0.5,if(lt(t,32.7),0.562341,"
                    "if(lt(t,33.5),0.562341+0.437659*(t-32.7)/0.8,1))))':eval=frame,"
                )
            # Quantize the music before adding speech and sound effects.
            filters = [
                "[0:a]loudnorm=I=-18:TP=-2:LRA=11,afade=t=in:d=1,"
                "afade=t=out:st=51:d=5,"
                + music_gain
                + "aformat=sample_fmts=s16:sample_rates=44100:channel_layouts=stereo[music]"
            ]
            layers = ["[music]"]
            for index, cue in enumerate(policy_cues[name], start=1):
                inputs.extend([
                    "-stream_loop", "-1", "-i",
                    str(root / "tools/assets/source/superevents" / cue.source),
                ])
                label = f"cue{index}"
                filters.append(
                    f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo,"
                    f"atrim=start={cue.offset}:duration={cue.duration},asetpts=PTS-STARTPTS,"
                    f"volume={cue.gain},alimiter=limit={cue.peak_limit}:level=false:latency=true,"
                    f"afade=t=in:d={cue.fade},"
                    f"afade=t=out:st={cue.duration - cue.fade}:d={cue.fade},"
                    f"adelay={round(cue.start * 1000)}:all=1[{label}]"
                )
                layers.append(f"[{label}]")
            # Limit effects individually; never normalize or compress the combined music bus.
            filters.append(
                "".join(layers)
                + f"amix=inputs={len(layers)}:duration=first:normalize=0,"
                + "asetpts=N/SR/TB,apad=whole_len=2469600,atrim=end_sample=2469600[out]"
            )
            encode(
                name, inputs,
                ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", "56"],
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
            if generated.stem in {*STP_POLICY_TRACKS, *WEST_POLICY_TRACKS, *SOUTH_POLICY_TRACKS, *VAL_POLICY_TRACKS, STP_FESTIVAL_TRACK, STP_HOUSES_TRACK} or generated.name in {
                "superevent_itora_legion_victory_sound.wav",
                "superevent_itora_committee_victory_sound.wav",
                "superevent_itora_stalk_portal_sound.wav",
                "superevent_rus_restoration_sound.wav",
                "superevent_rus_black_banner_sound.wav",
                "superevent_stelander_shabrat_republic_sound.wav",
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
