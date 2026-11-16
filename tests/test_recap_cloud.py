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
    account = FakeAccount(1, {"My Film 2024.mp4": Path(video).read_bytes(), "My Film 2024.rights.json": rights, "No Rights 2023.mp4": Path(video).read_bytes()})
    result = cloud.produce(db, [account], limit=2, runner=fake_runner, log=lambda *_: None)
    statuses = {r["status"] for r in result}
    assert statuses == {"already processed", "needs rights"}
    produced = next(r for r in result if r["status"] == "already processed")
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
        raise ValueError("narration duration outside allowed range")
    result = cloud.produce(db, [account], runner=boom, log=lambda *_: None)
    assert result[0]["status"] == "failed"
    failed = account.files["in0"]["parent"]
    assert failed.startswith("dir-") and "narration duration" in account.texts[(failed, "error.txt")]
    assert db.one("recap_films", {"id": result[0]["id"]})["status"] == "failed"


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
                i.update(uploaded=True, youtube={"id": "yt-" + n})
        core.dump(work / "state.json", st)
    result = cloud.upload_approved(db, [account], uploader=fake_upload, log=lambda *_: None)
    assert result == [{"project_id": "a" * 32, "status": "uploaded"}]
    assert seen["long"] == (True, False) and seen["short2"] == (False, True) and seen["short3"] == (False, False)
    assert account.files[folder]["parent"] == "f-uploaded"
    assert set(json.loads(account.texts[(folder, "uploads.json")])) == {"long", "short1", "short4"}
    assert not (tmp_path / "recap" / ("a" * 32)).exists()
