from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.environ.get("HUB_DB", DATA_DIR / "hub.sqlite"))
JWT_SECRET = os.environ.get("HUB_JWT_SECRET", "hub-dev-secret-change-me-32chars!!")
JWT_ALG = "HS256"

_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _lock:
        conn = connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS feeds (
                feed_id TEXT PRIMARY KEY,
                source_system TEXT NOT NULL,
                partner TEXT,
                region TEXT,
                channel TEXT,
                amount REAL,
                currency TEXT,
                status TEXT,
                event_time TEXT,
                correlation_id TEXT,
                canonical_json TEXT,
                ingested_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                headers TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                published_at TEXT,
                attempts INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS inbox (
                event_id TEXT PRIMARY KEY,
                topic TEXT,
                payload TEXT,
                received_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS dlq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                payload TEXT,
                error TEXT,
                failed_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT PRIMARY KEY,
                request_hash TEXT,
                response_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                event_type TEXT,
                payload TEXT,
                status TEXT,
                received_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sagas (
                saga_id TEXT PRIMARY KEY,
                name TEXT,
                state TEXT,
                context TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT,
                action TEXT,
                detail TEXT,
                at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                owner TEXT,
                scopes TEXT
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO api_keys(key, owner, scopes) VALUES (?,?,?)",
            ("hub_live_demo_key", "dashboard", "feeds:read,feeds:write,webhooks:write"),
        )
        conn.commit()
        conn.close()
