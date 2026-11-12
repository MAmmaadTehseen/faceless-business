"""Release oldest stockpile bundles through the normal publisher, without model calls."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from .common import Channel, OUT_DIR, now_iso, slugify, log
from .db import DB
from .drive import Drive
from .stockpile import notes, lock


def capacity(db, rows):
    today = datetime.now(timezone.utc).date().isoformat()
    used = db.one('quota_log', {'day': today}) or {}
    missing = [r for r in rows if not (db.one('publications', {'content_id': r['id'], 'platform': 'youtube'}) or {}).get('platform_id')]
    units = sum(50 for r in missing if r.get('thumbnail_path'))
    return (int(used.get('uploads', 0)) + len(missing) <= int(db.setting('youtube_uploads_per_day', 100)) - 2
            and int(used.get('units', 0)) + units <= int(db.setting('youtube_quota_units_per_day', 10000)) - 1000)


def pending(db, channel):
    # Include partially released parents: publisher may already have set status=published.
    from .evergreen import history
    if db.sb:
        ids = [r['id'] for r in history(db, channel)]
        rows = []
        for start in range(0, len(ids), 100):
            rows.extend(db.select('content', in_={'id': ids[start:start + 100]}))
    else:
        rows = db.select('content', {'channel': channel.key})
    return sorted([r for r in rows if not r.get('parent_id') and r.get('status') != 'killed'
                   and notes(r).get('stockpile') and not notes(r)['stockpile'].get('released')],
                  key=lambda r: (notes(r)['stockpile']['banked_at'], r['id']))


def release_one(db, channel, row, drive):
    from .publish import publish_all, publish_short
    checkpoint = notes(row)['stockpile']
    out = OUT_DIR / row['id']
    manifest_path = drive.download(checkpoint['manifest_id'], out / 'manifest.json', checkpoint['manifest_sha256'])
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('version') != 1 or manifest.get('content_id') != row['id'] or manifest.get('channel') != channel.key
            or manifest.get('containsSyntheticMedia') is not True):
        raise RuntimeError('Invalid stockpile manifest')
    rows = manifest['content']
    if not capacity(db, rows):
        return False
    # Validate paths before downloading; manifests cannot escape their work directory.
    for name, entry in manifest['files'].items():
        target = (out / name).resolve()
        if not target.is_relative_to(out.resolve()) or target == out.resolve():
            raise RuntimeError('Unsafe manifest path')
        drive.download(entry['id'], target, entry['sha256'])
        if target.stat().st_size != entry['size']:
            raise RuntimeError('Stockpile file size mismatch')
    for saved in rows:
        current = db.one('content', {'id': saved['id']})
        if not current or current.get('placeholder') or current.get('qa_status') != 'passed' or current.get('status') == 'killed':
            raise RuntimeError('Stockpile item no longer eligible for release')
        changes = {}
        for field in ('file_path', 'thumbnail_path'):
            if saved.get(field):
                name = Path(saved[field]).name
                if name not in manifest['files']:
                    raise RuntimeError('Manifest is missing publish media')
                changes[field] = str(out / name)
        db.update('content', {'id': saved['id']}, changes)
    channel.cfg = {**channel.cfg, 'category_id': manifest['category_id']}
    # Private scheduling is retained until the audit passes by the shared publisher.
    privacy = db.setting('publish_privacy', 'private')
    if row['kind'] == 'long':
        # Preserve child parent links: do not start Shorts until the long has a known remote ID.
        from .publish import _youtube_publish, _next_slot
        parent = db.one('publications', {'content_id': row['id'], 'platform': 'youtube'}) or {}
        if not parent.get('platform_id'):
            current = db.one('content', {'id': row['id']})
            _youtube_publish(db, current, channel, privacy, _next_slot(db, 'long', channel, content_id=row['id']))
            parent = db.one('publications', {'content_id': row['id'], 'platform': 'youtube'}) or {}
            if not parent.get('platform_id'):
                return False
        publish_all(db, row['id'], privacy, channel)
    else:
        publish_short(db, db.one('content', {'id': row['id']}), channel, privacy)
    publications = [db.one('publications', {'content_id': saved['id'], 'platform': 'youtube'}) or {} for saved in rows]
    if not all(p.get('platform_id') for p in publications):
        return False
    if manifest.get('article'):
        from .article import article_thumbnail, ping_indexnow
        from .publish.youtube_promotion import article_saved
        article = dict(manifest['article'])
        existing = db.one('articles', {'id': row['id']})
        if existing:
            article['slug'] = existing['slug']
        else:
            base = slugify(article['slug'], 60)
            suffix = 2
            article['slug'] = base
            while db.one('articles', {'slug': article['slug']}):
                tail = f'-{suffix}'
                article['slug'] = base[:60-len(tail)].rstrip('-') + tail
                suffix += 1
        article.update(youtube_id=publications[0]['platform_id'], published_at=(existing or {}).get('published_at') or now_iso(), updated_at=now_iso(),
                       thumbnail_path=article_thumbnail(db, row['id'], existing, False))
        db.upsert('articles', article, on='id')
        ping_indexnow(article['slug'])
        article_saved(db, row['id'])
    # A failed move leaves a discoverable pending checkpoint and is safe to retry.
    drive.release(checkpoint['folder_id'], checkpoint['root_id'])
    for saved in rows:
        current = db.one('content', {'id': saved['id']})
        db.update('content', {'id': saved['id']}, {'qa_notes': json.dumps({**notes(current),
            'stockpile': {**checkpoint, 'released': True, 'released_at': now_iso()}})})
    return True


def release(db, channel, maximum=1, *, scheduled=False, drive=None):
    # Disabled scheduled releases are read-only, without acquiring a lock or using Drive.
    if maximum < 1 or db.setting('pipeline_paused', False):
        return 0
    if scheduled and int(db.setting('banked_release_per_day', 0)) <= 0:
        return 0
    with lock(db, 'release_' + channel.key):
        return _release(db, channel, maximum, scheduled=scheduled, drive=drive)


def _release(db, channel, maximum=1, *, scheduled=False, drive=None):
    if maximum < 1 or db.setting('pipeline_paused', False):
        return 0
    from .publish import youtube
    youtube.use_channel(channel)
    if not youtube.configured() or youtube.auth_failed(channel):
        return 0
    rate = max(0, int(db.setting('banked_release_per_day', 0)))
    if scheduled and rate == 0:
        return 0
    day = datetime.now(timezone.utc).date().isoformat()
    ledger_key = f'banked_release_{channel.key}_{day}'
    ledger = db.setting(ledger_key, [])
    completed = 0
    for row in pending(db, channel):
        if completed >= maximum:
            break
        if scheduled and row['id'] not in ledger and len(ledger) >= rate:
            break
        children = db.select('content', {'parent_id': row['id']}) if row['kind'] == 'long' else []
        if not capacity(db, [row, *children]):
            break
        if row['id'] not in ledger:
            ledger.append(row['id'])
            db.set_setting(ledger_key, ledger)
        if release_one(db, channel, row, drive or Drive()):
            completed += 1
        else:
            break
    return completed


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--channel', required=True, choices=Channel.keys())
    ap.add_argument('--max', type=int, default=1)
    ap.add_argument('--scheduled', action='store_true')
    args = ap.parse_args()
    try:
        print(f'Released {release(DB(), Channel(args.channel), args.max, scheduled=args.scheduled)} bundles')
    except Exception as exc:
        # Provider exceptions can contain transport details; keep CLI logs safe.
        log.error('Stockpile release stopped (%s); checkpoint retained', type(exc).__name__)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
