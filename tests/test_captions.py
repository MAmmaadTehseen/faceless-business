"""Deterministic Short/Reel metadata and the Reels-follow-YouTube spacing rule."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

import pipeline.publish as publish
from pipeline.common import Channel
from pipeline.db import DB
from pipeline.publish.captions import (comment_question, hashtags, hook_line, reels_caption, short_tags,
                                       uses_legacy_description, youtube_short_description)

SCRIPT = ("The FTC is asking what drivers actually get paid. Uber says the median is thirty dollars an hour. "
          "The regulator's filing says the number hides waiting time. Here is why that matters for your next ride. "
          "Would you take the job at that rate?")


def row(**kw):
    base = {"id": "futurework-2026-11-16-x-short-1", "kind": "short", "parent_id": "futurework-2026-11-16-x",
            "title": "The FTC Is Asking What Drivers Get Paid", "script": SCRIPT, "channel": "futurework", "topic": "driver pay",
            "description": "The FTC Is Asking What Drivers Get Paid\n\nFull video: {LONG_URL}\n#shorts", "qa_status": "passed"}
    base.update(kw)
    return base


def test_hashtags_come_from_channel_config_and_are_distinct_per_channel():
    tags = {k: hashtags(Channel(k)) for k in ("futurework", "tradewinds", "escapevelocity")}
    for t in tags.values():
        assert 3 <= len(t) <= 5 and all(t_.isalnum() or "_" in t_ for t_ in t)
    assert not (set(tags["futurework"]) & set(tags["tradewinds"]) & set(tags["escapevelocity"]))


def test_reels_caption_has_hook_question_hashtags_and_no_links():
    text = reels_caption(row(), Channel("futurework"))
    assert text.startswith("The FTC is asking what drivers actually get paid.")
    assert "Would you take the job at that rate?" in text
    assert "#FutureOfWork" in text and "#shorts" not in text
    assert "http" not in text and "@" not in text and len(text) <= 2200


def test_reels_caption_falls_back_to_title_and_channel_question():
    ch = Channel("tradewinds")
    text = reels_caption(row(script="", title="Freight up 342 percent. Demand isn't."), ch)
    assert text.startswith("Freight up 342 percent. Demand isn't.")
    assert ch.cfg["caption_question"] in text
    assert comment_question({"script": "No question here."}, ch) == ch.cfg["caption_question"]


def test_youtube_short_description_keeps_link_footer_and_three_hashtags():
    ch = Channel("escapevelocity")
    desc = youtube_short_description(row(channel="escapevelocity"), ch, "https://youtu.be/abc")
    assert "Full video: https://youtu.be/abc" in desc and ch.cfg["description_footer"] in desc
    last = desc.splitlines()[-1]
    assert last.count("#") == 4 and last.endswith("#Shorts")
    assert "{LONG_URL}" in youtube_short_description(row(), ch)
    standalone = youtube_short_description(row(parent_id=None), ch)
    assert "Full video" not in standalone


def test_legacy_stub_detection_and_tags():
    assert uses_legacy_description("Title\n\nFull video: https://youtu.be/x\n#shorts")
    assert uses_legacy_description("")
    assert not uses_legacy_description("A real two-sentence description. Sources: https://example.com")
    tags = short_tags({"tags": ["AI jobs"]}, Channel("futurework"), ["Netherlands AI job cuts", "ai jobs"])
    assert tags[:2] == ["AI jobs", "Netherlands AI job cuts"] and len(tags) <= 15 and "future of work" in tags


def test_hook_line_prefers_spoken_first_sentence():
    assert hook_line(row()) == "The FTC is asking what drivers actually get paid."
    assert hook_line(row(script="Hi.")) == row()["title"]


@pytest.fixture
def meta_db(monkeypatch):
    db = DB()
    monkeypatch.setattr(publish.youtube, "configured", lambda: False)
    monkeypatch.setattr(publish.meta, "configured", lambda: True)
    monkeypatch.setattr(publish.meta, "ig_configured", lambda: True)
    monkeypatch.setattr(publish.meta, "fb_configured", lambda: True)
    monkeypatch.setattr(publish, "_media_url", lambda *a: "https://example.invalid/reel.mp4")
    monkeypatch.setattr(publish, "_local_file", lambda *a: "reel.mp4")
    ig, fb = Mock(return_value={"id": "ig-1"}), Mock(return_value={"id": "fb-1"})
    monkeypatch.setattr(publish.meta, "publish_instagram_reel", ig)
    monkeypatch.setattr(publish.meta, "publish_facebook_reel", fb)
    yield db, ig, fb
    db.conn.close()


def test_child_reels_wait_for_scheduled_youtube_slot(meta_db):
    db, ig, fb = meta_db
    r = row()
    db.insert("content", {k: r[k] for k in ("id", "kind", "parent_id", "title", "script", "channel", "description", "qa_status", "topic")})
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    db.insert("publications", {"content_id": r["id"], "platform": "youtube", "platform_id": "yt1", "privacy": "private",
                               "status": "live", "publish_at": future})
    publish.publish_short(db, r, Channel("futurework"), "public", "https://youtu.be/abc")
    assert ig.call_count == fb.call_count == 0
    assert "Full video: https://youtu.be/abc" in db.one("content", {"id": r["id"]})["description"]
    # Once sync sees the YouTube copy public, the follow-up publishes Reels with the new caption.
    db.update("publications", {"content_id": r["id"], "platform": "youtube"}, {"privacy": "public"})
    publish.publish_short(db, r, Channel("futurework"), "public", "https://youtu.be/abc")
    assert ig.call_count == fb.call_count == 1
    caption = ig.call_args.args[1]
    assert caption.startswith("The FTC is asking") and "#FutureOfWork" in caption and "youtu.be" not in caption


def test_standalone_and_setting_off_publish_reels_immediately(meta_db):
    db, ig, fb = meta_db
    r = row(parent_id=None, id="futurework-2026-11-16-short-x", description="")
    publish.publish_short(db, r, Channel("futurework"), "public")
    assert ig.call_count == 1
    db.set_setting("reels_follow_youtube", False)
    r2 = row(id="futurework-2026-11-16-y-short-1")
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    db.insert("publications", {"content_id": r2["id"], "platform": "youtube", "platform_id": "yt2", "privacy": "private",
                               "status": "live", "publish_at": future})
    publish.publish_short(db, r2, Channel("futurework"), "public")
    assert ig.call_count == 2
