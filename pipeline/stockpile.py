"""Bank a complete QA-approved bundle; the manifest is the release contract."""
from __future__ import annotations
import json
from contextlib import contextmanager
import uuid
import time
from pathlib import Path
from .common import OUT_DIR, now_iso, write_json
from .drive import Drive, digest


def notes(row):
    value = (row or {}).get('qa_notes') or '{}'
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return {'legacy_notes': value}
    return parsed if isinstance(parsed, dict) else {'issues': parsed}


@contextmanager
def lock(db, name, wait_seconds=0):
    """Fail closed across runners. A crashed lock requires owner review/removal."""
    key = 'stockpile_lock_' + name
    owner = uuid.uuid4().hex
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            db.insert('settings', {'key': key, 'value': owner})
            break
        except Exception:
            # Check ownership after an uncertain insert; never remove another worker's lock.
            current = db.setting(key)
            if current == owner:
                break
            if current is None or time.monotonic() >= deadline:
                raise RuntimeError('Stockpile operation locked/unavailable; review ' + key) from None
            time.sleep(10)
    try:
        yield
    finally:
        if db.sb:
            if db.setting(key) == owner:
                db.sb.table('settings').delete().eq('key', key).execute()
        else:
            db.conn.execute('delete from settings where key=? and value=?', (key, json.dumps(owner)))
            db.conn.commit()


def preflight(db, drive=None):
    drive = drive or Drive()
    # Conservative allowance before paying for production; exact bundle checked later.
    space = drive.space(2 * 1024**3)
    db.set_setting('stockpile_drive_space', {**space, 'checked_at': now_iso()})
    return drive


def mark_banked(db, rows, metadata):
    ids = [r['id'] for r in rows]
    # One database statement makes the complete bundle visible atomically.
    # Per-row QA/checkpoints remain untouched; metadata is identical for all members.
    if db.sb:
        # Keep root-specific metadata separate before the atomic status transition.
        for row in rows:
            db.update('content', {'id': row['id']}, {'qa_notes': json.dumps({**notes(row), 'stockpile': metadata})})
        db.sb.table('content').update({'status': 'banked'}).in_('id', ids).execute()
    else:
        with db.conn:
            for row in rows:
                db.conn.execute('update content set status=?, qa_notes=? where id=?',
                    ('banked', json.dumps({**notes(row), 'stockpile': metadata}), row['id']))


def bank_bundle(db, content_id, channel, *, claude=None, drive=None):
    # Serialize quota checks/uploads across both production slots to preserve the reserve.
    with lock(db, 'drive_upload', wait_seconds=3600):
        return _bank_bundle(db, content_id, channel, claude=claude, drive=drive)


def _bank_bundle(db, content_id, channel, *, claude=None, drive=None):
    drive = drive or Drive()
    root = db.one('content', {'id': content_id})
    if notes(root).get('stockpile'):
        raise RuntimeError('Bundle already checkpointed; release or recover it before banking again')
    children = db.select('content', {'parent_id': content_id}, order='id') if root['kind'] == 'long' else []
    rows = [root, *(row for row in children if row.get('qa_status') == 'passed')]
    for row in rows:
        if row.get('placeholder') or row.get('qa_status') != 'passed':
            raise RuntimeError('Banking requires real footage and passed QA for every item')
        if db.select('publications', {'content_id': row['id']}):
            raise RuntimeError('Cannot bank content with publications')
    out = OUT_DIR / content_id
    article = None
    if root['kind'] == 'long':
        from .article import write_article
        cached = out / 'bank-article.json'
        if cached.is_file():
            article = json.loads(cached.read_text())
        else:
            article = write_article(db, content_id, claude=claude, prepare_only=True)
            write_json(cached, article)
    files = {}
    for row in rows:
        for field in ('file_path', 'thumbnail_path'):
            if row.get(field):
                path = Path(row[field])
                if not path.is_file():
                    raise FileNotFoundError('Bank media missing')
                files[path.name] = path
    # Include narration, captions, production metadata and complete QA reports.
    for path in out.rglob('*'):
        if path.is_file() and path.suffix.lower() in ('.srt', '.json', '.mp3') and path.name != 'manifest.json':
            key = path.relative_to(out).as_posix()
            files[key] = path
    total = sum(p.stat().st_size for p in files.values())
    drive.space(total + 1024**2)
    drive_root = drive.folder('Faceless Stockpile')
    parent = drive.folder(channel.key, drive_root)
    folder = drive.folder(content_id, parent)
    entries = {}
    # Flatten Drive filenames deterministically, retaining relative paths in the manifest.
    for name, path in sorted(files.items()):
        entries[name] = {'id': drive.upload(path, folder), 'size': path.stat().st_size,
                         'sha256': digest(path)}
    manifest = {'version': 1, 'content_id': content_id, 'channel': channel.key, 'created_at': now_iso(),
        'category_id': str(channel.cfg.get('category_id', '28')), 'containsSyntheticMedia': True,
        'privacy': 'private', 'content': rows, 'article': article, 'files': entries}
    manifest_path = out / 'manifest.json'
    write_json(manifest_path, manifest)
    manifest_id = drive.upload(manifest_path, folder)
    metadata = {'root_id': drive_root, 'folder_id': folder, 'manifest_id': manifest_id,
        'manifest_sha256': digest(manifest_path), 'files': entries, 'bytes': total + manifest_path.stat().st_size,
        'banked_at': now_iso(), 'released': False}
    mark_banked(db, rows, metadata)
    db.set_setting('stockpile_drive_space', {**drive.space(), 'checked_at': now_iso()})
    # Keep local checkpoints for recovery. No local deletion is needed on ephemeral runners.
    return metadata
