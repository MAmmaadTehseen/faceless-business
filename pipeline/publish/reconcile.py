"""Resolve uncertain uploads before any retry; incomplete scans never clear uncertainty."""
import json
from datetime import datetime, timedelta, timezone

from . import youtube
from .jarvis import update
from .quota import reserve


def metadata(pub):
    try:
        value = json.loads(pub.get('error') or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def reconcile_uploads(db, channel, *, apply=True, now=None):
    youtube.use_channel(channel)
    rows = {r['id']: r for r in db.select('content', {'channel': channel.key})
            if r.get('status') != 'killed'}
    pending = [p for p in db.select('publications', {'platform': 'youtube'})
               if p['content_id'] in rows and not p.get('platform_id')
               and (p.get('status') == 'uploading' or metadata(p).get('upload_uncertain'))]
    if not pending or not youtube.configured() or youtube.auth_failed(channel):
        return []
    # Even dry runs reserve read quota: these are real API reads, never uploads.
    if not reserve(db, 1):
        return []
    try:
        api = youtube.yt()
        channels = api.channels().list(part='contentDetails', mine=True).execute()['items']
        playlist = channels[0]['contentDetails']['relatedPlaylists']['uploads']
        videos, token = [], None
        while True:
            if not reserve(db, 1):
                return []  # no negative decisions from partial history
            page = api.playlistItems().list(part='snippet,contentDetails', playlistId=playlist,
                                           maxResults=50, **({'pageToken': token} if token else {})).execute()
            videos.extend(page.get('items', []))
            token = page.get('nextPageToken')
            if not token:
                break
    except Exception as exc:
        if youtube.is_auth_failure(exc):
            youtube.mark_auth_failed()
            return []
        raise
    now = now or datetime.now(timezone.utc)
    decisions = []
    for pub in pending:
        row = rows[pub['content_id']]
        stamp = metadata(pub).get('attempted_at') or pub.get('created_at')
        try:
            attempted = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if attempted.tzinfo is None:
                attempted = None
        except (ValueError, TypeError, AttributeError):
            attempted = None
        # Any same-title upload blocks retry, but only a time-compatible unique
        # candidate can be adopted as the outcome of this upload attempt.
        matches = [v for v in videos if v.get('snippet', {}).get('title', '').strip().casefold()
                   == row['title'][:100].strip().casefold()]
        candidates = []
        for video in matches:
            published = video.get('contentDetails', {}).get('videoPublishedAt') or video.get('snippet', {}).get('publishedAt')
            try:
                uploaded = datetime.fromisoformat(published.replace('Z', '+00:00'))
                if attempted and attempted - timedelta(minutes=15) <= uploaded <= now:
                    candidates.append(video)
            except (ValueError, TypeError, AttributeError):
                pass
        fields = None
        if len(candidates) == 1:
            vid = candidates[0]['contentDetails']['videoId']
            fields = {'status': 'live', 'platform_id': vid, 'url': f'https://youtu.be/{vid}', 'error': None}
        elif not matches and (attempted is not None and now - attempted >= timedelta(hours=24)):
            # Unknown attempt age never permits another upload.
            fields = {'status': 'queued', 'error': json.dumps({'reason': 'reconciled_no_upload',
                      'reconciled_at': now.isoformat()})}
        if fields:
            decisions.append({'publication_id': pub['id'], **fields})
            if apply:
                if fields['status'] == 'queued':
                    from . import _queue_media
                    from ..retry import restore
                    try:
                        restored = restore(db, row, pub)
                        fields.update(_queue_media(db, restored, pub))
                    except Exception:
                        # Preserve uncertainty until media can be rebuilt/restored.
                        decisions[-1] = {'publication_id': pub['id'], 'status': pub['status'],
                                         'reason': 'media_not_recoverable'}
                        continue
                update(db, {'id': pub['id'], 'status': pub['status'], 'error': pub.get('error'),
                            'platform_id': None}, fields)
                current = db.one('publications', {'id': pub['id']})
                if fields['status'] == 'live' and current and current.get('platform_id') == fields['platform_id']:
                    db.update('content', {'id': row['id']}, {'status': 'published'})
    return decisions
