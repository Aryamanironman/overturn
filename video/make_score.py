#!/usr/bin/env python3
"""Mix the narrated story.

A warm A-minor bed (pad, slow arpeggio, soft pulse) sits under the narration
and ducks whenever a voice clip is speaking. Scene starts get a soft hit.

    python video/make_score.py
"""

from __future__ import annotations

import json
import math
import random
import struct
import wave
from pathlib import Path

VIDEO = Path(__file__).resolve().parent
SR = 44100
RNG = random.Random(20261025)
OUT = VIDEO / "assets" / "film-sound.wav"


def read_wav(path: Path) -> tuple[list[float], list[float]]:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 2 or handle.getsampwidth() != 2:
            raise ValueError(f"{path} is not stereo 16-bit")
        frames = handle.readframes(handle.getnframes())
    values = struct.unpack("<" + str(len(frames) // 2) + "h", frames)
    left = [values[i] / 32768.0 for i in range(0, len(values), 2)]
    right = [values[i] / 32768.0 for i in range(1, len(values), 2)]
    return left, right


def main() -> None:
    story = json.loads((VIDEO / "film.json").read_text(encoding="utf-8"))
    total = float(story["total"]) + 0.6
    n = int(total * SR)
    bed_l = [0.0] * n
    bed_r = [0.0] * n

    # ---- pad ---------------------------------------------------------
    for i in range(n):
        t = i / SR
        lfo = 0.70 + 0.30 * math.sin(2 * math.pi * 0.055 * t + 0.4)
        a = 0.018 * lfo * math.sin(2 * math.pi * 110.0 * t)
        e = 0.010 * lfo * math.sin(2 * math.pi * 164.81 * t + 0.8)
        c = 0.006 * lfo * math.sin(2 * math.pi * 261.63 * t + 1.7)
        bed_l[i] += a + e + c * 0.7
        bed_r[i] += a * 0.98 + e * 1.02 + c

    # ---- slow arpeggio ----------------------------------------------
    notes = [220.0, 261.63, 329.63, 392.0, 440.0, 523.25, 392.0, 329.63]
    moment = 0.9
    step = 0.0
    while moment < total - 1.0:
        freq = notes[int(step) % len(notes)]
        start = int(moment * SR)
        pan = 0.18 if int(step) % 2 == 0 else -0.18
        for i in range(int(1.25 * SR)):
            t = i / SR
            env = math.exp(-t * 2.9) * (1.0 - math.exp(-t * 150.0))
            tone = math.sin(2 * math.pi * freq * t) + 0.28 * math.sin(2 * math.pi * freq * 2 * t)
            value = 0.030 * env * tone
            if start + i < n:
                bed_l[start + i] += value * (1 - max(0.0, pan))
                bed_r[start + i] += value * (1 + min(0.0, pan))
        moment += 0.8
        step += 1

    # ---- soft pulse --------------------------------------------------
    moment = 0.0
    while moment < total - 1.0:
        start = int(moment * SR)
        for i in range(int(0.5 * SR)):
            t = i / SR
            env = math.exp(-t * 8.5)
            value = 0.035 * env * math.sin(2 * math.pi * 55.0 * t)
            if start + i < n:
                bed_l[start + i] += value
                bed_r[start + i] += value
        moment += 1.0

    # ---- scene hits --------------------------------------------------
    def hit(at: float, amp: float = 0.075) -> None:
        start = int(at * SR)
        for i in range(int(0.45 * SR)):
            t = i / SR
            freq = 46 + 58 * math.exp(-t * 15)
            env = math.exp(-t * 12)
            value = amp * env * math.sin(2 * math.pi * freq * t)
            if start + i < n:
                bed_l[start + i] += value
                bed_r[start + i] += value
        for i in range(int(0.03 * SR)):
            t = i / SR
            value = amp * 0.4 * math.exp(-t * 100) * RNG.uniform(-1, 1)
            if start + i < n:
                bed_l[start + i] += value
                bed_r[start + i] += value

    # a light driving kick under the pitch, four to the bar at 120 BPM
    beat = 0.0
    while beat < total - 1.0:
        hit(beat, 0.024)
        beat += 0.5

    for scene in story["scenes"]:
        hit(scene["start"] + 0.04, 0.060 if scene["layout"] == "mark" else 0.078)

    # riser into the passport
    passport = next(scene for scene in story["scenes"] if scene["layout"] == "score")
    rise_start = passport["start"] - 2.0
    rise_end = passport["start"] - 0.1
    begin = int(rise_start * SR)
    length = int((rise_end - rise_start) * SR)
    phase = 0.0
    for i in range(length):
        t = i / SR
        frac = i / max(1, length - 1)
        freq = 180.0 * (520.0 / 180.0) ** frac
        phase += 2 * math.pi * freq / SR
        value = 0.020 * math.sin(math.pi * frac) ** 1.2 * math.sin(phase)
        if begin + i < n:
            bed_l[begin + i] += value
            bed_r[begin + i] += value

    # resolve chord at the passport, low A at the mark
    def chord(at: float, freqs: list[float], amp: float, decay: float) -> None:
        start = int(at * SR)
        for i in range(int(min(decay, total - at) * SR)):
            t = i / SR
            env = math.exp(-t * 1.5)
            value = 0.0
            for freq in freqs:
                value += math.sin(2 * math.pi * freq * t + freq)
            value *= amp * env / len(freqs)
            if start + i < n:
                bed_l[start + i] += value
                bed_r[start + i] += value

    chord(passport["start"] + 0.1, [220.0, 261.63, 329.63, 440.0], 0.030, 3.2)
    mark = next(scene for scene in story["scenes"] if scene["layout"] == "mark")
    chord(mark["start"] + 0.1, [110.0, 220.0, 329.63], 0.026, 4.0)

    # ---- voice mix and ducking --------------------------------------
    mix_l = [0.0] * n
    mix_r = [0.0] * n
    voice_gain = [1.0] * n
    for scene in story["scenes"]:
        voice_l, voice_r = read_wav(VIDEO / scene["voice_file"])
        start = int(float(scene["voice_start"]) * SR)
        end = start + len(voice_l)
        for i, value in enumerate(voice_l):
            if start + i < n:
                mix_l[start + i] += value
        for i, value in enumerate(voice_r):
            if start + i < n:
                mix_r[start + i] += value
        duck_from = max(0, start - int(0.25 * SR))
        duck_to = min(n, end + int(0.25 * SR))
        for i in range(duck_from, duck_to):
            if i < start:
                frac = (i - duck_from) / max(1, start - duck_from)
            elif i > end:
                frac = 1.0 - (i - end) / max(1, duck_to - end)
            else:
                frac = 1.0
            target = 1.0 - 0.62 * frac
            voice_gain[i] = min(voice_gain[i], target)

    peak = 0.0
    for i in range(n):
        l = mix_l[i] + bed_l[i] * voice_gain[i]
        r = mix_r[i] + bed_r[i] * voice_gain[i]
        l = math.tanh(l * 1.05)
        r = math.tanh(r * 1.05)
        peak = max(peak, abs(l), abs(r))
        mix_l[i] = l
        mix_r[i] = r
    gain = 0.86 / peak if peak else 1.0

    frames = bytearray()
    for i in range(n):
        t = i / SR
        fade = min(1.0, t / 0.08, (total - t) / 0.9)
        l = math.tanh(mix_l[i] * gain) * fade
        r = math.tanh(mix_r[i] * gain) * fade
        frames += struct.pack("<hh", int(l * 32767), int(r * 32767))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(bytes(frames))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024 / 1024:.1f} MB, {total:.2f}s, peak {peak:.2f})")


if __name__ == "__main__":
    main()
