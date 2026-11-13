"""Local-only recap contracts, including real ffmpeg assembly on a lavfi fixture."""
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from pipeline.recap import core, worker


@pytest.fixture
def local_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    return tmp_path


@pytest.fixture
def video(local_outputs):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")
    target = local_outputs / "fixture.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24", "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=24000", "-t", "2", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", str(target)], check=True)
    return target


def payload(video):
    return {"path": str(video), "title": "Fixture", "year": 2026, "rights": {"basis": "own work"}}


@pytest.mark.parametrize("value", ["relative.mp4", "", "http://localhost/video.mp4", "/dev/null", "/tmp/a\x00.mp4"])
def test_path_rejects_invalid(value):
    with pytest.raises((ValueError, OSError)):
        core.validate_path(value)


def test_path_is_real_video(video):
    path, info = core.validate_path(str(video))
    assert path == video and info["duration"] == 2
    fake = video.with_name("fake.mp4")
    fake.write_text("not a video")
    with pytest.raises(subprocess.CalledProcessError):
        core.validate_path(str(fake))
    with pytest.raises(ValueError):
        core.job_dir("../secrets")


@pytest.mark.parametrize("rights", [None, {}, {"basis": "written permission", "note": None}, {"basis": "Creative Commons", "licence": None, "url": "https://example.org"}, {"basis": "other"}, {"basis": "Creative Commons"}, {"basis": "written permission", "note": " "}, {"basis": "Creative Commons", "licence": "CC BY", "url": "file:///private"}])
def test_rights_gate(rights):
    with pytest.raises(ValueError):
        core.rights_gate(rights)


@pytest.mark.parametrize("rights", [{"basis":"public domain"}, {"basis":"own work"}, {"basis":"written permission","note":"Signed by director"}, {"basis":"Creative Commons","licence":"CC BY 4.0","url":"https://example.org/licence"}])
def test_rights_accepts_supported(rights):
    assert core.rights_gate(rights) == rights


def test_plan_and_srt():
    p = core.plan(7200)
    assert p["stages"] == list(core.STAGES)
    assert len(p["pieces"]) == 5 and p["estimate_usd"] > 0
    assert p["long_seconds"] == [300, 540] and p["short_max_seconds"] < 60
    assert core.srt([{"start": 0, "end": 1.2, "text": "Hello."}, {"start": 61.005,"end":62,"text":"Analysis."}]) == "1\n00:00:00,000 --> 00:00:01,200\nHello.\n\n2\n00:01:01,005 --> 00:01:02,000\nAnalysis.\n"


def test_create_rights_and_public_state(video):
    state = core.create(payload(video))
    work = core.job_dir(state["id"])
    assert json.loads((work / "rights.json").read_text()) == {"basis":"own work"}
    assert "source" not in core.public_state(work)
    assert state["status"] == "estimated"
    bad = payload(video)
    bad["rights"] = {"basis":"other"}
    with pytest.raises(ValueError):
        core.create(bad)


def test_upload_requires_rights_before_platform(video):
    state = core.create(payload(video))
    work = core.job_dir(state["id"])
    core.dump(work / "rights.json", {})
    with pytest.raises(ValueError, match="Rights basis"):
        worker.upload(work, state)


def test_upload_missing_token_clear_setup(video):
    state = core.create(payload(video))
    with pytest.raises(ValueError, match="YT_REFRESH_TOKEN_FILMREVIEW"):
        worker.upload(core.job_dir(state["id"]), state)


def test_calendar_respects_slots():
    from pipeline.common import Channel
    channel = worker.FilmReviewChannel()
    db = Mock()
    db.select.side_effect = lambda table, filters: []
    long = worker.calendar(db, channel, "long", "a")
    assert long.weekday() in {1, 4, 6} and long.hour == 17
    assert long >= datetime.now(timezone.utc) + timedelta(minutes=59)
    short = worker.calendar(db, channel, "short", "b", long)
    assert short.date() == (long + timedelta(days=1)).date() and short.hour == 19


