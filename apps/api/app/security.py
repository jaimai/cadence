import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet

from app.config import get_settings

_hasher = PasswordHasher()
SESSION_COOKIE = "cadence_session"
SESSION_DAYS = 30
API_KEY_PREFIX = "cad_"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, ValueError):
        return False


def _encode(payload: dict[str, Any], ttl: timedelta) -> str:
    payload = {**payload, "exp": datetime.now(UTC) + ttl}
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


def _decode(token: str, typ: str) -> dict[str, Any] | None:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data if data.get("typ") == typ else None


def create_session_token(user_id: uuid.UUID, workspace_id: uuid.UUID) -> str:
    return _encode(
        {"typ": "session", "sub": str(user_id), "ws": str(workspace_id)},
        timedelta(days=SESSION_DAYS),
    )


def read_session_token(token: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    data = _decode(token, "session")
    if not data:
        return None
    return uuid.UUID(data["sub"]), uuid.UUID(data["ws"])


def create_oauth_state(workspace_id: uuid.UUID, platform: str, via_link: bool = False) -> str:
    payload = {"typ": "oauth", "ws": str(workspace_id), "p": platform, "n": secrets.token_hex(8)}
    if via_link:
        payload["l"] = 1
    return _encode(payload, timedelta(minutes=10))


def read_oauth_state(state: str, platform: str) -> tuple[uuid.UUID, bool] | None:
    """Returns (workspace id, started from a QR link) or None if invalid."""
    data = _decode(state, "oauth")
    if not data or data.get("p") != platform:
        return None
    return uuid.UUID(data["ws"]), bool(data.get("l"))


def _fernet() -> Fernet:
    s = get_settings()
    key = (
        s.encryption_key
        or base64.urlsafe_b64encode(hashlib.sha256(s.secret_key.encode()).digest()).decode()
    )
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (plaintext, display prefix, sha256 hash). Only the hash is stored."""
    key = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return key, key[:12], hash_api_key(key)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
