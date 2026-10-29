"""Atomic, project-wide upload reservations; never refund uncertain API attempts."""
from datetime import datetime, timezone

UPLOAD_COST = 1600
THUMB_COST = 50
UPDATE_COST = 50
RESERVE = 1000


def reserve(db, units, keep_reserve=RESERVE):
    if db.sb:
        return bool(db.sb.rpc("reserve_youtube_quota", {"p_units": units, "p_reserve": keep_reserve}).execute().data)
    day = datetime.now(timezone.utc).date().isoformat()
    db.conn.execute("begin immediate")
    try:
        row = db.conn.execute("select units from quota_log where day=?", (day,)).fetchone()
        legacy = db.conn.execute("""select coalesce(sum(1600 + case when c.thumbnail_path is not null then 50 else 0 end),0)
            from publications p join content c on c.id=p.content_id
            where p.platform='youtube' and date(p.published_at)=?""", (day,)).fetchone()[0]
        spent = max(row[0] if row else 0, legacy)
        budget = int(db.setting("youtube_quota_units_per_day", 10000)) - keep_reserve
        if spent + units > budget:
            db.conn.rollback()
            return False
        db.conn.execute("insert into quota_log(day,units) values(?,?) on conflict(day) do update set units=excluded.units", (day, spent + units))
        db.conn.commit()
        return True
    except Exception:
        db.conn.rollback()
        raise
