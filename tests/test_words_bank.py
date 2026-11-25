import json
from datetime import datetime, timezone

from pipeline import release_banked, stockpile
from pipeline.common import Channel
from pipeline.db import DB
from tests.test_stockpile import FakeDrive, mock_publish

CID = 'tentongues-2026-11-25-water'


def words_bundle(tmp_path, monkeypatch):
    db = DB()
    monkeypatch.setattr(stockpile, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(release_banked, 'OUT_DIR', tmp_path)
    out = tmp_path / CID
    out.mkdir()
    for i in range(3):
        key = CID if i == 0 else f'{CID}-short-{i:02d}'
        path = out / f'{key}.mp4'
        path.write_bytes(('video' + str(i)).encode())
        db.insert('content', {'id': key, 'channel': 'tentongues', 'kind': 'short' if i else 'long',
            'parent_id': CID if i else None, 'title': key, 'topic': 'water',
            'description': 'Full episode: {LONG_URL}' if i else 'water', 'file_path': str(path),
            'qa_status': 'passed', 'status': 'rendered', 'qa_notes': json.dumps({'issues': [], 'words_episode': {'word': 'water'}})})
    (out / 'episode.json').write_text('{"word": "water"}')
    return db, FakeDrive()


def test_words_bank_skips_explainer_article_and_keeps_episode(tmp_path, monkeypatch):
    db, drive = words_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr('pipeline.article.write_article', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no article call')))
    meta = stockpile.bank_bundle(db, CID, Channel('tentongues'), drive=drive)
    manifest = json.loads(drive.data[meta['manifest_id']])
    assert manifest['article'] is None and manifest['article_failed'] is False
    assert 'episode.json' in manifest['files'] and len(manifest['content']) == 3
    assert stockpile.notes(db.one('content', {'id': CID}))['words_episode'] == {'word': 'water'}
    assert not db.select('publications')


def test_fill_gap_releases_only_when_day_uncovered(tmp_path, monkeypatch):
    db, drive = words_bundle(tmp_path, monkeypatch)
    ch = Channel('tentongues')
    stockpile.bank_bundle(db, CID, ch, drive=drive)
    mock_publish(monkeypatch)
    written = []
    monkeypatch.setattr('pipeline.words_article.write_words_article', lambda db, cid: written.append(cid))
    early = datetime(2026, 11, 25, 5, tzinfo=timezone.utc)
    noon = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
    assert release_banked.fill_gap(db, ch, now=early, drive=drive) == 0  # live run may still be producing
    # The live daily run scheduled today's episode: nothing is released.
    db.insert('content', {'id': 'tentongues-2026-11-25-live', 'channel': 'tentongues', 'kind': 'long', 'topic': 'live', 'title': 'live'})
    db.insert('publications', {'content_id': 'tentongues-2026-11-25-live', 'platform': 'youtube', 'status': 'live',
                               'publish_at': '2026-11-25T07:00:00+00:00', 'platform_id': 'x'})
    assert release_banked.fill_gap(db, ch, now=noon, drive=drive) == 0
    # A live words run still in flight also blocks the fill.
    db.conn.execute("delete from publications"); db.conn.commit()
    db.insert('runs', {'workflow': 'words', 'channel': 'tentongues', 'status': 'running', 'started_at': '2026-11-25T11:00:00+00:00'})
    assert release_banked.fill_gap(db, ch, now=noon, drive=drive) == 0
    db.conn.execute("update runs set status='failed'"); db.conn.commit()
    db.set_setting('words_bank_fill_enabled', False)
    assert release_banked.fill_gap(db, ch, now=noon, drive=drive) == 0
    db.set_setting('words_bank_fill_enabled', True)
    assert release_banked.fill_gap(db, ch, now=noon, drive=drive) == 1
    assert written == [CID]
    assert len([p for p in db.select('publications') if p.get('platform') == 'youtube' and p.get('platform_id')]) == 3
    # Day now covered by the released episode (or queue empty): a second fill does nothing.
    assert release_banked.fill_gap(db, ch, now=noon, drive=drive) == 0


def test_fill_gap_ignores_explainer_channels(tmp_path, monkeypatch):
    assert release_banked.fill_gap(DB(), Channel('futurework')) == 0
