import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pipeline.common import Claude, CostGuard, source_context, validate_output

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


def response(text='{"ok":true}', status=200):
    mock = MagicMock(status_code=status, headers={})
    mock.json.return_value = {"model": "glm-5.3", "content": [{"type": "text", "text": text}],
                              "usage": {"input_tokens": 100, "output_tokens": 20}, "stop_reason": "end_turn"}
    return mock


def client(monkeypatch, db=None):
    monkeypatch.setenv("LLM_PROVIDER", "lunaroute")
    monkeypatch.setenv("LUNAROUTE_API_KEY", "test-only-key")
    return Claude(db)


def test_default_anthropic_http(monkeypatch):
    import httpx2 as httpx
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "msg_test", "type": "message", "role": "assistant",
            "model": "claude-opus-5-5", "content": [{"type": "text", "text": '{"ok":true}'}],
            "stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 10}}, request=request)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-key")
    monkeypatch.setattr(httpx.Client, "send", lambda self, request, **kwargs: handler(request))
    claude = Claude()
    # Real SDK request construction over mocked HTTP, preserving the wrapper stream interface.
    def stream(**kwargs):
        result = claude.client.beta.messages.create(**kwargs)
        context = MagicMock()
        context.__enter__.return_value.get_final_message.return_value = result
        return context
    monkeypatch.setattr(claude.client.beta.messages, "stream", stream)
    result, usd = claude.run("script", "fixture", schema=SCHEMA)
    assert result == {"ok": True} and usd > 0
    assert claude.provider == "anthropic"
    assert calls[0]["output_config"]["format"]["schema"] == SCHEMA
    assert calls[0]["fallbacks"] == "default"


def test_lunaroute_wire_and_cost(monkeypatch, tmp_path):
    from pipeline.db import DB
    db = DB()
    claude = client(monkeypatch, db)
    post = MagicMock(return_value=response())
    monkeypatch.setattr("requests.post", post)
    result, usd = claude.run("engage", "fixture", schema=SCHEMA)
    assert result == {"ok": True} and usd == 0
    args, kwargs = post.call_args
    assert args[0] == "https://gw.lunaroute.com/v1/messages"
    assert kwargs["json"]["model"] == "glm-5.3-flash"
    assert kwargs["headers"]["LUNAROUTE-API-KEY"] == "test-only-key"
    assert not {"tools", "betas", "fallbacks", "output_config"} & kwargs["json"].keys()
    assert db.select("costs")[0]["model"] == "lunaroute/glm-5.3"
    assert db.select("costs")[0]["usd"] == 0


@pytest.mark.parametrize("bad", ['not JSON', '{"ok":"yes"}', '{"wrong":true}'])
def test_one_schema_repair(monkeypatch, bad):
    claude = client(monkeypatch)
    post = MagicMock(side_effect=[response(bad), response()])
    monkeypatch.setattr("requests.post", post)
    assert claude.run("script", "fixture", schema=SCHEMA, retries=0)[0] == {"ok": True}
    assert post.call_count == 2 and claude.calls == 2
    assert "Repair" in post.call_args.kwargs["json"]["messages"][-1]["content"]


def test_repair_limit_and_call_guard(monkeypatch):
    claude = client(monkeypatch)
    post = MagicMock(return_value=response("{}"))
    monkeypatch.setattr("requests.post", post)
    with pytest.raises(RuntimeError, match="after one repair"):
        claude.run("script", "fixture", schema=SCHEMA)
    assert post.call_count == 2
    monkeypatch.setenv("LLM_MAX_CALLS_PER_CLIENT", "2")
    with pytest.raises(RuntimeError, match="call limit"):
        claude.run("script", "fixture")
    assert post.call_count == 2


def test_vision_format_and_override(monkeypatch, tmp_path):
    claude = client(monkeypatch)
    monkeypatch.setenv("LLM_MODEL_VISION", "glm-5.3-vision-custom")
    post = MagicMock(return_value=response())
    monkeypatch.setattr("requests.post", post)
    image = tmp_path / "fixture.png"
    image.write_bytes(b"fixture-image")
    claude.vision("recap_qa", "Check image", [image], SCHEMA)
    body = post.call_args.kwargs["json"]
    assert body["model"] == "glm-5.3-vision-custom"
    assert body["messages"][0]["content"][0]["source"]["media_type"] == "image/png"
    assert body["messages"][0]["content"][0]["source"]["type"] == "base64"


