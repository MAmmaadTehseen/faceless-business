import importlib.util
from pathlib import Path
from unittest import mock


def _load():
    spec = importlib.util.spec_from_file_location("yt_scoreboard", Path(__file__).parent.parent / "scripts" / "yt_scoreboard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_channel_videos_dedupes_repeated_playlist_items():
    sb = _load()
    pages = [
        {"items": [{"contentDetails": {"videoId": "a"}}, {"contentDetails": {"videoId": "b"}}], "nextPageToken": "t"},
        {"items": [{"contentDetails": {"videoId": "b"}}, {"contentDetails": {"videoId": "a"}}]},
    ]
    requested = []

    def videos_list(part, id):
        requested.append(id)
        items = [{"id": v, "status": {"privacyStatus": "public"}, "snippet": {"title": v, "publishedAt": "2026-11-20T00:00:00Z"},
                  "contentDetails": {"duration": "PT30S"}, "statistics": {"viewCount": "5"}} for v in id.split(",")]
        return mock.Mock(execute=mock.Mock(return_value={"items": items}))

    client = mock.Mock()
    client.channels().list().execute.return_value = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU"}}}]}
    client.playlistItems().list().execute.side_effect = pages
    client.videos().list.side_effect = videos_list
    with mock.patch.object(sb, "channel_for"), mock.patch.object(sb.youtube, "use_channel"), \
            mock.patch.object(sb.youtube, "yt", return_value=client), mock.patch.object(sb.youtube, "analytics", return_value={}), \
            mock.patch.object(sb, "known_ids", return_value=[]):
        rows = sb.channel_videos("futurework")
    assert [r["id"] for r in rows] == ["a", "b"]
    assert requested == ["a,b"]


def test_known_ids_adds_videos_the_playlist_dropped(tmp_path):
    import json
    sb = _load()
    (tmp_path / "2026-11-25T07.json").write_text(json.dumps({"videos": [
        {"channel": "tradewinds", "id": "old"}, {"channel": "futurework", "id": "other"}]}))
    (tmp_path / "broken.json").write_text("not json")
    assert sb.known_ids("tradewinds", tmp_path) == ["old"]
    client = mock.Mock()
    client.channels().list().execute.return_value = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU"}}}]}
    client.playlistItems().list().execute.return_value = {"items": [{"contentDetails": {"videoId": "new"}}]}
    requested = []

    def videos_list(part, id):
        requested.append(id)
        return mock.Mock(execute=mock.Mock(return_value={"items": []}))

    client.videos().list.side_effect = videos_list
    with mock.patch.object(sb, "channel_for"), mock.patch.object(sb.youtube, "use_channel"), \
            mock.patch.object(sb.youtube, "yt", return_value=client), mock.patch.object(sb.youtube, "analytics", return_value={}), \
            mock.patch.object(sb, "HISTORY", tmp_path):
        sb.channel_videos("tradewinds")
    assert requested == ["new,old"]
