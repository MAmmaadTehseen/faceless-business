"""Read YouTube's uploads playlist to resolve uncertain publications; never upload."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from pipeline.common import Channel
    from pipeline.db import DB
    from pipeline.publish.reconcile import reconcile_uploads
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='Only report proposed publication changes (read quota is recorded)')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--channel', choices=Channel.keys())
    args = parser.parse_args()
    db = DB()
    for key in ([args.channel] if args.channel else Channel.keys()):
        print(json.dumps({'channel': key, 'apply': args.apply,
                          'decisions': reconcile_uploads(db, Channel(key), apply=args.apply)}))


if __name__ == '__main__':
    main()
