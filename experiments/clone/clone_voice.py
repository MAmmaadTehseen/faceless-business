"""Clone the owner's voice with Chatterbox (MIT) and narrate a script.

Usage (run with the voice venv; `run.sh voice` does this):
  python clone_voice.py --ref input/voice_ref.wav --text input/sample_script.txt --out results/narration.wav
Outputs: <out>.wav (24 kHz mono), <out>.words.json (faster-whisper word timestamps), <out>.srt, <out>.metrics.json
Fallback: --backend openvoice --base-wav <existing TTS narration> converts an existing narration's tone
to the reference voice (OpenVoice v2, MIT); it needs a base TTS and cannot synthesise from text alone.
"""
import sys, re, argparse, resource, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import numpy as np, soundfile as sf, torch

def sentences(text):
    text = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for p in parts:                       # Chatterbox degrades past ~300 chars; split long sentences at commas/semicolons
        while len(p) > 280:
            cut = max(p.rfind(c, 0, 280) for c in ",;:")
            if cut < 60: cut = p.rfind(" ", 0, 280)
            out.append(p[:cut + 1].strip()); p = p[cut + 1:].strip()
        if p: out.append(p)
    # Chatterbox has ~45 s of fixed CPU cost per generate() call on this laptop, so merge short sentences
    # into chunks of up to ~220 characters instead of one call per sentence.
    merged, cur = [], ""
    for s in out:
        if cur and len(cur) + 1 + len(s) > 220: merged.append(cur); cur = s
        else: cur = (cur + " " + s).strip()
    if cur: merged.append(cur)
    return merged

def chatterbox(ref, text, exaggeration, cfg, seed):
    from chatterbox.tts import ChatterboxTTS
    torch.manual_seed(seed)
    snap = next((AVATAR / "voice/hf/hub/models--ResembleAI--chatterbox/snapshots").iterdir())
    t = time.monotonic(); model = ChatterboxTTS.from_local(snap, "cpu"); load = time.monotonic() - t
    t = time.monotonic(); model.prepare_conditionals(str(ref), exaggeration=exaggeration); cond = time.monotonic() - t
    pieces, rows = [], []
    for i, s in enumerate(sentences(text)):
        guard(); t = time.monotonic()
        wav = model.generate(s, exaggeration=exaggeration, cfg_weight=cfg).squeeze().detach().numpy()
        wav = trim(wav, model.sr)
        rows.append(dict(i=i, text=s, wall_s=round(time.monotonic() - t, 2), audio_s=round(len(wav) / model.sr, 2)))
        print(rows[-1], flush=True)
        pieces += [wav, np.zeros(int(0.18 * model.sr), np.float32)]
    return np.concatenate(pieces), model.sr, dict(load_s=load, conditioning_s=cond, chunks=rows)

def trim(wav, sr, thresh=0.01, pad=0.08):
    """Chatterbox sometimes leaves long tails/breaths; trim to the last audible sample + pad."""
    a = np.abs(wav); idx = np.where(a > thresh)[0]
    if len(idx) == 0: return wav
    return wav[max(0, idx[0] - int(pad * sr)): min(len(wav), idx[-1] + int(pad * sr))]

def openvoice(ref, base_wav):
    sys.path.insert(0, str(AVATAR / "vendor/OpenVoice"))
    from openvoice.api import ToneColorConverter, OpenVoiceBaseClass
    t = time.monotonic(); model = ToneColorConverter.__new__(ToneColorConverter)
    OpenVoiceBaseClass.__init__(model, str(AVATAR / "models/openvoice/config.json"), device="cpu")
    model.watermark_model = None; model.version = getattr(model.hps, "_version_", "v1")
    model.load_ckpt(str(AVATAR / "models/openvoice/checkpoint.pth")); load = time.monotonic() - t
    target = model.extract_se(str(ref)); source = model.extract_se(str(base_wav))
    t = time.monotonic(); audio = model.convert(str(base_wav), source, target, output_path=None, tau=0.3)
    return audio, model.hps.data.sampling_rate, dict(load_s=load, chunks=[dict(wall_s=time.monotonic() - t, audio_s=len(audio) / model.hps.data.sampling_rate)])

