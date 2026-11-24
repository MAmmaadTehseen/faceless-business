"""A child Short uploaded after a queued parent still links to the long video (2026-11-24).

publish_short fills {LONG_URL} only when the long URL is known at call time. When the long
upload queues (quota or auth), the drain path reaches _youtube_publish with the placeholder
still in the DB description; before this fix the placeholder went up literally on YouTube
(explainer legacy stubs) or was stripped to an empty link (words Shorts), losing the funnel
link from every Short to its long video. Two halves:
  - short_description keeps {LONG_URL} when the URL is unknown, so the DB stays resolvable;
  - _youtube_publish resolves it from the parent's publication row (no API call), else drops
    the line so no dangling "Full video:" goes up.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from pipeline.common import Channel
from pipeline import publish
from test_schedule import MemoryDB

SLOT = datetime.now(timezone.utc) + timedelta(days=2)
WORDS_DESC = 'How to say egg in Russian.\n\nFull episode, all 10 languages: {LONG_URL}\n#shorts'


def setup(tmp_path, monkeypatch):
    db = MemoryDB()
    monkeypatch.setattr(publish.youtube, 'configured', lambda: True)
    monkeypatch.setattr(publish.youtube, 'use_channel', lambda channel: None)
    monkeypatch.setattr(publish, 'reserve', Mock(return_value=True))
    upload = Mock(return_value={'id': 'child-remote', 'url': 'https://youtu.be/child-remote'})
    monkeypatch.setattr(publish.youtube, 'upload', upload)
    return db, upload


def child_row(tmp_path, description, channel='futurework', sid='parent-short-1'):
    video = tmp_path / 'short.mp4'
    video.write_bytes(b'mock short')
    return {'id': sid, 'channel': channel, 'kind': 'short', 'parent_id': 'parent',
            'title': 'Child Short', 'qa_status': 'passed', 'file_path': str(video),
            'description': description}


def queue_child(db, row):
    db.tables['content'].append(row)
    db.insert('publications', {'content_id': row['id'], 'platform': 'youtube', 'status': 'queued',
                              'publish_at': SLOT.isoformat()})


def test_drained_child_resolves_placeholder_from_parent_publication(tmp_path, monkeypatch):
    db, upload = setup(tmp_path, monkeypatch)
    # The parent was drained earlier: its publication row already knows the remote id.
    db.insert('publications', {'content_id': 'parent', 'platform': 'youtube', 'status': 'live',
                              'platform_id': 'PARENTID'})
    queue_child(db, child_row(tmp_path, 'Hook line.\n\nFull video: {LONG_URL}\n#shorts'))
    assert publish.drain_youtube_queue(db, Channel('futurework')) == 1
    description = upload.call_args.args[2]
    assert '{LONG_URL}' not in description
    assert 'https://youtu.be/PARENTID' in description


def test_drained_words_child_resolves_placeholder_too(tmp_path, monkeypatch):
    db, upload = setup(tmp_path, monkeypatch)
    db.insert('publications', {'content_id': 'parent', 'platform': 'youtube', 'status': 'live',
                              'platform_id': 'PARENTID'})
    queue_child(db, child_row(tmp_path, WORDS_DESC, channel='tentongues',
                              sid='tentongues-2026-11-24-egg-short-07'))
    assert publish.drain_youtube_queue(db, Channel('tentongues')) == 1
    description = upload.call_args.args[2]
    assert 'https://youtu.be/PARENTID' in description and '{LONG_URL}' not in description


def test_placeholder_without_parent_url_drops_the_line(tmp_path, monkeypatch):
    db, upload = setup(tmp_path, monkeypatch)
    # Parent still queued: no platform_id, so no link is invented.
    db.insert('publications', {'content_id': 'parent', 'platform': 'youtube', 'status': 'queued',
                              'publish_at': SLOT.isoformat()})
    queue_child(db, child_row(tmp_path, 'Hook line.\n\nFull video: {LONG_URL}\n#shorts'))
    assert publish.drain_youtube_queue(db, Channel('futurework')) == 1
    description = upload.call_args.args[2]
    assert '{LONG_URL}' not in description and 'Full video' not in description


def test_description_without_placeholder_untouched(tmp_path, monkeypatch):
    db, upload = setup(tmp_path, monkeypatch)
    db.insert('publications', {'content_id': 'parent', 'platform': 'youtube', 'status': 'live',
                              'platform_id': 'PARENTID'})
    queue_child(db, child_row(tmp_path, 'A real description already filled by publish_short.'))
    assert publish.drain_youtube_queue(db, Channel('futurework')) == 1
    assert upload.call_args.args[2] == 'A real description already filled by publish_short.'


def test_parent_long_url_reads_publication_row():
    db = MemoryDB()
    assert publish.parent_long_url(db, {'parent_id': None}) is None
    assert publish.parent_long_url(db, {'parent_id': 'missing'}) is None
    db.insert('publications', {'content_id': 'p2', 'platform': 'youtube', 'platform_id': 'XYZ'})
    assert publish.parent_long_url(db, {'parent_id': 'p2'}) == 'https://youtu.be/XYZ'
    db.update('publications', {'content_id': 'p2'}, {'url': 'https://www.youtube.com/watch?v=XYZ'})
    assert publish.parent_long_url(db, {'parent_id': 'p2'}) == 'https://www.youtube.com/watch?v=XYZ'


def test_short_description_keeps_placeholder_when_url_unknown():
    ch = Channel('tentongues')
    row = {'description': WORDS_DESC, 'parent_id': 'p'}
    assert publish.short_description(row, ch, None) == WORDS_DESC
    filled = publish.short_description(row, ch, 'https://youtu.be/x')
    assert 'https://youtu.be/x' in filled and '{LONG_URL}' not in filled


def test_publish_short_keeps_placeholder_in_db_for_later_drain(tmp_path, monkeypatch):
    db = MemoryDB()
    monkeypatch.setattr(publish.youtube, 'configured', lambda: False)
    monkeypatch.setattr(publish.meta, 'configured', lambda: False)
    row = child_row(tmp_path, WORDS_DESC, channel='tentongues', sid='tentongues-2026-11-24-egg-short-07')
    db.tables['content'].append(row)
    publish.publish_short(db, row, Channel('tentongues'), 'public', None)
    stored = db.one('content', {'id': row['id']})['description']
    assert '{LONG_URL}' in stored, 'DB row must stay resolvable when the parent URL is unknown'
    publish.publish_short(db, row, Channel('tentongues'), 'public', 'https://youtu.be/PARENTID')
    stored = db.one('content', {'id': row['id']})['description']
    assert 'https://youtu.be/PARENTID' in stored and '{LONG_URL}' not in stored


def test_words_reel_caption_never_leaks_placeholder():
    ch = Channel('tentongues')
    caption = publish.reel_caption({'title': 'Egg in Russian: yaytso'}, ch, WORDS_DESC)
    assert '{LONG_URL}' not in caption and 'youtu.be' not in caption
    assert caption.startswith('Egg in Russian: yaytso')
    assert 'Full episode' not in caption, 'unresolvable link line is dropped, not left dangling'
