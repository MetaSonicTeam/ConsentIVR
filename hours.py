"""
Business-hours evaluation. Used to gate inbound (after-hours message) and,
later, to keep outbound campaigns inside legal/polite calling windows.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from config import Config
from db import query


def _parse_hhmm(value):
    if not value:
        return None
    h, m = value.split(":")
    return time(int(h), int(m))


def now_local():
    try:
        return datetime.now(ZoneInfo(Config.TIMEZONE))
    except Exception:
        return datetime.now()


def is_open(at: datetime = None, default_when_unset: bool = True) -> bool:
    """True if the org is within configured business hours.

    `default_when_unset` controls the answer when NO business_hours rows exist:
      * Inbound uses the default (True) so callers are never blocked by a
        missing config.
      * Outbound MUST pass default_when_unset=False so an unconfigured calling
        window fails CLOSED -- never auto-dial at arbitrary hours (a calling-
        time compliance risk)."""
    at = at or now_local()
    dow = at.weekday()  # 0=Monday
    rows = query("SELECT dow, open_time, close_time, enabled FROM business_hours")
    if not rows:
        return default_when_unset
    row = next((r for r in rows if r["dow"] == dow), None)
    if row is None or not row["enabled"]:
        return False
    open_t = _parse_hhmm(row["open_time"])
    close_t = _parse_hhmm(row["close_time"])
    if open_t is None or close_t is None:
        return False
    return open_t <= at.time() <= close_t
