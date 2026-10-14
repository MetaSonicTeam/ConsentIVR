"""
Per-update request context.

An incoming Telegram update (a message, a button tap, a payment, ...) is parsed
once into a Ctx object that the middleware chain and handlers share. Ctx also
carries the reply helpers so a handler never touches the raw API or worries
about whether it should send a new message or edit the one under a button.
"""

from dataclasses import dataclass, field

from . import i18n


@dataclass
class Ctx:
    api: object                      # BotAPI
    update: dict                     # raw update
    kind: str                        # 'command' | 'text' | 'callback' | 'payment' | 'precheckout' | 'ignore'

    chat_id: int = None
    user_id: int = None
    username: str = None
    text: str = ""                   # message text (commands stripped of leading '/')
    command: str = None              # '/start' -> 'start'
    args: str = ""                   # text after the command
    data: str = ""                   # callback_data
    callback_id: str = None
    message_id: int = None           # message the callback button is attached to

    # filled in by middleware
    role: str = None                 # None = unauthorized
    locale: str = "en"
    payment: dict = None             # successful_payment payload
    precheckout: dict = None         # pre_checkout_query payload
    meta: dict = field(default_factory=dict)

    # --- i18n ------------------------------------------------------------
    def t(self, key, **kwargs):
        return i18n.t(self.locale, key, **kwargs)

    # --- replies ---------------------------------------------------------
    def reply(self, text, keyboard=None):
        """Send a new message to the chat."""
        return self.api.send_message(self.chat_id, text, reply_markup=keyboard)

    def edit(self, text, keyboard=None):
        """Edit the message a button is attached to; fall back to a new message
        (Telegram rejects an edit when the text/markup is unchanged, or when
        there is no message to edit — e.g. this came from a command)."""
        if self.message_id:
            try:
                return self.api.edit_message_text(
                    self.chat_id, self.message_id, text, reply_markup=keyboard
                )
            except Exception:
                pass
        return self.reply(text, keyboard)

    def answer(self, text=None, alert=False):
        """Acknowledge a callback query (stops the client spinner)."""
        if self.callback_id:
            try:
                self.api.answer_callback_query(self.callback_id, text=text, show_alert=alert)
            except Exception:
                pass


def parse_update(api, update: dict) -> Ctx:
    """Turn a raw Telegram update into a Ctx. Unknown shapes become kind
    'ignore' so the loop can skip them without special-casing."""
    # Button tap.
    if "callback_query" in update:
        cq = update["callback_query"]
        frm = cq.get("from", {})
        msg = cq.get("message", {}) or {}
        return Ctx(
            api=api, update=update, kind="callback",
            chat_id=(msg.get("chat") or {}).get("id") or frm.get("id"),
            user_id=frm.get("id"), username=frm.get("username"),
            data=cq.get("data", ""), callback_id=cq.get("id"),
            message_id=msg.get("message_id"),
        )

    # Payment confirmation step (must be answered within 10s).
    if "pre_checkout_query" in update:
        pcq = update["pre_checkout_query"]
        frm = pcq.get("from", {})
        return Ctx(
            api=api, update=update, kind="precheckout",
            chat_id=frm.get("id"), user_id=frm.get("id"),
            username=frm.get("username"), precheckout=pcq,
        )

    msg = update.get("message") or update.get("edited_message")
    if msg:
        frm = msg.get("from", {})
        chat = msg.get("chat", {})
        base = dict(
            api=api, update=update, chat_id=chat.get("id"),
            user_id=frm.get("id"), username=frm.get("username"),
        )
        # Completed payment.
        if "successful_payment" in msg:
            return Ctx(kind="payment", payment=msg["successful_payment"], **base)

        text = (msg.get("text") or "").strip()
        if text.startswith("/"):
            # "/launch@MyBot 12" -> command 'launch', args '12'
            head, _, rest = text.partition(" ")
            cmd = head[1:].split("@", 1)[0].lower()
            return Ctx(kind="command", command=cmd, args=rest.strip(),
                       text=text, **base)
        return Ctx(kind="text", text=text, **base)

    return Ctx(api=api, update=update, kind="ignore")
