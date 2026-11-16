"""Ten Tongues words channel: inventory, episode validation, segment plans, captions, calendar, playlists."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from pipeline import words
from pipeline.common import Channel
from pipeline.words_tts import segments_to_srt


@pytest.fixture
def channel():
    return Channel("tentongues")


@pytest.fixture
def fixture():
    return json.loads(words.FIXTURE.read_text())


class SettingsDB:
    sb = None

    def __init__(self):
        self.settings, self.content = {}, []

    def setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value

    def select(self, table, match=None, **kw):
        return [r for r in self.content if all(r.get(k) == v for k, v in (match or {}).items())]


def test_channel_registered_and_distinct(channel):
    assert "tentongues" in Channel.keys()
    assert channel.cfg["format"] == "words"
    assert len(words.languages(channel)) == 10
    assert len({l["code"] for l in words.languages(channel)}) == 10
    others = [Channel(k) for k in Channel.keys() if k != "tentongues"]
    assert all(o.voice.get("kokoro") != channel.voice["kokoro"] for o in others)
    assert all(tuple(o.style["accent"]) != tuple(channel.style["accent"]) for o in others)
    keys = {p["key"] for p in channel.cfg["topic_playlists"]}
    assert keys == {"long", *(l["code"] for l in words.languages(channel))}


def test_inventory_and_pick_skips_used(channel):
    inventory = words.word_inventory(channel)
    assert len(inventory) >= 250
    assert len({w["word"] for w in inventory}) == len(inventory)
    db = SettingsDB()
    assert words.pick_word(db, channel) == inventory[0]["word"]
    words.mark_used(db, channel, inventory[0]["word"])
    db.content.append({"channel": "tentongues", "kind": "long", "topic": inventory[1]["word"]})
    assert words.pick_word(db, channel) == inventory[2]["word"]
    assert words.pick_word(db, channel, inventory[0]["word"]) == inventory[0]["word"]
    with pytest.raises(ValueError):
        words.pick_word(db, channel, "notaword")
    words.mark_used(db, channel, inventory[0]["word"])
    assert db.settings["words_used_tentongues"].count(inventory[0]["word"]) == 1


def test_fixture_validates_and_language_order_enforced(channel, fixture):
    langs = words.languages(channel)
    data = words.validate_episode(deepcopy(fixture), langs)
    assert [l["code"] for l in data["languages"]] == [l["code"] for l in langs]
    shuffled = deepcopy(fixture)
    shuffled["languages"].reverse()
    assert [l["code"] for l in words.validate_episode(shuffled, langs)["languages"]] == [l["code"] for l in langs]
    missing = deepcopy(fixture)
    missing["languages"].pop()
    with pytest.raises(ValueError):
        words.validate_episode(missing, langs)
    bad = deepcopy(fixture)
    bad["languages"][0]["romanisation"] = "水"
    with pytest.raises(ValueError):
        words.validate_episode(bad, langs)
    retitled = deepcopy(fixture)
    retitled["title"] = "Water, the word"
    assert "10 languages" in words.validate_episode(retitled, langs)["title"]
    unsafe = deepcopy(fixture)
    unsafe["title"] = "Get rich saying water"
    assert words.validate_episode(unsafe, langs)["title"] == fixture["title_variants"][0]


def test_segment_plans(channel, fixture):
    long = words.long_segments(channel, fixture)
    assert len(long) == 2 + 4 * 10
    assert long[0]["kind"] == "narrator" and long[-1]["kind"] == "narrator"
    native = [s for s in long if s["kind"] == "native"]
    assert len(native) == 20
    assert all(s["spec"].get("backend") in ("kokoro", "piper") for s in native)
    assert any(s["spec"]["backend"] == "piper" for s in native)
    assert all(s["card"]["headline"] and s["card"]["colour"] for s in long)
    short = words.short_segments(channel, fixture, "ur")
    assert short[0]["text"] == "How do you say water in Urdu?"
    assert short[2]["spec"]["voice"] == "ur_PK-fasih-medium"
    assert short[2]["card"]["headline_script"] == "nastaliq"
    assert "Number eight" not in short[1]["text"]
    for cfg, lang in zip(words.languages(channel), fixture["languages"]):
        assert cfg["name"] in words.short_title(fixture, cfg, lang)
        assert "{LONG_URL}" in words.short_description(channel, fixture, cfg, lang)
    desc = words.long_description(channel, fixture)
    assert "Piper bn_BD-google" in desc and "pānī" in desc


def test_mixed_srt_has_word_chunks_and_whole_segment_cues():
    timings = [
        {"index": 0, "start": 0.0, "end": 1.0, "segment": {"kind": "narrator", "text": "Water is agua."},
         "words": [{"text": "Water", "start": 0.0, "end": 0.3}, {"text": "is", "start": 0.3, "end": 0.5}, {"text": "agua.", "start": 0.5, "end": 1.0}]},
        {"index": 1, "start": 1.5, "end": 3.0, "words": [], "segment": {"kind": "native", "text": "agua. agua.", "caption": "agua · agua"}},
    ]
    srt = segments_to_srt(timings)
    blocks = [b for b in srt.strip().split("\n\n") if b]
    assert blocks[0].startswith("1\n") and "Water is agua." in blocks[0]
    assert blocks[-1].startswith(f"{len(blocks)}\n00:00:01,500 --> 00:00:03,000\nagua · agua")


def test_card_renders_every_script(tmp_path, channel, fixture):
    from pipeline import cards
    for cfg, lang in zip(words.languages(channel), fixture["languages"]):
        out = cards.render_card(tmp_path / f"{cfg['code']}.png", size=(640, 360), bg=(20, 14, 36), accent=(167, 139, 250),
                                colour=tuple(cfg["colour"]), kicker=cfg["name"], headline=lang["native"],
                                headline_script=cfg["script"], sub=lang["romanisation"], sub2=lang["ipa"],
                                lines=[(lang["example_native"], cfg["script"]), (lang["memory_hook"], "latin")], footer="Ten Tongues")
        from PIL import Image
        img = Image.open(out)
        assert img.size == (640, 360)
        # Something must be drawn on the card: the bar plus text pixels.
        assert img.convert("L").getextrema()[1] > 200


def test_same_day_short_calendar_and_daily_long(channel):
    from pipeline.publish import _next_slot
    from tests.test_schedule import MemoryDB
    db = MemoryDB()
    now = datetime(2026, 11, 13, 3, 30, tzinfo=timezone.utc)
    long_slot = _next_slot(db, "long", channel, now=now)
    assert long_slot == datetime(2026, 11, 13, 7, tzinfo=timezone.utc)
    db.occupy(channel, long_slot, "long")
    previous = None
    slots = []
    for _ in range(10):
        slot = _next_slot(db, "short", channel, now=now, parent_slot=long_slot, after=previous)
        db.occupy(channel, slot)
        slots.append(slot)
        previous = slot
    assert slots[0] == datetime(2026, 11, 13, 9, tzinfo=timezone.utc)
    assert slots[-1] == datetime(2026, 11, 13, 18, tzinfo=timezone.utc)
    assert len({s.date() for s in slots}) == 1
    # Tomorrow's long video takes the next day, not a later weekday.
    assert _next_slot(db, "long", channel, now=now) == datetime(2026, 11, 14, 7, tzinfo=timezone.utc)
    # Other channels keep their fixed calendar and three-a-day cap.
    assert _next_slot(db, "long", Channel("tradewinds"), now=now) == datetime(2026, 11, 14, 11, tzinfo=timezone.utc)


def test_shorts_join_language_playlists(monkeypatch, channel):
    from pipeline.publish import youtube_promotion as promo
    db = MagicMock()
    settings = {"yt_playlists_enabled": True}
    db.setting.side_effect = lambda key, default=None: settings.get(key, default)
    db.set_setting.side_effect = lambda key, value: settings.__setitem__(key, value)
    api = MagicMock()
    api.playlists.return_value.insert.return_value.execute.return_value = {"id": "pl"}
    monkeypatch.setattr(promo.youtube, "yt", lambda: api)
    monkeypatch.setattr(promo, "reserve", MagicMock(return_value=True))
    promo.new_upload(db, {"id": "s", "kind": "short", "title": "Water in Spanish: agua"}, channel, "v1")
    assert api.playlists.return_value.insert.call_args.kwargs["body"]["snippet"]["title"] == "Spanish word of the day"
    assert settings["yt_playlist_tentongues_es"] == "pl"
    promo.new_upload(db, {"id": "l", "kind": "long", "title": "WATER in 10 languages: say it"}, channel, "v2")
    assert settings["yt_playlist_tentongues_long"] == "pl"
    assert api.playlistItems.return_value.insert.call_count == 2
    # Other channels still exclude Shorts.
    promo.new_upload(db, {"id": "x", "kind": "short", "title": "AI jobs"}, Channel("futurework"), "v3")
    assert api.playlistItems.return_value.insert.call_count == 2
