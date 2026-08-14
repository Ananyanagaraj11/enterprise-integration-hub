"""File-backed event bus that mirrors Kafka topics, consumer groups, and DLQ.

Use this locally. docker-compose can swap in Kafka later without changing publishers.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from hub.db import DATA_DIR, connect

BUS_DIR = DATA_DIR / "bus"
BUS_DIR.mkdir(parents=True, exist_ok=True)

TOPICS = (
    "feeds.ingested",
    "feeds.canonicalized",
    "feeds.failed",
    "webhooks.received",
    "sagas.commands",
    "sagas.events",
)


@dataclass
class Envelope:
    event_id: str
    topic: str
    key: str
    payload: dict
    headers: dict
    ts: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(raw: str) -> "Envelope":
        data = json.loads(raw)
        return Envelope(**data)


class FileBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        for topic in TOPICS:
            (BUS_DIR / topic).mkdir(exist_ok=True)
            (BUS_DIR / f"{topic}.dlq").mkdir(exist_ok=True)

    def publish(self, topic: str, payload: dict, key: str = "", headers: dict | None = None) -> Envelope:
        env = Envelope(
            event_id=str(uuid.uuid4()),
            topic=topic,
            key=key or payload.get("feed_id") or payload.get("correlation_id") or "",
            payload=payload,
            headers=headers or {},
            ts=time.time(),
        )
        path = BUS_DIR / topic / f"{int(env.ts * 1000)}_{env.event_id}.json"
        with self._lock:
            path.write_text(env.to_json(), encoding="utf-8")
            conn = connect()
            conn.execute(
                "INSERT INTO outbox(topic, payload, headers, published_at) VALUES (?,?,?,datetime('now'))",
                (topic, json.dumps(payload), json.dumps(headers or {})),
            )
            conn.commit()
            conn.close()
        return env

    def consume(self, topic: str, handler: Callable[[Envelope], None], max_messages: int = 50) -> int:
        folder = BUS_DIR / topic
        files = sorted(folder.glob("*.json"))[:max_messages]
        processed = 0
        for path in files:
            raw = path.read_text(encoding="utf-8")
            env = Envelope.from_json(raw)
            try:
                conn = connect()
                exists = conn.execute(
                    "SELECT 1 FROM inbox WHERE event_id=?", (env.event_id,)
                ).fetchone()
                if exists:
                    path.unlink(missing_ok=True)
                    conn.close()
                    continue
                handler(env)
                conn.execute(
                    "INSERT INTO inbox(event_id, topic, payload) VALUES (?,?,?)",
                    (env.event_id, topic, json.dumps(env.payload)),
                )
                conn.commit()
                conn.close()
                path.unlink(missing_ok=True)
                processed += 1
            except Exception as exc:  # noqa: BLE001
                dlq = BUS_DIR / f"{topic}.dlq" / path.name
                dlq.write_text(raw, encoding="utf-8")
                conn = connect()
                conn.execute(
                    "INSERT INTO dlq(topic, payload, error) VALUES (?,?,?)",
                    (topic, raw, str(exc)),
                )
                conn.commit()
                conn.close()
                path.unlink(missing_ok=True)
        return processed

    def backlog(self) -> dict:
        counts = {}
        for topic in TOPICS:
            counts[topic] = len(list((BUS_DIR / topic).glob("*.json")))
            counts[f"{topic}.dlq"] = len(list((BUS_DIR / f"{topic}.dlq").glob("*.json")))
        return counts


bus = FileBus()
