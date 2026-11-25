"""Render animated explainer segments with the Remotion project in ``motion/``.

Stage 1 of the motion-graphics plan (2026-11-25): the compositions live in
``motion/src/*.tsx``; this module is the Python entry point. Stage 2 wires it into
``pipeline/render.py``: when a channel's style has ``motion`` on and
:func:`ensure_installed` reports the project ready, chart/map/diagram/text shots
render here and every Remotion failure falls back to the existing Pillow path.

Usage::

    from pipeline.remotion import available, render_segment

    if available():
        clip = render_segment(
            "chart",
            {"title": "War risk premium, % of ship value",
             "items": [{"label": "Before", "value": 0.05, "shown": "0.05%"},
                       {"label": "After", "value": 0.5, "shown": "0.5%"}]},
            seconds=3.0,
            orientation="portrait",
            out=Path("out/chart.mp4"),
            brand={"accent": [231, 196, 122], "bg": [14, 18, 26]},
        )

Kinds map to compositions: chart -> Chart, map -> Map, text -> KineticText,
timeline -> Timeline, scale -> Scale, orbit -> Orbit, reveal -> WordReveal.

Cost note: each render is one ``npx remotion render`` subprocess that bundles
the project first (~4 s warm, more cold). To avoid re-bundling for every segment
in a batch, call :func:`bundle_once` and pass the returned directory as
``entry_point``; the render CLI accepts a bundle directory (a "serve URL") in
place of the source entry point.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .common import log

REPO_ROOT = Path(__file__).resolve().parent.parent
MOTION_DIR = REPO_ROOT / "motion"
ENTRY_POINT = "src/Root.tsx"
INSTALL_TIMEOUT = 600

# kind -> Composition id registered in motion/src/Root.tsx
KINDS: dict[str, str] = {
    "chart": "Chart",
    "map": "Map",
    "text": "KineticText",
    "timeline": "Timeline",
    "scale": "Scale",
    "orbit": "Orbit",
    "reveal": "WordReveal",
}

ORIENTATIONS: dict[str, tuple[int, int]] = {
    "portrait": (1080, 1920),
    "landscape": (1920, 1080),
}

_last_render_seconds = 0.0
_bundle_dir: Path | None = None          # bundle_once() memo, per process
_bundle_lock = threading.Lock()
_browser_ensured = False                  # npx remotion browser ensure, per process
_install_lock = threading.Lock()


def available() -> bool:
    """True when node + the motion project's node_modules are present."""
    if not shutil.which("node"):
        return False
    return (MOTION_DIR / "node_modules" / "remotion").is_dir()


def ensure_installed() -> bool:
    """Make the project renderable once per process, then report :func:`available`.

    When ``motion/node_modules`` is missing (a fresh clone or a new GitHub runner),
    run ``npm ci --no-audit --no-fund`` in ``motion/`` and then
    ``npx remotion browser ensure`` (one headless Chrome download) — both with a
    600 s timeout. Finally :func:`bundle_once` pre-bundles so the first segment
    does not pay the bundling cost. Every step is a no-op when already installed;
    failures log and leave ``available()`` False, so callers fall back to Pillow.
    """
    global _browser_ensured, _bundle_dir
    if not shutil.which("node"):
        return False
    with _install_lock:
        if not (MOTION_DIR / "node_modules" / "remotion").is_dir():
            proc = subprocess.run(
                ["npm", "ci", "--no-audit", "--no-fund"],
                cwd=MOTION_DIR, capture_output=True, text=True, timeout=INSTALL_TIMEOUT,
            )
            if proc.returncode != 0:
                log.warning("remotion npm ci failed (exit %d): %s",
                            proc.returncode, (proc.stderr or proc.stdout)[-2000:])
                return False
            if not _browser_ensured:
                proc = subprocess.run(
                    [_npx(), "remotion", "browser", "ensure"],
                    cwd=MOTION_DIR, capture_output=True, text=True, timeout=INSTALL_TIMEOUT,
                )
                if proc.returncode != 0:
                    log.warning("remotion browser ensure failed (exit %d): %s",
                                proc.returncode, (proc.stderr or proc.stdout)[-2000:])
                    return False
                _browser_ensured = True
        try:
            _bundle_dir = bundle_once()
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            log.warning("remotion bundle_once failed: %s", exc)
        return available()


def _npx() -> str:
    """Path to npx (falls back to the binary next to node when not on PATH)."""
    npx = shutil.which("npx")
    if npx:
        return npx
    node = shutil.which("node")
    if node:  # pragma: no cover - available() gates the common path
        sibling = Path(node).parent / "npx"
        if sibling.exists():
            return str(sibling)
    raise RuntimeError("npx not found; install Node.js")


def normalise_brand(brand: dict | None) -> dict:
    """Coerce ``brand`` to the TS ``Brand`` shape: accent/bg as int triples, optional font."""
    brand = dict(brand or {})
    accent = brand.get("accent") or [251, 191, 36]
    bg = brand.get("bg") or [14, 18, 26]
    brand["accent"] = [int(x) for x in accent][:3]
    brand["bg"] = [int(x) for x in bg][:3]
    if brand.get("font"):
        brand["font"] = str(brand["font"])
        if brand.get("fontFile"):
            brand["fontFile"] = Path(str(brand["fontFile"])).name
    else:
        brand.pop("font", None)
    return brand


