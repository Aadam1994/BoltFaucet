"""
Thin async wrapper around SQLite Database.
"""
from __future__ import annotations
import json
import sqlite3
import time
from datetime import date, timezone
from typing import Any
from pathlib import Path

DB_PATH = Path("faucet.db")

def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _init():
    with _conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)")
_init()

def _get(key: str, default: Any = None) -> Any:
    with _conn() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key =?", (key,)).fetchone()
    if row is None:
        return default
    raw = row[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw

def _set(key: str, value: Any) -> None:
    val = json.dumps(value) if not isinstance(value, str) else value
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?,?)", (key, val))

def _del(key: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM kv WHERE key =?", (key,))

def _keys(prefix: str):
    with _conn() as conn:
        rows = conn.execute("SELECT key FROM kv WHERE key LIKE?", (f"{prefix}%",)).fetchall()
    return [r[0] for r in rows]
