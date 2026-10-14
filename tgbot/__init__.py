"""
Interactive Telegram operator bot for ConsentIVR.

This package turns Telegram into a *control surface* for the platform, alongside
the web dashboard. It mirrors the dashboard's operations (overview, campaigns,
opt-out management, inbound mode, phone validation, messages) and is gated by
the same role model: admin / operator / viewer.

Unlike notify.py (which is one-directional push alerts), this accepts commands,
so access is an explicit allowlist (see access.py) and every state-changing
action is audited. Unauthorized users are offered a paid-access flow instead of
being able to do anything.

Layout (the pieces the task called out):
    api.py         Thin Telegram Bot API client (long-poll getUpdates + sends).
    context.py     Update -> Ctx parsing; the per-update request object.
    i18n.py        Translation catalogs (en/es/fr/pt/de) + t().
    keyboards.py   Inline-keyboard builders (reply_markup dicts).
    middleware.py  Auth, rate-limit, locale, audit pipeline around every update.
    handlers.py    Command + callback handlers (the actual operations).
    state.py       Per-chat conversation state for multi-step text input.
    access.py      telegram_users allowlist + role/locale/expiry resolution.
    payments.py    Telegram Stars + Crypto Pay paid-access flow.
    bot.py         Wires it together and runs the long-poll loop.
"""
