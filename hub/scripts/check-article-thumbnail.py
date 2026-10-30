"""Offline thumbnail persistence checks; import only the helper, never app config."""
import ast
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

source = Path(__file__).resolve().parents[2] / 'pipeline/article.py'
function = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'article_thumbnail')
with TemporaryDirectory() as temp:
    root = Path(temp)
    namespace = {'OUT_DIR': root, 'Path': Path, 'log': logging.getLogger('thumbnail-check')}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    persist = namespace['article_thumbnail']
    folder = root / 'example'
    folder.mkdir()
    (folder / 'example.jpg').write_bytes(b'fixture-jpeg')
    db = Mock()
    db.one.return_value = {'thumbnail_path': '/old/runner/example.jpg'}
    bucket = db.sb.storage.from_.return_value
    assert persist(db, 'example', None, False) == 'articles/example/thumbnail.jpg'
    bucket.upload.assert_called_once_with('articles/example/thumbnail.jpg', b'fixture-jpeg',
        file_options={'content-type': 'image/jpeg', 'upsert': 'true'})
    bucket.upload.reset_mock()
    assert persist(db, 'example', {'thumbnail_path': 'previous.jpg'}, True) == 'previous.jpg'
    bucket.upload.assert_not_called()
    (folder / 'example.jpg').unlink()
    assert persist(db, 'example', None, False) is None
    bucket.upload.assert_not_called()
    (folder / 'thumbnail.jpg').write_bytes(b'fixture-jpeg')
    assert persist(db, 'example', None, False) == 'articles/example/thumbnail.jpg'
    bucket.upload.side_effect = RuntimeError('synthetic failure')
    assert persist(db, 'example', {'thumbnail_path': 'previous.jpg'}, False) == 'previous.jpg'
print('PASS runner filename, thumbnail.jpg, dry run, missing media and failed-upload preservation')
