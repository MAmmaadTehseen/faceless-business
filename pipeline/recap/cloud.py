"""Cloud recap: films dropped into Google Drive inboxes (up to five accounts) are produced on
GitHub Actions and written back to a review folder. YouTube upload happens only for folders
the owner has moved to "approve". Nothing is ever deleted from Drive; sources move to done/failed."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
from pathlib import Path

from . import core
from .batch import display_title, parse_name

ROOT_NAME = "Faceless Recap"
SUBFOLDERS = ("inbox", "review", "approve", "uploaded", "done", "failed", "checkpoints")
SCOPE = "https://www.googleapis.com/auth/drive"
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
MAX_SLOTS = 5
INBOX_DIR = core.ROOT / "out" / "recap-inbox"
README = ("Produced by the recap tool. Watch the videos, then MOVE this whole folder into 'approve' to upload "
          "every passing piece to YouTube (long first, Shorts on following days), or leave it here. To keep a piece "
          "out of the upload, add an empty file named <piece>.skip (for example short2.skip) before moving the folder. "
          "Uploaded folders move to 'uploaded'. Edit titles in state.json only if you know the format.\n")


TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def retrying(fn, label, attempts=6, sleep=None):
    """Repeat a small Drive metadata call on transient network/API errors (broken SSL pipes, 5xx, 429)."""
    import time
    sleep = sleep or time.sleep
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            from pipeline.drive import transient
            status = getattr(getattr(exc, "resp", None), "status", None)
            if attempt == attempts or not (transient(exc) or isinstance(exc, (OSError, ConnectionError)) or status in TRANSIENT_STATUS):
                raise
            print(f"recap cloud: {label} attempt {attempt} failed ({type(exc).__name__}); retrying")
            sleep(min(60, 5 * attempt))


class Account:
    """One Drive account with full-drive scope, so films uploaded through drive.google.com are visible."""

    def __init__(self, slot, token=None, service=None):
        self.slot = slot
        if service is None:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from google_auth_httplib2 import AuthorizedHttp
            from pipeline.drive import plain_http
            cid, secret = os.getenv("YT_CLIENT_ID"), os.getenv("YT_CLIENT_SECRET")
            if not (token and cid and secret):
                raise RuntimeError("Drive OAuth configuration missing")
            credentials = Credentials(None, refresh_token=token, client_id=cid, client_secret=secret,
                                      token_uri="https://oauth2.googleapis.com/token", scopes=[SCOPE])
            service = build("drive", "v3", http=AuthorizedHttp(credentials, http=plain_http()), cache_discovery=False)
        from pipeline.drive import Drive
        self.service = service
        self.drive = Drive(service)
        self._folders = None

    def folders(self):
        if self._folders is None:
            root = self.folder(ROOT_NAME)
            self._folders = {name: self.folder(name, root) for name in SUBFOLDERS}
        return self._folders

    def folder(self, name, parent=None):
        return retrying(lambda: self.drive.folder(name, parent), f"folder {name}")

    def list(self, folder_id):
        rows, token = [], None
        while True:
            page = retrying(lambda: self.service.files().list(q=f"'{folder_id}' in parents and trashed = false",
                                                              fields="nextPageToken,files(id,name,size,md5Checksum,mimeType)",
                                                              pageSize=200, pageToken=token).execute(), "list")
            rows += page.get("files", [])
            token = page.get("nextPageToken")
            if not token:
                return rows

    def read_small(self, file_id):
        return retrying(lambda: self.service.files().get_media(fileId=file_id).execute(), "read")

    def download(self, file_id, target, md5):
        from googleapiclient.http import MediaIoBaseDownload
        from pipeline.drive import digest, next_chunk_retrying
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and digest(target, "md5") == md5:
            return target
        temporary = target.with_name(target.name + ".part")
        try:
            with temporary.open("wb") as output:
                request = MediaIoBaseDownload(output, self.service.files().get_media(fileId=file_id), chunksize=8 * 1024**2)
                next_chunk_retrying(request, "download " + target.name)
            if digest(temporary, "md5") != md5:
                raise RuntimeError("Drive download checksum mismatch")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def upload_file(self, path, parent, name=None):
        """Upload or replace a file of that name in the folder; never leaves two copies of state.json behind."""
        from googleapiclient.http import MediaFileUpload
        from pipeline.drive import next_chunk_retrying
        path = Path(path)
        if name and name != path.name:
            staged = path.parent / name
            shutil.copyfile(path, staged)
            path = staged
        existing = [f for f in self.list(parent) if f["name"] == path.name]
        if not existing:
            return retrying(lambda: self.drive.upload(path, parent), f"upload {path.name}")
        def replace():
            request = self.service.files().update(fileId=existing[0]["id"], media_body=MediaFileUpload(str(path), resumable=True, chunksize=8 * 1024**2), fields="id")
            return next_chunk_retrying(request, "replace " + path.name)["id"]
        file_id = retrying(replace, f"replace {path.name}")
        for duplicate in existing[1:]:
            self.delete(duplicate["id"])
        return file_id

    def write_text(self, name, text, parent):
        from googleapiclient.http import MediaIoBaseUpload
        existing = [f for f in self.list(parent) if f["name"] == name]
        def write():
            media = MediaIoBaseUpload(io.BytesIO(text.encode()), mimetype="text/plain")
            if existing:
                return self.service.files().update(fileId=existing[0]["id"], media_body=media, fields="id").execute()["id"]
            return self.service.files().create(body={"name": name, "parents": [parent]}, media_body=media, fields="id").execute()["id"]
        return retrying(write, f"write {name}")

    def delete(self, file_id):
        """Permanent delete (not trash), used only after a confirmed YouTube upload."""
        retrying(lambda: self.service.files().delete(fileId=file_id).execute(), "delete")

    def move(self, file_id, destination):
        def move():
            current = self.service.files().get(fileId=file_id, fields="parents").execute().get("parents", [])
            if destination in current:
                return
            self.service.files().update(fileId=file_id, addParents=destination, removeParents=",".join(current), fields="id").execute()
        retrying(move, "move")


def accounts():
    found = []
    for slot in range(1, MAX_SLOTS + 1):
        token = os.getenv(f"GDRIVE_RECAP_REFRESH_TOKEN_{slot}")
        if token:
            found.append(Account(slot, token))
    if not found:
        raise RuntimeError("No GDRIVE_RECAP_REFRESH_TOKEN_<n> configured")
    return found


def film_id(md5):
    return hashlib.sha256(f"drive:{md5}".encode()).hexdigest()[:32]


def inbox_films(account):
    """Videos in the inbox paired with their rights sidecars; the same film in two accounts is one film."""
    folders = account.folders()
    files = account.list(folders["inbox"])
    sidecars = {f["name"]: f for f in files if f["name"].lower().endswith(".json")}
    films = []
    for f in files:
        if Path(f["name"]).suffix.lower() not in VIDEO_EXT or not f.get("md5Checksum"):
            continue
        stem = Path(f["name"]).stem
        # Either "<film>.rights.json" or plain "<film>.json" next to the video.
        films.append({"file": f, "sidecar": sidecars.get(stem + ".rights.json") or sidecars.get(stem + ".json")})
    return films


def scan(db, accounts_):
    report = []
    for account in accounts_:
        for film in inbox_films(account):
            f = film["file"]
            row = db.one("recap_films", {"id": film_id(f["md5Checksum"])})
            status = row["status"] if row else ("needs rights" if not film["sidecar"] else "new")
            report.append({"account": account.slot, "id": film_id(f["md5Checksum"]), "status": status,
                           "size": int(f.get("size", 0)), "has_rights": bool(film["sidecar"])})
    return report


def produce(db, accounts_, limit=1, runner=None, log=print, auto_upload=True):
    """Produce up to `limit` inbox films, newest account order first. Returns per-film statuses."""
    from .worker import generate
    runner = runner or generate
    results = []
    for account in accounts_:
        if len([r for r in results if r["status"] in ("already processed", "failed")]) >= limit:
            break
        folders = account.folders()
        for film in inbox_films(account):
            if len([r for r in results if r["status"] in ("already processed", "failed")]) >= limit:
                break
            f = film["file"]
            ident = film_id(f["md5Checksum"])
            row = db.one("recap_films", {"id": ident})
            if row and row["status"] in ("already processed", "uploaded", "skipped", "duplicate"):
                # Already produced elsewhere; clear the duplicate from this inbox.
                account.move(f["id"], folders["done"])
                results.append({"id": ident, "status": row["status"]})
                continue
            title, year = parse_name(f["name"])
            same = [r for r in db.select("recap_films", {"normalized_title": title}) if r["id"] != ident and r.get("year") == year
                    and r.get("status") in ("already processed", "uploaded", "new")]
            if same and year:
                # Same title and year as a film already handled (a different file of the same movie). Sequels
                # and remakes differ by title or year ("Dune" vs "Dune 2", "Avengers 2012" vs "Avengers 2016") and are produced.
                db.upsert("recap_films", {"id": ident, "filename": f["name"], "source": f"drive:{account.slot}:{f['id']}",
                                          "normalized_title": title, "year": year, "file_size": int(f.get("size", 0)), "duration": 0,
                                          "content_hash": f["md5Checksum"], "status": "duplicate", "project_id": same[0].get("project_id"),
                                          "content_ids": "[]", "rights": "{}", "duplicate_confirmed": False}, on="id")
                account.move(f["id"], folders["done"])
                if film["sidecar"]:
                    account.move(film["sidecar"]["id"], folders["done"])
                results.append({"id": ident, "status": "duplicate"})
                continue
            try:
                if not film["sidecar"]:
                    raise ValueError("rights sidecar missing")
                rights = core.rights_gate(json.loads(account.read_small(film["sidecar"]["id"]).decode()))
                if not year or not title:
                    raise ValueError("title and year required in filename")
            except (ValueError, TypeError):
                db.upsert("recap_films", {"id": ident, "filename": f["name"], "source": f"drive:{account.slot}:{f['id']}",
                                          "normalized_title": title, "year": year, "file_size": int(f.get("size", 0)), "duration": 0,
                                          "content_hash": f["md5Checksum"], "status": "needs rights", "project_id": None,
                                          "content_ids": "[]", "rights": "{}", "duplicate_confirmed": False}, on="id")
                results.append({"id": ident, "status": "needs rights"})
                continue
            local = INBOX_DIR / f["name"]
            log(f"recap cloud: downloading film {ident} from account {account.slot}")
            account.download(f["id"], local, f["md5Checksum"])
            try:
                state = core.create({"path": str(local), "title": display_title(f["name"], title), "year": year, "rights": rights})
                work = core.job_dir(state["id"])
                db.upsert("recap_films", {"id": ident, "filename": f["name"], "source": f"drive:{account.slot}:{f['id']}",
                                          "normalized_title": title, "year": year, "file_size": int(f.get("size", 0)),
                                          "duration": state["probe"]["duration"], "content_hash": f["md5Checksum"], "status": "new",
                                          "project_id": state["id"], "content_ids": "[]", "rights": json.dumps(rights), "duplicate_confirmed": False}, on="id")
                state["batch_resume"] = True
                state["cloud_source"] = {"slot": account.slot, "film": f["id"], "sidecar": film["sidecar"]["id"], "registry": ident}
                core.dump(work / "state.json", state)
                restore_checkpoints(account, ident, work)
                try:
                    runner(work, state, db=db)
                finally:
                    save_checkpoints(account, ident, work)
                state = json.loads((work / "state.json").read_text())
                # Passing recaps go straight to the upload queue; a failed long recap waits for the owner in review.
                ready = auto_upload and bool(state["items"].get("long", {}).get("qa", {}).get("pass"))
                folder = publish_review(account, work, state, "approve" if ready else "review")
                db.update("recap_films", {"id": ident}, {"status": "already processed",
                          "content_ids": json.dumps(["filmreview-" + state["id"] + "-" + p for p in core.PIECES])})
                for item in (f, film["sidecar"]):
                    account.move(item["id"], folders["done"])
                results.append({"id": ident, "status": "already processed", "project_id": state["id"], "review_folder": folder, "queued_for_upload": ready})
            except Exception as exc:
                log(f"recap cloud: film {ident} failed: {type(exc).__name__}")
                db.update("recap_films", {"id": ident}, {"status": "failed"})
                failed = account.folder(f"{display_title(f['name'], title)} ({year})", folders["failed"])
                account.write_text("error.txt", f"{type(exc).__name__}: {exc if isinstance(exc, ValueError) else 'see workflow log'}\n", failed)
                for item in (f, film["sidecar"]):
                    account.move(item["id"], failed)
                results.append({"id": ident, "status": "failed"})
            finally:
                local.unlink(missing_ok=True)
    return results


CHECKPOINTS = ("transcript.json", "scenes.json")


def restore_checkpoints(account, ident, work):
    """Transcript and scene cuts from an earlier attempt, so a retry skips the long transcription."""
    folder = account.folder(ident, account.folders()["checkpoints"])
    for f in account.list(folder):
        if f["name"] in CHECKPOINTS and f.get("md5Checksum"):
            account.download(f["id"], work / f["name"], f["md5Checksum"])
    return folder


def save_checkpoints(account, ident, work):
    folder = account.folder(ident, account.folders()["checkpoints"])
    for name in CHECKPOINTS:
        if (work / name).exists():
            try:
                account.upload_file(work / name, folder)
            except Exception as exc:
                print(f"recap cloud: checkpoint {name} not saved: {type(exc).__name__}")


def publish_review(account, work, state, destination="review"):
    """Copy the finished pieces plus their records to <destination>/<title (year)>/ and return the folder id."""
    folders = account.folders()
    folder = account.folder(f"{state['title']} ({state['year']})", folders[destination])
    for name in core.PIECES:
        piece = work / name
        if not (piece / "video.mp4").exists():
            continue
        account.upload_file(piece / "video.mp4", folder, f"{name}.mp4")
        if (piece / "thumbnail.jpg").exists():
            account.upload_file(piece / "thumbnail.jpg", folder, f"{name}.jpg")
        if (piece / "captions.srt").exists():
            account.upload_file(piece / "captions.srt", folder, f"{name}.srt")
    account.upload_file(work / "state.json", folder)
    account.upload_file(work / "rights.json", folder)
    qa = {name: {"pass": item.get("qa", {}).get("pass"), "duration": item.get("duration"), "title": item.get("title"),
                 "issues": item.get("qa", {}).get("issues", [])} for name, item in state.get("items", {}).items()}
    account.write_text("qa.json", json.dumps(qa, indent=2, ensure_ascii=False), folder)
    account.write_text("README.txt", README, folder)
    return folder


def upload_approved(db, accounts_, uploader=None, log=print):
    """Upload every approve/<folder> through the normal worker; folders move to uploaded/ on success."""
    from .worker import upload
    uploader = uploader or upload
    results = []
    for account in accounts_:
        folders = account.folders()
        for entry in account.list(folders["approve"]):
            if entry.get("mimeType") != "application/vnd.google-apps.folder":
                continue
            files = {f["name"]: f for f in account.list(entry["id"])}
            if "state.json" not in files or "rights.json" not in files:
                log(f"recap cloud: approve folder without state/rights skipped ({entry['id']})")
                continue
            state = json.loads(account.read_small(files["state.json"]["id"]).decode())
            work = core.OUTPUT / state["id"]
            work.mkdir(parents=True, exist_ok=True)
            core.dump(work / "state.json", state)
            core.dump(work / "rights.json", json.loads(account.read_small(files["rights.json"]["id"]).decode()))
            for name, item in state.get("items", {}).items():
                skip = f"{name}.skip" in files
                present = f"{name}.mp4" in files
                item["discarded"] = skip or not present
                item["approved"] = bool(item.get("qa", {}).get("pass")) and present and not skip and not item.get("uploaded")
                if item["approved"] or item.get("uploaded"):
                    piece = work / name
                    piece.mkdir(exist_ok=True)
                    for suffix, target in ((".mp4", "video.mp4"), (".jpg", "thumbnail.jpg"), (".srt", "captions.srt")):
                        f = files.get(name + suffix)
                        if f:
                            account.download(f["id"], piece / target, f["md5Checksum"])
            long_ok = state.get("items", {}).get("long", {}).get("approved") or state.get("items", {}).get("long", {}).get("uploaded")
            if not long_ok:
                for name, item in state.get("items", {}).items():
                    item["approved"] = False  # Shorts never go up without their long recap.
            core.dump(work / "state.json", state)
            try:
                uploader(work, state)
                state = json.loads((work / "state.json").read_text())
                persist_short_media(db, state, work, log)
                account.write_text("uploads.json", json.dumps({n: i.get("youtube") for n, i in state["items"].items() if i.get("uploaded")}, indent=2), entry["id"])
                account.upload_file(work / "state.json", entry["id"])
                pending = [n for n, i in state["items"].items() if i.get("uploaded") and not i.get("captions_uploaded")]
                if pending:
                    # Videos are up; captions wait for quota. The folder stays queued so a later run finishes them.
                    account.write_text("error.txt", "captions pending (YouTube quota): " + ", ".join(pending) + "\n", entry["id"])
                    results.append({"project_id": state["id"], "status": "uploaded, captions pending"})
                    continue
                account.move(entry["id"], folders["uploaded"])
                free_space(account, accounts_, entry["id"], files, state, log)
                registry = state.get("cloud_source", {}).get("registry")
                if registry:
                    db.update("recap_films", {"id": registry}, {"status": "uploaded"})
                results.append({"project_id": state["id"], "status": "uploaded"})
            except Exception as exc:
                # Partial uploads are recorded in state.json so the next run resumes idempotently.
                state = json.loads((work / "state.json").read_text())
                account.upload_file(work / "state.json", entry["id"])
                deferred = isinstance(exc, ValueError) and "quota" in str(exc).lower()
                account.write_text("error.txt", f"{type(exc).__name__}: {exc if isinstance(exc, ValueError) else 'see workflow log'}\n", entry["id"])
                # Daily YouTube quota is shared with the other channels; a queued upload is retried by the next run.
                results.append({"project_id": state["id"], "status": "upload deferred (quota)" if deferred else "upload failed"})
            finally:
                shutil.rmtree(work, ignore_errors=True)
    return results


def free_space(account, accounts_, folder_id, files, state, log):
    """After a confirmed upload: delete the source film, its sidecar and the produced MP4s from Drive.
    Thumbnails, captions, state.json and uploads.json stay as the record."""
    source = state.get("cloud_source") or {}
    owner = next((a for a in accounts_ if a.slot == source.get("slot")), None)
    for key in ("film", "sidecar"):
        if owner and source.get(key):
            try:
                owner.delete(source[key])
            except Exception as exc:
                log(f"recap cloud: could not delete source {key}: {type(exc).__name__}")
    for name, f in files.items():
        # The long MP4 goes now; Short MP4s stay until their Reels have followed (see retire_reel_media).
        if name == "long.mp4":
            try:
                account.delete(f["id"])
            except Exception as exc:
                log(f"recap cloud: could not delete {name}: {type(exc).__name__}")


def retire_reel_media(db, accounts_, log=print, grace_days=9):
    """Delete Short MP4s from uploaded/ folders once Reels are posted on every configured Meta platform,
    or once the last Short has been public for more than grace_days (the Reels window is 7 days)."""
    from datetime import datetime, timedelta, timezone
    from pipeline.publish import meta
    want = ({"instagram"} if meta.ig_configured() else set()) | ({"facebook"} if meta.fb_configured() else set())
    now = datetime.now(timezone.utc)
    removed = 0
    for account in accounts_:
        for entry in account.list(account.folders()["uploaded"]):
            if entry.get("mimeType") != "application/vnd.google-apps.folder":
                continue
            files = {f["name"]: f for f in account.list(entry["id"])}
            shorts = [n for n in files if n.startswith("short") and n.endswith(".mp4")]
            if not shorts or "state.json" not in files:
                continue
            state = json.loads(account.read_small(files["state.json"]["id"]).decode())
            for name in shorts:
                cid = "filmreview-" + state["id"] + "-" + name[:-4]
                pubs = db.select("publications", {"content_id": cid})
                have = {p["platform"] for p in pubs if p.get("status") == "live" and p["platform"] != "youtube"}
                yt = next((p for p in pubs if p["platform"] == "youtube"), None)
                public_at = datetime.fromisoformat(str(yt["publish_at"]).replace("Z", "+00:00")) if yt and yt.get("publish_at") else None
                expired = public_at is not None and now - public_at > timedelta(days=grace_days)
                if want and want <= have or expired:
                    try:
                        account.delete(files[name]["id"]); removed += 1
                    except Exception as exc:
                        log(f"recap cloud: could not delete {name}: {type(exc).__name__}")
    return removed


def find_project(accounts_, project_id, log=print):
    """Locate a produced project's folder in approve/ or review/ across accounts by its state.json id."""
    for account in accounts_:
        folders = account.folders()
        for destination in ("approve", "review"):
            for entry in account.list(folders[destination]):
                if entry.get("mimeType") != "application/vnd.google-apps.folder":
                    continue
                files = {f["name"]: f for f in account.list(entry["id"])}
                if "state.json" not in files:
                    continue
                try:
                    state = json.loads(account.read_small(files["state.json"]["id"]).decode())
                except (ValueError, UnicodeDecodeError):
                    log(f"recap cloud: unreadable state.json skipped ({entry['id']})")
                    continue
                if state.get("id") == project_id:
                    return account, destination, entry, files, state
    raise ValueError("Project not found in approve/ or review/ of any connected account")