def test_vision_failure_blocks():
    claude = Mock()
    claude.vision.side_effect = RuntimeError("offline")
    checked = worker.StrictVision(claude)
    with pytest.raises(RuntimeError):
        checked.vision("qa")
    assert checked.failed


def test_lavfi_end_to_end_mocked_paid_services(video, monkeypatch):
    """All five outputs, real scene detection, media assembly, thumbnails and QA."""
    from pipeline.db import DB
    state = core.create(payload(video))
    work = core.job_dir(state["id"])
    monkeypatch.setattr(worker, "RENDER_SIZES", {False:(160,90), True:(90,160)})
    monkeypatch.setattr(worker, "transcribe", lambda *_: [{"start":0,"end":2,"text":"Fixture dialogue"}])
    claude = Mock()
    generated = {name: {"title":f"A case for scene {index}", "description":"Original film criticism; spoilers.",
                       "segments":[{"text":("The framing supports a compelling argument. " * (120 if name == "long" else 12)).strip(), "scene":0}]}
                 for index, name in enumerate(core.PIECES)}
    claude.run.return_value = (generated, 0)
    claude.vision.return_value = ({"pass":True,"issues":[],"thumbnail_ok":True,"frames_ok":True,"frames_without_caption":3}, 0)
    def fake_voice(item, directory, channel):
        duration = 300 if directory.name == "long" else 2
        audio = directory / "voice.wav"
        subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","sine=frequency=440:sample_rate=24000","-t",str(duration), str(audio)], check=True)
        return {"audio":audio,"duration":duration,"timings":[{"start":0,"end":duration}]}
    monkeypatch.setattr(worker, "narrate", fake_voice)
    db = DB()
    worker.generate(work, state, db=db, claude=claude)
    assert state["status"] == "review" and state["percent"] == 100
    assert set(state["items"]) == set(core.PIECES)
    for name, item in state["items"].items():
        assert item["qa"]["pass"] and not item["approved"]
        result = core.probe(work / name / "video.mp4")
        assert result["has_audio"]
        assert result["width"] < result["height"] if name != "long" else result["width"] > result["height"]
        assert (work / name / "captions.srt").read_text().startswith("1\n00:00:00,000 -->")
        assert "Fixture dialogue" not in (work / name / "captions.srt").read_text()
    assert claude.run.call_count == 1 and claude.vision.call_count == 5
    # Rebuild one piece without touching the other four approvals or files.
    state["items"]["long"]["approved"] = True
    before = (work / "long" / "video.mp4").stat().st_mtime_ns
    worker.generate(work, state, only="short2", db=db, claude=claude)
    assert state["items"]["long"]["approved"]
    assert (work / "long" / "video.mp4").stat().st_mtime_ns == before
    assert not state["items"]["short2"]["approved"]
    paid_calls = claude.run.call_count
    monkeypatch.setattr(worker, "narrate", lambda *_: pytest.fail("Re-render must reuse narration"))
    worker.generate(work, state, only="short2", db=db, claude=claude, rerender=True)
    assert claude.run.call_count == paid_calls
    assert "text still visible" in claude.vision.call_args.args[1]
    assert "Transcript language:" in claude.run.call_args.args[1][-1]["text"]
    assert "accuracy_check" in claude.run.call_args.kwargs["schema"]["properties"]["short2"]["required"]



def test_local_channel_never_discovered_by_crons():
    from pipeline.common import Channel
    assert "filmreview" not in Channel.keys()
    assert worker.FilmReviewChannel().env("YT_REFRESH_TOKEN") is None
    assert "<beliefs>" in worker.FilmReviewChannel().persona()


