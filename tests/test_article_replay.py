"""Offline illustrative replay, not a reconstruction of the lost paid outputs."""
import copy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from pipeline import article as a


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/article_task_exposure.json').read_text())


def test_realistic_replay(capsys):
    raw = fixture()
    before = a.validation_errors(raw, a.assemble_body(raw))
    repaired = a.repair_article(raw)
    errors, warnings = a.article_checks(repaired, a.assemble_body(repaired))
    assert not errors, errors
    assert len(before) >= 6
    assert any('450-600' in e for e in before)
    assert any('headings and intro' in e for e in before)
    assert any('almost identical' in e for e in before)
    assert repaired['entities'] == ['AI']
    assert raw == fixture()  # repair does not destroy the retained response
    assert a.repair_article(repaired) == repaired
    print('Likely failure causes (illustrative offline replay): ' + '; '.join(before))
    print('Remaining editorial warnings: ' + '; '.join(warnings))


def client_and_db():
    db = Mock()
    db.one.side_effect = lambda table, match: {'id':'replay', 'kind':'long', 'channel':'tradewinds'} if table == 'content' else None
    db.select.return_value = []
    db.setting.return_value = 100
    db.upsert.side_effect = lambda table, row, on: row
    return Mock(channel=a.Channel('tradewinds')), db


def prepare(monkeypatch, tmp_path):
    monkeypatch.setattr(a, 'OUT_DIR', tmp_path)
    monkeypatch.setattr(a.CostGuard, 'check', lambda *args, **kwargs: True)
    monkeypatch.setattr(a, 'ping_indexnow', Mock())


def test_one_call_and_patch_preserves_fields(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    client, db = client_and_db()
    data = fixture()
    data['cta_md'] = f'Watch the embedded video.\n\nSubscribe to [Trade Winds](https://www.youtube.com/@{client.channel.handle}).'
    client.run.return_value = (data, 0)
    result = a.write_article(db, 'replay', claude=client, script_data={'title': data['title']})
    assert client.run.call_count == 1
    client, db = client_and_db()
    broken = copy.deepcopy(data)
    broken['faqs'] = []
    client.run.side_effect = [(broken, 0), ({'faqs': data['faqs']}, 0)]
    retried = a.write_article(db, 'replay', claude=client, script_data={'title': data['title']})
    assert {k: v for k, v in retried.items() if k not in ('published_at', 'updated_at')} == {k: v for k, v in result.items() if k not in ('published_at', 'updated_at')}
    call = client.run.call_args
    assert set(call.kwargs['schema']['properties']) == {'faqs'}
    assert 'intro_md' not in call.args[1]
    files = list((tmp_path / 'article-failures').glob('*.json'))
    assert len(files) == 1
    saved = json.loads(files[0].read_text())
    assert saved['raw'] == broken
    assert saved['failures'] == ['Use exactly 5 FAQs']


def test_quality_failure_saves_every_attempt_and_never_publishes(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    client, db = client_and_db()
    data = fixture()
    data['sections'][1]['evidence']['source_url'] = data['sections'][0]['evidence']['source_url']
    client.run.side_effect = [(data, 0), ({'sections': data['sections'], 'cta_md': data['cta_md']}, 0)]
    with pytest.raises(ValueError, match='distinct registered domains'):
        a.write_article(db, 'replay', claude=client, script_data={'title': data['title']})
    assert len(list((tmp_path / 'article-failures').glob('*.json'))) == 2
    db.upsert.assert_not_called()


def test_backfill_prints_full_failure(monkeypatch, capsys):
    from scripts import backfill_articles as b
    from pipeline.db import DB
    from test_article_backfill import seed, sources
    db = DB()
    seed(db, 'bad')
    monkeypatch.setattr(b, 'write_article', Mock(side_effect=ValueError('First failure; Second failure')))
    assert b.backfill(db, apply=True, sources=sources()) == ['bad']
    assert 'ValueError: First failure; Second failure' in capsys.readouterr().out
