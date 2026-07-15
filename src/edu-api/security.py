"""Password hashing and JWT helpers for self-hosted authentication."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

import jwt

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32
USERNAME_PATTERN = re.compile(r"^[\w.-]+$", re.UNICODE)


def normalize_username(value: str) -> str:
    value = value.strip().casefold()
    if not USERNAME_PATTERN.fullmatch(value):
        raise ValueError("账户名只能包含文字、数字、下划线、点或短横线")
    return value


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_BYTES,
    )
    return "$".join(
        (
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_text, expected_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_text.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(
    *, user_id: str, username: str, secret: str, expires_minutes: int
) -> tuple[str, int]:
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=expires_minutes)
    payload = {
        "sub": user_id,
        "username": username,
        "type": "access",
        "iss": "edu-agent",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm="HS256"), int(expires_delta.total_seconds())


def decode_access_token(token: str, secret: str) -> dict:
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        issuer="edu-agent",
        options={"require": ["sub", "exp", "iat", "iss", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload
