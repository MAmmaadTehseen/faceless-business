# Owner voice + face clone (local, CPU, free)

Local research under `experiments/clone/`. Clones **the owner's own** voice and face from recordings the owner
supplies, and renders a sample presenter clip. No network inference, no uploads, no Claude calls, no `.env`,
no production source edits. Recordings, renders, weights and environments are gitignored.

Because the likeness is the owner's, the likeness-rights blocker from `experiments/avatar/REPORT.md` is gone.
Model and code licences still apply and are listed below.

## What the owner must supply (`input/`)

| file | content |
|---|---|
| `input/voice_ref.wav` (or `.m4a`) | 3–5 min reading any English text; quiet room, phone mic ~15 cm away, no music/filters. Only the first 30 s are used for the speaker embedding (`--max-ref-s`), so make the opening clean. |
| `input/face.mp4` | 20–30 s, 1080p (portrait 1080×1920 is best; landscape is cropped and upscaled), front-facing, even light, plain background, neutral expression, **mouth closed**, small natural head movement, normal blinks. No beauty filter/portrait blur. |
| `input/script_read.m4a` (optional) | ~60 s reading `input/sample_script.txt`, for a real-vs-clone comparison. |

## Setup

Disk on this laptop had 25 GiB free with a 20 GiB floor, so **no second multi-gigabyte environment was created**.
The scripts reuse the environments and MIT-licensed weights already downloaded for `experiments/avatar`:

- `experiments/avatar/voice/.venv` — Chatterbox 0.1.7, torch 2.6 (CUDA wheel, runs CPU-only via `CUDA_VISIBLE_DEVICES=""`),
  transformers 5.2, diffusers 0.29, plus `faster-whisper 1.2.1` added by this experiment (≈1.7 GB download incl. onnxruntime/av).
- `experiments/avatar/.venv` — torch 2.15 CPU + OpenCV (used by `pick_roi.py` and `compose.py`).
- Weights: `experiments/avatar/voice/hf` (Chatterbox), `experiments/avatar/models/{musetalk,sd-vae,whisper-tiny,openvoice}`,
  and the recap tool's `~/.cache/huggingface/.../faster-whisper-small` for word timings.

To recreate from scratch (needs ≈8 GB free): `uv venv .venv --python 3.11`, install CPU torch from the PyTorch CPU index,
then `chatterbox-tts==0.1.7 faster-whisper==1.2.1 diffusers==0.29 opencv-python-headless`, clone MuseTalk 1.5 for its
`musetalk/models/unet.py` PositionalEncoding, and download the MIT weights listed in the licence table.

## Commands

```bash
cd experiments/clone
./run.sh voice --ref input/voice_ref.wav --text input/sample_script.txt --out results/narration.wav   # Chatterbox clone + word timings (.words.json, .srt, .metrics.json)
./run.sh roi input/face.mp4 --t 1.0                 # suggests a square face ROI, writes work/roi_check.png; override with --roi x,y,w,h
./run.sh face --face input/face.mp4 --audio results/narration.wav --roi X,Y,W,H --out results/presenter.mp4 --portrait   # MuseTalk lip sync
./run.sh compose --presenter results/presenter.mp4 --audio results/narration.wav --srt results/narration.srt --out results/sample_60s.mp4 --layout hybrid [--stock clip.mp4]
```
`face` accepts `--limit S` to render only the first S seconds, `--batch N`, `--fps`. OpenVoice fallback
(tone-converts an existing narration, cannot synthesise from text): `./run.sh voice --backend openvoice --base-wav kokoro.wav ...`.

## Licences

| component | licence | role here | commercial use |
|---|---|---|---|
| Chatterbox 0.1.7 code + ResembleAI checkpoints | MIT | voice clone TTS (Perth watermark kept) | yes |
| OpenVoice v2 code + official weights | MIT | fallback tone conversion | yes |
| MuseTalk 1.5 code + `unet.pth` | MIT, author permits commercial use of its models | lip sync (manual ROI path only) | yes |
| openai/whisper-tiny | MIT | MuseTalk audio features | yes |
| stabilityai/sd-vae-ft-mse | MIT | MuseTalk latent codec | yes |
| Systran/faster-whisper-small, CTranslate2 | MIT | word timestamps / captions | yes |
| OpenCV + bundled Haar cascade | Apache-2.0 | frame IO, ROI suggestion | yes |
| ffmpeg (system) | LGPL/GPL build dependent | mux/compose | yes (tool use) |
| NOT used | — | InsightFace, DWPose, S3FD, GFPGAN, CodeFormer, Wav2Lip, F5-TTS, LatentSync | not cleared |

