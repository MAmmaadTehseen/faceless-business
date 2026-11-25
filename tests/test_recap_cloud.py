"""Cloud recap flow with a fake Drive account; no network, no model calls."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline.recap import cloud, core


@pytest.fixture
def video(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")
    target = tmp_path / "fixture.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=24", "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=24000", "-t", "2", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", str(target)], check=True)
    return target


class FakeAccount:
    def __init__(self, slot, inbox):
        self.slot = slot
        self.files = {}      # id -> {name, md5Checksum, size, mimeType, parent, bytes}
        self.folder_ids = {name: f"f-{name}" for name in cloud.SUBFOLDERS}
        self.created = {}
        self.texts = {}
        for i, (name, data) in enumerate(inbox.items()):
            self.files[f"in{i}"] = {"id": f"in{i}", "name": name, "md5Checksum": f"md5-{name}", "size": str(len(data)), "mimeType": "x", "parent": "f-inbox", "bytes": data}
        self.drive = self

    def folders(self):
        return self.folder_ids

    def folder(self, name, parent=None):
        key = f"{parent}/{name}"
        self.created.setdefault(key, f"dir-{len(self.created)}")
        return self.created[key]

    def list(self, folder_id):
        return [{k: v for k, v in f.items() if k != "bytes"} for f in self.files.values() if f["parent"] == folder_id]

    def read_small(self, file_id):
        return self.files[file_id]["bytes"]

    def download(self, file_id, target, md5):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_bytes(self.files[file_id]["bytes"])
        return Path(target)

    def upload_file(self, path, parent, name=None):
        fid = f"up{len(self.files)}"
        self.files[fid] = {"id": fid, "name": name or Path(path).name, "md5Checksum": "m", "size": "1", "mimeType": "x", "parent": parent, "bytes": Path(path).read_bytes()}
        return fid

    def write_text(self, name, text, parent):
        self.texts[(parent, name)] = text
        return self.upload_file_bytes(name, text.encode(), parent)

    def upload_file_bytes(self, name, data, parent):
        fid = f"up{len(self.files)}"
        self.files[fid] = {"id": fid, "name": name, "md5Checksum": "m", "size": "1", "mimeType": "x", "parent": parent, "bytes": data}
        return fid

    def move(self, file_id, destination):
        self.files[file_id]["parent"] = destination

    def delete(self, file_id):
        self.deleted = getattr(self, "deleted", []) + [self.files.pop(file_id)["name"]]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr("pipeline.db.DATA_DIR", tmp_path)
    from pipeline.db import DB
    return DB()


def fake_runner(work, state, **kw):
    for name in core.PIECES:
        piece = work / name
        piece.mkdir(exist_ok=True)
        (piece / "video.mp4").write_bytes(b"v")
        (piece / "thumbnail.jpg").write_bytes(b"t")
        (piece / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        state.setdefault("items", {})[name] = {"title": f"T {name}", "description": "d", "segments": [], "qa": {"pass": name != "short3", "issues": []}, "duration": 30}
    state.update(status="review", stage="review", percent=100)
    core.dump(work / "state.json", state)


def test_produce_writes_review_and_moves_sources(tmp_path, monkeypatch, db, video):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    rights = json.dumps({"basis": "own work"}).encode()
    account = FakeAccount(1, {"My Film 2024.mp4": Path(video).read_bytes(), "My Film 2024.json": rights, "No Rights 2023.mp4": Path(video).read_bytes()})
    result = cloud.produce(db, [account], limit=2, runner=fake_runner, log=lambda *_: None)
    statuses = {r["status"] for r in result}
    assert statuses == {"already processed", "needs rights"}
    produced = next(r for r in result if r["status"] == "already processed")
    assert produced["queued_for_upload"]  # long passed: folder sits in approve
    assert any(k.startswith("f-approve/") for k in account.created)
    names = {f["name"] for f in account.files.values() if f["parent"] == produced["review_folder"]}
    assert {"long.mp4", "short1.jpg", "short4.srt", "state.json", "rights.json", "qa.json", "README.txt"} <= names
    assert account.files["in0"]["parent"] == "f-done" and account.files["in1"]["parent"] == "f-done"
    assert account.files["in2"]["parent"] == "f-inbox"
    assert json.loads(account.texts[(produced["review_folder"], "qa.json")])["short3"]["pass"] is False
    assert db.one("recap_films", {"id": produced["id"]})["status"] == "already processed"
    assert not (tmp_path / "inbox" / "My Film 2024.mp4").exists()
    # A second run sees the registry: the produced film is gone from the inbox and nothing is re-produced.
    again = cloud.produce(db, [account], limit=2, runner=lambda *a, **k: pytest.fail("re-produced"), log=lambda *_: None)
    assert [r["status"] for r in again] == ["needs rights"]


def test_failed_film_moves_to_failed_folder(tmp_path, monkeypatch, db, video):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    account = FakeAccount(1, {"Bad Film 2024.mp4": Path(video).read_bytes(), "Bad Film 2024.rights.json": b'{"basis": "own work"}'})

    def boom(work, state, **kw):
        (work / "transcript.json").write_text('{"language": "en", "segments": []}')
        raise ValueError("narration duration outside allowed range")
    result = cloud.produce(db, [account], runner=boom, log=lambda *_: None)
    assert result[0]["status"] == "failed"
    failed = account.files["in0"]["parent"]
    assert failed.startswith("dir-") and "narration duration" in account.texts[(failed, "error.txt")]
    assert db.one("recap_films", {"id": result[0]["id"]})["status"] == "failed"
    # The transcript survived the failure and is restored on the next attempt.
    saved = [f for f in account.files.values() if f["name"] == "transcript.json"]
    assert saved and saved[0]["parent"].startswith("dir-")
    for fid in ("in0", "in1"):
        account.files[fid]["parent"] = "f-inbox"
    seen = {}
    def again(work, state, **kw):
        seen["restored"] = (work / "transcript.json").exists()
        fake_runner(work, state, **kw)
    assert cloud.produce(db, [account], runner=again, log=lambda *_: None)[0]["status"] == "already processed"
    assert seen["restored"]


def test_upload_approved_uses_worker_and_moves_folder(tmp_path, monkeypatch, db):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    account = FakeAccount(1, {})
    folder = "appr-1"
    account.files[folder] = {"id": folder, "name": "Film (2024)", "md5Checksum": "", "size": "0", "mimeType": "application/vnd.google-apps.folder", "parent": "f-approve", "bytes": b""}
    state = {"id": "a" * 32, "title": "Film", "year": 2024, "items": {n: {"title": n, "description": "d", "segments": [], "qa": {"pass": n != "short3"}, "duration": 30} for n in core.PIECES}}
    account.upload_file_bytes("state.json", json.dumps(state).encode(), folder)
    account.upload_file_bytes("rights.json", b'{"basis": "own work"}', folder)
    for n in core.PIECES:
        for suffix in (".mp4", ".jpg", ".srt"):
            account.upload_file_bytes(n + suffix, b"x", folder)
    account.upload_file_bytes("short2.skip", b"", folder)
    seen = {}

    def fake_upload(work, st):
        seen.update({n: (i["approved"], i["discarded"]) for n, i in st["items"].items()})
        assert (work / "long" / "video.mp4").exists() and not (work / "short2").exists()
        for n, i in st["items"].items():
            if i["approved"]:
                i.update(uploaded=True, youtube={"id": "yt-" + n}, captions_uploaded=True)
        core.dump(work / "state.json", st)
    result = cloud.upload_approved(db, [account], uploader=fake_upload, log=lambda *_: None)
    assert result == [{"project_id": "a" * 32, "status": "uploaded"}]
    assert seen["long"] == (True, False) and seen["short2"] == (False, True) and seen["short3"] == (False, False)
    assert account.files[folder]["parent"] == "f-uploaded"
    assert set(json.loads(account.texts[(folder, "uploads.json")])) == {"long", "short1", "short4"}
    assert not (tmp_path / "recap" / ("a" * 32)).exists()


def test_sequels_are_distinct_but_same_film_is_duplicate(tmp_path, monkeypatch, db, video):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    data = Path(video).read_bytes()
    account = FakeAccount(1, {"Dune 2021.mp4": data, "Dune 2021.rights.json": b'{"basis": "own work"}'})
    first = cloud.produce(db, [account], runner=fake_runner, log=lambda *_: None)
    assert first[0]["status"] == "already processed"
    account = FakeAccount(2, {"Dune 2 2024.mp4": data + b"a", "Dune 2 2024.rights.json": b'{"basis": "own work"}',
                             "DUNE.2021.1080p.mkv": data + b"b", "DUNE.2021.1080p.rights.json": b'{"basis": "own work"}'})
    second = cloud.produce(db, [account], limit=5, runner=fake_runner, log=lambda *_: None)
    assert sorted(r["status"] for r in second) == ["already processed", "duplicate"]
    assert {f["parent"] for f in account.files.values() if f["name"].startswith("DUNE")} == {"f-done"}


def test_upload_frees_space_and_records(tmp_path, monkeypatch, db):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    src = FakeAccount(1, {"Film 2024.mp4": b"m", "Film 2024.rights.json": b"{}"})
    src.files["in0"]["parent"] = "f-done"; src.files["in1"]["parent"] = "f-done"
    db.upsert("recap_films", {"id": "r" * 32, "filename": "Film 2024.mp4", "source": "drive:1:in0", "normalized_title": "film", "year": 2024,
                              "file_size": 1, "duration": 1, "content_hash": "h", "status": "already processed", "project_id": "b" * 32,
                              "content_ids": "[]", "rights": "{}", "duplicate_confirmed": False}, on="id")
    account = FakeAccount(2, {})
    folder = "appr-1"
    account.files[folder] = {"id": folder, "name": "Film (2024)", "md5Checksum": "", "size": "0", "mimeType": "application/vnd.google-apps.folder", "parent": "f-approve", "bytes": b""}
    state = {"id": "b" * 32, "title": "Film", "year": 2024, "cloud_source": {"slot": 1, "film": "in0", "sidecar": "in1", "registry": "r" * 32},
             "items": {n: {"title": n, "description": "d", "segments": [], "qa": {"pass": True}, "duration": 30} for n in core.PIECES}}
    account.upload_file_bytes("state.json", json.dumps(state).encode(), folder)
    account.upload_file_bytes("rights.json", b'{"basis": "own work"}', folder)
    for n in core.PIECES:
        for suffix in (".mp4", ".jpg", ".srt"):
            account.upload_file_bytes(n + suffix, b"x", folder)

    def no_captions(work, st):
        for i in st["items"].values():
            i.update(uploaded=True, youtube={"id": "yt"})
        core.dump(work / "state.json", st)
    assert cloud.upload_approved(db, [src, account], uploader=no_captions, log=lambda *_: None)[0]["status"] == "uploaded, captions pending"
    assert account.files[folder]["parent"] == "f-approve" and not getattr(src, "deleted", [])

    def fake_upload(work, st):
        for i in st["items"].values():
            i.update(uploaded=True, youtube={"id": "yt"}, captions_uploaded=True)
        core.dump(work / "state.json", st)
    result = cloud.upload_approved(db, [src, account], uploader=fake_upload, log=lambda *_: None)
    assert result[0]["status"] == "uploaded"
    assert sorted(src.deleted) == ["Film 2024.mp4", "Film 2024.rights.json"]
    remaining = {f["name"] for f in account.files.values() if f["parent"] == folder}
    assert "long.mp4" not in remaining and {"short1.mp4", "long.jpg", "state.json", "uploads.json"} <= remaining
    assert db.one("recap_films", {"id": "r" * 32})["status"] == "uploaded"


def test_shorts_wait_when_long_failed(tmp_path, monkeypatch, db):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    account = FakeAccount(1, {})
    folder = "appr-2"
    account.files[folder] = {"id": folder, "name": "F (2024)", "md5Checksum": "", "size": "0", "mimeType": "application/vnd.google-apps.folder", "parent": "f-approve", "bytes": b""}
    state = {"id": "c" * 32, "title": "F", "year": 2024, "items": {n: {"title": n, "description": "d", "segments": [], "qa": {"pass": n != "long"}, "duration": 30} for n in core.PIECES}}
    account.upload_file_bytes("state.json", json.dumps(state).encode(), folder)
    account.upload_file_bytes("rights.json", b'{"basis": "own work"}', folder)
    for n in core.PIECES:
        account.upload_file_bytes(n + ".mp4", b"x", folder)
    seen = {}
    cloud.upload_approved(db, [account], uploader=lambda w, st: seen.update({n: i["approved"] for n, i in st["items"].items()}), log=lambda *_: None)
    assert not any(seen.values())


def test_drive_metadata_calls_retry_transient_errors():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise BrokenPipeError("ssl send")
        return "ok"
    assert cloud.retrying(flaky, "move", sleep=lambda _: None) == "ok" and len(calls) == 3

    def fatal():
        raise ValueError("bad request")
    with pytest.raises(ValueError):
        cloud.retrying(fatal, "move", sleep=lambda _: None)


def test_assembly_repeats_short_scenes_without_stream_loop(tmp_path, monkeypatch, video):
    from pipeline.recap import worker
    monkeypatch.setattr(worker, "RENDER_SIZES", {False: (160, 90), True: (90, 160)})
    scenes = [{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 2.0}]
    item = {"segments": [{"text": "a b c", "scene": 0}]}
    audio = tmp_path / "voice.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000", "-t", "6", str(audio)], check=True)
    voice = {"audio": audio, "duration": 6.0, "timings": [{"start": 0, "end": 6, "words": [{"text": "a", "start": 0, "end": 1}]}]}
    out = worker.assemble(Path(video), scenes, item, voice, tmp_path, False)
    chain = (tmp_path / "chain-0.txt").read_text().splitlines()
    assert len(chain) >= 4 and all(line.startswith("file '/") for line in chain)
    assert abs(core.probe(out)["duration"] - 6.0) < 0.6


def test_upload_file_replaces_same_name(tmp_path):
    class Service:
        def __init__(self):
            self.rows = [{"id": "s1", "name": "state.json", "md5Checksum": "old", "size": "1", "mimeType": "x"}]
            self.updated = []
        def files(self):
            svc = self
            class Files:
                def list(self, **kw):
                    class R:
                        def execute(_):
                            return {"files": svc.rows}
                    return R()
                def update(self, fileId, media_body, fields):
                    class R:
                        resumable = True
                        def next_chunk(_, **kw):
                            svc.updated.append(fileId)
                            return None, {"id": fileId}
                    return R()
            return Files()
    service = Service()
    account = cloud.Account(1, service=service)
    local = tmp_path / "state.json"
    local.write_text("{}")
    assert account.upload_file(local, "folder") == "s1" and service.updated == ["s1"]


def test_quota_exhaustion_defers_instead_of_failing(tmp_path, monkeypatch, db):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    account = FakeAccount(1, {})
    folder = "appr-3"
    account.files[folder] = {"id": folder, "name": "Q (2024)", "md5Checksum": "", "size": "0", "mimeType": "application/vnd.google-apps.folder", "parent": "f-approve", "bytes": b""}
    state = {"id": "d" * 32, "title": "Q", "year": 2024, "items": {"long": {"title": "t", "description": "d", "segments": [], "qa": {"pass": True}, "duration": 300}}}
    account.upload_file_bytes("state.json", json.dumps(state).encode(), folder)
    account.upload_file_bytes("rights.json", b'{"basis": "own work"}', folder)
    account.upload_file_bytes("long.mp4", b"x", folder)

    def quota(work, st):
        raise ValueError("YouTube quota exhausted; retained locally. Retry Upload when quota resets.")
    result = cloud.upload_approved(db, [account], uploader=quota, log=lambda *_: None)
    assert result == [{"project_id": "d" * 32, "status": "upload deferred (quota)"}]
    assert account.files[folder]["parent"] == "f-approve"


def _produced_project(account, folder, destination, project_id, uploaded_long=False, film_id="in0"):
    account.files[folder] = {"id": folder, "name": "Film (2024)", "md5Checksum": "", "size": "0", "mimeType": "application/vnd.google-apps.folder", "parent": f"f-{destination}", "bytes": b""}
    state = {"id": project_id, "title": "Film", "year": 2024, "source": "/old/inbox/Film 2024.mp4", "batch_resume": True, "bed": 0,
             "plan": {"estimate_usd": 1.0}, "cloud_source": {"slot": 1, "film": film_id, "sidecar": "in1", "registry": "r" * 32},
             "items": {n: {"title": n, "description": "d", "segments": [], "qa": {"pass": n != "short2", "issues": [{"severity": "blocking", "text": "x"}] if n == "short2" else []},
                           "duration": 30, "uploaded": uploaded_long and n == "long"} for n in core.PIECES}}
    account.upload_file_bytes("state.json", json.dumps(state).encode(), folder)
    account.upload_file_bytes("rights.json", b'{"basis": "own work"}', folder)
    for n in core.PIECES:
        for suffix in (".mp4", ".jpg", ".srt"):
            account.upload_file_bytes(n + suffix, b"old", folder)
    return state


def test_regenerate_replaces_one_piece_in_place(tmp_path, monkeypatch, db):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    project = "e" * 32
    src = FakeAccount(1, {"Film 2024.mp4": b"movie", "Film 2024.rights.json": b"{}"})
    src.files["in0"]["parent"] = "f-done"; src.files["in1"]["parent"] = "f-done"
    cp = src.folder("r" * 32, "f-checkpoints")
    src.upload_file_bytes("transcript.json", b'{"language": "en", "segments": []}', cp)
    src.upload_file_bytes("scenes.json", b"[]", cp)
    db.upsert("recap_films", {"id": "r" * 32, "filename": "Film 2024.mp4", "source": "drive:1:in0", "normalized_title": "film", "year": 2024,
                              "file_size": 1, "duration": 1, "content_hash": "h", "status": "already processed", "project_id": project,
                              "content_ids": "[]", "rights": "{}", "duplicate_confirmed": False}, on="id")
    account = FakeAccount(2, {})
    _produced_project(account, "appr-9", "approve", project, uploaded_long=True)
    seen = {}

    def runner(work, state, only=None, **kw):
        seen.update(only=only, source=Path(state["source"]).read_bytes(), batch_resume=state.get("batch_resume"),
                    transcript=(work / "transcript.json").exists(), scenes=(work / "scenes.json").exists(),
                    rights=(work / "rights.json").exists())
        piece = work / only
        piece.mkdir()
        (piece / "video.mp4").write_bytes(b"new")
        (piece / "thumbnail.jpg").write_bytes(b"newt")
        (piece / "captions.srt").write_text("1\n")
        state["items"][only].update(title="fresh", qa={"pass": True, "issues": []}, duration=31)
        core.dump(work / "state.json", state)
    result = cloud.regenerate(db, [src, account], project, "short2", runner=runner, log=lambda *_: None)
    assert result == {"project_id": project, "piece": "short2", "status": "regenerated", "folder": "approve", "queued_for_upload": True}
    assert seen == {"only": "short2", "source": b"movie", "batch_resume": None, "transcript": True, "scenes": True, "rights": True}
    folder_files = [f for f in account.files.values() if f["parent"] == "appr-9"]
    latest = {}
    for f in folder_files:
        latest[f["name"]] = f["bytes"]
    assert latest["short2.mp4"] == b"new" and latest["short2.jpg"] == b"newt" and latest["short1.mp4"] == b"old"
    state = json.loads(latest["state.json"])
    assert state["items"]["short2"]["qa"]["pass"] and state["items"]["short2"]["title"] == "fresh"
    assert state["batch_resume"] is True and state["source"] == "/old/inbox/Film 2024.mp4" and state["items"]["long"]["uploaded"]
    assert json.loads(account.texts[("appr-9", "qa.json")])["short2"]["pass"] is True
    assert account.files["appr-9"]["parent"] == "f-approve"
    assert src.files["in0"]["parent"] == "f-done" and not getattr(src, "deleted", [])
    assert not (tmp_path / "inbox" / "Film 2024.mp4").exists() and not (tmp_path / "recap" / project).exists()


def test_regenerate_finds_source_by_filename_and_fails_when_deleted(tmp_path, monkeypatch, db):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    project = "f" * 32
    db.upsert("recap_films", {"id": "r" * 32, "filename": "Film 2024.mp4", "source": "drive:1:zzz", "normalized_title": "film", "year": 2024,
                              "file_size": 1, "duration": 1, "content_hash": "h", "status": "already processed", "project_id": project,
                              "content_ids": "[]", "rights": "{}", "duplicate_confirmed": False}, on="id")
    account = FakeAccount(1, {"Film 2024.mp4": b"movie"})
    account.files["in0"]["parent"] = "f-done"
    account.files["other"] = dict(account.files["in0"], id="other")  # the id in cloud_source no longer exists
    _produced_project(account, "rev-1", "review", project, film_id="gone")
    seen = {}

    def runner(work, state, only=None, **kw):
        seen["source"] = Path(state["source"]).read_bytes()
        (work / only).mkdir()
        (work / only / "video.mp4").write_bytes(b"n")
        state["items"][only]["qa"] = {"pass": False, "issues": []}
        core.dump(work / "state.json", state)
    result = cloud.regenerate(db, [account], project, "short2", runner=runner, log=lambda *_: None)
    assert seen["source"] == b"movie" and result["status"] == "qa failed" and result["queued_for_upload"] is False
    account.files["in0"]["parent"] = "f-failed"; account.files["other"]["parent"] = "f-failed"
    with pytest.raises(ValueError, match="no longer in done/"):
        cloud.regenerate(db, [account], project, "short2", runner=runner, log=lambda *_: None)
    with pytest.raises(ValueError, match="not found"):
        cloud.regenerate(db, [account], "0" * 32, "short2", runner=runner, log=lambda *_: None)
    with pytest.raises(ValueError, match="already uploaded"):
        up = FakeAccount(3, {})
        _produced_project(up, "appr-u", "approve", "1" * 32, uploaded_long=True)
        cloud.regenerate(db, [up], "1" * 32, "long", runner=runner, log=lambda *_: None)


def test_social_skips_without_meta_and_posts_long_once(db, monkeypatch):
    from pipeline.publish import meta
    monkeypatch.setattr(meta, "configured", lambda: False)
    assert "skipped" in cloud.social(db, log=lambda *_: None)
    monkeypatch.setattr(meta, "configured", lambda: True)
    monkeypatch.setattr(meta, "fb_configured", lambda: True)
    monkeypatch.setattr("pipeline.publish.follow_youtube_to_reels", lambda db, ch: 2)
    from datetime import datetime, timezone
    db.conn.execute("insert into content (id, channel, kind, topic, title, status) values (?, ?, ?, ?, ?, ?)", ("filmreview-x-long", "filmreview", "long", "T", "Film recap", "published"))
    db.upsert("publications", {"id": 777, "content_id": "filmreview-x-long", "platform": "youtube", "status": "live", "privacy": "public",
                               "platform_id": "yt1", "publish_at": datetime.now(timezone.utc).isoformat()}, on="id")
    posted = []
    monkeypatch.setattr(meta, "publish_facebook_link_post", lambda m, l: posted.append((m, l)) or {"id": "p1", "url": "https://www.facebook.com/p1"})
    assert cloud.social(db, log=lambda *_: None) == {"reels": 2, "facebook_posts": 1, "retired_short_files": 0}
    assert posted[0][1] == "https://youtu.be/yt1" and "Film recap" in posted[0][0]
    assert cloud.social(db, log=lambda *_: None) == {"reels": 2, "facebook_posts": 0, "retired_short_files": 0}


def test_short_media_retired_after_reels_or_grace(tmp_path, monkeypatch, db):
    from datetime import datetime, timedelta, timezone
    from pipeline.publish import meta
    monkeypatch.setattr(meta, "ig_configured", lambda: True)
    monkeypatch.setattr(meta, "fb_configured", lambda: False)
    account = FakeAccount(1, {})
    folder = "up-1"
    account.files[folder] = {"id": folder, "name": "F (2024)", "md5Checksum": "", "size": "0", "mimeType": "application/vnd.google-apps.folder", "parent": "f-uploaded", "bytes": b""}
    state = {"id": "e" * 32, "items": {}}
    account.upload_file_bytes("state.json", json.dumps(state).encode(), folder)
    for n in ("short1", "short2", "short3"):
        account.upload_file_bytes(n + ".mp4", b"x", folder)
        db.conn.execute("insert into content (id, channel, kind, topic, title, status) values (?, ?, ?, ?, ?, ?)", (f"filmreview-{'e'*32}-{n}", "filmreview", "short", "T", "T", "published"))
    old = (datetime.now(timezone.utc) - timedelta(days=12)).isoformat()
    new = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    db.upsert("publications", {"id": 1, "content_id": f"filmreview-{'e'*32}-short1", "platform": "youtube", "status": "live", "publish_at": new}, on="id")
    db.upsert("publications", {"id": 2, "content_id": f"filmreview-{'e'*32}-short1", "platform": "instagram", "status": "live"}, on="id")
    db.upsert("publications", {"id": 3, "content_id": f"filmreview-{'e'*32}-short2", "platform": "youtube", "status": "live", "publish_at": old}, on="id")
    db.upsert("publications", {"id": 4, "content_id": f"filmreview-{'e'*32}-short3", "platform": "youtube", "status": "live", "publish_at": new}, on="id")
    assert cloud.retire_reel_media(db, [account], log=lambda *_: None) == 2
    remaining = {f["name"] for f in account.files.values() if f["parent"] == folder}
    assert remaining == {"state.json", "short3.mp4"}


def test_regenerate_promotes_review_folder_once_long_passes(tmp_path, monkeypatch, db):
    """A folder parked in review/ because its long failed QA moves to approve/ when the regenerated long passes,
    even while another piece still fails; the upload run then takes every passing piece."""
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    project = "g" * 32
    src = FakeAccount(1, {"Film 2024.mp4": b"movie", "Film 2024.rights.json": b"{}"})
    src.files["in0"]["parent"] = "f-done"; src.files["in1"]["parent"] = "f-done"
    db.upsert("recap_films", {"id": "r" * 32, "filename": "Film 2024.mp4", "source": "drive:1:in0", "normalized_title": "film", "year": 2024,
                              "file_size": 1, "duration": 1, "content_hash": "h", "status": "already processed", "project_id": project,
                              "content_ids": "[]", "rights": "{}", "duplicate_confirmed": False}, on="id")
    account = FakeAccount(2, {})
    state = _produced_project(account, "rev-3", "review", project)
    state["items"]["long"]["qa"] = {"pass": False, "issues": [{"severity": "blocking", "text": "cropped"}]}
    account.upload_file_bytes("state.json", json.dumps(state).encode(), "rev-3")

    def runner(work, state, only=None, **kw):
        piece = work / only
        piece.mkdir()
        (piece / "video.mp4").write_bytes(b"new")
        state["items"][only].update(qa={"pass": True, "issues": []})
        core.dump(work / "state.json", state)
    result = cloud.regenerate(db, [src, account], project, "long", runner=runner, log=lambda *_: None)
    assert result == {"project_id": project, "piece": "long", "status": "regenerated", "folder": "approve", "queued_for_upload": True}
    assert account.files["rev-3"]["parent"] == "f-approve"
    latest = json.loads([f for f in account.files.values() if f["parent"] == "rev-3" and f["name"] == "state.json"][-1]["bytes"])
    assert latest["items"]["long"]["qa"]["pass"] and not latest["items"]["short2"]["qa"]["pass"]


def test_claimed_film_is_skipped_by_parallel_job(tmp_path, monkeypatch, db, video):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    rights = b'{"basis": "own work"}'
    account = FakeAccount(1, {"Film A 2020.mp4": Path(video).read_bytes(), "Film A 2020.json": rights,
                              "Film B 2021.mp4": Path(video).read_bytes(), "Film B 2021.json": rights})
    taken = cloud.film_id("md5-Film A 2020.mp4")
    assert cloud.claim_film(db, taken)            # another job owns Film A
    assert not cloud.claim_film(db, taken)        # and nobody else can take it
    result = cloud.produce(db, [account], limit=2, runner=fake_runner, log=lambda *_: None, claim=True)
    assert [r["id"] for r in result] == [cloud.film_id("md5-Film B 2021.mp4")]
    assert account.files["in0"]["parent"] == "f-inbox"
    # A stale claim (cancelled runner) is taken over.
    db.set_setting("recap_claim_" + taken, "dead@1")
    assert cloud.claim_film(db, taken)


def test_homelab_holds_film_and_checkpoints_and_drive_copy_goes(tmp_path, monkeypatch, db, video):
    monkeypatch.setattr(core, "OUTPUT", tmp_path / "recap")
    monkeypatch.setattr(cloud, "INBOX_DIR", tmp_path / "inbox")
    root = tmp_path / "stock"
    monkeypatch.setenv("STOCKPILE_BACKEND", "homelab")
    monkeypatch.setenv("HOMELAB_LOCAL", "1")
    monkeypatch.setenv("HOMELAB_STOCKPILE_ROOT", str(root))
    monkeypatch.setattr("pipeline.homelab_store.FLOOR", 0)

    def runner(work, state, **kw):
        (work / "transcript.json").write_text("{}")
        fake_runner(work, state)
    account = FakeAccount(1, {"My Film 2024.mp4": Path(video).read_bytes(), "My Film 2024.json": json.dumps({"basis": "own work"}).encode()})
    [result] = cloud.produce(db, [account], limit=1, runner=runner, log=lambda *_: None)
    assert result["status"] == "already processed"
    assert "in0" not in account.files and account.files["in1"]["parent"] == "f-done"
    film_dir = root / "recap" / result["id"]
    assert (film_dir / "transcript.json").exists()
    assert any(p.name.endswith("My Film 2024.mp4") for p in film_dir.iterdir())
    state = json.loads((core.job_dir(result["project_id"]) / "state.json").read_text())
    fetched = cloud.fetch_source(db, [account], state, log=lambda *_: None)
    assert fetched.read_bytes() == Path(video).read_bytes()
    cloud.free_space(account, [account], "x", {}, state, lambda *_: None)
    assert not film_dir.exists()
