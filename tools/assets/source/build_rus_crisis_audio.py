"""Mix the Khan finale's PCM16 stereo 44.1 kHz sound cues.

Owns sound/RUS/ADISCORD_rus_reactor_charge.wav,
sound/RUS/ADISCORD_rus_reactor_impact.wav and
sound/RUS/ADISCORD_rus_ruined_world.wav, plus
music/ADISCORD_rus_aftermath_silence.ogg. Run --check, --apply, then --check.
The entity starts charge at 0 s and impact at the particle's 10.0 s detonation.
The full mix is normalized once, then split at that exact sample boundary.
Requires NumPy, SciPy and FFmpeg in PATH. Source credits and CC0 licences are
recorded in rus_crisis_audio/SOURCES.txt; imported files remain unmodified.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import wave

import numpy as np
from scipy.signal import butter, resample, sosfilt


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "sound/RUS"
SOURCE = Path(__file__).with_name("rus_crisis_audio")
RATE = 44100
BEAM_START = 6.0
IMPACT_START = 10.0
STRIKE_DURATION = 26
AFTERMATH_SILENCE = 300
HASHES = {
    "explosionCrunch_004.ogg": "9c3a1c73cadf0de5d5a578b31a264f20b1ac7cb6ec9bbd34a203f58402ea5390",
    "computerNoise_000.ogg": "1527944e16eb14b48ee03fe3e7ce6aae94262833a4e1f83928d451a7414fe4e1",
    "unfa_huge_explosion_hq.mp3": "76d13e6718c0ac76860c733400379eb690ac35f6dca82bed9dd5fb5d5ab5634f",
    "NenadSimic_Muffled_Distant_Explosion.wav": "13a0bf75af94ec6d332bc71cba489b573466e05c4b17288158b3d683b41de39f",
}


def decode(name):
    path = SOURCE / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[name]:
        raise ValueError(f"Source audio differs: {name}")
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(RATE),
        "-f", "f32le", "-",
    ])
    samples = np.frombuffer(raw, dtype="<f4").reshape(-1, 2).astype(float)
    return samples / np.max(np.abs(samples))


def pitch(samples, rate):
    return resample(samples, round(len(samples) / rate), axis=0)


def timeline(duration):
    return np.arange(round(duration * RATE)) / RATE


def fade(samples, attack=0.02, release=0.2):
    result = samples.copy()
    envelope = np.ones(len(result))
    count = min(round(attack * RATE), len(result))
    envelope[:count] *= np.linspace(0, 1, count)
    count = min(round(release * RATE), len(result))
    envelope[-count:] *= np.linspace(1, 0, count)
    return result * (envelope[:, None] if result.ndim == 2 else envelope)


def noise(duration, low, high, seed):
    samples = np.random.default_rng(seed).normal(0, 1, round(duration * RATE))
    band = butter(3, [low, high], btype="bandpass", fs=RATE, output="sos")
    samples = sosfilt(band, samples)
    return samples / max(np.sqrt(np.mean(samples ** 2)), 1e-9)


def sweep(duration, start, finish):
    time = timeline(duration)
    slope = (finish - start) / duration
    return np.sin(2 * np.pi * (start * time + 0.5 * slope * time ** 2))


def add_layer(destination, samples, start=0, gain=1, pan=0):
    offset = round(start * RATE)
    count = min(len(samples), len(destination) - offset)
    angle = (pan + 1) * np.pi / 4
    left = samples[:count, 0] if samples.ndim == 2 else samples[:count]
    right = samples[:count, 1] if samples.ndim == 2 else samples[:count]
    destination[offset:offset + count, 0] += left * gain * np.cos(angle)
    destination[offset:offset + count, 1] += right * gain * np.sin(angle)


def detonation(duration, seed):
    time = timeline(duration)
    shock = noise(duration, 25, 900, seed) * np.exp(-time / 1.6)
    crack = noise(duration, 1100, 7500, seed + 1) * np.exp(-time / 0.12)
    pressure = sweep(duration, 76, 27) * np.exp(-time / 2.5)
    return fade(shock * 0.45 + crack * 0.25 + pressure * 0.5, 0.004, 0.8)


def reactor_strike(source):
    result = np.zeros((STRIKE_DURATION * RATE, 2))
    # One continuous low pressure bed carries the charge into the sustained beam.
    # Slow envelopes preserve the particle's build-up without discrete alarms.
    charge_time = timeline(IMPACT_START + 0.2)
    rise = np.clip(charge_time / BEAM_START, 0, 1)
    rise = rise ** 2 * (3 - 2 * rise)
    charge = np.sin(2 * np.pi * 36 * charge_time) * 0.1
    charge += np.sin(2 * np.pi * 54.3 * charge_time) * 0.065
    charge += np.sin(2 * np.pi * 72.1 * charge_time) * 0.025
    charge += noise(IMPACT_START + 0.2, 28, 210, 2163001) * 0.075
    charge *= (0.08 + 0.92 * rise) * (0.92 + 0.08 * np.sin(charge_time * 1.7))
    add_layer(result, fade(charge, 2.4, 0.25))

    swell = pitch(source["NenadSimic_Muffled_Distant_Explosion.wav"], 0.67)[::-1]
    swell = swell[-min(len(swell), round(BEAM_START * RATE)):]
    swell = sosfilt(butter(3, 220, fs=RATE, output="sos"), swell, axis=0)
    swell *= np.linspace(0, 1, len(swell))[:, None] ** 1.6
    add_layer(result, fade(swell, 2.2, 0.7), BEAM_START - len(swell) / RATE, 0.22)

    beam_duration = IMPACT_START - BEAM_START + 0.2
    beam_time = timeline(beam_duration)
    beam = noise(beam_duration, 32, 620, 2163002) * 0.12
    beam += np.sin(2 * np.pi * 46 * beam_time) * 0.14
    beam += noise(beam_duration, 160, 1200, 2163003) * 0.018
    beam *= np.linspace(0.5, 1, len(beam))
    add_layer(result, fade(beam, 0.8, 0.2), BEAM_START)

    add_layer(result, fade(source["unfa_huge_explosion_hq.mp3"], 0.003, 1), IMPACT_START, 1.6)
    add_layer(result, fade(source["explosionCrunch_004.ogg"], 0.003, 0.3), IMPACT_START + 0.02, 0.4)
    add_layer(result, detonation(9, 2163004), IMPACT_START, 0.16)
    # Later reflections widen the shock without smearing its central transient.
    echo = fade(pitch(source["NenadSimic_Muffled_Distant_Explosion.wav"], 0.72), 0.015, 0.6)
    add_layer(result, echo, IMPACT_START + 0.32, 0.28, -0.7)
    add_layer(result, echo, IMPACT_START + 0.67, 0.22, 0.7)
    rubble_time = timeline(10.5)
    rubble = noise(10.5, 80, 5000, 2163008)
    rubble *= np.exp(-rubble_time / 2.3)
    rubble *= 0.2 + np.sin(rubble_time * 8) ** 8
    add_layer(result, fade(rubble, 0.04, 1), IMPACT_START + 0.6, 0.12, -0.3)
    ring_time = timeline(7)
    ring = np.sin(2 * np.pi * 2100 * ring_time) * np.exp(-ring_time / 1.8)
    add_layer(result, fade(ring, 0.15, 0.8), IMPACT_START + 0.4, 0.025)
    for pan, seed in ((-0.9, 2163010), (0.9, 2163011)):
        tail_time = timeline(12)
        tail = noise(12, 40, 500, seed) * np.exp(-tail_time / 4)
        add_layer(result, fade(tail, 0.8, 3), IMPACT_START + 2.3, 0.035, pan)
    return result


def ruined_world(source):
    result = np.zeros((32 * RATE, 2))
    time = timeline(32)
    decay = np.exp(-time / 15)
    # A dead receiver, wind and distant collapses recede into silence.
    for pan, seed in ((-0.8, 2163101), (0.8, 2163102)):
        wind = noise(32, 45, 1200, seed)
        wind *= decay * (0.75 + 0.25 * np.sin(time * 0.9 + pan))
        add_layer(result, fade(wind, 1.8, 7), gain=0.12, pan=pan)
    hum = (np.sin(2 * np.pi * 49 * time) + 0.2 * np.sin(2 * np.pi * 98 * time))
    add_layer(result, fade(hum * decay, 0.3, 8), gain=0.09)
    dead_receiver = fade(source["computerNoise_000.ogg"], 0.05, 3.5)
    add_layer(result, dead_receiver, 0, 0.075, -0.2)
    for start, pan, seed in ((0.35, -0.3, 2163103), (2.2, 0.4, 2163104), (6.1, -0.5, 2163105)):
        static = noise(0.25, 1200, 4800, seed)
        add_layer(result, fade(static, 0.006, 0.08), start, 0.028, pan)
    for start, pan, rate, gain in ((3.2, -0.7, 0.75, 0.2), (10.5, 0.6, 0.65, 0.14), (18, -0.3, 0.6, 0.08)):
        collapse = pitch(source["NenadSimic_Muffled_Distant_Explosion.wav"], rate)
        collapse = sosfilt(butter(3, 600, fs=RATE, output="sos"), collapse, axis=0)
        add_layer(result, fade(collapse, 0.15, 1.5), start, gain, pan)
    return result


def wav_bytes(samples, peak_db):
    samples = samples - samples.mean(axis=0)
    samples = np.tanh(samples * 1.35)
    for channel in range(2):
        samples[:, channel] = fade(samples[:, channel], 0.006, 0.1)
    samples *= 10 ** (peak_db / 20) / np.max(np.abs(samples))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(np.rint(samples * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def split_wav(content, seconds):
    with wave.open(io.BytesIO(content), "rb") as audio:
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        rate = audio.getframerate()
        frames = audio.readframes(audio.getnframes())
    boundary = round(seconds * rate) * channels * width
    if not 0 < boundary < len(frames):
        raise ValueError("Audio split must be inside the complete cue")
    segments = []
    # Preserve quantized samples on both sides, including their shared boundary.
    # Separate normalization or fades would alter the entity-timed transition.
    for segment in (frames[:boundary], frames[boundary:]):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setnchannels(channels)
            audio.setsampwidth(width)
            audio.setframerate(rate)
            audio.writeframes(segment)
        segments.append(buffer.getvalue())
    return segments


def sound_samples():
    source = {name: decode(name) for name in HASHES}
    charge, impact = split_wav(wav_bytes(reactor_strike(source), -1.0), IMPACT_START)
    return {
        "ADISCORD_rus_reactor_charge.wav": charge,
        "ADISCORD_rus_reactor_impact.wav": impact,
        "ADISCORD_rus_ruined_world.wav": wav_bytes(ruined_world(source), -9.0),
    }


def silence_ogg_bytes():
    # Music time is independent of simulation speed and pause. Reserve the
    # full strike plus five minutes after it without muting GUI effects.
    return subprocess.check_output([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(STRIKE_DURATION + AFTERMATH_SILENCE), "-map_metadata", "-1", "-fflags", "+bitexact",
        "-flags:a", "+bitexact", "-c:a", "libvorbis", "-q:a", "1", "-f", "ogg", "-",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = []
    outputs = {OUTPUT / name: content for name, content in sound_samples().items()}
    outputs[ROOT / "music/ADISCORD_rus_aftermath_silence.ogg"] = silence_ogg_bytes()
    for path, content in outputs.items():
        if not path.exists() or path.read_bytes() != content:
            changed.append(path.name)
            if args.apply:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
    print(json.dumps({"changed": changed, "applied": args.apply}, indent=2))
    if changed and args.check:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
