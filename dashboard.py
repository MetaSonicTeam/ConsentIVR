"""
Web admin dashboard (Flask blueprint).

Scope for this first slice:
  * Login / logout (bcrypt, server-side session).
  * Overview: recent calls + live IVR events.
  * IVR menu viewer (menus + options) so operators can see the live routing.
  * Consent & opt-out management (add/remove opt-outs, view consent).

Campaign creation (survey / appointment outbound) will plug in here next.
"""

import csv
import io
import json
import re

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import Config
from consent import add_opt_out, has_consent, is_opted_out, normalize_e164, remove_opt_out
from db import audit, execute, get_setting, query, set_setting
from security import check_password, login_required, role_required

VALID_KINDS = ("reminder", "survey")
VALID_CHANNELS = ("voice", "sms", "whatsapp")
VALID_INBOUND_MODES = ("ivr", "forward", "voicemail", "closed")

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def home():
    calls = query("SELECT * FROM calls ORDER BY started_at DESC LIMIT 25")
    events = query("SELECT * FROM ivr_events ORDER BY created_at DESC LIMIT 25")
    stats = {
        "contacts": query("SELECT COUNT(*) c FROM contacts", one=True)["c"],
        "opt_outs": query("SELECT COUNT(*) c FROM opt_outs", one=True)["c"],
        "calls_today": query(
            "SELECT COUNT(*) c FROM calls WHERE date(started_at) = date('now')", one=True
        )["c"],
        "menus": query("SELECT COUNT(*) c FROM ivr_menus WHERE active=1", one=True)["c"],
    }
    return render_template("dashboard.html", calls=calls, events=events, stats=stats)


@bp.route("/menus")
@login_required
def menus():
    menus = query("SELECT * FROM ivr_menus ORDER BY is_entry DESC, menu_key")
    options = query("SELECT * FROM ivr_options ORDER BY menu_id, sort_order, digit")
    opts_by_menu = {}
    for o in options:
        opts_by_menu.setdefault(o["menu_id"], []).append(o)
    inbound = {
        "mode": get_setting("inbound_mode", "ivr"),
        "forward_number": get_setting("inbound_forward_number", ""),
        "closed_message": get_setting("inbound_closed_message", ""),
    }
    return render_template("menus.html", menus=menus, opts_by_menu=opts_by_menu,
                           voices=Config.AVAILABLE_VOICES, config_default_voice=Config.POLLY_VOICE,
                           inbound=inbound, inbound_modes=VALID_INBOUND_MODES)


@bp.route("/inbound-mode", methods=["POST"])
@role_required("admin", "operator")
def inbound_mode():
    mode = request.form.get("mode", "ivr").strip()
    if mode not in VALID_INBOUND_MODES:
        flash("Invalid inbound mode.", "error")
        return redirect(url_for("dashboard.menus"))
    fwd = normalize_e164(request.form.get("forward_number", "").strip()) if request.form.get("forward_number", "").strip() else ""
    closed_msg = request.form.get("closed_message", "").strip()

    if mode == "forward" and not fwd:
        flash("Forward mode needs a valid forward-to number.", "error")
        return redirect(url_for("dashboard.menus"))

    set_setting("inbound_mode", mode)
    set_setting("inbound_forward_number", fwd)
    set_setting("inbound_closed_message", closed_msg)
    audit(session.get("user", "operator"), "inbound_mode", mode,
          f"forward={fwd or '-'}")
    flash(f"Inbound mode set to '{mode}'.", "success")
    return redirect(url_for("dashboard.menus"))


@bp.route("/menus/<menu_key>/edit", methods=["POST"])
@role_required("admin", "operator")
def menu_edit(menu_key):
    menu = query("SELECT * FROM ivr_menus WHERE menu_key=?", (menu_key,), one=True)
    if not menu:
        flash("Menu not found.", "error")
        return redirect(url_for("dashboard.menus"))

    greeting = request.form.get("greeting", "").strip()
    if not greeting:
        flash("A greeting is required.", "error")
        return redirect(url_for("dashboard.menus"))
    after_hours_msg = request.form.get("after_hours_msg", "").strip() or None
    voice = request.form.get("voice", "").strip()
    if voice and not Config.is_valid_voice(voice):
        flash("Unknown voice.", "error")
        return redirect(url_for("dashboard.menus"))
    recording_enabled = 1 if request.form.get("recording_enabled") else 0
    active = 1 if request.form.get("active") else 0
    # Never let the entry menu be deactivated -- that silently breaks every
    # inbound call. Force it active and tell the operator.
    entry_note = ""
    if menu["is_entry"] and not active:
        active = 1
        entry_note = " (entry menu kept active)"

    execute(
        """UPDATE ivr_menus
              SET greeting=?, after_hours_msg=?, voice=?, recording_enabled=?, active=?,
                  updated_at=datetime('now')
            WHERE menu_key=?""",
        (greeting, after_hours_msg, voice or None, recording_enabled, active, menu_key),
    )
    audit(session.get("user", "operator"), "menu_edit", menu_key,
          f"voice={voice or 'default'} recording={recording_enabled} active={active}")
    flash(f"Menu '{menu_key}' updated.{entry_note}", "success")
    return redirect(url_for("dashboard.menus"))


