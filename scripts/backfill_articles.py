#!/usr/bin/env python3
"""Backfill articles from saved scripts. Dry-run performs reads only, without Claude."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import OUT_DIR
from pipeline.article import write_article
from scripts.audit_videos import production_db, read_table, gh_json, RemoteArchive, dt
from datetime import datetime, timezone


class ScriptSources:
    def __init__(self, out_dir=OUT_DIR):
        self.out_dir = out_dir
        self.archived = None
        self.errors = []

    def load_archives(self):
        self.archived = {}
        page = 1
        while True:
            rows = gh_json('api', f'repos/{{owner}}/{{repo}}/actions/artifacts?per_page=100&page={page}').get('artifacts', [])
            for artifact in rows:
                if artifact.get('expired') or not artifact['name'].startswith('videos-'):
                    continue
                if artifact.get('expires_at') and dt(artifact['expires_at']) <= datetime.now(timezone.utc):
                    continue
                try:
                    with zipfile.ZipFile(RemoteArchive(artifact['id'], artifact['size_in_bytes'])) as archive:
                        for name in archive.namelist():
                            path = Path(name)
                            if path.name == 'script.json':
                                data = json.loads(archive.read(name))
                                if usable(data):
                                    self.archived.setdefault(path.parent.name, (data, 'artifact:' + artifact['name']))
                except Exception as exc:
                    self.errors.append(f"{artifact['name']}: {type(exc).__name__}")
            if len(rows) < 100:
                break
            page += 1

    def find(self, row):
        path = self.out_dir / row['id'] / 'script.json'
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                if usable(data):
                    return data, str(path.relative_to(self.out_dir.parent))
            except (ValueError, OSError):
                pass
        if self.archived is None:
            try:
                self.load_archives()
            except Exception as exc:
                self.errors.append(f'artifact listing: {type(exc).__name__}')
                self.archived = self.archived or {}
        if row['id'] in self.archived:
            return self.archived[row['id']]
        if (row.get('script') or '').strip():
            return {'title': row['title'], 'script': [row['script']]}, 'DB:content.script'
        return None, None


def usable(data):
    return (isinstance(data, dict) and isinstance(data.get('title'), str)
            and isinstance(data.get('script'), list) and bool(data['script'])
            and all(isinstance(p, str) and p.strip() for p in data['script']))


def candidates(content, pubs, articles):
    existing = {a.get('content_id') or a['id'] for a in articles}
    live = {p['content_id'] for p in pubs if p['platform'] == 'youtube'
            and p.get('status') == 'live' and p.get('platform_id')}
    return sorted((c for c in content if c['kind'] == 'long' and c['id'] in live
                   and c['id'] not in existing and c.get('status') != 'killed'), key=lambda c: c['id'])


def backfill(db, *, apply=False, limit=None, sources=None):
    if limit is not None and limit < 1:
        raise ValueError('limit must be positive')
    rows = candidates(*(read_table(db, t) for t in ('content', 'publications', 'articles')))
    sources = sources or ScriptSources()
    missing, failed = [], []
    selected = rows[:limit] if limit else rows
    print(f"{'APPLY' if apply else 'DRY RUN'}: {len(selected)} of {len(rows)} missing articles; estimate $0.60 each (validation retries may cost more)")
    found = 0
    for row in selected:
        cid = row['id']
        data, source = sources.find(row)
        if data is None:
            missing.append(cid)
            continue
        found += 1
        print(f'{cid} | {source} | $0.60')
        if apply:
            # Recheck immediately before spending; never force an existing article.
            try:
                if db.one('articles', {'content_id': cid}):
                    print('  skipped: article already exists')
                    continue
                write_article(db, cid, script_data=data)
                print('  saved')
            except Exception as exc:
                failed.append(cid)
                print(f'  failed: {type(exc).__name__}: {exc}; continuing')
    print(f'Recoverable: {found}; estimated cost ${found * .60:.2f}')
    print('No script source: ' + (', '.join(missing) or 'none'))
    for error in sources.errors:
        print('Artifact read incomplete: ' + error)
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    raise SystemExit(bool(backfill(production_db(), apply=args.apply, limit=args.limit)))


if __name__ == '__main__':
    main()
