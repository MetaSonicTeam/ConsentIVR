"""
Tiny per-chat conversation state for multi-step flows.

Some actions need a follow-up text message from the operator (the phone number
to opt out, the recipients to add, the forward-to number, ...). We stash "what
we're waiting for" keyed by chat id. It's an in-memory dict guarded by a lock —
fine for a single long-poll process, which is how the bot runs. If you scale to
multiple bot processes, move this to the DB.

State is intentionally short-lived: any button tap or /command clears it, so a
half-finished flow never traps the operator.
"""

import threading
import time

_lock = threading.Lock()
_pending = {}  # chat_id -> {"action": str, "data": dict, "ts": float}

TTL = 600  # seconds; a stale prompt is dropped


def set_pending(chat_id, action, **data):
    with _lock:
        _pending[chat_id] = {"action": action, "data": data, "ts": time.time()}


def get_pending(chat_id):
    with _lock:
        item = _pending.get(chat_id)
        if not item:
            return None, {}
        if time.time() - item["ts"] > TTL:
            _pending.pop(chat_id, None)
            return None, {}
        return item["action"], item["data"]


def clear(chat_id):
    with _lock:
        _pending.pop(chat_id, None)
