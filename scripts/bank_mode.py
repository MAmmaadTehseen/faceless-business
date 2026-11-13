"""Owner-run: turn scheduled stockpile banking on or off.

    .venv/bin/python scripts/bank_mode.py on 2026-11-24   # JSON true + inclusive cutoff date
    .venv/bin/python scripts/bank_mode.py off
    .venv/bin/python scripts/bank_mode.py status

Reads Supabase configuration from .env via pipeline.common. Prints setting values only.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.db import DB  # noqa: E402
from pipeline.bank_gate import enabled  # noqa: E402


def main(argv):
    db = DB()
    action = argv[1] if len(argv) > 1 else 'status'
    if action == 'on':
        until = date.fromisoformat(argv[2])
        db.set_setting('bank_mode_enabled', True)
        db.set_setting('bank_until', until.isoformat())
    elif action == 'off':
        db.set_setting('bank_mode_enabled', False)
    elif action != 'status':
        raise SystemExit(__doc__)
    print('bank_mode_enabled =', repr(db.setting('bank_mode_enabled')))
    print('bank_until =', repr(db.setting('bank_until')))
    print('banked_release_per_day =', repr(db.setting('banked_release_per_day', 0)))
    print('scheduled gate open now:', enabled(db))


if __name__ == '__main__':
    main(sys.argv)
