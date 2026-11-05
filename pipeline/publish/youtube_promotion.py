"""Optional promotion for new uploads only; every platform failure is isolated."""
from urllib.parse import urlparse

from ..common import Channel, log
from . import youtube
from .cross_promotion import overlap_score
from .quota import reserve


def clip(text, limit=4900):
    return text.encode('utf-8')[:limit].decode('utf-8', errors='ignore')


def best_match(topic, configs):
    ranked = [(overlap_score(topic, c), i, c) for i, c in enumerate(configs)]
    return min((r for r in ranked if r[0]), key=lambda r: (-r[0], r[1]))[2] if any(r[0] for r in ranked) else None


def description_links(db, row, channel, description):
    try:
        if db.setting('yt_description_links_enabled', False) is not True:
            return clip(description)
        article = db.one('articles', {'id': row.get('parent_id') or row['id']})
        links = []
        if article and article.get('published_at') and article.get('slug'):
            links.append(('Read the article', 'https://hub.ammaad.online/a/' + article['slug']))
        sisters = [Channel(k).cfg for k in Channel.keys() if k != channel.key]
        sister = best_match(row.get('title') or '', [c for c in sisters if valid_url(c.get('youtube_url'))])
        if sister:
            links.append((sister['name'], sister['youtube_url']))
        # Never shorten original text or an existing URL to make room for promotion.
        result = clip(description)
        for label, url in links:
            if url in result:
                continue
            candidate = result.rstrip() + '\n\n' + label + ': ' + url
            if len(candidate.encode('utf-8')) <= 4900:
                result = candidate
        return result
    except Exception as exc:
        log.warning('YouTube description links skipped (%s)', type(exc).__name__)
        return clip(description)


def valid_url(url):
    if not isinstance(url, str) or any(c.isspace() for c in url):
        return False
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname in ('www.youtube.com', 'youtube.com', 'youtu.be') and bool(parsed.path.strip('/'))


def new_upload(db, row, channel, video_id):
    """Called only after a successful videos.insert, never for existing publications."""
    try:
        if db.setting('yt_description_links_enabled', False) is True:
            db.set_setting('yt_links_new_' + video_id, True)
    except Exception as exc:
        log.warning('YouTube link eligibility not saved (%s)', type(exc).__name__)
    try:
        if row['kind'] != 'long' or db.setting('yt_playlists_enabled', False) is not True:
            return
        key = 'yt_playlist_video_' + video_id
        if db.setting(key):
            return
        match = best_match(row.get('title') or '', channel.cfg.get('topic_playlists', []))
        if not match:
            return
        playlist_key = 'yt_playlist_' + channel.key + '_' + match['key']
        playlist_id = db.setting(playlist_key)
        if not playlist_id:
            if not reserve(db, 50):
                return
            playlist_id = youtube.yt().playlists().insert(part='snippet,status', body={
                'snippet': {'title': match['title']}, 'status': {'privacyStatus': 'private'}}).execute()['id']
            db.set_setting(playlist_key, playlist_id)
        if not reserve(db, 50):
            return
        # Retain an attempt marker even on uncertain API outcomes: never double-add.
        db.set_setting(key, {'playlist_id': playlist_id, 'attempted': True})
        youtube.yt().playlistItems().insert(part='snippet', body={'snippet': {
            'playlistId': playlist_id, 'resourceId': {'kind': 'youtube#video', 'videoId': video_id}}}).execute()
    except Exception as exc:
        log.warning('YouTube playlist skipped (%s)', type(exc).__name__)


def article_saved(db, content_id):
    """Refresh only opted-in new uploads in this article's family. No backfill."""
    try:
        if db.setting('yt_description_links_enabled', False) is not True:
            return
        parent = db.one('content', {'id': content_id})
        rows = [parent] + db.select('content', {'parent_id': content_id, 'kind': 'short'})
        channel = Channel(parent.get('channel') or 'futurework')
        youtube.use_channel(channel)
        for row in rows:
            try:
                pub = db.one('publications', {'content_id': row['id'], 'platform': 'youtube'}) or {}
                vid = pub.get('platform_id')
                if not vid or db.setting('yt_links_new_' + vid, False) is not True:
                    continue
                if not reserve(db, 1):
                    continue
                snippet = youtube.yt().videos().list(part='snippet', id=vid).execute()['items'][0]['snippet']
                description = description_links(db, row, channel, snippet.get('description', ''))
                if description == snippet.get('description', '') or not reserve(db, 50):
                    continue
                # Only writable snippet properties; status is deliberately absent.
                body = {k: v for k, v in snippet.items() if k in (
                    'title', 'categoryId', 'tags', 'defaultLanguage', 'defaultAudioLanguage')}
                body['description'] = description
                youtube.yt().videos().update(part='snippet', body={'id': vid, 'snippet': body}).execute()
            except Exception as exc:
                log.warning('YouTube article link skipped (%s)', type(exc).__name__)
    except Exception as exc:
        log.warning('YouTube article promotion skipped (%s)', type(exc).__name__)
