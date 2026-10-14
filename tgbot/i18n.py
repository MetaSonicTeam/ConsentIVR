"""
Internationalization for the Telegram operator bot.

t(locale, key, **kwargs) returns a localized string, falling back to English
when a locale or a key is missing, and finally to the key name itself so a
missing string is visible rather than crashing. Strings use str.format style
{placeholders}; a formatting error degrades to the unformatted template.

Shipping locales: en, es, fr, pt, de. Add a language by adding its dict to
CATALOG (English is the source of truth for the key set). LANGUAGES drives the
in-chat language picker.
"""

import logging

log = logging.getLogger(__name__)

DEFAULT = "en"

# (code, native label) - order shown in the language picker.
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("pt", "Português"),
    ("de", "Deutsch"),
]

_EN = {
    # --- generic ---
    "app_name": "ConsentIVR",
    "nav_choose": "Choose an action:",
    "btn_back": "« Back",
    "btn_home": "🏠 Home",
    "btn_refresh": "🔄 Refresh",
    "btn_cancel": "✖ Cancel",
    "cancelled": "Cancelled.",
    "none": "-",
    "unknown_command": "Unknown command. Send /start for the menu.",
    "error_generic": "Something went wrong handling that. Please try again.",
    "role_denied": "You don't have permission for that action (role: {role}).",
    "rate_limited": "You're going a bit fast - please wait a moment.",
    "masked_note": "Phone numbers are masked.",

    # --- start / help ---
    "start_welcome": "<b>{app}</b> operator console\nSigned in as <b>{role}</b>.",
    "help_text": (
        "<b>{app} - Telegram console</b>\n\n"
        "/start - open the main menu\n"
        "/overview - live stats\n"
        "/campaigns - list campaigns\n"
        "/optout &lt;phone&gt; - suppress a number\n"
        "/validate &lt;phone&gt; - check a number\n"
        "/language - change language\n"
        "/help - this help\n\n"
        "Most things are faster from the buttons on /start."
    ),

    # --- main menu ---
    "menu_title": "<b>{app}</b> - main menu",
    "btn_overview": "📊 Overview",
    "btn_campaigns": "📣 Campaigns",
    "btn_consent": "🛡 Consent & opt-outs",
    "btn_messages": "💬 Messages",
    "btn_inbound": "📞 Inbound mode",
    "btn_validate": "🔎 Validate number",
    "btn_menus": "🗂 IVR menus",
    "btn_language": "🌐 Language",
    "btn_users": "👤 Operators",

    # --- overview ---
    "overview_title": "<b>📊 Overview</b>",
    "stat_contacts": "Contacts",
    "stat_optouts": "Opt-outs",
    "stat_calls_today": "Calls today",
    "stat_active_menus": "Active menus",
    "recent_calls": "<b>Recent calls</b>",
    "recent_events": "<b>Recent IVR events</b>",

    # --- campaigns ---
    "campaigns_title": "<b>📣 Campaigns</b>",
    "campaigns_empty": "No campaigns yet. Create one from the web dashboard.",
    "camp_detail_title": "<b>📣 {name}</b>",
    "camp_field_kind": "Kind",
    "camp_field_channel": "Channel",
    "camp_field_purpose": "Purpose",
    "camp_field_status": "Status",
    "camp_field_progress": "Progress",
    "camp_tally": "<b>Recipients</b>",
    "btn_launch": "▶ Launch / resume",
    "btn_pause": "⏸ Pause",
    "btn_results": "📄 Results CSV",
    "btn_add_recipients": "➕ Add recipients",
    "camp_launched": "✅ Launched. It runs in the background - refresh for progress.",
    "camp_already_running": "This campaign is already running.",
    "camp_launch_failed": "Couldn't launch - it may already be running.",
    "camp_paused": "⏸ Paused. Dialing stops after the current recipient.",
    "camp_results_hint": "Download result CSVs from the web dashboard (they may be PGP-encrypted).",
    "prompt_recipients": (
        "Send the phone numbers to add to <b>{name}</b>, one per line.\n"
        "Optionally add merge data after a comma (becomes the reminder's "
        "<code>{{when}}</code>). Only consented, non-opted-out numbers are kept."
    ),
    "recipients_added": "Added {added}, {dup} already present, {rejected} rejected (no consent / opted out).",

    # --- consent / opt-outs ---
    "consent_title": "<b>🛡 Consent & opt-outs</b>",
    "optouts_recent": "<b>Recent opt-outs</b>",
    "consent_recent": "<b>Recent consent records</b>",
    "btn_add_optout": "🚫 Add opt-out",
    "btn_remove_optout": "♻ Remove opt-out",
    "btn_list_optouts": "📋 List opt-outs",
    "prompt_optout_add": "Send the phone number to add to the opt-out (Do-Not-Call) list.",
    "prompt_optout_remove": "Send the phone number to REMOVE from the opt-out list.",
    "optout_added": "🚫 {phone} added to the opt-out list.",
    "optout_removed": "♻ {phone} removed from the opt-out list.",
    "optout_invalid": "That doesn't look like a valid phone number.",

    # --- messages ---
    "messages_title": "<b>💬 Messages</b>",
    "msg_stat_out": "Outbound",
    "msg_stat_in": "Inbound",
    "msg_stat_delivered": "Delivered",
    "msg_stat_failed": "Failed",
    "messages_recent": "<b>Recent messages</b>",

    # --- inbound mode ---
    "inbound_title": "<b>📞 Inbound mode</b>",
    "inbound_current": "Current mode: <b>{mode}</b>",
    "inbound_choose": "Choose how every inbound call is handled right now:",
    "inbound_mode_ivr": "IVR menu flow",
    "inbound_mode_forward": "Forward all calls",
    "inbound_mode_voicemail": "Straight to voicemail",
    "inbound_mode_closed": "Closed message",
    "inbound_updated": "✅ Inbound mode set to <b>{mode}</b>.",
    "inbound_forward_needs_number": "Forward mode needs a forward-to number first. Send it now:",
    "prompt_forward_number": "Send the number to forward every inbound call to:",

    # --- validate ---
    "validate_title": "<b>🔎 Validate number</b>",
    "prompt_validate": "Send a phone number to validate (offline libphonenumber check).",
    "validate_result": (
        "<b>{input}</b>\n"
        "Valid: <b>{valid}</b>\n"
        "E.164: <code>{e164}</code>\n"
        "Region: {region}\n"
        "Line type: {line_type}\n"
        "Carrier: {carrier}\n"
        "Opted out: <b>{opted_out}</b>"
    ),
    "validate_invalid": "Could not parse that number.",

    # --- IVR menus ---
    "menus_title": "<b>🗂 IVR menus</b>",
    "menus_empty": "No menus configured. Run seed.py or use the dashboard.",
    "menu_entry_tag": "entry",
    "menu_inactive_tag": "inactive",

    # --- language ---
    "language_title": "<b>🌐 Language</b>",
    "language_choose": "Choose your language:",
    "language_set": "✅ Language set to <b>{lang}</b>.",

    # --- users (admin) ---
    "users_title": "<b>👤 Operators</b>",
    "users_empty": "No operators authorized yet (besides env admins).",
    "btn_add_user": "➕ Authorize operator",
    "btn_remove_user": "➖ Revoke",
    "prompt_add_user": (
        "Send the new operator as <code>&lt;telegram_id&gt; &lt;role&gt;</code>\n"
        "role = admin | operator | viewer. Example: <code>123456789 operator</code>\n"
        "They can get their id by sending /start to this bot."
    ),
    "user_added": "✅ Authorized <code>{id}</code> as <b>{role}</b>.",
    "user_removed": "✅ Revoked <code>{id}</code>.",
    "user_invalid": "Use: <telegram_id> <admin|operator|viewer>",
    "user_line": "<code>{id}</code> - <b>{role}</b>{expiry}{inactive}",

    # --- paid access ---
    "unauthorized_title": "🔒 <b>Access required</b>",
    "unauthorized_body": (
        "This is the {app} operator console. Your account isn't authorized yet.\n\n"
        "Your Telegram ID is <code>{id}</code> - send it to an administrator to be "
        "added, or get access below."
    ),
    "btn_pay_stars": "⭐ Pay {n} Stars",
    "btn_pay_crypto": "🪙 Pay {amount} {asset}",
    "btn_learn_more": "ℹ️ Learn more",
    "btn_check_payment": "🔄 I've paid - check",
    "pay_title": "{app} operator access",
    "pay_desc": "Operator access to the {app} console for {days} days.",
    "pay_desc_nolimit": "Operator access to the {app} console.",
    "pay_none_configured": (
        "Paid access isn't set up on this instance. Please contact an administrator "
        "to be added to the allowlist."
    ),
    "pay_crypto_created": (
        "🪙 Invoice created for <b>{amount} {asset}</b>.\n"
        "Pay it, then tap “I've paid - check”."
    ),
    "pay_crypto_unavailable": "Crypto payment isn't available right now.",
    "pay_not_yet": "No completed payment found yet. If you just paid, wait a few seconds and try again.",
    "pay_success": "✅ Payment received - you now have <b>{role}</b> access{expiry}. Send /start.",
    "pay_expiry_suffix": " until {date}",
    "access_expired": "Your access has expired. Use the buttons below to renew.",
}

