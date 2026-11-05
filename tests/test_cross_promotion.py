import json
from unittest.mock import Mock

import pytest

from pipeline.common import Channel
from pipeline.db import DB
from pipeline.publish.cross_promotion import instagram_caption, overlap_score


@pytest.fixture
def setup(monkeypatch):
    original = Channel.__init__
    def configured(self, key='futurework'):
        original(self, key)
        # Explicit synthetic handles only, never inferred from YouTube handles.
        self.cfg['instagram_handle'] = 'test_' + key
    monkeypatch.setattr(Channel, '__init__', configured)
    db = DB()
    db.set_setting('cross_mentions_enabled', True)
    yield db, Channel('tradewinds')
    db.conn.close()


def add(db, i, channel='tradewinds', error=None, platform='instagram', status='live'):
    cid = f'{channel}-{i}'
    db.insert('content', dict(id=cid, channel=channel, kind='short', topic='AI automation jobs', title='AI automation jobs', qa_status='passed'))
    db.insert('publications', dict(content_id=cid, platform=platform, platform_id=f'media-{cid}',
              status=status, error=error, published_at=f'2026-11-{i:02d}T00:00:00+00:00'))
    return db.one('content', {'id': cid})


def ready(db):
    for i in range(1, 4):
        add(db, i)


def caption(db, channel, title='AI automation jobs', base='Original caption'):
    return instagram_caption(db, {'title': title}, channel, base)


def test_overlap_boundaries_and_phrases():
    cfg = Channel('futurework').cfg
    assert overlap_score('AI automation changes jobs', cfg) == 3
    assert overlap_score('Paid claims about a railway', cfg) == 0
    assert overlap_score('MACHINE LEARNING', cfg) == 1
    assert overlap_score('NASA launches a lunar satellite', Channel('escapevelocity').cfg) == 3
    assert overlap_score('Tariffs disrupt the supply chain', Channel('tradewinds').cfg) == 2


@pytest.mark.parametrize('value', [None, False, 'false', 'true', 1])
def test_disabled_default(setup, value):
    db, ch = setup
    if value is None:
        db.conn.execute('delete from settings'); db.conn.commit()
    else:
        db.set_setting('cross_mentions_enabled', value)
    assert caption(db, ch) == ('Original caption', None)


def test_missing_handle_and_no_overlap(setup, monkeypatch):
    db, ch = setup
    ready(db)
    assert caption(db, ch, title='A recipe for soup')[1] is None
    # Use unmodified disk config, where all unknown IG handles are blank.
    monkeypatch.setattr(Channel, 'keys', staticmethod(lambda: []))
    assert caption(db, ch)[1] is None


def test_blank_handle_skipped(setup, monkeypatch):
    db, ch = setup
    ready(db)
    original = Channel.__init__
    def blank(self, key='futurework'):
        original(self, key)
        self.cfg['instagram_handle'] = ''
    monkeypatch.setattr(Channel, '__init__', blank)
    assert caption(db, ch)[1] is None


def test_rolling_four_and_account_isolation(setup):
    db, ch = setup
    for i in range(1, 4):
        assert caption(db, ch)[1] is None
        add(db, i)
    text, info = caption(db, ch)
    assert text.count('@') == 1 and '@test_futurework' in text
    assert json.loads(info)['cross_mention']['channel'] == 'futurework'
    add(db, 4, error=info)
    # Sister-account posts, failed posts and YouTube posts cannot advance it.
    for i in range(5, 8):
        add(db, i, channel='futurework')
        add(db, i + 10, status='failed')
        add(db, i + 20, platform='youtube')
    for i in range(5, 8):
        assert caption(db, ch)[1] is None
        add(db, i)
    assert caption(db, ch)[1] is not None


def test_one_mention_tie_and_caption_limit(setup):
    db, ch = setup
    ready(db)
    text, info = caption(db, ch, title='AI satellite', base='x' * 2300)
    assert len(text) <= 2200 and text.count('@') == 1
    assert info is not None
    assert caption(db, ch, title='tariffs sanctions')[1] is None  # no self mention


def test_history_failure_falls_back(setup, monkeypatch):
    db, ch = setup
    monkeypatch.setattr(db, 'select', Mock(side_effect=RuntimeError('offline')))
    assert caption(db, ch) == ('Original caption', None)


