from hub.bus import FileBus
from hub.db import init_db


def test_publish_and_idempotent_consume(tmp_path, monkeypatch):
    init_db()
    bus = FileBus()
    env = bus.publish("feeds.ingested", {"feed_id": "F-test", "ok": True}, key="F-test")
    seen = []
    n = bus.consume("feeds.ingested", lambda e: seen.append(e.event_id))
    assert n >= 1
    assert env.event_id in seen
    n2 = bus.consume("feeds.ingested", lambda e: seen.append(e.event_id))
    assert n2 == 0
