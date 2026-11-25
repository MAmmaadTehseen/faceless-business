#!/usr/bin/env python
"""Render one sample Short per channel with style motion forced ON (samples only).

These are stage-2 proof samples for the motion-graphics plan (2026-11-25): each
channel gets one portrait Short built exactly the way production builds one --
pipeline.shorts.make_short for the three explainer channels, the words pipeline's
own card/Short functions for Ten Tongues -- but with ``motion: true`` injected
into the channel style for this run only. No channel.json is modified.

Samples land in motion/out/samples/:
  <channel>.mp4       the Short itself
  <channel>_thumb.jpg one make_card_thumbnail per channel
  <channel>_sheet.jpg contact sheet (ffmpeg fps=1/3, tile 6x2)

Run from the repo root:

    .venv/bin/python scripts/render_channel_samples.py [--only futurework]

TTS_BACKEND is forced to kokoro. Real stock footage (Pixabay/Pexels/NASA) is
used, so PEXELS_API_KEY or PIXABAY_API_KEY must be in .env; the script never
prints any secret value.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLES_DIR = ROOT / "motion" / "out" / "samples"


# ---------------------------------------------------------------- short scripts
# Written here, not by a model: 60-90 spoken words each, one per channel, using the
# typed shots each channel's style would ask for in production (CHART/MAP/TEXT
# plus TIMELINE/ORBIT where the motion plan adds them). Facts match the shot specs.
# Every slot gets a distinct visual (12 shots for a ~40 s Short, as production
# asks for): the QA freeze detector chains sub-threshold motion across adjacent
# slots that share one query, so adjacent same-looking slots are avoided.

FUTUREWORK = {
    "hook_title": "AI layoffs hit 2 giants",
    "query": "office workers packing boxes",
    # 88 words. One distinct visual per ~3 s slot (12 slots for a 40 s Short),
    # like a production shot list, so no two adjacent slots look alike.
    "script": (
        "Amazon and Intel announced the two biggest AI-era job cuts so far. "
        "Amazon said 14,000 corporate roles will go. Intel is cutting 24,000 positions. "
        "That is 38,000 people in one month, and both companies blame restructuring, not demand. "
        "Look at the chart and the pattern is blunt. "
        "The cuts cluster in middle management, exactly where AI tools now write, summarise and plan. "
        "The map shows where the pain lands. "
        "Watch the task, not the job title. "
        "Would your role survive if one of your weekly reports wrote itself?"
    ),
    "shots": [
        "office workers packing boxes",
        "corporate office lobby",
        "CHART: AI job cuts announced | Amazon=14,000, Intel=24,000",
        "TEXT: AI cuts middle management first",
        "MAP: United States, India | Where the cuts land",
        "robot arm factory line",
        "empty office desks",
        "manager presentation meeting",
        "laptop typing closeup",
        "city office towers",
        "workers leaving building",
        "hands on keyboard working late",
    ],
}

TRADEWINDS = {
    "hook_title": "Hormuz war premium 10x",
    "query": "cargo tanker at sea",
    # 86 words. MAP + CHART + TEXT, the insurer angle.
    "script": (
        "War risk premiums for ships crossing the Strait of Hormuz jumped tenfold this year. "
        "A tanker passing Iran, Oman and the United Arab Emirates now pays about 0.5 percent of the ship's value per voyage. "
        "Before the strikes, the crossing cost 0.05 percent. "
        "On a 100 million dollar tanker that is 50,000 dollars becoming 500,000 dollars for one trip. "
        "Navies cannot fix that number. Insurers set it. "
        "Lloyd's market sets the real price of this crisis. "
        "Watch the insurers, not the navies. "
        "Who blinks first, London or Tehran?"
    ),
    "shots": [
        "cargo tanker at sea",
        "navy patrol boat ocean",
        "MAP: Iran, Oman, United Arab Emirates | Strait of Hormuz",
        "CHART: War risk premium, % of ship value | Before=0.05%, After=0.5%",
        "TEXT: Watch the insurers, not the navies",
        "shipping port cranes",
        "london city skyline",
        "insurance contract signing",
        "container ship aerial",
        "stock market screen",
        "oil tanker sunset",
        "harbour tugboat",
    ],
}

ESCAPEVELOCITY = {
    "hook_title": "Voyager 1 timeline",
    "query": "Voyager spacecraft",
    # 77 words. Real NASA footage + TIMELINE + ORBIT.
    "script": (
        "Voyager 1 is the farthest human-made object, and its whole story fits in one timeline. "
        "It launched in 1977, swung past Jupiter in 1979 and Saturn in 1980. "
        "In 1990, four billion miles out, it turned its camera home and took the Pale Blue Dot photo. "
        "By 2012 it had crossed into interstellar space, beyond the Sun's bubble. "
        "It still whispers to Earth on 1970s hardware. "
        "The orbit diagram shows the one place it is not: circling Earth. "
        "Which mission should follow it out?"
    ),
    "shots": [
        "Voyager spacecraft",
        "rocket launch 1977",
        "TIMELINE: Voyager | 1977=Launch, 1979=Jupiter, 1980=Saturn, 1990=Pale Blue Dot, 2012=Interstellar space",
        "ORBIT: Earth, Moon | Where Voyager is not",
        "deep space stars",
        "planet jupiter closeup",
        "saturn rings",
        "earth from space",
        "radio telescope dish",
        "nasa control room",
        "night sky milky way",
        "deep space nebula",
    ],
}

SHORTS = {
    "futurework": FUTUREWORK,
    "tradewinds": TRADEWINDS,
    "escapevelocity": ESCAPEVELOCITY,
}

# make_card_thumbnail text: 2-5 words, subject first (thumbnail.py wraps at 13 chars).
THUMB_TEXT = {
    "futurework": "AI Job Cuts",
    "tradewinds": "Hormuz Premium 10x",
    "escapevelocity": "Voyager 1 Story",
    "tentongues": "Water 10 Languages",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def ffprobe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def contact_sheet(video: Path, out: Path) -> Path:
    """One frame every 3 s, tiled 6x2 -- a 40+ s Short always fills the sheet."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video),
         "-vf", "fps=1/3,scale=360:640,tile=6x2", "-frames:v", "1", str(out)],
        check=True, timeout=300,
    )
    return out


