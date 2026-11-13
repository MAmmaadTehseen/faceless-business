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
