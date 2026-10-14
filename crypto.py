"""
PGP/GPG encryption helper.

We shell out to the system `gpg` binary (OpenPGP) rather than add a Python
crypto dependency, so output opens with the operator's normal GPG keychain.
Encryption is PUBLIC-KEY only: this process can encrypt PII that leaves the
system (e.g. a results CSV) to a configured recipient key, but it holds no
private key and cannot decrypt — the key holder decrypts offline.

Configure with PGP_PUBLIC_KEY_FILE (an ASCII-armored public key, .asc).

NOTE: This is for data IN TRANSIT / at export. It is deliberately NOT used to
encrypt phone-number columns in the database: PGP ciphertext is
non-deterministic, which would break opt-out exact-match suppression, UNIQUE
constraints and joins. For true at-rest DB encryption use SQLCipher or disk
encryption (see README).
"""

import logging
import shutil
import subprocess

from config import Config

log = logging.getLogger(__name__)


def gpg_available() -> bool:
    return bool(shutil.which("gpg"))


def exports_enabled() -> bool:
    """True if result exports should be PGP-encrypted."""
    return bool(Config.PGP_ENCRYPT_EXPORTS and Config.PGP_PUBLIC_KEY_FILE and gpg_available())


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt bytes to the configured recipient key; returns ASCII-armored
    OpenPGP output. Raises RuntimeError if gpg/key is missing or gpg fails."""
    if not Config.PGP_PUBLIC_KEY_FILE:
        raise RuntimeError("PGP_PUBLIC_KEY_FILE is not configured.")
    if not gpg_available():
        raise RuntimeError("gpg binary not found on PATH.")
    cmd = [
        "gpg", "--batch", "--yes", "--armor", "--no-tty",
        "--trust-model", "always",               # trust the supplied recipient key
        "--recipient-file", Config.PGP_PUBLIC_KEY_FILE,
        "--encrypt", "--output", "-",
    ]
    proc = subprocess.run(cmd, input=data, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("gpg encrypt failed: " + proc.stderr.decode(errors="replace").strip())
    return proc.stdout


def encrypt_text(text: str) -> str:
    return encrypt_bytes(text.encode("utf-8")).decode("ascii")
