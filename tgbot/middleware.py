"""
Middleware pipeline wrapped around every update.

Each middleware has the signature (ctx, nxt) and either calls nxt() to pass
control down the chain or short-circuits (e.g. an unauthorized user never
reaches a handler). The chain, outermost first:

    error      -> catch/kill exceptions so one bad update never stops the loop
    resolve    -> attach role + locale (so even denials are localized)
    rate_limit -> per-user flood guard
    authorize  -> allowlist gate; unauthorized users get the paid-access flow
    (handler)  -> handlers.dispatch

This mirrors the dashboard's login_required / role_required decorators, but as
a composable chain because a chat update has several shapes (command, button,
payment) that all need the same gate.
"""

import logging
import threading
import time

from config import Config
from db import audit
from . import access

log = logging.getLogger(__name__)


# --- per-user flood guard -------------------------------------------------
_rl_lock = threading.Lock()
_rl_hits = {}  # user_id -> [timestamps within window]
_RL_WINDOW = 10.0


def _rate_ok(user_id) -> bool:
    limit = Config.TELEGRAM_RATE_LIMIT or 20
    now = time.time()
    with _rl_lock:
        hits = [t for t in _rl_hits.get(user_id, []) if now - t < _RL_WINDOW]
        if len(hits) >= limit:
            _rl_hits[user_id] = hits
            return False
        hits.append(now)
        _rl_hits[user_id] = hits
        return True


# --- middlewares ----------------------------------------------------------

def mw_error(ctx, nxt):
    try:
        nxt()
    except Exception:
        log.exception("Unhandled error in update (user=%s, kind=%s)", ctx.user_id, ctx.kind)
        try:
            if ctx.callback_id:
                ctx.answer(ctx.t("error_generic"))
            elif ctx.chat_id:
                ctx.reply(ctx.t("error_generic"))
        except Exception:
            pass


def mw_resolve(ctx, nxt):
    if ctx.user_id is None:
        return  # nothing we can authorize (e.g. channel post) — drop it
    role, locale = access.resolve(ctx.user_id, ctx.username)
    ctx.role = role
    ctx.locale = locale or "en"
    nxt()


def mw_rate_limit(ctx, nxt):
    # Never rate-limit the pre-checkout step — it must be answered in 10s.
    if ctx.kind == "precheckout":
        return nxt()
    if not _rate_ok(ctx.user_id):
        if ctx.callback_id:
            ctx.answer(ctx.t("rate_limited"), alert=True)
        return
    nxt()


def mw_authorize(ctx, nxt):
    if ctx.role is None:
        # Unauthorized: the only things they can do are the paid-access flow.
        from . import handlers
        handlers.unauthorized(ctx)
        return
    nxt()


def _compose(middlewares, terminal):
    def runner(ctx):
        idx = -1

        def nxt():
            nonlocal idx
            idx += 1
            if idx < len(middlewares):
                middlewares[idx](ctx, nxt)
            else:
                terminal(ctx)
        nxt()
    return runner


def build(terminal):
    """Return a callable(ctx) that runs the full chain ending in `terminal`."""
    return _compose([mw_error, mw_resolve, mw_rate_limit, mw_authorize], terminal)


# --- audit helper (used by handlers) -------------------------------------

def record(ctx, action, target=None, detail=None):
    """Audit a state-changing action by a Telegram operator, tagged so it's
    distinguishable from dashboard actions in the audit log."""
    actor = f"tg:{ctx.user_id}" + (f" (@{ctx.username})" if ctx.username else "")
    audit(actor, action, target, detail)
