"""Database layer: Supabase (production) or SQLite (local dev) behind one tiny interface."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import DATA_DIR, log

JSON_COLS = {
    "articles": {"faqs", "entities", "takeaways"},
    "content": {"title_variants", "chapters", "tags"},
    "settings": {"value"},
}


class DB:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if url and key and os.getenv("DB_BACKEND", "auto") != "sqlite":
            from supabase import create_client
            self.sb = create_client(url, key)
            self.kind = "supabase"
            log.info("db: supabase")
        else:
            self.sb = None
            self.kind = "sqlite"
            DATA_DIR.mkdir(exist_ok=True)
            self.conn = sqlite3.connect(DATA_DIR / "local.db")
            self.conn.row_factory = sqlite3.Row
            self._init_sqlite()
            log.info("db: sqlite (local dev)")

    # ---------- sqlite bootstrap ----------
    def _init_sqlite(self):
        sql = (Path(__file__).resolve().parent.parent / "supabase" / "schema.sql").read_text()
        # Remaining objects are Postgres-only telemetry, RPCs and grants.
        sql = sql.split("-- First-party, cookie-free hub telemetry.", 1)[0]
        # Coerce Postgres types to SQLite.
        sql = (sql.replace("bigserial primary key", "integer primary key autoincrement")
                  .replace("timestamptz default now()", "text default (datetime('now'))")
                  .replace("timestamptz", "text")
                  .replace("jsonb", "text")
                  .replace("boolean", "integer")
                  .replace("on conflict (key) do nothing", "")
                  .replace("insert into settings", "insert or ignore into settings"))
        sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("alter table"))
        # Includes articles from schema.sql; the same type coercion applies to its timestamps.
        self.conn.executescript(sql)
        for stmt in ("alter table quota_log add column uploads int not null default 0",
                     "alter table content add column channel text not null default 'futurework'",
                     "alter table topic_queue add column channel text not null default 'futurework'",
                     "alter table content add column placeholder boolean default false",
                     "alter table content add column media_url text",
                     "alter table publications add column media_key text",
                     "alter table publications add column thumbnail_key text",
                     "alter table costs add column channel text", "alter table runs add column channel text"):
            try:
                self.conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        existing = {r[1] for r in self.conn.execute("pragma table_info(articles)")}
        for column in ("meta_title", "meta_description", "primary_keyword", "faqs", "entities", "quick_answer", "takeaways"):
            if column not in existing:
                self.conn.execute(f"alter table articles add column {column} text")
        self.conn.commit()

    # ---------- generic ops ----------
    def insert(self, table: str, row: dict) -> dict:
        row = self._encode(table, row)
        if self.sb:
            res = self.sb.table(table).insert(row).execute()
            return (res.data or [row])[0]
        cols = ", ".join(row)
        qs = ", ".join("?" for _ in row)
        cur = self.conn.execute(f"insert into {table} ({cols}) values ({qs})", list(row.values()))
        self.conn.commit()
        row = dict(row)
        row.setdefault("id", cur.lastrowid)
        return row

    def upsert(self, table: str, row: dict, on: str) -> dict:
        row = self._encode(table, row)
        if self.sb:
            res = self.sb.table(table).upsert(row, on_conflict=on).execute()
            return (res.data or [row])[0]
        cols = ", ".join(row)
        qs = ", ".join("?" for _ in row)
        sets = ", ".join(f"{c}=excluded.{c}" for c in row if c not in on.split(","))
        self.conn.execute(f"insert into {table} ({cols}) values ({qs}) on conflict({on}) do update set {sets}", list(row.values()))
        self.conn.commit()
        return row

    def update(self, table: str, match: dict, fields: dict) -> None:
        fields = self._encode(table, fields)
        if self.sb:
            q = self.sb.table(table).update(fields)
            for k, v in match.items():
                q = q.eq(k, v)
            q.execute()
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        where = " and ".join(f"{k}=?" for k in match)
        self.conn.execute(f"update {table} set {sets} where {where}", [*fields.values(), *match.values()])
        self.conn.commit()

    def select(self, table: str, match: dict | None = None, order: str | None = None, desc: bool = False,
               limit: int | None = None, in_: dict | None = None, gte: dict | None = None, lte: dict | None = None) -> list[dict]:
        if self.sb:
            q = self.sb.table(table).select("*")
            for k, v in (match or {}).items():
                q = q.eq(k, v) if v is not None else q.is_(k, "null")
            for k, v in (in_ or {}).items():
                q = q.in_(k, v)
            for k, v in (gte or {}).items():
                q = q.gte(k, v)
            for k, v in (lte or {}).items():
                q = q.lte(k, v)
            if order:
                q = q.order(order, desc=desc)
            if limit:
                q = q.limit(limit)
            return [self._decode(table, r) for r in (q.execute().data or [])]
        clauses, params = [], []
        for k, v in (match or {}).items():
            if v is None:
                clauses.append(f"{k} is null")
            else:
                clauses.append(f"{k}=?"); params.append(v)
        for k, v in (in_ or {}).items():
            clauses.append(f"{k} in ({', '.join('?' for _ in v)})"); params.extend(v)
        for k, v in (gte or {}).items():
            clauses.append(f"{k}>=?"); params.append(v)
        for k, v in (lte or {}).items():
            clauses.append(f"{k}<=?"); params.append(v)
        sql = f"select * from {table}"
        if clauses:
            sql += " where " + " and ".join(clauses)
        if order:
            sql += f" order by {order} {'desc' if desc else 'asc'}"
        if limit:
            sql += f" limit {limit}"
        return [self._decode(table, dict(r)) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, table: str, match: dict) -> dict | None:
        rows = self.select(table, match, limit=1)
        return rows[0] if rows else None

    # ---------- helpers ----------
    def setting(self, key: str, default: Any = None) -> Any:
        row = self.one("settings", {"key": key})
        if not row:
            return default
        v = row["value"]
        return v if v is not None else default

    def set_setting(self, key: str, value: Any) -> None:
        self.upsert("settings", {"key": key, "value": value}, on="key")

    def month_to_date_cost(self) -> float:
        start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        rows = self.select("costs", gte={"at": start})
        return round(sum(float(r.get("usd") or 0) for r in rows), 4)

    def latest_metrics(self, publication_id: int) -> dict | None:
        rows = self.select("metrics", {"publication_id": publication_id}, order="captured_at", desc=True, limit=1)
        return rows[0] if rows else None

    def _encode(self, table: str, row: dict) -> dict:
        out = {}
        for k, v in row.items():
            if isinstance(v, (dict, list)) or k in JSON_COLS.get(table, set()):
                out[k] = v if self.sb else json.dumps(v)
            elif isinstance(v, bool) and not self.sb:
                out[k] = int(v)
            else:
                out[k] = v
        return out

    def _decode(self, table: str, row: dict) -> dict:
        if self.sb:
            return row
        for k in JSON_COLS.get(table, set()):
            if isinstance(row.get(k), str):
                try:
                    row[k] = json.loads(row[k])
                except json.JSONDecodeError:
                    pass
        return row
