"""Source boundary: future remote sources can materialize files locally here."""
from pathlib import Path
from typing import Protocol


class Source(Protocol):
    def files(self) -> list[Path]: ...
    def open(self, path: Path): ...
    def size(self, path: Path) -> int: ...
    def materialize(self, path: Path) -> Path: ...
    def rights(self, path: Path) -> dict: ...


class LocalFolder:
    def __init__(self, folder):
        self.folder = Path(folder).expanduser().resolve(strict=True)
        if not self.folder.is_dir():
            raise ValueError('Select a folder')

    def files(self):
        return sorted(p for p in self.folder.iterdir() if p.is_file() and not p.is_symlink()
                      and p.suffix.lower() in {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v'})

    def open(self, path):
        return path.open('rb')

    def size(self, path):
        return path.stat().st_size

    def materialize(self, path):
        return path

    def rights(self, path):
        import json
        sidecar = path.with_suffix('.rights.json')
        if sidecar.exists():
            return json.loads(sidecar.read_text())
        sheet = self.folder / 'rights.json'
        # Explicit filename keys only: never inherit a folder-wide basis.
        return json.loads(sheet.read_text()).get(path.name, {}) if sheet.exists() else {}
