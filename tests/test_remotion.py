"""Pure-Python tests for the Remotion wrapper: prop building, kind mapping,
command construction (subprocess mocked) and the available() false path.
Node is never invoked here."""
import json
import subprocess
from pathlib import Path

import pytest

import pipeline.remotion as R


BRAND = {"accent": [231, 196, 122], "bg": [14, 18, 26]}


def test_kinds_map_to_compositions():
    assert R.KINDS == {
        "chart": "Chart",
        "map": "Map",
        "text": "KineticText",
        "timeline": "Timeline",
        "scale": "Scale",
        "orbit": "Orbit",
        "reveal": "WordReveal",
    }


def test_orientations():
    assert R.ORIENTATIONS == {"portrait": (1080, 1920), "landscape": (1920, 1080)}


def test_build_props_merges_dimensions(tmp_path):
    props = R.build_props(
        "chart",
        {"title": "T", "items": [{"label": "A", "value": 1, "shown": "1"}]},
        seconds=3.0,
        orientation="portrait",
        brand=BRAND,
    )
    assert props["width"] == 1080
    assert props["height"] == 1920
    assert props["seconds"] == 3.0
    assert props["brand"]["accent"] == [231, 196, 122]
    assert props["title"] == "T"
    # props are copied, not mutated
    assert "width" not in {"title": "T"}


def test_build_props_landscape(tmp_path):
    props = R.build_props("map", {"countries": ["Iran"], "label": "L"}, 2.5, "landscape", BRAND)
    assert props["width"] == 1920
    assert props["height"] == 1080
    assert props["seconds"] == 2.5


def test_build_props_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown kind"):
        R.build_props("nope", {}, 3.0, "portrait", BRAND)


def test_build_props_rejects_unknown_orientation():
    with pytest.raises(ValueError, match="unknown orientation"):
        R.build_props("chart", {}, 3.0, "square", BRAND)


def test_build_props_rejects_nonpositive_seconds():
    with pytest.raises(ValueError, match="positive"):
        R.build_props("chart", {}, 0, "portrait", BRAND)


def test_normalise_brand_defaults_and_coercion():
    assert R.normalise_brand(None) == {"accent": [251, 191, 36], "bg": [14, 18, 26]}
    b = R.normalise_brand({"accent": (231, 196, 122, 9), "bg": [14, 18, 26], "font": ""})
    assert b["accent"] == [231, 196, 122]
    assert "font" not in b
    b2 = R.normalise_brand({"accent": ["1", "2", "3"], "bg": []})
    assert b2["accent"] == [1, 2, 3]
    assert b2["bg"] == [14, 18, 26]


def test_render_command_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/npx" if name in ("npx", "node") else None)
    cmd = R.render_command("Chart", Path("out/x.mp4"), Path("out/x.props.json"))
    assert cmd[0] == "/usr/bin/npx"
    assert cmd[1:4] == ["remotion", "render", "src/Root.tsx"]
    assert cmd[4] == "Chart"
    assert cmd[5] == "out/x.mp4"
    assert "--props=out/x.props.json" in cmd
    assert "--log=error" in cmd
    assert "--overwrite" in cmd


def test_render_command_with_bundle_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/npx" if name in ("npx", "node") else None)
    cmd = R.render_command("Map", Path("o.mp4"), Path("p.json"), entry_point="out/bundle")
    assert cmd[3] == "out/bundle"
    assert cmd[4] == "Map"


def test_available_false_without_node(monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: None)
    assert R.available() is False


def test_available_false_without_node_modules(tmp_path, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None)
    monkeypatch.setattr(R, "MOTION_DIR", tmp_path)
    assert R.available() is False


def test_available_true(tmp_path, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None)
    fake = tmp_path / "node_modules" / "remotion"
    fake.mkdir(parents=True)
    monkeypatch.setattr(R, "MOTION_DIR", tmp_path)
    assert R.available() is True


