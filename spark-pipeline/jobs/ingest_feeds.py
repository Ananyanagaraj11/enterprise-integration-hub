"""Ingest sample feeds, aggregate by source/region/status, write JSON for the API.

Uses PySpark when available; falls back to pandas so the demo still runs locally.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "sample_feeds.csv"
OUT_DIR = ROOT.parent / "api" / "wwwroot" / "data"


def write_outputs(records: list[dict], summary: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "feeds.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} feeds -> {OUT_DIR / 'feeds.json'}")
    print(f"Wrote summary -> {OUT_DIR / 'summary.json'}")


def summarize(records: list[dict]) -> dict:
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_region: dict[str, float] = {}
    total = 0.0
    for row in records:
        src = row["sourceSystem"]
        by_source[src] = by_source.get(src, 0) + 1
        st = row["status"]
        by_status[st] = by_status.get(st, 0) + 1
        amt = float(row["amount"])
        total += amt
        region = row["region"]
        by_region[region] = round(by_region.get(region, 0.0) + amt, 2)
    return {
        "feedCount": len(records),
        "totalAmount": round(total, 2),
        "bySource": by_source,
        "byStatus": by_status,
        "amountByRegion": by_region,
        "engine": "pyspark" if "pyspark" in sys.modules else "pandas",
    }


def run_pandas() -> tuple[list[dict], dict]:
    import pandas as pd

    df = pd.read_csv(CSV_PATH)
    records = [
        {
            "feedId": row.feed_id,
            "sourceSystem": row.source_system,
            "region": row.region,
            "channel": row.channel,
            "amount": round(float(row.amount), 2),
            "status": row.status,
            "eventTime": row.event_time,
        }
        for row in df.itertuples(index=False)
    ]
    return records, summarize(records)


def run_spark() -> tuple[list[dict], dict]:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = (
        SparkSession.builder.master("local[*]")
        .appName("integration-hub-feed-ingest")
        .getOrCreate()
    )
    df = spark.read.option("header", True).option("inferSchema", True).csv(str(CSV_PATH))
    mapped = df.select(
        F.col("feed_id").alias("feedId"),
        F.col("source_system").alias("sourceSystem"),
        F.col("region"),
        F.col("channel"),
        F.col("amount").cast("double").alias("amount"),
        F.col("status"),
        F.col("event_time").alias("eventTime"),
    )
    records = [row.asDict(recursive=True) for row in mapped.collect()]
    for row in records:
        row["amount"] = round(float(row["amount"]), 2)
    spark.stop()
    summary = summarize(records)
    summary["engine"] = "pyspark"
    return records, summary


def main() -> None:
    use_spark = "--pandas" not in sys.argv
    if use_spark:
        try:
            records, summary = run_spark()
        except Exception as exc:  # noqa: BLE001 — demo fallback
            print(f"PySpark unavailable ({exc}). Falling back to pandas.")
            records, summary = run_pandas()
    else:
        records, summary = run_pandas()
    write_outputs(records, summary)


if __name__ == "__main__":
    main()
