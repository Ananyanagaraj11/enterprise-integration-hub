from __future__ import annotations

import csv
import json

from hub.bus import bus
from hub.canonical import to_canonical
from hub.db import ROOT, connect, init_db


def feed_count() -> int:
    conn = connect()
    n = conn.execute("SELECT COUNT(*) c FROM feeds").fetchone()["c"]
    conn.close()
    return int(n)


def load_canonical_csv() -> dict:
    csv_path = ROOT / "spark-pipeline" / "data" / "sample_feeds.csv"
    ingested = 0
    failed = 0
    conn = connect()
    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                canonical = to_canonical(row)
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
                ingested += 1
            except Exception:
                failed += 1
    conn.commit()
    conn.close()
    bus.publish("feeds.ingested", {"batch": True, "ingested": ingested, "failed": failed}, key="batch")
    return {"ingested": ingested, "failed": failed, "pattern": "canonical-load + single batch event"}


def seed_if_empty() -> dict | None:
    init_db()
    if feed_count() >= 50:
        return None
    return load_canonical_csv()
