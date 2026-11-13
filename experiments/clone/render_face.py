"""MuseTalk 1.5 manual-ROI lip sync on the owner's face video (CPU, no detector/parser/enhancer weights).

  python render_face.py --face input/face.mp4 --audio results/narration.wav --roi x,y,w,h --out results/presenter.mp4
Options: --limit S (only first S seconds of audio), --fps 25, --portrait (1080x1920 crop around the face), --batch 4,
--loop crossfade frames at the video wrap (default 12). Prints seconds per frame and writes <out>.metrics.json.
Models reused from experiments/avatar/models: MuseTalk UNet (MIT), whisper-tiny (MIT), sd-vae-ft-mse (MIT).
"""
import sys, argparse, resource, time, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from common import *
sys.path.append(str(AVATAR / "deps")); sys.path.insert(0, str(AVATAR / "vendor/MuseTalk"))
import cv2, numpy as np, soundfile as sf, torch, librosa
from diffusers import AutoencoderKL, UNet2DConditionModel
from transformers import WhisperModel, WhisperFeatureExtractor
from musetalk.models.unet import PositionalEncoding
cv2.setNumThreads(1)

def softmask(h, w, cx, cy, rx, ry, feather=0.3):
    yy, xx = np.mgrid[:h, :w]; q = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    a = np.clip((1 - q) / feather, 0, 1); return (a * a * (3 - 2 * a)).astype(np.float32)[..., None]

class Colour:                      # slow-moving per-channel offset so generated skin matches source lighting
    def __init__(self): self.d = None
    def apply(self, gen, base, mask):
        ring = (mask[..., 0] > 0.03) & (mask[..., 0] < 0.35)
        d = np.clip(np.median(base[ring].astype(float) - gen[ring], axis=0), -30, 30)
        self.d = d if self.d is None else 0.15 * d + 0.85 * self.d
        return np.clip(gen.astype(float) + self.d, 0, 255).astype(np.float32)

def read_video(path, max_frames=2000):
    cap = cv2.VideoCapture(str(path)); fps = cap.get(cv2.CAP_PROP_FPS) or 25; frames = []
    while len(frames) < max_frames:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    cap.release(); return frames, fps

