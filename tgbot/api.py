"""
Thin, synchronous Telegram Bot API client.

Uses `requests` long-polling (getUpdates) — the same dependency notify.py
already relies on — so the operator bot needs no async stack and no extra
packages. One short-lived HTTPS call per API method, matching the rest of the
app's "no heavy framework" style.

Only the handful of methods the bot actually uses are wrapped; everything else
can go through call() directly.
"""

import logging

import requests

log = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(Exception):
    """A non-ok response from the Bot API (description preserved)."""


class BotAPI:
    def __init__(self, token: str, timeout: int = 30):
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required to run the bot.")
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()

    # --- core -------------------------------------------------------------
    def call(self, method: str, http_timeout: int = None, **params):
        """Invoke a Bot API method. Returns the `result` payload or raises."""
        url = API_ROOT.format(token=self.token, method=method)
        try:
            resp = self._session.post(
                url, json={k: v for k, v in params.items() if v is not None},
                timeout=http_timeout or (self.timeout + 15),
            )
        except requests.RequestException as e:
            raise TelegramError(f"{method} transport error: {e}") from e
        try:
            data = resp.json()
        except ValueError:
            raise TelegramError(f"{method}: non-JSON response ({resp.status_code})")
        if not data.get("ok"):
            raise TelegramError(f"{method}: {data.get('description', 'unknown error')}")
        return data.get("result")

    # --- updates ----------------------------------------------------------
    def get_updates(self, offset=None, allowed_updates=None):
        """Long-poll for updates. Blocks up to `timeout` seconds server-side."""
        return self.call(
            "getUpdates",
            http_timeout=self.timeout + 15,
            offset=offset,
            timeout=self.timeout,
            allowed_updates=allowed_updates,
        )

    def get_me(self):
        return self.call("getMe")

    def delete_webhook(self, drop_pending=False):
        """getUpdates and webhooks are mutually exclusive; clear any webhook so
        long-polling works."""
        return self.call("deleteWebhook", drop_pending_updates=drop_pending)

    def set_my_commands(self, commands, language_code=None):
        return self.call("setMyCommands", commands=commands, language_code=language_code)

    # --- messaging --------------------------------------------------------
    def send_message(self, chat_id, text, reply_markup=None, parse_mode="HTML",
                     disable_preview=True):
        return self.call(
            "sendMessage", chat_id=chat_id, text=text,
            parse_mode=parse_mode, reply_markup=reply_markup,
            link_preview_options={"is_disabled": True} if disable_preview else None,
        )

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None,
                          parse_mode="HTML", disable_preview=True):
        return self.call(
            "editMessageText", chat_id=chat_id, message_id=message_id, text=text,
            parse_mode=parse_mode, reply_markup=reply_markup,
            link_preview_options={"is_disabled": True} if disable_preview else None,
        )

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        return self.call(
            "answerCallbackQuery", callback_query_id=callback_query_id,
            text=text, show_alert=show_alert,
        )

    # --- payments ---------------------------------------------------------
    def send_invoice(self, chat_id, title, description, payload, currency, prices,
                     provider_token="", reply_markup=None):
        """Send an invoice. For Telegram Stars use currency 'XTR' and an empty
        provider_token."""
        return self.call(
            "sendInvoice", chat_id=chat_id, title=title, description=description,
            payload=payload, provider_token=provider_token, currency=currency,
            prices=prices, reply_markup=reply_markup,
        )

    def answer_pre_checkout_query(self, pre_checkout_query_id, ok=True, error_message=None):
        return self.call(
            "answerPreCheckoutQuery", pre_checkout_query_id=pre_checkout_query_id,
            ok=ok, error_message=error_message,
        )