@pytest.mark.parametrize("provider,key,base,message", [
    ("unknown", "key", "https://gw.lunaroute.com", "LLM_PROVIDER"),
    ("lunaroute", "", "https://gw.lunaroute.com", "LUNAROUTE_API_KEY"),
    ("lunaroute", "key", "http://unsafe.example", "LUNAROUTE_BASE_URL"),
    ("lunaroute", "key", "https://host.example/bad", "LUNAROUTE_BASE_URL"),
    ("anthropic", "key", "https://gw.lunaroute.com", "ANTHROPIC_API_KEY"),
])
def test_fail_fast(monkeypatch, provider, key, base, message):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LUNAROUTE_API_KEY", key)
    monkeypatch.setenv("LUNAROUTE_BASE_URL", base)
    with pytest.raises(ValueError, match=message):
        Claude()


def test_auth_error_never_switches(monkeypatch):
    claude = client(monkeypatch)
    post = MagicMock(return_value=response(status=401))
    monkeypatch.setattr("requests.post", post)
    with pytest.raises(RuntimeError, match="HTTP 401"):
        claude.run("script", "fixture")
    assert post.call_count == 1 and claude.client is None


def test_research_http_extraction(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    fetched = MagicMock(status_code=200, headers={"Content-Type": "text/html"})
    fetched.iter_content.return_value = [b"<html><script>ignore me</script><p>Useful source text.</p></html>"]
    fetched.__enter__.return_value = fetched
    get = MagicMock(return_value=fetched)
    monkeypatch.setattr("requests.get", get)
    sources = source_context(["https://source.example/story"])
    assert "Useful source text" in sources[0]["text"]
    assert "ignore me" not in sources[0]["text"]
    assert get.call_args.kwargs["allow_redirects"] is False
    claude = client(monkeypatch)
    post = MagicMock(return_value=response())
    monkeypatch.setattr("requests.post", post)
    claude.run("script", "Seed headline", schema=SCHEMA, web_search=True,
               supplied_sources=["https://source.example/story"])
    system = post.call_args.kwargs["json"]["system"]
    assert "Only supplied sources may be cited" in system
    assert "Useful source text" in system
    assert "tools" not in post.call_args.kwargs["json"]


def test_source_timeout_and_private_hosts(monkeypatch):
    import requests
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    get = MagicMock(side_effect=requests.Timeout())
    monkeypatch.setattr("requests.get", get)
    assert "unavailable" in source_context(["https://source.example/story"])[0]["text"]
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    assert source_context(["https://private.example/story"]) == []


def test_zero_cost_budget_not_unlimited_calls(monkeypatch):
    from pipeline.db import DB
    db = DB()
    claude = client(monkeypatch, db)
    db.set_setting("monthly_budget_usd", 0)
    assert CostGuard(db).check("script", 100)
    monkeypatch.setenv("LLM_MAX_CALLS_PER_CLIENT", "0")
    with pytest.raises(RuntimeError, match="call limit"):
        claude.run("script", "fixture")


def test_schema_nested_constraints():
    schema = {"type": "array", "items": {"anyOf": [SCHEMA, {"type": "null"}]}}
    validate_output([None, {"ok": True}], schema)
    with pytest.raises(ValueError):
        validate_output([{"ok": 1}], schema)


def test_retries_remain_same_provider_and_are_logged(monkeypatch):
    from pipeline.db import DB
    db = DB()
    claude = client(monkeypatch, db)
    retry = response(status=429)
    retry.headers = {"Retry-After": "1"}
    post = MagicMock(side_effect=[retry, response()])
    monkeypatch.setattr("requests.post", post)
    sleep = MagicMock()
    monkeypatch.setattr("pipeline.common.time.sleep", sleep)
    assert claude.run("script", "fixture", schema=SCHEMA)[0] == {"ok": True}
    assert len(db.select("costs")) == 2
    assert {c["model"] for c in db.select("costs")} == {"lunaroute/glm-5.3"}
    assert all(call.args[0] == "https://gw.lunaroute.com/v1/messages" for call in post.call_args_list)
    sleep.assert_called_once_with(1)


def test_article_rejects_unsupplied_evidence(monkeypatch, tmp_path):
    from pipeline.article import write_article
    from pipeline.common import Channel
    from test_article import valid_article
    db = MagicMock()
    db.kind = "mock"
    db.one.side_effect = lambda table, match: {"id": "fixture", "kind": "long", "channel": "tradewinds"} if table == "content" else None
    db.select.return_value = []
    db.setting.side_effect = lambda key, default=None: default
    db.month_to_date_cost.return_value = 0
    monkeypatch.setattr("pipeline.article.OUT_DIR", tmp_path)
    monkeypatch.setattr("pipeline.article.article_thumbnail", lambda *a, **kw: None)
    claude = MagicMock(provider="lunaroute", channel=Channel("tradewinds"))
    good = valid_article()
    claude.run.return_value = (good, 0)
    with pytest.raises(ValueError, match="Evidence source_url must come from supplied_sources"):
        write_article(db, "fixture", claude=claude,
                      script_data={"title": "A Focused Explainer", "supplied_sources": ["https://other.example/story"]})
    assert claude.run.call_count == 2
    assert claude.run.call_args.kwargs["supplied_sources"] == ["https://other.example/story"]
    assert db.upsert.call_count == 0


def test_article_missing_sources_fails_before_model(monkeypatch):
    from pipeline.article import write_article
    from pipeline.common import Channel
    db = MagicMock()
    db.one.side_effect = lambda table, match: {"id": "fixture", "kind": "long", "channel": "tradewinds"} if table == "content" else None
    monkeypatch.setattr("pipeline.article.article_thumbnail", lambda *a, **kw: None)
    claude = MagicMock(provider="lunaroute", channel=Channel("tradewinds"))
    with pytest.raises(ValueError, match="saved supplied_sources"):
        write_article(db, "fixture", claude=claude, script_data={"title": "Fixture"})
    claude.run.assert_not_called()


def test_lunaroute_vision_failure_blocks_qa(monkeypatch, tmp_path):
    from pipeline.qa import run_qa
    monkeypatch.setattr("pipeline.qa.probe", lambda *a: {"duration": 20, "has_audio": True, "width": 1920, "height": 1080})
    monkeypatch.setattr("pipeline.qa.temporal_findings", lambda *a: [])
    monkeypatch.setattr("pipeline.qa.grab_frame", lambda *a: tmp_path / "frame.jpg")
    claude = MagicMock(provider="lunaroute")
    claude.vision.side_effect = RuntimeError("LunaRoute HTTP 401")
    with pytest.raises(RuntimeError, match="requires successful vision QA"):
        run_qa(claude, tmp_path / "video.mp4", None, 20, "fixture", tmp_path)


def test_provider_setting_and_env_precedence(monkeypatch):
    from pipeline.db import DB
    db = DB()
    db.set_setting("llm_provider", "lunaroute")
    monkeypatch.setenv("LUNAROUTE_API_KEY", "test-only-key")
    assert Claude(db).provider == "lunaroute"
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    # No Anthropic key: must fail rather than use configured LunaRoute.
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Claude(db)


def test_configured_base_and_models(monkeypatch):
    monkeypatch.setenv("LUNAROUTE_BASE_URL", "https://gateway.example/v1")
    claude = client(monkeypatch)
    monkeypatch.setenv("LLM_MODEL_SCRIPT", "deepseek-4.1-flash")
    post = MagicMock(return_value=response())
    monkeypatch.setattr("requests.post", post)
    claude.run("script", "fixture", schema=SCHEMA)
    assert post.call_args.args[0] == "https://gateway.example/v1/messages"
    assert post.call_args.kwargs["json"]["model"] == "deepseek-4.1-flash"
    assert post.call_args.kwargs["allow_redirects"] is False
    assert claude.model_for("recap_script") == "glm-5.3"


def test_http_redirect_refused(monkeypatch):
    claude = client(monkeypatch)
    post = MagicMock(return_value=response(status=307))
    monkeypatch.setattr("requests.post", post)
    with pytest.raises(RuntimeError, match="HTTP 307"):
        claude.run("script", "fixture")
    assert post.call_count == 1
