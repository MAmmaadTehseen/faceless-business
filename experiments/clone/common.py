"""Shared paths/env for the clone experiment. Local only: no network, no .env, no Claude."""
import os, json, time, shutil, pathlib, subprocess
R = pathlib.Path(__file__).resolve().parent
AVATAR = R.parent / "avatar"                     # reused models, vendor code and venvs
VOICE_PY = AVATAR / "voice/.venv/bin/python"      # Chatterbox + faster-whisper
FACE_PY = AVATAR / ".venv/bin/python"             # torch CPU + cv2 (MuseTalk UNet/VAE use voice venv)
FLOOR = 20 * 2**30

for k, v in {"TMPDIR": "work/tmp", "XDG_CACHE_HOME": "work/cache", "NUMBA_CACHE_DIR": "work/cache/numba",
             "MPLCONFIGDIR": "work/cache/mpl", "TORCH_HOME": str(AVATAR / "cache/torch")}.items():
    os.environ.setdefault(k, str(R / v) if not v.startswith("/") else v)
    pathlib.Path(os.environ[k]).mkdir(parents=True, exist_ok=True)
os.environ.update(CUDA_VISIBLE_DEVICES="", HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                  OMP_NUM_THREADS=os.environ.get("OMP_NUM_THREADS", "4"), MKL_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4")

def guard(extra=0):
    free = shutil.disk_usage(R).free - extra
    if free < FLOOR:
        raise RuntimeError(f"STOP: free disk {free/2**30:.1f} GiB would fall below the 20 GiB floor")

def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], text=True)
    return float(out.strip())

def to_wav(src, dst, sr=24000):
    """Any phone recording -> mono PCM WAV at sr. Light high-pass + loudness normalisation."""
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(sr),
                    "-af", "highpass=f=70,loudnorm=I=-20:TP=-2:LRA=9", "-c:a", "pcm_s16le", str(dst)], check=True)
    return dst

def write_json(path, obj):
    pathlib.Path(path).write_text(json.dumps(obj, indent=2))

def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def words_to_srt(words, path, max_words=4, max_dur=2.5):
    """Group word timestamps into short caption cues."""
    cues, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["end"] - cur[0]["start"] > max_dur or cur[-1]["word"].rstrip().endswith((".", "!", "?"))):
            cues.append(cur); cur = []
        cur.append(w)
    if cur: cues.append(cur)
    lines = []
    for i, c in enumerate(cues, 1):
        lines += [str(i), f"{srt_time(c[0]['start'])} --> {srt_time(c[-1]['end'])}", " ".join(w["word"].strip() for w in c), ""]
    pathlib.Path(path).write_text("\n".join(lines))
    return cues
