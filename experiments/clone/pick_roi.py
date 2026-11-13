"""Manual face-ROI helper (no InsightFace/DWPose). Prints a square ROI in source pixels and saves a check image.

  python pick_roi.py input/face.mp4 [--t 1.0] [--roi x,y,w,h]
Without --roi it suggests one from OpenCV's bundled Haar frontal-face cascade (Apache-2.0, ships with opencv-python);
verify the drawn box in work/roi_check.png and pass --roi to override. The lower half of the square is regenerated,
so the square should run from the eyebrows to just under the chin, slightly wider than the face.
"""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from common import *
sys.path.append(str(AVATAR / "deps")); import cv2, numpy as np

def frame_at(video, t):
    cap = cv2.VideoCapture(str(video)); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read(); cap.release()
    if not ok: raise SystemExit("could not read frame")
    return f

def suggest(frame):
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY); faces = casc.detectMultiScale(g, 1.1, 6, minSize=(80, 80))
    if len(faces) == 0: return None
    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
    side = int(max(w, h) * 1.25); cx, cy = x + w // 2, y + int(h * 0.6)      # centre slightly below eye line
    X, Y = max(0, cx - side // 2), max(0, cy - side // 2)
    side = min(side, frame.shape[1] - X, frame.shape[0] - Y)
    return int(X), int(Y), int(side), int(side)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--t", type=float, default=1.0); ap.add_argument("--roi"); a = ap.parse_args()
    f = frame_at(a.video, a.t); H, W = f.shape[:2]
    roi = tuple(int(v) for v in a.roi.split(",")) if a.roi else suggest(f)
    print(f"frame {W}x{H}")
    if roi is None: raise SystemExit("no face found; pass --roi x,y,w,h")
    x, y, w, h = roi; print(f"roi {x},{y},{w},{h}   (face px across square: {w})")
    chk = f.copy(); cv2.rectangle(chk, (x, y), (x + w, y + h), (0, 255, 0), 3); cv2.line(chk, (x, y + h // 2), (x + w, y + h // 2), (0, 200, 255), 2)
    out = R / "work/roi_check.png"; cv2.imwrite(str(out), chk); cv2.imwrite(str(R / "work/roi_crop.png"), f[y:y + h, x:x + w]); print("check", out)
    write_json(R / "work/roi.json", dict(video=str(a.video), roi=[x, y, w, h], width=W, height=H))

if __name__ == "__main__": main()