class SampleRunner:
    """Renders the four channel samples and reports each artefact."""

    def __init__(self):
        self.channels: dict[str, "Channel"] = {}

    def channel(self, key: str):
        if key not in self.channels:
            from pipeline.common import Channel
            self.channels[key] = Channel(key)
        return self.channels[key]

    def render(self, key: str) -> None:
        if key == "tentongues":
            self.render_tentongues()
        else:
            self.render_explainer(key)

    def finish(self, key: str) -> tuple[Path, float, float, Path, Path]:
        """Probe the finished Short, draw the thumbnail, build the contact sheet."""
        from pipeline.thumbnail import make_card_thumbnail

        # The renderer drops .clean*.jpg probe frames next to the Short; remove
        # them so the samples folder holds only deliverables.
        for clean in SAMPLES_DIR.rglob("*.clean*.jpg"):
            clean.unlink(missing_ok=True)
        probed = ffprobe_duration(self.final)
        ch = self.channel(key)
        thumb = make_card_thumbnail(
            THUMB_TEXT[key], SAMPLES_DIR / f"{key}_thumb.jpg",
            accent=tuple(ch.style.get("accent", (251, 191, 36))),
            bg=tuple(ch.style.get("bg", (14, 18, 26))),
        )
        sheet = contact_sheet(self.final, SAMPLES_DIR / f"{key}_sheet.jpg")
        return self.final, probed, self.seconds, thumb, sheet

    def render_explainer(self, key: str) -> None:
        from pipeline.footage import Footage
        from pipeline.shorts import make_short

        ch = self.channel(key)
        short = dict(SHORTS[key])
        # Motion on for this run only: the samples demonstrate the Remotion path,
        # without touching channels/<key>/channel.json.
        style = {**ch.style, "motion": True}
        footage = Footage(providers=ch.cfg.get("footage", {}).get("providers"))
        if footage.placeholder:
            raise RuntimeError(
                f"{key}: no footage API keys found in .env (PIXABAY_API_KEY / PEXELS_API_KEY); "
                "samples must use real footage"
            )
        # TTS/segment work files go to samples/<key>/; make_short writes the
        # finished Short to <out_dir>/<name>.mp4, so pass name=../<key> is not
        # an option -- render into a work dir, then move the Short up to
        # samples/<key>.mp4 where the deliverable belongs.
        work = SAMPLES_DIR / key
        t0 = time.monotonic()
        result = make_short(short, work, ch.voice, footage, name=key, style=style)
        self.final = SAMPLES_DIR / f"{key}.mp4"
        moved = work / f"{key}.mp4"
        if moved != self.final:
            self.final.write_bytes(moved.read_bytes())
            moved.unlink(missing_ok=True)
        self.duration = result["duration"]
        self.seconds = time.monotonic() - t0

    def render_tentongues(self) -> None:
        """One language Short for the fixture word, Japanese, reveal on, motion forced on.

        Uses the words pipeline's own short_segments + synthesize_segments +
        render_cards_video with the reveal payload attached, exactly as
        produce_episode renders a language Short. The fixture word is 'water'
        (data/fixture_words.json); the reveal exercises the WordReveal
        composition through Japanese's configured Kokoro voice.
        """
        import json
        from pipeline.words import short_segments, validate_episode, render_cards_video
        from pipeline.words_tts import synthesize_segments
        from pipeline.remotion import ensure_installed

        ch = self.channel("tentongues")
        fixture = ROOT / "data" / "fixture_words.json"
        data = validate_episode(json.loads(fixture.read_text()), ch.cfg["languages"])
        if not ensure_installed():
            raise RuntimeError("tentongues: Remotion is not available; run npm ci in motion/")

        code = "ja"  # Japanese reveal; Urdu (ur) is the other fixture language
        out_dir = SAMPLES_DIR / "tentongues"
        segs = short_segments(ch, data, code)
        # render_cards_video reads channel.style["motion"] to switch the word card
        # to the WordReveal composition, so force it on for this sample only.
        ch.style = {**ch.style, "motion": True}
        t0 = time.monotonic()
        tts = synthesize_segments(segs, out_dir, name="tentongues_voice")
        video = render_cards_video(tts["timings"], tts["audio"], tts["srt"],
                                   out_dir / "tentongues.mp4", "portrait", ch,
                                   music_db=-22.0)
        self.final = SAMPLES_DIR / "tentongues.mp4"
        moved = out_dir / "tentongues.mp4"
        if moved != self.final:
            self.final.write_bytes(moved.read_bytes())
            moved.unlink(missing_ok=True)
        self.duration = tts["duration"]
        self.seconds = time.monotonic() - t0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=[*SHORTS, "tentongues"], help="render just one channel")
    args = ap.parse_args()

    # .env is loaded before pipeline imports read it; TTS_BACKEND=kokoro per the
    # hard rules (edge-tts is blocked from datacenter IPs). No secret is ever printed.
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    os.environ["TTS_BACKEND"] = "kokoro"

    # Imported after load_dotenv: pipeline modules read the env at import/use time.
    if not ensure_remotion_ready():
        return 2

    wanted = [args.only] if args.only else [*SHORTS, "tentongues"]
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    runner = SampleRunner()
    report = []
    for key in wanted:
        log(f"=== {key} ===")
        try:
            runner.render(key)
            final, probed, seconds, thumb, sheet = runner.finish(key)
        except Exception as exc:  # noqa: BLE001 - report and continue with the rest
            log(f"FAIL {key}: {str(exc)[-500:]}")
            continue
        report.append((key, final, probed, seconds, thumb, sheet))
        log(f"{key}: {final.name} {probed:.2f}s (render {seconds:.1f}s), "
            f"{thumb.name}, {sheet.name}")

    log("")
    log("=== summary ===")
    for key, final, probed, seconds, thumb, sheet in report:
        log(f"{key}: {final}  duration={probed:.2f}s  render={seconds:.1f}s")
        log(f"          {thumb}")
        log(f"          {sheet}")
    return 0 if len(report) == len(wanted) else 1


def ensure_remotion_ready() -> bool:
    from pipeline import remotion
    if not remotion.available():
        log("Remotion is not available (node or motion/node_modules missing); "
            "run npm ci in motion/ first")
        return False
    if not remotion.ensure_installed():
        log("Remotion install/bundle failed")
        return False
    log(f"remotion bundle: {remotion.bundled_entry_point()}")
    return True


if __name__ == "__main__":
    raise SystemExit(main())