# --- Spanish --------------------------------------------------------------
_ES = {
    "nav_choose": "Elige una acción:",
    "btn_back": "« Atrás",
    "btn_home": "🏠 Inicio",
    "btn_refresh": "🔄 Actualizar",
    "btn_cancel": "✖ Cancelar",
    "cancelled": "Cancelado.",
    "unknown_command": "Comando desconocido. Envía /start para el menú.",
    "error_generic": "Algo salió mal. Inténtalo de nuevo.",
    "role_denied": "No tienes permiso para esa acción (rol: {role}).",
    "rate_limited": "Vas demasiado rápido, espera un momento.",
    "masked_note": "Los números de teléfono están enmascarados.",
    "start_welcome": "Consola de operador de <b>{app}</b>\nConectado como <b>{role}</b>.",
    "help_text": (
        "<b>{app} - consola de Telegram</b>\n\n"
        "/start - menú principal\n"
        "/overview - estadísticas en vivo\n"
        "/campaigns - listar campañas\n"
        "/optout &lt;teléfono&gt; - suprimir un número\n"
        "/validate &lt;teléfono&gt; - validar un número\n"
        "/language - cambiar idioma\n"
        "/help - esta ayuda\n\n"
        "Casi todo es más rápido con los botones de /start."
    ),
    "menu_title": "<b>{app}</b> - menú principal",
    "btn_overview": "📊 Resumen",
    "btn_campaigns": "📣 Campañas",
    "btn_consent": "🛡 Consentimiento y bajas",
    "btn_messages": "💬 Mensajes",
    "btn_inbound": "📞 Modo entrante",
    "btn_validate": "🔎 Validar número",
    "btn_menus": "🗂 Menús IVR",
    "btn_language": "🌐 Idioma",
    "btn_users": "👤 Operadores",
    "overview_title": "<b>📊 Resumen</b>",
    "stat_contacts": "Contactos",
    "stat_optouts": "Bajas",
    "stat_calls_today": "Llamadas hoy",
    "stat_active_menus": "Menús activos",
    "recent_calls": "<b>Llamadas recientes</b>",
    "recent_events": "<b>Eventos IVR recientes</b>",
    "campaigns_title": "<b>📣 Campañas</b>",
    "campaigns_empty": "Aún no hay campañas. Crea una desde el panel web.",
    "camp_detail_title": "<b>📣 {name}</b>",
    "camp_field_kind": "Tipo",
    "camp_field_channel": "Canal",
    "camp_field_purpose": "Propósito",
    "camp_field_status": "Estado",
    "camp_field_progress": "Progreso",
    "camp_tally": "<b>Destinatarios</b>",
    "btn_launch": "▶ Iniciar / reanudar",
    "btn_pause": "⏸ Pausar",
    "btn_results": "📄 CSV de resultados",
    "btn_add_recipients": "➕ Añadir destinatarios",
    "camp_launched": "✅ Iniciada. Se ejecuta en segundo plano; actualiza para ver el progreso.",
    "camp_already_running": "Esta campaña ya se está ejecutando.",
    "camp_launch_failed": "No se pudo iniciar; puede que ya esté en ejecución.",
    "camp_paused": "⏸ Pausada. La marcación se detiene tras el destinatario actual.",
    "camp_results_hint": "Descarga los CSV de resultados desde el panel web (pueden estar cifrados con PGP).",
    "prompt_recipients": (
        "Envía los números para añadir a <b>{name}</b>, uno por línea.\n"
        "Opcionalmente añade datos tras una coma (será el <code>{{when}}</code> del "
        "recordatorio). Solo se conservan números con consentimiento y sin baja."
    ),
    "recipients_added": "Añadidos {added}, {dup} ya presentes, {rejected} rechazados (sin consentimiento / dados de baja).",
    "consent_title": "<b>🛡 Consentimiento y bajas</b>",
    "optouts_recent": "<b>Bajas recientes</b>",
    "consent_recent": "<b>Consentimientos recientes</b>",
    "btn_add_optout": "🚫 Añadir baja",
    "btn_remove_optout": "♻ Quitar baja",
    "btn_list_optouts": "📋 Listar bajas",
    "prompt_optout_add": "Envía el número para añadir a la lista de bajas (No llamar).",
    "prompt_optout_remove": "Envía el número para QUITAR de la lista de bajas.",
    "optout_added": "🚫 {phone} añadido a la lista de bajas.",
    "optout_removed": "♻ {phone} quitado de la lista de bajas.",
    "optout_invalid": "No parece un número de teléfono válido.",
    "messages_title": "<b>💬 Mensajes</b>",
    "msg_stat_out": "Salientes",
    "msg_stat_in": "Entrantes",
    "msg_stat_delivered": "Entregados",
    "msg_stat_failed": "Fallidos",
    "messages_recent": "<b>Mensajes recientes</b>",
    "inbound_title": "<b>📞 Modo entrante</b>",
    "inbound_current": "Modo actual: <b>{mode}</b>",
    "inbound_choose": "Elige cómo se gestionan ahora todas las llamadas entrantes:",
    "inbound_mode_ivr": "Flujo de menú IVR",
    "inbound_mode_forward": "Desviar todas",
    "inbound_mode_voicemail": "Directo a buzón",
    "inbound_mode_closed": "Mensaje de cerrado",
    "inbound_updated": "✅ Modo entrante establecido en <b>{mode}</b>.",
    "inbound_forward_needs_number": "El modo desvío necesita un número de destino. Envíalo ahora:",
    "prompt_forward_number": "Envía el número al que desviar todas las llamadas entrantes:",
    "validate_title": "<b>🔎 Validar número</b>",
    "prompt_validate": "Envía un número para validar (comprobación offline libphonenumber).",
    "validate_result": (
        "<b>{input}</b>\n"
        "Válido: <b>{valid}</b>\n"
        "E.164: <code>{e164}</code>\n"
        "Región: {region}\n"
        "Tipo de línea: {line_type}\n"
        "Operadora: {carrier}\n"
        "Dado de baja: <b>{opted_out}</b>"
    ),
    "validate_invalid": "No se pudo interpretar ese número.",
    "menus_title": "<b>🗂 Menús IVR</b>",
    "menus_empty": "No hay menús configurados. Ejecuta seed.py o usa el panel.",
    "menu_entry_tag": "entrada",
    "menu_inactive_tag": "inactivo",
    "language_title": "<b>🌐 Idioma</b>",
    "language_choose": "Elige tu idioma:",
    "language_set": "✅ Idioma establecido en <b>{lang}</b>.",
    "users_title": "<b>👤 Operadores</b>",
    "users_empty": "Aún no hay operadores autorizados (además de los admin del entorno).",
    "btn_add_user": "➕ Autorizar operador",
    "btn_remove_user": "➖ Revocar",
    "prompt_add_user": (
        "Envía el nuevo operador como <code>&lt;telegram_id&gt; &lt;rol&gt;</code>\n"
        "rol = admin | operator | viewer. Ejemplo: <code>123456789 operator</code>\n"
        "Pueden obtener su id enviando /start a este bot."
    ),
    "user_added": "✅ Autorizado <code>{id}</code> como <b>{role}</b>.",
    "user_removed": "✅ Revocado <code>{id}</code>.",
    "user_invalid": "Usa: <telegram_id> <admin|operator|viewer>",
    "user_line": "<code>{id}</code> - <b>{role}</b>{expiry}{inactive}",
    "unauthorized_title": "🔒 <b>Acceso requerido</b>",
    "unauthorized_body": (
        "Esta es la consola de operador de {app}. Tu cuenta aún no está autorizada.\n\n"
        "Tu ID de Telegram es <code>{id}</code>: envíalo a un administrador para que te "
        "añada, u obtén acceso abajo."
    ),
    "btn_pay_stars": "⭐ Pagar {n} Stars",
    "btn_pay_crypto": "🪙 Pagar {amount} {asset}",
    "btn_learn_more": "ℹ️ Más información",
    "btn_check_payment": "🔄 Ya pagué - comprobar",
    "pay_title": "Acceso de operador {app}",
    "pay_desc": "Acceso de operador a la consola {app} durante {days} días.",
    "pay_desc_nolimit": "Acceso de operador a la consola {app}.",
    "pay_none_configured": (
        "El acceso de pago no está configurado en esta instancia. Contacta a un "
        "administrador para que te añada a la lista."
    ),
    "pay_crypto_created": (
        "🪙 Factura creada por <b>{amount} {asset}</b>.\n"
        "Págala y pulsa «Ya pagué - comprobar»."
    ),
    "pay_crypto_unavailable": "El pago con cripto no está disponible ahora.",
    "pay_not_yet": "Aún no se encontró un pago completado. Si acabas de pagar, espera unos segundos y reintenta.",
    "pay_success": "✅ Pago recibido: ahora tienes acceso <b>{role}</b>{expiry}. Envía /start.",
    "pay_expiry_suffix": " hasta {date}",
    "access_expired": "Tu acceso ha caducado. Usa los botones de abajo para renovar.",
}

