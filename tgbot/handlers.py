"""
Command, callback, and text handlers — the actual operator actions.

Every handler mirrors an operation the web dashboard already exposes and reuses
the SAME domain functions (consent gates, jobs runner, settings), so Telegram
and the dashboard can never drift apart or bypass a consent check. Role gating
mirrors the dashboard's role_required: viewers read, operators change campaign/
opt-out/inbound state, admins additionally manage operators and remove opt-outs.

Rendering helpers return (text, keyboard); callbacks edit the message in place,
commands send a fresh one. Bulk PII (lists, overviews) is phone-masked with the
same masker notify.py uses for alerts.
"""

import html
import json
import logging

import notify
from config import Config
from consent import add_opt_out, has_consent, is_opted_out, normalize_e164, remove_opt_out
from db import execute, get_setting, query, set_setting

from . import keyboards, payments, state
from .access import (ROLES, authorize, has_at_least, list_users, revoke, set_locale)
from .i18n import LANGUAGES
from .middleware import record

log = logging.getLogger(__name__)

VALID_INBOUND_MODES = ("ivr", "forward", "voicemail", "closed")


# --- small helpers --------------------------------------------------------

def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def mask(text: str) -> str:
    """Mask phone numbers in a bulk view, honoring NOTIFY_MASK_NUMBERS."""
    return notify.mask_numbers(text) if Config.NOTIFY_MASK_NUMBERS else text


def _deny(ctx) -> bool:
    """Acknowledge a role denial on a callback. Returns True (so the caller can
    `return _deny(ctx)`)."""
    ctx.answer(ctx.t("role_denied", role=ctx.role or "-"), alert=True)
    return True


def _require(ctx, minimum) -> bool:
    return has_at_least(ctx.role, minimum)


# =========================================================================
# Views  (return (text, keyboard))
# =========================================================================

def view_main(ctx):
    return (ctx.t("menu_title", app=ctx.t("app_name")) + "\n\n" + ctx.t("nav_choose"),
            keyboards.main_menu(ctx))


def view_overview(ctx):
    stats = {
        "contacts": query("SELECT COUNT(*) c FROM contacts", one=True)["c"],
        "opt_outs": query("SELECT COUNT(*) c FROM opt_outs", one=True)["c"],
        "calls_today": query("SELECT COUNT(*) c FROM calls WHERE date(started_at)=date('now')", one=True)["c"],
        "menus": query("SELECT COUNT(*) c FROM ivr_menus WHERE active=1", one=True)["c"],
    }
    calls = query("SELECT * FROM calls ORDER BY started_at DESC LIMIT 8")
    events = query("SELECT * FROM ivr_events ORDER BY created_at DESC LIMIT 8")

    lines = [ctx.t("overview_title"), ""]
    lines.append(f"{ctx.t('stat_contacts')}: <b>{stats['contacts']}</b>  ·  "
                 f"{ctx.t('stat_optouts')}: <b>{stats['opt_outs']}</b>")
    lines.append(f"{ctx.t('stat_calls_today')}: <b>{stats['calls_today']}</b>  ·  "
                 f"{ctx.t('stat_active_menus')}: <b>{stats['menus']}</b>")
    lines.append("")
    lines.append(ctx.t("recent_calls"))
    if calls:
        for c in calls:
            lines.append(f"• {esc(c['started_at'])} {esc(c['direction'])} "
                         f"{esc(c['from_number'])}→{esc(c['to_number'])} "
                         f"<i>{esc(c['status'])}</i>")
    else:
        lines.append(ctx.t("none"))
    lines.append("")
    lines.append(ctx.t("recent_events"))
    if events:
        for e in events:
            lines.append(f"• {esc(e['created_at'])} <b>{esc(e['event'])}</b> {esc(e['detail'] or '')}")
    else:
        lines.append(ctx.t("none"))
    return mask("\n".join(lines)), keyboards.back_home(ctx, back="nav:main")


