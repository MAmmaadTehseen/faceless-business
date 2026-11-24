from pipeline.db import DB, PAGE


class Query:
    def __init__(self, rows, calls):
        self.rows, self.calls, self.window = rows, calls, None

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def range(self, start, end):
        self.calls.append((start, end))
        self.window = (start, end)
        return self

    def execute(self):
        start, end = self.window
        return type("R", (), {"data": self.rows[start:end + 1]})()


def db_with(rows):
    calls = []
    db = DB.__new__(DB)
    db.sb = type("SB", (), {"table": lambda self, _: Query(rows, calls)})()
    return db, calls


def test_select_reads_past_postgrest_page_cap():
    rows = [{"id": i} for i in range(2 * PAGE + 5)]
    db, calls = db_with(rows)
    assert [r["id"] for r in db.select("metrics")] == list(range(2 * PAGE + 5))
    assert calls == [(0, PAGE - 1), (PAGE, 2 * PAGE - 1), (2 * PAGE, 3 * PAGE - 1)]


def test_select_limit_stops_early():
    db, calls = db_with([{"id": i} for i in range(3 * PAGE)])
    assert len(db.select("metrics", match={"x": 1}, limit=PAGE + 10)) == PAGE + 10
    assert calls == [(0, PAGE - 1), (PAGE, PAGE + 9)]