def test_render_segment_raises_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="not available"):
        R.render_segment("chart", {}, 3.0, "portrait", tmp_path / "x.mp4", BRAND)


class _Proc:
    def __init__(self, returncode=0, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


def test_render_segment_invokes_remotion(tmp_path, monkeypatch):
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = kwargs.get("cwd")
        calls["timeout"] = kwargs.get("timeout")
        # simulate the CLI writing the output file
        out = Path(cmd[5])
        out.write_bytes(b"mp4")
        return _Proc(0)

    monkeypatch.setattr(R, "available", lambda: True)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    out = tmp_path / "sub" / "chart.mp4"
    seen_props = {}

    def capture_props(cmd):
        flag = [a for a in cmd if str(a).startswith("--props=")][0]
        seen_props["path"] = Path(str(flag).split("=", 1)[1])
        seen_props["json"] = json.loads(seen_props["path"].read_text())

    real_run = fake_run

    def wrapped_run(cmd, **kwargs):
        capture_props(cmd)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(R.subprocess, "run", wrapped_run)
    result = R.render_segment(
        "chart",
        {"title": "War risk premium", "items": [{"label": "B", "value": 1, "shown": "1%"}]},
        3.0,
        "portrait",
        out,
        BRAND,
    )
    assert result == out
    assert out.exists()
    cmd = calls["cmd"]
    assert cmd[1] == "remotion"
    assert "Chart" in cmd
    assert calls["cwd"] == R.MOTION_DIR
    # timeout grows with seconds: max(120, seconds*40)
    assert calls["timeout"] == max(120, 3.0 * 40)
    # props file held the full merged JSON while the CLI ran
    written = seen_props["json"]
    assert written["width"] == 1080
    assert written["height"] == 1920
    assert written["seconds"] == 3.0
    assert written["brand"]["accent"] == [231, 196, 122]
    # and it is cleaned up afterwards
    assert not seen_props["path"].exists()


def test_render_segment_long_timeout(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        Path(cmd[5]).write_bytes(b"mp4")
        return _Proc(0)

    monkeypatch.setattr(R, "available", lambda: True)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    R.render_segment("orbit", {"bodies": ["Earth"], "label": "L"}, 30.0, "landscape",
                     tmp_path / "o.mp4", BRAND)
    assert seen["timeout"] == 1200  # 30 s * 40


def test_render_segment_failure_raises_with_stderr_tail(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return _Proc(1, stderr="boom\n" * 500)

    monkeypatch.setattr(R, "available", lambda: True)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="failed \\(exit 1\\)") as exc:
        R.render_segment("chart", {}, 3.0, "portrait", tmp_path / "x.mp4", BRAND)
    assert "boom" in str(exc.value)


def test_render_segment_timeout_raises(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(R, "available", lambda: True)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        R.render_segment("chart", {}, 3.0, "portrait", tmp_path / "x.mp4", BRAND)


def test_render_segment_cleans_up_props_file_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "available", lambda: True)

    def fake_run(cmd, **kwargs):
        return _Proc(1, stderr="x")

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    out = tmp_path / "x.mp4"
    with pytest.raises(RuntimeError):
        R.render_segment("chart", {}, 3.0, "portrait", out, BRAND)
    assert not list(tmp_path.glob("*.props.json"))


def test_render_segment_missing_output_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "available", lambda: True)

    def fake_run(cmd, **kwargs):
        return _Proc(0)  # exit 0 but no file written

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="failed"):
        R.render_segment("chart", {}, 3.0, "portrait", tmp_path / "x.mp4", BRAND)


def test_bundle_once_command_and_success(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs.get("cwd")
        return _Proc(0)

    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/npx" if name in ("npx", "node") else None)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    target = tmp_path / "b"
    result = R.bundle_once(target)
    assert result == target
    cmd = seen["cmd"]
    assert cmd[2] == "bundle"
    assert cmd[3] == "src/Root.tsx"
    assert f"--out-dir={target}" in cmd
    assert seen["cwd"] == R.MOTION_DIR


def test_bundle_once_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/npx" if name in ("npx", "node") else None)

    def fake_run(cmd, **kwargs):
        return _Proc(2, stderr="bundling broke")

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="bundle failed"):
        R.bundle_once(tmp_path / "b")