@bp.route("/consent")
@login_required
def consent_view():
    opt_outs = query("SELECT * FROM opt_outs ORDER BY created_at DESC LIMIT 200")
    consents = query(
        """SELECT c.*, ct.phone_e164, ct.display_name
             FROM consent c JOIN contacts ct ON ct.id = c.contact_id
            ORDER BY c.granted_at DESC LIMIT 200"""
    )
    return render_template("consent.html", opt_outs=opt_outs, consents=consents)


@bp.route("/messages")
@login_required
def messages():
    direction = request.args.get("direction", "")
    sql = (
        "SELECT m.*, c.name AS campaign_name FROM messages m "
        "LEFT JOIN campaigns c ON c.id = m.campaign_id"
    )
    params = ()
    if direction in ("inbound", "outbound"):
        sql += " WHERE m.direction = ?"
        params = (direction,)
    sql += " ORDER BY m.created_at DESC LIMIT 200"
    rows = query(sql, params)
    stats = {
        "outbound": query("SELECT COUNT(*) c FROM messages WHERE direction='outbound'", one=True)["c"],
        "inbound": query("SELECT COUNT(*) c FROM messages WHERE direction='inbound'", one=True)["c"],
        "delivered": query("SELECT COUNT(*) c FROM messages WHERE status='delivered'", one=True)["c"],
        "failed": query("SELECT COUNT(*) c FROM messages WHERE status IN ('failed','undelivered')", one=True)["c"],
    }
    return render_template("messages.html", messages=rows, stats=stats, direction=direction)


@bp.route("/validate", methods=["GET"])
@login_required
def validate_phone():
    import validate as validator
    number = request.args.get("number", "").strip()
    region = request.args.get("region", "").strip() or Config.DEFAULT_REGION
    do_lookup = request.args.get("lookup") == "1"

    result = None
    lookup = None
    lookup_error = None
    if number:
        result = validator.validate_number(number, region=region)
        if do_lookup and result.get("e164"):
            try:
                lookup = validator.provider_lookup(result["e164"]) or None
                if lookup is None:
                    lookup_error = "No lookup provider configured (needs Twilio credentials)."
            except Exception as e:
                lookup_error = str(e)
    return render_template("validate.html", number=number, region=region,
                           result=result, lookup=lookup, lookup_error=lookup_error,
                           default_region=Config.DEFAULT_REGION)


@bp.route("/opt-out", methods=["POST"])
@role_required("admin", "operator")
def opt_out_add():
    phone = request.form.get("phone", "").strip()
    scope = request.form.get("scope", "all").strip() or "all"
    if phone:
        add_opt_out(phone, scope=scope, reason="operator", actor=session.get("user", "operator"))
        flash(f"{phone} added to opt-out list.", "success")
    return redirect(url_for("dashboard.consent_view"))


@bp.route("/opt-out/remove", methods=["POST"])
@role_required("admin")
def opt_out_remove():
    phone = request.form.get("phone", "").strip()
    if phone:
        remove_opt_out(phone, actor=session.get("user", "admin"))
        flash(f"{phone} removed from opt-out list.", "success")
    return redirect(url_for("dashboard.consent_view"))


