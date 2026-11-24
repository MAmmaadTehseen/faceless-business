"""Weekly retention review turns measured drop-offs into prompt lessons (growth log 2026-11-24)."""
from unittest.mock import patch

from pipeline.common import Channel
from pipeline.db import DB
from pipeline import retention_review as rr


def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr("pipeline.db.DATA_DIR", tmp_path)
    return DB()


def test_analyse_finds_steepest_drop_and_snippet():
    pts = [(i / 100, 1.0) for i in range(10)] + [(0.10, 0.6)] + [(i / 100, 0.55) for i in range(11, 100)]
    script = " ".join(f"w{i}" for i in range(200))
    found = rr.analyse(pts, 300.0, script)
    assert found["drop_at_s"] == 30 and found["drop"] == 0.4
    assert "w20" in found["left_during"] and found["opening"].startswith("w0")


def test_review_stores_lessons_weekly_and_prompt_block(tmp_path, monkeypatch):
    db = _db(tmp_path, monkeypatch)
    db.insert("content", {"id": "futurework-a", "channel": "futurework", "kind": "long", "topic": "t",
                          "title": "Title A", "script": " ".join(f"w{i}" for i in range(300)), "duration_sec": 120})
    db.insert("publications", {"content_id": "futurework-a", "platform": "youtube", "status": "live",
                               "privacy": "public", "platform_id": "VID1", "publish_at": "2026-11-20T00:00:00Z"})
    pts = [(i / 100, 1.0 if i < 15 else 0.5) for i in range(100)]
    with patch.object(rr.youtube, "configured", return_value=True), \
         patch.object(rr.youtube, "auth_failed", return_value=False), \
         patch.object(rr.youtube, "use_channel"), \
         patch.object(rr.youtube, "stats", return_value={"VID1": {"views": 40}}), \
         patch.object(rr, "_curve", return_value=pts):
        lessons = rr.review(db, Channel("futurework"))
        assert lessons["long"]["worst"][0]["drop_at_s"] == 18
        assert rr.review(db, Channel("futurework")) is None  # weekly: second call in the same week is skipped
    block = rr.prompt_block(db, "futurework", "long")
    assert "Title A" in block and "lost 50% of viewers at 18 s" in block
    assert rr.prompt_block(db, "futurework", "short") == ""