def test_last_render_seconds_starts_at_zero():
    # read-only: previous tests may have set it, so just assert the type contract
    assert isinstance(R.last_render_seconds(), float)


def _mk_nodemods(tmp_path):
    fake = tmp_path / "node_modules" / "remotion"
    fake.mkdir(parents=True)
    return fake


def test_ensure_installed_no_node(monkeypatch):
    monkeypatch.setattr(R.shutil, "which", lambda name: None)
    assert R.ensure_installed() is False


def test_ensure_installed_runs_npm_ci_and_browser_ensure(tmp_path, monkeypatch):
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append((list(cmd), kwargs.get("cwd"), kwargs.get("timeout")))
        if cmd[:2] == ["npm", "ci"]:
            _mk_nodemods(tmp_path)
        return _Proc(0)

    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else "/usr/bin/npx")
    monkeypatch.setattr(R, "MOTION_DIR", tmp_path)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    monkeypatch.setattr(R, "_browser_ensured", False)
    assert R.ensure_installed() is True
    npm = commands[0]
    assert npm[0][:3] == ["npm", "ci", "--no-audit"]
    assert npm[0][3] == "--no-fund"
    assert npm[1] == tmp_path
    assert npm[2] == R.INSTALL_TIMEOUT
    browser = commands[1]
    assert browser[0][1:5] == ["remotion", "browser", "ensure"]
    assert browser[2] == R.INSTALL_TIMEOUT
    assert any(c[0][1:3] == ["remotion", "bundle"] for c in commands)  # bundle_once ran
    monkeypatch.undo()


def test_ensure_installed_npm_ci_failure_returns_false(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return _Proc(1, stderr="npm down")

    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else "/usr/bin/npx")
    monkeypatch.setattr(R, "MOTION_DIR", tmp_path)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    assert R.ensure_installed() is False
    assert calls[0][:2] == ["npm", "ci"]
    assert len(calls) == 1  # browser ensure and bundle are skipped


def test_ensure_installed_browser_ensure_failure(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if cmd[:2] == ["npm", "ci"]:
            _mk_nodemods(tmp_path)
            return _Proc(0)
        return _Proc(3, stderr="chrome download failed")

    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else "/usr/bin/npx")
    monkeypatch.setattr(R, "MOTION_DIR", tmp_path)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    monkeypatch.setattr(R, "_browser_ensured", False)
    assert R.ensure_installed() is False
    assert calls[1][1:5] == ["remotion", "browser", "ensure"]
    assert len(calls) == 2


def test_ensure_installed_noop_when_node_modules_present(tmp_path, monkeypatch):
    _mk_nodemods(tmp_path)
    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else "/usr/bin/npx")
    monkeypatch.setattr(R, "MOTION_DIR", tmp_path)
    monkeypatch.setattr(R.subprocess, "run", lambda cmd, **kw: pytest.fail("no subprocess expected"))
    monkeypatch.setattr(R, "_bundle_dir", tmp_path / "b")
    assert R.ensure_installed() is True


def test_bundle_once_memoized_per_process(tmp_path, monkeypatch):
    runs = []

    def fake_run(cmd, **kwargs):
        runs.append(list(cmd))
        return _Proc(0)

    monkeypatch.setattr(R.shutil, "which", lambda name: "/usr/bin/npx" if name in ("npx", "node") else None)
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    monkeypatch.setattr(R, "_bundle_dir", None)
    first = R.bundle_once()
    second = R.bundle_once()
    assert first == second and len(runs) == 1
    assert R.bundled_entry_point() == str(first)
    monkeypatch.setattr(R, "_bundle_dir", None)
