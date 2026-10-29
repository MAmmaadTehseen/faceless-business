#!/usr/bin/env python3
"""Anon-only regression probes. Never reads .env or uses a service key.

Only unique probe rows/objects are mutated. A broken policy may leave probe data;
FAIL output identifies the table/bucket without printing response bodies or keys.
Empty RLS-filtered Storage results prove no disclosure/deletion for that request,
not the absence of grants. SQL catalog review remains necessary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    # Never forward credentials to a redirect destination.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Checker:
    def __init__(self, url: str, key: str):
        self.url, self.key = url.rstrip('/'), key
        self.failed = 0
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, payload=None, *, raw=False, public=False):
        headers = {} if public else {'apikey': self.key, 'Authorization': f'Bearer {self.key}'}
        if payload is not None:
            headers['Content-Type'] = 'video/mp4' if raw else 'application/json'
            payload = payload if raw else json.dumps(payload).encode()
        if path.startswith('/rest/v1/'):
            headers['Prefer'] = 'return=representation'
        if public:
            headers['Range'] = 'bytes=0-0'
        try:
            with self.opener.open(Request(self.url + path, data=payload, headers=headers,
                                          method=method), timeout=30) as response:
                if public:
                    response.read(1)  # Do not download an entire video.
                    return response.status, None
                body = response.read(65536)
                try:
                    return response.status, json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    return response.status, None
        except HTTPError as error:
            try:
                body = json.loads(error.read(65536))
            except (ValueError, UnicodeDecodeError):
                body = None
            return error.code, body
        except (URLError, TimeoutError, OSError):
            return 0, None

    def report(self, label, passed, detail):
        print(f'{"PASS" if passed else "FAIL"} {label}: {detail}')
        self.failed += not passed

    def denied(self, label, result, *, storage=False, filtered=False):
        status, body = result
        code = str(body.get('code', '')) if isinstance(body, dict) else ''
        message = str(body.get('message', '')).lower() if isinstance(body, dict) else ''
        # Invalid keys, missing objects/functions, validation errors and outages
        # are never evidence that authorization works.
        denied = (status in (401, 403) and code == '42501')
        if storage:
            denied = denied or (status in (400, 403) and isinstance(body, dict)
                                and ('row-level security' in message or 'permission denied' in message
                                     or body.get('error') in ('AccessDenied', 'Unauthorized')))
        empty = filtered and 200 <= status < 300 and body == []
        self.report(label, denied or empty,
                    'denied' if denied else 'RLS filtered: no objects affected/returned' if empty
                    else f'HTTP {status}; access succeeded or denial unverified')


def table_names():
    root = Path(__file__).resolve().parents[1] / 'supabase'
    sql = '\n'.join(p.read_text() for p in [root / 'schema.sql', *sorted((root / 'migrations').glob('*.sql'))])
    return sorted(set(re.findall(r'create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?(\w+)\s*\(', sql, re.I)))


def main():
    url, key = os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_ANON_KEY')
    if not url or not key:
        print('Set SUPABASE_URL and SUPABASE_ANON_KEY in your shell, then run:')
        print('  python3 scripts/check_rls.py')
        print('Use the project anon key supplied by the owner; never use the service role key.')
        return 2
    parts = urlsplit(url)
    if parts.scheme not in ('https', 'http') or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
        print('SUPABASE_URL must be a project HTTP(S) URL without credentials or query parameters.')
        return 2
    # Reject accidental service-role or authenticated JWTs before any mutation.
    if key.startswith('sb_secret_'):
        print('Refusing a secret key. Supply the anon key.')
        return 2
    if key.count('.') == 2:
        import base64
        try:
            claims = json.loads(base64.urlsafe_b64decode(key.split('.')[1] + '==='))
        except (ValueError, UnicodeDecodeError):
            print('Invalid anon JWT format.')
            return 2
        if claims.get('role') != 'anon':
            print('Refusing a JWT whose role is not anon.')
            return 2
    c = Checker(url, key)
    marker = 'rls-probe-' + uuid.uuid4().hex
    numeric_id = -int(uuid.uuid4().hex[:14], 16)
    rows = {
        'content': {'id': marker, 'kind': 'short', 'topic': marker, 'title': marker},
        'publications': {'id': numeric_id, 'platform': marker},
        'metrics': {'id': numeric_id, 'views': 0},
        'comments': {'id': numeric_id, 'platform': marker, 'platform_comment_id': marker, 'text': marker},
        'topic_queue': {'id': numeric_id, 'topic': marker},
        'costs': {'id': numeric_id, 'step': marker, 'usd': 0},
        'settings': {'key': marker, 'value': False},
        'runs': {'id': numeric_id, 'workflow': marker},
        'articles': {'id': marker, 'slug': marker, 'title': marker},
        'quota_log': {'day': marker, 'units': 0, 'uploads': 0},
        'hub_events': {'id': numeric_id, 'event': 'pageview', 'path': '/' + marker},
    }
    for table in table_names():
        endpoint = '/rest/v1/' + quote(table, safe='')
        c.denied(f'{table} SELECT', c.request('GET', endpoint + '?select=*&limit=1'))
        if table not in rows:
            c.report(f'{table} mutations', False, 'add a valid harmless fixture for this new table')
            continue
        row = rows[table]
        pk = next(iter(row))
        target = endpoint + '?' + urlencode({pk: 'eq.' + str(row[pk])})
        c.denied(f'{table} INSERT', c.request('POST', endpoint, row))
        c.denied(f'{table} UPDATE', c.request('PATCH', target, row))
        c.denied(f'{table} DELETE / probe cleanup', c.request('DELETE', target))
    # Zero-unit arguments exercise EXECUTE permission without reserving quota.
    c.denied('reserve_youtube_quota RPC', c.request('POST', '/rest/v1/rpc/reserve_youtube_quota',
             {'p_units': 0, 'p_uploads': 0, 'p_reserve': 0, 'p_upload_reserve': 0}))
    c.denied('hub_analytics RPC', c.request('POST', '/rest/v1/rpc/hub_analytics',
             {'since': '2000-01-01T00:00:00Z', 'until_ts': '2000-01-01T00:00:00Z', 'channel_key': None}))
    media_object = os.getenv('RLS_MEDIA_OBJECT')  # Optional known bucket-relative path.
    for bucket in ('media', 'youtube-queue'):
        result = c.request('POST', '/storage/v1/object/list/' + bucket, {'prefix': '', 'limit': 100})
        if bucket == 'media':
            status, objects = result
            c.report('media LIST', status == 200 and isinstance(objects, list), f'HTTP {status}; public SELECT expected')
            # Auto-discover a root object; for nested folders supply RLS_MEDIA_OBJECT.
            if not media_object and isinstance(objects, list):
                media_object = next((o['name'] for o in objects if isinstance(o, dict)
                                     and o.get('id') and o.get('name')), None)
        else:
            c.denied('youtube-queue LIST', result, storage=True, filtered=True)
        name = marker + '.mp4'
        c.denied(f'{bucket} UPLOAD', c.request('POST', f'/storage/v1/object/{bucket}/{name}', b'RLS probe', raw=True), storage=True)
        c.denied(f'{bucket} DELETE / probe cleanup', c.request('DELETE', '/storage/v1/object/' + bucket,
                 {'prefixes': [name]}), storage=True, filtered=True)
    if media_object:
        status, _ = c.request('GET', '/storage/v1/object/public/media/' + quote(media_object, safe='/'), public=True)
        c.report('media public GET (no credentials)', status in (200, 206), f'HTTP {status}')
    else:
        c.report('media public GET', False, 'no existing root object found; set RLS_MEDIA_OBJECT to an existing bucket-relative path')
    print(f'{c.failed} failed or unverified check(s).')
    return 1 if c.failed else 0


if __name__ == '__main__':
    sys.exit(main())
