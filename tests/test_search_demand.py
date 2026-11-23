"""Search demand from YouTube autocomplete, and the quick/standard Shorts length budgets."""
import pipeline.search_demand as sd
from pipeline.script import budget, tighten_shorts, QUICK_WORDS, SHORT_WORDS


class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_phrases_are_specific_content_ngrams():
    assert sd.subject_terms("Starship Flight 15: the catch is not the test")[0] == "starship flight 15"
    assert "nasa swift" in sd.subject_terms("NASA's Swift Is Falling: Where It Lands")


def test_demand_and_prompt_block(monkeypatch):
    calls = []
    monkeypatch.setattr(sd.requests, "get", lambda url, params, timeout: calls.append(params["q"]) or Resp([params["q"], [params["q"] + " launch", "unrelated thing"]]))
    d = sd.demand("Starship Flight 15 test")
    assert d["score"] >= 3 and "starship flight 15 launch" in d["phrases"] and "unrelated thing" not in d["phrases"]
    block = sd.prompt_block("Starship Flight 15 test")
    assert block.startswith("Real YouTube search phrases") and "hook_title" in block
    n = len(calls)
    sd.demand("Starship Flight 15 test")
    assert len(calls) == n  # cached


def test_failures_are_soft():
    assert sd.suggestions("anything") == []  # conftest disables the network
    assert sd.prompt_block("anything at all") == ""


def test_quick_and_standard_budgets():
    assert budget({"length": "quick"})[0] == QUICK_WORDS
    assert budget({})[0] == SHORT_WORDS


def test_tighten_uses_quick_budget():
    class FakeClaude:
        def __init__(self):
            self.prompts = []

        def run(self, step, prompt, **kw):
            self.prompts.append(prompt)
            return {"script": " ".join(["word"] * 60)}, 0.0

    c = FakeClaude()
    script = " ".join(["word"] * 90)  # fine for standard, too long for quick
    out = tighten_shorts(c, [{"hook_title": "q", "script": script, "length": "quick"}, {"hook_title": "s", "script": script}])
    assert len(c.prompts) == 1 and "50-70 words" in c.prompts[0]
    assert len(out[0]["script"].split()) == 60 and out[1]["script"] == script
