from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import Header, HTTPException

from app.config import get_settings


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _signature(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def create_token(email: str) -> str:
    settings = get_settings()
    normalized = email.strip().lower()
    now = int(time.time())
    payload = {
        "sub": normalized,
        "iat": now,
        "exp": now + settings.auth_token_ttl_seconds,
    }
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{encoded_payload}.{_signature(encoded_payload, settings.auth_secret)}"


def verify_token(token: str) -> str:
    settings = get_settings()
    try:
        encoded_payload, provided_signature = token.split(".", 1)
        expected_signature = _signature(encoded_payload, settings.auth_secret)
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise ValueError("bad signature")
        payload = json.loads(_b64decode(encoded_payload))
    except (ValueError, json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid session token")

    email = str(payload.get("sub", "")).strip().lower()
    if email != settings.allowed_login_email.lower():
        raise HTTPException(status_code=403, detail="Email is not allowed")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Session expired")
    return email


def require_auth(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return verify_token(authorization.removeprefix("Bearer ").strip())