def build_props(kind: str, props: dict, seconds: float, orientation: str, brand: dict) -> dict:
    """Validate inputs and merge them with orientation/duration metadata into the
    exact JSON the composition's ``calculateMetadata`` expects."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {sorted(KINDS)}")
    if orientation not in ORIENTATIONS:
        raise ValueError(
            f"unknown orientation {orientation!r}; expected one of {sorted(ORIENTATIONS)}"
        )
    if seconds <= 0:
        raise ValueError(f"seconds must be positive, got {seconds}")
    width, height = ORIENTATIONS[orientation]
    merged = dict(props)
    merged["brand"] = normalise_brand(brand)
    merged["width"] = width
    merged["height"] = height
    merged["seconds"] = seconds
    return merged


def render_command(
    composition: str,
    out: Path,
    props_file: Path,
    entry_point: str = ENTRY_POINT,
) -> list[str]:
    """The exact argv handed to subprocess.run (exposed for tests)."""
    return [
        _npx(),
        "remotion",
        "render",
        entry_point,
        composition,
        str(out),
        f"--props={props_file}",
        "--log=error",
        "--overwrite",
    ]


def render_segment(
    kind: str,
    props: dict,
    seconds: float,
    orientation: str,
    out: Path,
    brand: dict,
    entry_point: str = ENTRY_POINT,
) -> Path:
    """Render one segment to ``out`` (mp4); returns ``out``.

    Runs ``npx remotion render <entry> <Composition> <out> --props=<file> --log=error``
    from ``motion/``. Width/height come from the orientation and are also embedded
    in the props file because the compositions read dimensions from input props
    (one composition renders both orientations). Timeout: ``max(120, seconds * 40)``.
    Raises RuntimeError with the stderr tail on failure.
    """
    global _last_render_seconds
    if not available():
        raise RuntimeError(
            "Remotion is not available (node or motion/node_modules missing); run npm install in motion/"
        )
    composition = KINDS[kind]
    sync_fonts()
    merged = build_props(kind, props, seconds, orientation, brand)
    # Absolute paths: the CLI runs with cwd=motion/, so relative paths would
    # resolve against motion/ instead of the caller's working directory.
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    props_file = out.with_suffix(out.suffix + ".props.json")
    props_file.write_text(json.dumps(merged), encoding="utf-8")
    try:
        cmd = render_command(composition, out, props_file, entry_point)
        timeout = max(120, seconds * 40)
        started = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=MOTION_DIR, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            tail = exc.stderr or b""
            if isinstance(tail, bytes):
                tail = tail.decode("utf-8", "replace")
            raise RuntimeError(
                f"remotion render of {composition} timed out after {timeout:.0f}s\n{str(tail)[-2000:]}"
            ) from None
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(
                f"remotion render of {composition} failed (exit {proc.returncode}):\n"
                f"{(proc.stderr or proc.stdout)[-2000:]}"
            )
        _last_render_seconds = time.monotonic() - started
    finally:
        props_file.unlink(missing_ok=True)
    return out


def sync_fonts() -> None:
    """Copy the vendored channel fonts (assets/fonts/ofl, OFL) into motion/public/fonts so the
    compositions can load them with staticFile(). The copies are git-ignored."""
    src = MOTION_DIR.parent / "assets" / "fonts" / "ofl"
    dst = MOTION_DIR / "public" / "fonts"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.ttf"):
        target = dst / f.name
        if not target.exists() or target.stat().st_size != f.stat().st_size:
            shutil.copyfile(f, target)


def bundle_once(bundle_dir: Path | str | None = None) -> Path:
    """Pre-bundle the project once per process; the directory can then be passed
    as ``entry_point`` to :func:`render_segment` so segments skip re-bundling."""
    global _bundle_dir
    with _bundle_lock:
        if bundle_dir is None and _bundle_dir is not None:
            return _bundle_dir
        target = Path(bundle_dir) if bundle_dir else MOTION_DIR / "out" / "bundle"
        target.parent.mkdir(parents=True, exist_ok=True)
        sync_fonts()
        cmd = [_npx(), "remotion", "bundle", ENTRY_POINT, f"--out-dir={target}", "--quiet"]
        proc = subprocess.run(cmd, cwd=MOTION_DIR, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(
                f"remotion bundle failed (exit {proc.returncode}):\n{(proc.stderr or proc.stdout)[-2000:]}"
            )
        if bundle_dir is None:
            _bundle_dir = target
        return target


def bundled_entry_point() -> str:
    """The pre-bundled directory from :func:`bundle_once`, or the source entry point."""
    return str(_bundle_dir) if _bundle_dir is not None else ENTRY_POINT


def last_render_seconds() -> float:
    """Wall-clock seconds of the last successful render_segment call (0.0 before any)."""
    return _last_render_seconds
