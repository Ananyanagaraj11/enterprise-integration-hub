from fastapi.testclient import TestClient

from hub.app import app
from hub.db import init_db


def test_login_and_system_ingest():
    init_db()
    client = TestClient(app)
    token = client.post("/auth/login", json={"username": "ananya", "password": "hub-demo"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "demo-1"}
    res = client.post(
        "/system/v1/feeds",
        json={
            "feed_id": "F-api-1",
            "source_system": "payments-core",
            "partner": "orbit-pay",
            "region": "NA",
            "channel": "api",
            "amount": 12.34,
            "currency": "USD",
            "status": "settled",
            "event_time": "2026-08-01T00:00:00Z",
            "correlation_id": "c-api",
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["state"] == "completed"
    replay = client.post(
        "/system/v1/feeds",
        json={
            "feed_id": "F-api-1",
            "source_system": "payments-core",
            "partner": "orbit-pay",
            "region": "NA",
            "channel": "api",
            "amount": 12.34,
            "currency": "USD",
            "status": "settled",
            "event_time": "2026-08-01T00:00:00Z",
            "correlation_id": "c-api",
        },
        headers=headers,
    )
    assert replay.json()["sagaId"] == res.json()["sagaId"]
