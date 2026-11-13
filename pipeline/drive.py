"""Private app-created Drive files only; never log credentials or request bodies."""
from __future__ import annotations
import hashlib
import http.client
import logging
import os
import socket
import ssl
import time
from pathlib import Path

SCOPE = 'https://www.googleapis.com/auth/drive.file'
FLOOR = 5 * 1024**3
SOCKET_TIMEOUT = 300  # seconds per socket operation; the library default of 60 s drops large chunks
MAX_ATTEMPTS = 10  # explicit next_chunk retries per file, on top of the library's own num_retries
MAX_RETRY_SECONDS = 15 * 60
log = logging.getLogger('pipeline')


def transient(exc):
    """Errors worth resuming the same resumable request for; never credential or 4xx errors."""
    from googleapiclient.errors import HttpError
    if isinstance(exc, HttpError):
        status = getattr(getattr(exc, 'resp', None), 'status', 0) or 0
        return status >= 500 or status in (408, 429)
    try:
        import httplib2
        if isinstance(exc, httplib2.HttpLib2Error):
            return True
    except ImportError:
        pass
    return isinstance(exc, (TimeoutError, socket.timeout, ConnectionError, ssl.SSLError, http.client.HTTPException))


def plain_http():
    """httplib2 client with a long timeout; 308 is 'Resume Incomplete' for uploads, not a redirect."""
    import httplib2
    http = httplib2.Http(timeout=SOCKET_TIMEOUT)
    http.redirect_codes = http.redirect_codes - {308}
    return http


def next_chunk_retrying(request, label, sleep=time.sleep):
    """Drive a MediaIoBaseUpload/Download to completion, resuming after transient failures.

    The same request object is reused so a resumable upload continues from the last
    acknowledged byte instead of restarting the file.
    """
    attempt = 0
    started = time.monotonic()
    while True:
        try:
            progress, response = request.next_chunk(num_retries=8)
        except Exception as exc:
            attempt += 1
            waited = time.monotonic() - started
            if not transient(exc) or attempt >= MAX_ATTEMPTS or waited >= MAX_RETRY_SECONDS:
                raise
            delay = min(2 ** attempt, 120)
            log.warning('Drive %s interrupted (%s); retry %d/%d in %ds', label, type(exc).__name__,
                        attempt, MAX_ATTEMPTS, delay)
            sleep(delay)
            continue
        # Uploads return the file resource when complete; downloads return done=True.
        if response:
            return response


class DriveFull(RuntimeError):
    pass


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


class Drive:
    def __init__(self, service=None):
        if service is None:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            import httplib2
            from google_auth_httplib2 import AuthorizedHttp
            values = [os.getenv(k) for k in ('GDRIVE_REFRESH_TOKEN', 'YT_CLIENT_ID', 'YT_CLIENT_SECRET')]
            if not all(values):
                raise RuntimeError('Drive OAuth configuration missing')
            credentials = Credentials(None, refresh_token=values[0], client_id=values[1], client_secret=values[2],
                                      token_uri='https://oauth2.googleapis.com/token', scopes=[SCOPE])
            # Long socket timeout: 8 MiB chunks from a busy runner regularly exceed the 60 s default.
            http = AuthorizedHttp(credentials, http=plain_http())
            service = build('drive', 'v3', http=http, cache_discovery=False)
        self.service = service

    def space(self, required=0):
        quota = self.service.about().get(fields='storageQuota').execute()['storageQuota']
        # An absent limit cannot prove that the 5 GB reserve is safe.
        limit, used = int(quota.get('limit', 0)), int(quota.get('usage', 0))
        if limit <= 0 or limit - used - required < FLOOR:
            raise DriveFull('Drive reserve reached; banking stopped (keep 5 GiB free)')
        return {'used': used, 'limit': limit}

    def folder(self, name, parent=None):
        escaped = name.replace('\\', '\\\\').replace("'", "\\'")
        query = f"trashed = false and mimeType = 'application/vnd.google-apps.folder' and name = '{escaped}'"
        if parent:
            query += f" and '{parent}' in parents"
        rows = self.service.files().list(q=query, fields='files(id)', pageSize=100).execute().get('files', [])
        if len(rows) > 1:
            raise RuntimeError('Ambiguous stockpile folder; owner review required')
        if rows:
            return rows[0]['id']
        body = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent:
            body['parents'] = [parent]
        return self.service.files().create(body=body, fields='id').execute()['id']

    def upload(self, path, parent):
        from googleapiclient.http import MediaFileUpload
        path = Path(path)
        # Reuse an already verified file after an interrupted bundle upload.
        escaped = path.name.replace('\\', '\\\\').replace("'", "\\'")
        rows = self.service.files().list(q=f"'{parent}' in parents and trashed = false and name = '{escaped}'",
                                        fields='files(id,size,md5Checksum)', pageSize=100).execute().get('files', [])
        md5 = digest(path, 'md5')
        for row in rows:
            if int(row.get('size', -1)) == path.stat().st_size and row.get('md5Checksum') == md5:
                return row['id']
        self.space(path.stat().st_size)
        request = self.service.files().create(body={'name': path.name, 'parents': [parent]},
            media_body=MediaFileUpload(str(path), resumable=True, chunksize=8 * 1024**2), fields='id')
        response = next_chunk_retrying(request, 'upload ' + path.name)
        remote = self.service.files().get(fileId=response['id'], fields='size,md5Checksum').execute()
        if int(remote.get('size', -1)) != path.stat().st_size or remote.get('md5Checksum') != md5:
            raise RuntimeError('Drive uploaded bytes failed verification; local media retained')
        return response['id']

    def download(self, file_id, target, checksum):
        from googleapiclient.http import MediaIoBaseDownload
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.part')
        try:
            with temporary.open('wb') as output:
                request = MediaIoBaseDownload(output, self.service.files().get_media(fileId=file_id), chunksize=8 * 1024**2)
                next_chunk_retrying(request, 'download ' + target.name)
            if digest(temporary) != checksum:
                raise RuntimeError('Drive download checksum mismatch')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def release(self, folder_id, root):
        destination = self.folder('released', root)
        current = self.service.files().get(fileId=folder_id, fields='parents').execute().get('parents', [])
        if destination in current:
            return
        self.service.files().update(fileId=folder_id, addParents=destination,
                                   removeParents=','.join(current), fields='id').execute()
