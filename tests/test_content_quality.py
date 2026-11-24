"""Content-quality pass (2026-11-24): playbook items 1, 2, 4 enforcement and the six-block spine.

`opening_names_actor_or_number` is the measurable half of playbook item 1: concept-only
openings ("Being Right Is No Longer Enough" class) are the documented anti-pattern on
every channel, so the first 40 words of a long script must contain a named actor or a
number. It warns rather than rejects: a reject would strand the paid script response.
The prompt tests pin the six-block spine and the claim/title agreement so a refactor
cannot silently drop them.
"""
import json
from unittest.mock import Mock

from pipeline import script
from pipeline.common import ROOT
from pipeline.script import opening_names_actor_or_number, write_script

FIXTURE = json.loads((ROOT / "data" / "fixture_script.json").read_text())


def test_concept_only_opening_is_flagged():
    assert not opening_names_actor_or_number(
        ["Being right is no longer enough in the modern workplace. The tools changed the "
         "balance of power between people who verify claims and people who merely repeat them."])


def test_number_in_first_words_passes():
    assert opening_names_actor_or_number(
        ["Four hundred thousand dollars per box. That is what one shipment now costs"])


def test_named_actor_mid_sentence_passes():
    assert opening_names_actor_or_number(
        ["The company behind the biggest rollout just filed its numbers. Microsoft disclosed"])


def test_sentence_initial_capital_is_not_an_actor():
    # "The" starting a sentence must not count as a named actor; no digit anywhere either.
    assert not opening_names_actor_or_number(
        ["The quiet rule spreading through hiring this year is simple. The people who "
         "manage the tools are the people who keep the job."])


def test_window_is_the_opening_not_the_whole_script():
    words = ["word"] * 45
    assert not opening_names_actor_or_number([" ".join(words) + " and then 25,000 of them."])


def _claude(db, responses):
    claude = Mock(db=db, provider="anthropic")
    fallback = ({"script": "Microsoft filed the buyout numbers this week. Twenty five thousand people got the offer. "
                            "The filing says the rest pay for it through the winter. Who pays at your desk?"}, 0.0)
    claude.run.side_effect = lambda step, user, **kw: (responses.pop(0) if responses else fallback)
    return claude


def test_write_script_prompt_carries_six_blocks_and_title_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "OUT_DIR", tmp_path)
    db = Mock()
    db.one.return_value = None
    db.select.return_value = []
    claude = _claude(db, [(FIXTURE, 0.6), ({"changed": False}, 0.01)])
    write_script(claude, {"topic": "Test"}, "cid")
    calls = claude.run.call_args_list
    user_prompt = calls[0].args[1]
    for block in ("(1) Hook", "(2) Context beat", "(3) Core message", "(4) Evidence",
                  "(5) Application", "(6) CTA"):
        assert block in user_prompt, f"missing spine block {block}"
    assert "just confirmed it" in user_prompt
    assert "the same claim the first spoken sentence makes" in user_prompt
    assert "first 40 words" in user_prompt
    assert "no title that begins with a gerund" in user_prompt
    hook_prompt = calls[1].args[1]
    assert "first forty words" in hook_prompt


def test_concept_opening_logs_a_warning_not_a_rejection(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(script, "OUT_DIR", tmp_path)
    db = Mock()
    db.one.return_value = None
    db.select.return_value = []
    data = json.loads(json.dumps(FIXTURE))
    data["script"] = ["Being right is no longer enough. " + FIXTURE["script"][0], *FIXTURE["script"][1:]]
    claude = _claude(db, [(data, 0.6), ({"changed": False}, 0.01)])
    import logging
    with caplog.at_level(logging.WARNING, logger="pipeline"):
        out = write_script(claude, {"topic": "Test"}, "cid")
    assert "no named actor or number" in caplog.text
    assert out["script"][0].startswith("Being right")  # not rejected, still produced


def test_daily_short_prompt_carries_the_same_hook_rules():
    """The standalone daily Short shares the winning-title rules (searchable subject first,
    claim-first title, no gerund/adjective opener). Source inspection: the prompt is built
    inline in produce_daily; assert on the module source so a silent revert fails loudly."""
    import inspect
    from pipeline import shorts_daily
    src = inspect.getsource(shorts_daily)
    assert "states a checkable fact or an exact answer (never a mood or a metaphor)" in src
    assert "the title never begins with a gerund or an adjective" in src
    assert "The title states the same claim as the first spoken sentence" in src


def test_ideate_prompt_scores_candidates_and_requires_own_angle():
    import inspect
    from pipeline import ideate
    src = inspect.getsource(ideate)
    assert "series potential" in src
    assert "what everyone else missed" in src
    assert "Rising, not saturated" in src
