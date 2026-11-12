"""Read-only scheduled banking gate. Invalid dates and settings fail closed."""
from datetime import datetime, timezone, date


def enabled(db, today=None):
    if db.setting('bank_mode_enabled', False) is not True or db.setting('pipeline_paused', False):
        return False
    try:
        until = date.fromisoformat(db.setting('bank_until', ''))
    except (ValueError, TypeError):
        return False
    return (today or datetime.now(timezone.utc).date()) <= until


if __name__ == '__main__':
    from .db import DB
    print('true' if enabled(DB()) else 'false')
