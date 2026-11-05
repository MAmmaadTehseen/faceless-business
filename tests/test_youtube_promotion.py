from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from pipeline.common import Channel
from pipeline.publish import youtube_promotion as promo


@pytest.fixture
def setup(monkeypatch):
    db = MagicMock()
    settings = {}
    db.setting.side_effect = lambda key, default=None: settings.get(key, default)
    db.set_setting.side_effect = lambda key, value: settings.__setitem__(key, value)
    db.one.return_value = None
    api = MagicMock()
    monkeypatch.setattr(promo.youtube, 'yt', lambda: api)
    reserve = MagicMock(return_value=True)
    monkeypatch.setattr(promo, 'reserve', reserve)
    return db, settings, api, reserve


def test_disabled_defaults(setup):
    db, settings, api, reserve = setup
    row = {'id': 'new', 'kind': 'long', 'title': 'AI jobs'}
    assert promo.description_links(db, row, Channel(), 'Original') == 'Original'
    promo.new_upload(db, row, Channel(), 'v')
    promo.article_saved(db, 'new')
    api.playlists.assert_not_called()
    reserve.assert_not_called()
    assert not settings


def test_links_overlap_idempotency_and_limits(setup):
    db, settings, api, reserve = setup
    settings['yt_description_links_enabled'] = True
    db.one.return_value = {'slug': 'article', 'published_at': 'today'}
    row = {'id': 'short', 'parent_id': 'parent', 'title': 'NASA trade sanctions'}
    result = promo.description_links(db, row, Channel(), 'Sources')
    assert '/a/article' in result
    assert '@tradewindsreport' in result
    assert '@escapevelocitydaily' not in result
    assert promo.description_links(db, row, Channel(), result) == result
    db.one.assert_called_with('articles', {'id': 'parent'})
    full = 'é' * 2450
    assert promo.description_links(db, row, Channel(), full) == full
    assert len(promo.clip('é' * 5000).encode()) == 4900
    assert promo.best_match('paid', [{'cross_mention_keywords': ['AI']}]) is None
    assert promo.best_match('AI trade', [{'cross_mention_keywords': ['AI']}])


def test_playlists_match_once_and_shorts_excluded(setup):
    db, settings, api, reserve = setup
    settings['yt_playlists_enabled'] = True
    api.playlists.return_value.insert.return_value.execute.return_value = {'id': 'playlist'}
    row = {'id': 'new', 'kind': 'long', 'title': 'AI jobs'}
    promo.new_upload(db, row, Channel(), 'video')
    promo.new_upload(db, row, Channel(), 'video')
    api.playlists.return_value.insert.assert_called_once()
    assert api.playlists.return_value.insert.call_args.kwargs['body']['snippet']['title'] == 'AI and the Workplace'
    api.playlistItems.return_value.insert.assert_called_once()
    assert [c.args[1] for c in reserve.call_args_list] == [50, 50]
    promo.new_upload(db, {**row, 'kind': 'short'}, Channel(), 'short')
    promo.new_upload(db, {**row, 'title': 'unrelated'}, Channel(), 'other')
    api.playlistItems.return_value.insert.assert_called_once()


def test_article_update_preserves_status_and_idempotency(setup, monkeypatch):
    db, settings, api, reserve = setup
    settings.update(yt_description_links_enabled=True, yt_links_new_video=True)
    parent = {'id': 'new', 'channel': 'futurework', 'title': 'AI jobs'}
    db.select.return_value = []
    def one(table, match):
        return {'content': parent, 'publications': {'platform_id': 'video'},
                'articles': {'slug': 'story', 'published_at': 'today'}}[table]
    db.one.side_effect = one
    remote = {'snippet': {'title': 'AI jobs', 'categoryId': '28', 'description': 'Sources', 'tags': ['AI']},
              'status': {'privacyStatus': 'private', 'publishAt': '2027-01-01T06:00:00Z', 'containsSyntheticMedia': True}}
    old_status = deepcopy(remote['status'])
    api.videos.return_value.list.return_value.execute.side_effect = lambda: {'items': [deepcopy(remote)]}
    def update(**kwargs):
        assert kwargs['part'] == 'snippet'
        assert 'status' not in kwargs['body']
        remote['snippet'] = kwargs['body']['snippet']
        return MagicMock()
    api.videos.return_value.update.side_effect = update
    promo.article_saved(db, 'new')
    promo.article_saved(db, 'new')
    api.videos.return_value.update.assert_called_once()
    assert remote['status'] == old_status
    assert '/a/story' in remote['snippet']['description']
    settings.pop('yt_links_new_video')
    api.reset_mock()
    promo.article_saved(db, 'new')
    api.videos.assert_not_called()


@pytest.mark.parametrize('failure', ['quota', 'api', 'db'])
def test_failures_isolated(setup, failure):
    db, settings, api, reserve = setup
    settings.update(yt_playlists_enabled=True, yt_description_links_enabled=True)
    if failure == 'quota':
        reserve.return_value = False
    elif failure == 'api':
        api.playlists.return_value.insert.side_effect = RuntimeError('offline')
    else:
        db.setting.side_effect = RuntimeError('offline')
    promo.new_upload(db, {'id': 'new', 'kind': 'long', 'title': 'AI jobs'}, Channel(), 'v')
    promo.article_saved(db, 'new')
    if failure == 'quota':
        api.playlists.assert_not_called()


def test_article_refresh_includes_only_eligible_children(setup):
    db, settings, api, reserve = setup
    settings.update(yt_description_links_enabled=True, yt_links_new_child=True)
    parent = {'id': 'parent', 'channel': 'futurework', 'title': 'Unrelated'}
    db.select.return_value = [{'id': 'child', 'parent_id': 'parent', 'title': 'Unrelated', 'kind': 'short'}]
    def one(table, match):
        if table == 'content':
            return parent
        if table == 'publications':
            return {'platform_id': match['content_id']}
        return {'slug': 'parent-story', 'published_at': 'today'}
    db.one.side_effect = one
    api.videos.return_value.list.return_value.execute.return_value = {
        'items': [{'snippet': {'title': 'Short', 'categoryId': '28', 'description': ''}}]}
    promo.article_saved(db, 'parent')
    api.videos.return_value.list.assert_called_once_with(part='snippet', id='child')
    assert '/a/parent-story' in api.videos.return_value.update.call_args.kwargs['body']['snippet']['description']
    api.videos.return_value.update.side_effect = RuntimeError('offline')
    promo.article_saved(db, 'parent')  # Optional update failure cannot escape.
