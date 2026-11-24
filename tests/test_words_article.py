"""Ten Tongues hub articles: deterministic build from the saved episode, saved like the model writer."""
import json
from unittest.mock import MagicMock, patch

import pytest

from pipeline import words, words_article
from pipeline.common import Channel


@pytest.fixture
def channel():
    return Channel("tentongues")


@pytest.fixture
def episode():
    return json.loads(words.FIXTURE.read_text())


def test_build_article_tables_sections_and_faq(channel, episode):
    data = words_article.build_article(channel, episode)
    assert data["title"] == "WATER in 10 languages"
    assert data["slug"] == "how-to-say-water-in-10-languages"
    body = data["body_md"]
    assert "{{YOUTUBE}}" in body and "| Language | Word | Romanisation | IPA |" in body
    assert body.count("\n| ") >= 22  # two tables of ten rows plus separators
    russian = next(l for l in episode["languages"] if l["code"] == "ru")
    assert "## How to say water in Russian" in body and russian["native"] in body
    questions = [f["question"] for f in data["faqs"]]
    assert questions[0] == "How do you say water in different languages?"
    assert "How do you say water in Russian?" in questions and len(questions) == 6
    assert "水 (shuǐ) in Mandarin" in data["quick_answer"]
    assert len(data["meta_description"]) <= 160 and len(data["meta_title"]) <= 70
    assert "bn_BD" not in body  # Bengali (CC BY-SA credit line) replaced by German 2026-11-24


def test_table_cells_escape_pipes(channel, episode):
    episode["languages"][0]["example_english"] = "a | b"
    assert "a \\| b" in words_article.build_article(channel, episode)["body_md"]


def fake_db(episode, youtube_id="abcdefghijk", existing=None):
    db = MagicMock()
    db.sb = None
    rows = {
        "content": {"id": "tt-1", "kind": "long", "channel": "tentongues", "qa_notes": json.dumps({"words_episode": episode})},
        "publications": {"platform_id": youtube_id} if youtube_id else None,
        "articles": existing,
    }
    db.one.side_effect = lambda table, match: rows[table] if table != "articles" or "id" in match else None
    db.select.return_value = []
    db.upsert.side_effect = lambda table, row, on: row
    return db


@patch("pipeline.publish.youtube_promotion.article_saved")
@patch.object(words_article, "ping_indexnow")
def test_write_saves_article_row_without_model(ping, saved_hook, episode):
    db = fake_db(episode)
    row = words_article.write_words_article(db, "tt-1", share=False)
    assert row["youtube_id"] == "abcdefghijk" and row["channel"] == "tentongues"
    assert row["published_at"] and "Explore [Ten Tongues](/c/tentongues)" in row["body_md"]
    assert set(row) >= {"title", "excerpt", "body_md", "meta_title", "faqs", "takeaways", "quick_answer", "slug"}
    ping.assert_called_once_with("how-to-say-water-in-10-languages")
    saved_hook.assert_called_once()


def test_write_waits_for_youtube_id(episode):
    db = fake_db(episode, youtube_id=None)
    assert words_article.write_words_article(db, "tt-1") is None
    db.upsert.assert_not_called()


@patch("pipeline.publish.youtube_promotion.article_saved")
@patch.object(words_article, "ping_indexnow")
def test_existing_slug_and_date_preserved(ping, saved_hook, episode):
    db = fake_db(episode, existing={"slug": "water-old", "published_at": "2026-11-20T00:00:00+00:00"})
    row = words_article.write_words_article(db, "tt-1", share=False)
    assert row["slug"] == "water-old" and row["published_at"].startswith("2026-11-20")


@patch("pipeline.publish.youtube_promotion.article_saved")
@patch.object(words_article, "ping_indexnow")
def test_scheduled_episode_article_waits_for_video(ping, saved_hook, episode):
    db = fake_db(episode)
    db.one.side_effect = lambda table, match: {
        "content": {"id": "tt-1", "kind": "long", "channel": "tentongues", "qa_notes": json.dumps({"words_episode": episode})},
        "publications": {"platform_id": "abcdefghijk", "publish_at": "2099-01-01T07:00:00+00:00"},
    }.get(table)
    row = words_article.write_words_article(db, "tt-1", share=False)
    assert row["published_at"] == "2099-01-01T07:00:00+00:00"


def test_facebook_share_skips_future_articles():
    from pipeline.publish import hub_share
    db = MagicMock()
    db.setting.return_value = None
    assert hub_share.share_article_to_facebook(db, {"id": "a", "published_at": "2099-01-01T00:00:00+00:00"}, Channel("tentongues")) is None
    assert hub_share.is_live({"published_at": "2026-01-01T00:00:00+00:00"})
