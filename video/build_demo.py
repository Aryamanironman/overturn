#!/usr/bin/env python3
"""Mix the demo narration and encode the film.

    python video/build_demo.py --audio
    python video/build_demo.py --encode

The bed is calmer than the pitch film: a low pad, a slow arpeggio and a soft
hit on each scene, ducked under the voice. Voices are already loudness
normalised by make_demo_voice.py; the final mix is mastered to -14 LUFS.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

VIDEO = Path(__file__).resolve().parent
ROOT = VIDEO.parent
STORY = json.loads((VIDEO / "demo.json").read_text(encoding="utf-8"))
SR = 44100
OUT_AUDIO = VIDEO / "assets" / "demo-sound.wav"
OUT_VIDEO = VIDEO / "out" / "overturn-demo.mp4"
FPS = 30


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        data = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError(f"{path} is not 16-bit")
    values = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    if channels == 1:
        values = np.stack([values, values], axis=1)
    else:
        values = values.reshape(-1, channels)[:, :2]
    return values


def build_audio() -> None:
    total = float(STORY["total"]) + 0.6
    n = int(total * SR)
    voice = np.zeros((n, 2), dtype=np.float32)
    for scene in STORY["scenes"]:
        clip = read_wav(VIDEO / scene["voice_file"])
        start = int(float(scene["voice_start"]) * SR)
        end = min(n, start + len(clip))
        voice[start:end] += clip[: end - start]

    t = np.arange(n, dtype=np.float32) / SR
    bed = np.zeros((n, 2), dtype=np.float32)

    # low pad, A minor
    lfo = 0.72 + 0.28 * np.sin(2 * np.pi * 0.05 * t + 0.4)
    pad = (
        0.016 * np.sin(2 * np.pi * 110.00 * t)
        + 0.009 * np.sin(2 * np.pi * 164.81 * t + 0.8)
        + 0.005 * np.sin(2 * np.pi * 261.63 * t + 1.7)
    ) * lfo
    bed[:, 0] += pad
    bed[:, 1] += pad * 0.98

    # slow arpeggio
    notes = [220.0, 261.63, 329.63, 392.0, 440.0, 329.63]
    moment = 1.2
    step = 0
    while moment < total - 1.2:
        freq = notes[step % len(notes)]
        length = int(1.6 * SR)
        start = int(moment * SR)
        tt = np.arange(length, dtype=np.float32) / SR
        env = np.exp(-tt * 2.4) * (1.0 - np.exp(-tt * 120.0))
        tone = np.sin(2 * np.pi * freq * tt) + 0.25 * np.sin(2 * np.pi * freq * 2 * tt)
        value = 0.024 * env * tone
        pan = 0.16 if step % 2 == 0 else -0.16
        end = min(n, start + length)
        bed[start:end, 0] += value[: end - start] * (1 - max(0.0, pan))
        bed[start:end, 1] += value[: end - start] * (1 + min(0.0, pan))
        moment += 1.1
        step += 1

    # soft pulse
    moment = 0.0
    while moment < total - 1.0:
        start = int(moment * SR)
        length = int(0.55 * SR)
        tt = np.arange(length, dtype=np.float32) / SR
        value = 0.024 * np.exp(-tt * 7.0) * np.sin(2 * np.pi * 55.0 * tt)
        end = min(n, start + length)
        bed[start:end, 0] += value[: end - start]
        bed[start:end, 1] += value[: end - start]
        moment += 1.25

    # scene hits
    for scene in STORY["scenes"]:
        start = int(float(scene["start"]) * SR) + int(0.03 * SR)
        length = int(0.55 * SR)
        tt = np.arange(length, dtype=np.float32) / SR
        freq = 46 + 54 * np.exp(-tt * 14)
        value = 0.055 * np.exp(-tt * 11) * np.sin(2 * np.pi * freq * tt)
        end = min(n, start + length)
        bed[start:end, 0] += value[: end - start]
        bed[start:end, 1] += value[: end - start]

    # duck the bed under the voice
    env = np.abs(voice).max(axis=1)
    window = int(0.18 * SR)
    kernel = np.ones(window, dtype=np.float32) / window
    env = np.convolve(env, kernel, mode="same")
    peak = float(env.max()) or 1.0
    duck = 1.0 - 0.62 * np.clip(env / peak, 0.0, 1.0)
    mix = voice + bed * duck[:, None]

    peak = float(np.abs(mix).max()) or 1.0
    mix = mix / peak * 0.90
    OUT_AUDIO.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT_AUDIO), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes((mix * 32767.0).astype("<i2").tobytes())
    print(f"wrote {OUT_AUDIO}  {n/SR:.2f}s")


def encode() -> None:
    frames = sorted((VIDEO / "frames-demo").glob("f*.png"))
    if not frames:
        raise SystemExit("no frames; run render_demo.py --frames first")
    OUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", str(FPS), "-start_number", "0",
            "-i", str(VIDEO / "frames-demo" / "f%05d.png"),
            "-i", str(OUT_AUDIO),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=9",
            "-shortest", "-movflags", "+faststart",
            str(OUT_VIDEO),
        ],
        check=True,
    )
    print(f"wrote {OUT_VIDEO}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--encode", action="store_true")
    args = parser.parse_args()
    if args.audio or not args.encode:
        build_audio()
    if args.encode:
        encode()
