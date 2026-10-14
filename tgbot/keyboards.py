"""
Inline-keyboard builders.

Each function returns a reply_markup dict ({"inline_keyboard": [[button,...]]})
ready to hand to the API. Buttons carry a compact callback_data string routed in
handlers.py — scheme "<group>:<action>[:<arg>]" (kept well under Telegram's
64-byte limit). URL buttons are used for the external "Learn more" link.

Keyboards take the Ctx so labels are localized (ctx.t) and role-sensitive rows
are shown only to operators/admins — the handler still re-checks the role, this
just avoids dangling buttons.
"""

from config import Config
from . import i18n
from .access import has_at_least


def _btn(text, data):
    return {"text": text, "callback_data": data}


def _url(text, url):
    return {"text": text, "url": url}


def main_menu(ctx):
    rows = [
        [_btn(ctx.t("btn_overview"), "nav:overview"),
         _btn(ctx.t("btn_campaigns"), "nav:campaigns")],
        [_btn(ctx.t("btn_consent"), "nav:consent"),
         _btn(ctx.t("btn_messages"), "nav:messages")],
        [_btn(ctx.t("btn_inbound"), "nav:inbound"),
         _btn(ctx.t("btn_validate"), "nav:validate")],
        [_btn(ctx.t("btn_menus"), "nav:menus"),
         _btn(ctx.t("btn_language"), "nav:language")],
    ]
    if has_at_least(ctx.role, "admin"):
        rows.append([_btn(ctx.t("btn_users"), "nav:users")])
    return {"inline_keyboard": rows}


def back_home(ctx, back="nav:main"):
    return {"inline_keyboard": [[
        _btn(ctx.t("btn_back"), back),
        _btn(ctx.t("btn_refresh"), ctx.data or back),
    ]]}


def cancel(ctx):
    return {"inline_keyboard": [[_btn(ctx.t("btn_cancel"), "nav:cancel")]]}


def home_only(ctx):
    return {"inline_keyboard": [[_btn(ctx.t("btn_home"), "nav:main")]]}


def campaigns_list(ctx, campaigns):
    rows = []
    for c in campaigns:
        total = c["total"] or 0
        done = c["done"] or 0
        label = f"{c['name']} · {c['status']} · {done}/{total}"
        rows.append([_btn(label[:60], f"camp:view:{c['id']}")])
    rows.append([_btn(ctx.t("btn_home"), "nav:main")])
    return {"inline_keyboard": rows}


def campaign_detail(ctx, campaign):
    cid = campaign["id"]
    rows = []
    if has_at_least(ctx.role, "operator"):
        if campaign["status"] == "running":
            rows.append([_btn(ctx.t("btn_pause"), f"camp:pause:{cid}")])
        else:
            rows.append([_btn(ctx.t("btn_launch"), f"camp:launch:{cid}")])
        rows.append([_btn(ctx.t("btn_add_recipients"), f"camp:recipients:{cid}")])
    rows.append([_btn(ctx.t("btn_back"), "nav:campaigns"),
                 _btn(ctx.t("btn_refresh"), f"camp:view:{cid}")])
    return {"inline_keyboard": rows}


def consent_menu(ctx):
    rows = []
    if has_at_least(ctx.role, "operator"):
        rows.append([_btn(ctx.t("btn_add_optout"), "opt:add")])
    if has_at_least(ctx.role, "admin"):
        rows.append([_btn(ctx.t("btn_remove_optout"), "opt:remove")])
    rows.append([_btn(ctx.t("btn_list_optouts"), "opt:list")])
    rows.append([_btn(ctx.t("btn_home"), "nav:main")])
    return {"inline_keyboard": rows}


def inbound_menu(ctx):
    rows = []
    if has_at_least(ctx.role, "operator"):
        rows = [
            [_btn(ctx.t("inbound_mode_ivr"), "inb:set:ivr"),
             _btn(ctx.t("inbound_mode_forward"), "inb:set:forward")],
            [_btn(ctx.t("inbound_mode_voicemail"), "inb:set:voicemail"),
             _btn(ctx.t("inbound_mode_closed"), "inb:set:closed")],
        ]
    rows.append([_btn(ctx.t("btn_home"), "nav:main")])
    return {"inline_keyboard": rows}


def language_menu(ctx):
    rows = []
    row = []
    for code, label in i18n.LANGUAGES:
        mark = "✓ " if code == ctx.locale else ""
        row.append(_btn(f"{mark}{label}", f"lang:set:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn(ctx.t("btn_home"), "nav:main")])
    return {"inline_keyboard": rows}


def users_menu(ctx, users):
    rows = []
    for u in users:
        if not u["active"]:
            continue
        rows.append([_btn(f"➖ {u['tg_user_id']} ({u['role']})", f"usr:rm:{u['tg_user_id']}")])
    rows.append([_btn(ctx.t("btn_add_user"), "usr:add")])
    rows.append([_btn(ctx.t("btn_home"), "nav:main")])
    return {"inline_keyboard": rows}


def paywall(ctx):
    """Buttons offered to an unauthorized user. Only shows a payment method that
    is actually configured; always offers the Learn-more link when set."""
    rows = []
    if Config.TG_ACCESS_PRICE_STARS and Config.TG_ACCESS_PRICE_STARS > 0:
        rows.append([_btn(ctx.t("btn_pay_stars", n=Config.TG_ACCESS_PRICE_STARS), "pay:stars")])
    if Config.CRYPTO_PAY_API_TOKEN:
        rows.append([_btn(
            ctx.t("btn_pay_crypto", amount=Config.TG_ACCESS_PRICE_CRYPTO,
                  asset=Config.TG_ACCESS_CRYPTO_ASSET),
            "pay:crypto")])
    if Config.TG_LEARN_MORE_URL:
        rows.append([_url(ctx.t("btn_learn_more"), Config.TG_LEARN_MORE_URL)])
    return {"inline_keyboard": rows} if rows else None


def crypto_check(ctx, invoice_id):
    rows = [[_btn(ctx.t("btn_check_payment"), f"pay:check:{invoice_id}")]]
    if Config.TG_LEARN_MORE_URL:
        rows.append([_url(ctx.t("btn_learn_more"), Config.TG_LEARN_MORE_URL)])
    return {"inline_keyboard": rows}
