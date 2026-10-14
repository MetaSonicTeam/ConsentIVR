"""
Inbound IVR routing (Flask blueprint).

Call flow:
    POST /ivr/inbound           entry point Twilio hits when a call arrives
      -> business-hours check -> after-hours message / voicemail, or
      -> play greeting + <Gather> digits for the entry menu
    POST /ivr/menu/<menu_key>   handles a pressed digit, routes per config
    POST /ivr/voicemail         records a voicemail (consent announced first)
    POST /ivr/recording-status  Twilio callback with the finished recording

Everything is data-driven from the ivr_menus / ivr_options tables so menus
can be edited from the dashboard without code changes.

Guardrails:
  * No prompt anywhere asks for OTPs, SSNs, card numbers or passcodes.
    The only digit we interpret is a single menu selection.
  * Recording is OFF unless a menu explicitly enables it, and when enabled
    the caller hears the recording notice before any audio is captured.
  * Callers can always opt out (a menu option of type 'optout').
"""

from flask import Blueprint, Response, request
from twilio.twiml.voice_response import Gather, VoiceResponse

from config import Config
from consent import add_opt_out
from db import execute, get_setting, log_ivr_event, query
from hours import is_open
import notify

bp = Blueprint("ivr", __name__, url_prefix="/ivr")

# Import the decorator lazily to avoid a circular import at module load.
from security import verify_twilio_request  # noqa: E402


def _say(vr, text, voice=None):
    voice = voice or Config.POLLY_VOICE
    vr.say(text, voice=voice, language=Config.language_for(voice))


def _menu_voice(menu):
    """Per-menu Polly voice, falling back to the global default."""
    try:
        v = menu["voice"]
    except (KeyError, IndexError, TypeError):
        v = None
    return v or Config.POLLY_VOICE


def _twiml(vr):
    return Response(str(vr), mimetype="text/xml")


def whisper_text():
    """Short announcement the AGENT hears before the caller is bridged in."""
    return f"Connecting a caller for {Config.ORG_NAME}. Press star to decline."


def _transfer(vr, number, action, voice=None):
    """Attended (warm) transfer: dial `number`, play a whisper to the agent
    first (the <Number url> leg), allow the caller to press star to pull out of
    the call, and route to `action` when the dial ends."""
    dial = vr.dial(
        caller_id=Config.TWILIO_CALLER_ID or None,
        action=action,
        method="POST",
        timeout=25,
        record="do-not-record",
        hangup_on_star=True,          # caller presses * to leave the agent call
    )
    dial.number(number, url="/ivr/whisper", method="POST")
    return dial


@bp.route("/whisper", methods=["POST"])
@verify_twilio_request
def whisper():
    """TwiML played to the agent on answer, before the caller is bridged."""
    vr = VoiceResponse()
    _say(vr, whisper_text())
    return _twiml(vr)


def _get_menu(menu_key=None, entry=False):
    if entry:
        return query(
            "SELECT * FROM ivr_menus WHERE is_entry = 1 AND active = 1 LIMIT 1",
            one=True,
        )
    return query(
        "SELECT * FROM ivr_menus WHERE menu_key = ? AND active = 1 LIMIT 1",
        (menu_key,),
        one=True,
    )


def _options_for(menu_id):
    return query(
        "SELECT * FROM ivr_options WHERE menu_id = ? ORDER BY sort_order, digit",
        (menu_id,),
    )


def _ensure_call_row(sid, direction, frm, to, purpose):
    row = query("SELECT id FROM calls WHERE provider_sid = ?", (sid,), one=True)
    if row:
        return row["id"]
    return execute(
        """INSERT INTO calls (provider_sid, direction, from_number, to_number, purpose, status)
           VALUES (?,?,?,?,?,?)""",
        (sid, direction, frm, to, purpose, "in-progress"),
    )


def _render_menu(menu, attempt=1):
    """Build a <Gather> for a menu and return TwiML."""
    vr = VoiceResponse()
    voice = _menu_voice(menu)
    prompt = menu["greeting"] if attempt == 1 else menu["invalid_prompt"] + " " + menu["greeting"]
    gather = Gather(
        num_digits=1,
        action=f"/ivr/menu/{menu['menu_key']}?attempt={attempt}",
        method="POST",
        timeout=7,
    )
    gather.say(prompt, voice=voice, language=Config.language_for(voice))
    vr.append(gather)
    # No input -> re-prompt up to max_attempts, then say goodbye. Never trap.
    if attempt < menu["max_attempts"]:
        vr.redirect(f"/ivr/menu/{menu['menu_key']}?attempt={attempt + 1}&timeout=1", method="POST")
    else:
        _say(vr, "We did not receive a selection. Goodbye.", voice=voice)
        vr.hangup()
    return _twiml(vr)