# --- French ---------------------------------------------------------------
_FR = {
    "nav_choose": "Choisissez une action :",
    "btn_back": "« Retour",
    "btn_home": "🏠 Accueil",
    "btn_refresh": "🔄 Actualiser",
    "btn_cancel": "✖ Annuler",
    "cancelled": "Annulé.",
    "unknown_command": "Commande inconnue. Envoyez /start pour le menu.",
    "error_generic": "Une erreur est survenue. Réessayez.",
    "role_denied": "Vous n'avez pas la permission (rôle : {role}).",
    "rate_limited": "Vous allez un peu vite, patientez un instant.",
    "masked_note": "Les numéros de téléphone sont masqués.",
    "start_welcome": "Console opérateur <b>{app}</b>\nConnecté en tant que <b>{role}</b>.",
    "help_text": (
        "<b>{app} - console Telegram</b>\n\n"
        "/start - menu principal\n"
        "/overview - statistiques en direct\n"
        "/campaigns - lister les campagnes\n"
        "/optout &lt;numéro&gt; - supprimer un numéro\n"
        "/validate &lt;numéro&gt; - vérifier un numéro\n"
        "/language - changer de langue\n"
        "/help - cette aide\n\n"
        "Le plus rapide reste les boutons de /start."
    ),
    "menu_title": "<b>{app}</b> - menu principal",
    "btn_overview": "📊 Aperçu",
    "btn_campaigns": "📣 Campagnes",
    "btn_consent": "🛡 Consentement & retraits",
    "btn_messages": "💬 Messages",
    "btn_inbound": "📞 Mode entrant",
    "btn_validate": "🔎 Valider un numéro",
    "btn_menus": "🗂 Menus SVI",
    "btn_language": "🌐 Langue",
    "btn_users": "👤 Opérateurs",
    "overview_title": "<b>📊 Aperçu</b>",
    "stat_contacts": "Contacts",
    "stat_optouts": "Retraits",
    "stat_calls_today": "Appels aujourd'hui",
    "stat_active_menus": "Menus actifs",
    "recent_calls": "<b>Appels récents</b>",
    "recent_events": "<b>Événements SVI récents</b>",
    "campaigns_title": "<b>📣 Campagnes</b>",
    "campaigns_empty": "Aucune campagne. Créez-en une depuis le tableau de bord web.",
    "camp_detail_title": "<b>📣 {name}</b>",
    "camp_field_kind": "Type",
    "camp_field_channel": "Canal",
    "camp_field_purpose": "Objet",
    "camp_field_status": "Statut",
    "camp_field_progress": "Progression",
    "camp_tally": "<b>Destinataires</b>",
    "btn_launch": "▶ Lancer / reprendre",
    "btn_pause": "⏸ Pause",
    "btn_results": "📄 CSV des résultats",
    "btn_add_recipients": "➕ Ajouter des destinataires",
    "camp_launched": "✅ Lancée. Elle tourne en arrière-plan ; actualisez pour la progression.",
    "camp_already_running": "Cette campagne est déjà en cours.",
    "camp_launch_failed": "Impossible de lancer - elle est peut-être déjà en cours.",
    "camp_paused": "⏸ En pause. La numérotation s'arrête après le destinataire en cours.",
    "camp_results_hint": "Téléchargez les CSV depuis le tableau de bord web (ils peuvent être chiffrés PGP).",
    "prompt_recipients": (
        "Envoyez les numéros à ajouter à <b>{name}</b>, un par ligne.\n"
        "Vous pouvez ajouter des données après une virgule (devient le "
        "<code>{{when}}</code> du rappel). Seuls les numéros consentants et non retirés sont gardés."
    ),
    "recipients_added": "Ajoutés {added}, {dup} déjà présents, {rejected} rejetés (pas de consentement / retirés).",
    "consent_title": "<b>🛡 Consentement & retraits</b>",
    "optouts_recent": "<b>Retraits récents</b>",
    "consent_recent": "<b>Consentements récents</b>",
    "btn_add_optout": "🚫 Ajouter un retrait",
    "btn_remove_optout": "♻ Retirer un retrait",
    "btn_list_optouts": "📋 Lister les retraits",
    "prompt_optout_add": "Envoyez le numéro à ajouter à la liste de retrait (Ne pas appeler).",
    "prompt_optout_remove": "Envoyez le numéro à RETIRER de la liste de retrait.",
    "optout_added": "🚫 {phone} ajouté à la liste de retrait.",
    "optout_removed": "♻ {phone} retiré de la liste de retrait.",
    "optout_invalid": "Cela ne ressemble pas à un numéro valide.",
    "messages_title": "<b>💬 Messages</b>",
    "msg_stat_out": "Sortants",
    "msg_stat_in": "Entrants",
    "msg_stat_delivered": "Livrés",
    "msg_stat_failed": "Échecs",
    "messages_recent": "<b>Messages récents</b>",
    "inbound_title": "<b>📞 Mode entrant</b>",
    "inbound_current": "Mode actuel : <b>{mode}</b>",
    "inbound_choose": "Choisissez le traitement de tous les appels entrants maintenant :",
    "inbound_mode_ivr": "Flux de menu SVI",
    "inbound_mode_forward": "Tout transférer",
    "inbound_mode_voicemail": "Directement à la messagerie",
    "inbound_mode_closed": "Message de fermeture",
    "inbound_updated": "✅ Mode entrant réglé sur <b>{mode}</b>.",
    "inbound_forward_needs_number": "Le mode transfert requiert un numéro de destination. Envoyez-le :",
    "prompt_forward_number": "Envoyez le numéro vers lequel transférer tous les appels entrants :",
    "validate_title": "<b>🔎 Valider un numéro</b>",
    "prompt_validate": "Envoyez un numéro à valider (contrôle hors-ligne libphonenumber).",
    "validate_result": (
        "<b>{input}</b>\n"
        "Valide : <b>{valid}</b>\n"
        "E.164 : <code>{e164}</code>\n"
        "Région : {region}\n"
        "Type de ligne : {line_type}\n"
        "Opérateur : {carrier}\n"
        "Retiré : <b>{opted_out}</b>"
    ),
    "validate_invalid": "Impossible d'analyser ce numéro.",
    "menus_title": "<b>🗂 Menus SVI</b>",
    "menus_empty": "Aucun menu configuré. Lancez seed.py ou utilisez le tableau de bord.",
    "menu_entry_tag": "entrée",
    "menu_inactive_tag": "inactif",
    "language_title": "<b>🌐 Langue</b>",
    "language_choose": "Choisissez votre langue :",
    "language_set": "✅ Langue réglée sur <b>{lang}</b>.",
    "users_title": "<b>👤 Opérateurs</b>",
    "users_empty": "Aucun opérateur autorisé pour l'instant (hors admins d'environnement).",
    "btn_add_user": "➕ Autoriser un opérateur",
    "btn_remove_user": "➖ Révoquer",
    "prompt_add_user": (
        "Envoyez le nouvel opérateur sous la forme <code>&lt;telegram_id&gt; &lt;rôle&gt;</code>\n"
        "rôle = admin | operator | viewer. Exemple : <code>123456789 operator</code>\n"
        "Il peut obtenir son id en envoyant /start à ce bot."
    ),
    "user_added": "✅ Autorisé <code>{id}</code> comme <b>{role}</b>.",
    "user_removed": "✅ Révoqué <code>{id}</code>.",
    "user_invalid": "Utilisez : <telegram_id> <admin|operator|viewer>",
    "user_line": "<code>{id}</code> - <b>{role}</b>{expiry}{inactive}",
    "unauthorized_title": "🔒 <b>Accès requis</b>",
    "unauthorized_body": (
        "Ceci est la console opérateur {app}. Votre compte n'est pas encore autorisé.\n\n"
        "Votre identifiant Telegram est <code>{id}</code> - envoyez-le à un administrateur "
        "pour être ajouté, ou obtenez l'accès ci-dessous."
    ),
    "btn_pay_stars": "⭐ Payer {n} Stars",
    "btn_pay_crypto": "🪙 Payer {amount} {asset}",
    "btn_learn_more": "ℹ️ En savoir plus",
    "btn_check_payment": "🔄 J'ai payé - vérifier",
    "pay_title": "Accès opérateur {app}",
    "pay_desc": "Accès opérateur à la console {app} pendant {days} jours.",
    "pay_desc_nolimit": "Accès opérateur à la console {app}.",
    "pay_none_configured": (
        "L'accès payant n'est pas configuré sur cette instance. Contactez un "
        "administrateur pour être ajouté à la liste."
    ),
    "pay_crypto_created": (
        "🪙 Facture créée pour <b>{amount} {asset}</b>.\n"
        "Payez-la puis appuyez sur « J'ai payé - vérifier »."
    ),
    "pay_crypto_unavailable": "Le paiement en crypto n'est pas disponible actuellement.",
    "pay_not_yet": "Aucun paiement finalisé pour l'instant. Si vous venez de payer, patientez puis réessayez.",
    "pay_success": "✅ Paiement reçu - vous avez l'accès <b>{role}</b>{expiry}. Envoyez /start.",
    "pay_expiry_suffix": " jusqu'au {date}",
    "access_expired": "Votre accès a expiré. Utilisez les boutons ci-dessous pour renouveler.",
}

