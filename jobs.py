"""
In-process background runner for outbound campaigns.

Campaign dialing is paced (a few seconds per recipient) and makes blocking
provider calls, so running it inside a web request would tie up a worker for
minutes and time out. This runs each campaign in a daemon thread instead; the
dashboard enqueues and returns immediately, and progress is visible by
refreshing the campaign page.

Why a thread (not Celery/RQ): zero extra dependencies, works identically on
Windows and Linux, and the data layer already uses short-lived SQLite
connections so concurrent access is safe. run_campaign re-reads the campaign
status between calls, so a dashboard "Pause" stops an in-flight run cleanly.

If you later move to multiple web workers/processes, swap this for a real queue
(the dashboard only depends on launch()/is_running()).
"""

import logging
import threading

import joblock

log = logging.getLogger(__name__)

_lock = threading.Lock()
_running = {}  # campaign_id -> Thread


def is_running(campaign_id: int) -> bool:
    """True if a run is in flight -- in this process OR on any other worker
    (the DB lock is the cross-process source of truth)."""
    with _lock:
        t = _running.get(campaign_id)
        if t and t.is_alive():
            return True
    return joblock.is_locked(campaign_id)


def launch(campaign_id: int, actor: str = "system") -> bool:
    """Start a campaign in the background. Returns False if it is already
    running (so the caller can tell the operator rather than double-dialing).
    The authoritative guard is the DB lock claimed inside run_campaign; this is
    an early check for a clean operator message."""
    if joblock.is_locked(campaign_id):
        return False
    with _lock:
        t = _running.get(campaign_id)
        if t and t.is_alive():
            return False
        t = threading.Thread(
            target=_run, args=(campaign_id, actor),
            name=f"campaign-{campaign_id}", daemon=True,
        )
        _running[campaign_id] = t
        t.start()
        return True


def _run(campaign_id: int, actor: str):
    # Imported here so importing jobs never pulls in the Twilio client.
    from outbound import run_campaign
    try:
        summary = run_campaign(campaign_id, actor=actor)
        log.info("Campaign %s finished: %s", campaign_id, summary)
    except Exception:
        log.exception("Campaign %s crashed", campaign_id)
    finally:
        with _lock:
            _running.pop(campaign_id, None)
