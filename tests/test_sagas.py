from hub.db import init_db
from hub.sagas import start_saga


def test_happy_path_saga():
    init_db()
    result = start_saga(
        {
            "feed_id": "F-saga-1",
            "source_system": "payments-core",
            "partner": "orbit-pay",
            "region": "EU",
            "channel": "api",
            "amount": 99.0,
            "currency": "EUR",
            "status": "settled",
            "event_time": "2026-08-01T00:00:00Z",
            "correlation_id": "c-saga",
        }
    )
    assert result["state"] == "completed"
    assert result["canonical"]["feedId"] == "F-saga-1"


def test_saga_compensates_on_invalid_amount():
    init_db()
    result = start_saga({"feed_id": "F-bad", "source_system": "x", "amount": -1, "status": "pending"})
    assert result["state"] == "failed"