@bp.route("/campaigns")
@login_required
def campaigns():
    rows = query(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM campaign_recipients r WHERE r.campaign_id=c.id) AS total,
                  (SELECT COUNT(*) FROM campaign_recipients r WHERE r.campaign_id=c.id AND r.status='done') AS done
             FROM campaigns c ORDER BY c.created_at DESC"""
    )
    return render_template("campaigns.html", campaigns=rows, voices=Config.AVAILABLE_VOICES)


@bp.route("/campaigns/new", methods=["POST"])
@role_required("admin", "operator")
def campaign_new():
    name = request.form.get("name", "").strip()
    kind = request.form.get("kind", "").strip()
    channel = request.form.get("channel", "voice").strip() or "voice"
    purpose = request.form.get("purpose", "").strip()
    script_text = request.form.get("script_text", "").strip() or None
    voice = request.form.get("voice", "").strip() or None
    amd_enabled = 1 if request.form.get("amd_enabled") else 0
    agent_raw = request.form.get("agent_number", "").strip()
    agent_number = normalize_e164(agent_raw) if agent_raw else None

    if not name or kind not in VALID_KINDS or not purpose or channel not in VALID_CHANNELS:
        flash("Name, a valid kind (reminder/survey), channel, and a consent purpose are required.", "error")
        return redirect(url_for("dashboard.campaigns"))
    if voice and not Config.is_valid_voice(voice):
        voice = None  # ignore an unknown voice; fall back to the global default

    # Surveys run over voice only; SMS / WhatsApp are reminder-style messaging.
    if channel in ("sms", "whatsapp"):
        kind = "reminder"
    if kind == "survey":
        channel = "voice"
    if channel != "voice":
        agent_number = None  # 'press 0' transfer is a voice-only feature

    cid = execute(
        "INSERT INTO campaigns (name, kind, channel, voice, amd_enabled, agent_number, purpose, script_text, status, created_by) "
        "VALUES (?,?,?,?,?,?,?,?, 'draft', ?)",
        (name, kind, channel, voice, amd_enabled, agent_number, purpose, script_text, session.get("user", "operator")),
    )
    audit(session.get("user", "operator"), "campaign_create", str(cid), f"{kind}/{channel}/{purpose}")
    flash(f"Created campaign '{name}'. Add recipients, then launch.", "success")
    return redirect(url_for("dashboard.campaign_detail", cid=cid))


def _parse_recipient_line(line):
    """A line is 'phone' optionally followed by ',' or '|' then merge data.
    The merge data is used as-is if it's a JSON object, otherwise treated as
    the reminder's {when} value. Returns (phone_raw, vars_json_or_None)."""
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
        return phone.strip(), rest  # assume caller-provided JSON
    # Shorthand: bare text becomes the {when} merge field for reminders.
    import json
    return phone.strip(), json.dumps({"when": rest})


@bp.route("/campaigns/<int:cid>/recipients", methods=["POST"])
@role_required("admin", "operator")
def campaign_add_recipients(cid):
    campaign = query("SELECT * FROM campaigns WHERE id=?", (cid,), one=True)
    if not campaign:
        flash("Campaign not found.", "error")
        return redirect(url_for("dashboard.campaigns"))

    purpose = campaign["purpose"]
    channel = "sms" if (campaign["channel"] or "voice") == "sms" else None
    raw = request.form.get("numbers", "")
    added = rejected = dup = 0
    rejected_samples = []

    for line in raw.splitlines():
        phone_raw, vars_json = _parse_recipient_line(line)
        if not phone_raw:
            continue
        phone = normalize_e164(phone_raw)
        if not phone:
            continue

        # CONSENT GATE at import time: only consented, non-suppressed numbers
        # become recipients. (It is re-checked again at dial time.)
        if is_opted_out(phone, purpose) or not has_consent(phone, purpose, channel=channel):
            rejected += 1
            if len(rejected_samples) < 5:
                rejected_samples.append(phone)
            continue

        contact = query("SELECT id FROM contacts WHERE phone_e164=?", (phone,), one=True)
        try:
            execute(
                """INSERT INTO campaign_recipients (campaign_id, contact_id, phone_e164, vars_json)
                   VALUES (?,?,?,?)""",
                (cid, contact["id"] if contact else None, phone, vars_json),
            )
            added += 1
        except Exception:
            dup += 1  # UNIQUE(campaign_id, phone_e164) -> already a recipient

    audit(session.get("user", "operator"), "campaign_add_recipients", str(cid),
          f"added={added} rejected_no_consent={rejected} dup={dup}")
    msg = f"Added {added} recipient(s)."
    if dup:
        msg += f" {dup} already present."
    if rejected:
        msg += (f" {rejected} rejected (no consent / opted out for '{purpose}'): "
                + ", ".join(rejected_samples) + ("…" if rejected > len(rejected_samples) else ""))
    flash(msg, "success" if added else "error")
    return redirect(url_for("dashboard.campaign_detail", cid=cid))


