# itkb/api/auth.py
from __future__ import annotations
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


def make_session_token(api_key: str, secret: str, ttl_days: int = 30) -> str:
    expiry = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
    payload = f"{api_key}:{expiry}"
    return f"{payload}.{_sign(payload, secret)}"


def verify_session_token(token: str, api_key: str, secret: str) -> bool:
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        return False
    if not secrets.compare_digest(sig, _sign(payload, secret)):
        return False
    try:
        stored_key, expiry = payload.split(":", 1)
    except ValueError:
        return False
    if stored_key != api_key:
        return False
    try:
        exp = datetime.fromisoformat(expiry)
    except ValueError:
        return False
    return exp > datetime.now(timezone.utc)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
