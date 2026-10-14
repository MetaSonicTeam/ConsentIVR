"""
Single-flight campaign lock, backed by the SQLite `job_locks` table.

Why: the background runner (jobs.py) runs campaigns in a thread, which is fine
for one process. But a production deployment with several Gunicorn/Waitress
workers would otherwise let two workers dial the SAME campaign at once ->
double calls. This lock makes a campaign claim atomic across processes: the
campaign_id is the table's primary key, so only one INSERT can win.

A holder refreshes `heartbeat_at` while it works. If a worker crashes and stops
heartbeating, the lock goes STALE after STALE_SECONDS and another worker may
reclaim it -- so a dead process never wedges a campaign forever.

No Redis, no extra process: the DB we already have is the coordination point.
"""

import logging
import os
import socket
import sqlite3

from db import execute, get_conn, query

log = logging.getLogger(__name__)

# A lock older than this (no heartbeat) is considered abandoned and reclaimable.
# Must comfortably exceed the per-recipient pacing gap so a live run is never
# mistaken for a dead one.
STALE_SECONDS = 120


def owner_id() -> str:
    """Identifies the process holding a lock (host:pid)."""
    return f"{socket.gethostname()}:{os.getpid()}"


def claim(campaign_id: int, owner: str) -> bool:
    """Atomically acquire the lock for `campaign_id`. Returns True on success,
    False if another live worker already holds it."""
    with get_conn() as conn:
        # Clear an abandoned lock first (stale heartbeat), then try to insert.
        conn.execute(
            "DELETE FROM job_locks WHERE campaign_id = ? "
            "AND heartbeat_at < datetime('now', ?)",
            (campaign_id, f"-{STALE_SECONDS} seconds"),
        )
        try:
            conn.execute(
                "INSERT INTO job_locks (campaign_id, locked_by, locked_at, heartbeat_at) "
                "VALUES (?, ?, datetime('now'), datetime('now'))",
                (campaign_id, owner),
            )
            return True
        except sqlite3.IntegrityError:
            # Another worker holds a live lock.
            return False


def heartbeat(campaign_id: int, owner: str) -> None:
    execute(
        "UPDATE job_locks SET heartbeat_at = datetime('now') "
        "WHERE campaign_id = ? AND locked_by = ?",
        (campaign_id, owner),
    )


def release(campaign_id: int, owner: str) -> None:
    execute(
        "DELETE FROM job_locks WHERE campaign_id = ? AND locked_by = ?",
        (campaign_id, owner),
    )


def is_locked(campaign_id: int) -> bool:
    """True if a live (non-stale) lock exists for this campaign."""
    row = query(
        "SELECT 1 FROM job_locks WHERE campaign_id = ? "
        "AND heartbeat_at >= datetime('now', ?) LIMIT 1",
        (campaign_id, f"-{STALE_SECONDS} seconds"),
        one=True,
    )
    return row is not None
