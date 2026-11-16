"""Hub article -> Facebook Page link posts."""
import json

from pipeline.common import Channel
from pipeline.publish import hub_share, meta


class MemDB:
    def __init__(self, articles):
        self.articles, self.settings = articles, {}

    def setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value

    def select(self, table, match=None, order=None, desc=False, **kw):
        rows = [r for r in self.articles if all(r.get(k) == v for k, v in (match or {}).items())]
        if order:
            rows.sort(key=lambda r: r.get(order) or "", reverse=desc)
        return rows


ART = {"id": "futurework-2026-11-10-x", "slug": "layoffs-fell", "title": "Layoffs fell. Tech kept cutting.",
       "quick_answer": "Layoffs fell nationally. Tech firms kept cutting anyway. A third sentence that should be dropped.",
       "excerpt": "e", "channel": "futurework", "published_at": "2026-11-10T00:00:00+00:00"}


def _configure(monkeypatch, posted):
    monkeypatch.setattr(meta, "fb_configured", lambda: True)
    monkeypatch.setattr(meta, "publish_facebook_link_post", lambda message, link: posted.append((message, link)) or {"id": "1_2", "url": "https://www.facebook.com/1_2"})


def test_message_has_title_two_sentences_question_link_and_tags():
    msg = hub_share.article_post_message(ART, Channel("futurework"))
    assert msg.startswith("Layoffs fell. Tech kept cutting.")
    assert "third sentence" not in msg
    assert "https://hub.ammaad.online/a/layoffs-fell" in msg
    assert msg.count("#") == 2 and "?" in msg


def test_share_posts_once_and_records_marker(monkeypatch):
    posted = []
    _configure(monkeypatch, posted)
    db = MemDB([ART])
    assert hub_share.share_article_to_facebook(db, ART, Channel("futurework")) == "1_2"
    assert hub_share.share_article_to_facebook(db, ART, Channel("futurework")) is None
    assert len(posted) == 1 and posted[0][1].endswith("/a/layoffs-fell")
    assert db.settings["fb_article_post_" + ART["id"]]["post_id"] == "1_2"


def test_disabled_unpublished_and_failures_never_raise(monkeypatch):
    posted = []
    _configure(monkeypatch, posted)
    db = MemDB([ART])
    db.set_setting("fb_article_posts_enabled", False)
    assert hub_share.share_article_to_facebook(db, ART, Channel("futurework")) is None
    db.set_setting("fb_article_posts_enabled", True)
    assert hub_share.share_article_to_facebook(db, {**ART, "published_at": None}, Channel("futurework")) is None
    def boom(message, link):
        raise RuntimeError("api down")
    monkeypatch.setattr(meta, "publish_facebook_link_post", boom)
    assert hub_share.share_article_to_facebook(db, ART, Channel("futurework")) is None
    assert posted == [] and "fb_article_post_" + ART["id"] not in db.settings


def test_backfill_one_per_day_newest_first(monkeypatch):
    posted = []
    _configure(monkeypatch, posted)
    older = {**ART, "id": "old", "slug": "old", "published_at": "2026-11-01T00:00:00+00:00"}
    db = MemDB([older, ART])
    ch = Channel("futurework")
    assert hub_share.backfill_articles(db, ch) == 1
    assert posted[0][1].endswith("/a/layoffs-fell")
    assert hub_share.backfill_articles(db, ch) == 0  # daily cap
    assert hub_share.backfill_articles(db, ch, max_per_day=2) == 1  # second slot shares the older one
    assert posted[1][1].endswith("/a/old")
