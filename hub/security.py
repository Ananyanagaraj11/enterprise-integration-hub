from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Header, HTTPException

from hub.db import JWT_ALG, JWT_SECRET, connect

USERS = {
    "ananya": {"password": "hub-demo", "role": "engineer"},
    "recruiter": {"password": "interview", "role": "reader"},
}


def issue_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": username, "role": role, "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=8)).timestamp())},
        JWT_SECRET,
        algorithm=JWT_ALG,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc


def require_auth(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)) -> dict:
    if x_api_key:
        conn = connect()
        row = conn.execute("SELECT owner, scopes FROM api_keys WHERE key=?", (x_api_key,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=401, detail="invalid api key")
        return {"sub": row["owner"], "role": "api-key", "scopes": row["scopes"]}
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token or x-api-key")
    return decode_token(authorization.split(" ", 1)[1])


class TokenBucket:
    def __init__(self, rate: int = 30, per_seconds: int = 10) -> None:
        self.rate = rate
        self.per = per_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > self.per:
            q.popleft()
        if len(q) >= self.rate:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        q.append(now)


limiter = TokenBucket()


def idempotency_lookup(key: str | None, body: Any) -> dict | None:
    if not key:
        return None
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    conn = connect()
    row = conn.execute(
        "SELECT request_hash, response_json FROM idempotency_keys WHERE key=?", (key,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    if row["request_hash"] != digest:
        raise HTTPException(status_code=409, detail="idempotency key reused with different body")
    return json.loads(row["response_json"])


def idempotency_store(key: str | None, body: Any, response: dict) -> None:
    if not key:
        return
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO idempotency_keys(key, request_hash, response_json) VALUES (?,?,?)",
        (key, digest, json.dumps(response)),
    )
    conn.commit()
    conn.close()
