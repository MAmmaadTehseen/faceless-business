"""Stockpile storage on the owner's home server (reached over Tailscale), with the same
interface stockpile/release_banked use for Google Drive: space, folder, upload, download,
release, delete_folder. Ids are paths under HOMELAB_STOCKPILE_ROOT.

Env: HOMELAB_SSH_HOST (default 100.117.61.18), HOMELAB_SSH_USER (ammaad), HOMELAB_SSH_KEY_FILE,
HOMELAB_STOCKPILE_ROOT (/mnt/data/stockpile). HOMELAB_LOCAL=1 uses the filesystem directly
(when running on the server itself). STOCKPILE_BACKEND=homelab selects this store for banking.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from .drive import DriveFull, digest

FLOOR = 20 * 1024**3  # keep the data disk from filling


def backend_for(metadata=None):
    """Store for an existing checkpoint (its recorded backend) or for new banking (env)."""
    name = (metadata or {}).get('backend') if metadata is not None else os.getenv('STOCKPILE_BACKEND', 'drive')
    if name == 'homelab':
        return HomelabStore()
    from .drive import Drive
    return Drive()


class HomelabStore:
    backend = 'homelab'

    def __init__(self, host=None, user=None, key=None, root=None, local=None):
        self.host = host or os.getenv('HOMELAB_SSH_HOST', '100.117.61.18')
        self.user = user or os.getenv('HOMELAB_SSH_USER', 'ammaad')
        self.key = key or os.getenv('HOMELAB_SSH_KEY_FILE')
        self.root = root or os.getenv('HOMELAB_STOCKPILE_ROOT', '/mnt/data/stockpile')
        self.local = os.getenv('HOMELAB_LOCAL') == '1' if local is None else local

    # ---- transport ----
    def _ssh_args(self):
        args = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=20',
                '-o', 'ServerAliveInterval=30']
        if self.key:
            args += ['-o', 'IdentitiesOnly=yes', '-i', self.key]
        return args

    def _run(self, command):
        if self.local:
            return subprocess.run(['bash', '-c', command], check=True, capture_output=True, text=True).stdout
        for attempt in range(4):
            done = subprocess.run(['ssh', *self._ssh_args(), f'{self.user}@{self.host}', command],
                                  capture_output=True, text=True, timeout=600)
            if done.returncode == 0:
                return done.stdout
            # 255 is ssh's own connection failure (tailnet path still settling); command errors fail at once.
            if done.returncode != 255 or attempt == 3:
                raise RuntimeError(f'homelab ssh failed ({done.returncode}): {done.stderr.strip()[-300:]}')
            time.sleep(15 * (attempt + 1))

    def _copy(self, src, dst, to_remote):
        if self.local:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            return
        # OpenSSH 9+ scp uses SFTP: the remote path is taken literally, so it must not be shell-quoted.
        remote = f'{self.user}@{self.host}:{dst if to_remote else src}'
        pair = [str(src), remote] if to_remote else [remote, str(dst)]
        for attempt in range(3):
            try:
                subprocess.run(['scp', '-q', *self._ssh_args(), *pair], check=True, timeout=4 * 3600)
                return
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                if attempt == 2:
                    raise

    def _inside(self, path):
        p = os.path.normpath(str(path))
        if not (p == self.root or p.startswith(self.root.rstrip('/') + '/')):
            raise RuntimeError('Unsafe stockpile path')
        return p

    # ---- Drive-compatible interface ----
    def space(self, required=0):
        avail = int(self._run(f'mkdir -p {shlex.quote(self.root)} && df -B1 --output=avail {shlex.quote(self.root)} | tail -1').strip())
        total = int(self._run(f'df -B1 --output=size {shlex.quote(self.root)} | tail -1').strip())
        if avail - required < FLOOR:
            raise DriveFull('Homelab stockpile reserve reached; banking stopped (keep 20 GiB free)')
        return {'used': total - avail, 'limit': total}

    def folder(self, name, parent=None):
        if '/' in name or name in ('', '.', '..'):
            raise ValueError('Invalid folder name')
        path = self._inside(f'{parent or self.root}/{name}')
        self._run(f'mkdir -p {shlex.quote(path)}')
        return path

    def upload(self, path, parent):
        path = Path(path)
        # Content-addressed name: two files with the same basename never overwrite each other.
        target = self._inside(f'{parent}/{digest(path)[:12]}-{path.name}')
        tmp = target + '.part'
        self._copy(path, tmp, True)
        self._run(f'mv -f {shlex.quote(tmp)} {shlex.quote(target)}')
        return target

    def download(self, key, target, checksum):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.download')
        try:
            self._copy(self._inside(key), temporary, False)
            if digest(temporary) != checksum:
                raise RuntimeError('Homelab download checksum mismatch')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def release(self, folder_id, root):
        folder_id = self._inside(folder_id)
        dest = self._inside(f'{root}/released')
        self._run(f'mkdir -p {shlex.quote(dest)} && mv -n {shlex.quote(folder_id)} {shlex.quote(dest)}/ 2>/dev/null || true')

    def delete_folder(self, folder_id):
        folder_id = self._inside(folder_id)
        if folder_id == os.path.normpath(self.root):
            raise RuntimeError('Refusing to delete the stockpile root')
        self._run(f'rm -rf -- {shlex.quote(folder_id)}')
