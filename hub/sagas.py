"""Orchestration saga: ingest → canonicalize → enrich → persist → notify."""
from __future__ import annotations

import json
import uuid
from typing import Any

from hub.bus import bus
from hub.canonical import content_based_route, to_canonical
from hub.db import connect


STEPS = ("validate", "canonicalize", "route", "persist", "notify")


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, threshold: int = 5) -> None:
        self.threshold = threshold
        self.failures = 0
        self.open = False

    def record_success(self) -> None:
        self.failures = 0
        self.open = False

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open = True

    def guard(self) -> None:
        if self.open:
            raise CircuitOpen("circuit open: downstream unavailable")


notify_breaker = CircuitBreaker()


def start_saga(feed: dict[str, Any]) -> dict[str, Any]:
    saga_id = str(uuid.uuid4())
    context = {"feed": feed, "completed": []}
    _save(saga_id, "started", context)
    return run_saga(saga_id, context)


def run_saga(saga_id: str, context: dict[str, Any]) -> dict[str, Any]:
    feed = context["feed"]
    try:
        _step(context, "validate", lambda: _validate(feed))
        canonical = _step(context, "canonicalize", lambda: to_canonical(feed))
        context["canonical"] = canonical
        topic = _step(context, "route", lambda: content_based_route(canonical))
        context["topic"] = topic
        _step(context, "persist", lambda: _persist(canonical))
        _step(context, "notify", lambda: _notify(canonical, topic))
        _save(saga_id, "completed", context)
        return {"sagaId": saga_id, "state": "completed", "topic": topic, "canonical": canonical}
    except Exception as exc:  # noqa: BLE001
        context["error"] = str(exc)
        _save(saga_id, "compensating", context)
        _compensate(context)
        _save(saga_id, "failed", context)
        return {"sagaId": saga_id, "state": "failed", "error": str(exc)}


def _step(context: dict, name: str, fn):
    result = fn()
    context["completed"].append(name)
    return result


def _validate(feed: dict) -> None:
    if not feed.get("feed_id") and not feed.get("feedId"):
        raise ValueError("feed_id required")
    amount = float(feed.get("amount") or 0)
    if amount < 0:
        raise ValueError("amount cannot be negative")


def _persist(canonical: dict) -> None:
    conn = connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO feeds(
            feed_id, source_system, partner, region, channel, amount, currency, status,
            event_time, correlation_id, canonical_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            canonical["feedId"],
            canonical["source"]["system"],
            canonical["source"]["partner"],
            canonical["geo"]["region"],
            canonical["source"]["channel"],
            canonical["money"]["amount"],
            canonical["money"]["currency"],
            canonical["lifecycle"]["status"],
            canonical["trace"]["eventTime"],
            canonical["trace"]["correlationId"],
            json.dumps(canonical),
        ),
    )
    conn.commit()
    conn.close()


def _notify(canonical: dict, topic: str) -> None:
    notify_breaker.guard()
    bus.publish(topic, canonical, key=canonical["feedId"])
    notify_breaker.record_success()


def _compensate(context: dict) -> None:
    feed_id = (context.get("canonical") or context.get("feed") or {}).get("feedId") or context.get("feed", {}).get("feed_id")
    if feed_id:
        conn = connect()
        conn.execute("DELETE FROM feeds WHERE feed_id=?", (feed_id,))
        conn.commit()
        conn.close()
    bus.publish("feeds.failed", {"compensation": True, "context": {"completed": context.get("completed"), "error": context.get("error")}})


def _save(saga_id: str, state: str, context: dict) -> None:
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO sagas(saga_id, name, state, context, updated_at) VALUES (?,?,?,?,datetime('now'))",
        (saga_id, "feed-ingest", state, json.dumps(context, default=str)),
    )
    conn.commit()
    conn.close()
