"""TOTP (RFC 6238) two-factor auth, implemented on stdlib only.

Compatible with Google Authenticator, Authy, 1Password, etc.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse

DIGITS = 6
STEP = 30
WINDOW = 1  # accept the previous/next step to tolerate clock drift


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** DIGITS)).zfill(DIGITS)


def now_code(secret: str, at: int | None = None) -> str:
    return _hotp(secret, int((at or time.time()) // STEP))


def verify(secret: str, code: str, at: int | None = None) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return False
    counter = int((at or time.time()) // STEP)
    for drift in range(-WINDOW, WINDOW + 1):
        if hmac.compare_digest(_hotp(secret, counter + drift), code):
            return True
    return False


def provisioning_uri(secret: str, account: str, issuer: str = "Sentinel") -> str:
    label = urllib.parse.quote(f"{issuer}:{account}")
    params = urllib.parse.urlencode({
        "secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": DIGITS, "period": STEP,
    })
    return f"otpauth://totp/{label}?{params}"