@bp.route("/inbound", methods=["POST"])
@verify_twilio_request
def inbound():
    sid = request.form.get("CallSid", "")
    frm = request.form.get("From", "")
    to = request.form.get("To", "")
    _ensure_call_row(sid, "inbound", frm, to, "inbound-ivr")
    log_ivr_event(sid, "inbound", f"from={frm}")
    notify.send(f"\U0001F4DE Inbound call from <code>{frm}</code>")

    # Global inbound mode (operator-controlled) can override the normal IVR.
    mode = get_setting("inbound_mode", "ivr")
    if mode == "forward":
        number = get_setting("inbound_forward_number", "")
        if number:
            vr = VoiceResponse()
            _say(vr, "Please hold while we connect you.")
            _transfer(vr, number, action="/ivr/dial-complete")
            log_ivr_event(sid, "route", f"inbound-mode forward -> {number}")
            notify.send(f"→ Inbound forwarded to <code>{number}</code>")
            return _twiml(vr)
        # No forward number configured -> fall through to the normal IVR.
    elif mode == "voicemail":
        log_ivr_event(sid, "route", "inbound-mode voicemail")
        return _start_voicemail(reason="inbound-mode")
    elif mode == "closed":
        vr = VoiceResponse()
        _say(vr, get_setting("inbound_closed_message", "") or (
            f"Thank you for calling {Config.ORG_NAME}. We are currently closed. "
            "Please call again later."))
        vr.hangup()
        log_ivr_event(sid, "route", "inbound-mode closed")
        return _twiml(vr)

    menu = _get_menu(entry=True)
    if menu is None:
        vr = VoiceResponse()
        _say(vr, f"Thank you for calling {Config.ORG_NAME}. Our menu is not configured yet. Goodbye.")
        vr.hangup()
        return _twiml(vr)

    # After-hours handling.
    if not is_open():
        vr = VoiceResponse()
        msg = menu["after_hours_msg"] or (
            f"Thank you for calling {Config.ORG_NAME}. "
            "We are currently closed. Please call back during business hours."
        )
        _say(vr, msg)
        # Offer voicemail after the message.
        vr.redirect("/ivr/voicemail?reason=after-hours", method="POST")
        log_ivr_event(sid, "after-hours")
        return _twiml(vr)

    return _render_menu(menu, attempt=1)


@bp.route("/menu/<menu_key>", methods=["POST"])
@verify_twilio_request
def menu(menu_key):
    sid = request.form.get("CallSid", "")
    digit = request.form.get("Digits", "")
    attempt = int(request.args.get("attempt", "1"))
    is_timeout = request.args.get("timeout") == "1"

    menu = _get_menu(menu_key)
    if menu is None:
        vr = VoiceResponse()
        _say(vr, "That menu is unavailable. Goodbye.")
        vr.hangup()
        return _twiml(vr)

    # A timeout redirect (no input) just re-renders the same menu.
    if is_timeout and not digit:
        return _render_menu(menu, attempt=attempt)

    option = query(
        "SELECT * FROM ivr_options WHERE menu_id = ? AND digit = ?",
        (menu["id"], digit),
        one=True,
    )

    if option is None:
        log_ivr_event(sid, "invalid", f"digit={digit} menu={menu_key}")
        next_attempt = attempt + 1
        if next_attempt > menu["max_attempts"]:
            vr = VoiceResponse()
            _say(vr, "Too many invalid selections. Goodbye.")
            vr.hangup()
            return _twiml(vr)
        return _render_menu(menu, attempt=next_attempt)

    log_ivr_event(sid, "digit", f"digit={digit} -> {option['action_type']}:{option['action_value']}")
    return _route_option(menu, option, sid)


def _route_option(menu, option, sid):
    vr = VoiceResponse()
    action = option["action_type"]
    value = option["action_value"] or ""

    if action == "dial":
        _say(vr, "Connecting you now. Please hold.", voice=_menu_voice(menu))
        _transfer(vr, value, action="/ivr/dial-complete")
        log_ivr_event(sid, "route", f"warm-transfer {value}")
        notify.send(f"→ Call routed to agent/number <code>{value}</code>")

    elif action == "submenu":
        sub = _get_menu(value)
        if sub is None:
            _say(vr, "That option is temporarily unavailable.")
            vr.redirect(f"/ivr/menu/{menu['menu_key']}?attempt=1&timeout=1", method="POST")
        else:
            return _render_menu(sub, attempt=1)

    elif action == "voicemail":
        return _start_voicemail(reason=f"menu:{menu['menu_key']}")

    elif action == "message":
        _say(vr, value or "Thank you.")
        _say(vr, "Returning to the main menu.")
        entry = _get_menu(entry=True)
        if entry:
            return _render_menu(entry, attempt=1)
        vr.hangup()

    elif action == "optout":
        frm = request.form.get("From", "")
        add_opt_out(frm, scope="all", reason="ivr-keypress")
        log_ivr_event(sid, "optout", frm)
        notify.send(f"\U0001F6AB Caller <code>{frm}</code> opted out via IVR")
        _say(vr, "You have been removed from our calling list. You will not receive further calls. Goodbye.")
        vr.hangup()

    elif action == "repeat":
        return _render_menu(menu, attempt=1)

    else:  # 'hangup' or unknown
        _say(vr, "Thank you for calling. Goodbye.")
        vr.hangup()

    return _twiml(vr)


