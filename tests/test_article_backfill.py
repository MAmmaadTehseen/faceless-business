import json
from unittest.mock import Mock

from scripts import backfill_articles as b
from pipeline import script
from pipeline.db import DB


def seed(db, cid):
    db.insert('content', {'id': cid, 'kind': 'long', 'topic': 'Test', 'title': 'Saved title', 'script': 'Saved narration', 'status': 'published'})
    db.insert('publications', {'content_id': cid, 'platform': 'youtube', 'platform_id': cid, 'status': 'live'})


def sources():
    source = b.ScriptSources()
    source.archived = {}
    return source


def test_dry_run_never_writes_or_calls_article(monkeypatch, capsys):
    db = DB()
    seed(db, 'one')
    monkeypatch.setattr(b, 'write_article', Mock(side_effect=AssertionError('no spend')))
    monkeypatch.setattr(db, 'update', Mock(side_effect=AssertionError('no writes')))
    assert b.backfill(db, sources=sources()) == []
    assert 'one | DB:content.script | $0.60' in capsys.readouterr().out
    assert db.select('articles') == []


def test_apply_continues_and_is_idempotent(monkeypatch):
    db = DB()
    for cid in ('bad', 'good'):
        seed(db, cid)
    def write(db, cid, **kwargs):
        assert kwargs['script_data']['script'] == ['Saved narration']
        if cid == 'bad':
            raise ValueError('validation')
        db.insert('articles', {'id': cid, 'content_id': cid, 'slug': cid, 'title': cid, 'body_md': 'text'})
    writer = Mock(side_effect=write)
    monkeypatch.setattr(b, 'write_article', writer)
    assert b.backfill(db, apply=True, sources=sources()) == ['bad']
    assert b.backfill(db, apply=True, sources=sources()) == ['bad']
    assert [c.args[1] for c in writer.call_args_list] == ['bad', 'good', 'bad']


def test_script_source_precedence_and_missing(tmp_path):
    src = b.ScriptSources(tmp_path)
    src.archived = {'one': ({'title': 'Archive', 'script': ['Archive']}, 'artifact:test')}
    row = {'id': 'one', 'title': 'DB', 'script': 'DB'}
    assert src.find(row)[1] == 'artifact:test'
    folder = tmp_path / 'one'
    folder.mkdir()
    (folder / 'script.json').write_text(json.dumps({'title': 'Local', 'script': ['Local']}))
    assert src.find(row)[0]['title'] == 'Local'
    assert src.find({'id': 'empty'}) == (None, None)


def test_paid_script_survives_validation_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(script, 'OUT_DIR', tmp_path)
    db = DB()
    db.insert('content', {'id': 'one', 'kind': 'long', 'topic': 'Test', 'title': 'Test'})
    response = json.loads(open('data/fixture_script.json').read())
    response['title'] = 'Get rich while you sleep'
    response['title_variants'] = []
    claude = Mock(db=db)
    claude.run.side_effect = [(response, .6), ({'changed': False}, .01)]
    import pytest
    for _ in range(2):
        with pytest.raises(RuntimeError, match='policy'):
            script.write_script(claude, {'topic': 'Test'}, 'one')
    assert claude.run.call_count == 2  # initial script + hook only
    (tmp_path / 'one' / 'paid_script.json').unlink()
    with pytest.raises(RuntimeError, match='policy'):
        script.write_script(claude, {'topic': 'Test'}, 'one')  # DB checkpoint
    assert claude.run.call_count == 2


def test_paid_script_missing_refuses_repurchase(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(script, 'OUT_DIR', tmp_path)
    db = DB()
    db.insert('costs', {'content_id': 'lost', 'step': 'script', 'usd': .6})
    claude = Mock(db=db)
    with pytest.raises(RuntimeError, match='restore its artifact'):
        script.write_script(claude, {'topic': 'Test'}, 'lost')
    claude.run.assert_not_called()


def test_archive_listing_failure_falls_back_without_exposing_error(monkeypatch, tmp_path):
    source = b.ScriptSources(tmp_path)
    monkeypatch.setattr(b, 'gh_json', Mock(side_effect=RuntimeError('sensitive URL')))
    data, name = source.find({'id': 'one', 'title': 'Title', 'script': 'Saved'})
    assert name == 'DB:content.script'
    assert data['script'] == ['Saved']
    assert source.errors == ['artifact listing: RuntimeError']


def test_recovered_script_uses_existing_article_guard(monkeypatch, tmp_path):
    import pytest
    from pipeline import article
    db = DB()
    seed(db, 'one')
    monkeypatch.setattr(article, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(article.CostGuard, 'check', lambda *a, **kw: False)
    client = Mock(channel=article.Channel())
    with pytest.raises(RuntimeError, match='budget guard'):
        article.write_article(db, 'one', claude=client,
                              script_data={'title': 'Saved', 'script': ['Saved']})
    client.run.assert_not_called()
    assert db.select('articles') == []