@bp.route("/campaigns/<int:cid>/questions", methods=["POST"])
@role_required("admin", "operator")
def campaign_add_question(cid):
    campaign = query("SELECT * FROM campaigns WHERE id=?", (cid,), one=True)
    if not campaign or campaign["kind"] != "survey":
        flash("Questions can only be added to a survey campaign.", "error")
        return redirect(url_for("dashboard.campaign_detail", cid=cid))

    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        flash("A question prompt is required.", "error")
        return redirect(url_for("dashboard.campaign_detail", cid=cid))
    try:
        num_digits = max(1, min(10, int(request.form.get("num_digits", "1"))))
    except ValueError:
        num_digits = 1

    choices_json = _parse_choices(request.form.get("choices", ""))

    next_seq = query(
        "SELECT COALESCE(MAX(seq)+1, 0) AS s FROM survey_questions WHERE campaign_id=?",
        (cid,), one=True,
    )["s"]
    execute(
        "INSERT INTO survey_questions (campaign_id, seq, prompt, qtype, num_digits, choices_json) "
        "VALUES (?,?,?, 'dtmf', ?, ?)",
        (cid, next_seq, prompt, num_digits, choices_json),
    )
    flash(f"Added question #{next_seq}.", "success")
    return redirect(url_for("dashboard.campaign_detail", cid=cid))


def _parse_choices(raw):
    """Turn operator input into a JSON map of digit -> label, or None.
    Accepts a JSON object, or a friendly list like '1=Poor, 2=Fair, 3=Good'
    (pairs separated by comma/newline/semicolon)."""
    import json
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            return json.dumps({str(k): str(v) for k, v in data.items()}) if isinstance(data, dict) else None
        except (ValueError, TypeError):
            return None
    pairs = {}
    for part in re.split(r"[,;\n]", raw):
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                pairs[k] = v
    return json.dumps(pairs) if pairs else None


@bp.route("/campaigns/<int:cid>/pause", methods=["POST"])
@role_required("admin", "operator")
def campaign_pause(cid):
    execute("UPDATE campaigns SET status='paused', updated_at=datetime('now') WHERE id=?", (cid,))
    audit(session.get("user", "operator"), "campaign_pause", str(cid))
    flash("Campaign paused. In-progress dialing stops after the current call. "
          "Use Launch / resume to continue.", "success")
    return redirect(url_for("dashboard.campaign_detail", cid=cid))


@bp.route("/campaigns/<int:cid>")
@login_required
def campaign_detail(cid):
    campaign = query("SELECT * FROM campaigns WHERE id=?", (cid,), one=True)
    if not campaign:
        flash("Campaign not found.", "error")
        return redirect(url_for("dashboard.campaigns"))
    recipients = query(
        "SELECT * FROM campaign_recipients WHERE campaign_id=? ORDER BY id", (cid,)
    )
    # Status tally for the progress summary.
    tally = {}
    for r in recipients:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    questions = query(
        "SELECT * FROM survey_questions WHERE campaign_id=? ORDER BY seq", (cid,)
    )
    results = _survey_results(cid, questions) if campaign["kind"] == "survey" else None
    return render_template(
        "campaign_detail.html",
        campaign=campaign, recipients=recipients, tally=tally,
        questions=questions, results=results,
    )


def _survey_results(cid, questions):
    """Per-question answer breakdown with human labels from choices_json.

    Returns a list (one entry per question) of:
        {seq, prompt, total, rows: [{answer, label, count, pct}]}
    Defined choices are always shown (even at 0 responses, so you can see an
    option nobody picked); any unexpected answers are appended after them."""
    raw = query(
        "SELECT question_seq, answer, COUNT(*) AS n FROM survey_answers "
        "WHERE campaign_id=? GROUP BY question_seq, answer",
        (cid,),
    )
    counts = {}  # seq -> {answer: n}
    for r in raw:
        counts.setdefault(r["question_seq"], {})[r["answer"] if r["answer"] not in (None, "") else "—"] = r["n"]

    out = []
    for q in questions:
        seq = q["seq"]
        qcounts = dict(counts.get(seq, {}))
        total = sum(qcounts.values())

        labels = {}
        if q["choices_json"]:
            try:
                labels = {str(k): str(v) for k, v in json.loads(q["choices_json"]).items()}
            except (ValueError, TypeError):
                labels = {}

        rows = []
        seen = set()
        # Defined choices first, in their given order.
        for key, label in labels.items():
            n = qcounts.get(key, 0)
            seen.add(key)
            rows.append({"answer": key, "label": label,
                         "count": n, "pct": round(100 * n / total) if total else 0})
        # Any answers that weren't in the defined choices.
        for key in sorted(k for k in qcounts if k not in seen):
            n = qcounts[key]
            rows.append({"answer": key, "label": "",
                         "count": n, "pct": round(100 * n / total) if total else 0})

        out.append({"seq": seq, "prompt": q["prompt"], "total": total, "rows": rows})
    return out