## Measurements (2026-11-13, synthetic placeholder, **under heavy concurrent load**)

The owner's recordings had not arrived, so the probes used the research-only fixtures from `experiments/avatar`
(Kokoro `voice/ref.wav` as the voice reference; the anonymous `idle_loop.mp4` face, 512×512). Those outputs are
**not publishable** (no likeness rights) and live only in `work/`. During every measurement another session was
running ffmpeg + the recap batch at ~600 % CPU (load average 11–14 on a 4-core i7-1185G7), so the numbers below
are pessimistic; the clean figures from `experiments/avatar/REPORT.md` (same models, idle laptop) are shown beside them.

| step | this run (loaded laptop) | earlier clean run | notes |
|---|---|---|---|
| Chatterbox, 77-word excerpt → 25.7 s audio | 640 s wall, RTF 24.9, **2.4 s audio per CPU minute**, 6.7 GiB RSS | RTF 7.0 (≈8.6 s audio/min) | ≈45 s fixed cost per `generate()` call; sentences are now merged into ≤220-char chunks (6 calls for the 165-word sample script instead of 12) |
| faster-whisper-small word timings, 25.7 s | 11 s | — | 76/77 script words recognised; peak 0.90, no clipping, RMS −21.8 dBFS |
| MuseTalk 376-px ROI, batch 1 | 11.1 s/frame = **277 min per output minute** | 4.1 s/frame (≈104 min/min) | 7.3 GiB RSS |
| MuseTalk, batch 8 | 8.9 s/frame = 224 min per output minute | — | batching helps ~20 % |
| pose encode (VAE) for 22 source frames | 147–158 s | 50 s | once per source clip |

Projection for one 10-minute long video with the presenter visible throughout: 17–46 h of CPU for the face alone.
That is not viable. With the **hybrid layout** (presenter full-screen for an 8 s hook and 5 s close, corner for
about 40 % of the middle, stock otherwise) a 10-minute video needs ≈4.2 min of lip-synced frames: **≈7 h loaded /
≈4.5 h clean**, plus Chatterbox ≈70–170 min for the narration. A 60-second Short needs ≈1–1.5 h face + ≈7–25 min voice.
Per week (9 longs + 40 Shorts) that is roughly 80–100 h of laptop CPU: only feasible if the laptop renders
overnight and the pipeline keeps the presenter to hook/close plus a few corner segments, or if renders move to a
GPU box.

## Quality verdict (placeholder fixture; owner footage will differ)

- **Lip sync:** the mouth does open and close with the speech (see `work/probe_b8_contact.png`), but the regenerated
  lower face is visibly softer than the eyes and forehead: MuseTalk works at 256×256, so anything above ~300 px of
  face width is an upscale. At 1080×1920 full-screen with a 600–700 px face this blur will be obvious; in a
  **420 px corner box** the face is ~250 px wide and the generated region is at native resolution.
- **Voice:** I cannot judge timbre by ear. The ASR recovered 76/77 words, levels are clean, no clipping. Chatterbox
  paces each chunk itself, so captions must come from its output (`.srt`), not from the script timing. The owner
  must do the listening gate (headphones + phone speaker; names, numbers, chunk joins) before any use.
- **Head motion:** the source clip loops with a 12-frame dissolve at the wrap; blinks and head motion repeat with
  the clip length, so a 30 s recording gives a 30 s cycle. Longer, calmer face footage looks better.

## Recommendation

1. **Voice only** is the first thing worth using: it costs no video rendering, the licence is clean (MIT), and if
   the owner's listening gate passes it replaces Kokoro for one channel at a time (YouTube's distinct-channel rule
   still needs different voices per channel, so clone one channel only, or keep Kokoro on the other two).
2. **Corner presenter** for the hook and a few middle segments is the only face use that is both visually
   defensible and affordable on this laptop (~1 h per Short, ~5 h per long overnight).
3. **Full-screen presenter**: not with MuseTalk on CPU at 1080p. If the owner wants full-screen, record the real
   hook and close on camera (the earlier report's advice) and let the clone only carry the voice.
4. Do not integrate into `pipeline/` until the owner has reviewed `results/sample_60s.mp4` made from their own
   recordings; the commands above produce it once `input/` is populated.

## Files
`common.py` (paths, disk floor, WAV cleanup, SRT writer) · `clone_voice.py` · `pick_roi.py` · `render_face.py` · `compose.py` · `run.sh` ·
`work/` (probes, gitignored) · `results/` (final sample, gitignored) · `input/sample_script.txt` (Future Work excerpt used for the sample).
