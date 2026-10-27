# Materials — OVERTURN workflow demo

Every piece on screen comes from the product in this repository or from a
font the repository already uses. There are no stock images, invented UI or
placeholder data.

| Piece | Source | Notes / licence |
|---|---|---|
| Case facts, denial reasons, rebuttals, score, counterfactuals | `out/appeal_packet.json` — a real `python -m overturn.run --case ava` output | Generated 27 Oct 2026; SAMPLE_MODE |
| Terminal lines | `python -m overturn.run --case ava --out out/` stdout and `out/trace.jsonl` | Real output, abbreviated to fit the frame |
| Evidence map screenshot | `out/receipt.html`, captured with `om still` | Real generated HTML; no retouching |
| Seven source tables and row counts | `data/sources/*.csv`, `scripts/register_zetaris_sources.sql` | Synthetic data authored for this project |
| Hash head `387f5f91…` | `out/appeal_packet.json` → `provenance.head_hash` | Real SHA-256 chain output |
| Archivo Black | `video/assets/fonts/ArchivoBlack-400.woff` | SIL Open Font License |
| Inter (variable) | `video/assets/fonts/Inter-var.woff` | SIL Open Font License |
| Narration | VoiceStudio / OmniVoice, `feat_13_the_podcaster`, generated locally from `script.txt` | OmniVoice weights are non-commercial (CC-BY-NC and related terms); this is a non-commercial hackathon film. See `THIRD_PARTY.md` |
| Music and effects | `om sound` from the declared `OM.music` direction and `OM.sfx` hits | Synthesized by the tool |

The film is a workflow demo, not a live sponsor run. The screen says
**SAMPLE_MODE** where that distinction matters: the same control flow with
deterministic model stubs and a read-only SQLite mirror of the Zetaris tables.
The sponsor scene describes the live wiring; it does not claim a live call.
