from pathlib import Path
import pandas as pd
from hub.canonical import to_canonical


def test_canonical_schema():
    row = {
        "feed_id": "F-1",
        "source_system": "payments-core",
        "partner": "orbit-pay",
        "region": "NA",
        "channel": "api",
        "amount": 10.5,
        "currency": "USD",
        "status": "settled",
        "event_time": "2026-08-01T00:00:00Z",
        "correlation_id": "c-1",
    }
    out = to_canonical(row)
    assert out["schema"] == "canonical.feed"
    assert out["feedId"] == "F-1"
    assert out["money"]["amount"] == 10.5


def test_sample_csv_exists_and_wide():
    path = Path("spark-pipeline/data/sample_feeds.csv")
    df = pd.read_csv(path)
    assert len(df) >= 500
    assert {"feed_id", "source_system", "amount", "status"} <= set(df.columns)
