"""Argon2 password verification and tightly scoped JWT creation/validation."""
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pydantic import SecretStr

from app.config import Settings

logger = logging.getLogger(__name__)
password_hasher = PasswordHash.recommended()


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    return password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    # Unknown accounts also perform Argon2 verification to reduce timing differences.
    try:
        valid = password_hasher.verify(password, stored_hash or dummy_password_hash())
    except (UnknownHashError, ValueError):
        password_hasher.verify(password, dummy_password_hash())
        return False
    return stored_hash is not None and valid


class TokenService:
    def __init__(self, config: Settings):
        self._secret = config.jwt_secret_key or SecretStr(secrets.token_urlsafe(48))
        self._algorithm = config.jwt_algorithm
        self.expires_in = config.access_token_expire_minutes * 60
        if config.jwt_secret_key is None:
            logger.warning(
                "Development-only ephemeral JWT key in use; tokens expire on restart. "
                "Set JWT_SECRET_KEY for a stable key and APP_ENV=production for deployment."
            )

    def issue(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=self.expires_in)},
            self._secret.get_secret_value(), algorithm=self._algorithm,
        )

    def subject(self, token: str) -> int:
        try:
            payload = jwt.decode(
                token, self._secret.get_secret_value(), algorithms=[self._algorithm],
                options={"require": ["sub", "iat", "exp"]},
            )
        except (TypeError, ValueError, OverflowError) as exc:
            # Malformed claim types must fail authentication, not cause HTTP 500.
            raise InvalidTokenError("Invalid claims") from exc
        subject = payload["sub"]
        if not isinstance(subject, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", subject):
            raise InvalidTokenError("Invalid subject")
        user_id = int(subject)
        if user_id > 2**63 - 1:
            raise InvalidTokenError("Invalid subject")
        if (
            type(payload["iat"]) is not int or type(payload["exp"]) is not int
            or payload["exp"] <= payload["iat"]
        ):
            raise InvalidTokenError("Invalid timestamps")
        return user_id
