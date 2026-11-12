"""Owner-only OAuth helper. Tokens are saved locally and never printed."""
import argparse
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
KEYS = ('futurework', 'tradewinds', 'escapevelocity')
SCOPES = ['https://www.googleapis.com/auth/youtube', 'https://www.googleapis.com/auth/youtube.force-ssl',
          'https://www.googleapis.com/auth/yt-analytics.readonly']
REDIRECT = 'http://localhost:8765/'


def token_variable(key):
    if key == 'drive':
        return 'GDRIVE_REFRESH_TOKEN'
    if key not in KEYS:
        raise ValueError('Unknown channel key')
    return 'YT_REFRESH_TOKEN' + ('' if key == 'futurework' else '_' + key.upper())


def steps(key):
    if key == 'drive':
        return ('1. Enable Google Drive API on the existing OAuth project; add only drive.file for this grant.\n'
                '2. Run: .venv/bin/python scripts/youtube_auth.py url drive\n'
                '3. Open privately using the owner Google Drive account; copy the localhost redirect.\n'
                '4. Run: .venv/bin/python scripts/youtube_auth.py token "<full redirect URL>" drive\n'
                '5. Owner: set Actions secret GDRIVE_REFRESH_TOKEN from the local saved value, never logs.')
    return (f'1. Google Cloud Console > Google Auth Platform > Audience: check Publishing status. '
            'External apps in Testing issue 7-day refresh tokens for YouTube scopes. '
            'Use Publish app / In production when eligible; complete requested verification. '
            'This is separate from the YouTube API compliance audit.\n'
            f'2. Run: .venv/bin/python scripts/youtube_auth.py url {key}\n'
            '3. Open the URL privately, select the correct YouTube channel and allow access. '
            'Copy the full localhost redirect URL even if the page does not load.\n'
            f'4. Run: .venv/bin/python scripts/youtube_auth.py token "<full redirect URL>" {key}\n'
            f'5. Owner: update GitHub Actions secret {token_variable(key)} from the saved local value '
            'using gh secret set or GitHub Settings > Secrets and variables > Actions. Never paste it in logs.\n'
            f'6. Run reconciliation --dry-run, review, then --apply before draining {key}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('url', 'steps'):
        cmd = sub.add_parser(command)
        cmd.add_argument('channel', choices=(*KEYS, 'drive'), nargs='?', default='futurework')
    cmd = sub.add_parser('token')
    cmd.add_argument('redirect_url')
    cmd.add_argument('channel', choices=(*KEYS, 'drive'), nargs='?', default='futurework')
    args = parser.parse_args()
    if args.command == 'steps':
        print(steps(args.channel))
        return
    from dotenv import load_dotenv
    from google_auth_oauthlib.flow import Flow
    load_dotenv(ROOT / '.env')
    cid, secret = os.getenv('YT_CLIENT_ID'), os.getenv('YT_CLIENT_SECRET')
    if not cid or not secret:
        parser.exit(1, 'Set YT_CLIENT_ID and YT_CLIENT_SECRET locally first.\n')
    flow = Flow.from_client_config({'installed': {'client_id': cid, 'client_secret': secret,
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth', 'token_uri': 'https://oauth2.googleapis.com/token',
        'redirect_uris': [REDIRECT]}}, ['https://www.googleapis.com/auth/drive.file'] if args.channel == 'drive' else SCOPES, redirect_uri=REDIRECT, autogenerate_code_verifier=False)
    if args.command == 'url':
        print(steps(args.channel))
        url, _ = flow.authorization_url(access_type='offline', prompt='consent', include_granted_scopes='false' if args.channel == 'drive' else 'true')
        print(url)
        return
    code = parse_qs(urlparse(args.redirect_url).query).get('code', [None])[0]
    if not code:
        parser.exit(1, 'Could not find code= in redirect URL.\n')
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    try:
        flow.fetch_token(code=code)
    except Exception:
        parser.exit(1, 'OAuth exchange failed. Generate a new URL and retry; credentials were not printed.\n')
    token = flow.credentials.refresh_token
    if not token:
        parser.exit(1, 'No refresh token: revoke app access at myaccount.google.com/permissions and retry.\n')
    variable = token_variable(args.channel)
    path = ROOT / '.env'
    env = path.read_text() if path.exists() else ''
    env = re.sub(rf'^{variable}=.*$', lambda _: f'{variable}={token}', env, flags=re.M) if re.search(rf'^{variable}=', env, re.M) else env.rstrip('\n') + f'\n{variable}={token}\n'
    path.write_text(env)
    print(f'{variable} saved locally; token not printed. Owner must update the matching GitHub secret.')


if __name__ == '__main__':
    main()
