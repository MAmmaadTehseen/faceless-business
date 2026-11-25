from pipeline.db import DB
from pipeline.sync import comments_grew


def test_comment_threads_read_only_when_count_rises():
    db = DB()
    assert comments_grew(db, 1, 0) is False
    assert comments_grew(db, 1, 3) is True  # never measured
    db.insert_many("metrics", [{"publication_id": 1, "views": 10, "likes": 0, "comments": 3}])
    assert comments_grew(db, 1, 3) is False
    assert comments_grew(db, 1, 2) is False  # a deletion is not new comments
    assert comments_grew(db, 1, 4) is True