def test_publish_and_replay_preserve_metadata_and_facebook(setup, monkeypatch):
    import pipeline.publish as publish
    db, ch = setup
    ready(db)
    row = add(db, 8, status='failed')
    monkeypatch.setattr(publish.youtube, 'configured', lambda: False)
    monkeypatch.setattr(publish.meta, 'configured', lambda: True)
    monkeypatch.setattr(publish.meta, 'ig_configured', lambda: True)
    monkeypatch.setattr(publish.meta, 'fb_configured', lambda: True)
    monkeypatch.setattr(publish, '_media_url', lambda *a: 'https://example.invalid/reel.mp4')
    monkeypatch.setattr(publish, '_local_file', lambda *a: 'reel.mp4')
    ig = Mock(return_value={'id': 'ig-new'})
    fb = Mock(return_value={'id': 'fb-new'})
    monkeypatch.setattr(publish.meta, 'publish_instagram_reel', ig)
    monkeypatch.setattr(publish.meta, 'publish_facebook_reel', fb)
    # Simulate a failed attempt, with no platform id yet.
    db.update('publications', {'content_id': row['id']}, {'platform_id': None})
    publish.publish_short(db, row, ch, 'public')
    assert '@test_futurework' in ig.call_args.args[1]
    assert '@' not in fb.call_args.args[1]
    before = db.one('publications', {'content_id': row['id'], 'platform': 'instagram'})
    assert json.loads(before['error'])['cross_mention']
    publish.publish_short(db, row, ch, 'public')
    assert ig.call_count == fb.call_count == 1
    after = db.one('publications', {'id': before['id']})
    assert after['error'] == before['error'] and after['published_at'] == before['published_at']


def test_collab_fallback_is_plain_single_reel(setup, monkeypatch):
    # Unsupported/unclear capability: even a stray true setting must not send
    # collaborators, upload a second Reel or attempt an invite acceptance.
    from pipeline.publish import meta
    db, ch = setup
    db.set_setting('collab_posts_enabled', True)
    monkeypatch.setattr(meta, '_current', ch)
    monkeypatch.setattr(ch, 'env', lambda *a: 'test-account')
    monkeypatch.setattr(meta, '_ig_tok', lambda: 'test-token')
    monkeypatch.setattr(meta, '_wait_container', lambda *a: None)
    responses = [Mock(ok=True, json=lambda: {'id': 'container'}), Mock(ok=True, json=lambda: {'id': 'reel'})]
    post = Mock(side_effect=responses)
    monkeypatch.setattr(meta.requests, 'post', post)
    monkeypatch.setattr(meta.requests, 'get', Mock(return_value=Mock(ok=True, json=lambda: {'permalink': 'https://example.invalid/reel'})))
    assert meta.publish_instagram_reel('https://example.invalid/video.mp4', 'caption')['id'] == 'reel'
    assert post.call_count == 2
    assert 'collaborators' not in post.call_args_list[0].kwargs['data']


def test_instagram_retry_records_mention(setup, monkeypatch):
    import pipeline.retry as retry
    db, ch = setup
    ready(db)
    row = add(db, 8, status='failed')
    db.set_setting('publish_privacy', 'public')
    db.update('publications', {'content_id': row['id']}, {'platform_id': None})
    pub = db.one('publications', {'content_id': row['id']})
    monkeypatch.setattr(retry, 'restore', lambda *a: row)
    monkeypatch.setattr(retry, '_media_url', lambda *a: 'https://example.invalid/video.mp4')
    send = Mock(return_value={'id': 'retry-reel'})
    monkeypatch.setattr(retry.meta, 'publish_instagram_reel', send)
    assert retry.retry_one(db, pub)
    assert '@test_futurework' in send.call_args.args[1]
    saved = db.one('publications', {'id': pub['id']})
    assert saved['status'] == 'live'
    assert json.loads(saved['error'])['cross_mention']['channel'] == 'futurework'


def test_existing_mention_and_truncated_history_skip(setup, monkeypatch):
    db, ch = setup
    ready(db)
    assert caption(db, ch, base='See @someone for context')[1] is None
    monkeypatch.setattr(db, 'setting', lambda *a: True)
    monkeypatch.setattr(db, 'select', lambda *a, **kw: [{'id': str(i)} for i in range(1000)])
    assert caption(db, ch)[1] is None
