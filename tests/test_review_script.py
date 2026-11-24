"""Playbook items 13 and 15 (growth log 2026-11-24): per-script review checklist and art-text
digit verification. Deterministic (no model calls): the prompts carry the rules, these tests
pin the measurable enforcement so a refactor cannot silently drop them.
"""
import json
from unittest.mock import Mock

from pipeline.common import ROOT, Channel
from pipeline.review_script import art_text_mismatch, review_findings, log_review
from pipeline import script as script_mod
from pipeline.script import write_script

FIXTURE = json.loads((ROOT / "data" / "fixture_script.json").read_text())


# --- Item 13: art text digits must exist in the narration -------------------------------

def test_art_number_present_in_script_is_clean():
    assert art_text_mismatch("25,000 AI BUYOUTS", "Microsoft offered 25,000 people a buyout.") is None


def test_art_number_absent_from_script_is_flagged():
    finding = art_text_mismatch("200K PER MONTH", "The plan saves two hundred dollars per month.")
    assert finding is not None and "200" in finding


def test_art_abbreviation_matching_script_digits_is_clean():
    # "$25K" on art, "25,000 dollars" spoken: digits agree, currency is backed.
    assert art_text_mismatch("$25K", "The package was worth 25,000 dollars.") is None


def test_art_currency_without_money_word_is_flagged():
    finding = art_text_mismatch("$25,000 SEVERANCE", "The package covers 25,000 people for a year.")
    assert finding is not None and "$" in finding


def test_empty_art_text_is_clean():
    assert art_text_mismatch("", "any narration") is None


def test_spelled_large_number_counts_as_stated():
    # "A million" spoken satisfies "1,000,000" on art.
    assert art_text_mismatch("1,000,000 USERS", "Nearly a million accounts were hit.") is None


# --- Item 15: the review checklist -------------------------------------------------------

def _long_data(opening="Microsoft filed the buyout numbers this week. Twenty five thousand people got the offer."):
    data = json.loads(json.dumps(FIXTURE))
    data["script"] = [opening] + data["script"][1:]
    data["thumbnail_text"] = "25,000 BUYOUTS"
    return data


def test_review_clean_script_has_no_findings():
    assert review_findings(_long_data()) == []


def test_review_flags_concept_opening():
    findings = review_findings(_long_data(opening="Being right is no longer enough in the modern workplace."))
    assert any(f["text"].startswith("review/strategy") for f in findings)


def test_review_flags_banned_filler_phrase():
    data = _long_data()
    data["script"][0] += " In this video we look at the rest."
    findings = review_findings(data)
    assert any(f["text"].startswith("review/voice") for f in findings)


def test_review_flags_art_text_digits_missing_from_script():
    data = _long_data()
    data["thumbnail_text"] = "73,000 BUYOUTS"  # script says twenty five thousand
    findings = review_findings(data)
    assert any(f["text"].startswith("review/accuracy") for f in findings)


def test_review_short_mode_uses_hook_title_for_art():
    data = {"hook_title": "Freight up 342 percent", "script": "Freight rates rose 342 percent this quarter.", "thumbnail_text": ""}
    assert review_findings(data, is_short=True, title_key="hook_title", script_key="script") == []


def test_log_review_info_when_clean_warning_when_dirty(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="pipeline"):
        log_review([], "cid-clean")
        log_review([{"severity": "minor", "text": "review/strategy: no actor"}], "cid-dirty")
    warnings = [r for r in caplog.records if "cid-dirty" in r.getMessage()]
    assert warnings and warnings[0].levelname == "WARNING" and "no actor" in warnings[0].getMessage()
    infos = [r for r in caplog.records if "all checklist areas pass" in r.getMessage()]
    assert infos and infos[0].levelname == "INFO"


# --- run_all preserves the review across the rebuild_notes overwrite ---------------------

def test_rebuild_notes_preserves_script_review():
    from pipeline.run_all import rebuild_notes
    prior = json.dumps({"script_review": [{"severity": "minor", "text": "review/strategy: no actor"}],
                        "paid_script": {"title": "old"}})
    notes = json.loads(rebuild_notes([{"severity": "minor", "text": "soft frame"}],
                                     Channel("futurework"), {"title": "t"}, prior_notes=prior))
    assert notes["script_review"] == [{"severity": "minor", "text": "review/strategy: no actor"}]
    assert notes["rebuild_script"] == {"title": "t"}
    # No prior notes: nothing extra appears and nothing crashes.
    plain = json.loads(rebuild_notes([], Channel("futurework"), {"title": "t"}))
    assert "script_review" not in plain


# --- Integration: write_script stores the review in qa_notes -----------------------------

def test_write_script_persists_review_findings(tmp_path, monkeypatch, caplog):
    import logging
    monkeypatch.setattr(script_mod, "OUT_DIR", tmp_path)
    db = Mock()
    db.one.return_value = None
    db.select.return_value = []
    claude = Mock(db=db)
    data = json.loads(json.dumps(FIXTURE))
    data["script"] = ["Being right is no longer enough. " + FIXTURE["script"][0], *FIXTURE["script"][1:]]
    claude.run.side_effect = lambda step, user, **kw: (data, 0.6) if step == "script" else ({"changed": False}, 0.01)
    with caplog.at_level(logging.WARNING, logger="pipeline"):
        write_script(claude, {"topic": "Test"}, "cid-review")
    notes = None
    for call in db.update.call_args_list:
        payload = call.args[2]
        if isinstance(payload, dict) and "qa_notes" in payload:
            notes = json.loads(payload["qa_notes"])
    assert notes is not None and isinstance(notes.get("script_review"), list)
    assert any("review/" in f["text"] for f in notes["script_review"])
    assert "script review" in caplog.text
