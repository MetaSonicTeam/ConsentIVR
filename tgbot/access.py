"""
Telegram operator allowlist + role resolution.

The bot is an operator surface, so identity and authorization are explicit:

  * Bootstrap admins come from TELEGRAM_ADMIN_IDS (env). They are ALWAYS admins
    and are auto-provisioned into telegram_users on first contact, so they never
    lock themselves out by forgetting to add their own row.
  * Everyone else must have an active telegram_users row (added by an admin
    in-chat, by tg_authorize.py, or by a completed paid-access grant).
  * A paid grant can carry an expiry; expired rows resolve to "no access" and
    are deactivated on sight.

Roles (same as the dashboard): admin > operator > viewer.
"""

import logging
from datetime import datetime, timedelta, timezone

from config import Config
from db import audit, execute, query

log = logging.getLogger(__name__)

ROLES = ("admin", "operator", "viewer")
_RANK = {"viewer": 1, "operator": 2, "admin": 3}


def role_rank(role: str) -> int:
    return _RANK.get(role or "", 0)


def has_at_least(role: str, minimum: str) -> bool:
    return role_rank(role) >= role_rank(minimum)


def _now():
    return datetime.now(timezone.utc)


def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def get_user(tg_user_id: int):
    return query("SELECT * FROM telegram_users WHERE tg_user_id = ?", (tg_user_id,), one=True)


def resolve(tg_user_id: int, username: str = None):
    """Return (role, locale) for a user, or (None, default_locale) if they have
    no access. Keeps the stored @username fresh and self-provisions env admins.
    Expired paid grants are deactivated here."""
    default_locale = Config.TELEGRAM_DEFAULT_LOCALE or "en"

    if tg_user_id in Config.telegram_admin_ids():
        row = get_user(tg_user_id)
        if not row:
            execute(
                "INSERT INTO telegram_users (tg_user_id, username, role, locale, added_by) "
                "VALUES (?,?,'admin',?, 'env')",
                (tg_user_id, username, default_locale),
            )
            return "admin", default_locale
        # Ensure the env admin stays admin+active even if a row was downgraded.
        if row["role"] != "admin" or not row["active"]:
            execute("UPDATE telegram_users SET role='admin', active=1 WHERE tg_user_id=?", (tg_user_id,))
        if username and username != row["username"]:
            execute("UPDATE telegram_users SET username=? WHERE tg_user_id=?", (username, tg_user_id))
        return "admin", row["locale"] or default_locale

    row = get_user(tg_user_id)
    if not row or not row["active"]:
        return None, default_locale

    expiry = _parse_dt(row["access_expires_at"])
    if expiry and expiry < _now():
        execute("UPDATE telegram_users SET active=0 WHERE tg_user_id=?", (tg_user_id,))
        audit("system", "tg_access_expired", str(tg_user_id))
        return None, row["locale"] or default_locale

    if username and username != row["username"]:
        execute("UPDATE telegram_users SET username=? WHERE tg_user_id=?", (username, tg_user_id))
    return row["role"], row["locale"] or default_locale


def set_locale(tg_user_id: int, locale: str):
    execute("UPDATE telegram_users SET locale=? WHERE tg_user_id=?", (locale, tg_user_id))


def authorize(tg_user_id: int, role: str, added_by: str, days: int = 0,
              username: str = None) -> bool:
    """Add or update an operator. Returns False for an invalid role."""
    if role not in ROLES:
        return False
    expires = None
    if days and days > 0:
        expires = (_now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    execute(
        "INSERT INTO telegram_users (tg_user_id, username, role, locale, active, access_expires_at, added_by) "
        "VALUES (?,?,?,?,1,?,?) "
        "ON CONFLICT(tg_user_id) DO UPDATE SET role=excluded.role, active=1, "
        "access_expires_at=excluded.access_expires_at, added_by=excluded.added_by, "
        "username=COALESCE(excluded.username, telegram_users.username)",
        (tg_user_id, username, role, Config.TELEGRAM_DEFAULT_LOCALE or "en", expires, added_by),
    )
    audit(added_by, "tg_authorize", str(tg_user_id), f"role={role} days={days or 'inf'}")
    return True


def revoke(tg_user_id: int, actor: str):
    execute("UPDATE telegram_users SET active=0 WHERE tg_user_id=?", (tg_user_id,))
    audit(actor, "tg_revoke", str(tg_user_id))


def list_users():
    """All non-env operators (env admins are implicit and may not have a row)."""
    return query(
        "SELECT * FROM telegram_users ORDER BY active DESC, role DESC, tg_user_id"
    )
