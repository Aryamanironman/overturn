#!/usr/bin/env python3
"""Generate the OVERTURN pitch narration with VoiceStudio.

Voice: The Podcaster (female, young adult, high pitch, Australian accent).
Backend: http://127.0.0.1:3900 (VoiceStudio / OmniVoice).

The first call loads the OmniVoice model; later calls are faster.

    python video/make_voice.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx

VIDEO = Path(__file__).resolve().parent
SOURCE = VIDEO / "film_source.json"
VOICE_DIR = VIDEO / "voice"
STORY = VIDEO / "film.json"
STORY_JS = VIDEO / "film-data.js"

BASE = "http://127.0.0.1:3900"
ARCHETYPE = "feat_13_the_podcaster"
SPEED = 1.05
START_PAD = 0.6


def ensure_profile() -> str:
    """Reuse The Podcaster profile, creating it if this VoiceStudio is fresh."""
    try:
        profiles = httpx.get(BASE + "/profiles", timeout=30).json()
        if isinstance(profiles, dict):
            profiles = profiles.get("profiles", profiles.get("items", []))
        for profile in profiles if isinstance(profiles, list) else []:
            name = str(profile.get("name", "")).lower()
            if "podcaster" in name:
                return str(profile.get("profile_id") or profile.get("id"))
    except Exception:
        pass
    response = httpx.post(BASE + f"/archetypes/{ARCHETYPE}/use", timeout=120)
    response.raise_for_status()
    payload = response.json()
    return str(payload.get("profile_id") or payload.get("id"))


def synth(text: str, wav: Path, profile_id: str) -> None:
    payload = {
        "model": "omnivoice",
        "voice": profile_id,
        "input": text,
        "response_format": "wav",
        "speed": SPEED,
    }
    response = httpx.post(BASE + "/v1/audio/speech", json=payload, timeout=900)
    if response.status_code != 200 or not response.content.startswith(b"RIFF"):
        raise RuntimeError(f"VoiceStudio {response.status_code}: {response.text[:500]}")
    wav.write_bytes(response.content)


def convert(source: Path, target: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(source),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=9",
            "-ar", "44100", "-ac", "2", str(target),
        ],
        check=True,
    )


def duration(path: Path) -> float:
    output = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ],
        text=True,
    )
    return float(output.strip())


def main() -> None:
    VOICE_DIR.mkdir(exist_ok=True)
    scenes = json.loads(SOURCE.read_text(encoding="utf-8"))
    profile_id = ensure_profile()
    cursor = START_PAD
    out = []
    for index, scene in enumerate(scenes, start=1):
        stem = f"{index:02d}-{scene['id']}"
        raw = VOICE_DIR / f"{stem}-raw.wav"
        wav = VOICE_DIR / f"{stem}.wav"
        synth(scene["voice"], raw, profile_id)
        convert(raw, wav)
        length_seconds = duration(wav)
        length = max(float(scene["hold"]), length_seconds + 0.6)
        out.append({
            **scene,
            "index": index,
            "voice_file": f"voice/{stem}.wav",
            "voice_duration": round(length_seconds, 3),
            "voice_start": round(cursor + 0.15, 3),
            "start": round(cursor, 3),
            "end": round(cursor + length, 3),
            "duration": round(length, 3),
        })
        cursor += length
        print(f"{scene['id']:10s} voice {length_seconds:5.2f}s  scene {length:5.2f}s", flush=True)

    total = round(cursor + 1.0, 3)
    payload = {"voice": "The Podcaster", "profile_id": profile_id, "scenes": out, "total": total}
    STORY.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    STORY_JS.write_text(
        "window.STORY = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"total {total:.2f}s  profile {profile_id}")


if __name__ == "__main__":
    main()
