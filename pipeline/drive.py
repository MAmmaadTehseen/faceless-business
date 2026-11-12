"""Private app-created Drive files only; never log credentials or request bodies."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path

SCOPE = 'https://www.googleapis.com/auth/drive.file'
FLOOR = 5 * 1024**3


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
            values = [os.getenv(k) for k in ('GDRIVE_REFRESH_TOKEN', 'YT_CLIENT_ID', 'YT_CLIENT_SECRET')]
            if not all(values):
                raise RuntimeError('Drive OAuth configuration missing')
            service = build('drive', 'v3', credentials=Credentials(None, refresh_token=values[0],
                client_id=values[1], client_secret=values[2], token_uri='https://oauth2.googleapis.com/token',
                scopes=[SCOPE]), cache_discovery=False)
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
        response = None
        while response is None:
            _, response = request.next_chunk(num_retries=3)
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
                done = False
                while not done:
                    _, done = request.next_chunk(num_retries=3)
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
