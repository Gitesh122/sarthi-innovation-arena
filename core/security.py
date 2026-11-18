"""Password hashing (PBKDF2-SHA256, standard library only) and helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(it))
        return hmac.compare_digest(dk, base64.b64decode(digest))
    except Exception:
        return False


def generate_password() -> str:
    """Readable one-time password, e.g. 'Kite-4827-Mx'."""
    words = ["Lotus", "Tiger", "Robot", "Spark", "Orbit", "Pixel", "Kite", "Delta", "Nova", "Prism", "Atlas", "Comet"]
    up, lo = "ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghjkmnpqrstuvwxyz"
    return f"{secrets.choice(words)}-{secrets.randbelow(9000) + 1000}-{secrets.choice(up)}{secrets.choice(lo)}"


def strong_enough(pw: str) -> bool:
    return len(pw) >= 8 and bool(re.search(r"[A-Za-z]", pw)) and bool(re.search(r"\d", pw))


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+0-9][0-9\s-]{8,15}$")


def valid_email(e: str) -> bool:
    return bool(EMAIL_RE.match(e or ""))


def valid_phone(p: str) -> bool:
    return bool(PHONE_RE.match(p or ""))