@bp.route("/dial-complete", methods=["POST"])
@verify_twilio_request
def dial_complete():
    """After a transferred call ends: voicemail if the agent didn't pick up,
    otherwise a short post-call menu so the caller can re-enter the IVR (this is
    also where a caller lands after pressing star to leave the agent call)."""
    sid = request.form.get("CallSid", "")
    status = request.form.get("DialCallStatus", "")
    if status in ("no-answer", "busy", "failed", "canceled"):
        log_ivr_event(sid, "route", f"dial unanswered ({status})")
        vr = VoiceResponse()
        _say(vr, "Our team is unavailable right now.")
        return _start_voicemail(reason=f"unanswered:{status}")

    # Completed (agent hung up, or caller pressed star to transfer out).
    entry = _get_menu(entry=True)
    voice = _menu_voice(entry) if entry else None
    vr = VoiceResponse()
    if entry:
        gather = Gather(num_digits=1, action="/ivr/post-call", method="POST", timeout=5)
        gather.say("To return to the main menu, press 1. Otherwise, goodbye.",
                   voice=voice, language=Config.language_for(voice))
        vr.append(gather)
    _say(vr, "Thank you for calling. Goodbye.", voice=voice)
    vr.hangup()
    return _twiml(vr)


@bp.route("/post-call", methods=["POST"])
@verify_twilio_request
def post_call():
    """Caller's choice after a transfer ends: 1 re-enters the IVR, else goodbye."""
    sid = request.form.get("CallSid", "")
    digit = request.form.get("Digits", "")
    if digit == "1":
        entry = _get_menu(entry=True)
        if entry:
            log_ivr_event(sid, "route", "post-call back to menu")
            return _render_menu(entry, attempt=1)
    vr = VoiceResponse()
    _say(vr, "Thank you for calling. Goodbye.")
    vr.hangup()
    return _twiml(vr)


def _start_voicemail(reason=""):
    """Record a voicemail. If recording is globally enabled on the entry menu,
    the caller is told first (recording notice)."""
    sid = request.form.get("CallSid", "")
    entry = _get_menu(entry=True)
    recording_on = bool(entry and entry["recording_enabled"])

    vr = VoiceResponse()
    if recording_on:
        _say(vr, Config.RECORD_NOTICE)
        _say(vr, "Please leave a message after the tone. Press pound when finished.")
        vr.record(
            action="/ivr/voicemail-done",
            method="POST",
            max_length=120,
            finish_on_key="#",
            play_beep=True,
            recording_status_callback="/ivr/recording-status",
            recording_status_callback_method="POST",
        )
        _say(vr, "We did not receive a recording. Goodbye.")
        vr.hangup()
    else:
        # Recording disabled: don't capture audio. Give an alternative.
        phone = Config.ORG_SUPPORT_PHONE
        tail = f" You can also reach us at {phone}." if phone else ""
        _say(vr, f"We are unable to take a message right now.{tail} Goodbye.")
        vr.hangup()
    log_ivr_event(sid, "voicemail", reason)
    return _twiml(vr)


@bp.route("/voicemail", methods=["POST"])
@verify_twilio_request
def voicemail():
    return _start_voicemail(reason=request.args.get("reason", ""))


@bp.route("/voicemail-done", methods=["POST"])
@verify_twilio_request
def voicemail_done():
    sid = request.form.get("CallSid", "")
    vr = VoiceResponse()
    _say(vr, "Thank you. Your message has been recorded. Goodbye.")
    vr.hangup()
    log_ivr_event(sid, "voicemail", "recorded")
    notify.send("\U0001F399 Voicemail left on inbound call")
    return _twiml(vr)


@bp.route("/recording-status", methods=["POST"])
@verify_twilio_request
def recording_status():
    sid = request.form.get("CallSid", "")
    rec_sid = request.form.get("RecordingSid", "")
    rec_url = request.form.get("RecordingUrl", "")
    duration = request.form.get("RecordingDuration", "")
    call = query("SELECT id FROM calls WHERE provider_sid = ?", (sid,), one=True)
    execute(
        """INSERT INTO recordings (call_id, provider_sid, recording_sid, recording_url, duration_sec, kind)
           VALUES (?,?,?,?,?,?)""",
        (call["id"] if call else None, sid, rec_sid, rec_url,
         int(duration) if duration.isdigit() else None, "voicemail"),
    )
    return ("", 204)
