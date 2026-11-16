"""tighten_shorts shortens over-budget Short scripts and keeps originals on failure."""
from pipeline.script import SHORT_WORDS, tighten_shorts


LONG = " ".join(f"word{i}" for i in range(130))
SHORT = "Nvidia lost ninety billion dollars in one afternoon. " + " ".join(f"w{i}" for i in range(80)) + " Who pays?"


class FakeClaude:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def run(self, step, user, **kw):
        self.calls.append((step, kw.get("content_id")))
        if self.error:
            raise self.error
        return {"script": self.reply}, 0.0


def test_short_within_budget_is_untouched():
    claude = FakeClaude(reply=SHORT)
    out = tighten_shorts(claude, [{"hook_title": "ok", "script": SHORT, "query": "q"}], "cid")
    assert out[0]["script"] == SHORT
    assert claude.calls == []


def test_long_short_is_rewritten_with_one_small_call():
    claude = FakeClaude(reply=SHORT)
    out = tighten_shorts(claude, [{"hook_title": "long", "script": LONG, "query": "q"}], "cid")
    assert out[0]["script"] == SHORT
    assert len(out[0]["script"].split()) <= SHORT_WORDS[1] + 5
    assert out[0]["query"] == "q" and out[0]["hook_title"] == "long"
    assert claude.calls == [("short_tighten", "cid")]


def test_rewrite_still_too_long_or_too_short_keeps_original():
    assert tighten_shorts(FakeClaude(reply=LONG), [{"hook_title": "x", "script": LONG}])[0]["script"] == LONG
    assert tighten_shorts(FakeClaude(reply="too short"), [{"hook_title": "x", "script": LONG}])[0]["script"] == LONG


def test_model_failure_is_nonfatal():
    out = tighten_shorts(FakeClaude(error=RuntimeError("boom")), [{"hook_title": "x", "script": LONG}])
    assert out[0]["script"] == LONG