def fetch_source(db, accounts_, state, log=print):
    """Download the original film from done/ for a re-render; clear error when it was deleted after upload."""
    source = state.get("cloud_source") or {}
    owner = next((a for a in accounts_ if a.slot == source.get("slot")), None)
    candidates = [a for a in ([owner] if owner else []) + accounts_ if a]
    row = db.one("recap_films", {"id": source["registry"]}) if source.get("registry") else None
    filename = row["filename"] if row else None
    seen = set()
    for account in candidates:
        if account.slot in seen:
            continue
        seen.add(account.slot)
        rows = [f for f in account.list(account.folders()["done"]) if f.get("md5Checksum")]
        match = next((f for f in rows if f["id"] == source.get("film")), None)
        if match is None and filename:
            match = next((f for f in rows if f["name"] == filename), None)
        if match is None:
            continue
        local = INBOX_DIR / match["name"]
        log(f"recap cloud: downloading source for {state['id']} from account {account.slot}")
        account.download(match["id"], local, match["md5Checksum"])
        return local
    raise ValueError("Source film is no longer in done/ (it is deleted after a confirmed upload); "
                     "re-upload the film and its rights sidecar to the inbox to produce it again")


def regenerate(db, accounts_, project_id, piece, runner=None, log=print):
    """Re-make one piece of a produced recap (new script, narration, render, QA) and replace it in its Drive folder.
    The folder stays where it is: a passing piece in approve/ is picked up by the next upload run."""
    from .worker import generate
    runner = runner or generate
    if piece not in core.PIECES:
        raise ValueError("Invalid piece")
    account, destination, entry, files, state = find_project(accounts_, project_id, log)
    item = state.get("items", {}).get(piece, {})
    if item.get("uploaded"):
        raise ValueError("Piece already uploaded; it cannot be regenerated")
    if "rights.json" not in files:
        raise ValueError("Project folder has no rights.json")
    work = core.OUTPUT / state["id"]
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    core.dump(work / "state.json", state)
    core.dump(work / "rights.json", json.loads(account.read_small(files["rights.json"]["id"]).decode()))
    registry = (state.get("cloud_source") or {}).get("registry")
    # Checkpoints live in the account that produced the film, which may differ from the folder's account.
    keeper = next((a for a in accounts_ if a.slot == (state.get("cloud_source") or {}).get("slot")), account)
    if registry:
        restore_checkpoints(keeper, registry, work)
    else:
        log(f"recap cloud: {project_id} has no registry id; transcript may be rebuilt")
    local = fetch_source(db, accounts_, state, log)
    original_source = state.get("source")
    state["source"] = str(local)
    # Without batch_resume the worker buys a fresh script for this one piece instead of re-narrating the old one.
    state.pop("batch_resume", None)
    core.dump(work / "state.json", state)
    try:
        try:
            runner(work, state, only=piece, db=db)
        finally:
            if registry:
                save_checkpoints(keeper, registry, work)
        state = json.loads((work / "state.json").read_text())
        state["batch_resume"] = True
        if original_source:
            state["source"] = original_source
        core.dump(work / "state.json", state)
        folder = entry["id"]
        produced = work / piece
        account.upload_file(produced / "video.mp4", folder, f"{piece}.mp4")
        for local_name, suffix in (("thumbnail.jpg", ".jpg"), ("captions.srt", ".srt")):
            if (produced / local_name).exists():
                account.upload_file(produced / local_name, folder, piece + suffix)
        account.upload_file(work / "state.json", folder)
        qa = {name: {"pass": i.get("qa", {}).get("pass"), "duration": i.get("duration"), "title": i.get("title"),
                     "issues": i.get("qa", {}).get("issues", [])} for name, i in state.get("items", {}).items()}
        account.write_text("qa.json", json.dumps(qa, indent=2, ensure_ascii=False), folder)
        passed = bool(state["items"].get(piece, {}).get("qa", {}).get("pass"))
        long_up = bool(state["items"].get("long", {}).get("uploaded"))
        long_ok = long_up or bool(state["items"].get("long", {}).get("qa", {}).get("pass"))
        if destination == "review" and long_ok:
            # The long gate is open now: promote the folder so the next upload run takes every passing piece.
            account.move(folder, account.folders()["approve"])
            destination = "approve"
        log(f"recap cloud: {project_id} {piece} regenerated; qa {'passed' if passed else 'failed'}; folder in {destination}")
        return {"project_id": project_id, "piece": piece, "status": "regenerated" if passed else "qa failed",
                "folder": destination, "queued_for_upload": passed and destination == "approve" and long_ok}
    finally:
        local.unlink(missing_ok=True)
        shutil.rmtree(work, ignore_errors=True)