def timestamps(wav_path):
    from faster_whisper import WhisperModel
    # Reuse the recap tool's cached Systran/faster-whisper-small (MIT) from ~/.cache/huggingface; no download.
    snaps = sorted((Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots").glob("*"))
    if not snaps: raise SystemExit("faster-whisper-small is not cached; run the repo recap tool once or download it")
    model = WhisperModel(str(snaps[-1]), device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(wav_path), language="en", word_timestamps=True, beam_size=3, vad_filter=False)
    words = [dict(word=w.word, start=round(w.start, 3), end=round(w.end, 3), p=round(w.probability, 2)) for s in segs for w in s.words]
    return words

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True); ap.add_argument("--text", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--backend", default="chatterbox", choices=["chatterbox", "openvoice"]); ap.add_argument("--base-wav")
    ap.add_argument("--exaggeration", type=float, default=0.4); ap.add_argument("--cfg", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=1234); ap.add_argument("--max-ref-s", type=float, default=30)
    ap.add_argument("--threads", type=int, default=4); ap.add_argument("--no-timestamps", action="store_true")
    ap.add_argument("--timestamps-only", action="store_true", help="skip synthesis; only re-run word timing on an existing --out")
    a = ap.parse_args(); guard()
    torch.set_num_threads(a.threads); torch.set_num_interop_threads(1)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); work = R / "work"; work.mkdir(exist_ok=True)
    # Reference: cleaned, mono, and limited to the first N seconds (Chatterbox uses ~10 s for the speaker embedding).
    ref = to_wav(a.ref, work / "ref_clean.wav")
    data, sr = sf.read(ref); data = data[: int(a.max_ref_s * sr)]; sf.write(ref, data, sr)
    text = Path(a.text).read_text()
    if a.timestamps_only:
        words = timestamps(out); write_json(out.with_suffix(".words.json"), words); words_to_srt(words, out.with_suffix(".srt")); print(len(words), "words"); return
    t0 = time.monotonic()
    if a.backend == "chatterbox":
        audio, sr, metrics = chatterbox(ref, text, a.exaggeration, a.cfg, a.seed)
    else:
        if not a.base_wav: sys.exit("--backend openvoice needs --base-wav (an existing narration to convert)")
        audio, sr, metrics = openvoice(ref, a.base_wav)
    total = time.monotonic() - t0
    audio = audio / max(1e-6, np.abs(audio).max()) * 0.9
    sf.write(out, audio.astype(np.float32), sr)
    audio_s = len(audio) / sr
    metrics.update(backend=a.backend, audio_s=round(audio_s, 2), wall_s=round(total, 1), inference_s=round(sum(c["wall_s"] for c in metrics["chunks"]), 1),
                   audio_seconds_per_cpu_minute=round(audio_s / (total / 60), 2), rtf=round(total / audio_s, 2),
                   peak_rss_gib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2), threads=a.threads, ref=str(a.ref))
    write_json(out.with_suffix(".metrics.json"), metrics)        # saved before timing so a whisper failure keeps the benchmark
    if not a.no_timestamps:
        t = time.monotonic(); words = timestamps(out); metrics["timestamps_s"] = round(time.monotonic() - t, 1)
        write_json(out.with_suffix(".words.json"), words); words_to_srt(words, out.with_suffix(".srt"))
        script_words = re.findall(r"[A-Za-z0-9']+", text.lower()); asr_words = re.findall(r"[A-Za-z0-9']+", " ".join(w["word"] for w in words).lower())
        metrics["asr_word_count"] = len(asr_words); metrics["script_word_count"] = len(script_words)
    write_json(out.with_suffix(".metrics.json"), metrics)
    print(json.dumps({k: v for k, v in metrics.items() if k != "chunks"}, indent=2))

if __name__ == "__main__":
    main()
