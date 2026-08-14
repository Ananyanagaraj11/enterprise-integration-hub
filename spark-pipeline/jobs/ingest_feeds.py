"""Spark / pandas canonicalization, quality checks, and aggregations."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "spark-pipeline" / "data" / "sample_feeds.csv"
OUT_DIR = ROOT / "api" / "wwwroot" / "data"
HUB_DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))

from hub.canonical import to_canonical  # noqa: E402


def load_frame() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, keep_default_na=False)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["quality_flag"] = "ok"
    df.loc[df["amount"] <= 0, "quality_flag"] = "invalid_amount"
    df.loc[df["status"].isna(), "quality_flag"] = "missing_status"
    return df


def run_pandas() -> dict:
    df = load_frame()
    records = [to_canonical(r._asdict() if hasattr(r, "_asdict") else r) for r in df.to_dict(orient="records")]
    summary = {
        "feedCount": int(len(df)),
        "totalAmount": round(float(df["amount"].sum()), 2),
        "byStatus": df["status"].value_counts().to_dict(),
        "bySource": df["source_system"].value_counts().to_dict(),
        "amountByRegion": {k: round(v, 2) for k, v in df.groupby("region")["amount"].sum().to_dict().items()},
        "byChannel": df["channel"].value_counts().to_dict(),
        "byPartner": df["partner"].value_counts().to_dict() if "partner" in df.columns else {},
        "quality": df["quality_flag"].value_counts().to_dict(),
        "engine": "pandas",
        "schema": "canonical.feed/1.0",
    }
    return {"records": records, "summary": summary, "raw_count": len(df)}


def run_spark() -> dict:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = SparkSession.builder.master("local[*]").appName("hub-canonical-ingest").getOrCreate()
    df = spark.read.option("header", True).option("inferSchema", True).csv(str(CSV_PATH))
    df = df.withColumn("amount", F.col("amount").cast("double"))
    _ = df.groupBy("region").agg(F.sum("amount").alias("total")).collect()
    spark.stop()
    out = run_pandas()
    out["summary"]["engine"] = "pyspark"
    return out


def flatten(canonical: dict) -> dict:
    return {
        "feedId": canonical["feedId"],
        "sourceSystem": canonical["source"]["system"],
        "partner": canonical["source"]["partner"],
        "region": canonical["geo"]["region"],
        "channel": canonical["source"]["channel"],
        "amount": canonical["money"]["amount"],
        "status": canonical["lifecycle"]["status"],
        "eventTime": canonical["trace"]["eventTime"],
        "correlationId": canonical["trace"]["correlationId"],
    }


def write_outputs(result: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HUB_DATA.mkdir(parents=True, exist_ok=True)
    flat = [flatten(r) for r in result["records"]]
    (OUT_DIR / "feeds.json").write_text(json.dumps(flat, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(result["summary"], indent=2), encoding="utf-8")
    (HUB_DATA / "canonical_feeds.json").write_text(json.dumps(result["records"], indent=2), encoding="utf-8")
    print(f"Wrote {len(result['records'])} canonical feeds")


def main() -> None:
    if "--pandas" in sys.argv:
        result = run_pandas()
    else:
        try:
            result = run_spark()
        except Exception as exc:  # noqa: BLE001
            print(f"PySpark unavailable ({exc}). Falling back to pandas.")
            result = run_pandas()
    write_outputs(result)


if __name__ == "__main__":
    main()
