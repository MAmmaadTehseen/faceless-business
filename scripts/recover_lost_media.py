"""Find queued YouTube media needing rebuilds. Never dispatch workflows."""
import argparse
import json
import os
import shlex
import sys
from pathlib import Path

# Recovery must only use explicitly exported configuration, never local .env.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.db import DB
from pipeline.retry import restore, _json


def recover(db, *, apply=False):
    groups = {}
    for pub in db.select('publications', {'platform': 'youtube', 'status': 'queued'}):
        if pub.get('platform_id') or _json(pub.get('error')).get('upload_uncertain'):
            continue
        row = db.one('content', {'id': pub['content_id']})
        if not row or row.get('status') == 'killed':
            continue
        try:
            restore(db, row, pub)
            continue
        except FileNotFoundError:
            pass
        parent = row.get('parent_id') or row['id']
        groups.setdefault(parent, []).append(pub)
        if apply:
            info = _json(pub.get('error'))
            info['drain_attempts'] = 0
            # Compare-and-set: never overwrite an intervening upload or retry.
            db.update('publications', {'id': pub['id'], 'status': 'queued',
                                      'error': pub.get('error'), 'platform_id': None},
                      {'error': json.dumps(info)})
    for parent, pubs in sorted(groups.items()):
        print(f"{parent}: lost media for queued publications " + ', '.join(str(p['id']) for p in pubs))
        print('gh workflow run produce.yml -f resume_id=' + shlex.quote(parent) +
              ' -f rebuild=true -f privacy=private')
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_SERVICE_KEY'):
        parser.exit(2, 'DB unavailable: export Supabase configuration; .env is never loaded.\n')
    if os.getenv('DB_BACKEND') == 'sqlite':
        parser.exit(2, 'Recovery requires Supabase; refusing to initialize a local database.\n')
    recover(DB(), apply=args.apply)


if __name__ == '__main__':
    main()
