"""Sequential, restartable local batches. Never uploads."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
from . import core
from .source import LocalFolder


def parse_name(name):
    stem = Path(name).stem
    match = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', stem)
    year = int(match[1]) if match else None
    title = stem[:match.start()] if match else stem
    title = re.split(r'(?i)\b(?:\d{3,4}p|[xh]26[45]|web[ ._-]?rip|web[ ._-]?dl|bluray|brrip|dvdrip|hdtv)\b', title)[0]
    title = re.sub(r'[^\w]+', ' ', title.replace('_', ' ')).strip().casefold()
    return title, year


def display_title(filename, normalized):
    """Title as written in the filename (dots/underscores as spaces); the casefolded form is only for matching."""
    stem = Path(filename).stem
    raw = re.sub(r'[._]+', ' ', stem)
    match = re.search(r'(?i)\b' + r'\W+'.join(map(re.escape, normalized.split())) + r'\b', raw)
    return (match[0].strip() if match else normalized).strip() or normalized


def fast_hash(source, path, chunk=1024*1024):
    size = source.size(path)
    digest = hashlib.sha256(str(size).encode())
    with source.open(path) as stream:
        for offset in (0, max(0, (size-chunk)//2), max(0, size-chunk)):
            stream.seek(offset)
            digest.update(stream.read(chunk))
    return digest.hexdigest()


def duplicate_decision(film, others):
    # Rows already marked duplicate or skipped must not block the copy that gets processed.
    others = [r for r in others if r['id'] != film['id'] and r.get('status') not in ('duplicate', 'skipped')]
    if any(r['content_hash'] == film['content_hash'] for r in others):
        return 'duplicate'
    if not film.get('duplicate_confirmed') and any(
        (r['normalized_title'] == film['normalized_title'] and r['year'] == film['year'])
        or abs(r['duration']-film['duration']) <= max(2, film['duration']*.002) for r in others):
        return 'possible duplicate'
    return 'new'


def manifest(source):
    key = hashlib.sha256(str(source.folder).encode()).hexdigest()[:32]
    return core.OUTPUT / 'batches' / (key+'.json')


def scan(source, db):
    films = []
    errors = []
    for path in source.files():
        try:
            fingerprint = fast_hash(source, path)
            ident = hashlib.sha256((str(path)+fingerprint).encode()).hexdigest()[:32]
            row = db.one('recap_films', {'id': ident})
            if not row:
                title, year = parse_name(path.name)
                info = core.probe(source.materialize(path))
                row = dict(id=ident, filename=path.name, source=str(path), normalized_title=title,
                           year=year, file_size=source.size(path), duration=info['duration'],
                           content_hash=fingerprint, status='new', project_id=None, content_ids='[]', rights='{}', duplicate_confirmed=False)
            if row.get('project_id'):
                state = json.loads((core.job_dir(row['project_id'])/'state.json').read_text())
                row['status'] = 'already processed' if state['status'] == 'review' else 'failed' if state['status'] == 'error' else row['status']
            if row['status'] not in {'already processed', 'skipped'}:
                decision = duplicate_decision(row, db.select('recap_films'))
                if decision != 'new':
                    row['status'] = decision
                else:
                    try:
                        rights = core.rights_gate(source.rights(path) or json.loads(row['rights']))
                        row['rights'] = json.dumps(rights)
                        if not row['year'] or not row['normalized_title']:
                            raise ValueError('Title and year required in filename')
                        if row['status'] != 'failed':
                            row['status'] = 'new'
                    except (ValueError, TypeError):
                        row['status'] = 'needs rights'
            db.upsert('recap_films', row, on='id')
            reviewed = any(parse_name(r.get('topic',''))[0] == row['normalized_title'] for r in db.select('content', {'channel':'filmreview'}))
            films.append({**row, 'title_warning': reviewed})
        except Exception:
            errors.append({'filename': path.name, 'status':'failed', 'error':'Cannot inspect file or rights sidecar'})
    estimate = round(sum(core.plan(r['duration'])['estimate_usd'] for r in films if r['status'] == 'new'), 2)
    return {'films':films+errors, 'estimate_usd':estimate, 'note':'Estimate, not a cap. Retries cost extra. No automatic uploads.'}


def run_batch(source, db, approve=False, auto_new=False, runner=None):
    from pipeline.common import CostGuard
    from .worker import generate
    runner = runner or generate
    target = manifest(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    # OS lock is released on crashes/restarts; serializes all batch workers.
    with (target.parent/'worker.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = scan(source, db)
        saved = json.loads(target.read_text()) if target.exists() else {'approved':[], 'auto_new':False}
        if approve:
            saved['approved'] = [r['id'] for r in report['films'] if r['status'] == 'new']
            saved['auto_new'] = bool(auto_new)
            core.dump(target, saved)
        candidates = [r for r in report['films'] if r['status'] == 'new' and (r['id'] in saved['approved'] or saved['auto_new'])]
        total = sum(core.plan(r['duration'])['estimate_usd'] for r in candidates)
        if candidates and not CostGuard(db).check('recap_batch', total):
            raise ValueError('Monthly budget guard refused batch')
        for row in candidates:
            try:
                # Recheck source identity and rights immediately before paid processing.
                path = Path(row['source'])
                if fast_hash(source, path) != row['content_hash']:
                    raise ValueError('Source changed; scan again')
                rights = core.rights_gate(source.rights(path) or json.loads(row['rights']))
                if row['project_id']:
                    work = core.job_dir(row['project_id'])
                    state = json.loads((work/'state.json').read_text())
                else:
                    state = core.create({'path':str(source.materialize(path)), 'title':display_title(row['filename'], row['normalized_title']), 'year':row['year'], 'rights':rights})
                    row['project_id'] = state['id']
                    db.update('recap_films', {'id':row['id']}, {'project_id':state['id']})
                    work = core.job_dir(state['id'])
                with (work/'lock').open('w') as project_lock:
                    fcntl.flock(project_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    core.dump(work/'rights.json', rights)
                    state['batch_resume'] = True
                    runner(work, state, db=db)
                db.update('recap_films', {'id':row['id']}, {'status':'already processed', 'content_ids':json.dumps(['filmreview-'+state['id']+'-'+p for p in core.PIECES])})
            except Exception as exc:
                db.update('recap_films', {'id':row['id']}, {'status':'failed'})
                if row.get('project_id'):
                    # Leave the project in a resumable error state, as the single worker does.
                    work = core.job_dir(row['project_id'])
                    state = json.loads((work/'state.json').read_text())
                    state.update(status='error', error=str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__} at {state.get('stage')}; check local dependencies and retry")
                    core.dump(work/'state.json', state)
        return scan(source, db)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', required=True)
    parser.add_argument('--approve', action='store_true', help='Approve the displayed batch estimate')
    parser.add_argument('--auto-new', action='store_true', help='After approval, allow new eligible files on subsequent runs')
    parser.add_argument('--run', action='store_true', help='Resume previously approved batch')
    parser.add_argument('--edit', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.environ.get('RECAP_LOCAL_DB'):
        os.environ['DB_BACKEND'] = 'sqlite'
    from pipeline.db import DB
    db, source = DB(), LocalFolder(args.folder)
    if args.edit:
        import sys
        edit = json.load(sys.stdin)
        row = db.one('recap_films', {'id':edit['id']})
        if not row or Path(row['source']).parent != source.folder:
            raise ValueError('Film not in folder')
        fields = {}
        if 'rights' in edit:
            fields['rights'] = json.dumps(core.rights_gate(edit['rights']))
        if edit.get('decision') == 'confirm':
            fields.update(duplicate_confirmed=True, status='new')
        elif edit.get('decision') == 'skip':
            fields['status'] = 'skipped'
        if edit.get('retry') and row['status'] == 'failed':
            fields['status'] = 'new'
            if row.get('project_id'):
                work = core.job_dir(row['project_id'])
                state = json.loads((work/'state.json').read_text())
                state['status'] = 'estimated'
                core.dump(work/'state.json', state)
        db.update('recap_films', {'id':row['id']}, fields)
    result = run_batch(source, db, args.approve, args.auto_new) if args.approve or args.run else scan(source, db)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