def persist_short_media(db, state, work, log=print):
    """Keep a public copy of each uploaded Short so Reels can follow YouTube after the Drive MP4s are gone."""
    from pipeline.publish import _media_url
    for name, item in state.get("items", {}).items():
        video = work / name / "video.mp4"
        if name == "long" or not item.get("uploaded") or not video.exists():
            continue
        cid = "filmreview-" + state["id"] + "-" + name
        row = db.one("content", {"id": cid})
        if not row or row.get("media_url"):
            continue
        try:
            _media_url(db, {**row, "file_path": str(video)})
        except Exception as exc:
            log(f"recap cloud: media copy for {name} deferred: {type(exc).__name__}")


def stage_short_media_from_drive(db, log=print):
    """Download retained Short MP4s so the shared Reels follow-up finds a local file even without a storage copy."""
    try:
        found = accounts()
    except RuntimeError:
        return
    for account in found:
        for entry in account.list(account.folders()["uploaded"]):
            if entry.get("mimeType") != "application/vnd.google-apps.folder":
                continue
            files = {f["name"]: f for f in account.list(entry["id"])}
            if "state.json" not in files:
                continue
            state = json.loads(account.read_small(files["state.json"]["id"]).decode())
            for name, f in files.items():
                if not (name.startswith("short") and name.endswith(".mp4")):
                    continue
                cid = "filmreview-" + state["id"] + "-" + name[:-4]
                row = db.one("content", {"id": cid})
                if not row:
                    continue
                target = core.OUTPUT / state["id"] / name[:-4] / "video.mp4"
                try:
                    account.download(f["id"], target, f["md5Checksum"])
                    db.update("content", {"id": cid}, {"file_path": str(target)})
                except Exception as exc:
                    log(f"recap cloud: could not stage {name}: {type(exc).__name__}")