def portrait_crop(frames, roi):
    """Landscape phone video -> 9:16 column centred on the face, scaled to 1080x1920 (upscale if needed)."""
    H, W = frames[0].shape[:2]; x, y, w, h = roi
    if W * 16 <= H * 9:  return frames, roi, (W, H)
    cw = int(H * 9 / 16); cx = min(max(x + w // 2, cw // 2), W - cw // 2); x0 = cx - cw // 2
    return [f[:, x0:x0 + cw] for f in frames], (x - x0, y, w, h), (cw, H)

def loop_frames(frames, n_needed, xfade):
    """Forward play; at the wrap, dissolve the last xfade frames into the first ones (no reverse play)."""
    base = frames[:]
    if xfade and len(base) > 2 * xfade:
        for k in range(xfade):
            a = (k + 1) / (xfade + 1); base[-xfade + k] = cv2.addWeighted(base[-xfade + k], 1 - a, frames[k], a, 0)
    out = []
    while len(out) < n_needed: out += base
    return out[:n_needed]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--face", required=True); ap.add_argument("--audio", required=True); ap.add_argument("--roi", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=float); ap.add_argument("--fps", type=int, default=25); ap.add_argument("--portrait", action="store_true")
    ap.add_argument("--batch", type=int, default=4); ap.add_argument("--loop", type=int, default=12); ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--max-src-frames", type=int, default=900)
    a = ap.parse_args(); guard(); torch.set_num_threads(a.threads); torch.set_num_interop_threads(1); torch.manual_seed(1234)
    t = time.monotonic()
    vae = AutoencoderKL.from_pretrained(AVATAR / "models/sd-vae", local_files_only=True).eval(); vae.enable_slicing()
    cfg = json.loads((AVATAR / "models/musetalk/musetalk.json").read_text()); unet = UNet2DConditionModel(**cfg)
    unet.load_state_dict(torch.load(AVATAR / "models/musetalk/unet.pth", map_location="cpu", weights_only=True)); unet.eval(); pe = PositionalEncoding(384)
    whisper = WhisperModel.from_pretrained(AVATAR / "models/whisper-tiny", local_files_only=True).eval()
    fe = WhisperFeatureExtractor.from_pretrained(AVATAR / "models/whisper-tiny", local_files_only=True)
    load = time.monotonic() - t; print("loaded", round(load, 1), flush=True)

    # ---- source frames
    frames, src_fps = read_video(a.face, a.max_src_frames)
    roi = tuple(int(v) for v in a.roi.split(","))
    if a.portrait: frames, roi, _ = portrait_crop(frames, roi)
    if abs(src_fps - a.fps) > 0.5:                                   # resample by index to the output fps
        idx = np.round(np.arange(0, len(frames), src_fps / a.fps)).astype(int); frames = [frames[i] for i in idx if i < len(frames)]
    x, y, w, h = roi; H, W = frames[0].shape[:2]; print(f"source {W}x{H} {len(frames)} frames @ {a.fps} fps, roi {roi}", flush=True)

    # ---- audio -> whisper features (50 per second, 2 per frame at 25 fps)
    au, sr = sf.read(a.audio)
    if au.ndim > 1: au = au.mean(1)
    if a.limit: au = au[: int(a.limit * sr)]
    if sr != 16000: au = librosa.resample(au.astype(np.float32), orig_sr=sr, target_sr=16000); sr = 16000
    n = int(np.ceil(len(au) / sr * a.fps)); feats = []
    t = time.monotonic()
    with torch.inference_mode():
        for s in range(0, len(au), 30 * sr):                             # whisper windows of 30 s
            chunk = au[s:s + 30 * sr]; inp = fe(chunk, sampling_rate=sr, return_tensors="pt").input_features
            hs = torch.stack(whisper.encoder(inp, output_hidden_states=True).hidden_states, dim=2)[:, : int(len(chunk) / sr * 50)]
            feats.append(hs)
    feats = torch.cat(feats, 1); feats = torch.cat([torch.zeros_like(feats[:, :4]), feats, torch.zeros_like(feats[:, :12])], 1)
    step = 50 / a.fps
    audio = torch.cat([feats[:, int(i * step): int(i * step) + 10] for i in range(n)], 0).reshape(n, 50, 384)
    print("audio features", round(time.monotonic() - t, 1), "s for", n, "frames", flush=True)

    # ---- encode each source pose once
    t = time.monotonic(); seq = loop_frames(frames, n, a.loop); uniq = {}
    latents = []
    with torch.inference_mode():
        for i, f in enumerate(seq):
            key = id(f)
            if key not in uniq:
                crop = cv2.resize(f[y:y + h, x:x + w], (256, 256), interpolation=cv2.INTER_AREA)
                ten = torch.from_numpy(crop[:, :, ::-1].copy()).permute(2, 0, 1).float()[None] / 255
                masked = ten.clone(); masked[:, :, 128:] = 0
                lat = torch.cat([vae.encode(masked * 2 - 1).latent_dist.mode(), vae.encode(ten * 2 - 1).latent_dist.mode()], 1) * vae.config.scaling_factor
                uniq[key] = lat
            latents.append(uniq[key])
    prep = time.monotonic() - t; print("pose encode", round(prep, 1), "s for", len(uniq), "unique frames", flush=True)

    # ---- generate + composite, streaming into ffmpeg
    mask = softmask(h, w, w * 0.5, h * 0.74, w * 0.36, h * 0.27); colour = Colour(); times = []
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "pipe:0",
           "-i", str(a.audio)] + (["-t", str(a.limit)] if a.limit else []) + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        with torch.inference_mode():
            for s in range(0, n, a.batch):
                t = time.monotonic(); b = list(range(s, min(n, s + a.batch)))
                lat = unet(torch.cat([latents[i] for i in b]), torch.tensor([0]), encoder_hidden_states=pe(audio[b])).sample
                pred = vae.decode(lat / vae.config.scaling_factor).sample
                pred = ((pred / 2 + 0.5).clamp(0, 1).permute(0, 2, 3, 1).numpy() * 255).astype(np.uint8)[..., ::-1]
                for j, i in enumerate(b):
                    base = seq[i]; gen = base.copy(); gen[y:y + h, x:x + w] = cv2.resize(pred[j], (w, h), interpolation=cv2.INTER_CUBIC)
                    region = base[y:y + h, x:x + w].astype(np.float32); matched = colour.apply(gen[y:y + h, x:x + w], base[y:y + h, x:x + w], mask)
                    comp = base.copy(); comp[y:y + h, x:x + w] = np.clip(region * (1 - mask) + matched * mask, 0, 255).astype(np.uint8)
                    p.stdin.write(comp.tobytes())
                times.append((time.monotonic() - t) / len(b))
                if s % (a.batch * 10) == 0: guard(); print(f"frame {s}/{n}  {times[-1]:.2f} s/frame  eta {(n - s) * np.mean(times[-10:]) / 60:.1f} min", flush=True)
    finally:
        p.stdin.close()
    if p.wait(timeout=300): raise RuntimeError("ffmpeg failed")
    metrics = dict(frames=n, fps=a.fps, batch=a.batch, threads=a.threads, load_s=round(load, 1), pose_encode_s=round(prep, 1), unique_poses=len(uniq),
                   mean_s_per_frame=round(float(np.mean(times)), 3), generate_s=round(float(np.mean(times) * n), 1),
                   minutes_per_output_minute=round(float(np.mean(times)) * a.fps, 2), peak_rss_gib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 2),
                   output=str(out), size=[W, H], roi=list(roi))
    write_json(out.with_suffix(".metrics.json"), metrics); print(json.dumps(metrics, indent=2))

if __name__ == "__main__": main()
