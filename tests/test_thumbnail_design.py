"""Thumbnail text layout, frame choice and the thumbnail retry bookkeeping."""
from pathlib import Path

from PIL import Image

from pipeline.thumbnail import frame_score, thumbnail_lines


def test_thumbnail_lines_subject_first_and_capped():
    assert thumbnail_lines("DUTCH GOVT: 25,000 AI CUTS") == ["DUTCH GOVT:", "25,000 AI", "CUTS"]
    assert thumbnail_lines("GOLDMAN: AI LAYOFFS DELAYED") == ["GOLDMAN: AI", "LAYOFFS", "DELAYED"]
    assert thumbnail_lines("one two three four five six") == ["ONE TWO", "THREE FOUR", "FIVE"]


def test_flat_colour_card_scores_below_textured_frame(tmp_path):
    card = tmp_path / "card.jpg"
    Image.new("RGB", (320, 180), (210, 60, 200)).save(card)
    textured = tmp_path / "tex.jpg"
    img = Image.new("RGB", (320, 180))
    px = img.load()
    for x in range(320):
        for y in range(180):
            px[x, y] = ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    img.save(textured)
    assert frame_score(card) < frame_score(textured)


def test_upload_reports_thumbnail_failure_and_sync_retries(monkeypatch, tmp_path):
    from pipeline.publish import youtube, remember_pending_thumbnail, retry_pending_thumbnails, PENDING_THUMB
    from pipeline.common import Channel
    from tests.test_hub_share import MemDB
    thumb = tmp_path / "t.jpg"
    Image.new("RGB", (1280, 720), (10, 10, 10)).save(thumb)
    db = MemDB([])
    db.sb = None
    db.select = lambda table, *a, **k: [{"key": k_, "value": v} for k_, v in db.settings.items()] if table == "settings" else []
    class Conn:
        def execute(self, sql, params): db.settings.pop(params[0], None)
        def commit(self): pass
    db.conn = Conn()
    ch = Channel("escapevelocity")
    remember_pending_thumbnail(db, ch, "vid1", thumb)
    assert db.settings[PENDING_THUMB + "vid1"]["channel"] == "escapevelocity"
    calls = []
    monkeypatch.setattr(youtube, "set_thumbnail", lambda vid, path: calls.append((vid, Path(path).name)))
    monkeypatch.setattr(youtube, "use_channel", lambda c: None)
    import pipeline.publish as pub
    monkeypatch.setattr(pub, "reserve", lambda db_, units: True)
    assert retry_pending_thumbnails(db, Channel("futurework")) == 0  # other channel's row untouched
    assert retry_pending_thumbnails(db, ch) == 1
    assert calls == [("vid1", "t.jpg")] and PENDING_THUMB + "vid1" not in db.settings
