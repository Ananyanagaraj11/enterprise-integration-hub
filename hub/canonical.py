"""Canonical data model + message translator (EIP)."""
from __future__ import annotations

from typing import Any


CANONICAL_VERSION = "1.0"


def to_canonical(row: dict[str, Any]) -> dict[str, Any]:
    amount = float(row.get("amount") or 0)
    status = str(row.get("status") or "unknown").lower()
    return {
        "schema": "canonical.feed",
        "schemaVersion": CANONICAL_VERSION,
        "feedId": row.get("feed_id") or row.get("feedId"),
        "source": {
            "system": row.get("source_system") or row.get("sourceSystem"),
            "partner": row.get("partner"),
            "channel": row.get("channel"),
        },
        "geo": {"region": row.get("region")},
        "money": {
            "amount": round(amount, 2),
            "currency": row.get("currency") or "USD",
        },
        "lifecycle": {"status": status},
        "trace": {
            "correlationId": row.get("correlation_id") or row.get("correlationId"),
            "eventTime": row.get("event_time") or row.get("eventTime"),
        },
    }


def content_based_route(canonical: dict[str, Any]) -> str:
    status = canonical["lifecycle"]["status"]
    amount = canonical["money"]["amount"]
    if status == "failed":
        return "feeds.failed"
    if amount >= 50000:
        return "feeds.canonicalized"
    return "feeds.ingested"