def view_campaigns(ctx):
    rows = query(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM campaign_recipients r WHERE r.campaign_id=c.id) AS total,
                  (SELECT COUNT(*) FROM campaign_recipients r WHERE r.campaign_id=c.id AND r.status='done') AS done
             FROM campaigns c ORDER BY c.created_at DESC LIMIT 30"""
    )
    if not rows:
        return ctx.t("campaigns_title") + "\n\n" + ctx.t("campaigns_empty"), keyboards.home_only(ctx)
    return ctx.t("campaigns_title") + "\n\n" + ctx.t("nav_choose"), keyboards.campaigns_list(ctx, rows)


def view_campaign(ctx, cid):
    c = query("SELECT * FROM campaigns WHERE id=?", (cid,), one=True)
    if not c:
        return ctx.t("campaigns_empty"), keyboards.home_only(ctx)
    recips = query("SELECT status, COUNT(*) n FROM campaign_recipients WHERE campaign_id=? GROUP BY status", (cid,))
    total = sum(r["n"] for r in recips)
    done = sum(r["n"] for r in recips if r["status"] == "done")
    tally = "  ".join(f"{esc(r['status'])}={r['n']}" for r in recips) or ctx.t("none")

    lines = [
        ctx.t("camp_detail_title", name=esc(c["name"])), "",
        f"{ctx.t('camp_field_kind')}: <b>{esc(c['kind'])}</b>",
        f"{ctx.t('camp_field_channel')}: <b>{esc(c['channel'])}</b>",
        f"{ctx.t('camp_field_purpose')}: <b>{esc(c['purpose'])}</b>",
        f"{ctx.t('camp_field_status')}: <b>{esc(c['status'])}</b>",
        f"{ctx.t('camp_field_progress')}: <b>{done}/{total}</b>",
        "", ctx.t("camp_tally"), tally,
    ]
    if c["kind"] == "survey":
        lines += ["", f"<i>{ctx.t('camp_results_hint')}</i>"]
    return "\n".join(lines), keyboards.campaign_detail(ctx, c)


def view_consent(ctx):
    opt_outs = query("SELECT * FROM opt_outs ORDER BY created_at DESC LIMIT 10")
    lines = [ctx.t("consent_title"), "", ctx.t("optouts_recent")]
    if opt_outs:
        for o in opt_outs:
            lines.append(f"• <code>{esc(o['phone_e164'])}</code> "
                         f"({esc(o['scope'])}) {esc(o['reason'] or '')}")
    else:
        lines.append(ctx.t("none"))
    return mask("\n".join(lines)), keyboards.consent_menu(ctx)


def view_optouts(ctx):
    rows = query("SELECT * FROM opt_outs ORDER BY created_at DESC LIMIT 50")
    lines = [ctx.t("optouts_recent"), ""]
    if rows:
        for o in rows:
            lines.append(f"• <code>{esc(o['phone_e164'])}</code> "
                         f"({esc(o['scope'])}) - {esc(o['created_at'])}")
    else:
        lines.append(ctx.t("none"))
    return mask("\n".join(lines)), keyboards.back_home(ctx, back="nav:consent")


def view_messages(ctx):
    stats = {
        "out": query("SELECT COUNT(*) c FROM messages WHERE direction='outbound'", one=True)["c"],
        "in": query("SELECT COUNT(*) c FROM messages WHERE direction='inbound'", one=True)["c"],
        "delivered": query("SELECT COUNT(*) c FROM messages WHERE status='delivered'", one=True)["c"],
        "failed": query("SELECT COUNT(*) c FROM messages WHERE status IN ('failed','undelivered')", one=True)["c"],
    }
    rows = query("SELECT * FROM messages ORDER BY created_at DESC LIMIT 10")
    lines = [
        ctx.t("messages_title"), "",
        f"{ctx.t('msg_stat_out')}: <b>{stats['out']}</b>  ·  {ctx.t('msg_stat_in')}: <b>{stats['in']}</b>",
        f"{ctx.t('msg_stat_delivered')}: <b>{stats['delivered']}</b>  ·  {ctx.t('msg_stat_failed')}: <b>{stats['failed']}</b>",
        "", ctx.t("messages_recent"),
    ]
    if rows:
        for m in rows:
            body = (m["body"] or "")[:40]
            lines.append(f"• {esc(m['created_at'])} {esc(m['direction'])} "
                         f"{esc(m['to_number'])} <i>{esc(m['status'])}</i>: {esc(body)}")
    else:
        lines.append(ctx.t("none"))
    return mask("\n".join(lines)), keyboards.back_home(ctx, back="nav:main")


def view_inbound(ctx):
    mode = get_setting("inbound_mode", "ivr")
    fwd = get_setting("inbound_forward_number", "")
    lines = [ctx.t("inbound_title"), "", ctx.t("inbound_current", mode=esc(mode))]
    if fwd:
        lines.append(f"→ <code>{esc(fwd)}</code>")
    lines += ["", ctx.t("inbound_choose")]
    return mask("\n".join(lines)), keyboards.inbound_menu(ctx)


def view_menus(ctx):
    menus = query("SELECT * FROM ivr_menus ORDER BY is_entry DESC, menu_key")
    lines = [ctx.t("menus_title"), ""]
    if not menus:
        lines.append(ctx.t("menus_empty"))
        return "\n".join(lines), keyboards.home_only(ctx)
    for m in menus:
        n = query("SELECT COUNT(*) c FROM ivr_options WHERE menu_id=?", (m["id"],), one=True)["c"]
        tags = []
        if m["is_entry"]:
            tags.append(ctx.t("menu_entry_tag"))
        if not m["active"]:
            tags.append(ctx.t("menu_inactive_tag"))
        tag = f" <i>({', '.join(tags)})</i>" if tags else ""
        lines.append(f"• <b>{esc(m['menu_key'])}</b> - {esc(m['name'])} · {n} opt.{tag}")
    return "\n".join(lines), keyboards.back_home(ctx, back="nav:main")


def view_language(ctx):
    return ctx.t("language_title") + "\n\n" + ctx.t("language_choose"), keyboards.language_menu(ctx)


def view_users(ctx):
    users = list_users()
    lines = [ctx.t("users_title"), ""]
    active = [u for u in users if u["active"]]
    if not active:
        lines.append(ctx.t("users_empty"))
    else:
        for u in active:
            expiry = ""
            if u["access_expires_at"]:
                expiry = f" · ⏳{esc(u['access_expires_at'][:10])}"
            handle = f" @{esc(u['username'])}" if u["username"] else ""
            lines.append(ctx.t("user_line", id=u["tg_user_id"], role=esc(u["role"]),
                                expiry=expiry, inactive="") + handle)
    return "\n".join(lines), keyboards.users_menu(ctx, users)


# =========================================================================
# Operations
# =========================================================================

def _parse_recipient_line(line):
    line = line.strip()
    if not line:
        return None, None
    sep = "," if "," in line else ("|" if "|" in line else None)
    if sep:
        phone, rest = line.split(sep, 1)
        rest = rest.strip()
    else:
        phone, rest = line, ""
    if not rest:
        return phone.strip(), None
    if rest.startswith("{"):
        return phone.strip(), rest
    return phone.strip(), json.dumps({"when": rest})


def _add_recipients(cid, raw):
    """Consent-gated recipient import (same rules as the dashboard)."""
    campaign = query("SELECT * FROM campaigns WHERE id=?", (cid,), one=True)
    if not campaign:
        return None
    purpose = campaign["purpose"]
    channel = "sms" if (campaign["channel"] or "voice") == "sms" else None
    added = rejected = dup = 0
    for line in raw.splitlines():
        phone_raw, vars_json = _parse_recipient_line(line)
        if not phone_raw:
            continue
        phone = normalize_e164(phone_raw)
        if not phone:
            continue
        if is_opted_out(phone, purpose) or not has_consent(phone, purpose, channel=channel):
            rejected += 1
            continue
        contact = query("SELECT id FROM contacts WHERE phone_e164=?", (phone,), one=True)
        try:
            execute(
                "INSERT INTO campaign_recipients (campaign_id, contact_id, phone_e164, vars_json) "
                "VALUES (?,?,?,?)",
                (cid, contact["id"] if contact else None, phone, vars_json),
            )
            added += 1
        except Exception:
            dup += 1
    return added, dup, rejected


# =========================================================================
# Unauthorized (paid-access flow)
# =========================================================================

def unauthorized(ctx):
    # Payment confirmation handshake — must be answered fast.
    if ctx.kind == "precheckout":
        payments.approve_precheckout(ctx)
        return
    if ctx.kind == "payment":
        role, expiry = payments.handle_successful_payment(ctx)
        suffix = ctx.t("pay_expiry_suffix", date=expiry) if expiry else ""
        ctx.reply(ctx.t("pay_success", role=role, expiry=suffix))
        return

    if ctx.kind == "callback" and ctx.data.startswith("pay:"):
        return _handle_pay_callback(ctx)

    # Anything else from an unauthorized user -> the paywall.
    _show_paywall(ctx)


def _show_paywall(ctx):
    ctx.answer()  # stop the client spinner if this came from a stale button
    body = (ctx.t("unauthorized_title") + "\n\n" +
            ctx.t("unauthorized_body", app=ctx.t("app_name"), id=ctx.user_id))
    kb = keyboards.paywall(ctx)
    if kb is None:
        body += "\n\n" + ctx.t("pay_none_configured")
    ctx.reply(body, kb)


def _handle_pay_callback(ctx):
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "stars":
        if not payments.stars_enabled():
            return ctx.answer(ctx.t("pay_none_configured"), alert=True)
        ctx.answer()
        payments.send_stars_invoice(ctx)
        return

    if action == "crypto":
        if not payments.crypto_enabled():
            return ctx.answer(ctx.t("pay_crypto_unavailable"), alert=True)
        ctx.answer()
        try:
            invoice_id, pay_url = payments.create_crypto_invoice(ctx)
        except Exception:
            log.exception("Crypto invoice creation failed")
            return ctx.reply(ctx.t("pay_crypto_unavailable"))
        kb = {"inline_keyboard": [
            [{"text": ctx.t("btn_pay_crypto", amount=Config.TG_ACCESS_PRICE_CRYPTO,
                             asset=Config.TG_ACCESS_CRYPTO_ASSET), "url": pay_url}],
            keyboards.crypto_check(ctx, invoice_id)["inline_keyboard"][0],
        ]}
        ctx.reply(ctx.t("pay_crypto_created", amount=Config.TG_ACCESS_PRICE_CRYPTO,
                         asset=Config.TG_ACCESS_CRYPTO_ASSET), kb)
        return

    if action == "check":
        invoice_id = parts[2] if len(parts) > 2 else ""
        try:
            granted, role, expiry = payments.check_crypto_invoice(ctx, invoice_id)
        except Exception:
            log.exception("Crypto invoice check failed")
            return ctx.answer(ctx.t("pay_crypto_unavailable"), alert=True)
        if granted:
            suffix = ctx.t("pay_expiry_suffix", date=expiry) if expiry else ""
            ctx.answer()
            ctx.reply(ctx.t("pay_success", role=role, expiry=suffix))
        else:
            ctx.answer(ctx.t("pay_not_yet"), alert=True)
        return

    ctx.answer()


# =========================================================================
# Dispatch
# =========================================================================

def dispatch(ctx):
    if ctx.kind == "precheckout":
        # Authorized user re-buying (e.g. renewal): approve too.
        payments.approve_precheckout(ctx)
        return
    if ctx.kind == "payment":
        role, expiry = payments.handle_successful_payment(ctx)
        suffix = ctx.t("pay_expiry_suffix", date=expiry) if expiry else ""
        ctx.reply(ctx.t("pay_success", role=role, expiry=suffix))
        return
    if ctx.kind == "command":
        return _dispatch_command(ctx)
    if ctx.kind == "callback":
        return _dispatch_callback(ctx)
    if ctx.kind == "text":
        return _dispatch_text(ctx)


def _dispatch_command(ctx):
    cmd = ctx.command
    state.clear(ctx.chat_id)
    if cmd in ("start", "menu"):
        text, kb = view_main(ctx)
        hello = ctx.t("start_welcome", app=ctx.t("app_name"), role=ctx.role) + "\n\n"
        return ctx.reply(hello + text, kb)
    if cmd == "help":
        return ctx.reply(ctx.t("help_text", app=ctx.t("app_name")), keyboards.home_only(ctx))
    if cmd == "overview":
        return ctx.reply(*view_overview(ctx))
    if cmd == "campaigns":
        return ctx.reply(*view_campaigns(ctx))
    if cmd == "messages":
        return ctx.reply(*view_messages(ctx))
    if cmd == "language":
        return ctx.reply(*view_language(ctx))
    if cmd == "menus":
        return ctx.reply(*view_menus(ctx))
    if cmd == "optout":
        if not _require(ctx, "operator"):
            return ctx.reply(ctx.t("role_denied", role=ctx.role))
        if ctx.args:
            return _do_optout_add(ctx, ctx.args)
        state.set_pending(ctx.chat_id, "optout_add")
        return ctx.reply(ctx.t("prompt_optout_add"), keyboards.cancel(ctx))
    if cmd == "validate":
        if ctx.args:
            return _do_validate(ctx, ctx.args)
        state.set_pending(ctx.chat_id, "validate")
        return ctx.reply(ctx.t("prompt_validate"), keyboards.cancel(ctx))
    return ctx.reply(ctx.t("unknown_command"), keyboards.home_only(ctx))


def _dispatch_callback(ctx):
    data = ctx.data or ""
    group, _, rest = data.partition(":")

    # Navigation.
    if group == "nav":
        ctx.answer()
        if rest == "cancel":
            state.clear(ctx.chat_id)
            return ctx.edit(*view_main(ctx))
        view = {
            "main": view_main, "overview": view_overview, "campaigns": view_campaigns,
            "consent": view_consent, "messages": view_messages, "inbound": view_inbound,
            "validate": None, "menus": view_menus, "language": view_language,
            "users": view_users,
        }.get(rest)
        if rest == "validate":
            state.set_pending(ctx.chat_id, "validate")
            return ctx.edit(ctx.t("prompt_validate"), keyboards.cancel(ctx))
        if rest == "users" and not _require(ctx, "admin"):
            return _deny(ctx)
        if view:
            return ctx.edit(*view(ctx))
        return

    if group == "camp":
        return _cb_campaign(ctx, rest)
    if group == "opt":
        return _cb_optout(ctx, rest)
    if group == "inb":
        return _cb_inbound(ctx, rest)
    if group == "lang":
        return _cb_language(ctx, rest)
    if group == "usr":
        return _cb_users(ctx, rest)
    if group == "pay":
        # An already-authorized user tapping a stale pay button — just refresh.
        ctx.answer()
        return ctx.edit(*view_main(ctx))
    ctx.answer()


def _cb_campaign(ctx, rest):
    action, _, cid = rest.partition(":")
    cid = int(cid) if cid.isdigit() else None
    if action == "view":
        ctx.answer()
        return ctx.edit(*view_campaign(ctx, cid))
    if action == "launch":
        if not _require(ctx, "operator"):
            return _deny(ctx)
        import jobs
        if jobs.is_running(cid):
            ctx.answer(ctx.t("camp_already_running"), alert=True)
        elif jobs.launch(cid, actor=f"tg:{ctx.user_id}"):
            record(ctx, "campaign_launch", str(cid))
            ctx.answer(ctx.t("camp_launched"))
        else:
            ctx.answer(ctx.t("camp_launch_failed"), alert=True)
        return ctx.edit(*view_campaign(ctx, cid))
    if action == "pause":
        if not _require(ctx, "operator"):
            return _deny(ctx)
        execute("UPDATE campaigns SET status='paused', updated_at=datetime('now') WHERE id=?", (cid,))
        record(ctx, "campaign_pause", str(cid))
        ctx.answer(ctx.t("camp_paused"))
        return ctx.edit(*view_campaign(ctx, cid))
    if action == "recipients":
        if not _require(ctx, "operator"):
            return _deny(ctx)
        c = query("SELECT name FROM campaigns WHERE id=?", (cid,), one=True)
        state.set_pending(ctx.chat_id, "recipients", cid=cid)
        ctx.answer()
        return ctx.edit(ctx.t("prompt_recipients", name=esc(c["name"]) if c else cid),
                        keyboards.cancel(ctx))
    ctx.answer()


def _cb_optout(ctx, rest):
    if rest == "list":
        ctx.answer()
        return ctx.edit(*view_optouts(ctx))
    if rest == "add":
        if not _require(ctx, "operator"):
            return _deny(ctx)
        state.set_pending(ctx.chat_id, "optout_add")
        ctx.answer()
        return ctx.edit(ctx.t("prompt_optout_add"), keyboards.cancel(ctx))
    if rest == "remove":
        if not _require(ctx, "admin"):
            return _deny(ctx)
        state.set_pending(ctx.chat_id, "optout_remove")
        ctx.answer()
        return ctx.edit(ctx.t("prompt_optout_remove"), keyboards.cancel(ctx))
    ctx.answer()


def _cb_inbound(ctx, rest):
    action, _, mode = rest.partition(":")
    if action != "set":
        return ctx.answer()
    if not _require(ctx, "operator"):
        return _deny(ctx)
    if mode not in VALID_INBOUND_MODES:
        return ctx.answer()
    if mode == "forward" and not get_setting("inbound_forward_number", ""):
        state.set_pending(ctx.chat_id, "forward_number")
        ctx.answer()
        return ctx.edit(ctx.t("inbound_forward_needs_number"), keyboards.cancel(ctx))
    set_setting("inbound_mode", mode)
    record(ctx, "inbound_mode", mode)
    ctx.answer(ctx.t("inbound_updated", mode=mode))
    return ctx.edit(*view_inbound(ctx))


def _cb_language(ctx, rest):
    action, _, code = rest.partition(":")
    if action != "set":
        return ctx.answer()
    valid = {c for c, _label in LANGUAGES}
    if code not in valid:
        return ctx.answer()
    set_locale(ctx.user_id, code)
    ctx.locale = code
    label = dict(LANGUAGES).get(code, code)
    ctx.answer(ctx.t("language_set", lang=label))
    return ctx.edit(*view_main(ctx))


def _cb_users(ctx, rest):
    if not _require(ctx, "admin"):
        return _deny(ctx)
    action, _, arg = rest.partition(":")
    if action == "add":
        state.set_pending(ctx.chat_id, "add_user")
        ctx.answer()
        return ctx.edit(ctx.t("prompt_add_user"), keyboards.cancel(ctx))
    if action == "rm" and arg.lstrip("-").isdigit():
        revoke(int(arg), actor=f"tg:{ctx.user_id}")
        ctx.answer(ctx.t("user_removed", id=arg))
        return ctx.edit(*view_users(ctx))
    ctx.answer()


# --- text (follow-ups to a pending prompt) -------------------------------

def _dispatch_text(ctx):
    action, data = state.get_pending(ctx.chat_id)
    if not action:
        # No pending flow: treat free text as "show me the menu".
        text, kb = view_main(ctx)
        return ctx.reply(text, kb)
    state.clear(ctx.chat_id)

    if action == "optout_add":
        return _do_optout_add(ctx, ctx.text)
    if action == "optout_remove":
        return _do_optout_remove(ctx, ctx.text)
    if action == "validate":
        return _do_validate(ctx, ctx.text)
    if action == "forward_number":
        return _do_forward_number(ctx, ctx.text)
    if action == "recipients":
        return _do_recipients(ctx, data.get("cid"), ctx.text)
    if action == "add_user":
        return _do_add_user(ctx, ctx.text)
    return ctx.reply(ctx.t("unknown_command"), keyboards.home_only(ctx))


def _do_optout_add(ctx, raw):
    if not _require(ctx, "operator"):
        return ctx.reply(ctx.t("role_denied", role=ctx.role))
    phone = normalize_e164(raw.strip())
    if not phone:
        return ctx.reply(ctx.t("optout_invalid"), keyboards.consent_menu(ctx))
    add_opt_out(phone, scope="all", reason="operator", actor=f"tg:{ctx.user_id}")
    return ctx.reply(ctx.t("optout_added", phone=esc(phone)), keyboards.consent_menu(ctx))


def _do_optout_remove(ctx, raw):
    if not _require(ctx, "admin"):
        return ctx.reply(ctx.t("role_denied", role=ctx.role))
    phone = normalize_e164(raw.strip())
    if not phone:
        return ctx.reply(ctx.t("optout_invalid"), keyboards.consent_menu(ctx))
    remove_opt_out(phone, actor=f"tg:{ctx.user_id}")
    return ctx.reply(ctx.t("optout_removed", phone=esc(phone)), keyboards.consent_menu(ctx))


def _do_validate(ctx, raw):
    import validate as validator
    result = validator.validate_number(raw.strip(), region=Config.DEFAULT_REGION)
    if not result or not result.get("e164"):
        return ctx.reply(ctx.t("validate_invalid"), keyboards.home_only(ctx))
    opted = is_opted_out(result["e164"])
    text = ctx.t(
        "validate_result",
        input=esc(raw.strip()),
        valid="✅" if result.get("valid") else "❌",
        e164=esc(result.get("e164") or "-"),
        region=esc(result.get("region") or "-"),
        line_type=esc(result.get("type") or "-"),
        carrier=esc(result.get("carrier") or "-"),
        opted_out="✅" if opted else "❌",
    )
    return ctx.reply(text, keyboards.home_only(ctx))


def _do_forward_number(ctx, raw):
    if not _require(ctx, "operator"):
        return ctx.reply(ctx.t("role_denied", role=ctx.role))
    phone = normalize_e164(raw.strip())
    if not phone:
        return ctx.reply(ctx.t("optout_invalid"), keyboards.inbound_menu(ctx))
    set_setting("inbound_forward_number", phone)
    set_setting("inbound_mode", "forward")
    record(ctx, "inbound_mode", "forward", f"forward={phone}")
    ctx.reply(ctx.t("inbound_updated", mode="forward"))
    return ctx.reply(*view_inbound(ctx))


def _do_recipients(ctx, cid, raw):
    if not _require(ctx, "operator"):
        return ctx.reply(ctx.t("role_denied", role=ctx.role))
    res = _add_recipients(cid, raw)
    if res is None:
        return ctx.reply(ctx.t("campaigns_empty"), keyboards.home_only(ctx))
    added, dup, rejected = res
    record(ctx, "campaign_add_recipients", str(cid),
           f"added={added} dup={dup} rejected={rejected}")
    ctx.reply(ctx.t("recipients_added", added=added, dup=dup, rejected=rejected))
    return ctx.reply(*view_campaign(ctx, cid))


def _do_add_user(ctx, raw):
    if not _require(ctx, "admin"):
        return ctx.reply(ctx.t("role_denied", role=ctx.role))
    parts = raw.split()
    if len(parts) < 2 or not parts[0].lstrip("-").isdigit() or parts[1].lower() not in ROLES:
        return ctx.reply(ctx.t("user_invalid"), keyboards.cancel(ctx))
    tg_id = int(parts[0])
    role = parts[1].lower()
    authorize(tg_id, role, added_by=f"tg:{ctx.user_id}", days=0)
    ctx.reply(ctx.t("user_added", id=tg_id, role=role))
    return ctx.reply(*view_users(ctx))
