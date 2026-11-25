"""Ten Tongues words channel: inventory, episode validation, segment plans, captions, calendar, playlists."""
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
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
    assert "pānī" in desc and "Wasser" in desc and "bn_BD" not in desc


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


def test_short_title_ab_by_day():
    data, cfg, lang = {"word": "rice"}, {"name": "Russian"}, {"romanisation": "ris"}
    assert words.short_title(data, cfg, lang) == "Rice in Russian: ris"
    assert words.short_title(data, cfg, lang, "2026-11-25", ab=True) == "Rice in Russian: ris"
    assert words.short_title(data, cfg, lang, "2026-11-26", ab=True) == "How to Say Rice in Russian (ris)"
    assert words.short_title(data, cfg, lang, "2026-11-26", ab=False) == "Rice in Russian: ris"
    assert "how to say rice in Russian" in words.short_tags("rice", cfg)


def test_short_tags_native_queries():
    hindi = words.short_tags("milk", {"name": "Hindi", "code": "hi"}, {"romanisation": "dūdh"})
    assert "hindi mein dudh kaise likhte hain" in hindi
    assert "milk ko hindi mein kya kehte hain" in hindi
    assert "dudh in english" in hindi
    spanish = words.short_tags("milk", {"name": "Spanish", "code": "es"}, {"romanisation": "leche"})
    assert "cómo se dice leche en inglés" in spanish
    assert words.plain("shuǐguǒ") == "shuiguo"
    french = words.short_tags("fruit", {"name": "French", "code": "fr"}, {"romanisation": "fruit"})
    assert "fruit in english" not in french and len(french) == len(set(french)) <= 15
    assert words.short_tags("rice", {"name": "Russian", "code": "ru"}) == words.short_tags("rice", {"name": "Russian"})


# ---------- word reveal (Remotion WordReveal, mocked; ffmpeg never runs) ----------

REVEAL_TIMINGS = [
    {"index": 0, "start": 0.0, "end": 2.0, "segment": {"card": {"kicker": "title", "headline": "WATER", "colour": [1, 2, 3]}}},
    {"index": 1, "start": 2.45, "end": 5.0, "segment": {"card": {"kicker": "urdu", "headline": "پانی", "colour": [4, 5, 6]},
                                                       "reveal": {"native": "پانی", "romanisation": "pānī", "language": "Urdu",
                                                                  "script": "nastaliq", "direction": "rtl"}}},
    {"index": 2, "start": 5.45, "end": 8.0, "segment": {"card": {"kicker": "example", "headline": "میں پانی پیتا ہوں", "colour": [4, 5, 6]}}},
    {"index": 3, "start": 8.45, "end": 12.0, "segment": {"card": {"kicker": "remember it", "headline": "pānī", "colour": [4, 5, 6]}}},
]


def _motion_channel(channel):
    """The same Channel with style.motion forced on (channel.json ships it false)."""
    channel.style = {**channel.style, "motion": True}
    return channel


def test_reveal_used_when_motion_on(tmp_path, monkeypatch, channel):
    """style.motion on + ensure_installed true -> the native-word card segment renders through
    remotion.render_segment('reveal', ...) with exactly the card clip's duration."""
    from pipeline import remotion

    channel = _motion_channel(channel)
    renders = MagicMock(return_value=tmp_path / "seg_reveal.mp4")
    cards = MagicMock(side_effect=lambda png, sec, out, orientation: out)
    monkeypatch.setattr(remotion, "render_segment", renders)
    monkeypatch.setattr(remotion, "ensure_installed", MagicMock(return_value=True))
    monkeypatch.setattr(remotion, "bundled_entry_point", lambda: "src/Root.tsx")
    monkeypatch.setattr(words, "render_card", lambda *a, **k: tmp_path / "c.png")
    monkeypatch.setattr(words, "card_clip", cards)

    clips = words._segment_clips(REVEAL_TIMINGS, "landscape", channel, tmp_path / "work")

    assert renders.call_count == 1  # only the native-word card segment
    args = renders.call_args.args
    assert args[0] == "reveal"
    assert args[1] == {"native": "پانی", "romanisation": "pānī", "language": "Urdu",
                       "script": "nastaliq", "direction": "rtl"}
    # same duration as the card clip it replaces: ceil(sec*30) frames at 30 fps
    until = REVEAL_TIMINGS[2]["start"]  # the card stays up through the gap
    assert args[2] == math.ceil(max(until - REVEAL_TIMINGS[1]["start"], 0.5) * 30) / 30
    assert args[3] == "landscape" and args[4].name == "seg_001.mp4"
    assert {"accent", "bg"} <= set(args[5]) and args[5].get("fontFile", "Poppins-ExtraBold.ttf") == "Poppins-ExtraBold.ttf"
    assert args[5]["accent"] == list(channel.style["accent"])
    assert cards.call_count == 3  # the other three segments use the still card clip
    assert [c.name for c in clips][1] == "seg_reveal.mp4"