@bp.route("/campaigns/<int:cid>/launch", methods=["POST"])
@role_required("admin", "operator")
def campaign_launch(cid):
    import jobs

    if jobs.is_running(cid):
        flash("This campaign is already running. Refresh to see progress.", "error")
    elif jobs.launch(cid, actor=session.get("user", "operator")):
        audit(session.get("user", "operator"), "campaign_launch", str(cid))
        flash("Campaign started in the background. Refresh this page to watch progress; "
              "use Pause to stop it.", "success")
    else:
        flash("This campaign is already running.", "error")
    return redirect(url_for("dashboard.campaign_detail", cid=cid))


@bp.route("/campaigns/<int:cid>/results.csv")
@login_required
def campaign_results_csv(cid):
    campaign = query("SELECT * FROM campaigns WHERE id=?", (cid,), one=True)
    if not campaign:
        flash("Campaign not found.", "error")
        return redirect(url_for("dashboard.campaigns"))

    buf = io.StringIO()
    writer = csv.writer(buf)

    # By default answers are exported as their human labels (choices_json);
    # ?raw=1 keeps the raw keypad digits instead.
    raw_mode = request.args.get("raw") == "1"

    if campaign["kind"] == "survey":
        questions = query(
            "SELECT seq, prompt, choices_json FROM survey_questions WHERE campaign_id=? ORDER BY seq", (cid,)
        )
        # Per-question digit -> label maps.
        label_maps = {}
        for q in questions:
            m = {}
            if q["choices_json"]:
                try:
                    m = {str(k): str(v) for k, v in json.loads(q["choices_json"]).items()}
                except (ValueError, TypeError):
                    m = {}
            label_maps[q["seq"]] = m

        def _cell(seq, answer):
            """Label for a recorded answer; raw digit if unlabeled or in raw mode."""
            if answer in (None, ""):
                return ""
            if raw_mode:
                return answer
            return label_maps[seq].get(answer, answer)

        # Header names the question (q0: <prompt>) so a labeled column is readable.
        header = ["phone", "status", "outcome"] + [f"q{q['seq']}: {q['prompt']}" for q in questions]
        writer.writerow(header)
        recipients = query("SELECT * FROM campaign_recipients WHERE campaign_id=? ORDER BY id", (cid,))
        for r in recipients:
            answers = query(
                "SELECT question_seq, answer FROM survey_answers WHERE recipient_id=?", (r["id"],)
            )
            amap = {a["question_seq"]: a["answer"] for a in answers}
            writer.writerow(
                [r["phone_e164"], r["status"], r["outcome"] or ""]
                + [_cell(q["seq"], amap.get(q["seq"], "")) for q in questions]
            )
    else:
        writer.writerow(["phone", "status", "outcome", "attempts", "last_attempt"])
        recipients = query("SELECT * FROM campaign_recipients WHERE campaign_id=? ORDER BY id", (cid,))
        for r in recipients:
            writer.writerow([r["phone_e164"], r["status"], r["outcome"] or "",
                             r["attempts"], r["last_attempt_at"] or ""])

    data = buf.getvalue()
    filename = f"campaign_{cid}_results.csv"

    # When a PGP public key is configured, the CSV (which contains PII) leaves
    # the system encrypted; only the key holder can open it.
    import crypto
    if crypto.exports_enabled():
        try:
            body = crypto.encrypt_bytes(data.encode("utf-8"))
            return Response(
                body,
                mimetype="application/pgp-encrypted",
                headers={"Content-Disposition": f'attachment; filename="{filename}.pgp"'},
            )
        except Exception as e:
            # Fail safe: do NOT silently hand back plaintext PII. Surface the error.
            flash(f"PGP encryption failed, export aborted: {e}", "error")
            return redirect(url_for("dashboard.campaign_detail", cid=cid))

    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE username = ? AND active = 1", (username,), one=True)
        if user and check_password(password, user["password_hash"]):
            session["user"] = user["username"]
            session["role"] = user["role"]
            audit(user["username"], "login")
            nxt = request.args.get("next") or url_for("dashboard.home")
            return redirect(nxt)
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    if session.get("user"):
        audit(session["user"], "logout")
    session.clear()
    return redirect(url_for("dashboard.login"))
