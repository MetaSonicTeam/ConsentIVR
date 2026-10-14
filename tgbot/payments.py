"""
Paid-access flow for unauthorized Telegram users.

Two optional rails, either/both configurable:

  * Telegram Stars (XTR) — native digital-goods payment. Needs only the bot
    token (no provider token). We sendInvoice, approve the pre_checkout_query,
    and on `successful_payment` grant access. Fully in-chat.

  * Crypto Pay (@CryptoBot Crypto Pay API) — we create an invoice via their REST
    API and hand back the pay URL. Because the bot long-polls (no public
    webhook), confirmation is pull-based: the user taps "I've paid — check" and
    we verify the invoice status. No wallet secrets ever touch this process.

A completed payment grants TG_ACCESS_GRANT_ROLE for TG_ACCESS_GRANT_DAYS (0 =
no expiry) and is recorded in tg_payments for accountability. We never store
card/wallet data — only the provider's charge/invoice id.
"""

import logging

import requests

from config import Config
from db import audit, execute
from . import access

log = logging.getLogger(__name__)

_CRYPTO_BASE = {
    "main": "https://pay.crypt.bot/api",
    "test": "https://testnet-pay.crypt.bot/api",
}


# --- Telegram Stars -------------------------------------------------------

def stars_enabled() -> bool:
    return bool(Config.TG_ACCESS_PRICE_STARS and Config.TG_ACCESS_PRICE_STARS > 0)


def send_stars_invoice(ctx):
    """Send a Telegram Stars invoice for operator access."""
    n = Config.TG_ACCESS_PRICE_STARS
    days = Config.TG_ACCESS_GRANT_DAYS
    desc = (ctx.t("pay_desc", app=ctx.t("app_name"), days=days) if days
            else ctx.t("pay_desc_nolimit", app=ctx.t("app_name")))
    ctx.api.send_invoice(
        chat_id=ctx.chat_id,
        title=ctx.t("pay_title", app=ctx.t("app_name")),
        description=desc,
        payload=f"access:{ctx.user_id}",
        currency="XTR",
        prices=[{"label": ctx.t("pay_title", app=ctx.t("app_name")), "amount": n}],
        provider_token="",   # Stars: empty provider token
    )


def approve_precheckout(ctx):
    """Approve the pre-checkout step. Must happen within 10s or the payment
    fails on the client."""
    pcq = ctx.precheckout or {}
    ok = str(pcq.get("invoice_payload", "")).startswith("access:")
    ctx.api.answer_pre_checkout_query(
        pcq.get("id"), ok=ok,
        error_message=None if ok else "This item is no longer available.",
    )


def handle_successful_payment(ctx) -> tuple:
    """Grant access after Telegram confirms a Stars payment. Returns
    (role, expiry_date_or_None)."""
    sp = ctx.payment or {}
    charge_id = sp.get("telegram_payment_charge_id")
    amount = sp.get("total_amount")
    role = Config.TG_ACCESS_GRANT_ROLE if Config.TG_ACCESS_GRANT_ROLE in access.ROLES else "operator"
    days = Config.TG_ACCESS_GRANT_DAYS

    execute(
        "INSERT INTO tg_payments (tg_user_id, provider, amount, asset, charge_id, status) "
        "VALUES (?, 'stars', ?, 'XTR', ?, 'paid')",
        (ctx.user_id, str(amount), charge_id),
    )
    access.authorize(ctx.user_id, role, added_by="payment:stars", days=days,
                     username=ctx.username)
    audit("payment:stars", "tg_access_granted", str(ctx.user_id), f"charge={charge_id}")
    return role, _expiry_label(days)


# --- Crypto Pay -----------------------------------------------------------

def crypto_enabled() -> bool:
    return bool(Config.CRYPTO_PAY_API_TOKEN)


def _crypto_call(method: str, payload: dict = None):
    base = _CRYPTO_BASE.get(Config.CRYPTO_PAY_NETWORK, _CRYPTO_BASE["main"])
    resp = requests.post(
        f"{base}/{method}",
        headers={"Crypto-Pay-API-Token": Config.CRYPTO_PAY_API_TOKEN},
        json=payload or {},
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Crypto Pay {method}: {data.get('error')}")
    return data["result"]


def create_crypto_invoice(ctx):
    """Create a Crypto Pay invoice. Returns (invoice_id, pay_url)."""
    result = _crypto_call("createInvoice", {
        "asset": Config.TG_ACCESS_CRYPTO_ASSET,
        "amount": str(Config.TG_ACCESS_PRICE_CRYPTO),
        "description": ctx.t("pay_title", app=ctx.t("app_name")),
        "payload": f"access:{ctx.user_id}",
        "allow_comments": False,
        "allow_anonymous": False,
    })
    invoice_id = result.get("invoice_id")
    pay_url = result.get("pay_url") or result.get("bot_invoice_url")
    execute(
        "INSERT INTO tg_payments (tg_user_id, provider, amount, asset, charge_id, status) "
        "VALUES (?, 'crypto', ?, ?, ?, 'pending')",
        (ctx.user_id, str(Config.TG_ACCESS_PRICE_CRYPTO), Config.TG_ACCESS_CRYPTO_ASSET, str(invoice_id)),
    )
    return invoice_id, pay_url


def check_crypto_invoice(ctx, invoice_id) -> tuple:
    """Poll a Crypto Pay invoice. If paid (and belongs to this user), grant
    access. Returns (granted: bool, role, expiry_label)."""
    result = _crypto_call("getInvoices", {"invoice_ids": str(invoice_id)})
    items = result.get("items") or []
    inv = items[0] if items else None
    if not inv or inv.get("status") != "paid":
        return False, None, None
    # Make sure the invoice really was for this user.
    if str(inv.get("payload", "")) != f"access:{ctx.user_id}":
        return False, None, None

    role = Config.TG_ACCESS_GRANT_ROLE if Config.TG_ACCESS_GRANT_ROLE in access.ROLES else "operator"
    days = Config.TG_ACCESS_GRANT_DAYS
    execute("UPDATE tg_payments SET status='paid' WHERE charge_id=? AND provider='crypto'",
            (str(invoice_id),))
    access.authorize(ctx.user_id, role, added_by="payment:crypto", days=days,
                     username=ctx.username)
    audit("payment:crypto", "tg_access_granted", str(ctx.user_id), f"invoice={invoice_id}")
    return True, role, _expiry_label(days)


# --- shared ---------------------------------------------------------------

def _expiry_label(days: int):
    if not days or days <= 0:
        return None
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
