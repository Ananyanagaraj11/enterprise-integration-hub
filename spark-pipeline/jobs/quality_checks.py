"""Data quality rules for inbound feeds (completeness, range, referential)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "spark-pipeline" / "data" / "sample_feeds.csv"
OUT = ROOT / "data" / "quality_report.json"

ALLOWED_STATUS = {"settled", "pending", "failed", "retrying"}
ALLOWED_REGION = {"AMER", "EU", "APAC", "LATAM"}


def main() -> None:
    df = pd.read_csv(CSV_PATH, keep_default_na=False)
    issues = []
    dupes = df[df.duplicated("feed_id", keep=False)]
    if not dupes.empty:
        issues.append({"rule": "unique_feed_id", "count": int(len(dupes))})
    missing = df[df[["feed_id", "source_system", "amount", "status"]].isna().any(axis=1)]
    if not missing.empty:
        issues.append({"rule": "required_fields", "count": int(len(missing))})
    bad_status = df[~df["status"].isin(ALLOWED_STATUS)]
    if not bad_status.empty:
        issues.append({"rule": "status_domain", "count": int(len(bad_status))})
    bad_region = df[~df["region"].isin(ALLOWED_REGION)]
    if not bad_region.empty:
        issues.append({"rule": "region_domain", "count": int(len(bad_region))})
    negative = df[pd.to_numeric(df["amount"], errors="coerce") < 0]
    if not negative.empty:
        issues.append({"rule": "amount_non_negative", "count": int(len(negative))})
    report = {
        "rows": int(len(df)),
        "passed": len(issues) == 0,
        "issues": issues,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
