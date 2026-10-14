"""
Thin SQLite data-access layer for ConsentIVR.

Uses WAL mode and short-lived connections (safe under Flask's threaded dev
server and typical WSGI workers). Row access is dict-like via sqlite3.Row.
"""

import importlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import Config

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# SQLCipher driver, resolved lazily and cached: a module (truthy) if available,
# False if we've looked and found none. Only consulted when a key is configured.
_SQLCIPHER = None


def _sqlcipher_module():
    global _SQLCIPHER
    if _SQLCIPHER is not None:
        return _SQLCIPHER
    for name in ("sqlcipher3", "sqlcipher3.dbapi2", "pysqlcipher3.dbapi2"):
        try:
            _SQLCIPHER = importlib.import_module(name)
            return _SQLCIPHER
        except Exception:
            continue
    _SQLCIPHER = False
    return False


def _connect():
    key = Config.DB_ENCRYPTION_KEY
    if key:
        # Encryption requested: use SQLCipher, and FAIL LOUDLY if it's missing
        # rather than silently opening the database unencrypted.
        mod = _sqlcipher_module()
        if not mod:
            raise RuntimeError(
                "DB_ENCRYPTION_KEY is set but no SQLCipher driver is installed. "
                "Install one (e.g. `pip install sqlcipher3-binary`) or unset "
                "DB_ENCRYPTION_KEY to use an unencrypted database."
            )
        conn = mod.connect(Config.DB_PATH, timeout=15)
        conn.row_factory = getattr(mod, "Row", sqlite3.Row)
        # PRAGMA key must be the first statement on the connection. SQLCipher
        # takes no bound params here, so escape single quotes in the passphrase.
        conn.execute("PRAGMA key = '%s';" % key.replace("'", "''"))
    else:
        conn = sqlite3.connect(Config.DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def encryption_active() -> bool:
    """True if the DB is being opened with SQLCipher encryption."""
    return bool(Config.DB_ENCRYPTION_KEY)


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables from schema.sql if they do not exist, then run small
    additive migrations for columns added after a DB was first created."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate(conn)


def _migrate(conn):
    """Idempotent, additive migrations. SQLite's CREATE TABLE IF NOT EXISTS
    never adds columns to a pre-existing table, so new columns go here."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(campaigns)")}
    if "channel" not in cols:
        conn.execute(
            "ALTER TABLE campaigns ADD COLUMN channel TEXT NOT NULL DEFAULT 'voice'"
        )
    if "voice" not in cols:
        conn.execute("ALTER TABLE campaigns ADD COLUMN voice TEXT")
    if "amd_enabled" not in cols:
        conn.execute("ALTER TABLE campaigns ADD COLUMN amd_enabled INTEGER NOT NULL DEFAULT 1")
    if "agent_number" not in cols:
        conn.execute("ALTER TABLE campaigns ADD COLUMN agent_number TEXT")

    menu_cols = {r["name"] for r in conn.execute("PRAGMA table_info(ivr_menus)")}
    if "voice" not in menu_cols:
        conn.execute("ALTER TABLE ivr_menus ADD COLUMN voice TEXT")


def query(sql, params=(), one=False):
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=()):
    """Run a write and return lastrowid."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


# --- Convenience helpers used across the app -------------------------------

def audit(actor, action, target=None, detail=None):
    execute(
        "INSERT INTO audit_log (actor, action, target, detail) VALUES (?,?,?,?)",
        (actor, action, target, detail),
    )


def log_ivr_event(provider_sid, event, detail=None, call_id=None):
    execute(
        "INSERT INTO ivr_events (call_id, provider_sid, event, detail) VALUES (?,?,?,?)",
        (call_id, provider_sid, event, detail),
    )


def get_setting(key, default=None):
    row = query("SELECT value FROM settings WHERE key = ?", (key,), one=True)
    return row["value"] if row else default


def set_setting(key, value):
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
