"""Atomic, project-wide upload reservations; never refund uncertain API attempts."""
from datetime import datetime, timezone

THUMB_COST = 50
UPDATE_COST = 50
RESERVE = 1000
UPLOAD_RESERVE = 2


def reserve(db, units, keep_reserve=RESERVE, *, uploads=0, keep_upload_reserve=UPLOAD_RESERVE, force=False):
    if units < 0 or uploads < 0 or units + uploads == 0:
        return False
    keep_reserve = max(keep_reserve, 0)
    keep_upload_reserve = max(keep_upload_reserve, 0)
    if db.sb and force:
        return bool(db.sb.rpc("record_youtube_retry_usage", {"p_units": units, "p_uploads": uploads}).execute().data)
    if db.sb:
        return bool(db.sb.rpc("reserve_youtube_quota", {"p_units": units, "p_reserve": keep_reserve, "p_uploads": uploads, "p_upload_reserve": keep_upload_reserve}).execute().data)
    day = datetime.now(timezone.utc).date().isoformat()
    db.conn.execute("begin immediate")
    try:
        row = db.conn.execute("select units, uploads from quota_log where day=?", (day,)).fetchone()
        spent, uploaded = (row[0], row[1]) if row else (0, 0)
        budget = int(db.setting("youtube_quota_units_per_day", 10000)) - keep_reserve
        upload_budget = int(db.setting("youtube_uploads_per_day", 100)) - keep_upload_reserve
        if not force and (spent + units > budget or uploaded + uploads > upload_budget):
            db.conn.rollback()
            return False
        db.conn.execute("insert into quota_log(day,units,uploads) values(?,?,?) on conflict(day) do update set units=excluded.units, uploads=excluded.uploads", (day, spent + units, uploaded + uploads))
        db.conn.commit()
        return True
    except Exception:
        db.conn.rollback()
        raise
