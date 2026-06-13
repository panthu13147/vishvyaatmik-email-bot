"""
Lightweight SQLite store. Two jobs:

1. Idempotency -- remember every email we've already triaged (keyed by its
   Message-ID), so a flaky `\\Seen` flag can never cause a duplicate
   Discord post or a duplicate (quota-burning) AI call.

2. A running log of every triaged email -- the foundation for future
   features like a daily digest, "what did I miss today" queries, and
   eventually the voice-assistant layer.
"""

import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vishvyaatmik.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    message_id      TEXT PRIMARY KEY,
    sender          TEXT,
    subject         TEXT,
    category        TEXT,
    summary         TEXT,
    action_required TEXT,
    key_details     TEXT,
    provider        TEXT,
    processed_at    INTEGER
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as conn:
        conn.execute(SCHEMA)


def already_processed(message_id: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM emails WHERE message_id = ?", (message_id,)
        ).fetchone()
        return row is not None


def record_email(message_id, sender, subject, verdict):
    with _conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO emails
               (message_id, sender, subject, category, summary,
                action_required, key_details, provider, processed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id, sender, subject,
                verdict.get("category"), verdict.get("summary"),
                verdict.get("action_required"), verdict.get("key_details"),
                verdict.get("provider"), int(time.time()),
            ),
        )


def stats_since(timestamp: int) -> dict:
    """Returns {category: count} for everything processed since `timestamp`."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) FROM emails "
            "WHERE processed_at >= ? GROUP BY category",
            (timestamp,),
        ).fetchall()
        return dict(rows)
