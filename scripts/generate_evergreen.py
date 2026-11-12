"""Owner-run LunaRoute inventory generation. Writes JSON and durable settings; no publishing."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import Channel, Claude, CostGuard, CHANNELS_DIR
from pipeline.db import DB
from pipeline.evergreen import duplicate, history, inventory, SOURCES


def generate(db, channel, claude):
    if claude.provider != 'lunaroute':
        raise RuntimeError('Evergreen generation requires LLM_PROVIDER=lunaroute')
    if not CostGuard(db).check('ideate', est_usd=0):
        raise RuntimeError('Budget guard stopped evergreen generation')
    old = inventory(db, channel)
    avoid = [r.get(k, '') for r in history(db, channel) for k in ('title', 'topic')] + [r['topic'] for r in old]
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['topics'], 'properties': {
        'topics': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
          'required': ['topic', 'angle'], 'properties': {'topic': {'type': 'string'}, 'angle': {'type': 'string'}}}}}}
    data, _ = claude.run('ideate', 'Generate 75 distinct timeless educational video topics for this channel persona. '
        'Explain durable mechanisms; no news, dates, current officeholders, prices or time-bound forecasts. '
        'Avoid income promises and medical/legal/financial advice. Return 60-80 topics. Avoid these existing topics/titles: '
        + json.dumps(avoid) + '\nGround topics in these durable sources: ' + json.dumps(SOURCES[channel.key]), supplied_sources=SOURCES[channel.key], web_search=True, schema=schema, max_tokens=14000)
    accepted = []
    from pipeline.script import BANNED_TITLE
    for item in data['topics']:
        if not BANNED_TITLE.search(item['topic']) and not duplicate(item['topic'], avoid + [x['topic'] for x in accepted]):
            item['source_urls'] = SOURCES[channel.key]
            accepted.append(item)
    if not 60 <= len(accepted) <= 80:
        raise RuntimeError(f'Only {len(accepted)} unique topics; inventory unchanged. Rerun owner script.')
    # Settings survive fresh runners; file is the owner-reviewable snapshot.
    path = CHANNELS_DIR / channel.key / 'evergreen.json'
    path.write_text(json.dumps(old + accepted, indent=2) + '\n')
    db.set_setting('evergreen_topics_' + channel.key, old + accepted)
    return len(accepted)


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--channel', required=True, choices=Channel.keys())
    args = ap.parse_args()
    db, channel = DB(), Channel(args.channel)
    print(f'Generated {generate(db, channel, Claude(db, channel=channel))} topics for {channel.key}')


if __name__ == '__main__':
    main()
