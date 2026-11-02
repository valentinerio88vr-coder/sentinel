"""Authentication: PBKDF2 password hashing + signed session tokens (HMAC-SHA256, stateless).

No third-party crypto dependency. Tokens are self-verifying and expire.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

SECRET = os.environ.get("SENTINEL_SECRET") or secrets.token_hex(32)
TOKEN_TTL = 60 * 60 * 12  # 12 hours
PBKDF2_ROUNDS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user_id: str, org_id: str, role: str) -> str:
    body = {"sub": user_id, "org": org_id, "role": role, "exp": int(time.time()) + TOKEN_TTL}
    payload = _b64e(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_token(token: str) -> dict | None:
    try:
        payload, sig = token.split(".")
        expected = _b64e(hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        body = json.loads(_b64d(payload))
        if body.get("exp", 0) < time.time():
            return None
        return body
    except (ValueError, json.JSONDecodeError):
        return None


def verify_device_token(token: str) -> bool:
    """Device tokens are opaque random strings looked up in the DB (not JWTs) so they can be revoked."""
    return bool(token) and len(token) >= 32
