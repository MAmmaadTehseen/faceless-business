from unittest.mock import MagicMock

from pipeline.publish import youtube


def test_upload_sets_embeddable_and_public_stats(tmp_path, monkeypatch):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")
    api = MagicMock()
    api.videos.return_value.insert.return_value.next_chunk.return_value = (None, {"id": "abc"})
    monkeypatch.setattr(youtube, "yt", lambda: api)
    monkeypatch.setattr(youtube, "synthetic_media", lambda: False)
    monkeypatch.setattr(youtube, "MediaFileUpload", MagicMock())
    try:
        youtube.upload(video, "t", "d", [], privacy="private")
    except Exception:
        pass  # post-insert steps (thumbnail, captions) are not under test
    status = api.videos.return_value.insert.call_args.kwargs["body"]["status"]
    assert status["embeddable"] is True
    assert status["publicStatsViewable"] is True
    assert status["containsSyntheticMedia"] is False