def test_dashboard_gate_is_local_and_vercel_always_denied():
    """Execute the actual edge gate after TypeScript transpilation; no server/network."""
    root = Path(__file__).resolve().parents[1]
    script = r'''
const fs = require('fs');
const ts = require('./dashboard/node_modules/typescript');
const text = fs.readFileSync('./dashboard/src/lib/recap-local.ts','utf8');
const result = ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const target = {exports:{}};
new Function('module','exports',result)(target,target.exports);
const {recapRequestAllowed: allowed} = target.exports;
process.env.NODE_ENV = 'development'; delete process.env.VERCEL;
const request = (headers={}) => new Request('http://127.0.0.1:3000/api/recap',{headers:{host:'127.0.0.1:3000',...headers}});
const assert = require('node:assert/strict');
assert.equal(allowed(request()),true);
assert.equal(allowed(request({'x-forwarded-for':'127.0.0.1'})),true);
assert.equal(allowed(request({origin:'https://evil.example'})),false);
assert.equal(allowed(request({host:'evil.example'})),false);
assert.equal(allowed(request({'x-forwarded-for':'203.0.113.2'})),false);
assert.equal(allowed(request({'sec-fetch-site':'cross-site'})),false);
process.env.NODE_ENV = 'production'; delete process.env.LOCAL_RECAP;
assert.equal(allowed(request()),false);
process.env.LOCAL_RECAP = '1';
assert.equal(allowed(request()),true);
process.env.VERCEL = '1';
assert.equal(allowed(request()),false);
'''
    subprocess.run(["node", "-e", script], cwd=root, check=True, capture_output=True)


