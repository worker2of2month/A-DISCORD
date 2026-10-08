"""Synthesize the Khan finale's original PCM16 stereo 44.1 kHz sound cues.

Owns sound/RUS/ADISCORD_rus_reactor_strike.wav and
sound/RUS/ADISCORD_rus_ruined_world.wav. Run --check, --apply, then --check.
The strike follows the particle's beam at 0.7 s and detonation at 3.7 s.
Requires NumPy and SciPy; no external recordings are used.
"""

import argparse
import io
import json
from pathlib import Path
import wave

import numpy as np
from scipy.signal import butter, sosfilt


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "sound/RUS"
RATE = 44100


def timeline(duration):
    return np.arange(round(duration * RATE)) / RATE


def fade(samples, attack=0.02, release=0.2):
    result = samples.copy()
    count = min(round(attack * RATE), len(result))
    result[:count] *= np.linspace(0, 1, count)
    count = min(round(release * RATE), len(result))
    result[-count:] *= np.linspace(1, 0, count)
    return result


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
    destination[offset:offset + count, 0] += samples[:count] * gain * np.cos(angle)
    destination[offset:offset + count, 1] += samples[:count] * gain * np.sin(angle)


def detonation(duration, seed):
    time = timeline(duration)
    shock = noise(duration, 25, 900, seed) * np.exp(-time / 1.6)
    crack = noise(duration, 1100, 7500, seed + 1) * np.exp(-time / 0.12)
    pressure = sweep(duration, 76, 27) * np.exp(-time / 2.5)
    return fade(shock * 0.45 + crack * 0.25 + pressure * 0.5, 0.004, 0.8)


def reactor_strike():
    result = np.zeros((18 * RATE, 2))
    # Target lock and capacitor whine occupy the particle's initial 0.7 seconds.
    lock_time = timeline(0.13)
    lock = fade(np.sin(2 * np.pi * 920 * lock_time), 0.008, 0.04)
    for start in (0, 0.20, 0.40):
        add_layer(result, lock, start, 0.15)
    charge = sweep(0.7, 95, 1350) + 0.18 * sweep(0.7, 190, 2700)
    charge *= np.linspace(0.02, 0.45, len(charge))
    add_layer(result, fade(charge, 0.015, 0.025))

    beam_time = timeline(3.15)
    beam = 0.14 * sweep(3.15, 230, 155)
    beam += noise(3.15, 170, 2800, 2163001) * 0.1
    beam *= 0.7 + 0.3 * np.sin(2 * np.pi * 31 * beam_time) ** 2
    add_layer(result, fade(beam, 0.035, 0.05), 0.7)
    add_layer(result, fade(sweep(0.36, 2600, 230), 0.01, 0.1), 0.7, 0.3)

    add_layer(result, detonation(9, 2163002), 3.7, 0.9)
    # Later reflections widen the shock without smearing its central transient.
    add_layer(result, detonation(7, 2163004), 4.02, 0.28, -0.7)
    add_layer(result, detonation(7, 2163006), 4.37, 0.22, 0.7)
    rubble_time = timeline(10.5)
    rubble = noise(10.5, 80, 5000, 2163008)
    rubble *= np.exp(-rubble_time / 2.3)
    rubble *= 0.2 + np.sin(rubble_time * 8) ** 8
    add_layer(result, fade(rubble, 0.04, 1), 4.3, 0.12, -0.3)
    ring_time = timeline(7)
    ring = np.sin(2 * np.pi * 2100 * ring_time) * np.exp(-ring_time / 1.8)
    add_layer(result, fade(ring, 0.15, 0.8), 4.1, 0.025)
    for pan, seed in ((-0.9, 2163010), (0.9, 2163011)):
        tail_time = timeline(12)
        tail = noise(12, 40, 500, seed) * np.exp(-tail_time / 4)
        add_layer(result, fade(tail, 0.8, 3), 6, 0.035, pan)
    return result


def ruined_world():
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
    for start, pan, seed in ((0.35, -0.3, 2163103), (2.2, 0.4, 2163104), (6.1, -0.5, 2163105)):
        static = noise(0.25, 1200, 4800, seed)
        add_layer(result, fade(static, 0.006, 0.08), start, 0.028, pan)
    for start, pan, seed in ((3.2, -0.7, 2163106), (10.5, 0.6, 2163108), (18, -0.3, 2163110)):
        collapse = noise(7, 28, 210, seed) * np.exp(-timeline(7) / 2)
        add_layer(result, fade(collapse, 0.15, 1.5), start, 0.09, pan)
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


def sound_samples():
    return {
        "ADISCORD_rus_reactor_strike.wav": wav_bytes(reactor_strike(), -1.0),
        "ADISCORD_rus_ruined_world.wav": wav_bytes(ruined_world(), -9.0),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = []
    for name, content in sound_samples().items():
        path = OUTPUT / name
        if not path.exists() or path.read_bytes() != content:
            changed.append(name)
            if args.apply:
                OUTPUT.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
    print(json.dumps({"changed": changed, "applied": args.apply}, indent=2))
    if changed and args.check:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
