# Materials — OVERTURN pitch film

Everything on screen is the product's own output, the product's own type, or a
font already in the repository. No stock images, no invented UI.

| Piece | Source | Notes / licence |
|---|---|---|
| Case facts, denial reasons, score, hash head | `out/appeal_packet.json` from a real `python -m overturn.run --case ava` run | SAMPLE_MODE output, 27 Oct 2026 |
| Source table names and row counts | `data/sources/*.csv`, `scripts/register_zetaris_sources.sql` | Synthetic data authored for this project |
| Evidence map screenshot | `out/receipt.html`, captured with `om still` | Real generated HTML |
| Ledger rows and chain blocks | `out/trace.jsonl`, `out/appeal_packet.json` | Real output, abbreviated for the frame |
| Archivo Black | `demo-film/assets/fonts/ArchivoBlack-400.woff` | SIL Open Font License |
| Inter (variable) | `demo-film/assets/fonts/Inter-var.woff` | SIL Open Font License |
| Narration | Kokoro TTS (`af_heart`), built into huashu-motion, generated from `script.txt` | Local synthesis; no third-party recording |
| Music and effects | `om sound` from the declared `OM.music` direction and `OM.sfx` hits | Synthesized by the tool |

The film is a pitch, not a live sponsor run. The spoken line "Built with
Zetaris, Meterless, and NVIDIA Nemotron" describes the integration in the
repository; the run shown is SAMPLE_MODE, with deterministic model stubs and a
read-only SQLite mirror of the Zetaris tables. See `SPONSOR_TECH.md` for the
verified/live split.
