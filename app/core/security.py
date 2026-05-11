"""Small authentication helpers for the MVP."""

import base64
import hmac
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password for demo user storage.

    This keeps the MVP dependency-light. Replace with passlib/bcrypt before production auth.
    """
    return sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Compare a plain password with a stored hash."""
    return hmac.compare_digest(hash_password(password), password_hash)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(subject: dict[str, Any]) -> str:
    """Create a signed bearer token for Streamlit/API sessions.

    The token format is intentionally simple for the MVP. Swap it for JWT/OAuth2 before exposing this outside a
    trusted internal network.
    """
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {**subject, "exp": int(expires_at.timestamp())}
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.auth_secret_key.encode("utf-8"), encoded_payload.encode("ascii"), sha256).digest()
    return f"{encoded_payload}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Validate and decode a bearer token."""
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        encoded_payload.encode("ascii"),
        sha256,
    ).digest()
    try:
        provided_signature = _b64url_decode(encoded_signature)
    except ValueError:
        return None
    if not hmac.compare_digest(expected_signature, provided_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (ValueError, TypeError):
        return None
    if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
        return None
    return payload
