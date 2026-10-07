"""Build the combat robot's PCM16 mono 44.1 kHz sound samples.

Run from the repository root with --check, then --apply, then --check.
Original recordings are kept in combat_robot_audio; only sound/combat_robots
WAV files are generated. Model events and shared sound registries are authored.
Requires NumPy, SciPy and FFmpeg in PATH.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import wave

import numpy as np
from scipy.signal import resample

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name("combat_robot_audio")
OUTPUT = ROOT / "sound/combat_robots"
RATE = 44100
HASHES = {
    "engineCircular_000.ogg": "8ab85f9fa85e9e692287f98acb36b9ac3ba15313b007c039055e286b736f4e3a",
    "gunshot.mp3": "23c64b967fbaf55744f43099d569205a92fab7014c0a920c258fcfde1a307cb8",
    "impactMetal_000.ogg": "956c6612a256aa1a67a2327fffe2454f6b1d82e4c1c2be28fd66916335d5b1d6",
    "servo.wav": "b10e696e2c01ef7c4b160577a5bd99c405e290c4410aaa574b2405dffd3faddf",
    "stomp.flac": "c9114c31ab07a371db12bfb22190d3a8e08424813319b67b6040df1f23fa9bba",
}


def decode(name):
    path = SOURCE / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == HASHES[name], name
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE),
        "-f", "f32le", "-",
    ])
    samples = np.frombuffer(raw, dtype="<f4").astype(float)
    return samples / np.max(np.abs(samples))


def pitch(samples, rate):
    return resample(samples, round(len(samples) / rate))


def one_shot(samples, duration):
    active = np.flatnonzero(np.abs(samples) > .015 * np.max(np.abs(samples)))
    samples = samples[max(0, active[0] - 88):].copy()
    result = np.zeros(round(duration * RATE))
    count = min(len(result), len(samples))
    result[:count] = samples[:count]
    result[:88] *= np.linspace(0, 1, 88)
    tail = min(round(.09 * RATE), count)
    result[count - tail:count] *= np.linspace(1, 0, tail)
    return result


def mix(duration, layers):
    result = np.zeros(round(duration * RATE))
    for samples, at, gain in layers:
        start = round(at * RATE)
        count = min(len(samples), len(result) - start)
        result[start:start + count] += samples[:count] * gain
    return result


def wav_bytes(samples):
    samples = samples * (.84 / np.max(np.abs(samples)))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(np.rint(samples * 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def sound_samples():
    source = {name: decode(name) for name in HASHES}
    # Whole cycles and a periodic texture keep the low motor bed seamless.
    count = 6 * RATE
    time = np.arange(count) / RATE
    texture = np.fft.rfft(resample(source["engineCircular_000.ogg"], count))
    frequencies = np.fft.rfftfreq(count, 1 / RATE)
    texture[(frequencies < 45) | (frequencies > 180)] = 0
    texture = np.fft.irfft(texture, n=count)
    texture /= np.max(np.abs(texture))
    idle = (np.sin(2 * np.pi * 68 * time)
            + .22 * np.sin(2 * np.pi * 102 * time)
            + .10 * np.sin(2 * np.pi * 136 * time))
    idle *= .96 + .04 * np.sin(2 * np.pi * .5 * time)
    idle += .08 * texture
    servo = pitch(source["servo.wav"], .8)
    metal = pitch(source["impactMetal_000.ogg"], .85)
    start = one_shot(mix(1.3, [(servo, 0, .8), (metal, .18, .15)]), 1.3)
    outputs = {"idle": idle, "start": start}
    for index, rate in enumerate((.85, .91), 1):
        stomp = pitch(source["stomp.flac"], rate)
        step = mix(.72, [(stomp, 0, .8), (metal, .025, .12), (servo, .1, .1)])
        outputs[f"step_{index}"] = one_shot(step, .72)
    shot = one_shot(pitch(source["gunshot.mp3"], .86), .7)
    burst = mix(1.05, [(shot, 0, 1), (shot, .115, .9), (shot, .23, .95), (metal, .35, .12)])
    outputs["burst"] = one_shot(burst, 1.05)
    return {f"ADISCORD_robot_{name}.wav": wav_bytes(samples) for name, samples in outputs.items()}


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
