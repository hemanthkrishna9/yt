"""SQLite user store — one table, thread-safe."""

import sqlite3
import threading
from pathlib import Path

DB_PATH = Path("data/users.db")
_local = threading.local()


def _conn() -> sqlite3.Connection:
    """Return a per-thread connection."""
    if not hasattr(_local, "conn"):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH))
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db():
    conn = _conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        )"""
    )
    conn.commit()


def create_user(email: str, password_hash: str) -> int:
    """Insert user and return id. Raises sqlite3.IntegrityError on duplicate."""
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, password_hash),
    )
    conn.commit()
    return cur.lastrowid


def get_user_by_email(email: str) -> dict | None:
    row = _conn().execute(
        "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "email": row["email"], "password_hash": row["password_hash"]}
