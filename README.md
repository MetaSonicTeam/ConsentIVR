# ConsentIVR

![ConsentIVR Banner](https://raw.githubusercontent.com/MetaSonicTeam/ConsentIVR/main/doc/ConsentIVR-logo/banner/consentivr-social-header-1500x500@2x.png)

**Consent-first voice, SMS, and WhatsApp communications — enforced in code.**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-%23000.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Telegram Bot](https://img.shields.io/badge/telegram-bot-%2326A5E4.svg?logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![Twilio](https://img.shields.io/badge/twilio-%23F22F46.svg?logo=twilio&logoColor=white)](https://www.twilio.com/)
[![Telnyx](https://img.shields.io/badge/telnyx-%2300E3B0.svg)](https://telnyx.com/)
[![Plivo](https://img.shields.io/badge/plivo-%23F76B1C.svg)](https://www.plivo.com/)
[![Vonage](https://img.shields.io/badge/vonage-%23000000.svg)](https://www.vonage.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/MetaSonicTeam/ConsentIVR/pulls)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()

ConsentIVR is a Flask-based inbound IVR and opt-in outbound communications platform. It combines editable call menus, appointment reminders and surveys, consent and opt-out enforcement, a web dashboard, and an interactive Telegram operator console.

> **Project artifact:** https://metasonic.ca/blog_post.php?slug=consentivr-consent-first-voice-sms-whatsapp-platform

## Overview

ConsentIVR is designed for organizations that need to manage inbound calls and contact consenting recipients through voice, SMS, or WhatsApp. Call menus, business hours, campaigns, and recipients are stored in the database so operators can change routing and campaign settings without editing application code.

Key design goals:

- Consent checks before outbound contact, repeated at send time.
- Opt-out suppression for calls and messages.
- Configurable inbound IVR menus, forwarding, voicemail, and closed messages.
- Dashboard and Telegram-based operations.
- Authenticated carrier webhooks and role-based Telegram access.
- No collection of OTPs, passcodes, card numbers, SSNs, or other identity secrets.

## Features

### Inbound IVR
- Database-driven menus and keypad options.
- Configurable inbound modes: IVR, call forwarding, voicemail, or closed message.
- Business-hours and after-hours handling.
- Menu actions for dialing, submenus, voicemail, messages, opt-out, and repeating a menu.
- Warm transfers with an agent whisper, caller exit option, and voicemail fallback.
- Optional return to the menu after an agent call.

### Consent-first outbound campaigns
- Appointment reminders and surveys through supported voice, SMS, and WhatsApp channels.
- Three send-time checks: recipient is not opted out, has consent for the specific purpose and channel, and is within the configured contact window.
- Separate consent for voice, SMS, and WhatsApp.
- E.164 phone-number normalization for suppression matching.
- Background campaign runner with a SQLite single-flight lock.
- Press 0 warm transfer to an agent during reminder calls.
- `STOP` opt-out and `START` re-subscription handling for SMS and WhatsApp.

### Dashboard and reporting
- Campaign and inbound-mode controls.
- Message log with direction and delivery status.
- DTMF survey results, question breakdowns, and CSV export.
- Phone-number validation using offline `libphonenumber` data, cross-checked against consent and opt-out records.
- Amazon Polly voice selection and answering-machine detection (AMD) settings.
- Optional PGP-encrypted exports for CSV files containing personal information.

### Telegram operator console
- Inline-keyboard controls for stats, campaign launch/pause, recipients, opt-outs, inbound mode, and phone validation.
- Per-Telegram-ID allowlist and roles: viewer, operator, and admin.
- Audited actions, rate limiting, and localized command menus.
- English, Spanish, French, Portuguese, and German.
- Optional paid console access through Telegram Stars or Crypto Pay, depending on configuration.
- Phone-number masking in bot views and alerts.

### Security and privacy
- Carrier webhook signature verification.
- SQLite storage, with optional SQLCipher encryption at rest.
- If SQLCipher encryption is configured as required but the driver is missing, the application is designed to refuse an unencrypted start.
- Optional PGP encryption for exports containing personal information.
- Recording is off by default; when enabled, a disclosure is played before audio capture.
- No WhatsApp/Telegram presence lookup or profile scraping.

## Architecture

```text
Voice / SMS / WhatsApp Providers
            |
            v
      Provider Adapter
            |
            v
 Flask Web App / Webhooks / IVR / Dashboard
            |
      +-----+------+
      |            |
      v            v
 Consent, Hours,   Telegram Operator Bot
 Jobs, Validation, (allowlist + roles)
 Crypto
      |
      v
 SQLite / optional SQLCipher
```

The application is documented as running the web app, carrier webhooks, and Telegram bot from one process using `python app.py`.

## Provider support

| Provider | SMS | Voice | WhatsApp | Notes |
| --- | --- | --- | --- | --- |
| Twilio | Yes | Yes - TwiML | Yes | Default backend in the project documentation |
| Telnyx | Yes | Yes - TeXML | Not listed | Voice uses a TeXML application |
| Plivo | Yes | Not listed | Not listed | SMS support documented |
| Vonage | Yes | Not listed | Not listed | SMS support documented |
| Console | Logs only | Logs only | Logs only | Local testing without provider charges |

Provider and channel availability depends on the implementation and configuration in your checked-out version.

## Requirements

The supplied project documentation identifies Flask, Python, SQLite, a Telegram bot, and provider integrations. It does **not** specify a complete pinned dependency list, exact Python version, or the full environment-variable schema. Confirm these details in the repository before deployment.

You may need credentials and configuration for whichever providers and optional services you enable, such as:

- Voice/SMS provider credentials and webhook configuration.
- Telegram bot token and approved operator Telegram IDs.
- Database and encryption settings.
- Optional PGP public key for encrypted exports.
- Optional Telegram Stars or Crypto Pay configuration if paid access is enabled.

## Setup

1. Clone your repository:

   ```bash
   git clone <YOUR-GITHUB-REPOSITORY-URL>
   cd <ConsentIVRSITORY-DIRECTORY>
   ```

2. Create and activate a Python virtual environment using the method appropriate for your operating system.

3. Install the dependencies listed by the repository (for example, from its `requirements.txt` if present).

4. Configure the environment variables documented by the project. Use the console provider first where available to test flows without sending real messages or placing calls.

5. Configure provider webhooks with the correct public HTTPS endpoint and ensure signature verification is enabled.

6. Start the application:

   ```bash
   python app.py
   ```

The command above is the startup command documented by the project. Exact dependency installation, environment-variable names, database initialization, and production server instructions should be taken from the actual repository files; they are not fully specified in the supplied project overview.

## Consent and compliance

ConsentIVR provides technical controls to support consent-based communication, but software controls do not by themselves guarantee legal compliance.

Before sending campaigns, verify that:

- You have documented permission for the intended purpose and channel.
- Suppression and opt-out lists are current and checked before each send.
- Calls and messages occur only during permitted contact windows.
- Recording disclosures and consent meet the laws applicable to your recipients and organization.
- Caller ID identifies a number you control and prompts truthfully identify your organization.
- Access to personal information, exports, logs, and encryption keys is restricted appropriately.

Applicable rules may include the TCPA, state call-recording laws, privacy requirements, and local equivalents. Obtain appropriate legal guidance for your use case.

## Responsible-use boundaries

ConsentIVR is designed for legitimate, consent-based communications. It intentionally excludes identity-secret collection and messaging-platform presence checks or profile scraping. The Telegram bot is an operator console, not a tool for discovering whether arbitrary phone numbers use a messaging service.

## Project links

- **Claude artifact:** https://metasonic.ca/blog_post.php?slug=consentivr-consent-first-voice-sms-whatsapp-platform
- **GitHub repository:** Add your repository URL here.
- **Issues and support:** Use the Issues tab in your GitHub repository once enabled.

## Status

This README describes the features in the supplied ConsentIVR project overview. Verify implementation details against the source code in your repository before relying on any feature in production.

---

### Badge notes

Replace the placeholder GitHub URLs (`MetaSonicTeam/ConsentIVR`) with your actual repository path. The badge set above covers:

- **License** - update `MIT` to match your actual license.
- **Python** - update `3.8+` to your minimum supported version.
- **Framework/runtime** - Flask, SQLite.
- **Integrations** - Telegram, Twilio, Telnyx, Plivo, Vonage.
- **Community** - PRs welcome.
- **Status** - active.

If you later add CI/CD, coverage, or Docker, add badges such as:

[![ConsentIVR](https://raw.githubusercontent.com/MetaSonicTeam/ConsentIVR/main/doc/ConsentIVR-logo/icons/favicon-32.png)](https://github.com/MetaSonicTeam/ConsentIVR)
[![codecov](https://codecov.io/gh/MetaSonicTeam/ConsentIVR/branch/main/graph/badge.svg)](https://codecov.io/gh/MetaSonicTeam/ConsentIVR)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