def social(db, log=print):
    """Reels for Shorts whose YouTube copy went public, and one Page link post per public long recap."""
    from datetime import datetime, timedelta, timezone
    from pipeline.publish import meta, follow_youtube_to_reels
    from .channel import FilmReviewChannel
    channel = FilmReviewChannel()
    meta.use_channel(channel)
    if not meta.configured():
        return {"skipped": "no Meta configuration for filmreview"}
    stage_short_media_from_drive(db, log)
    reels = follow_youtube_to_reels(db, channel)
    posts = 0
    if meta.fb_configured():
        recent = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        longs = {c["id"]: c for c in db.select("content", {"channel": channel.key, "kind": "long"})}
        for p in db.select("publications", {"platform": "youtube", "status": "live"}):
            row = longs.get(p["content_id"])
            if not row or p.get("privacy") != "public" or (p.get("publish_at") or "") < recent:
                continue
            if db.setting(f"fb_recap_post_{row['id']}"):
                continue
            url = p.get("url") or f"https://youtu.be/{p.get('platform_id')}"
            try:
                post = meta.publish_facebook_link_post(f"{row['title']}\n\nFull recap on YouTube.", url)
                db.set_setting(f"fb_recap_post_{row['id']}", {"post_id": post["id"], "url": post.get("url")})
                posts += 1
            except Exception as exc:
                log(f"recap cloud: facebook post for {row['id']} failed: {type(exc).__name__}")
    try:
        retired = retire_reel_media(db, accounts(), log)
    except RuntimeError:
        retired = 0
    return {"reels": reels, "facebook_posts": posts, "retired_short_files": retired}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["scan", "produce", "upload", "regenerate", "social"])
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--project", help="regenerate: project id (state.json id) in approve/ or review/")
    parser.add_argument("--piece", choices=list(core.PIECES), help="regenerate: which piece to re-make")
    parser.add_argument("--gated", action="store_true", help="Exit quietly unless setting recap_cloud_enabled is true")
    args = parser.parse_args()
    os.environ.setdefault("LUNAROUTE_THINKING_BUDGET", "3000")
    from pipeline.db import DB
    from pipeline.qa import _strict_enabled
    db = DB()
    if args.gated and not _strict_enabled(db.setting("recap_cloud_enabled", True)):
        print(json.dumps({"skipped": "recap_cloud_enabled is false"}))
        return
    if args.action == "social":
        try:
            print(json.dumps(social(db)))
        except Exception as exc:
            # Reels and Page posts are best effort; the next scheduled run retries them.
            print(json.dumps({"social_failed": type(exc).__name__}))
        return
    found = accounts()
    if args.action == "scan":
        print(json.dumps(scan(db, found)))
        return
    if args.action == "regenerate":
        if not args.project or not args.piece:
            parser.error("regenerate needs --project and --piece")
        result = [regenerate(db, found, args.project, args.piece)]
    elif args.action == "upload":
        result = upload_approved(db, found)
    else:
        result = produce(db, found, limit=args.limit, auto_upload=_strict_enabled(db.setting("recap_auto_upload", True)))
        if any(r.get("queued_for_upload") for r in result):
            result += upload_approved(db, found)
    print(json.dumps(result))
    if any(r["status"] in ("failed", "upload failed", "qa failed") for r in result):
        sys.exit(1)


if __name__ == "__main__":
    main()
