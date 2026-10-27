# OVERTURN — 76-second pitch film

**File:** `video/out/overturn-film.mp4` — 1920 × 1080, 30 fps, 76.0 s,
H.264/AAC. **Narration:** The Podcaster (VoiceStudio / OmniVoice; young
Australian woman, high pitch), speed 1.05. **Music and effects:** a 120 BPM
driving bed that ducks under the voice.

**Also:** `video/out/overturn-film.gif` (opening 8 s, 640 px),
`video/out/overturn-poster.png`, and a copy at `out/overturn-film.mp4`.

## The pitch

Ava's insurer said no. Four reasons. Three are wrong; the fourth is a document
that is genuinely missing.

OVERTURN reads the policy, the clinical record and the codes, catches the
experimental clause that does not apply, the contrast code that is not the
file's code, the twelve weeks of physiotherapy the denial says does not exist,
and the missing specialist letter it refuses to invent. It runs the agent loop
in public: Planner → Reconciler → Critic → Advocate → Reporter, with a re-query
when the Advocate lands a blow.

The appeal is **84 / 100 — solid — conditional**. Send the one missing letter
and it becomes **100 / ready**. That is the pitch: not a score, a next action.

## Post

> Her insurer said no. Four reasons.
>
> Three were wrong. One was a letter that was actually missing.
>
> OVERTURN reads the policy, the record and the codes — then answers every
> reason with evidence. It shows the agent loop, the re-query, and the one
> document it refuses to invent.
>
> 84. Solid. Conditional. Send the letter: 100. Ready.
>
> The denial, answered with evidence.

## How it was made

- One paused GSAP timeline, `window.seek(t)`, the huashu-motion fonts and its
  signature in the last 1.3 s.
- Narration generated locally with VoiceStudio (The Podcaster profile,
  `feat_13_the_podcaster`) and mixed with a synthesised 120 BPM bed.
- Frames rendered through Playwright against the installed Chromium; encoded
  with FFmpeg; mastered to −14 LUFS / −1.5 dBTP.
- The film is a pitch, not the required 1–4 minute workflow demo. The demo
  still needs a screen recording of the live system.

## Licence

The OmniVoice weights are non-commercial (CC-BY-NC and related terms). This
film is a non-commercial hackathon demo. See `THIRD_PARTY.md`. Do not reuse the
narration commercially without replacing the voice or clearing the model terms.
