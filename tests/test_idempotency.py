from hub.db import init_db
from hub.security import idempotency_lookup, idempotency_store


def test_idempotency_replay():
    init_db()
    body = {"feed_id": "F-1"}
    idempotency_store("k1", body, {"ok": True})
    assert idempotency_lookup("k1", body) == {"ok": True}
