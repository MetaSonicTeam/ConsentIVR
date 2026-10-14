"""
Long-poll runner: wires the pieces together and pumps updates.

    from tgbot.bot import run
    run()

One process, one blocking getUpdates loop. Each update is parsed into a Ctx
(context.py), run through the middleware chain (middleware.py) ending in the
handler dispatch (handlers.py). Offsets are tracked in-memory and advanced only
after an update is handled, so a crash re-sees the last update rather than
dropping it (handlers are idempotent enough for that to be safe).

The bot and the Flask app are independent processes that share the same SQLite
database — run `python app.py` (web + webhooks) and `python run_telegram.py`
(this) side by side.
"""

import logging
import threading
import time

from config import Config
from db import init_db

from . import context, handlers, middleware
from .api import BotAPI, TelegramError
from .i18n import LANGUAGES

log = logging.getLogger(__name__)

# Commands advertised in the Telegram "/" menu (localized per shipped locale).
_COMMAND_KEYS = [
    ("start", "btn_home"),
    ("overview", "btn_overview"),
    ("campaigns", "btn_campaigns"),
    ("optout", "btn_add_optout"),
    ("validate", "btn_validate"),
    ("language", "btn_language"),
    ("help", "help_text"),
]


def _register_commands(api):
    """Publish the slash-command menu in each shipped language. Best-effort —
    a failure here never stops the bot."""
    from . import i18n
    # Short, menu-friendly descriptions (not the long help_text body).
    desc = {
        "start": {"en": "Main menu", "es": "Menú principal", "fr": "Menu principal",
                  "pt": "Menu principal", "de": "Hauptmenü"},
        "overview": {"en": "Live stats", "es": "Estadísticas", "fr": "Statistiques",
                     "pt": "Estatísticas", "de": "Statistiken"},
        "campaigns": {"en": "List campaigns", "es": "Campañas", "fr": "Campagnes",
                      "pt": "Campanhas", "de": "Kampagnen"},
        "optout": {"en": "Suppress a number", "es": "Suprimir un número",
                   "fr": "Supprimer un numéro", "pt": "Suprimir número",
                   "de": "Nummer sperren"},
        "validate": {"en": "Validate a number", "es": "Validar un número",
                     "fr": "Valider un numéro", "pt": "Validar número",
                     "de": "Nummer prüfen"},
        "language": {"en": "Change language", "es": "Cambiar idioma",
                     "fr": "Changer de langue", "pt": "Mudar idioma",
                     "de": "Sprache ändern"},
        "help": {"en": "Help", "es": "Ayuda", "fr": "Aide", "pt": "Ajuda", "de": "Hilfe"},
    }
    for code, _label in LANGUAGES:
        cmds = [{"command": cmd, "description": desc[cmd].get(code, desc[cmd]["en"])}
                for cmd in desc]
        try:
            api.set_my_commands(cmds, language_code=None if code == "en" else code)
        except TelegramError as e:
            log.warning("setMyCommands(%s) failed: %s", code, e)


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not Config.TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Add it to .env (talk to @BotFather to "
            "create a bot), then run `python run_telegram.py` again."
        )

    init_db()  # ensure telegram_users / tg_payments exist and migrations ran

    api = BotAPI(Config.TELEGRAM_BOT_TOKEN, timeout=max(0, min(50, Config.TELEGRAM_POLL_TIMEOUT)))
    me = api.get_me()
    log.info("Starting Telegram operator bot as @%s (id=%s)", me.get("username"), me.get("id"))
    admins = Config.telegram_admin_ids()
    if admins:
        log.info("Bootstrap admins: %s", ", ".join(str(a) for a in sorted(admins)))
    else:
        log.warning("No TELEGRAM_ADMIN_IDS set — no one can administer the bot until you add one.")

    api.delete_webhook(drop_pending=False)  # getUpdates needs no webhook
    _register_commands(api)

    pipeline = middleware.build(handlers.dispatch)
    # We only care about these update types (payments included).
    allowed = ["message", "edited_message", "callback_query", "pre_checkout_query"]
    offset = None

    log.info("Polling for updates (Ctrl+C to stop)…")
    while True:
        try:
            updates = api.get_updates(offset=offset, allowed_updates=allowed) or []
        except TelegramError as e:
            log.warning("getUpdates error: %s — backing off 3s", e)
            time.sleep(3)
            continue
        except KeyboardInterrupt:
            log.info("Stopping (keyboard interrupt).")
            break

        for update in updates:
            offset = update["update_id"] + 1
            ctx = context.parse_update(api, update)
            if ctx.kind == "ignore":
                continue
            try:
                pipeline(ctx)
            except Exception:
                # mw_error already guards, but never let the loop die.
                log.exception("Pipeline crashed on update %s", update.get("update_id"))


# --- run alongside the web app -------------------------------------------
_bot_thread = None
_thread_lock = threading.Lock()


def start_in_thread():
    """Start the bot in a daemon thread so one process can serve the web app
    AND the Telegram bot (see app.py). Idempotent: a second call while the bot
    is alive is a no-op, which also makes it safe under the Flask reloader.
    Returns the thread, or None if the bot can't/shouldn't start."""
    global _bot_thread
    with _thread_lock:
        if _bot_thread and _bot_thread.is_alive():
            return _bot_thread
        if not Config.TELEGRAM_BOT_TOKEN:
            log.info("TELEGRAM_BOT_TOKEN not set — Telegram bot not started.")
            return None
        t = threading.Thread(target=_run_safe, name="telegram-bot", daemon=True)
        t.start()
        _bot_thread = t
        return t


def _run_safe():
    """run() for the threaded case: log and exit the thread on any failure
    (including a missing token) instead of taking the web process down."""
    try:
        run()
    except SystemExit as e:
        log.warning("Telegram bot not started: %s", e)
    except Exception:
        log.exception("Telegram bot thread crashed")