# --- Portuguese -----------------------------------------------------------
_PT = {
    "nav_choose": "Escolha uma ação:",
    "btn_back": "« Voltar",
    "btn_home": "🏠 Início",
    "btn_refresh": "🔄 Atualizar",
    "btn_cancel": "✖ Cancelar",
    "cancelled": "Cancelado.",
    "unknown_command": "Comando desconhecido. Envie /start para o menu.",
    "error_generic": "Algo deu errado. Tente novamente.",
    "role_denied": "Você não tem permissão para essa ação (função: {role}).",
    "rate_limited": "Você está indo rápido demais - aguarde um momento.",
    "masked_note": "Os números de telefone estão mascarados.",
    "start_welcome": "Console de operador do <b>{app}</b>\nConectado como <b>{role}</b>.",
    "help_text": (
        "<b>{app} - console do Telegram</b>\n\n"
        "/start - menu principal\n"
        "/overview - estatísticas ao vivo\n"
        "/campaigns - listar campanhas\n"
        "/optout &lt;telefone&gt; - suprimir um número\n"
        "/validate &lt;telefone&gt; - validar um número\n"
        "/language - mudar idioma\n"
        "/help - esta ajuda\n\n"
        "Quase tudo é mais rápido pelos botões do /start."
    ),
    "menu_title": "<b>{app}</b> - menu principal",
    "btn_overview": "📊 Visão geral",
    "btn_campaigns": "📣 Campanhas",
    "btn_consent": "🛡 Consentimento e exclusões",
    "btn_messages": "💬 Mensagens",
    "btn_inbound": "📞 Modo de entrada",
    "btn_validate": "🔎 Validar número",
    "btn_menus": "🗂 Menus URA",
    "btn_language": "🌐 Idioma",
    "btn_users": "👤 Operadores",
    "overview_title": "<b>📊 Visão geral</b>",
    "stat_contacts": "Contatos",
    "stat_optouts": "Exclusões",
    "stat_calls_today": "Chamadas hoje",
    "stat_active_menus": "Menus ativos",
    "recent_calls": "<b>Chamadas recentes</b>",
    "recent_events": "<b>Eventos de URA recentes</b>",
    "campaigns_title": "<b>📣 Campanhas</b>",
    "campaigns_empty": "Ainda não há campanhas. Crie uma no painel web.",
    "camp_detail_title": "<b>📣 {name}</b>",
    "camp_field_kind": "Tipo",
    "camp_field_channel": "Canal",
    "camp_field_purpose": "Finalidade",
    "camp_field_status": "Status",
    "camp_field_progress": "Progresso",
    "camp_tally": "<b>Destinatários</b>",
    "btn_launch": "▶ Iniciar / retomar",
    "btn_pause": "⏸ Pausar",
    "btn_results": "📄 CSV de resultados",
    "btn_add_recipients": "➕ Adicionar destinatários",
    "camp_launched": "✅ Iniciada. Roda em segundo plano; atualize para ver o progresso.",
    "camp_already_running": "Esta campanha já está em execução.",
    "camp_launch_failed": "Não foi possível iniciar - pode já estar em execução.",
    "camp_paused": "⏸ Pausada. A discagem para após o destinatário atual.",
    "camp_results_hint": "Baixe os CSVs de resultados no painel web (podem estar criptografados com PGP).",
    "prompt_recipients": (
        "Envie os números para adicionar a <b>{name}</b>, um por linha.\n"
        "Opcionalmente adicione dados após uma vírgula (vira o <code>{{when}}</code> do "
        "lembrete). Apenas números com consentimento e sem exclusão são mantidos."
    ),
    "recipients_added": "Adicionados {added}, {dup} já presentes, {rejected} rejeitados (sem consentimento / excluídos).",
    "consent_title": "<b>🛡 Consentimento e exclusões</b>",
    "optouts_recent": "<b>Exclusões recentes</b>",
    "consent_recent": "<b>Consentimentos recentes</b>",
    "btn_add_optout": "🚫 Adicionar exclusão",
    "btn_remove_optout": "♻ Remover exclusão",
    "btn_list_optouts": "📋 Listar exclusões",
    "prompt_optout_add": "Envie o número para adicionar à lista de exclusão (Não Perturbe).",
    "prompt_optout_remove": "Envie o número para REMOVER da lista de exclusão.",
    "optout_added": "🚫 {phone} adicionado à lista de exclusão.",
    "optout_removed": "♻ {phone} removido da lista de exclusão.",
    "optout_invalid": "Isso não parece um número de telefone válido.",
    "messages_title": "<b>💬 Mensagens</b>",
    "msg_stat_out": "Enviadas",
    "msg_stat_in": "Recebidas",
    "msg_stat_delivered": "Entregues",
    "msg_stat_failed": "Falhas",
    "messages_recent": "<b>Mensagens recentes</b>",
    "inbound_title": "<b>📞 Modo de entrada</b>",
    "inbound_current": "Modo atual: <b>{mode}</b>",
    "inbound_choose": "Escolha como todas as chamadas de entrada são tratadas agora:",
    "inbound_mode_ivr": "Fluxo de menu URA",
    "inbound_mode_forward": "Encaminhar todas",
    "inbound_mode_voicemail": "Direto para o correio de voz",
    "inbound_mode_closed": "Mensagem de fechado",
    "inbound_updated": "✅ Modo de entrada definido como <b>{mode}</b>.",
    "inbound_forward_needs_number": "O modo de encaminhamento precisa de um número de destino. Envie-o:",
    "prompt_forward_number": "Envie o número para onde encaminhar todas as chamadas de entrada:",
    "validate_title": "<b>🔎 Validar número</b>",
    "prompt_validate": "Envie um número para validar (verificação offline libphonenumber).",
    "validate_result": (
        "<b>{input}</b>\n"
        "Válido: <b>{valid}</b>\n"
        "E.164: <code>{e164}</code>\n"
        "Região: {region}\n"
        "Tipo de linha: {line_type}\n"
        "Operadora: {carrier}\n"
        "Excluído: <b>{opted_out}</b>"
    ),
    "validate_invalid": "Não foi possível interpretar esse número.",
    "menus_title": "<b>🗂 Menus URA</b>",
    "menus_empty": "Nenhum menu configurado. Execute seed.py ou use o painel.",
    "menu_entry_tag": "entrada",
    "menu_inactive_tag": "inativo",
    "language_title": "<b>🌐 Idioma</b>",
    "language_choose": "Escolha seu idioma:",
    "language_set": "✅ Idioma definido como <b>{lang}</b>.",
    "users_title": "<b>👤 Operadores</b>",
    "users_empty": "Nenhum operador autorizado ainda (além dos admins do ambiente).",
    "btn_add_user": "➕ Autorizar operador",
    "btn_remove_user": "➖ Revogar",
    "prompt_add_user": (
        "Envie o novo operador como <code>&lt;telegram_id&gt; &lt;função&gt;</code>\n"
        "função = admin | operator | viewer. Exemplo: <code>123456789 operator</code>\n"
        "Ele pode obter o id enviando /start para este bot."
    ),
    "user_added": "✅ Autorizado <code>{id}</code> como <b>{role}</b>.",
    "user_removed": "✅ Revogado <code>{id}</code>.",
    "user_invalid": "Use: <telegram_id> <admin|operator|viewer>",
    "user_line": "<code>{id}</code> - <b>{role}</b>{expiry}{inactive}",
    "unauthorized_title": "🔒 <b>Acesso necessário</b>",
    "unauthorized_body": (
        "Este é o console de operador do {app}. Sua conta ainda não está autorizada.\n\n"
        "Seu ID do Telegram é <code>{id}</code> - envie-o a um administrador para ser "
        "adicionado, ou obtenha acesso abaixo."
    ),
    "btn_pay_stars": "⭐ Pagar {n} Stars",
    "btn_pay_crypto": "🪙 Pagar {amount} {asset}",
    "btn_learn_more": "ℹ️ Saiba mais",
    "btn_check_payment": "🔄 Paguei - verificar",
    "pay_title": "Acesso de operador {app}",
    "pay_desc": "Acesso de operador ao console {app} por {days} dias.",
    "pay_desc_nolimit": "Acesso de operador ao console {app}.",
    "pay_none_configured": (
        "O acesso pago não está configurado nesta instância. Contate um administrador "
        "para ser adicionado à lista."
    ),
    "pay_crypto_created": (
        "🪙 Fatura criada de <b>{amount} {asset}</b>.\n"
        "Pague e toque em “Paguei - verificar”."
    ),
    "pay_crypto_unavailable": "O pagamento em cripto não está disponível agora.",
    "pay_not_yet": "Nenhum pagamento concluído ainda. Se você acabou de pagar, aguarde alguns segundos e tente de novo.",
    "pay_success": "✅ Pagamento recebido - você agora tem acesso <b>{role}</b>{expiry}. Envie /start.",
    "pay_expiry_suffix": " até {date}",
    "access_expired": "Seu acesso expirou. Use os botões abaixo para renovar.",
}

