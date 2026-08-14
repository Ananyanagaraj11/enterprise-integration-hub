from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from hub import __version__
from hub.bus import bus
from hub.canonical import to_canonical
from hub.db import DATA_DIR, ROOT, connect, init_db
from hub.sagas import start_saga
from hub.security import USERS, idempotency_lookup, idempotency_store, issue_token, limiter, require_auth
from hub.seed import load_canonical_csv, seed_if_empty

init_db()
seed_if_empty()
app = FastAPI(
    title="Enterprise Integration Hub",
    version=__version__,
    description="API-led integration platform: System / Process / Experience APIs, JWT, webhooks, sagas, DLQ.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginBody(BaseModel):
    username: str
    password: str


class FeedIn(BaseModel):
    feed_id: str
    source_system: str
    partner: str | None = None
    region: str | None = None
    channel: str | None = "api"
    amount: float
    currency: str = "USD"
    status: str = "pending"
    event_time: str | None = None
    correlation_id: str | None = None


class WebhookIn(BaseModel):
    source: str
    event_type: str = "feed.updated"
    payload: dict = Field(default_factory=dict)


@app.middleware("http")
async def rate_and_metrics(request: Request, call_next):
    client = request.client.host if request.client else "anon"
    if request.url.path not in ("/health", "/metrics", "/docs", "/openapi.json"):
        limiter.check(client)
    response = await call_next(request)
    response.headers["X-Hub-Version"] = __version__
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "process-api", "version": __version__, "bus": bus.backlog()}


@app.get("/metrics")
def metrics():
    conn = connect()
    feeds = conn.execute("SELECT COUNT(*) c FROM feeds").fetchone()["c"]
    dlq = conn.execute("SELECT COUNT(*) c FROM dlq").fetchone()["c"]
    sagas = conn.execute("SELECT COUNT(*) c FROM sagas").fetchone()["c"]
    conn.close()
    body = "\n".join(
        [
            "# HELP hub_feeds_total Canonical feeds stored",
            "# TYPE hub_feeds_total gauge",
            f"hub_feeds_total {feeds}",
            "# HELP hub_dlq_total Dead-letter messages",
            "# TYPE hub_dlq_total gauge",
            f"hub_dlq_total {dlq}",
            "# HELP hub_sagas_total Saga instances",
            "# TYPE hub_sagas_total gauge",
            f"hub_sagas_total {sagas}",
        ]
    )
    return JSONResponse(content=body, media_type="text/plain")


@app.post("/auth/login")
def login(body: LoginBody):
    user = USERS.get(body.username)
    if not user or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = issue_token(body.username, user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.post("/system/v1/feeds")
def system_ingest(
    body: FeedIn,
    principal: dict = Depends(require_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    cached = idempotency_lookup(idempotency_key, body.model_dump())
    if cached:
        return cached
    result = start_saga(body.model_dump())
    idempotency_store(idempotency_key, body.model_dump(), result)
    _audit(principal["sub"], "system.ingest", body.feed_id)
    return result


@app.post("/process/v1/feeds/batch")
def process_batch(principal: dict = Depends(require_auth)):
    result = load_canonical_csv()
    _audit(principal["sub"], "process.batch", f"{result['ingested']}/{result['failed']}")
    return result


@app.post("/process/v1/webhooks")
def webhook(body: WebhookIn, principal: dict = Depends(require_auth)):
    conn = connect()
    conn.execute(
        "INSERT INTO webhooks(source, event_type, payload, status) VALUES (?,?,?,?)",
        (body.source, body.event_type, json.dumps(body.payload), "accepted"),
    )
    conn.commit()
    conn.close()
    bus.publish("webhooks.received", body.model_dump(), key=body.source)
    if "feed_id" in body.payload or "feedId" in body.payload:
        start_saga({**body.payload, "source_system": body.source, "channel": "webhook"})
    _audit(principal["sub"], "webhook", body.event_type)
    return {"status": "accepted"}


@app.post("/process/v1/events/drain")
def drain(principal: dict = Depends(require_auth)):
    total = 0
    for topic in ("feeds.ingested", "feeds.canonicalized", "feeds.failed", "webhooks.received"):
        total += bus.consume(topic, lambda env: None)
    return {"processed": total, "backlog": bus.backlog()}


@app.get("/experience/v1/feeds")
def experience_feeds(
    status: str | None = None,
    source: str | None = None,
    region: str | None = None,
    limit: int = 100,
    principal: dict = Depends(require_auth),
):
    sql = "SELECT * FROM feeds WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status=?"
        args.append(status)
    if source:
        sql += " AND source_system=?"
        args.append(source)
    if region:
        sql += " AND region=?"
        args.append(region)
    sql += " ORDER BY event_time DESC LIMIT ?"
    args.append(min(limit, 500))
    conn = connect()
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    return rows


@app.get("/experience/v1/summary")
def experience_summary(principal: dict = Depends(require_auth)):
    conn = connect()
    total = conn.execute("SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM feeds").fetchone()
    by_status = {r["status"]: r["c"] for r in conn.execute("SELECT status, COUNT(*) c FROM feeds GROUP BY status")}
    by_source = {r["source_system"]: r["c"] for r in conn.execute("SELECT source_system, COUNT(*) c FROM feeds GROUP BY source_system")}
    by_region = {r["region"]: round(r["s"], 2) for r in conn.execute("SELECT region, SUM(amount) s FROM feeds GROUP BY region")}
    sagas = [dict(r) for r in conn.execute("SELECT saga_id, state, updated_at FROM sagas ORDER BY updated_at DESC LIMIT 20")]
    dlq = [dict(r) for r in conn.execute("SELECT id, topic, error, failed_at FROM dlq ORDER BY id DESC LIMIT 20")]
    conn.close()
    return {
        "feedCount": total["c"],
        "totalAmount": round(total["s"], 2),
        "byStatus": by_status,
        "bySource": by_source,
        "amountByRegion": by_region,
        "bus": bus.backlog(),
        "recentSagas": sagas,
        "dlq": dlq,
        "engine": "sqlite+file-bus",
    }


@app.get("/experience/v1/graphql")
def graphql_shim(query: str = "feeds", principal: dict = Depends(require_auth)):
    """Minimal GraphQL-style query surface for JD keyword coverage."""
    if "dlq" in query:
        conn = connect()
        rows = [dict(r) for r in conn.execute("SELECT * FROM dlq ORDER BY id DESC LIMIT 50")]
        conn.close()
        return {"data": {"dlq": rows}}
    conn = connect()
    rows = [dict(r) for r in conn.execute("SELECT feed_id, status, amount, region FROM feeds LIMIT 50")]
    conn.close()
    return {"data": {"feeds": rows}}


@app.get("/experience/v1/canonical/{feed_id}")
def canonical(feed_id: str, principal: dict = Depends(require_auth)):
    conn = connect()
    row = conn.execute("SELECT canonical_json FROM feeds WHERE feed_id=?", (feed_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="feed not found")
    return json.loads(row["canonical_json"])


def _audit(actor: str, action: str, detail: str) -> None:
    conn = connect()
    conn.execute("INSERT INTO audit(actor, action, detail) VALUES (?,?,?)", (actor, action, detail))
    conn.commit()
    conn.close()


dash = ROOT / "dashboard"
if dash.exists():
    app.mount("/", StaticFiles(directory=dash, html=True), name="dashboard")