def test_reveal_off_when_motion_false(tmp_path, monkeypatch, channel):
    """style.motion false (channel.json today) -> no remotion call at all, every clip a card."""
    from pipeline import remotion

    renders = MagicMock()
    monkeypatch.setattr(remotion, "render_segment", renders)
    monkeypatch.setattr(remotion, "ensure_installed", MagicMock(return_value=True))
    monkeypatch.setattr(words, "render_card", lambda *a, **k: tmp_path / "c.png")
    monkeypatch.setattr(words, "card_clip", MagicMock(side_effect=lambda png, sec, out, orientation: out))

    clips = words._segment_clips(REVEAL_TIMINGS, "portrait", channel, tmp_path / "work")

    renders.assert_not_called()
    assert len(clips) == len(REVEAL_TIMINGS)


def test_reveal_failure_falls_back_to_card(tmp_path, monkeypatch, channel):
    """remotion.render_segment raising -> the existing still card clip is used for that segment."""
    from pipeline import remotion

    channel = _motion_channel(channel)
    monkeypatch.setattr(remotion, "render_segment", MagicMock(side_effect=RuntimeError("chrome missing")))
    monkeypatch.setattr(remotion, "ensure_installed", MagicMock(return_value=True))
    monkeypatch.setattr(remotion, "bundled_entry_point", lambda: "src/Root.tsx")
    monkeypatch.setattr(words, "render_card", lambda *a, **k: tmp_path / "c.png")
    cards = MagicMock(side_effect=lambda png, sec, out, orientation: out)
    monkeypatch.setattr(words, "card_clip", cards)

    clips = words._segment_clips(REVEAL_TIMINGS, "landscape", channel, tmp_path / "work")

    assert len(clips) == len(REVEAL_TIMINGS)  # one clip per segment, no gaps
    assert cards.call_count == 4  # the failed reveal fell back to the card path


def test_reveal_direction_rtl_for_urdu_and_ltr_others(channel, fixture):
    """nastaliq/arabic scripts reveal right to left; every other script left to right."""
    ur = next(cfg for cfg in words.languages(channel) if cfg["code"] == "ur")
    urdu = next(l for l in fixture["languages"] if l["code"] == "ur")
    assert words._reveal_payload(ur, urdu) == {"native": "پانی", "romanisation": "pānī", "language": "Urdu",
                                               "script": "nastaliq", "direction": "rtl"}
    for cfg, lang in zip(words.languages(channel), fixture["languages"]):
        payload = words._reveal_payload(cfg, lang)
        assert payload["direction"] == ("rtl" if cfg["script"] in ("arabic", "nastaliq") else "ltr")
        assert payload["script"] == cfg["script"] and payload["language"] == cfg["name"]
        assert payload["native"] == lang["native"] and payload["romanisation"] == lang["romanisation"]
    # segment plans attach the payload to the native-word card segments only
    long = words.long_segments(channel, fixture)
    with_reveal = [s for s in long if s.get("reveal")]
    assert len(with_reveal) == 2 * len(words.languages(channel))
    assert all(s["card"]["headline"] == s["reveal"]["native"] for s in with_reveal)
    assert not any(s.get("reveal") for s in long if s not in with_reveal)
    short = words.short_segments(channel, fixture, "ur")
    assert [s.get("reveal") for s in short].count(words._reveal_payload(ur, urdu)) == 3