def test_mocked_upload_reuses_guard_and_inserts_captions(video, monkeypatch):
    from pipeline.db import DB
    from pipeline.publish import youtube
    import pipeline.publish
    import pipeline.publish.quota
    state = core.create(payload(video))
    work = core.job_dir(state["id"])
    for name in core.PIECES:
        state["items"][name] = {"title":"A critical reading", "description":"Review", "approved":True,"discarded":False,"qa":{"pass":True}}
        directory = work / name
        directory.mkdir()
        (directory / "video.mp4").write_bytes(b"fixture")
        (directory / "thumbnail.jpg").write_bytes(b"fixture")
        (directory / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nOpinion.\n")
    db = DB()
    monkeypatch.setattr("pipeline.db.DB", lambda: db)
    monkeypatch.setattr(youtube, "configured", lambda: True)
    monkeypatch.setattr(pipeline.publish.quota, "reserve", lambda *a, **k: True)
    mocked = Mock()
    mocked.captions.return_value.list.return_value.execute.return_value = {"items":[]}
    monkeypatch.setattr(youtube, "yt", lambda: mocked)
    calls = []
    def guard(db, row, channel, privacy, slot):
        calls.append((row["id"], privacy, slot))
        assert row["qa_status"] == "passed" and channel.key == "filmreview"
        return {"id": row["id"], "url":"https://example.org/video"}
    monkeypatch.setattr(pipeline.publish, "_youtube_publish", guard)
    worker.upload(work, state)
    assert len(calls) == 5 and all(c[1] == "private" for c in calls)
    assert [c[2].date() for c in calls] == [(calls[0][2] + timedelta(days=i)).date() for i in range(5)]
    assert mocked.captions.return_value.insert.call_count == 5
    worker.upload(work, state)
    assert mocked.captions.return_value.insert.call_count == 5
    assert all(i["captions_uploaded"] for i in state["items"].values())


def test_scene_walk_skips_credits_and_prefers_unused():
    from pipeline.recap.worker import scene_walk
    scenes = [{"start": i * 10.0, "end": i * 10.0 + 10} for i in range(100)]
    walk = scene_walk(scenes, 50, {51})
    assert walk[0] == 50 and walk[1] == 52 and walk[-1] == 51
    assert 99 not in walk and 0 not in walk


def test_usable_scene_rejects_black_and_flat():
    from pipeline.recap.worker import usable_scene
    scene = {"start": 0, "end": 2}
    assert not usable_scene("x", scene, reader=lambda c: bytes(2304))
    assert not usable_scene("x", scene, reader=lambda c: b"\x80" * 2304)
    assert usable_scene("x", scene, reader=lambda c: bytes(range(0, 240, 5)) * 48)


def test_excluded_scenes_never_walked():
    scenes = [{"start": i*5, "end": (i+1)*5} for i in range(10)]
    assert 3 not in worker.scene_walk(scenes, 3, {2, 3}, [3])
    assert worker.scene_walk(scenes, 0, set(), list(range(10))) == []


def test_findings_map_frame_to_actual_scene(tmp_path):
    core.dump(tmp_path / "shots.json", [{"start": 0, "end": 4, "scene": 8}])
    qa = {"issues": [{"text": "Subtitles remain at 2.5 seconds", "severity": "blocking"}, {"text": "Unknown frame"}]}
    worker.annotate_findings(qa, tmp_path)
    assert qa["issues"][0]["scene"] == 8
    assert qa["issues"][0]["time"] == 2.5
    assert "scene" not in qa["issues"][1]


def test_spend_is_project_scoped():
    db = Mock()
    db.select.return_value = [{"content_id": "filmreview-abc", "usd": .2}, {"content_id": "filmreview-abc-short1", "usd": .1}, {"content_id": "filmreview-abcd", "usd": 9}]
    assert worker.project_spend(db, "abc") == pytest.approx(.3)


def test_rerender_requires_saved_narration(video):
    from pipeline.db import DB
    state = core.create(payload(video))
    with pytest.raises(ValueError, match="Saved script and narration"):
        worker.generate(core.job_dir(state["id"]), state, only="long", rerender=True, db=DB(), claude=Mock())


def test_recap_rls_fixture_is_schema_complete(monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("recap_rls_probe", core.ROOT / "scripts/check_rls.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-fixture")
    monkeypatch.setenv("RLS_MEDIA_OBJECT", "fixture.mp4")
    monkeypatch.setattr(module, "table_names", lambda: ["recap_films"])
    calls = []
    def request(self, method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if path.endswith("/list/media"):
            return 200, []
        if kwargs.get("public"):
            return 206, None
        return 403, {"code": "42501"}
    monkeypatch.setattr(module.Checker, "request", request)
    assert module.main() == 0
    row = next(payload for method, path, payload in calls if method == "POST" and path == "/rest/v1/recap_films")
    assert row["id"].startswith("rls-probe-")
    assert {"filename", "source", "normalized_title", "file_size", "duration", "content_hash", "status"} <= row.keys()


def test_recap_review_flow_contract():
    page = (core.ROOT / "dashboard/src/app/recap/review.tsx").read_text()
    batch = (core.ROOT / "dashboard/src/app/recap/scan.tsx").read_text()
    assert '["Choose film","Generate","Review","Upload"]' in page
    assert "window.confirm" in page and "QA costs apply" in page
    assert "Avoid this shot" in page and "Accuracy check" in page
    assert "spend_usd" in page
    assert "useState(false)" in batch and "<table>" in batch and "without another estimate approval" in batch


def test_legacy_narration_reuse(tmp_path, monkeypatch):
    (tmp_path / "voice.mp3").write_bytes(b"fixture")
    core.dump(tmp_path / "voice_timings.json", [{"start": 0, "end": 2}])
    monkeypatch.setattr(worker, "probe", lambda _: {"duration": 2})
    voice = worker.saved_voice(tmp_path)
    assert voice["duration"] == 2 and voice["timings"][0]["start"] == 0


def test_on_screen_captions_are_narration_word_groups(tmp_path):
    from pipeline.recap import worker
    timings = [{"start": 0, "end": 2, "words": [{"text": w, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, w in enumerate("the gym sells a body".split())]}]
    assert worker.caption_filter(tmp_path, timings, True).startswith("subtitles=")
    text = (tmp_path / "on_screen.srt").read_text()
    assert "THE GYM SELLS" in text and "the gym" not in text
    assert all(len(line.split()) <= 3 for line in text.splitlines() if line and not line[0].isdigit())
    assert worker.caption_filter(tmp_path, [{"start": 0, "end": 2}], False) == "null"