# --- German ---------------------------------------------------------------
_DE = {
    "nav_choose": "Aktion wählen:",
    "btn_back": "« Zurück",
    "btn_home": "🏠 Start",
    "btn_refresh": "🔄 Aktualisieren",
    "btn_cancel": "✖ Abbrechen",
    "cancelled": "Abgebrochen.",
    "unknown_command": "Unbekannter Befehl. Sende /start für das Menü.",
    "error_generic": "Etwas ist schiefgelaufen. Bitte erneut versuchen.",
    "role_denied": "Du hast keine Berechtigung dafür (Rolle: {role}).",
    "rate_limited": "Etwas zu schnell - bitte kurz warten.",
    "masked_note": "Telefonnummern sind maskiert.",
    "start_welcome": "<b>{app}</b> Bedienkonsole\nAngemeldet als <b>{role}</b>.",
    "help_text": (
        "<b>{app} - Telegram-Konsole</b>\n\n"
        "/start - Hauptmenü\n"
        "/overview - Live-Statistiken\n"
        "/campaigns - Kampagnen auflisten\n"
        "/optout &lt;Nummer&gt; - Nummer sperren\n"
        "/validate &lt;Nummer&gt; - Nummer prüfen\n"
        "/language - Sprache ändern\n"
        "/help - diese Hilfe\n\n"
        "Das meiste geht schneller über die Buttons bei /start."
    ),
    "menu_title": "<b>{app}</b> - Hauptmenü",
    "btn_overview": "📊 Übersicht",
    "btn_campaigns": "📣 Kampagnen",
    "btn_consent": "🛡 Einwilligung & Sperren",
    "btn_messages": "💬 Nachrichten",
    "btn_inbound": "📞 Eingangsmodus",
    "btn_validate": "🔎 Nummer prüfen",
    "btn_menus": "🗂 IVR-Menüs",
    "btn_language": "🌐 Sprache",
    "btn_users": "👤 Bediener",
    "overview_title": "<b>📊 Übersicht</b>",
    "stat_contacts": "Kontakte",
    "stat_optouts": "Sperren",
    "stat_calls_today": "Anrufe heute",
    "stat_active_menus": "Aktive Menüs",
    "recent_calls": "<b>Letzte Anrufe</b>",
    "recent_events": "<b>Letzte IVR-Ereignisse</b>",
    "campaigns_title": "<b>📣 Kampagnen</b>",
    "campaigns_empty": "Noch keine Kampagnen. Erstelle eine im Web-Dashboard.",
    "camp_detail_title": "<b>📣 {name}</b>",
    "camp_field_kind": "Art",
    "camp_field_channel": "Kanal",
    "camp_field_purpose": "Zweck",
    "camp_field_status": "Status",
    "camp_field_progress": "Fortschritt",
    "camp_tally": "<b>Empfänger</b>",
    "btn_launch": "▶ Starten / fortsetzen",
    "btn_pause": "⏸ Pausieren",
    "btn_results": "📄 Ergebnis-CSV",
    "btn_add_recipients": "➕ Empfänger hinzufügen",
    "camp_launched": "✅ Gestartet. Läuft im Hintergrund - zum Fortschritt aktualisieren.",
    "camp_already_running": "Diese Kampagne läuft bereits.",
    "camp_launch_failed": "Start nicht möglich - läuft evtl. schon.",
    "camp_paused": "⏸ Pausiert. Die Wahl stoppt nach dem aktuellen Empfänger.",
    "camp_results_hint": "Lade die Ergebnis-CSVs im Web-Dashboard herunter (evtl. PGP-verschlüsselt).",
    "prompt_recipients": (
        "Sende die Nummern für <b>{name}</b>, eine pro Zeile.\n"
        "Optional nach einem Komma Zusatzdaten (wird zum <code>{{when}}</code> der "
        "Erinnerung). Nur eingewilligte, nicht gesperrte Nummern werden übernommen."
    ),
    "recipients_added": "{added} hinzugefügt, {dup} bereits vorhanden, {rejected} abgelehnt (keine Einwilligung / gesperrt).",
    "consent_title": "<b>🛡 Einwilligung & Sperren</b>",
    "optouts_recent": "<b>Letzte Sperren</b>",
    "consent_recent": "<b>Letzte Einwilligungen</b>",
    "btn_add_optout": "🚫 Sperre hinzufügen",
    "btn_remove_optout": "♻ Sperre entfernen",
    "btn_list_optouts": "📋 Sperren auflisten",
    "prompt_optout_add": "Sende die Nummer für die Sperrliste (Nicht anrufen).",
    "prompt_optout_remove": "Sende die Nummer, die aus der Sperrliste ENTFERNT werden soll.",
    "optout_added": "🚫 {phone} zur Sperrliste hinzugefügt.",
    "optout_removed": "♻ {phone} aus der Sperrliste entfernt.",
    "optout_invalid": "Das sieht nicht nach einer gültigen Nummer aus.",
    "messages_title": "<b>💬 Nachrichten</b>",
    "msg_stat_out": "Ausgehend",
    "msg_stat_in": "Eingehend",
    "msg_stat_delivered": "Zugestellt",
    "msg_stat_failed": "Fehlgeschlagen",
    "messages_recent": "<b>Letzte Nachrichten</b>",
    "inbound_title": "<b>📞 Eingangsmodus</b>",
    "inbound_current": "Aktueller Modus: <b>{mode}</b>",
    "inbound_choose": "Wähle, wie alle eingehenden Anrufe jetzt behandelt werden:",
    "inbound_mode_ivr": "IVR-Menüfluss",
    "inbound_mode_forward": "Alle weiterleiten",
    "inbound_mode_voicemail": "Direkt zur Mailbox",
    "inbound_mode_closed": "Geschlossen-Nachricht",
    "inbound_updated": "✅ Eingangsmodus auf <b>{mode}</b> gesetzt.",
    "inbound_forward_needs_number": "Der Weiterleitungsmodus braucht zuerst eine Zielnummer. Sende sie:",
    "prompt_forward_number": "Sende die Nummer, an die alle eingehenden Anrufe weitergeleitet werden:",
    "validate_title": "<b>🔎 Nummer prüfen</b>",
    "prompt_validate": "Sende eine Nummer zur Prüfung (offline libphonenumber).",
    "validate_result": (
        "<b>{input}</b>\n"
        "Gültig: <b>{valid}</b>\n"
        "E.164: <code>{e164}</code>\n"
        "Region: {region}\n"
        "Anschlussart: {line_type}\n"
        "Anbieter: {carrier}\n"
        "Gesperrt: <b>{opted_out}</b>"
    ),
    "validate_invalid": "Diese Nummer konnte nicht geparst werden.",
    "menus_title": "<b>🗂 IVR-Menüs</b>",
    "menus_empty": "Keine Menüs konfiguriert. seed.py ausführen oder Dashboard nutzen.",
    "menu_entry_tag": "Einstieg",
    "menu_inactive_tag": "inaktiv",
    "language_title": "<b>🌐 Sprache</b>",
    "language_choose": "Wähle deine Sprache:",
    "language_set": "✅ Sprache auf <b>{lang}</b> gesetzt.",
    "users_title": "<b>👤 Bediener</b>",
    "users_empty": "Noch keine Bediener autorisiert (außer Umgebungs-Admins).",
    "btn_add_user": "➕ Bediener autorisieren",
    "btn_remove_user": "➖ Entziehen",
    "prompt_add_user": (
        "Sende den neuen Bediener als <code>&lt;telegram_id&gt; &lt;Rolle&gt;</code>\n"
        "Rolle = admin | operator | viewer. Beispiel: <code>123456789 operator</code>\n"
        "Die ID bekommt man per /start an diesen Bot."
    ),
    "user_added": "✅ <code>{id}</code> als <b>{role}</b> autorisiert.",
    "user_removed": "✅ <code>{id}</code> entzogen.",
    "user_invalid": "Nutze: <telegram_id> <admin|operator|viewer>",
    "user_line": "<code>{id}</code> - <b>{role}</b>{expiry}{inactive}",
    "unauthorized_title": "🔒 <b>Zugang erforderlich</b>",
    "unauthorized_body": (
        "Dies ist die {app}-Bedienkonsole. Dein Konto ist noch nicht autorisiert.\n\n"
        "Deine Telegram-ID ist <code>{id}</code> - sende sie einem Administrator zum "
        "Freischalten, oder hole dir unten Zugang."
    ),
    "btn_pay_stars": "⭐ {n} Stars zahlen",
    "btn_pay_crypto": "🪙 {amount} {asset} zahlen",
    "btn_learn_more": "ℹ️ Mehr erfahren",
    "btn_check_payment": "🔄 Bezahlt - prüfen",
    "pay_title": "{app} Bedienerzugang",
    "pay_desc": "Bedienerzugang zur {app}-Konsole für {days} Tage.",
    "pay_desc_nolimit": "Bedienerzugang zur {app}-Konsole.",
    "pay_none_configured": (
        "Bezahlter Zugang ist auf dieser Instanz nicht eingerichtet. Bitte einen "
        "Administrator um Aufnahme in die Liste."
    ),
    "pay_crypto_created": (
        "🪙 Rechnung über <b>{amount} {asset}</b> erstellt.\n"
        "Bezahle sie und tippe „Bezahlt - prüfen“."
    ),
    "pay_crypto_unavailable": "Krypto-Zahlung ist derzeit nicht verfügbar.",
    "pay_not_yet": "Noch keine abgeschlossene Zahlung gefunden. Falls gerade bezahlt, kurz warten und erneut versuchen.",
    "pay_success": "✅ Zahlung erhalten - du hast jetzt <b>{role}</b>-Zugang{expiry}. Sende /start.",
    "pay_expiry_suffix": " bis {date}",
    "access_expired": "Dein Zugang ist abgelaufen. Nutze die Buttons unten zum Verlängern.",
}

CATALOG = {"en": _EN, "es": _ES, "fr": _FR, "pt": _PT, "de": _DE}


def normalize_locale(code: str) -> str:
    """Map a Telegram language_code (e.g. 'es-419', 'pt-BR') to a shipped
    locale, falling back to the default."""
    if not code:
        return DEFAULT
    code = code.lower().replace("_", "-").split("-", 1)[0]
    return code if code in CATALOG else DEFAULT


def t(locale: str, key: str, **kwargs) -> str:
    table = CATALOG.get(locale or DEFAULT, _EN)
    template = table.get(key) or _EN.get(key) or key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        # Missing/extra placeholder - show the template rather than crash.
        return template
