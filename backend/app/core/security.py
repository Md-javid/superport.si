import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
    return hmac.compare_digest(candidate, digest_hex)


def create_access_token(user_id: int, remember: bool = False) -> str:
    settings = get_settings()
    minutes = settings.access_token_minutes * (14 if remember else 1)
    payload = {"sub": str(user_id), "typ": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
        if payload.get("typ", "access") != "access":  # verification and reset tokens are never valid sessions
            return None
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def pw_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:12]


def create_purpose_token(purpose: str, subject: int, minutes: int, extra: dict | None = None) -> str:
    payload = {"typ": purpose, "sub": str(subject), "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes), **(extra or {})}
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def decode_purpose_token(token: str, purpose: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == purpose else None
